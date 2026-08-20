"""Tests for the copy-based, Claude Code-compatible INSTALL command."""

import json
from pathlib import Path

import pytest

from skillsync.commands.install import (
    MARKER_NAME,
    InstallAction,
    InstallError,
    installed_from,
    run_install,
)
from skillsync.layout import write_text


def _seed_skill_set(root: Path, category: str, *names: str) -> dict[str, Path]:
    """Lay down minimal skills in one top-level category directory."""
    skills: dict[str, Path] = {}
    for name in names:
        write_text(root / "skills" / category / name / "SKILL.md", "# demo\n")
        skills[name] = (root / "skills" / category / name).resolve()
    return skills


def test_install_copies_each_selected_skill_into_every_target(tmp_path: Path) -> None:
    """A fresh target holds a real directory per selected skill, not a symlink."""
    _seed_skill_set(tmp_path, "documents", "docx", "pdf")
    _seed_skill_set(tmp_path, "engineering", "code-review")
    agents, claude = tmp_path / "agents", tmp_path / "claude"

    actions = run_install(
        tmp_path,
        target_dirs=[agents, claude],
        skill_sets={"documents", "engineering"},
    )

    assert {(a.name, a.path.parent, a.action) for a in actions} == {
        (name, target, "create")
        for name in ("code-review", "docx", "pdf")
        for target in (agents, claude)
    }
    for target in (agents, claude):
        for name in ("code-review", "docx", "pdf"):
            copy = target / name
            assert copy.is_dir() and not copy.is_symlink()
            assert (copy / "SKILL.md").read_text() == "# demo\n"
        assert not (target / "documents").exists()


def test_install_copies_aux_files_but_not_repository_bookkeeping(tmp_path: Path) -> None:
    """Scripts and references travel; `.upstream/`, `.generated/`, adaptation stay home."""
    skill = tmp_path / "skills" / "documents" / "docx"
    write_text(skill / "SKILL.md", "# docx\n")
    write_text(skill / "scripts" / "run.py", "print('hi')\n")
    write_text(skill / "references" / "notes.md", "notes\n")
    write_text(skill / "adaptation.md", "rules\n")
    write_text(skill / ".upstream" / "SKILL.md", "pristine\n")
    write_text(skill / ".generated" / "SKILL.md", "# docx\n")
    target = tmp_path / "agent_skills"

    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    copy = target / "docx"
    assert (copy / "scripts" / "run.py").read_text() == "print('hi')\n"
    assert (copy / "references" / "notes.md").read_text() == "notes\n"
    assert not (copy / "adaptation.md").exists()
    assert not (copy / ".upstream").exists()
    assert not (copy / ".generated").exists()


def test_install_records_an_ownership_marker(tmp_path: Path) -> None:
    """Each copy records the skill folder it came from, readable via `installed_from`."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    marker = json.loads((target / "docx" / MARKER_NAME).read_text())
    assert marker["source"] == str(documents["docx"])
    assert marker["digest"]
    assert installed_from(target / "docx") == documents["docx"]


def test_install_creates_target_dir_when_absent(tmp_path: Path) -> None:
    """The target directory is created only after selection validation succeeds."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "nested" / "agent_skills"

    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert target.is_dir()
    assert (target / "docx" / "SKILL.md").is_file()


def test_install_is_idempotent(tmp_path: Path) -> None:
    """Re-running an identical selection leaves up-to-date copies untouched."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})
    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "unchanged")
    ]


def test_install_refreshes_a_copy_whose_source_changed(tmp_path: Path) -> None:
    """An edited skill is re-copied, and files it no longer ships are dropped."""
    skill = tmp_path / "skills" / "documents" / "docx"
    write_text(skill / "SKILL.md", "# v1\n")
    write_text(skill / "scripts" / "gone.py", "old\n")
    target = tmp_path / "agent_skills"
    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    write_text(skill / "SKILL.md", "# v2\n")
    (skill / "scripts" / "gone.py").unlink()
    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [("docx", "update")]
    assert (target / "docx" / "SKILL.md").read_text() == "# v2\n"
    assert not (target / "docx" / "scripts" / "gone.py").exists()


def test_install_reports_stale_copy_under_dry_run(tmp_path: Path) -> None:
    """Dry-run is how staleness surfaces: `update` without changing the copy."""
    skill = tmp_path / "skills" / "documents" / "docx"
    write_text(skill / "SKILL.md", "# v1\n")
    target = tmp_path / "agent_skills"
    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})
    write_text(skill / "SKILL.md", "# v2\n")

    actions = run_install(
        tmp_path, target_dirs=[target], skill_sets={"documents"}, dry_run=True
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "update")]
    assert (target / "docx" / "SKILL.md").read_text() == "# v1\n"


def test_install_replaces_a_legacy_symlink_with_a_copy(tmp_path: Path) -> None:
    """A link left by the symlink-based releases is migrated in place."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "docx").symlink_to(documents["docx"])

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [action.action for action in actions] == ["update"]
    assert not (target / "docx").is_symlink()
    assert (target / "docx" / "SKILL.md").read_text() == "# demo\n"


