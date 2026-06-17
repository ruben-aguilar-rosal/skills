"""Tests for the STATUS report (`skillsync.commands.status`).

`gather_status` builds one row per on-disk skill folder showing: the short
`synced_sha` from its pin, whether upstream is ahead (via the injected `GitPort`,
offline-tolerant — `None` when it cannot be determined), whether the committed
`SKILL.md` has drifted from its `.generated` snapshot, and whether the skill is
linked into the target skills dir. The git port is optional so these tests run
with `git=None` (offline) except where upstream-ahead is exercised explicitly.
"""

from pathlib import Path

from skillsync.commands.status import SkillStatus, gather_status
from skillsync.config import Config, SkillPin, Source
from skillsync.layout import write_text
from skillsync.testing.fakes import FakeGit


def _config(name: str, synced_sha: str | None) -> Config:
    """A config pinning one skill `skills/<name>` at `synced_sha`."""
    return Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[SkillPin(path=f"skills/{name}", synced_sha=synced_sha)],
            )
        ]
    )


def test_status_reports_short_sha_and_drift_offline(tmp_path: Path) -> None:
    """Offline (git=None): a drifted skill reports its short sha, drift, no ahead."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "hand-edited\n")
    write_text(tmp_path / "skills" / "demo" / ".generated" / "SKILL.md", "generated\n")
    config = _config("demo", "abcdef1234567")

    rows = gather_status(config, tmp_path, git=None, target_dir=tmp_path / "links")

    assert [r.name for r in rows] == ["demo"]
    row = rows[0]
    assert isinstance(row, SkillStatus)
    assert row.synced_sha == "abcdef1"
    assert row.drift is True
    assert row.upstream_ahead is None
    assert row.linked is False


def test_status_no_drift_when_skill_matches_snapshot(tmp_path: Path) -> None:
    """A SKILL.md identical to its snapshot reports no drift."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "same\n")
    write_text(tmp_path / "skills" / "demo" / ".generated" / "SKILL.md", "same\n")
    config = _config("demo", "abc1234")

    [row] = gather_status(config, tmp_path, git=None, target_dir=tmp_path / "links")

    assert row.drift is False


def test_status_reports_linked_state(tmp_path: Path) -> None:
    """A skill symlinked into the target dir reports `linked=True`."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    target = tmp_path / "links"
    target.mkdir()
    (target / "demo").symlink_to((tmp_path / "skills" / "demo").resolve())
    config = _config("demo", "abc1234")

    [row] = gather_status(config, tmp_path, git=None, target_dir=target)

    assert row.linked is True


def test_status_unlinked_when_symlink_points_elsewhere(tmp_path: Path) -> None:
    """A symlink pointing at a different folder does not count as linked."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    target = tmp_path / "links"
    target.mkdir()
    (target / "demo").symlink_to(tmp_path / "somewhere-else")
    config = _config("demo", "abc1234")

    [row] = gather_status(config, tmp_path, git=None, target_dir=target)

    assert row.linked is False


def test_status_upstream_ahead_via_git(tmp_path: Path) -> None:
    """With a git port, a synced_sha behind HEAD reports upstream ahead."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "old\n"})
    git.add_commit("sha2", {"skills/demo/SKILL.md": "new\n"})
    git.set_ref("main", "sha2")
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dir=tmp_path / "links")

    assert row.upstream_ahead is True


def test_status_upstream_not_ahead_when_synced_to_head(tmp_path: Path) -> None:
    """A synced_sha equal to HEAD reports upstream not ahead."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "old\n"})
    git.set_ref("main", "sha1")
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dir=tmp_path / "links")

    assert row.upstream_ahead is False


def test_status_upstream_ahead_none_on_git_error(tmp_path: Path) -> None:
    """An unreachable ref degrades upstream-ahead to None rather than raising."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()  # empty history: any ref lookup raises GitError
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dir=tmp_path / "links")

    assert row.upstream_ahead is None


def test_status_skill_absent_from_config_has_no_sha(tmp_path: Path) -> None:
    """A skill folder present on disk but unpinned reports no sha and no ahead."""
    write_text(tmp_path / "skills" / "orphan" / "SKILL.md", "x\n")
    config = Config(sources=[])

    [row] = gather_status(config, tmp_path, git=None, target_dir=tmp_path / "links")

    assert row.name == "orphan"
    assert row.synced_sha is None
    assert row.upstream_ahead is None


def test_status_empty_repo_yields_no_rows(tmp_path: Path) -> None:
    """A repo with no skill folders yields no status rows."""
    rows = gather_status(
        Config(sources=[]), tmp_path, git=None, target_dir=tmp_path / "links"
    )

    assert rows == []
