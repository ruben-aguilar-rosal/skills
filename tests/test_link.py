"""Tests for the flat, Claude Code-compatible LINK command."""

from pathlib import Path

import pytest

from skillsync.commands.link import LinkError, LinkAction, run_link
from skillsync.layout import write_text


def _seed_skill_set(root: Path, category: str, *names: str) -> dict[str, Path]:
    """Lay down minimal skills in one top-level category directory."""
    skills: dict[str, Path] = {}
    for name in names:
        write_text(root / "skills" / category / name / "SKILL.md", "# demo\n")
        skills[name] = (root / "skills" / category / name).resolve()
    return skills


def test_link_creates_one_direct_symlink_per_selected_skill(tmp_path: Path) -> None:
    """A fresh target exposes every selected skill as an immediate child."""
    documents = _seed_skill_set(tmp_path, "documents", "docx", "pdf")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents", "engineering"},
    )

    assert {a.name: a.action for a in actions} == {
        "code-review": "create",
        "docx": "create",
        "pdf": "create",
    }
    for name, source in {**documents, **engineering}.items():
        assert (target / name).resolve() == source
    assert not (target / "documents").exists()
    assert not (target / "engineering").exists()


def test_link_creates_target_dir_when_absent(tmp_path: Path) -> None:
    """The target directory is created only after selection validation succeeds."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "nested" / "agent_skills"

    run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert target.is_dir()
    assert (target / "docx").is_symlink()


def test_link_is_idempotent(tmp_path: Path) -> None:
    """Re-running an identical selection leaves direct links unchanged."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    run_link(tmp_path, target_dir=target, skill_sets={"documents"})
    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "unchanged")
    ]


def test_link_repoints_stale_selected_symlink(tmp_path: Path) -> None:
    """A direct skill symlink pointing elsewhere is refreshed."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "docx").symlink_to(tmp_path / "elsewhere")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [action.action for action in actions] == ["update"]
    assert (target / "docx").resolve() == documents["docx"]


def test_link_skips_conflicting_non_symlink_path(tmp_path: Path) -> None:
    """A real target path is reported but never clobbered."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "docx").mkdir()
    write_text(target / "docx" / "keep.txt", "precious")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [action.action for action in actions] == ["conflict"]
    assert not (target / "docx").is_symlink()
    assert (target / "docx" / "keep.txt").read_text() == "precious"


def test_link_removes_unselected_direct_repository_skill_link(tmp_path: Path) -> None:
    """Changing selection deletes a repository-owned direct link outside it."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "docx").symlink_to(documents["docx"])
    (target / "code-review").symlink_to(engineering["code-review"])

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "unchanged"),
        ("code-review", "remove"),
    ]
    assert (target / "docx").is_symlink()
    assert not (target / "code-review").exists()


def test_link_append_preserves_unselected_repository_links(tmp_path: Path) -> None:
    """Append mode adds selected skills without deactivating existing ones."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "code-review").symlink_to(engineering["code-review"])

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents"},
        append=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "docx").resolve() == documents["docx"]
    assert (target / "code-review").resolve() == engineering["code-review"]


def test_link_append_preserves_legacy_category_links(tmp_path: Path) -> None:
    """Append mode leaves old category links outside its selected skills alone."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    legacy = target / "engineering"
    legacy.symlink_to(tmp_path / "skills" / "engineering")

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents"},
        append=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "docx").resolve() == documents["docx"]
    assert legacy.is_symlink()


def test_link_append_refreshes_selected_stale_link(tmp_path: Path) -> None:
    """Append mode still repairs a selected link that points elsewhere."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "docx").symlink_to(tmp_path / "elsewhere")

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents"},
        append=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "update")]
    assert (target / "docx").resolve() == documents["docx"]


