"""GitHub/git output port consumed by the PR layer.

`GhPort` is the contract the PR-publishing step depends on: branch, commit, and
open-PR operations. A real implementation (`GhCli`) shells out to `git` and
`gh pr create`; a `FakeGh` in `testing/fakes` records every call for tests.
Nothing above this port ever invokes `git` or `gh` directly.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable


class GhError(Exception):
    """Raised when a git/gh operation fails (non-zero exit, timeout, bad input)."""


@runtime_checkable
class GhPort(Protocol):
    """Write-side git/gh operations the PR layer needs."""

    def current_branch(self, root: Path) -> str:
        """Return the name of the currently checked-out branch in `root`."""
        ...

    def create_branch(self, root: Path, name: str) -> None:
        """Create and switch to branch `name` in `root`."""
        ...

    def commit_all(self, root: Path, message: str) -> None:
        """Stage every change in `root` and commit it with `message`."""
        ...

    def open_pr(
        self,
        root: Path,
        branch: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> str:
        """Open a PR for `branch` with `title`/`body`/`labels`; return its URL."""
        ...

    def open_issue(
        self, root: Path, title: str, body: str, labels: list[str]
    ) -> str:
        """Open an issue with `title`/`body`/`labels`; return its URL.

        Used for the no-PR outcomes — quarantine (gate fail) and a validation
        failure — where the pipeline must surface the problem without a branch.
        """
        ...
