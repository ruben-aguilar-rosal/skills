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

_SOURCE_KEYS = {"repo", "ref", "skills"}
_SKILL_KEYS = {"path", "synced_sha", "hold"}


class ConfigError(Exception):
    """Raised when the configuration cannot be loaded or parsed."""


@dataclass
class SkillPin:
    """One allowlisted skill: its subtree path and last-synced upstream SHA."""

    path: str
    synced_sha: str | None
    hold: bool = False


@dataclass
class Source:
    """One upstream repo: what to fetch (`ref`) and its pinned skills."""

    repo: str
    ref: str
    skills: list[SkillPin]


@dataclass
class Config:
    """Parsed `sources.yaml`. `warnings` is metadata, excluded from equality."""

    sources: list[Source]
    warnings: list[str] = field(default_factory=list, compare=False)


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
    payload = {
        "sources": [
            {
                "repo": source.repo,
                "ref": source.ref,
                "skills": [
                    {
                        "path": pin.path,
                        "synced_sha": pin.synced_sha,
                        "hold": pin.hold,
                    }
                    for pin in source.skills
                ],
            }
            for source in config.sources
        ]
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


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
    return Source(repo=entry["repo"], ref=entry["ref"], skills=skills)


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
    )
