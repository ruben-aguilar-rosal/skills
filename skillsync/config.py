"""Configuration layer: `sources.yaml` model and `profile.md` reader.

Functional core — these helpers parse and serialize data only. Unknown keys are
collected as warnings (return-and-log) rather than printed, so the imperative
shell decides how to surface them.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

_SOURCE_KEYS = {"repo", "ref", "skills", "watch", "ignore", "dest"}
_SKILL_KEYS = {"path", "synced_sha", "hold", "dest"}

# Default parent dir for a skill folder when neither the pin nor its source sets a
# `dest`. Skills land in `<dest>/<skill-name>/`.
DEFAULT_DEST = "skills"


class ConfigError(Exception):
    """Raised when the configuration cannot be loaded or parsed."""


@dataclass
class SkillPin:
    """One allowlisted skill: its subtree path and last-synced upstream SHA.

    `dest` overrides where this skill's folder is stored locally (the parent dir
    its name is appended to); `None` falls back to the source's `dest`, then the
    global default. Use it to group specific skills from different repos together.
    """

    path: str
    synced_sha: str | None
    hold: bool = False
    dest: str | None = None


@dataclass
class Source:
    """One upstream repo: what to fetch (`ref`) and its pinned skills.

    `watch` lists upstream folders to discover skills in: on a sync run, every
    subfolder under a watched folder that contains a `SKILL.md` is checked against
    the pins, and any not-yet-tracked one is surfaced for adoption. `ignore` is the
    durable "no" list — discovered paths the author has rejected, so they stop being
    surfaced. Both default to empty (a source with no `watch` behaves exactly as
    before: only its explicit `skills` are synced).

    `dest` is the default parent dir for this source's skill folders (each skill's
    name is appended); an individual pin's `dest` overrides it, and `None` falls
    back to the global default.
    """

    repo: str
    ref: str
    skills: list[SkillPin]
    watch: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    dest: str | None = None


@dataclass
class Config:
    """Parsed `sources.yaml`. `warnings` is metadata, excluded from equality."""

    sources: list[Source]
    warnings: list[str] = field(default_factory=list, compare=False)


def skill_dest(source: Source, pin: SkillPin) -> str:
    """Resolve the parent dir a skill's folder is stored under.

    Precedence: the pin's own `dest`, then its source's `dest`, then the global
    `DEFAULT_DEST`. The skill's folder name is appended to this by the layout.
    """
    return pin.dest or source.dest or DEFAULT_DEST


def load_config(path: Path) -> Config:
    """Parse `sources.yaml` into a Config, collecting unknown-key warnings."""
    if not path.exists():
        raise ConfigError(
            f"Configuration file not found: {path}. "
            "Create a sources.yaml with a top-level 'sources:' list."
        )

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Expected a mapping at the top level of {path}.")

    warnings: list[str] = []
    sources = [
        _parse_source(entry, index, warnings)
        for index, entry in enumerate(raw.get("sources") or [])
    ]
    for warning in warnings:
        _log.warning(warning)
    return Config(sources=sources, warnings=warnings)


def save_config(config: Config, path: Path) -> None:
    """Serialize a Config to `sources.yaml` with stable key order."""
    payload = {"sources": [_dump_source(source) for source in config.sources]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def _dump_source(source: Source) -> dict[str, Any]:
    """Serialize one Source, emitting `dest` only when it is set."""
    out: dict[str, Any] = {
        "repo": source.repo,
        "ref": source.ref,
        "watch": list(source.watch),
        "ignore": list(source.ignore),
    }
    if source.dest is not None:
        out["dest"] = source.dest
    out["skills"] = [_dump_skill(pin) for pin in source.skills]
    return out


def _dump_skill(pin: SkillPin) -> dict[str, Any]:
    """Serialize one SkillPin, emitting `dest` only when it is set."""
    out: dict[str, Any] = {
        "path": pin.path,
        "synced_sha": pin.synced_sha,
        "hold": pin.hold,
    }
    if pin.dest is not None:
        out["dest"] = pin.dest
    return out


def load_profile(path: Path) -> str:
    """Read `profile.md`, returning an empty string if it is absent."""
    if not path.exists():
        return ""
    return path.read_text()


def _parse_source(entry: dict[str, Any], index: int, warnings: list[str]) -> Source:
    """Build a Source from a raw mapping, recording unknown keys."""
    for key in set(entry) - _SOURCE_KEYS:
        warnings.append(f"sources[{index}]: ignoring unknown key {key!r}")
    skills = [
        _parse_skill(skill, index, skill_index, warnings)
        for skill_index, skill in enumerate(entry.get("skills") or [])
    ]
    return Source(
        repo=entry["repo"],
        ref=entry["ref"],
        skills=skills,
        watch=list(entry.get("watch") or []),
        ignore=list(entry.get("ignore") or []),
        dest=entry.get("dest"),
    )


def _parse_skill(
    entry: dict[str, Any], source_index: int, skill_index: int, warnings: list[str]
) -> SkillPin:
    """Build a SkillPin from a raw mapping, recording unknown keys."""
    for key in set(entry) - _SKILL_KEYS:
        warnings.append(
            f"sources[{source_index}].skills[{skill_index}]: "
            f"ignoring unknown key {key!r}"
        )
    return SkillPin(
        path=entry["path"],
        synced_sha=entry.get("synced_sha"),
        hold=entry.get("hold", False),
        dest=entry.get("dest"),
    )
