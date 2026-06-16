"""Typer CLI entry point for skillsync."""

import typer

from skillsync import __version__

app = typer.Typer(help="Mirror, security-scan, and agentically adapt upstream skills.")


@app.callback()
def main() -> None:
    """skillsync command group."""


@app.command()
def version() -> None:
    """Print the installed skillsync version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
