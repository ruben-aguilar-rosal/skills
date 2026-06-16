"""Tests for the skillsync CLI skeleton."""

from typer.testing import CliRunner

from skillsync import __version__
from skillsync.cli import app

RUNNER = CliRunner()


def test_version_exits_zero_and_prints_version() -> None:
    """`skillsync version` exits 0 and prints the package version string."""
    result = RUNNER.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout
