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
  rather than failing the whole report; always `None` for a local skill. Each
  distinct `(repo, ref)` head is resolved ONCE — with a lightweight `git ls-remote`
  (no fetch) — and the probes run concurrently, so a config with many pins over a
  few repos stays fast;
- **drift** — whether the committed `SKILL.md` differs from its `.generated`
  snapshot (a hand-edit), reusing the reconcile stage's `detect_drift`;
- **installed** — whether EVERY target directory holds a `skillsync install` copy of
  this skill (see `commands.install`). A copy that has fallen behind its source still
  counts as installed; `skillsync install --dry-run` is what reports staleness.

The CLI assembles the real `GitCli` (or `None` when offline) and prints the rows.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from typing import Literal

Origin = Literal["vendored", "local"]
from skillsync.commands.install import installed_from
from skillsync.config import Config, SkillPin
from skillsync.layout import SkillLayout, discover_skills, pin_index, read_skill
from skillsync.ports.git import GitError, GitPort
from skillsync.stages.reconcile import detect_drift

# How many leading characters of a SHA to show in the report.
_SHORT_SHA_LEN = 7

# Cap on concurrent upstream probes; each is one short `git ls-remote` round-trip.
_MAX_PROBE_WORKERS = 8


@dataclass(frozen=True)
class SkillStatus:
    """The status report row for one skill folder.

    `origin` is `vendored` or `local`; `synced_sha` is the short pinned SHA (`None`
    if local/unpinned); `upstream_ahead` is True/False from the git port or `None`
    when undetermined (offline / git error / local / no pin); `drift` is True when
    SKILL.md was hand-edited away from its snapshot; `installed` is True when every
    target skills dir holds a copy of this skill.
    """

    name: str
    origin: Origin
    synced_sha: str | None
    upstream_ahead: bool | None
    drift: bool
    installed: bool


def gather_status(
    config: Config,
    root: Path,
    *,
    git: GitPort | None,
    target_dirs: list[Path],
) -> list[SkillStatus]:
    """Build a status row for every skill folder under `root/skills/`.

    Skills are enumerated from the FILESYSTEM (`discover_skills`), so hand-written
    local skills appear alongside vendored ones. Each row is joined against
    `sources.yaml` to recover its pin (sha, ref, accept rules) when vendored; a row
    with no pin is `local`. `git=None` skips the (online) upstream-ahead probe.
    `target_dirs` are the skills dirs the install state is checked against.

    The upstream-ahead probe resolves each distinct `(repo, ref)` head exactly once,
    concurrently, so N pins over M repos cost M (not N) network round-trips.
    """
    pins = pin_index(config, root)
    heads = _resolve_heads(config, git)
    rows: list[SkillStatus] = []
    for layout in discover_skills(root):
        match = pins.get(layout.root.resolve())
        context = (
            _PinContext(match[0].repo, match[0].ref, match[1]) if match else None
        )
        rows.append(_status_one(layout, context, heads, target_dirs))
    return rows


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
    """The `sources.yaml` context for one pinned skill: repo, ref, and pin."""

    repo: str
    ref: str
    pin: SkillPin


def _status_one(
    layout: SkillLayout,
    context: "_PinContext | None",
    heads: dict[tuple[str, str], str | None],
    target_dirs: list[Path],
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
        upstream_ahead=_upstream_ahead(context, heads),
        drift=detect_drift(read_skill(layout)) is not None,
        installed=_is_installed(layout, target_dirs),
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


def _is_installed(layout: SkillLayout, target_dirs: list[Path]) -> bool:
    """Return True when every target dir holds a copy installed from this skill.

    A skill present in some targets but not others reports False — the fix is one
    `skillsync install` run, which reconciles them all. A legacy symlink does not
    count: it is exactly what installing replaces.
    """
    source = layout.root.resolve()
    return all(
        installed_from(target_dir / layout.name) == source for target_dir in target_dirs
    )
