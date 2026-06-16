"""Contract tests for `FakeGit`, mirroring the cases the stages need.

`FakeGit` is backed by an in-memory `{sha: {path: content}}` snapshot map and a
linear history. These tests assert it honours the same `GitPort` contract that
`test_git_cli.py` checks against real git, so stages can be tested with the fake.
"""

from pathlib import Path

import pytest

from skillsync.ports.git import GitError, GitPort
from skillsync.testing.fakes import FakeGit

SUBTREE = "skills/demo"


@pytest.fixture
def fake() -> FakeGit:
    """A fake repo with two commits touching `skills/demo`, ref `main` at HEAD."""
    git = FakeGit()
    git.add_commit(
        "sha1",
        {
            "skills/demo/SKILL.md": "# Demo\nfirst line\n",
            "README.md": "outside the subtree\n",
        },
    )
    git.add_commit(
        "sha2",
        {
            "skills/demo/SKILL.md": "# Demo\nsecond line\n",
            "skills/demo/scripts/run.sh": "echo hi\n",
            "README.md": "changed but outside the subtree\n",
        },
    )
    git.set_ref("main", "sha2")
    return git


def test_fake_satisfies_protocol(fake: FakeGit) -> None:
    """`FakeGit` is a structural `GitPort`."""
    assert isinstance(fake, GitPort)


def test_mirror_returns_a_path(fake: FakeGit) -> None:
    """`mirror` returns a checkout path for the requested repo."""
    assert isinstance(fake.mirror("owner/repo", "main"), Path)


def test_head_sha_resolves_ref(fake: FakeGit) -> None:
    """`head_sha` resolves a ref to its commit SHA."""
    assert fake.head_sha(Path("/repo"), "main") == "sha2"


def test_is_ancestor_true_for_first_commit(fake: FakeGit) -> None:
    """The first commit is an ancestor of the ref at HEAD."""
    assert fake.is_ancestor(Path("/repo"), "sha1", "main") is True


def test_is_ancestor_false_for_unrelated_sha(fake: FakeGit) -> None:
    """HEAD is not an ancestor of an earlier commit."""
    assert fake.is_ancestor(Path("/repo"), "sha2", "sha1") is False


def test_diff_subtree_between_commits_limited_to_subtree(fake: FakeGit) -> None:
    """`diff_subtree` shows subtree changes only, excluding outside files."""
    diff = fake.diff_subtree(Path("/repo"), "sha1", "main", SUBTREE)

    assert "SKILL.md" in diff
    assert "scripts/run.sh" in diff
    assert "-first line" in diff
    assert "+second line" in diff
    assert "README.md" not in diff


def test_diff_subtree_from_none_renders_full_content_as_added(fake: FakeGit) -> None:
    """With `from_sha=None`, the whole subtree at the ref is rendered as added."""
    diff = fake.diff_subtree(Path("/repo"), None, "main", SUBTREE)

    assert "SKILL.md" in diff
    assert "+second line" in diff
    assert "README.md" not in diff


def test_list_subtree_files_returns_relative_paths(fake: FakeGit) -> None:
    """`list_subtree_files` returns subtree-relative paths at the ref."""
    files = fake.list_subtree_files(Path("/repo"), "main", SUBTREE)

    assert sorted(files) == ["SKILL.md", "scripts/run.sh"]


def test_head_sha_unknown_ref_raises_git_error(fake: FakeGit) -> None:
    """An unknown ref surfaces as a typed GitError."""
    with pytest.raises(GitError):
        fake.head_sha(Path("/repo"), "no-such-ref")
