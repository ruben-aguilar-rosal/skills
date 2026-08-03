"""Deterministic DISCOVER stage — surface watched-folder skills, zero LLM.

A `watch` folder in `sources.yaml` is a *discovery* mechanism, not a tracked unit:
the tracked unit stays one skill = one pin. `discover` walks each source's watched
folders, finds every subfolder that ships a `SKILL.md` upstream, and classifies it
against the source's pins and ignore list:

- **new** — a discovered skill that is neither already pinned nor on the `ignore`
  list. These are surfaced for the author to adopt (`skillsync add`) or reject
  (`skillsync ignore`); discovery NEVER auto-onboards them (no LLM, no quota spent).
- **removed** — a skill that IS pinned under a watched folder but no longer exists
  upstream (deleted or renamed). Surfaced so the author notices the drift.

A pin that lives outside every watched folder is left entirely alone — it is
hand-managed, so its absence from a watch folder means nothing. The stage is
offline-tolerant: a watch folder that cannot be listed degrades to "nothing
discovered there" rather than failing the run.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skillsync.config import Config, Source
from skillsync.ports.git import GitError, GitPort
from skillsync.subtree import subtree_basename

# The marker file that makes a folder a skill (PLAN.md: each skill folder ships one).
_SKILL_FILE = "SKILL.md"

Kind = Literal["new", "removed"]


@dataclass(frozen=True)
class Discovery:
    """One watched-folder finding: a new or removed skill under a `watch` folder.

    `skill_path` is the upstream subtree path (what `skillsync add`/`ignore` take);
    `name` is its folder name (last path segment); `kind` is `new` or `removed`.
    """

    repo: str
    skill_path: str
    name: str
    kind: Kind


def discover(config: Config, git: GitPort, root: Path) -> list[Discovery]:
    """Find new and removed skills across every source's watched folders.

    For each source with `watch` folders, lists the upstream skill folders under
    them, then reports the not-yet-pinned/not-ignored ones as `new` and the pinned
    ones that vanished upstream as `removed`. Sources without `watch` are skipped
    (no git contact). `root` anchors the port contract; the order is sources in
    config order, new before removed within a source, each group path-sorted.
    """
    found: list[Discovery] = []
    for source in config.sources:
        if not source.watch:
            continue
        found.extend(_discover_source(source, git, root))
    return found


def _discover_source(source: Source, git: GitPort, root: Path) -> list[Discovery]:
    """Classify the watched folders of a single source into new/removed findings."""
    repo_path = git.mirror(source.repo, source.ref)
    discovered = _discovered_skill_paths(source, git, repo_path, root)
    pinned = {pin.path.rstrip("/") for pin in source.skills}
    ignored = {path.rstrip("/") for path in source.ignore}

    new = sorted(discovered - pinned - ignored)
    removed = sorted(
        path
        for path in pinned
        if path not in discovered and _under_any_watch(path, source.watch)
    )
    return [_finding(source.repo, path, "new") for path in new] + [
        _finding(source.repo, path, "removed") for path in removed
    ]


def _discovered_skill_paths(
    source: Source, git: GitPort, repo_path: Path, root: Path
) -> set[str]:
    """Return every upstream skill folder (full subtree path) under the watch folders."""
    paths: set[str] = set()
    for watch in source.watch:
        prefix = watch.rstrip("/")
        try:
            files = git.list_subtree_files(repo_path, source.ref, watch)
        except GitError:
            continue  # offline / unlistable watch folder: discover nothing there
        for rel_path in files:
            if rel_path == _SKILL_FILE or rel_path.endswith("/" + _SKILL_FILE):
                folder = rel_path[: -len(_SKILL_FILE)].rstrip("/")
                paths.add(f"{prefix}/{folder}".rstrip("/") if folder else prefix)
    return paths


def _under_any_watch(path: str, watch: list[str]) -> bool:
    """True if `path` lives under one of the `watch` folders."""
    return any(path == w.rstrip("/") or path.startswith(w.rstrip("/") + "/") for w in watch)


def _finding(repo: str, skill_path: str, kind: Kind) -> Discovery:
    """Build a Discovery, naming the skill by its last path segment.

    A repo-root skill path has no last segment, so it falls back to the repo's own
    name — a discovery is only a suggestion to display, and adopting it via `add`
    is where the real folder name gets chosen (`--name`).
    """
    name = subtree_basename(skill_path) or subtree_basename(repo)
    return Discovery(repo=repo, skill_path=skill_path, name=name, kind=kind)
