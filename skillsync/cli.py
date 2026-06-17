"""Typer CLI entry point for skillsync."""

from pathlib import Path

import typer

from skillsync import __version__
from skillsync.commands.add import run_add
from skillsync.commands.link import default_target_dir, run_link
from skillsync.commands.regen import run_regen
from skillsync.commands.reprofile import ReprofileOutcome, run_reprofile
from skillsync.commands.status import SkillStatus, gather_status
from skillsync.config import ConfigError, load_config
from skillsync.layout import SkillLayout, read_skill
from skillsync.pipeline import SyncOutcome, run_sync
from skillsync.ports.gh import GhPort
from skillsync.ports.gh_cli import GhCli
from skillsync.ports.git import GitPort
from skillsync.ports.git_cli import GitCli
from skillsync.ports.llm import LLMPort
from skillsync.ports.llm_claude import ClaudeCli
from skillsync.stages.detect import detect
from skillsync.stages.gate import DEFAULT_MAX_FILE_BYTES
from skillsync.stages.validate import validate_skill

app = typer.Typer(help="Mirror, security-scan, and agentically adapt upstream skills.")


def make_git() -> GitPort:
    """Construct the git port the commands use.

    A dependency-injection seam: tests monkeypatch this factory to return a
    `FakeGit`, so the CLI never shells out to real git under test.
    """
    return GitCli()


def make_llm() -> LLMPort:
    """Construct the LLM port the agentic stages use (real headless `claude -p`)."""
    return ClaudeCli()


def make_gh() -> GhPort:
    """Construct the gh port the PR/issue output uses (real `git`/`gh` CLIs)."""
    return GhCli()


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
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(
        Path("."), help="Repo root containing the skills/ directory."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Skip the (online) upstream-ahead probe."
    ),
) -> None:
    """Report per skill its synced sha, upstream-ahead, drift, and link state.

    Loads `sources.yaml` for the pins, then prints one row per skill folder under
    `skills/`. The upstream-ahead column uses the real git port (offline-tolerant —
    a `?` means undetermined); pass `--offline` to skip it entirely.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    git = None if offline else make_git()
    rows = gather_status(config, root, git=git, target_dir=default_target_dir())
    _print_status(rows)


def _print_status(rows: list[SkillStatus]) -> None:
    """Print the per-skill status table, one row per skill folder."""
    if not rows:
        typer.echo("no skills found under skills/")
        return

    width = max(len(row.name) for row in rows)
    for row in rows:
        sha = row.synced_sha or "-------"
        ahead = {True: "ahead", False: "synced", None: "?"}[row.upstream_ahead]
        drift = "drift" if row.drift else "clean"
        link = "linked" if row.linked else "unlinked"
        typer.echo(
            f"{row.name.ljust(width)}  {sha}  upstream={ahead}  {drift}  {link}"
        )


@app.command(name="link")
def link_cmd(
    root: Path = typer.Option(
        Path("."), help="Repo root containing the skills/ directory."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print planned actions without changing anything."
    ),
) -> None:
    """Symlink each skill folder under `skills/` into the native skills dir.

    The target dir is `$SKILLSYNC_LINK_DIR` if set, else `~/.claude/skills`. A real
    (non-symlink) path already occupying a slot is skipped with a warning and never
    clobbered. `--dry-run` prints the plan without touching the filesystem.
    """
    actions = run_link(root, target_dir=default_target_dir(), dry_run=dry_run)
    if not actions:
        typer.echo("no skills found under skills/")
        return

    prefix = "would " if dry_run else ""
    width = max(len(a.name) for a in actions)
    for action in actions:
        if action.action == "conflict":
            typer.echo(
                f"warning: {action.name}: {action.link_path} exists and is not a "
                "symlink; skipping",
                err=True,
            )
            continue
        typer.echo(f"{action.name.ljust(width)}  {prefix}{action.action}")


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


@app.command(name="validate")
def validate_cmd(
    name: str = typer.Argument(..., help="Skill folder name under skills/."),
    root: Path = typer.Option(
        Path("."), help="Repo root containing the skills/ directory."
    ),
    byte_cap: int = typer.Option(
        DEFAULT_MAX_FILE_BYTES, "--byte-cap", help="Maximum SKILL.md size in bytes."
    ),
) -> None:
    """Validate a skill's on-disk SKILL.md, printing PASS or the errors found."""
    layout = SkillLayout.resolve(root, name)
    skill_md_text = read_skill(layout).skill_md
    if skill_md_text is None:
        typer.echo(f"{name}: no SKILL.md found at {layout.skill_md_path}", err=True)
        raise typer.Exit(code=1)

    result = validate_skill(layout, skill_md_text, byte_cap)
    if result.passed:
        typer.echo(f"{name}: PASS")
        return

    typer.echo(f"{name}: FAIL", err=True)
    for error in result.errors:
        typer.echo(f"  - {error}", err=True)
    raise typer.Exit(code=1)


