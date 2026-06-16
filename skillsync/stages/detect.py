"""Deterministic DETECT stage — zero LLM, fully reproducible.

For each non-held `SkillPin`, mirror the source ref and compare the last-synced
SHA against the ref's HEAD to classify the skill as `none`, `changed`, or
`reonboard`. A `reonboard` happens on first onboarding (no `synced_sha`) or when
upstream rewrote history so the synced SHA is no longer an ancestor of the ref.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from skillsync.config import Config, SkillPin
from skillsync.ports.git import GitPort

Kind = Literal["none", "changed", "reonboard"]


@dataclass
class ChangeSet:
    """The detect verdict for one skill: its kind, SHA bounds, diff, and files."""

    skill_path: str
    name: str
    kind: Kind
    from_sha: str | None
    to_sha: str
    diff: str
    changed_files: list[str] = field(default_factory=list)
    rewritten_history: bool = False


def detect(config: Config, git: GitPort, root: Path) -> list[ChangeSet]:
    """Classify every non-held skill pin into a `ChangeSet`.

    `root` anchors the local repo for the (unused-by-fake) port contract. Held
    pins (`hold=True`) are skipped entirely and produce no change set.
    """
    changes: list[ChangeSet] = []
    for source in config.sources:
        for pin in source.skills:
            if pin.hold:
                continue
            changes.append(_detect_one(source.repo, source.ref, pin, git))
    return changes


def _detect_one(repo: str, ref: str, pin: SkillPin, git: GitPort) -> ChangeSet:
    """Mirror `repo`, resolve HEAD, and classify a single pin."""
    repo_path = git.mirror(repo, ref)
    to_sha = git.head_sha(repo_path, ref)
    name = pin.path.rstrip("/").rsplit("/", 1)[-1]

    # New skill: no prior sync point — full subtree is the diff.
    if pin.synced_sha is None:
        return _reonboard(pin.path, name, to_sha, git, repo_path, ref, rewritten=False)

    # History rewrite: the synced SHA is no longer reachable from the ref.
    if not git.is_ancestor(repo_path, pin.synced_sha, ref):
        return _reonboard(pin.path, name, to_sha, git, repo_path, ref, rewritten=True)

    diff = git.diff_subtree(repo_path, pin.synced_sha, ref, pin.path)
    if not diff:
        return ChangeSet(
            skill_path=pin.path,
            name=name,
            kind="none",
            from_sha=pin.synced_sha,
            to_sha=to_sha,
            diff="",
            changed_files=[],
        )
    return ChangeSet(
        skill_path=pin.path,
        name=name,
        kind="changed",
        from_sha=pin.synced_sha,
        to_sha=to_sha,
        diff=diff,
        changed_files=_changed_files(diff, pin.path),
    )


def _reonboard(
    skill_path: str,
    name: str,
    to_sha: str,
    git: GitPort,
    repo_path: Path,
    ref: str,
    *,
    rewritten: bool,
) -> ChangeSet:
    """Build a `reonboard` change set whose diff is the full subtree content."""
    diff = git.diff_subtree(repo_path, None, ref, skill_path)
    return ChangeSet(
        skill_path=skill_path,
        name=name,
        kind="reonboard",
        from_sha=None,
        to_sha=to_sha,
        diff=diff,
        changed_files=_changed_files(diff, skill_path),
        rewritten_history=rewritten,
    )


def _changed_files(diff: str, subtree: str) -> list[str]:
    """Extract subtree-relative file paths from a unified diff's `---`/`+++` headers."""
    prefix = subtree.rstrip("/") + "/"
    files: set[str] = set()
    for line in diff.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        path = line[4:].strip()
        if path == "/dev/null":
            continue
        if path.startswith(("a/", "b/")):
            path = path[2:]
        if path.startswith(prefix):
            path = path[len(prefix) :]
        files.add(path)
    return sorted(files)
