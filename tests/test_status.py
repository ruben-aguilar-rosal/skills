"""Tests for the STATUS report (`skillsync.commands.status`).

`gather_status` builds one row per on-disk skill folder showing: the short
`synced_sha` from its pin, whether upstream is ahead (via the injected `GitPort`,
offline-tolerant — `None` when it cannot be determined), whether the committed
`SKILL.md` has drifted from its `.generated` snapshot, and whether the skill is
installed into every target skills dir. The git port is optional so these tests run
with `git=None` (offline) except where upstream-ahead is exercised explicitly.
"""

import json
from pathlib import Path

from skillsync.commands.install import MARKER_NAME, run_install
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

    rows = gather_status(config, tmp_path, git=None, target_dirs=[tmp_path / "links"])

    assert [r.name for r in rows] == ["demo"]
    row = rows[0]
    assert isinstance(row, SkillStatus)
    assert row.origin == "vendored"
    assert row.synced_sha == "abcdef1"
    assert row.drift is True
    assert row.upstream_ahead is None
    assert row.installed is False


def test_status_no_drift_when_skill_matches_snapshot(tmp_path: Path) -> None:
    """A SKILL.md identical to its snapshot reports no drift."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "same\n")
    write_text(tmp_path / "skills" / "demo" / ".generated" / "SKILL.md", "same\n")
    config = _config("demo", "abc1234")

    [row] = gather_status(config, tmp_path, git=None, target_dirs=[tmp_path / "links"])

    assert row.drift is False


def test_status_reports_installed_after_install_run(tmp_path: Path) -> None:
    """A skill is installed when the target holds a copy made from its folder."""
    write_text(tmp_path / "skills" / "documents" / "demo" / "SKILL.md", "x\n")
    target = tmp_path / "links"
    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                dest="skills/documents",
                skills=[SkillPin(path="upstream/demo", synced_sha="abc1234")],
            )
        ]
    )

    [row] = gather_status(config, tmp_path, git=None, target_dirs=[target])

    assert row.installed is True


def test_status_uninstalled_when_missing_from_one_target(tmp_path: Path) -> None:
    """Installed in one target but not the other still reports uninstalled."""
    write_text(tmp_path / "skills" / "documents" / "demo" / "SKILL.md", "x\n")
    agents, claude = tmp_path / "agents", tmp_path / "claude"
    run_install(tmp_path, target_dirs=[agents], skill_sets={"documents"})

    [row] = gather_status(
        Config(sources=[]), tmp_path, git=None, target_dirs=[agents, claude]
    )

    assert row.installed is False


def test_status_uninstalled_when_copy_records_another_source(tmp_path: Path) -> None:
    """A copy under this name installed from somewhere else does not count."""
    write_text(tmp_path / "skills" / "documents" / "demo" / "SKILL.md", "x\n")
    target = tmp_path / "links"
    marker = {"digest": "d", "source": str(tmp_path / "elsewhere" / "demo")}
    write_text(target / "demo" / MARKER_NAME, json.dumps(marker))

    [row] = gather_status(Config(sources=[]), tmp_path, git=None, target_dirs=[target])

    assert row.installed is False


def test_status_uninstalled_through_legacy_symlinks(tmp_path: Path) -> None:
    """Links left by the symlink era do not count: installing is what replaces them."""
    skill = tmp_path / "skills" / "documents" / "demo"
    write_text(skill / "SKILL.md", "x\n")
    target = tmp_path / "links"
    target.mkdir()
    (target / "demo").symlink_to(skill.resolve())
    (target / "documents").symlink_to((tmp_path / "skills" / "documents").resolve())

    [row] = gather_status(Config(sources=[]), tmp_path, git=None, target_dirs=[target])

    assert row.installed is False


def test_status_upstream_ahead_via_git(tmp_path: Path) -> None:
    """With a git port, a synced_sha behind HEAD reports upstream ahead."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "old\n"})
    git.add_commit("sha2", {"skills/demo/SKILL.md": "new\n"})
    git.set_ref("main", "sha2")
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dirs=[tmp_path / "links"])

    assert row.upstream_ahead is True


def test_status_upstream_not_ahead_when_synced_to_head(tmp_path: Path) -> None:
    """A synced_sha equal to HEAD reports upstream not ahead."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "old\n"})
    git.set_ref("main", "sha1")
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dirs=[tmp_path / "links"])

    assert row.upstream_ahead is False


def test_status_upstream_ahead_none_on_git_error(tmp_path: Path) -> None:
    """An unreachable ref degrades upstream-ahead to None rather than raising."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")
    git = FakeGit()  # empty history: any ref lookup raises GitError
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dirs=[tmp_path / "links"])

    assert row.upstream_ahead is None


