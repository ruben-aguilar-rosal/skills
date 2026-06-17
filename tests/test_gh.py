"""Contract tests for the `GhPort` implementations.

`FakeGh` is exercised directly for call recording. `GhCli` is driven with an
injected fake runner so the real `git`/`gh` executables are NEVER invoked — the
tests assert it builds the right argv (with `shell=False` semantics) and returns
the PR URL printed by `gh pr create`.
"""

import subprocess
from pathlib import Path

import pytest

from skillsync.ports.gh import GhError, GhPort
from skillsync.ports.gh_cli import GhCli
from skillsync.testing.fakes import FakeGh

ROOT = Path("/repo")


def test_fake_gh_records_calls_in_order_and_tracks_branch() -> None:
    """`FakeGh` records each call and adopts a created branch as current."""
    gh = FakeGh(branch="main")

    assert gh.current_branch(ROOT) == "main"
    gh.create_branch(ROOT, "skillsync/demo")
    assert gh.current_branch(ROOT) == "skillsync/demo"
    gh.commit_all(ROOT, "msg")
    url = gh.open_pr(ROOT, "skillsync/demo", "title", "body", ["skillsync"])

    assert url == "https://github.com/fake/skills/pull/skillsync/demo"
    assert [c.method for c in gh.calls] == [
        "current_branch",
        "create_branch",
        "current_branch",
        "commit_all",
        "open_pr",
    ]


def test_fake_gh_satisfies_gh_port() -> None:
    """`FakeGh` is a runtime instance of the `GhPort` protocol."""
    assert isinstance(FakeGh(), GhPort)


class _ScriptedRunner:
    """A fake subprocess runner returning scripted results keyed by the command word."""

    def __init__(self, results: dict[str, subprocess.CompletedProcess[str]]) -> None:
        self.results = results
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: list[str], cwd: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        # Key on the first two argv tokens (e.g. "git checkout", "gh pr").
        key = " ".join(argv[:2])
        return self.results.get(
            key, subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        )


def _ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    """A zero-exit completed process with the given stdout."""
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def test_gh_cli_current_branch_parses_rev_parse() -> None:
    """`current_branch` returns the stripped `git rev-parse --abbrev-ref` output."""
    runner = _ScriptedRunner({"git rev-parse": _ok("main\n")})

    assert GhCli(runner=runner).current_branch(ROOT) == "main"


def test_gh_cli_open_pr_returns_url_and_builds_argv() -> None:
    """`open_pr` pushes, runs `gh pr create` with labels, and returns the URL."""
    url = "https://github.com/o/r/pull/7"
    runner = _ScriptedRunner({"gh pr": _ok(url + "\n")})

    result = GhCli(runner=runner).open_pr(
        ROOT, "skillsync/demo", "t", "b", ["skillsync", "advisory-risk-low"]
    )

    assert result == url
    gh_argv = next(a for a in runner.calls if a[:2] == ["gh", "pr"])
    assert "--head" in gh_argv and "skillsync/demo" in gh_argv
    assert gh_argv.count("--label") == 2


def test_gh_cli_raises_gh_error_on_nonzero_exit() -> None:
    """A non-zero exit from a git/gh command surfaces as a typed GhError."""
    runner = _ScriptedRunner(
        {"git checkout": subprocess.CompletedProcess([], 1, stdout="", stderr="boom")}
    )

    with pytest.raises(GhError):
        GhCli(runner=runner).create_branch(ROOT, "skillsync/demo")
