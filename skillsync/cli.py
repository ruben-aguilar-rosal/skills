"""Typer CLI entry point for skillsync."""

from pathlib import Path

import typer

from skillsync import __version__
from skillsync.config import ConfigError, load_config
from skillsync.layout import discover_skills, read_skill
from skillsync.ports.git import GitPort
from skillsync.ports.git_cli import GitCli
from skillsync.stages.detect import detect

app = typer.Typer(help="Mirror, security-scan, and agentically adapt upstream skills.")


def make_git() -> GitPort:
    """Construct the git port the commands use.

    A dependency-injection seam: tests monkeypatch this factory to return a
    `FakeGit`, so the CLI never shells out to real git under test.
    """
    return GitCli()


@app.callback()
def main() -> None:
    """skillsync command group."""


@app.command()
def version() -> None:
    """Print the installed skillsync version."""
    typer.echo(__version__)


@app.command()
def config_check() -> None:
    """Load sources.yaml from the repo root and report source/skill counts."""
    try:
        config = load_config(Path("sources.yaml"))
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    skill_count = sum(len(source.skills) for source in config.sources)
    typer.echo(f"{len(config.sources)} source(s), {skill_count} skill(s)")


@app.command()
def status(
    root: Path = typer.Option(
        Path("."), help="Repo root containing the skills/ directory."
    ),
) -> None:
    """List skill folders under `skills/` and which files each has present."""
    layouts = discover_skills(root)
    if not layouts:
        typer.echo("no skills found under skills/")
        return

    for layout in layouts:
        files = read_skill(layout)
        marks = (
            f"adaptation={'✓' if files.adaptation is not None else '✗'} "
            f"SKILL={'✓' if files.skill_md is not None else '✗'} "
            f"generated={'✓' if files.generated_skill_md is not None else '✗'}"
        )
        typer.echo(f"{layout.name}: {marks}")


@app.command(name="detect")
def detect_cmd(
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root (passed to the git port)."),
) -> None:
    """Detect upstream changes per skill and print a name → kind table."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    changes = detect(config, make_git(), root)
    if not changes:
        typer.echo("no skills to detect (all held or none configured)")
        return

    width = max(len(change.name) for change in changes)
    for change in changes:
        flag = "  ⚠ history rewritten" if change.rewritten_history else ""
        typer.echo(f"{change.name.ljust(width)}  {change.kind}{flag}")


if __name__ == "__main__":
    app()
