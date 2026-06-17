"""Tests for the LINK command (`skillsync.commands.link`).

`run_link` symlinks every skill folder under `skills/` into the native skills
directory (`~/.claude/skills/<name>` in real use). The target dir is configurable
so these tests point it at `tmp_path` and never touch the real home directory:

- **create** → a fresh target dir gets one symlink per skill, each pointing at the
  skill folder;
- **idempotent** → a second run repoints nothing and reports every link unchanged;
- **conflict** → a pre-existing non-symlink path is skipped with a warning, never
  clobbered;
- **dry-run** → planned actions are returned but the filesystem is untouched.
"""

from pathlib import Path

from skillsync.commands.link import LinkAction, run_link
from skillsync.layout import write_text


def _seed_skill(root: Path, name: str) -> Path:
    """Lay down a minimal on-disk skill folder under `skills/<name>/`."""
    write_text(root / "skills" / name / "SKILL.md", f"# {name}\n")
    return (root / "skills" / name).resolve()


def test_link_creates_one_symlink_per_skill(tmp_path: Path) -> None:
    """A fresh target dir gets a symlink per skill pointing at the skill folder."""
    demo = _seed_skill(tmp_path, "demo")
    gamma = _seed_skill(tmp_path, "gamma")
    target = tmp_path / "claude_skills"

    actions = run_link(tmp_path, target_dir=target)

    assert {a.name: a.action for a in actions} == {"demo": "create", "gamma": "create"}
    assert (target / "demo").is_symlink()
    assert (target / "gamma").is_symlink()
    assert (target / "demo").resolve() == demo
    assert (target / "gamma").resolve() == gamma


def test_link_creates_target_dir_when_absent(tmp_path: Path) -> None:
    """The target dir is created on demand when it does not yet exist."""
    _seed_skill(tmp_path, "demo")
    target = tmp_path / "nested" / "claude_skills"

    run_link(tmp_path, target_dir=target)

    assert target.is_dir()
    assert (target / "demo").is_symlink()


def test_link_is_idempotent(tmp_path: Path) -> None:
    """Re-running over an already-linked target repoints nothing and reports unchanged."""
    _seed_skill(tmp_path, "demo")
    target = tmp_path / "claude_skills"

    run_link(tmp_path, target_dir=target)
    actions = run_link(tmp_path, target_dir=target)

    assert [a.action for a in actions] == ["unchanged"]
    assert (target / "demo").is_symlink()


def test_link_repoints_a_stale_symlink(tmp_path: Path) -> None:
    """A symlink pointing somewhere else is refreshed to the skill folder."""
    demo = _seed_skill(tmp_path, "demo")
    target = tmp_path / "claude_skills"
    target.mkdir()
    (target / "demo").symlink_to(tmp_path / "elsewhere")

    actions = run_link(tmp_path, target_dir=target)

    assert [a.action for a in actions] == ["update"]
    assert (target / "demo").resolve() == demo


def test_link_skips_conflicting_non_symlink_path(tmp_path: Path) -> None:
    """A real (non-symlink) path at the target is skipped, warned, and never clobbered."""
    _seed_skill(tmp_path, "demo")
    target = tmp_path / "claude_skills"
    target.mkdir()
    # A real directory occupies the slot the symlink would take.
    (target / "demo").mkdir()
    write_text(target / "demo" / "keep.txt", "precious")

    actions = run_link(tmp_path, target_dir=target)

    assert [a.action for a in actions] == ["conflict"]
    # The conflicting path is untouched: still a real dir with its file.
    assert not (target / "demo").is_symlink()
    assert (target / "demo" / "keep.txt").read_text() == "precious"


def test_link_dry_run_makes_no_changes(tmp_path: Path) -> None:
    """`dry_run=True` returns the planned actions but writes nothing to disk."""
    _seed_skill(tmp_path, "demo")
    target = tmp_path / "claude_skills"

    actions = run_link(tmp_path, target_dir=target, dry_run=True)

    assert [a.action for a in actions] == ["create"]
    assert not target.exists()


def test_link_reports_nothing_when_no_skills(tmp_path: Path) -> None:
    """A repo with no skill folders yields no link actions."""
    actions = run_link(tmp_path, target_dir=tmp_path / "claude_skills")

    assert actions == []


def test_link_action_is_a_dataclass_carrying_paths(tmp_path: Path) -> None:
    """Each LinkAction carries the link path and its resolved skill-folder source."""
    demo = _seed_skill(tmp_path, "demo")
    target = tmp_path / "claude_skills"

    [action] = run_link(tmp_path, target_dir=target, dry_run=True)

    assert isinstance(action, LinkAction)
    assert action.name == "demo"
    assert action.link_path == target / "demo"
    assert action.source == demo
