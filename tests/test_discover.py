"""Tests for the deterministic DISCOVER stage (`skillsync.stages.discover`).

`discover` walks each source's `watch` folders, lists the subfolders that contain a
`SKILL.md` upstream, and classifies them against the pins:

- **new** — a discovered skill that is neither pinned nor ignored (surface for adoption);
- **removed** — a pinned skill under a watched folder that no longer exists upstream.

It is deterministic (no LLM) and drives the injected `FakeGit`.
"""

from pathlib import Path

from skillsync.config import Config, SkillPin, Source
from skillsync.stages.discover import Discovery, discover
from skillsync.testing.fakes import FakeGit


def _git_with_skills(*skill_dirs: str) -> FakeGit:
    """A FakeGit whose `main` commit holds a SKILL.md under each given dir."""
    git = FakeGit()
    git.add_commit(
        "sha1", {f"{d.rstrip('/')}/SKILL.md": f"# {d}\n" for d in skill_dirs}
    )
    git.set_ref("main", "sha1")
    return git


def _source(
    *,
    skills: list[SkillPin] | None = None,
    watch: list[str] | None = None,
    ignore: list[str] | None = None,
) -> Config:
    """A single-source config with the given pins/watch/ignore."""
    return Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=skills or [],
                watch=watch or [],
                ignore=ignore or [],
            )
        ]
    )


def test_discovers_new_skill_in_watched_folder(tmp_path: Path) -> None:
    """A SKILL.md folder under a watched dir that isn't pinned is reported as new."""
    git = _git_with_skills("engineering/to-issues", "engineering/pr-review")
    config = _source(
        skills=[SkillPin(path="engineering/to-issues", synced_sha="sha1")],
        watch=["engineering/"],
    )

    found = discover(config, git, tmp_path)

    assert found == [
        Discovery(
            repo="owner/repo",
            skill_path="engineering/pr-review",
            name="pr-review",
            kind="new",
        )
    ]


def test_ignored_paths_are_not_surfaced(tmp_path: Path) -> None:
    """A discovered skill on the ignore list is not reported as new."""
    git = _git_with_skills("engineering/to-issues", "engineering/experimental")
    config = _source(watch=["engineering/"], ignore=["engineering/experimental"])

    found = discover(config, git, tmp_path)

    assert [d.skill_path for d in found] == ["engineering/to-issues"]


def test_removed_pinned_skill_is_reported(tmp_path: Path) -> None:
    """A pinned skill under a watched folder that vanished upstream is reported removed."""
    git = _git_with_skills("engineering/to-issues")  # pr-review is gone upstream
    config = _source(
        skills=[
            SkillPin(path="engineering/to-issues", synced_sha="sha1"),
            SkillPin(path="engineering/pr-review", synced_sha="sha1"),
        ],
        watch=["engineering/"],
    )

    found = discover(config, git, tmp_path)

    assert found == [
        Discovery(
            repo="owner/repo",
            skill_path="engineering/pr-review",
            name="pr-review",
            kind="removed",
        )
    ]


def test_pinned_skill_outside_watch_is_never_removed(tmp_path: Path) -> None:
    """A pin that isn't under any watched folder is left alone, never marked removed."""
    git = _git_with_skills("engineering/to-issues")
    config = _source(
        skills=[
            SkillPin(path="engineering/to-issues", synced_sha="sha1"),
            SkillPin(path="manual/hand-added", synced_sha="sha1"),
        ],
        watch=["engineering/"],
    )

    found = discover(config, git, tmp_path)

    assert found == []


def test_source_without_watch_discovers_nothing(tmp_path: Path) -> None:
    """A source with no watch folders never touches git and discovers nothing."""
    git = FakeGit()  # any git call would raise (empty history)
    config = _source(skills=[SkillPin(path="engineering/to-issues", synced_sha="sha1")])

    assert discover(config, git, tmp_path) == []


def test_nested_skill_paths_resolve_to_their_skill_folder(tmp_path: Path) -> None:
    """A deeply nested SKILL.md is reported at its own folder, not the watch root."""
    git = _git_with_skills("category/group/deep-skill")
    config = _source(watch=["category/"])

    found = discover(config, git, tmp_path)

    assert found == [
        Discovery(
            repo="owner/repo",
            skill_path="category/group/deep-skill",
            name="deep-skill",
            kind="new",
        )
    ]


def test_offline_git_error_yields_no_discoveries(tmp_path: Path) -> None:
    """An unreachable watch folder degrades to no discoveries rather than raising."""
    git = FakeGit()
    git.add_commit("sha1", {"other/thing.txt": "x"})
    git.set_ref("main", "sha1")  # ref resolves, but listing engineering/ is empty
    config = _source(watch=["engineering/"])

    assert discover(config, git, tmp_path) == []
