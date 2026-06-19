"""Typer CLI entry point for skillsync."""

import os
import shlex
from pathlib import Path

import typer

from skillsync import __version__
from skillsync.commands.add import run_add
from skillsync.commands.discovery import DiscoveryNotice, surface_discoveries
from skillsync.commands.ignore import IgnoreError, run_ignore
from skillsync.commands.link import default_target_dir, run_link
from skillsync.commands.regen import run_regen
from skillsync.commands.reprofile import ReprofileOutcome, run_reprofile
from skillsync.commands.status import SkillStatus, gather_status
from skillsync.config import ConfigError, load_config
from skillsync.layout import SkillLayout, read_skill
from skillsync.pipeline import SyncOptions, SyncOutcome, run_sync
from skillsync.ports.gh import GhPort
from skillsync.ports.gh_cli import GhCli
from skillsync.ports.git import GitPort
from skillsync.ports.git_cli import GitCli
from skillsync.ports.llm import LLMPort
from skillsync.ports.llm_claude import ClaudeCli
from skillsync.stages.detect import detect
from skillsync.stages.discover import discover
from skillsync.stages.gate import DEFAULT_MAX_FILE_BYTES
from skillsync.stages.validate import validate_skill

app = typer.Typer(help="Mirror, security-scan, and agentically adapt upstream skills.")


def make_git() -> GitPort:
    """Construct the git port the commands use.

    A dependency-injection seam: tests monkeypatch this factory to return a
    `FakeGit`, so the CLI never shells out to real git under test.
    """
    return GitCli()


# The prefix that runs `claude` through an interactive zsh, so a `claude` shell
# function (and the env it sets up) is in scope. The prompt/flags skillsync appends
# land in `$@`; the trailing `_` is the placeholder for `$0`. The prompt stays a
# discrete argv element — no shell interpolation, no injection.
_ZSH_CLAUDE_COMMAND = ["zsh", "-ic", 'claude "$@"', "_"]


def resolve_claude_command(env: "os._Environ[str] | dict[str, str]") -> list[str] | None:
    """Resolve the `claude` invocation prefix from the environment.

    Precedence:
    1. `SKILLSYNC_CLAUDE_CMD` — an explicit, shell-split command prefix (full control).
    2. `SKILLSYNC_CLAUDE_VIA_ZSH` truthy — the canned `zsh -ic 'claude "$@"' _`
       prefix, the friendly shorthand for "my `claude` is a zsh function".
    3. otherwise `None` — `ClaudeCli` falls back to a bare `claude` on PATH.
    """
    raw = env.get("SKILLSYNC_CLAUDE_CMD")
    if raw:
        return shlex.split(raw)
    if env.get("SKILLSYNC_CLAUDE_VIA_ZSH", "").strip().lower() in {"1", "true", "yes"}:
        return list(_ZSH_CLAUDE_COMMAND)
    return None


