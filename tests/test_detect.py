"""Tests for the deterministic DETECT stage, driven entirely by `FakeGit`.

Each case constructs an in-memory history and a `Config` pin, then asserts the
`ChangeSet` kind the detector reports — no disk, no network, no real git.
"""

from pathlib import Path

import pytest

from skillsync.config import Config, SkillPin, Source
from skillsync.stages.detect import ChangeSet, detect
from skillsync.testing.fakes import FakeGit

REPO = "owner/repo"
SUBTREE = "skills/demo"


def _config(synced_sha: str | None, *, hold: bool = False) -> Config:
    """Build a single-source, single-skill config pinned at `synced_sha`."""
    return Config(
        sources=[
            Source(
                repo=REPO,
                ref="main",
                skills=[SkillPin(path=SUBTREE, synced_sha=synced_sha, hold=hold)],
            )
        ]
    )


@pytest.fixture
def fake() -> FakeGit:
    """A repo with two commits touching `skills/demo`; `main` at the second."""
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "# Demo\nfirst line\n"})
    git.add_commit("sha2", {"skills/demo/SKILL.md": "# Demo\nsecond line\n"})
    git.set_ref("main", "sha2")
    return git


def test_no_change_when_synced_at_head(fake: FakeGit) -> None:
    """A pin already at HEAD yields a single `none` change set with empty diff."""
    changes = detect(_config("sha2"), fake, Path("/repo"))

    assert len(changes) == 1
    change = changes[0]
    assert change.kind == "none"
    assert change.from_sha == "sha2"
    assert change.to_sha == "sha2"
    assert change.diff == ""
    assert change.changed_files == []


def test_normal_change_reports_changed_with_diff(fake: FakeGit) -> None:
    """A pin behind HEAD on the same history reports `changed` with the subtree diff."""
    [change] = detect(_config("sha1"), fake, Path("/repo"))

    assert change.kind == "changed"
    assert change.from_sha == "sha1"
    assert change.to_sha == "sha2"
    assert "-first line" in change.diff
    assert "+second line" in change.diff
    assert change.changed_files == ["SKILL.md"]


def test_new_skill_with_none_sha_is_reonboard_with_full_content(fake: FakeGit) -> None:
    """A pin with no `synced_sha` is a `reonboard` whose diff is the full subtree."""
    [change] = detect(_config(None), fake, Path("/repo"))

    assert change.kind == "reonboard"
    assert change.rewritten_history is False
    assert change.from_sha is None
    assert change.to_sha == "sha2"
    assert "+second line" in change.diff
    assert change.changed_files == ["SKILL.md"]


def test_rewritten_history_is_reonboard(fake: FakeGit) -> None:
    """A `synced_sha` not an ancestor of the ref (force-push) becomes a `reonboard`."""
    # `orphan` is a real commit but off the linear path to `main`.
    fake.add_commit("orphan", {"skills/demo/SKILL.md": "# Demo\nrewritten\n"})

    [change] = detect(_config("sha2"), fake, Path("/repo"))
    # sha2 is HEAD on the main line, so it IS an ancestor -> not a reonboard.
    assert change.kind == "none"

    # But pinning at a later, off-line commit means HEAD is not a descendant.
    fake.set_ref("main", "sha1")
    [change] = detect(_config("sha2"), fake, Path("/repo"))
    assert change.kind == "reonboard"
    assert change.rewritten_history is True
    assert change.from_sha is None
    assert change.to_sha == "sha1"


def test_held_skill_is_skipped(fake: FakeGit) -> None:
    """A pin with `hold=True` is excluded from detection entirely."""
    assert detect(_config("sha1", hold=True), fake, Path("/repo")) == []


def test_changeset_carries_skill_path_and_name(fake: FakeGit) -> None:
    """Each change set records its subtree path and last-segment name."""
    [change] = detect(_config("sha1"), fake, Path("/repo"))

    assert isinstance(change, ChangeSet)
    assert change.skill_path == SUBTREE
    assert change.name == "demo"
