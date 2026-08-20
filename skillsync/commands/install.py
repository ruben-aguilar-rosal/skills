"""INSTALL command — copy selected skills into the agent skills directories.

For each selected top-level category under ``skills/``, ``run_install`` discovers its
skill folders and writes a plain ``<target>/<skill-name>`` directory for each one, in
every target directory. Claude Code only discovers immediate children of its skills
dir, so categories are flattened at the install boundary while the repository keeps
its organized nested layout.

Copies, not symlinks: a symlinked skill resolves to its real path inside this
repository, so consumers see repo internals and behave differently depending on where
the repo lives. A copy is just a directory. The trade-off is that an installed skill
is a SNAPSHOT — re-run the command after changing a skill, and use ``--dry-run`` to
see which copies are stale.

Repository bookkeeping stays behind: ``.upstream/``, ``.generated/`` and
``adaptation.md`` record how a skill is maintained, not how it is used.

Each copy carries a ``.skillsync-install.json`` marker holding its source folder and a
digest of the installed files. The marker is what makes a copy recognizable later: it
identifies the copies this repository owns, so unchanged ones are left alone and
unselected ones can be removed. A directory without a marker is never clobbered or
removed. Symlinks from the earlier link-based releases — per-skill and per-category
alike — are migrated to copies.
"""

import hashlib
import json
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Literal

from skillsync.layout import SkillLayout, discover_skills, write_file

# Env var that overrides the default target dirs (os.pathsep-separated), so the real
# home is never touched under test. The CLI reads it via `default_target_dirs`.
_TARGET_DIRS_ENV = "SKILLSYNC_INSTALL_DIR"

# Where shared Agent Skills are consumed from when nothing overrides it.
_DEFAULT_TARGET_DIRS = (
    Path.home() / ".agents" / "skills",
    Path.home() / ".claude" / "skills",
)

# Ownership marker written inside every installed copy.
MARKER_NAME = ".skillsync-install.json"

# Skill-folder entries that are repository bookkeeping, not part of the usable skill.
_EXCLUDED_ROOT_NAMES = frozenset({".upstream", ".generated", "adaptation.md"})

Action = Literal["create", "update", "unchanged", "conflict", "remove"]

# One installable file: its path relative to the skill folder, and where to read it.
Payload = list[tuple[str, Path]]


class InstallError(ValueError):
    """The requested skill-set selection cannot be installed safely."""


@dataclass(frozen=True)
class InstallAction:
    """One planned/performed skill copy operation.

    ``path`` is the copy's slot under a target dir (its parent IS that target dir);
    ``source`` is the skill directory it was copied (or would be copied) from;
    ``action`` is the verdict.
    """

    name: str
    path: Path
    source: Path
    action: Action


def default_target_dirs() -> list[Path]:
    """Return `$SKILLSYNC_INSTALL_DIR` split on `os.pathsep`, else the two defaults.

    The defaults are `~/.agents/skills` (shared Agent Skills) and `~/.claude/skills`
    (Claude Code), so one run keeps both consumers in step.
    """
    override = os.environ.get(_TARGET_DIRS_ENV)
    if not override:
        return _dedupe(_DEFAULT_TARGET_DIRS)
    return _dedupe(Path(entry) for entry in override.split(os.pathsep) if entry)


def run_install(
    root: Path,
    *,
    target_dirs: list[Path],
    skill_sets: set[str],
    append: bool = False,
    dry_run: bool = False,
) -> list[InstallAction]:
    """Copy every skill in selected direct children of ``root/skills`` to each target.

    All selected categories, their discovered skills, and their global names are
    validated before any target dir is created or any copy changes. A selected skill
    lands at ``target_dir / <skill-name>``. By default copies this repository owns
    that fall outside the selection — and legacy symlinks — are removed; ``append=True``
    preserves them. With ``dry_run=True`` no filesystem changes are made, so the
    returned verdicts are a report of what is missing or stale.
    """
    targets = _dedupe(target_dirs)
    if not targets:
        raise InstallError("at least one target directory is required")

    selected = _selected_skills(root, skill_sets)
    skills_dir = (root / "skills").resolve()
    known_skills = {layout.root.resolve() for layout in discover_skills(root)}
    payloads = {name: _payload(source) for name, source in selected.items()}
    digests = {name: _digest(payload) for name, payload in payloads.items()}

    actions: list[InstallAction] = []
    for target_dir in targets:
        actions.extend(
            InstallAction(
                name, target_dir / name, source, _plan(target_dir / name, digests[name])
            )
            for name, source in sorted(selected.items())
        )
        if not append:
            actions.extend(
                _stale_actions(target_dir, skills_dir, known_skills, set(selected))
            )

    if dry_run:
        return actions

    for target_dir in targets:
        target_dir.mkdir(parents=True, exist_ok=True)
    for action in actions:
        if action.action in ("create", "update"):
            _install(
                action.path,
                action.source,
                payloads[action.name],
                digests[action.name],
            )
        elif action.action == "remove":
            _remove(action.path)
    return actions


def group_by_target(actions: list[InstallAction]) -> list[tuple[Path, list[InstallAction]]]:
    """Group actions by the target dir they belong to, preserving run order."""
    return [
        (target_dir, list(group))
        for target_dir, group in groupby(actions, key=lambda action: action.path.parent)
    ]