@app.command(name="sync")
def sync_cmd(
    skill: str | None = typer.Option(
        None, "--skill", help="Restrict the run to this skill folder name."
    ),
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root containing skills/."),
) -> None:
    """Run the full sync pipeline and print a per-skill outcome summary table.

    Assembles the real git/LLM/gh ports (Opus, temperature 0) and runs
    detect → gate → reconcile → adapt → verify → validate → PR per changed skill.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    outcomes = run_sync(
        config, root, git=make_git(), llm=make_llm(), gh=make_gh(), only=skill
    )
    _print_outcomes(outcomes)


@app.command(name="add")
def add_cmd(
    repo: str = typer.Argument(..., help="Upstream repo, e.g. owner/repo."),
    skill_path: str = typer.Argument(..., help="Subtree path of the skill to onboard."),
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root containing skills/."),
    ref: str = typer.Option("main", "--ref", help="Upstream ref to fetch."),
) -> None:
    """Onboard a new upstream skill: draft adaptation.md, full-generate, and open a PR.

    Appends an unsynced pin to sources.yaml, mirrors upstream, runs the security
    gate, then (on pass) drafts a self-contained adaptation.md from profile.md plus
    the upstream SKILL.md, full-generates the first SKILL.md, validates it, and opens
    an `onboarding`-labelled PR. Assembles the real git/LLM/gh ports (Opus, temp 0).
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    outcome = run_add(
        config,
        root,
        repo,
        skill_path,
        git=make_git(),
        llm=make_llm(),
        gh=make_gh(),
        ref=ref,
    )
    suffix = f"  {outcome.url}" if outcome.url else ""
    typer.echo(f"{outcome.name}  {outcome.status}{suffix}")


@app.command(name="regen")
def regen_cmd(
    name: str = typer.Argument(..., help="Skill folder name under skills/."),
    force: bool = typer.Option(
        False, "--force", help="Full rewrite (regen is always a full rebuild)."
    ),
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root containing skills/."),
) -> None:
    """Regenerate one skill's SKILL.md from its on-disk upstream + adaptation, opening a PR.

    Reads the upstream mirror and adaptation.md already under skills/<name>/,
    full-generates a fresh SKILL.md, validates it, and opens a `skillsync/regen-<name>`
    PR (or files an issue on a validation failure). Never bumps the pin's synced_sha.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    outcome = run_regen(
        config, root, name, llm=make_llm(), gh=make_gh(), force=force
    )
    suffix = f"  {outcome.url}" if outcome.url else ""
    typer.echo(f"{outcome.name}  {outcome.status}{suffix}")


@app.command(name="reprofile")
def reprofile_cmd(
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root containing skills/."),
) -> None:
    """Re-bake the current profile.md into every skill's adaptation.md, one PR per skill.

    For each tracked skill, an LLM pass re-bakes profile.md into its adaptation.md,
    then SKILL.md is regenerated, validated, and shipped as a `reprofile`-labelled PR.
    A skill that fails validation is blocked (issue, no PR) without affecting others.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    outcomes = run_reprofile(config, root, llm=make_llm(), gh=make_gh())
    _print_reprofile_outcomes(outcomes)


def _print_reprofile_outcomes(outcomes: list[ReprofileOutcome]) -> None:
    """Print a name → status → url summary table for the reprofile run."""
    if not outcomes:
        typer.echo("no skills to reprofile (none configured)")
        return

    width = max(len(o.name) for o in outcomes)
    for outcome in outcomes:
        suffix = f"  {outcome.url}" if outcome.url else ""
        typer.echo(f"{outcome.name.ljust(width)}  {outcome.status}{suffix}")


def _print_outcomes(outcomes: list[SyncOutcome]) -> None:
    """Print a name → status → url summary table for the sync run."""
    if not outcomes:
        typer.echo("no skills to sync (all held, unchanged, or none configured)")
        return

    width = max(len(o.name) for o in outcomes)
    for outcome in outcomes:
        suffix = f"  {outcome.url}" if outcome.url else ""
        typer.echo(f"{outcome.name.ljust(width)}  {outcome.status}{suffix}")


if __name__ == "__main__":
    app()
