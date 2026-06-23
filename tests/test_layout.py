"""Tests for the skill layout path model and folder I/O helpers."""

from pathlib import Path

from skillsync.config import Config, SkillPin, Source
from skillsync.layout import (
    SkillFiles,
    SkillLayout,
    discover_skills,
    layouts_from_config,
    mirror_files,
    read_skill,
    read_text,
    write_aux_files,
    write_text,
)


def test_layout_resolves_paths_under_skills_dir(tmp_path: Path) -> None:
    """`SkillLayout.resolve` places every path under `skills/<name>/`."""
    layout = SkillLayout.resolve(tmp_path, "engineering/to-issues")

    assert layout.name == "to-issues"
    assert layout.root == tmp_path / "skills" / "to-issues"
    assert layout.upstream_dir == layout.root / ".upstream"
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


def test_write_aux_files_copies_non_skill_md_into_root(tmp_path: Path) -> None:
    """`write_aux_files` lays the skill's ship-along files beside SKILL.md, not the .md."""
    layout = SkillLayout.resolve(tmp_path, "demo")
    new_files = {
        "SKILL.md": "# demo\n",
        "scripts/run.py": "print('hi')\n",
        "references/guide.md": "guide\n",
    }

    write_aux_files(layout, new_files)

    # The scripts/references the skill ships land in the skill folder root...
    assert read_text(layout.root / "scripts" / "run.py") == "print('hi')\n"
    assert read_text(layout.root / "references" / "guide.md") == "guide\n"
    # ...but SKILL.md is NOT written here (it's owned by the adapt/vendor step).
    assert read_text(layout.root / "SKILL.md") is None


def test_write_aux_files_prunes_stale_aux(tmp_path: Path) -> None:
    """A second call drops aux files no longer present upstream."""
    layout = SkillLayout.resolve(tmp_path, "demo")
    write_aux_files(layout, {"SKILL.md": "x", "scripts/old.py": "old"})

    write_aux_files(layout, {"SKILL.md": "x", "scripts/new.py": "new"})

    assert read_text(layout.root / "scripts" / "new.py") == "new"
    assert read_text(layout.root / "scripts" / "old.py") is None


def test_write_aux_files_preserves_committed_skill_files(tmp_path: Path) -> None:
    """Pruning aux files never touches SKILL.md, adaptation.md, or .generated/."""
    layout = SkillLayout.resolve(tmp_path, "demo")
    write_text(layout.skill_md_path, "committed")
    write_text(layout.adaptation_path, "rules")
    write_text(layout.generated_skill_md_path, "snap")

    write_aux_files(layout, {"SKILL.md": "x", "scripts/run.py": "code"})

    assert read_text(layout.skill_md_path) == "committed"
    assert read_text(layout.adaptation_path) == "rules"
    assert read_text(layout.generated_skill_md_path) == "snap"
    assert read_text(layout.root / "scripts" / "run.py") == "code"


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


def test_layout_resolve_custom_dest(tmp_path: Path) -> None:
    """An explicit `dest` places the skill folder under that parent dir."""
    layout = SkillLayout.resolve(tmp_path, "a/to-issues", dest="skills/aily")

    assert layout.root == tmp_path / "skills" / "aily" / "to-issues"
    assert layout.skill_md_path == layout.root / "SKILL.md"


def test_layouts_from_config_uses_dest_precedence(tmp_path: Path) -> None:
    """`layouts_from_config` resolves each pin under its effective dest."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                dest="skills/aily",
                skills=[
                    SkillPin(path="a/one", synced_sha="x"),
                    SkillPin(path="a/two", synced_sha="y", dest="skills/aws"),
                ],
            )
        ]
    )

    layouts = layouts_from_config(config, tmp_path)

    assert layouts[0].root == tmp_path / "skills" / "aily" / "one"
    assert layouts[1].root == tmp_path / "skills" / "aws" / "two"
