"""In-memory fakes for skillsync ports.

`FakeGit` backs `GitPort` with a linear commit history and per-commit content
snapshots, enough to exercise the ancestor/diff/listing logic the deterministic
stages rely on — without touching disk or the network.
"""

import difflib
from pathlib import Path

from skillsync.ports.git import GitError

_EMPTY_TREE = "<empty>"


class FakeGit:
    """`GitPort` backed by `{sha: {path: content}}` and a linear history."""

    def __init__(self) -> None:
        """Start with an empty history, no commits, and no refs."""
        self._history: list[str] = []
        self._snapshots: dict[str, dict[str, str]] = {}
        self._refs: dict[str, str] = {}

    def add_commit(self, sha: str, files: dict[str, str]) -> None:
        """Append a commit `sha` with a full file snapshot to the linear history."""
        if sha in self._snapshots:
            raise ValueError(f"duplicate commit sha: {sha}")
        self._history.append(sha)
        self._snapshots[sha] = dict(files)

    def set_ref(self, name: str, sha: str) -> None:
        """Point ref `name` at an existing commit `sha`."""
        if sha not in self._snapshots:
            raise ValueError(f"unknown commit sha: {sha}")
        self._refs[name] = sha

    def mirror(self, repo: str, ref: str) -> Path:
        """Return a synthetic checkout path; no I/O is performed."""
        self.head_sha(Path("/fake"), ref)  # validate the ref exists
        return Path("/fake/mirrors") / repo.replace("/", "__")

    def head_sha(self, repo_path: Path, ref: str) -> str:
        """Resolve `ref` (a ref name or a known sha) to a commit SHA."""
        return self._resolve(ref)

    def is_ancestor(self, repo_path: Path, ancestor_sha: str, ref: str) -> bool:
        """Return True if `ancestor_sha` precedes `ref` in the linear history."""
        ancestor = self._resolve(ancestor_sha)
        target = self._resolve(ref)
        return self._history.index(ancestor) <= self._history.index(target)

    def diff_subtree(
        self, repo_path: Path, from_sha: str | None, ref: str, subtree: str
    ) -> str:
        """Unified diff of `subtree` from `from_sha` (or nothing) to `ref`."""
        old = {} if from_sha is None else self._subtree_files(self._resolve(from_sha), subtree)
        new = self._subtree_files(self._resolve(ref), subtree)

        chunks: list[str] = []
        for path in sorted(set(old) | set(new)):
            old_lines = old.get(path, "").splitlines(keepends=True)
            new_lines = new.get(path, "").splitlines(keepends=True)
            if old_lines == new_lines:
                continue
            from_label = "/dev/null" if path not in old else f"a/{path}"
            to_label = "/dev/null" if path not in new else f"b/{path}"
            chunks.extend(
                difflib.unified_diff(
                    old_lines, new_lines, fromfile=from_label, tofile=to_label
                )
            )
        return "".join(chunks)

    def list_subtree_files(self, repo_path: Path, ref: str, subtree: str) -> list[str]:
        """List subtree-relative file paths present under `subtree` at `ref`."""
        return sorted(self._subtree_files(self._resolve(ref), subtree))

    def _resolve(self, ref: str) -> str:
        """Resolve a ref name or raw sha to a known commit sha, or raise GitError."""
        if ref in self._refs:
            return self._refs[ref]
        if ref in self._snapshots:
            return ref
        raise GitError(f"unknown ref or sha: {ref}")

    def _subtree_files(self, sha: str, subtree: str) -> dict[str, str]:
        """Return `{subtree-relative-path: content}` for files under `subtree` at `sha`."""
        prefix = subtree.rstrip("/") + "/"
        return {
            path[len(prefix) :]: content
            for path, content in self._snapshots[sha].items()
            if path.startswith(prefix)
        }
