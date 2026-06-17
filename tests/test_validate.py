"""Tests for the deterministic VALIDATE stage.

Each case builds a `SkillLayout` over a `tmp_path` skill folder, feeds
`validate_skill` the SKILL.md text, and asserts the `ValidationResult`: whether
validation passes and which errors surface. Validate is the last gate before a
PR — it guarantees the skill is loadable. No network, no LLM.
"""

from pathlib import Path

from skillsync.layout import SkillLayout, write_text
from skillsync.stages.validate import ValidationResult, validate_skill

BYTE_CAP = 64 * 1024


def _layout(tmp_path: Path, name: str = "demo") -> SkillLayout:
    """Resolve a layout for a skill named `name` under `tmp_path/skills/`."""
    return SkillLayout.resolve(tmp_path, name)


def _skill_md(name: str = "demo", description: str = "A demo skill.", body: str = "") -> str:
    """Compose a SKILL.md with valid frontmatter and an optional body."""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n{body}"


def test_well_formed_skill_passes(tmp_path: Path) -> None:
    """A skill whose frontmatter, name, size, and references are all good passes."""
    layout = _layout(tmp_path)
    write_text(layout.root / "scripts" / "run.sh", "echo hi\n")
    text = _skill_md(body="\nSee [the script](scripts/run.sh) for details.\n")
    write_text(layout.skill_md_path, text)

    result = validate_skill(layout, text, BYTE_CAP)

    assert isinstance(result, ValidationResult)
    assert result.passed is True
    assert result.errors == []


def test_missing_description_fails(tmp_path: Path) -> None:
    """Frontmatter without a non-empty `description` fails validation."""
    layout = _layout(tmp_path)
    text = "---\nname: demo\ndescription:\n---\n\n# demo\n"

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is False
    assert any("description" in err for err in result.errors)


def test_no_frontmatter_block_fails(tmp_path: Path) -> None:
    """A SKILL.md with no YAML frontmatter at all fails validation."""
    layout = _layout(tmp_path)
    text = "# demo\nno frontmatter here\n"

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is False
    assert any("frontmatter" in err.lower() for err in result.errors)


def test_name_dir_mismatch_fails(tmp_path: Path) -> None:
    """A frontmatter `name` that differs from the skill folder name fails."""
    layout = _layout(tmp_path, name="demo")
    text = _skill_md(name="something-else")

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is False
    assert any("name" in err and "demo" in err for err in result.errors)


def test_broken_relative_reference_fails(tmp_path: Path) -> None:
    """A body link to a file that does not exist under the skill folder fails."""
    layout = _layout(tmp_path)
    text = _skill_md(body="\nSee [the script](scripts/missing.sh).\n")

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is False
    assert any("scripts/missing.sh" in err for err in result.errors)


def test_oversize_fails(tmp_path: Path) -> None:
    """A SKILL.md larger than the byte cap fails validation."""
    layout = _layout(tmp_path)
    text = _skill_md(body="\n" + "x" * 500 + "\n")

    result = validate_skill(layout, text, byte_cap=50)

    assert result.passed is False
    assert any("byte" in err.lower() or "size" in err.lower() for err in result.errors)


def test_external_urls_and_anchors_are_not_checked(tmp_path: Path) -> None:
    """Absolute URLs and in-page anchors are not treated as relative references."""
    layout = _layout(tmp_path)
    text = _skill_md(
        body=(
            "\nSee [docs](https://example.com/x) and [top](#heading) and "
            "[mail](mailto:a@b.com).\n"
        )
    )

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is True
    assert result.errors == []


def test_bare_script_reference_is_checked(tmp_path: Path) -> None:
    """An inline-code path like `scripts/x.sh` must exist under the skill folder."""
    layout = _layout(tmp_path)
    text = _skill_md(body="\nRun the helper at `scripts/helper.sh` first.\n")

    result = validate_skill(layout, text, BYTE_CAP)

    assert result.passed is False
    assert any("scripts/helper.sh" in err for err in result.errors)
