"""Git I/O port consumed by the deterministic stages.

`GitPort` is the contract the detect/scan stages depend on. A real implementation
(`GitCli`) shells out to `git`; a `FakeGit` backs the same contract with an
in-memory history for tests. Stages depend only on this protocol, never on `git`.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable


class GitError(Exception):
    """Raised when a git operation fails (non-zero exit, timeout, bad ref)."""


@runtime_checkable
class GitPort(Protocol):
    """Read-mostly git operations the deterministic stages need."""

    def mirror(self, repo: str, ref: str) -> Path:
        """Ensure a local mirror of `repo`, fetch `ref`, return the checkout path."""
        ...

    def remote_head(self, repo: str, ref: str) -> str:
        """Return the SHA `ref` resolves to on the remote, without fetching objects.

        A lightweight `git ls-remote` probe: it transfers only the ref advertisement,
        not a pack, and needs no local mirror — so a caller that only compares the
        upstream head against a pinned SHA (e.g. the status report) can skip the cost
        of `mirror`. Raises `GitError` if the remote is unreachable or the ref absent.
        """
        ...

    def head_sha(self, repo_path: Path, ref: str) -> str:
        """Return the commit SHA that `ref` resolves to in `repo_path`."""
        ...

    def is_ancestor(self, repo_path: Path, ancestor_sha: str, ref: str) -> bool:
        """Return True if `ancestor_sha` is an ancestor of `ref`."""
        ...

    def diff_subtree(
        self, repo_path: Path, from_sha: str | None, ref: str, subtree: str
    ) -> str:
        """Unified diff of `subtree` from `from_sha` to `ref`.

        With `from_sha=None`, every file under `subtree` at `ref` is rendered as
        added (full content), so first-time onboarding sees the whole subtree.
        """
        ...

    def list_subtree_files(self, repo_path: Path, ref: str, subtree: str) -> list[str]:
        """List subtree-relative file paths present under `subtree` at `ref`."""
        ...

    def read_subtree_files(
        self, repo_path: Path, ref: str, subtree: str
    ) -> dict[str, str | bytes]:
        """Return `{subtree-relative-path: content}` for every file under `subtree` at `ref`.

        This is the content surface the security gate scans and full-mode adapt /
        the upstream mirror write consume. Text blobs are `str`; non-UTF-8 blobs
        (binary aux assets) are `bytes`.
        """
        ...