def test_install_skips_conflicting_directory_it_does_not_own(tmp_path: Path) -> None:
    """A hand-made directory with no marker is reported but never clobbered."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    write_text(target / "docx" / "keep.txt", "precious")

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [action.action for action in actions] == ["conflict"]
    assert (target / "docx" / "keep.txt").read_text() == "precious"
    assert not (target / "docx" / "SKILL.md").exists()


def test_install_treats_a_damaged_marker_as_a_conflict(tmp_path: Path) -> None:
    """An unparseable marker means 'not ours': the directory is left alone."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    write_text(target / "docx" / MARKER_NAME, "{not json")
    write_text(target / "docx" / "SKILL.md", "someone else's\n")

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [action.action for action in actions] == ["conflict"]
    assert (target / "docx" / "SKILL.md").read_text() == "someone else's\n"


def test_install_removes_unselected_copy_it_owns(tmp_path: Path) -> None:
    """Changing selection deletes a repository-owned copy outside it."""
    _seed_skill_set(tmp_path, "documents", "docx")
    _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    run_install(
        tmp_path, target_dirs=[target], skill_sets={"documents", "engineering"}
    )

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "unchanged"),
        ("code-review", "remove"),
    ]
    assert (target / "docx").is_dir()
    assert not (target / "code-review").exists()


def test_install_removes_copy_of_a_skill_deleted_from_the_repo(tmp_path: Path) -> None:
    """A copy whose source skill no longer exists is still recognized and removed."""
    _seed_skill_set(tmp_path, "documents", "docx", "retired")
    target = tmp_path / "agent_skills"
    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    (tmp_path / "skills" / "documents" / "retired" / "SKILL.md").unlink()
    (tmp_path / "skills" / "documents" / "retired").rmdir()
    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "unchanged"),
        ("retired", "remove"),
    ]
    assert not (target / "retired").exists()


def test_install_append_preserves_unselected_copies(tmp_path: Path) -> None:
    """Append mode adds selected skills without deactivating existing ones."""
    _seed_skill_set(tmp_path, "documents", "docx")
    _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    run_install(tmp_path, target_dirs=[target], skill_sets={"engineering"})

    actions = run_install(
        tmp_path,
        target_dirs=[target],
        skill_sets={"documents"},
        append=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "docx" / "SKILL.md").is_file()
    assert (target / "code-review" / "SKILL.md").is_file()


def test_install_append_preserves_legacy_category_links(tmp_path: Path) -> None:
    """Append mode leaves old category links outside its selected skills alone."""
    _seed_skill_set(tmp_path, "documents", "docx")
    _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    legacy = target / "engineering"
    legacy.symlink_to(tmp_path / "skills" / "engineering")

    actions = run_install(
        tmp_path,
        target_dirs=[target],
        skill_sets={"documents"},
        append=True,
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "docx" / "SKILL.md").is_file()
    assert legacy.is_symlink()


def test_install_migrates_legacy_category_links(tmp_path: Path) -> None:
    """A normal run replaces legacy category links with direct skill copies."""
    _seed_skill_set(tmp_path, "documents", "docx", "pdf")
    engineering = _seed_skill_set(tmp_path, "engineering", "code-review")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(tmp_path / "skills" / "documents")
    (target / "engineering").symlink_to(tmp_path / "skills" / "engineering")

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "create"),
        ("pdf", "create"),
        ("documents", "remove"),
        ("engineering", "remove"),
    ]
    assert (target / "docx" / "SKILL.md").is_file()
    assert (target / "pdf" / "SKILL.md").is_file()
    assert not (target / "documents").exists()
    assert not (target / "engineering").exists()
    assert engineering["code-review"].is_dir()  # the repo itself is untouched


