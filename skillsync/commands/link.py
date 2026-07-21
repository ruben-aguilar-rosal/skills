"""LINK command — activate selected top-level skill sets for native consumers.

`run_link` is the consumption lever (PLAN.md "Consumption"): for each requested
category directly under `skills/`, it creates or refreshes a category symlink
`<target>/<skill-set>` pointing at that directory. This preserves the nested layout
of every selected set rather than flattening individual skill folders. The target
dir defaults to `~/.agents/skills` but is configurable — tests point it at
`tmp_path` and the `SKILLSYNC_LINK_DIR` env var overrides it without touching the
real home.

The command also removes stale category symlinks that point directly into this
repository's `skills/` directory and were not selected. It never removes a regular
path, an external symlink, or a link into a deeper repository path.

This is DETERMINISTIC and filesystem-only — no git, no LLM, no network. Each
category resolves to exactly one of five planned actions, returned for the caller
to print:

- **create** — no path at the target slot yet; a fresh symlink is made;
- **update** — a symlink already there points elsewhere; it is repointed;
- **unchanged** — a symlink already points at the selected category; nothing to do;
- **conflict** — a REAL (non-symlink) path occupies the slot; it is skipped and
  warned, never clobbered, so a hand-managed category can't be silently destroyed;
- **remove** — a stale, repository-owned category symlink is deleted.

`dry_run=True` computes the same plan but performs no filesystem writes.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
    """One planned/performed link operation for a top-level skill set.

    `link_path` is the symlink slot under the target dir; `source` is the resolved
    category directory it points (or would point) at; `action` is the verdict.
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
    dry_run: bool = False,
) -> list[LinkAction]:
    """Activate selected direct children of `root/skills` in `target_dir`.

    Every requested name must resolve to an existing direct category directory under
    `skills/`. All selections are validated before `target_dir` is created or any
    link is modified, so a typo cannot trigger stale-link cleanup. Existing selected
    target slots follow the safe create/update/unchanged/conflict behavior. After
    planning them, stale top-level symlinks that resolve to direct children of this
    repository's `skills/` directory are removed unless selected. With
    `dry_run=True` no filesystem changes are made — not even creating `target_dir`.
    """
    sources = _selected_sources(root, skill_sets)
    skills_dir = (root / "skills").resolve()

    actions = [
        _action_for_selected(name, source, target_dir)
        for name, source in sorted(sources.items())
    ]
    actions.extend(_stale_actions(target_dir, skills_dir, set(sources)))

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        for action in actions:
            if action.action in ("create", "update"):
                _apply(action.link_path, action.source, action.action)
            elif action.action == "remove":
                action.link_path.unlink()
    return actions


def _selected_sources(root: Path, skill_sets: set[str]) -> dict[str, Path]:
    """Resolve and validate requested direct children of the repository skills dir."""
    if not skill_sets:
        raise LinkError("at least one --skill-set is required")

    skills_dir = (root / "skills").resolve()
    if not skills_dir.is_dir():
        raise LinkError(f"no skills directory found at {root / 'skills'}")

    sources: dict[str, Path] = {}
    invalid: list[str] = []
    for name in sorted(skill_sets):
        candidate = skills_dir / name
        if (
            not name
            or Path(name).name != name
            or not candidate.is_dir()
            or candidate.resolve().parent != skills_dir
        ):
            invalid.append(name)
            continue
        sources[name] = candidate.resolve()
    if invalid:
        joined = ", ".join(invalid)
        raise LinkError(f"unknown skill set(s): {joined}")
    return sources


def _action_for_selected(name: str, source: Path, target_dir: Path) -> LinkAction:
    """Plan the target slot for one selected category directory."""
    link_path = target_dir / name
    return LinkAction(name, link_path, source, _plan(link_path, source))


def _stale_actions(
    target_dir: Path, skills_dir: Path, selected: set[str]
) -> list[LinkAction]:
    """Plan removal of unselected symlinks owned by this repository's skill tree."""
    if not target_dir.is_dir():
        return []

    actions: list[LinkAction] = []
    for link_path in sorted(target_dir.iterdir(), key=lambda path: path.name):
        if link_path.name in selected or not link_path.is_symlink():
            continue
        source = link_path.resolve()
        if source.parent == skills_dir:
            actions.append(LinkAction(link_path.name, link_path, source, "remove"))
    return actions


def _plan(link_path: Path, source: Path) -> Action:
    """Classify the target slot into create/update/unchanged/conflict."""
    if link_path.is_symlink():
        # `resolve()` follows the link; compare against the resolved category dir.
        if link_path.resolve() == source:
            return "unchanged"
        return "update"
    if link_path.exists():
        # A real file/dir occupies the slot — never clobber it.
        return "conflict"
    return "create"


def _apply(link_path: Path, source: Path, action: Action) -> None:
    """Create or repoint the symlink at `link_path` to `source`."""
    if action == "update":
        link_path.unlink()
    link_path.symlink_to(source)