def test_status_reads_skill_under_custom_dest(tmp_path: Path) -> None:
    """A skill pinned with a custom dest is read from that dest, not flat skills/."""
    write_text(tmp_path / "skills" / "aily" / "demo" / "SKILL.md", "hand\n")
    write_text(tmp_path / "skills" / "aily" / "demo" / ".generated" / "SKILL.md", "gen\n")
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                dest="skills/aily",
                skills=[SkillPin(path="x/demo", synced_sha="abc1234")],
            )
        ]
    )

    [row] = gather_status(config, tmp_path, git=None, target_dirs=[tmp_path / "links"])

    assert row.name == "demo"
    assert row.synced_sha == "abc1234"
    assert row.drift is True  # read from skills/aily/demo, where the files are


def test_status_empty_repo_yields_no_rows(tmp_path: Path) -> None:
    """A repo with no skill folders yields no status rows."""
    rows = gather_status(
        Config(sources=[]), tmp_path, git=None, target_dirs=[tmp_path / "links"]
    )

    assert rows == []


class _CountingGit(FakeGit):
    """A FakeGit that records every `remote_head` call, to assert dedup."""

    def __init__(self) -> None:
        super().__init__()
        self.remote_head_calls: list[tuple[str, str]] = []

    def remote_head(self, repo: str, ref: str) -> str:
        self.remote_head_calls.append((repo, ref))
        return super().remote_head(repo, ref)


def test_status_resolves_each_repo_head_once(tmp_path: Path) -> None:
    """Many pins over one (repo, ref) trigger a single upstream probe, not one per pin."""
    for name in ("a", "b", "c"):
        write_text(tmp_path / "skills" / name / "SKILL.md", "x\n")
    git = _CountingGit()
    git.add_commit("sha1", {"skills/a/SKILL.md": "x\n"})
    git.set_ref("main", "sha1")
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path="skills/a", synced_sha="sha1"),
                    SkillPin(path="skills/b", synced_sha="sha1"),
                    SkillPin(path="skills/c", synced_sha="sha1"),
                ],
            )
        ]
    )

    rows = gather_status(config, tmp_path, git=git, target_dirs=[tmp_path / "links"])

    assert len(rows) == 3
    assert all(r.upstream_ahead is False for r in rows)
    # Three pins, one (repo, ref) — exactly one network probe.
    assert git.remote_head_calls == [("owner/repo", "main")]


def test_status_uses_remote_head_not_mirror(tmp_path: Path) -> None:
    """The upstream probe goes through the no-fetch `remote_head`, never `mirror`."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "x\n")

    class _NoMirrorGit(_CountingGit):
        def mirror(self, repo: str, ref: str):  # pragma: no cover - must not be hit
            raise AssertionError("status must not call mirror() for the upstream probe")

    git = _NoMirrorGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "x\n"})
    git.set_ref("main", "sha1")
    config = _config("demo", "sha1")

    [row] = gather_status(config, tmp_path, git=git, target_dirs=[tmp_path / "links"])

    assert row.upstream_ahead is False
    assert git.remote_head_calls == [("owner/repo", "main")]


def test_status_includes_local_skill_absent_from_config(tmp_path: Path) -> None:
    """A hand-written skill with no pin appears as `local`, no sha, no upstream."""
    write_text(tmp_path / "skills" / "meta" / "mine" / "SKILL.md", "x\n")

    [row] = gather_status(
        Config(sources=[]), tmp_path, git=None, target_dirs=[tmp_path / "links"]
    )

    assert row.name == "mine"
    assert row.origin == "local"
    assert row.synced_sha is None
    assert row.upstream_ahead is None


def test_status_lists_both_vendored_and_local(tmp_path: Path) -> None:
    """Vendored and local skills are both reported, tagged by origin, sorted by name."""
    write_text(tmp_path / "skills" / "vend" / "SKILL.md", "v\n")
    write_text(tmp_path / "skills" / "meta" / "mine" / "SKILL.md", "m\n")
    config = _config("vend", "abc1234")

    rows = gather_status(config, tmp_path, git=None, target_dirs=[tmp_path / "links"])

    by_name = {r.name: r.origin for r in rows}
    assert by_name == {"mine": "local", "vend": "vendored"}
