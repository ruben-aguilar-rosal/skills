"""STATUS report — per-skill sync/drift/link state.

`gather_status` builds one `SkillStatus` row per on-disk skill folder under
`skills/`, combining four independent, DETERMINISTIC signals (no LLM):

- **synced_sha** — the short SHA the skill is pinned at in `sources.yaml` (`None`
  when the folder is present but unpinned);
- **upstream_ahead** — whether the pinned ref has commits past `synced_sha`, via the
  injected `GitPort`. It is OPTIONAL and OFFLINE-TOLERANT: pass `git=None` to skip
  it, and any `GitError` (no network, unknown ref) degrades the field to `None`
  rather than failing the whole report. Each distinct `(repo, ref)` head is resolved
  ONCE — with a lightweight `git ls-remote` (no fetch) — and the probes run
  concurrently, so a config with many pins over a few repos stays fast;
- **drift** — whether the committed `SKILL.md` differs from its `.generated`
  snapshot (a hand-edit), reusing the reconcile stage's `detect_drift`;
- **linked** — whether `<target_dir>/<name>` is a symlink resolving to this skill
  folder, reusing the link command's planner.

The CLI assembles the real `GitCli` (or `None` when offline) and prints the rows.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from skillsync.commands.link import _plan
from skillsync.config import Config, SkillPin, skill_dest
from skillsync.layout import SkillLayout, read_skill
from skillsync.ports.git import GitError, GitPort
from skillsync.stages.reconcile import detect_drift

# How many leading characters of a SHA to show in the report.
_SHORT_SHA_LEN = 7

# Cap on concurrent upstream probes; each is one short `git ls-remote` round-trip.
_MAX_PROBE_WORKERS = 8


@dataclass(frozen=True)
class SkillStatus:
    """The status report row for one skill folder.

    `synced_sha` is the short pinned SHA (`None` if unpinned); `upstream_ahead` is
    True/False from the git port or `None` when undetermined (offline / git error /
    no pin); `drift` is True when SKILL.md was hand-edited away from its snapshot;
    `linked` is True when the skill is symlinked into the target skills dir.
    """

    name: str
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

    `config` is the source of truth for which skills exist and where each lives
    (its `dest`); a row is produced per pinned skill. `git=None` skips the (online)
    upstream-ahead probe. `target_dir` is the skills dir the link state is checked
    against.

    The upstream-ahead probe resolves each distinct `(repo, ref)` head exactly once,
    concurrently, so N pins over M repos cost M (not N) network round-trips.
    """
    heads = _resolve_heads(config, git)
    return [
        _status_one(
            _PinContext(source.repo, source.ref, pin, skill_dest(source, pin)),
            root,
            heads,
            target_dir,
        )
        for source in config.sources
        for pin in source.skills
    ]


def _resolve_heads(
    config: Config, git: GitPort | None
) -> dict[tuple[str, str], str | None]:
    """Resolve every distinct `(repo, ref)` to its upstream head SHA, concurrently.

    Returns `{(repo, ref): head_sha}`, with the value `None` when undetermined
    (offline, unknown ref, or `git is None`). One `git ls-remote` per pair, run in a
    small thread pool — a `GitError` on one repo degrades only that entry to `None`.
    """
    if git is None:
        return {}
    pairs = {(source.repo, source.ref) for source in config.sources}
    if not pairs:
        return {}

    def probe(pair: tuple[str, str]) -> tuple[tuple[str, str], str | None]:
        repo, ref = pair
        try:
            return pair, git.remote_head(repo, ref)
        except GitError:
            return pair, None

    workers = min(_MAX_PROBE_WORKERS, len(pairs))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(probe, pairs))


@dataclass(frozen=True)
class _PinContext:
    """The `sources.yaml` context for one pinned skill: repo, ref, pin, and dest."""

    repo: str
    ref: str
    pin: SkillPin
    dest: str


def _status_one(
    context: _PinContext,
    root: Path,
    heads: dict[tuple[str, str], str | None],
    target_dir: Path,
) -> SkillStatus:
    """Assemble the four status signals for a single pinned skill."""
    layout = SkillLayout.resolve(root, context.pin.path, dest=context.dest)
    return SkillStatus(
        name=layout.name,
        synced_sha=_short(context.pin.synced_sha),
        upstream_ahead=_upstream_ahead(context, heads),
        drift=detect_drift(read_skill(layout)) is not None,
        linked=_is_linked(layout, target_dir),
    )


def _short(sha: str | None) -> str | None:
    """Truncate a SHA to its short form, leaving `None` untouched."""
    return sha[:_SHORT_SHA_LEN] if sha else sha


def _upstream_ahead(
    context: _PinContext | None, heads: dict[tuple[str, str], str | None]
) -> bool | None:
    """Return whether the pinned ref is past `synced_sha`, or None when undetermined.

    Compares the pin's `synced_sha` against the pre-resolved upstream head for its
    `(repo, ref)`. Returns `None` (undetermined) when there is no pin, no
    `synced_sha`, or the head could not be resolved (offline / unknown ref / probe
    skipped), so a single unreachable repo never breaks the whole report.
    """
    if context is None or context.pin.synced_sha is None:
        return None
    head = heads.get((context.repo, context.ref))
    if head is None:
        return None
    return head != context.pin.synced_sha


def _is_linked(layout: SkillLayout, target_dir: Path) -> bool:
    """Return True when `<target_dir>/<name>` symlinks to this skill folder."""
    source = layout.root.resolve()
    return _plan(target_dir / layout.name, source) == "unchanged"
