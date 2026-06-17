"""Tests for the skillsync CLI skeleton."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillsync import __version__, cli
from skillsync.cli import app
from skillsync.layout import write_text
from skillsync.testing.fakes import FakeGit

RUNNER = CliRunner()


def test_version_exits_zero_and_prints_version() -> None:
    """`skillsync version` exits 0 and prints the package version string."""
    result = RUNNER.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_status_lists_skill_folders_and_presence(tmp_path: Path) -> None:
    """`skillsync status` lists each skill folder and which files are present."""
    write_text(tmp_path / "skills" / "alpha" / "adaptation.md", "rules")
    write_text(tmp_path / "skills" / "alpha" / "SKILL.md", "skill")
    write_text(tmp_path / "skills" / "alpha" / ".generated" / "SKILL.md", "snap")
    write_text(tmp_path / "skills" / "beta" / "adaptation.md", "rules")

    result = RUNNER.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_status_reports_no_skills(tmp_path: Path) -> None:
    """`skillsync status` reports cleanly when no skill folders exist."""
    result = RUNNER.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "no skills" in result.stdout.lower()


def test_detect_prints_kind_table_with_injected_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync detect` prints a name → kind table using an injected `FakeGit`."""
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "# Demo\nfirst\n"})
    git.add_commit("sha2", {"skills/demo/SKILL.md": "# Demo\nsecond\n"})
    git.set_ref("main", "sha2")
    monkeypatch.setattr(cli, "make_git", lambda: git)

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/demo\n"
        "        synced_sha: sha1\n"
    )

    result = RUNNER.invoke(app, ["detect", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "changed" in result.stdout


def test_validate_passes_for_well_formed_skill(tmp_path: Path) -> None:
    """`skillsync validate` exits 0 and prints PASS for a loadable skill."""
    skill_md = (
        "---\nname: demo\ndescription: A demo skill.\n---\n\n# demo\nNothing to see.\n"
    )
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", skill_md)

    result = RUNNER.invoke(app, ["validate", "demo", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_validate_exits_one_for_broken_skill(tmp_path: Path) -> None:
    """`skillsync validate` exits 1 and reports the error for a broken skill."""
    # Frontmatter name does not match the folder, and a referenced file is missing.
    skill_md = (
        "---\nname: wrong\ndescription: Bad.\n---\n\n"
        "# demo\nSee [the script](scripts/missing.sh).\n"
    )
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", skill_md)

    result = RUNNER.invoke(app, ["validate", "demo", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "scripts/missing.sh" in result.output
