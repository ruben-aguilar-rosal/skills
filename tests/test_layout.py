"""Tests for the skill layout path model and folder I/O helpers."""

from pathlib import Path

from skillsync.config import Config, SkillPin, Source
from skillsync.layout import (
    SkillFiles,
    SkillLayout,
    discover_skills,
    mirror_files,
    pin_index,
    read_skill,
    read_text,
    read_tree,
    write_aux_files,
    write_file,
    write_text,
)

# A 2-byte sequence that is not valid UTF-8 — stands in for a font/image/archive blob.
_BINARY_BLOB = b"\x89\x91"


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


def test_write_file_writes_bytes_verbatim(tmp_path: Path) -> None:
    """`write_file` writes raw bytes without decoding, creating parent dirs."""
    target = tmp_path / "fonts" / "x.ttf"

    write_file(target, _BINARY_BLOB)

    assert target.read_bytes() == _BINARY_BLOB


def test_mirror_files_handles_binary_content(tmp_path: Path) -> None:
    """`mirror_files` writes binary blobs verbatim alongside text files."""
    dest = tmp_path / "upstream"

    mirror_files({"SKILL.md": "# demo\n", "fonts/x.ttf": _BINARY_BLOB}, dest)

    assert read_text(dest / "SKILL.md") == "# demo\n"
    assert (dest / "fonts" / "x.ttf").read_bytes() == _BINARY_BLOB


def test_write_aux_files_handles_binary_content(tmp_path: Path) -> None:
    """A binary aux asset (e.g. a font) lands beside SKILL.md byte-for-byte."""
    layout = SkillLayout.resolve(tmp_path, "demo")

    write_aux_files(layout, {"SKILL.md": "# demo\n", "fonts/x.ttf": _BINARY_BLOB})

    assert (layout.root / "fonts" / "x.ttf").read_bytes() == _BINARY_BLOB


def test_read_tree_round_trips_binary(tmp_path: Path) -> None:
    """`read_tree` reads binary files back as bytes and text as str."""
    dest = tmp_path / "upstream"
    mirror_files({"SKILL.md": "# demo\n", "fonts/x.ttf": _BINARY_BLOB}, dest)

    tree = read_tree(dest)

    assert tree["SKILL.md"] == "# demo\n"
    assert tree["fonts/x.ttf"] == _BINARY_BLOB


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


def test_discover_skills_lists_folders_with_skill_md_sorted(tmp_path: Path) -> None:
    """`discover_skills` returns a layout per folder that has a SKILL.md, sorted."""
    write_text(tmp_path / "skills" / "beta" / "SKILL.md", "b")
    write_text(tmp_path / "skills" / "alpha" / "SKILL.md", "a")
    # A folder without a SKILL.md is not a skill, even with other files present.
    write_text(tmp_path / "skills" / "notaskill" / "adaptation.md", "x")

    layouts = discover_skills(tmp_path)

    assert [layout.name for layout in layouts] == ["alpha", "beta"]


def test_discover_skills_recurses_into_category_subfolders(tmp_path: Path) -> None:
    """A skill nested under a category dir (skills/ui/taste/<name>) is discovered."""
    write_text(tmp_path / "skills" / "ui" / "taste" / "taste-skill" / "SKILL.md", "t")
    write_text(tmp_path / "skills" / "meta" / "vendor" / "SKILL.md", "v")

    layouts = discover_skills(tmp_path)

    by_name = {layout.name: layout for layout in layouts}
    assert set(by_name) == {"taste-skill", "vendor"}
    assert by_name["taste-skill"].root == (
        tmp_path / "skills" / "ui" / "taste" / "taste-skill"
    )


def test_discover_skills_ignores_internal_mirror_and_snapshot(tmp_path: Path) -> None:
    """A SKILL.md inside .upstream/.generated does not register as its own skill."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "real")
    write_text(tmp_path / "skills" / "demo" / ".upstream" / "SKILL.md", "mirror")
    write_text(tmp_path / "skills" / "demo" / ".generated" / "SKILL.md", "snapshot")

    layouts = discover_skills(tmp_path)

    assert [layout.name for layout in layouts] == ["demo"]


def test_discover_skills_empty_when_no_skills_dir(tmp_path: Path) -> None:
    """`discover_skills` returns an empty list when `skills/` is absent."""
    assert discover_skills(tmp_path) == []


def test_layout_resolve_custom_dest(tmp_path: Path) -> None:
    """An explicit `dest` places the skill folder under that parent dir."""
    layout = SkillLayout.resolve(tmp_path, "a/to-issues", dest="skills/aily")

    assert layout.root == tmp_path / "skills" / "aily" / "to-issues"
    assert layout.skill_md_path == layout.root / "SKILL.md"


def test_pin_index_maps_resolved_folder_to_source_and_pin(tmp_path: Path) -> None:
    """`pin_index` keys each pinned skill by its resolved folder path (dest-aware)."""
    one = SkillPin(path="a/one", synced_sha="x")
    two = SkillPin(path="a/two", synced_sha="y", dest="skills/aws")  # per-pin override
    config = Config(
        sources=[
            Source(
                repo="owner/repo", ref="main", dest="skills/aily", skills=[one, two]
            )
        ]
    )

    index = pin_index(config, tmp_path)

    key_one = (tmp_path / "skills" / "aily" / "one").resolve()  # source dest
    key_two = (tmp_path / "skills" / "aws" / "two").resolve()  # pin dest wins
    assert index[key_one][1] is one
    assert index[key_two][1] is two
    assert index[key_one][0].repo == "owner/repo"


def test_pin_index_is_empty_without_config(tmp_path: Path) -> None:
    """`pin_index(None, ...)` is empty, so every discovered skill reads as local."""
    assert pin_index(None, tmp_path) == {}
