"""STATUS report — per-skill sync/drift/link state.

`gather_status` builds one `SkillStatus` row per on-disk skill folder under
`skills/` (every folder with a `SKILL.md`, vendored or local), combining
independent, DETERMINISTIC signals (no LLM):

- **origin** — `vendored` (the folder has a pin in `sources.yaml`) or `local`
  (hand-written, no upstream);
- **synced_sha** — the short SHA the skill is pinned at in `sources.yaml` (`None`
  for a local skill, or a vendored one with no recorded sha);
- **upstream_ahead** — whether the pinned ref has commits past `synced_sha`, via the
  injected `GitPort`. It is OPTIONAL and OFFLINE-TOLERANT: pass `git=None` to skip
  it, and any `GitError` (no network, unknown ref) degrades the field to `None`
  rather than failing the whole report; always `None` for a local skill;
- **drift** — whether the committed `SKILL.md` differs from its `.generated`
  snapshot (a hand-edit), reusing the reconcile stage's `detect_drift`;
- **linked** — whether `<target_dir>/<name>` is a symlink resolving to this skill
  folder, reusing the link command's planner.

The CLI assembles the real `GitCli` (or `None` when offline) and prints the rows.
"""

from dataclasses import dataclass
from pathlib import Path

from skillsync.commands.link import Origin, _plan
from skillsync.config import Config, SkillPin
from skillsync.layout import SkillLayout, discover_skills, pin_index, read_skill
from skillsync.ports.git import GitError, GitPort
from skillsync.stages.reconcile import detect_drift

# How many leading characters of a SHA to show in the report.
_SHORT_SHA_LEN = 7


@dataclass(frozen=True)
class SkillStatus:
    """The status report row for one skill folder.

    `origin` is `vendored` or `local`; `synced_sha` is the short pinned SHA (`None`
    if local/unpinned); `upstream_ahead` is True/False from the git port or `None`
    when undetermined (offline / git error / local / no pin); `drift` is True when
    SKILL.md was hand-edited away from its snapshot; `linked` is True when the skill
    is symlinked into the target skills dir.
    """

    name: str
    origin: Origin
    synced_sha: str | None
    upstream_ahead: bool | None
    drift: bool
    linked: bool


def gather_status(
    config: Config,
    root: Path,
    *,
    git: GitPort | None,
    target_dir: Path,
) -> list[SkillStatus]:
    """Build a status row for every skill folder under `root/skills/`.

    Skills are enumerated from the FILESYSTEM (`discover_skills`), so hand-written
    local skills appear alongside vendored ones. Each row is joined against
    `sources.yaml` to recover its pin (sha, ref, accept rules) when vendored; a row
    with no pin is `local`. `git=None` skips the (online) upstream-ahead probe.
    `target_dir` is the skills dir the link state is checked against.
    """
    pins = pin_index(config, root)
    rows: list[SkillStatus] = []
    for layout in discover_skills(root):
        match = pins.get(layout.root.resolve())
        context = (
            _PinContext(match[0].repo, match[0].ref, match[1]) if match else None
        )
        rows.append(_status_one(layout, context, git, target_dir))
    return rows


@dataclass(frozen=True)
class _PinContext:
    """The `sources.yaml` context for one pinned skill: repo, ref, and pin."""

    repo: str
    ref: str
    pin: SkillPin


def _status_one(
    layout: SkillLayout,
    context: "_PinContext | None",
    git: GitPort | None,
    target_dir: Path,
) -> SkillStatus:
    """Assemble the status signals for one on-disk skill (vendored or local).

    `context` is its `sources.yaml` pin when vendored, or `None` when local — a
    local skill reports `origin='local'`, no sha, and no upstream-ahead.
    """
    pin = context.pin if context else None
    return SkillStatus(
        name=layout.name,
        origin="vendored" if context else "local",
        synced_sha=_short(pin.synced_sha) if pin else None,
        upstream_ahead=_upstream_ahead(context, git),
        drift=detect_drift(read_skill(layout)) is not None,
        linked=_is_linked(layout, target_dir),
    )


def _short(sha: str | None) -> str | None:
    """Truncate a SHA to its short form, leaving `None` untouched."""
    return sha[:_SHORT_SHA_LEN] if sha else sha


def _upstream_ahead(context: _PinContext | None, git: GitPort | None) -> bool | None:
    """Return whether the pinned ref is past `synced_sha`, or None when undetermined.

    Returns `None` (undetermined) when there is no git port, no pin, or no
    `synced_sha`, and degrades any `GitError` (offline / unknown ref) to `None` so a
    single unreachable repo never breaks the whole report.
    """
    if git is None or context is None or context.pin.synced_sha is None:
        return None
    try:
        repo_path = git.mirror(context.repo, context.ref)
        head = git.head_sha(repo_path, context.ref)
        return head != context.pin.synced_sha
    except GitError:
        return None


def _is_linked(layout: SkillLayout, target_dir: Path) -> bool:
    """Return True when `<target_dir>/<name>` symlinks to this skill folder."""
    source = layout.root.resolve()
    return _plan(target_dir / layout.name, source) == "unchanged"
