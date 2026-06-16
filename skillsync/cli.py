"""Typer CLI entry point for skillsync."""

from pathlib import Path

import typer

from skillsync import __version__
from skillsync.config import ConfigError, load_config
from skillsync.layout import discover_skills, read_skill

app = typer.Typer(help="Mirror, security-scan, and agentically adapt upstream skills.")


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


if __name__ == "__main__":
    app()