def _dedupe(paths: Iterable[Path]) -> list[Path]:
    """Drop target dirs that point at the same place, keeping the first spelling.

    Compares resolved paths, not names: `~/.claude/skills` is often itself a symlink
    to a shared agent skills dir, and installing into both spellings would copy every
    skill twice into one directory.
    """
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _selected_skills(root: Path, skill_sets: set[str]) -> dict[str, Path]:
    """Validate selected categories and return their skills keyed by global name."""
    if not skill_sets:
        raise InstallError("at least one --skill-set is required")

    skills_dir = (root / "skills").resolve()
    if not skills_dir.is_dir():
        raise InstallError(f"no skills directory found at {root / 'skills'}")

    invalid = [
        name
        for name in sorted(skill_sets)
        if not name
        or Path(name).name != name
        or not (skills_dir / name).is_dir()
        or (skills_dir / name).resolve().parent != skills_dir
    ]
    if invalid:
        raise InstallError(f"unknown skill set(s): {', '.join(invalid)}")

    selected_layouts = [
        layout
        for layout in discover_skills(root)
        if layout.root.resolve().relative_to(skills_dir).parts[0] in skill_sets
    ]
    if not selected_layouts:
        raise InstallError("selected skill set(s) contain no skill folders")

    by_name: dict[str, list[SkillLayout]] = {}
    for layout in selected_layouts:
        by_name.setdefault(layout.name, []).append(layout)
    collisions = {
        name: layouts for name, layouts in by_name.items() if len(layouts) > 1
    }
    if collisions:
        details = "; ".join(
            f"{name}: {', '.join(str(layout.root.relative_to(root)) for layout in layouts)}"
            for name, layouts in sorted(collisions.items())
        )
        raise InstallError(f"duplicate skill name(s) across selected sets: {details}")

    return {name: layouts[0].root.resolve() for name, layouts in by_name.items()}


def _payload(source: Path) -> Payload:
    """Every file to install from a skill folder, sorted by relative path.

    Repository bookkeeping (`_EXCLUDED_ROOT_NAMES`) is dropped; everything else the
    skill ships — `SKILL.md`, `scripts/`, `references/`, assets — is installed.
    """
    files: Payload = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if rel.parts[0] in _EXCLUDED_ROOT_NAMES or not path.is_file():
            continue
        files.append((rel.as_posix(), path))
    return files


def _digest(payload: Payload) -> str:
    """A stable hash over the payload's relative paths and file contents.

    Recorded in the marker so a later run can tell an up-to-date copy (`unchanged`)
    from one whose source has moved on (`update`) without diffing two trees.
    """
    digest = hashlib.sha256()
    for rel, path in payload:
        content = path.read_bytes()
        digest.update(f"{rel}\0{len(content)}\0".encode())
        digest.update(content)
    return digest.hexdigest()


def _plan(dest: Path, digest: str) -> Action:
    """Classify a selected skill's target slot into create/update/unchanged/conflict."""
    if dest.is_symlink():
        return "update"  # a link from the symlink era: replace it with a copy
    if not dest.exists():
        return "create"
    marker = _read_marker(dest)
    if marker is None:
        return "conflict"
    return "unchanged" if marker.get("digest") == digest else "update"


def _stale_actions(
    target_dir: Path,
    skills_dir: Path,
    known_skills: set[Path],
    selected: set[str],
) -> list[InstallAction]:
    """Plan removal of unselected copies and legacy links this repository owns."""
    if not target_dir.is_dir():
        return []

    actions: list[InstallAction] = []
    for path in sorted(target_dir.iterdir(), key=lambda entry: entry.name):
        if path.name in selected:
            continue
        source = _owned_source(path, skills_dir, known_skills)
        if source is not None:
            actions.append(InstallAction(path.name, path, source, "remove"))
    return actions


def _owned_source(
    path: Path, skills_dir: Path, known_skills: set[Path]
) -> Path | None:
    """The repository folder `path` exposes, or None when this repo does not own it.

    An installed copy is owned when its marker names a source under this repo's
    `skills/` dir and the copy still sits under that skill's own name — so a copy
    renamed by hand is left alone, while one whose skill was renamed or deleted
    upstream is still cleaned up. A symlink is owned when it points at a direct child
    of `skills/` (the legacy per-category layout) or at a known skill folder under
    that skill's name. Real paths and external symlinks are owned by nobody.
    """
    if path.is_symlink():
        source = path.resolve()
        legacy_category = source.parent == skills_dir
        direct_skill = source in known_skills and path.name == source.name
        return source if legacy_category or direct_skill else None

    marker = _read_marker(path)
    if marker is None:
        return None
    source = Path(str(marker.get("source", "")))
    if source.name != path.name or not source.is_relative_to(skills_dir):
        return None
    return source


def installed_from(path: Path) -> Path | None:
    """The skill folder the copy at `path` was installed from, or None if not a copy.

    The read side of the ownership marker, for callers (the status report) that only
    need to know whether a target slot holds this repository's skill.
    """
    marker = _read_marker(path)
    if marker is None:
        return None
    return Path(str(marker.get("source", "")))


def _read_marker(path: Path) -> dict[str, object] | None:
    """The install marker inside `path`, or None when `path` is not an owned copy.

    An unreadable or malformed marker reads as "not ours", so a damaged directory is
    reported as a conflict rather than silently overwritten.
    """
    if path.is_symlink() or not path.is_dir():
        return None
    marker = path / MARKER_NAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _install(dest: Path, source: Path, payload: Payload, digest: str) -> None:
    """Replace `dest` with a fresh copy of `source`, plus its ownership marker.

    The old copy is removed rather than written over, so a file the source no longer
    ships cannot survive in the installed skill.
    """
    _remove(dest)
    for rel, path in payload:
        write_file(dest / rel, path.read_bytes())
    marker = {"digest": digest, "source": str(source)}
    write_file(dest / MARKER_NAME, json.dumps(marker, indent=2, sort_keys=True) + "\n")


def _remove(dest: Path) -> None:
    """Delete an owned copy or legacy link at `dest`, if anything is there."""
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