def make_llm() -> LLMPort:
    """Construct the LLM port the agentic stages use (real headless `claude -p`).

    By default it invokes a bare `claude` on PATH. When `claude` is a shell function
    (so it needs the shell's env set up first), either set `SKILLSYNC_CLAUDE_VIA_ZSH=1`
    for the canned `zsh -ic 'claude "$@"' _` prefix, or set `SKILLSYNC_CLAUDE_CMD` to a
    custom shell-split prefix. skillsync appends `-p <prompt> --output-format json
    --model …` to whichever it resolves.
    """
    return ClaudeCli(command=resolve_claude_command(os.environ))


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
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(
        Path("."), help="Repo root containing the skills/ directory."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print planned actions without changing anything."
    ),
) -> None:
    """Symlink each configured skill folder into the native skills dir.

    Skills are resolved under their configured `dest` dirs from sources.yaml (when
    present); without a config it falls back to scanning the default `skills/` dir.
    The target dir is `$SKILLSYNC_LINK_DIR` if set, else `~/.claude/skills`. A real
    (non-symlink) path already occupying a slot is skipped with a warning and never
    clobbered. `--dry-run` prints the plan without touching the filesystem.
    """
    config = load_config(config_path) if config_path.exists() else None
    actions = run_link(
        root, target_dir=default_target_dir(), config=config, dry_run=dry_run
    )
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
    no_pr: bool = typer.Option(
        False,
        "--no-pr",
        help="Adapt and write artifacts to the working tree, but don't open a PR.",
    ),
    skip_advisory: bool = typer.Option(
        False, "--skip-advisory", help="Skip the advisory LLM scan (saves quota)."
    ),
    skip_reconcile: bool = typer.Option(
        False,
        "--skip-reconcile",
        help="Skip hand-edit drift fold-back and preservation verify.",
    ),
    skip_validate: bool = typer.Option(
        False,
        "--skip-validate",
        help="Skip the blocking validation (write even a malformed SKILL.md).",
    ),
) -> None:
    """Run the full sync pipeline and print a per-skill outcome summary table.

    Assembles the real git/LLM/gh ports (Opus, temperature 0) and runs
    detect → gate → reconcile → adapt → verify → validate → PR per changed skill.

    The stage toggles let you sync skills locally and play with them before any PR:
    `--no-pr` writes the adapted artifacts to the working tree (and bumps the pin)
    without opening a PR, while `--skip-advisory` / `--skip-reconcile` /
    `--skip-validate` turn off individual optional stages. The deterministic security
    gate and the adapt step always run.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    options = SyncOptions(
        open_pr=not no_pr,
        run_advisory=not skip_advisory,
        run_reconcile=not skip_reconcile,
        run_validate=not skip_validate,
    )
    git = make_git()
    gh = make_gh()
    outcomes = run_sync(
        config, root, git=git, llm=make_llm(), gh=gh, only=skill, options=options
    )
    _print_outcomes(outcomes)

    # Surface watched-folder discoveries as awareness issues. Skipped on a local
    # (`--no-pr`) run — which deliberately opens no GitHub artifacts — and when
    # `--skill` narrows the run to a single, already-tracked skill.
    if not no_pr and skill is None:
        notices = surface_discoveries(config, root, git=git, gh=gh)
        _print_discoveries(notices)


def _print_discoveries(notices: list[DiscoveryNotice]) -> None:
    """Print the watched-folder discovery summary, one line per surfaced skill."""
    if not notices:
        return
    typer.echo(f"\n{len(notices)} watched-folder discovery(ies):")
    width = max(len(n.skill_path) for n in notices)
    for notice in notices:
        typer.echo(f"  {notice.kind.ljust(7)} {notice.skill_path.ljust(width)}  {notice.url}")


@app.command(name="discover")
def discover_cmd(
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root (passed to the git port)."),
    open_issues: bool = typer.Option(
        False,
        "--open-issues",
        help="Also file an awareness issue per finding (like sync does).",
    ),
) -> None:
    """Preview new/removed skills in watched folders; opens nothing by default.

    Runs the deterministic discovery stage and prints each new (appeared upstream,
    not yet tracked) or removed (pinned but gone upstream) skill. Read-only unless
    `--open-issues` is passed, which files the same idempotent awareness issues a
    full `sync` would — handy for surfacing them without running the whole pipeline.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    for warning in config.warnings:
        typer.echo(f"warning: {warning}", err=True)

    git = make_git()
    if open_issues:
        _print_discoveries(surface_discoveries(config, root, git=git, gh=make_gh()))
        return

    findings = discover(config, git, root)
    if not findings:
        typer.echo("no watched-folder discoveries (nothing new or removed upstream)")
        return

    typer.echo(f"{len(findings)} watched-folder discovery(ies):")
    width = max(len(f.skill_path) for f in findings)
    for finding in findings:
        typer.echo(f"  {finding.kind.ljust(7)} {finding.skill_path.ljust(width)}  ({finding.repo})")
    typer.echo("\nadopt: skillsync add <repo> <path>   reject: skillsync ignore <repo> <path>")


@app.command(name="add")
def add_cmd(
    repo: str = typer.Argument(..., help="Upstream repo, e.g. owner/repo."),
    skill_path: str = typer.Argument(..., help="Subtree path of the skill to onboard."),
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
    root: Path = typer.Option(Path("."), help="Repo root containing skills/."),
    ref: str = typer.Option("main", "--ref", help="Upstream ref to fetch."),
    adapt: bool = typer.Option(
        False,
        "--adapt",
        help="Draft an adaptation.md and full-generate (LLM); default just vendors.",
    ),
    dest: str | None = typer.Option(
        None, "--dest", help="Parent dir to store the skill under (default skills/)."
    ),
    no_pr: bool = typer.Option(
        False,
        "--no-pr",
        help="Write the skill to the working tree without opening a PR.",
    ),
) -> None:
    """Onboard a new upstream skill and open a PR.

    By default it **vendors** the upstream skill verbatim (no LLM): appends an
    unsynced pin to sources.yaml, mirrors upstream, runs the security gate, copies
    SKILL.md as-is, validates, and opens a `vendored` PR. Adaptation is opt-in —
    pass `--adapt` to instead draft a self-contained adaptation.md from profile.md
    and full-generate the first SKILL.md (an `onboarding` PR). `--dest` overrides
    where the skill folder is stored, to group skills from different repos. `--no-pr`
    writes the skill to the working tree and stops, opening no PR.
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
        adapt=adapt,
        dest=dest,
        open_pr=not no_pr,
    )
    suffix = f"  {outcome.url}" if outcome.url else ""
    typer.echo(f"{outcome.name}  {outcome.status}{suffix}")


@app.command(name="ignore")
def ignore_cmd(
    repo: str = typer.Argument(..., help="Upstream repo, e.g. owner/repo."),
    skill_path: str = typer.Argument(..., help="Discovered skill path to stop surfacing."),
    config_path: Path = typer.Option(
        Path("sources.yaml"), "--config", help="Path to sources.yaml."
    ),
) -> None:
    """Stop a discovered upstream skill from being surfaced by future syncs.

    Appends `skill_path` to the matching source's `ignore` list in sources.yaml.
    This is the rejection counterpart to `skillsync add` for watched-folder
    discoveries — a durable "no" that survives across sync runs.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        run_ignore(config, config_path, repo, skill_path)
    except IgnoreError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"ignoring {skill_path} from {repo}")


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