def test_install_preserves_external_links_and_renamed_copies(tmp_path: Path) -> None:
    """Cleanup leaves external links and copies renamed by hand untouched."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (target / "external").symlink_to(external)
    (target / "renamed-docx").symlink_to(documents["docx"])
    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})
    (target / "docx").rename(target / "my-docx")

    actions = run_install(tmp_path, target_dirs=[target], skill_sets={"documents"})

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]
    assert (target / "external").is_symlink()
    assert (target / "renamed-docx").is_symlink()
    assert (target / "my-docx" / "SKILL.md").is_file()


def test_install_rejects_duplicate_names_before_mutating(tmp_path: Path) -> None:
    """Duplicate global names are reported before any existing entry is touched."""
    documents = _seed_skill_set(tmp_path, "documents", "shared")
    _seed_skill_set(tmp_path, "engineering", "shared")
    target = tmp_path / "agent_skills"
    target.mkdir()
    stale = target / "documents"
    stale.symlink_to(tmp_path / "skills" / "documents")

    with pytest.raises(InstallError, match="duplicate skill name"):
        run_install(
            tmp_path,
            target_dirs=[target],
            skill_sets={"documents", "engineering"},
        )

    assert stale.is_symlink()
    assert documents["shared"].is_dir()


def test_install_dry_run_makes_no_changes(tmp_path: Path) -> None:
    """Dry-run reports creation and legacy cleanup without changing the filesystem."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"
    target.mkdir()
    (target / "documents").symlink_to(tmp_path / "skills" / "documents")

    actions = run_install(
        tmp_path, target_dirs=[target], skill_sets={"documents"}, dry_run=True
    )

    assert [(action.name, action.action) for action in actions] == [
        ("docx", "create"),
        ("documents", "remove"),
    ]
    assert not (target / "docx").exists()
    assert (target / "documents").resolve() == tmp_path / "skills" / "documents"
    assert documents["docx"].is_dir()


def test_install_dry_run_does_not_create_target_dirs(tmp_path: Path) -> None:
    """Dry-run touches nothing at all, not even an absent target directory."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    run_install(tmp_path, target_dirs=[target], skill_sets={"documents"}, dry_run=True)

    assert not target.exists()


def test_install_dedupes_repeated_target_dirs(tmp_path: Path) -> None:
    """The same target listed twice is planned and applied once."""
    _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    actions = run_install(
        tmp_path, target_dirs=[target, target], skill_sets={"documents"}
    )

    assert [(action.name, action.action) for action in actions] == [("docx", "create")]


def test_install_dedupes_a_target_dir_that_links_to_another(tmp_path: Path) -> None:
    """Two spellings of one directory install once, into the first spelling."""
    _seed_skill_set(tmp_path, "documents", "docx")
    agents = tmp_path / "agents"
    agents.mkdir()
    claude = tmp_path / "claude"
    claude.symlink_to(agents)

    actions = run_install(
        tmp_path, target_dirs=[agents, claude], skill_sets={"documents"}
    )

    assert [(action.name, action.path) for action in actions] == [
        ("docx", agents / "docx")
    ]
    assert (agents / "docx" / "SKILL.md").is_file()


def test_install_rejects_empty_unknown_or_empty_category_before_mutating(
    tmp_path: Path,
) -> None:
    """Invalid selections fail before creating a target or removing anything."""
    _seed_skill_set(tmp_path, "documents", "docx")
    (tmp_path / "skills" / "empty").mkdir(parents=True)
    target = tmp_path / "agent_skills"
    target.mkdir()
    stale = target / "documents"
    stale.symlink_to(tmp_path / "skills" / "documents")

    with pytest.raises(InstallError, match="at least one --skill-set"):
        run_install(tmp_path, target_dirs=[target], skill_sets=set())
    with pytest.raises(InstallError, match="unknown skill set"):
        run_install(tmp_path, target_dirs=[target], skill_sets={"missing"})
    with pytest.raises(InstallError, match="contain no skill folders"):
        run_install(tmp_path, target_dirs=[target], skill_sets={"empty"})
    with pytest.raises(InstallError, match="at least one target directory"):
        run_install(tmp_path, target_dirs=[], skill_sets={"documents"})

    assert stale.is_symlink()


def test_install_action_is_a_dataclass_carrying_paths(tmp_path: Path) -> None:
    """Each InstallAction carries the skill source and its target copy path."""
    documents = _seed_skill_set(tmp_path, "documents", "docx")
    target = tmp_path / "agent_skills"

    [action] = run_install(
        tmp_path, target_dirs=[target], skill_sets={"documents"}, dry_run=True
    )

    assert isinstance(action, InstallAction)
    assert action.name == "docx"
    assert action.path == target / "docx"
    assert action.source == documents["docx"]
