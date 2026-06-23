"""Tests for surfacing discoveries as awareness issues (`commands.discovery`).

`surface_discoveries` runs the discover stage and opens ONE awareness issue per new
or removed skill — idempotently: a skill already surfaced (an open issue with the
same title exists) is not filed again. It never onboards anything; adoption stays
the explicit `skillsync add`. Drives the injected `FakeGit` + `FakeGh`.
"""

from pathlib import Path

from skillsync.commands.discovery import DiscoveryNotice, surface_discoveries
from skillsync.config import Config, SkillPin, Source
from skillsync.testing.fakes import FakeGh, FakeGit


def _git_with_skills(*skill_dirs: str) -> FakeGit:
    """A FakeGit whose `main` commit holds a SKILL.md under each given dir."""
    git = FakeGit()
    git.add_commit("sha1", {f"{d.rstrip('/')}/SKILL.md": f"# {d}\n" for d in skill_dirs})
    git.set_ref("main", "sha1")
    return git


def _config(
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


def test_new_skill_opens_one_awareness_issue(tmp_path: Path) -> None:
    """A newly-discovered skill is surfaced as a single issue with adopt/ignore hints."""
    git = _git_with_skills("engineering/to-issues", "engineering/pr-review")
    config = _config(
        skills=[SkillPin(path="engineering/to-issues", synced_sha="sha1")],
        watch=["engineering/"],
    )
    gh = FakeGh()

    notices = surface_discoveries(config, tmp_path, git=git, gh=gh)

    assert [n.skill_path for n in notices] == ["engineering/pr-review"]
    assert isinstance(notices[0], DiscoveryNotice)
    opened = [c for c in gh.calls if c.method == "open_issue"]
    assert len(opened) == 1
    title, body = opened[0].args[1], opened[0].args[2]
    assert "pr-review" in title
    # The body teaches both the adopt and the reject path.
    assert "skillsync add owner/repo engineering/pr-review" in body
    assert "skillsync ignore owner/repo engineering/pr-review" in body


def test_duplicate_is_not_filed_twice(tmp_path: Path) -> None:
    """Re-running discovery does not file a second issue for the same skill."""
    git = _git_with_skills("engineering/to-issues")
    config = _config(watch=["engineering/"])
    gh = FakeGh()

    surface_discoveries(config, tmp_path, git=git, gh=gh)
    surface_discoveries(config, tmp_path, git=git, gh=gh)

    opened = [c for c in gh.calls if c.method == "open_issue"]
    assert len(opened) == 1  # the second run reused the existing issue


def test_removed_skill_is_surfaced(tmp_path: Path) -> None:
    """A pinned skill gone from upstream is surfaced as a removed-skill issue."""
    git = _git_with_skills("engineering/to-issues")
    config = _config(
        skills=[
            SkillPin(path="engineering/to-issues", synced_sha="sha1"),
            SkillPin(path="engineering/pr-review", synced_sha="sha1"),
        ],
        watch=["engineering/"],
    )
    gh = FakeGh()

    notices = surface_discoveries(config, tmp_path, git=git, gh=gh)

    assert [(n.kind, n.skill_path) for n in notices] == [
        ("removed", "engineering/pr-review")
    ]
    title = next(c for c in gh.calls if c.method == "open_issue").args[1]
    assert "no longer" in title.lower() or "removed" in title.lower()


def test_no_watch_no_issues(tmp_path: Path) -> None:
    """With no watch folders, discovery surfaces nothing and never calls gh."""
    git = FakeGit()
    config = _config(skills=[SkillPin(path="engineering/to-issues", synced_sha="sha1")])
    gh = FakeGh()

    notices = surface_discoveries(config, tmp_path, git=git, gh=gh)

    assert notices == []
    assert gh.calls == []
