"""LINK command — symlink skill folders into the native skills dir.

`run_link` is the consumption lever (PLAN.md "Consumption"): for each skill folder
under `skills/`, it creates or refreshes a symlink `<target>/<name>` pointing at the
skill folder, so Claude Code loads the adapted skill from this repo. The target dir
defaults to `~/.claude/skills` but is configurable — tests point it at `tmp_path`
and the `SKILLSYNC_LINK_DIR` env var overrides it without touching the real home.

This is DETERMINISTIC and filesystem-only — no git, no LLM, no network. Each skill
resolves to exactly one of four planned actions, returned for the caller to print:

- **create** — no path at the target slot yet; a fresh symlink is made;
- **update** — a symlink already there points elsewhere; it is repointed;
- **unchanged** — a symlink already points at the skill folder; nothing to do;
- **conflict** — a REAL (non-symlink) path occupies the slot; it is skipped and
  warned, never clobbered, so a hand-managed skill can't be silently destroyed.

`dry_run=True` computes the same plan but performs no filesystem writes.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skillsync.layout import discover_skills

# Env var that overrides the default target dir, so the real home is never touched
# under test. The CLI reads it via `default_target_dir`.
_TARGET_DIR_ENV = "SKILLSYNC_LINK_DIR"

# Where skills are consumed from when nothing overrides it (PLAN.md "Consumption").
_DEFAULT_TARGET_DIR = Path.home() / ".claude" / "skills"

Action = Literal["create", "update", "unchanged", "conflict"]


@dataclass(frozen=True)
class LinkAction:
    """One planned/performed link operation for a single skill folder.

    `link_path` is the symlink slot under the target dir; `source` is the resolved
    skill folder it points (or would point) at; `action` is the verdict.
    """

    name: str
    link_path: Path
    source: Path
    action: Action


def default_target_dir() -> Path:
    """Return the link target dir: `$SKILLSYNC_LINK_DIR` if set, else `~/.claude/skills`."""
    override = os.environ.get(_TARGET_DIR_ENV)
    return Path(override) if override else _DEFAULT_TARGET_DIR


def run_link(
    root: Path,
    *,
    target_dir: Path,
    dry_run: bool = False,
) -> list[LinkAction]:
    """Symlink each skill folder under `root/skills/` into `target_dir`.

    Returns one `LinkAction` per skill describing what was (or, with `dry_run`, would
    be) done. A non-symlink path already occupying a slot is reported as `conflict`
    and left untouched. With `dry_run=True` no filesystem changes are made — not even
    creating `target_dir`.
    """
    layouts = discover_skills(root)
    if not layouts:
        return []

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    actions: list[LinkAction] = []
    for layout in layouts:
        source = layout.root.resolve()
        link_path = target_dir / layout.name
        action = _plan(link_path, source)
        if not dry_run and action in ("create", "update"):
            _apply(link_path, source, action)
        actions.append(
            LinkAction(
                name=layout.name, link_path=link_path, source=source, action=action
            )
        )
    return actions


def _plan(link_path: Path, source: Path) -> Action:
    """Classify the target slot into one of the four link actions."""
    if link_path.is_symlink():
        # `resolve()` follows the link; compare against the resolved skill folder.
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