def test_link_migrates_legacy_category_links(tmp_path: Path) -> None:
    """A normal run replaces legacy category links with direct skill links."""
    documents = _seed_skill_set(tmp_path, "documents", "docx", "pdf")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(tmp_path / "skills" / "documents")
    (target / "engineering").symlink_to(tmp_path / "skills" / "engineering")

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "create"),
        ("pdf", "create"),
        ("documents", "remove"),
        ("engineering", "remove"),
    ]
    assert (target / "docx").resolve() == documents["docx"]
    assert (target / "pdf").resolve() == documents["pdf"]
    assert not (target / "documents").exists()
    assert not (target / "engineering").exists()
    assert engineering["code-review"].is_dir()


def test_link_preserves_external_and_noncanonical_repository_links(tmp_path: Path) -> None:
    """Cleanup leaves external links and repository links under custom names untouched."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (target / "external").symlink_to(external)
    (target / "renamed-docx").symlink_to(documents["docx"])

    actions = run_link(tmp_path, target_dir=target, skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "external").is_symlink()
    assert (target / "renamed-docx").is_symlink()


def test_link_rejects_duplicate_names_before_mutating(tmp_path: Path) -> None:
    """Duplicate global names are reported before any existing link is touched."""
    documents = _seed_skill_set(tmp_path, "documents", "shared")
    _seed_skill_set(tmp_path, "engineering", "shared")
    target = tmp_path / "agent_skills"
    target.mkdir()
    stale = target / "documents"
    stale.symlink_to(tmp_path / "skills" / "documents")

    with pytest.raises(LinkError, match="duplicate skill name"):
        run_link(
            tmp_path,
            target_dir=target,
            skill_sets={"documents", "engineering"},
        )

    assert stale.is_symlink()
    assert documents["shared"].is_dir()


def test_link_dry_run_makes_no_changes(tmp_path: Path) -> None:
    """Dry-run reports creation and legacy cleanup without changing the filesystem."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(tmp_path / "skills" / "documents")

    actions = run_link(
        tmp_path, target_dir=target, skill_sets={"documents"}, dry_run=True
    )

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "create"),
        ("documents", "remove"),
    ]
    assert not (target / "docx").exists()
    assert (target / "documents").resolve() == tmp_path / "skills" / "documents"
    assert documents["docx"].is_dir()


def test_link_append_dry_run_reports_no_removals(tmp_path: Path) -> None:
    """Append dry-run reports selected changes while preserving every existing link."""
    _seed_skill_set(tmp_path, "documents", "docx")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    existing = target / "code-review"
    existing.symlink_to(engineering["code-review"])

    actions = run_link(
        tmp_path,
        target_dir=target,
        skill_sets={"documents"},
        append=True,
        dry_run=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert not (target / "docx").exists()
    assert existing.resolve() == engineering["code-review"]


def test_link_rejects_empty_unknown_or_empty_category_before_mutating(
    tmp_path: Path,
) -> None:
    """Invalid selections fail before creating a target or removing stale links."""
    _seed_skill_set(tmp_path, "documents", "docx")
    (tmp_path / "skills" / "empty").mkdir(parents=True)
    target = tmp_path / "agent_skills"
    target.mkdir()
    stale = target / "documents"
    stale.symlink_to(tmp_path / "skills" / "documents")

    with pytest.raises(LinkError, match="at least one"):
        run_link(tmp_path, target_dir=target, skill_sets=set())
    with pytest.raises(LinkError, match="unknown skill set"):
        run_link(tmp_path, target_dir=target, skill_sets={"missing"})
    with pytest.raises(LinkError, match="contain no skill folders"):
        run_link(tmp_path, target_dir=target, skill_sets={"empty"})

    assert stale.is_symlink()


def test_link_action_is_a_dataclass_carrying_paths(tmp_path: Path) -> None:
    """Each LinkAction carries the direct skill source and target paths."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    [action] = run_link(
        tmp_path, target_dir=target, skill_sets={"documents"}, dry_run=True
    )

    assert isinstance(action, LinkAction)
    assert action.name == "docx"
    assert action.link_path == target / "docx"
    assert action.source == documents["docx"]
