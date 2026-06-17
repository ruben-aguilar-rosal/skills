"""Real `GhPort` implementation shelling out to `git` and `gh`.

Every subprocess call uses an args list with `shell=False` and a timeout — no
value (branch name, commit message, PR body) is ever interpolated into a shell
string. `open_pr` invokes `gh pr create` and returns the PR URL it prints.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

from skillsync.ports.gh import GhError

_DEFAULT_TIMEOUT = 120

# A subprocess runner: takes argv + cwd + timeout, returns the completed process.
# The default shells out for real; tests inject a fake to avoid touching git/gh.
Runner = Callable[[list[str], Path, int], "subprocess.CompletedProcess[str]"]


def _default_runner(
    argv: list[str], cwd: Path, timeout: int
) -> "subprocess.CompletedProcess[str]":
    """Run `argv` in `cwd` with `shell=False`, capturing text output under a timeout."""
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class GhCli:
    """`GhPort` backed by the local `git` and `gh` CLIs."""

    def __init__(
        self, runner: Runner | None = None, timeout: int = _DEFAULT_TIMEOUT
    ) -> None:
        """Configure the subprocess `runner` (injectable) and per-command timeout."""
        self._runner = runner or _default_runner
        self._timeout = timeout

    def current_branch(self, root: Path) -> str:
        """Return the name of the currently checked-out branch in `root`."""
        return self._run(root, "git", "rev-parse", "--abbrev-ref", "HEAD").strip()

    def create_branch(self, root: Path, name: str) -> None:
        """Create and switch to branch `name` in `root`."""
        self._run(root, "git", "checkout", "-b", name)

    def commit_all(self, root: Path, message: str) -> None:
        """Stage every change in `root` and commit it with `message`."""
        self._run(root, "git", "add", "-A")
        self._run(root, "git", "commit", "-m", message)

    def open_pr(
        self,
        root: Path,
        branch: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> str:
        """Open a PR for `branch` via `gh pr create`; return the printed URL."""
        self._run(root, "git", "push", "--set-upstream", "origin", branch)
        argv = [
            "gh",
            "pr",
            "create",
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
        for label in labels:
            argv += ["--label", label]
        return self._run(root, *argv).strip()

    def open_issue(
        self, root: Path, title: str, body: str, labels: list[str]
    ) -> str:
        """Open an issue via `gh issue create`; return the printed URL."""
        argv = ["gh", "issue", "create", "--title", title, "--body", body]
        for label in labels:
            argv += ["--label", label]
        return self._run(root, *argv).strip()

    def _exec(self, cwd: Path, *args: str) -> "subprocess.CompletedProcess[str]":
        """Run a command with `shell=False` and a timeout; never raises on exit code."""
        try:
            return self._runner(list(args), cwd, self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise GhError(f"{' '.join(args)} timed out after {self._timeout}s") from exc
        except OSError as exc:
            raise GhError(f"{' '.join(args)} could not be executed: {exc}") from exc

    def _run(self, cwd: Path, *args: str) -> str:
        """Run a command and return stdout, raising GhError on failure."""
        completed = self._exec(cwd, *args)
        if completed.returncode != 0:
            raise GhError(
                f"{' '.join(args)} failed ({completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        return completed.stdout
