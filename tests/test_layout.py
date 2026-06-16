"""Tests for the skill layout path model and folder I/O helpers."""

from pathlib import Path

from skillsync.layout import (
    SkillFiles,
    SkillLayout,
    discover_skills,
    mirror_files,
    read_skill,
    read_text,
    write_text,
)


def test_layout_resolves_paths_under_skills_dir(tmp_path: Path) -> None:
    """`SkillLayout.resolve` places every path under `skills/<name>/`."""
    layout = SkillLayout.resolve(tmp_path, "engineering/to-issues")

    assert layout.name == "to-issues"
    assert layout.root == tmp_path / "skills" / "to-issues"
    assert layout.upstream_dir == layout.root / "upstream"
    assert layout.adaptation_path == layout.root / "adaptation.md"
    assert layout.skill_md_path == layout.root / "SKILL.md"
    assert layout.generated_dir == layout.root / ".generated"
    assert layout.generated_skill_md_path == layout.root / ".generated" / "SKILL.md"


def test_layout_name_override(tmp_path: Path) -> None:
    """An explicit `name` overrides the subtree's last path segment."""
    layout = SkillLayout.resolve(tmp_path, "engineering/to-issues", name="my-issues")

    assert layout.name == "my-issues"
    assert layout.root == tmp_path / "skills" / "my-issues"


def test_layout_name_ignores_trailing_slash(tmp_path: Path) -> None:
    """A trailing slash on the subtree does not produce an empty name."""
    layout = SkillLayout.resolve(tmp_path, "engineering/to-issues/")

    assert layout.name == "to-issues"


def test_read_text_returns_none_for_absent_file(tmp_path: Path) -> None:
    """`read_text` returns None when the file does not exist."""
    assert read_text(tmp_path / "absent.md") is None


def test_write_text_creates_parent_dirs(tmp_path: Path) -> None:
    """`write_text` creates intermediate directories before writing."""
    target = tmp_path / "a" / "b" / "c.md"

    write_text(target, "hello")

    assert read_text(target) == "hello"


def test_mirror_files_replaces_stale_contents(tmp_path: Path) -> None:
    """`mirror_files` drops files absent from the new snapshot."""
    dest = tmp_path / "upstream"
    mirror_files({"SKILL.md": "old", "scripts/run.sh": "echo old"}, dest)

    mirror_files({"SKILL.md": "new"}, dest)

    assert read_text(dest / "SKILL.md") == "new"
    assert read_text(dest / "scripts" / "run.sh") is None
    assert not (dest / "scripts").exists()


def test_read_skill_returns_none_for_absent_files(tmp_path: Path) -> None:
    """`read_skill` returns None for each file that is not present."""
    layout = SkillLayout.resolve(tmp_path, "demo")

    files = read_skill(layout)

    assert files == SkillFiles(adaptation=None, skill_md=None, generated_skill_md=None)


def test_read_skill_reads_present_files(tmp_path: Path) -> None:
    """`read_skill` reads adaptation, SKILL.md, and the generated snapshot."""
    layout = SkillLayout.resolve(tmp_path, "demo")
    write_text(layout.adaptation_path, "rules")
    write_text(layout.skill_md_path, "skill")
    write_text(layout.generated_skill_md_path, "snapshot")

    files = read_skill(layout)

    assert files == SkillFiles(
        adaptation="rules", skill_md="skill", generated_skill_md="snapshot"
    )


def test_discover_skills_lists_folders_sorted(tmp_path: Path) -> None:
    """`discover_skills` returns a layout per folder under `skills/`, sorted."""
    write_text(tmp_path / "skills" / "beta" / "SKILL.md", "b")
    write_text(tmp_path / "skills" / "alpha" / "adaptation.md", "a")
    (tmp_path / "skills" / "alpha" / "upstream").mkdir(parents=True)

    layouts = discover_skills(tmp_path)

    assert [layout.name for layout in layouts] == ["alpha", "beta"]


def test_discover_skills_empty_when_no_skills_dir(tmp_path: Path) -> None:
    """`discover_skills` returns an empty list when `skills/` is absent."""
    assert discover_skills(tmp_path) == []
