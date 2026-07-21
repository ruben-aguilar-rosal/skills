"""Tests for the selected-category LINK command.

`run_link` creates category symlinks under a configurable target directory, pruning
only stale symlinks that are direct children of the repository's `skills/` directory.
"""

from pathlib import Path

import pytest

from skillsync.commands.link import LinkError, LinkAction, run_link
from skillsync.layout import write_text


def _seed_skill_set(root: Path, name: str) -> Path:
    """Lay down a minimal nested skill in one top-level category directory."""
    write_text(root / "skills" / name / "demo" / "SKILL.md", "# demo\n")
    return (root / "skills" / name).resolve()


def test_link_creates_one_symlink_per_selected_skill_set(tmp_path: Path) -> None:
    """A fresh target gets one category symlink for each requested set."""
    documents = _seed_skill_set(tmp_path, "documents")
    engineering = _seed_skill_set(tmp_path, "engineering")
    target = tmp_path / "agent_skills"

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents", "engineering"},
    )

    assert {a.name: a.action for a in actions} == {
        "documents": "create",
        "engineering": "create",
    }
    assert (target / "documents").resolve() == documents
    assert (target / "engineering").resolve() == engineering


def test_link_creates_target_dir_when_absent(tmp_path: Path) -> None:
    """The target directory is created only after selection validation succeeds."""
    _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "nested" / "agent_skills"

    run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert target.is_dir()
    assert (target / "documents").is_symlink()


def test_link_is_idempotent(tmp_path: Path) -> None:
    """Re-running an identical selection reports its category link unchanged."""
    _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"

    run_link(tmp_path, target_dir=target, skill_sets={"documents"})
    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [a.action for a in actions] == ["unchanged"]


def test_link_repoints_stale_selected_symlink(tmp_path: Path) -> None:
    """A selected category symlink pointing elsewhere is refreshed."""
    documents = _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(tmp_path / "elsewhere")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [a.action for a in actions] == ["update"]
    assert (target / "documents").resolve() == documents


def test_link_skips_conflicting_non_symlink_path(tmp_path: Path) -> None:
    """A real target path is reported but never clobbered."""
    _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").mkdir()
    write_text(target / "documents" / "keep.txt", "precious")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [a.action for a in actions] == ["conflict"]
    assert not (target / "documents").is_symlink()
    assert (target / "documents" / "keep.txt").read_text() == "precious"


def test_link_removes_unselected_repository_owned_symlink(tmp_path: Path) -> None:
    """Changing selection deletes stale category symlinks owned by this repository."""
    documents = _seed_skill_set(tmp_path, "documents")
    engineering = _seed_skill_set(tmp_path, "engineering")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(documents)
    (target / "engineering").symlink_to(engineering)

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(a.name, a.action) for a in actions] == [
        ("documents", "unchanged"),
        ("engineering", "remove"),
    ]
    assert (target / "documents").is_symlink()
    assert not (target / "engineering").exists()


def test_link_preserves_external_and_non_category_target_entries(tmp_path: Path) -> None:
    """Cleanup leaves external links and links into nested repository paths untouched."""
    documents = _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"
    target.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (target / "external").symlink_to(external)
    (target / "nested").symlink_to(documents / "demo")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(a.name, a.action) for a in actions] == [("documents", "create")]
    assert (target / "external").is_symlink()
    assert (target / "nested").is_symlink()


def test_link_dry_run_makes_no_changes(tmp_path: Path) -> None:
    """Dry-run reports planned creation and removal without filesystem changes."""
    documents = _seed_skill_set(tmp_path, "documents")
    engineering = _seed_skill_set(tmp_path, "engineering")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "engineering").symlink_to(engineering)

    actions = run_link(
        tmp_path, target_dir=target, skill_sets={"documents"}, dry_run=True
    )

    assert [(a.name, a.action) for a in actions] == [
        ("documents", "create"),
        ("engineering", "remove"),
    ]
    assert not (target / "documents").exists()
    assert (target / "engineering").resolve() == engineering


def test_link_rejects_empty_or_unknown_selection_before_mutating(tmp_path: Path) -> None:
    """Invalid selection errors before it creates a target or removes stale links."""
    documents = _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"
    target.mkdir()
    stale = target / "documents"
    stale.symlink_to(documents)

    with pytest.raises(LinkError, match="at least one"):
        run_link(tmp_path, target_dir=target, skill_sets=set())
    with pytest.raises(LinkError, match="unknown skill set"):
        run_link(tmp_path, target_dir=target, skill_sets={"missing"})

    assert stale.is_symlink()


def test_link_action_is_a_dataclass_carrying_paths(tmp_path: Path) -> None:
    """Each LinkAction carries the selected category's source and target paths."""
    documents = _seed_skill_set(tmp_path, "documents")
    target = tmp_path / "agent_skills"

    [action] = run_link(
        tmp_path, target_dir=target, skill_sets={"documents"}, dry_run=True
    )

    assert isinstance(action, LinkAction)
    assert action.name == "documents"
    assert action.link_path == target / "documents"
    assert action.source == documents
