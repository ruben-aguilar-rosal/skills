"""Real `GitPort` implementation shelling out to the `git` executable.

Every subprocess call uses an args list with `shell=False` and a timeout. No
command interpolates untrusted input into a shell string. Read operations work
against bare mirrors as well as working trees.
"""

import subprocess
from pathlib import Path

from skillsync.ports.git import GitError
from skillsync.subtree import subtree_pathspec, subtree_prefix

# Git's well-known empty-tree object; diffing against it renders a ref's files
# as pure additions (used for the `from_sha=None` full-content case).
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_DEFAULT_TIMEOUT = 120


def _repo_url(repo: str) -> str:
    """Resolve a `repo` spec to a git URL `clone`/`ls-remote` accepts.

    A spec that already looks like a URL (`scheme://…`, `git@…`), an absolute path,
    or an existing local path is used as-is; otherwise it is treated as a GitHub
    `owner/name` shorthand. Recognizing local paths lets tests point at an on-disk
    repo without a network round-trip.
    """
    if "://" in repo or repo.startswith("git@") or repo.startswith("/"):
        return repo
    if Path(repo).exists():
        return repo
    return f"https://github.com/{repo}.git"


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
        url = _repo_url(repo)
        dest = self._cache_dir / (repo.replace("/", "__") + ".git")
        if dest.exists():
            self._run(dest, "fetch", "--prune", "origin", ref)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            self._run(self._cache_dir, "clone", "--mirror", url, str(dest))
            self._run(dest, "fetch", "--prune", "origin", ref)
        return dest

    def remote_head(self, repo: str, ref: str) -> str:
        """Return the SHA `ref` resolves to on the remote via `git ls-remote`.

        Transfers only the ref advertisement (no pack, no local mirror). Raises
        `GitError` if the remote is unreachable or `ref` matches no remote ref.
        """
        out = self._run(self._cache_dir_for_lsremote(), "ls-remote", _repo_url(repo), ref)
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name in (ref, f"refs/heads/{ref}", f"refs/tags/{ref}"):
                return sha.strip()
        # Fall back to the first advertised line (a bare sha or single match).
        first = out.split("\t", 1)[0].strip() if out.strip() else ""
        if first:
            return first
        raise GitError(f"git ls-remote {repo} {ref} returned no matching ref")

    def _cache_dir_for_lsremote(self) -> Path:
        """A directory to run `ls-remote` from; the cache dir, created if absent."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir

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
        return self._run(repo_path, "diff", base, ref, "--", subtree_pathspec(subtree))

    def list_subtree_files(self, repo_path: Path, ref: str, subtree: str) -> list[str]:
        """List subtree-relative file paths present under `subtree` at `ref`."""
        prefix = subtree_prefix(subtree)
        output = self._run(
            repo_path, "ls-tree", "-r", "--name-only", ref, "--", subtree_pathspec(subtree)
        )
        return [
            line[len(prefix) :] if line.startswith(prefix) else line
            for line in output.splitlines()
            if line
        ]

    def read_subtree_files(
        self, repo_path: Path, ref: str, subtree: str
    ) -> dict[str, str | bytes]:
        """Return `{subtree-relative-path: content}` for every file under `subtree` at `ref`.

        Reads each blob with `git show <ref>:<path>` so it works against a bare
        mirror with no working tree checked out. Text blobs come back as `str`;
        a blob that is not valid UTF-8 (a font, image, archive, …) comes back as
        `bytes` so binary ship-along assets survive vendoring intact.
        """
        prefix = subtree_prefix(subtree)
        files: dict[str, str | bytes] = {}
        for rel_path in self.list_subtree_files(repo_path, ref, subtree):
            full_path = f"{prefix}{rel_path}"
            files[rel_path] = self._show_blob(repo_path, ref, full_path)
        return files

    def _show_blob(self, repo_path: Path, ref: str, path: str) -> str | bytes:
        """Read one blob at `ref:path`, as `str` if UTF-8 decodable else `bytes`."""
        raw = self._exec_bytes(repo_path, "show", f"{ref}:{path}")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw

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

    def _exec_bytes(self, cwd: Path, *args: str) -> bytes:
        """Run a git command with no text decoding; return raw stdout bytes.

        Used to read blobs that may be binary; raises GitError on failure exactly
        like `_run`, decoding only stderr (a diagnostic) for the message.
        """
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out after {self._timeout}s") from exc
        except OSError as exc:
            raise GitError(f"git {' '.join(args)} could not be executed: {exc}") from exc
        if completed.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed ({completed.returncode}): "
                f"{completed.stderr.decode('utf-8', 'replace').strip()}"
            )
        return completed.stdout
