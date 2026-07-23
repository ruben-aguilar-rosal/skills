"""LINK command — expose selected skills as direct links for native consumers.

For each selected top-level category under ``skills/``, ``run_link`` discovers its
skill folders and creates a direct ``<target>/<skill-name>`` symlink for each one.
Claude Code only discovers immediate children of its skills directory, so categories
must be flattened at the link boundary while the repository retains its organized
nested layout.

By default the command safely migrates old category links and reconciles stale direct
links it owns. With append mode, it only creates or refreshes selected links and leaves
all unselected target entries alone. A link is owned when it either points to a direct
child of this repository's ``skills/`` directory (the legacy category layout), or its
basename matches a known skill name and it points at that skill folder. Real paths,
external symlinks, and repository links with noncanonical names are never clobbered or
removed.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skillsync.layout import SkillLayout, discover_skills

# Env var that overrides the default target dir, so the real home is never touched
# under test. The CLI reads it via `default_target_dir`.
_TARGET_DIR_ENV = "SKILLSYNC_LINK_DIR"

# Where shared Agent Skills are consumed from when nothing overrides it.
_DEFAULT_TARGET_DIR = Path.home() / ".agents" / "skills"

Action = Literal["create", "update", "unchanged", "conflict", "remove"]


class LinkError(ValueError):
    """The requested skill-set selection cannot be linked safely."""


@dataclass(frozen=True)
class LinkAction:
    """One planned/performed direct skill link operation.

    ``link_path`` is the link slot under the target dir; ``source`` is the resolved
    skill directory it points (or would point) at; ``action`` is the verdict.
    """

    name: str
    link_path: Path
    source: Path
    action: Action


def default_target_dir() -> Path:
    """Return `$SKILLSYNC_LINK_DIR`, or the shared `~/.agents/skills` directory."""
    override = os.environ.get(_TARGET_DIR_ENV)
    return Path(override) if override else _DEFAULT_TARGET_DIR


def run_link(
    root: Path,
    *,
    target_dir: Path,
    skill_sets: set[str],
    append: bool = False,
    dry_run: bool = False,
) -> list[LinkAction]:
    """Expose every skill in selected direct children of ``root/skills``.

    All selected categories, their discovered skills, and their global names are
    validated before ``target_dir`` is created or any link changes. Selected skills
    are linked directly at ``target_dir / <skill-name>``. By default repository-owned
    links outside the selection and legacy category links are removed; ``append=True``
    preserves them. With ``dry_run=True`` no filesystem changes are made — not even
    creating ``target_dir``.
    """
    selected = _selected_skills(root, skill_sets)
    skills_dir = (root / "skills").resolve()
    known_skills = {layout.root.resolve() for layout in discover_skills(root)}

    actions = [
        _action_for_selected(name, source, target_dir)
        for name, source in sorted(selected.items())
    ]
    if not append:
        actions.extend(
            _stale_actions(target_dir, skills_dir, known_skills, set(selected))
        )

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        for action in actions:
            if action.action in ("create", "update"):
                _apply(action.link_path, action.source, action.action)
            elif action.action == "remove":
                action.link_path.unlink()
    return actions


def _selected_skills(root: Path, skill_sets: set[str]) -> dict[str, Path]:
    """Validate selected categories and return their skills keyed by global name."""
    if not skill_sets:
        raise LinkError("at least one --skill-set is required")

    skills_dir = (root / "skills").resolve()
    if not skills_dir.is_dir():
        raise LinkError(f"no skills directory found at {root / 'skills'}")

    invalid = [
        name
        for name in sorted(skill_sets)
        if not name
        or Path(name).name != name
        or not (skills_dir / name).is_dir()
        or (skills_dir / name).resolve().parent != skills_dir
    ]
    if invalid:
        raise LinkError(f"unknown skill set(s): {', '.join(invalid)}")

    selected_layouts = [
        layout
        for layout in discover_skills(root)
        if layout.root.resolve().relative_to(skills_dir).parts[0] in skill_sets
    ]
    if not selected_layouts:
        raise LinkError("selected skill set(s) contain no skill folders")

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
        raise LinkError(f"duplicate skill name(s) across selected sets: {details}")

    return {name: layouts[0].root.resolve() for name, layouts in by_name.items()}


def _action_for_selected(name: str, source: Path, target_dir: Path) -> LinkAction:
    """Plan the target slot for one selected skill."""
    link_path = target_dir / name
    return LinkAction(name, link_path, source, _plan(link_path, source))


def _stale_actions(
    target_dir: Path,
    skills_dir: Path,
    known_skills: set[Path],
    selected: set[str],
) -> list[LinkAction]:
    """Plan removal of stale direct or legacy category links owned by this repo."""
    if not target_dir.is_dir():
        return []

    actions: list[LinkAction] = []
    for link_path in sorted(target_dir.iterdir(), key=lambda path: path.name):
        if link_path.name in selected or not link_path.is_symlink():
            continue
        source = link_path.resolve()
        legacy_category = source.parent == skills_dir
        direct_skill = source in known_skills and link_path.name == source.name
        if legacy_category or direct_skill:
            actions.append(LinkAction(link_path.name, link_path, source, "remove"))
    return actions


def _plan(link_path: Path, source: Path) -> Action:
    """Classify the target slot into create/update/unchanged/conflict."""
    if link_path.is_symlink():
        if link_path.resolve() == source:
            return "unchanged"
        return "update"
    if link_path.exists():
        return "conflict"
    return "create"


def _apply(link_path: Path, source: Path, action: Action) -> None:
    """Create or repoint the symlink at ``link_path`` to ``source``."""
    if action == "update":
        link_path.unlink()
    link_path.symlink_to(source)
