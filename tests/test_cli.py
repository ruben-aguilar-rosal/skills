"""Tests for the skillsync CLI skeleton."""

from pathlib import Path

from typer.testing import CliRunner

from skillsync import __version__
from skillsync.cli import app
from skillsync.layout import write_text

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
