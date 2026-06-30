"""Contract tests for `GitCli` against a real, local temp git repository.

No network: a temp repo is initialized on disk with two commits touching a
subtree, then `GitCli` is exercised against it. Skipped if `git` is unavailable.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from skillsync.ports.git import GitError
from skillsync.ports.git_cli import GitCli

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git executable not available"
)

SUBTREE = "skills/demo"


def _run_git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture
def two_commit_repo(tmp_path: Path) -> Path:
    """A local git repo with two commits touching `skills/demo`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    _run_git(repo, "branch", "-m", "main")

    subtree = repo / SUBTREE
    subtree.mkdir(parents=True)
    (subtree / "SKILL.md").write_text("# Demo\nfirst line\n")
    (repo / "README.md").write_text("outside the subtree\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "first")

    (subtree / "SKILL.md").write_text("# Demo\nsecond line\n")
    (subtree / "scripts").mkdir()
    (subtree / "scripts" / "run.sh").write_text("echo hi\n")
    (repo / "README.md").write_text("changed but outside the subtree\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "second")

    return repo


def test_head_sha_resolves_ref(two_commit_repo: Path) -> None:
    """`head_sha` returns the full 40-char SHA that the ref resolves to."""
    sha = GitCli().head_sha(two_commit_repo, "main")

    assert len(sha) == 40
    assert sha == _run_git(two_commit_repo, "rev-parse", "main")


def test_remote_head_resolves_ref_without_fetch(two_commit_repo: Path) -> None:
    """`remote_head` returns the ref's SHA via ls-remote against a (local) repo URL."""
    sha = GitCli().remote_head(str(two_commit_repo), "main")

    assert len(sha) == 40
    assert sha == _run_git(two_commit_repo, "rev-parse", "main")


def test_remote_head_raises_on_unknown_ref(two_commit_repo: Path) -> None:
    """An absent ref surfaces as a GitError rather than a bogus SHA."""
    with pytest.raises(GitError):
        GitCli().remote_head(str(two_commit_repo), "no-such-branch")


def test_is_ancestor_true_for_first_commit(two_commit_repo: Path) -> None:
    """The first commit is an ancestor of the second (HEAD)."""
    first = _run_git(two_commit_repo, "rev-parse", "HEAD~1")

    assert GitCli().is_ancestor(two_commit_repo, first, "main") is True


def test_is_ancestor_false_for_unrelated_sha(two_commit_repo: Path) -> None:
    """HEAD is not an ancestor of its own parent."""
    head = _run_git(two_commit_repo, "rev-parse", "HEAD")
    first = _run_git(two_commit_repo, "rev-parse", "HEAD~1")

    assert GitCli().is_ancestor(two_commit_repo, head, first) is False


def test_diff_subtree_between_commits_limited_to_subtree(
    two_commit_repo: Path,
) -> None:
    """`diff_subtree` shows subtree changes only, excluding outside files."""
    first = _run_git(two_commit_repo, "rev-parse", "HEAD~1")

    diff = GitCli().diff_subtree(two_commit_repo, first, "main", SUBTREE)

    assert "SKILL.md" in diff
    assert "scripts/run.sh" in diff
    assert "-first line" in diff
    assert "+second line" in diff
    assert "README.md" not in diff


def test_diff_subtree_from_none_renders_full_content_as_added(
    two_commit_repo: Path,
) -> None:
    """With `from_sha=None`, the whole subtree at the ref is rendered as added."""
    diff = GitCli().diff_subtree(two_commit_repo, None, "main", SUBTREE)

    assert "SKILL.md" in diff
    assert "+second line" in diff
    assert "README.md" not in diff


def test_list_subtree_files_returns_relative_paths(two_commit_repo: Path) -> None:
    """`list_subtree_files` returns subtree-relative paths at the ref."""
    files = GitCli().list_subtree_files(two_commit_repo, "main", SUBTREE)

    assert sorted(files) == ["SKILL.md", "scripts/run.sh"]


def test_head_sha_unknown_ref_raises_git_error(two_commit_repo: Path) -> None:
    """An unresolvable ref surfaces as a typed GitError."""
    with pytest.raises(GitError):
        GitCli().head_sha(two_commit_repo, "no-such-ref")
