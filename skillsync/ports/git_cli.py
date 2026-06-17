"""Real `GitPort` implementation shelling out to the `git` executable.

Every subprocess call uses an args list with `shell=False` and a timeout. No
command interpolates untrusted input into a shell string. Read operations work
against bare mirrors as well as working trees.
"""

import subprocess
from pathlib import Path

from skillsync.ports.git import GitError

# Git's well-known empty-tree object; diffing against it renders a ref's files
# as pure additions (used for the `from_sha=None` full-content case).
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_DEFAULT_TIMEOUT = 120


class GitCli:
    """`GitPort` backed by the local `git` CLI."""

    def __init__(
        self, cache_dir: Path | None = None, timeout: int = _DEFAULT_TIMEOUT
    ) -> None:
        """Configure where mirrors are cached and the per-command timeout."""
        self._cache_dir = cache_dir or (Path.home() / ".cache" / "skillsync" / "mirrors")
        self._timeout = timeout

    def mirror(self, repo: str, ref: str) -> Path:
        """Ensure a local bare mirror of `repo`, fetch `ref`, return its path."""
        url = repo if "://" in repo or repo.startswith("git@") else f"https://github.com/{repo}.git"
        dest = self._cache_dir / (repo.replace("/", "__") + ".git")
        if dest.exists():
            self._run(dest, "fetch", "--prune", "origin", ref)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            self._run(self._cache_dir, "clone", "--mirror", url, str(dest))
            self._run(dest, "fetch", "--prune", "origin", ref)
        return dest

    def head_sha(self, repo_path: Path, ref: str) -> str:
        """Return the commit SHA that `ref` resolves to in `repo_path`."""
        return self._run(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()

    def is_ancestor(self, repo_path: Path, ancestor_sha: str, ref: str) -> bool:
        """Return True if `ancestor_sha` is an ancestor of `ref`."""
        completed = self._exec(
            repo_path, "merge-base", "--is-ancestor", ancestor_sha, ref
        )
        if completed.returncode == 0:
            return True
        if completed.returncode == 1:
            return False
        raise GitError(
            f"git merge-base failed ({completed.returncode}): {completed.stderr.strip()}"
        )

    def diff_subtree(
        self, repo_path: Path, from_sha: str | None, ref: str, subtree: str
    ) -> str:
        """Unified diff of `subtree` from `from_sha` (or empty tree) to `ref`."""
        base = from_sha if from_sha is not None else _EMPTY_TREE
        return self._run(repo_path, "diff", base, ref, "--", subtree)

    def list_subtree_files(self, repo_path: Path, ref: str, subtree: str) -> list[str]:
        """List subtree-relative file paths present under `subtree` at `ref`."""
        prefix = subtree.rstrip("/") + "/"
        output = self._run(repo_path, "ls-tree", "-r", "--name-only", ref, "--", subtree)
        return [
            line[len(prefix) :] if line.startswith(prefix) else line
            for line in output.splitlines()
            if line
        ]

    def read_subtree_files(
        self, repo_path: Path, ref: str, subtree: str
    ) -> dict[str, str]:
        """Return `{subtree-relative-path: content}` for every file under `subtree` at `ref`.

        Reads each blob with `git show <ref>:<path>` so it works against a bare
        mirror with no working tree checked out.
        """
        prefix = subtree.rstrip("/") + "/"
        files: dict[str, str] = {}
        for rel_path in self.list_subtree_files(repo_path, ref, subtree):
            full_path = f"{prefix}{rel_path}"
            files[rel_path] = self._run(repo_path, "show", f"{ref}:{full_path}")
        return files

    def _exec(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a git command with `shell=False` and a timeout; never raises on exit code."""
        try:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out after {self._timeout}s") from exc
        except OSError as exc:
            raise GitError(f"git {' '.join(args)} could not be executed: {exc}") from exc

    def _run(self, cwd: Path, *args: str) -> str:
        """Run a git command and return stdout, raising GitError on failure."""
        completed = self._exec(cwd, *args)
        if completed.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed ({completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        return completed.stdout
