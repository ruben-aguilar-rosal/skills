"""End-to-end SYNC pipeline — wires the deterministic and agentic stages together.

`run_sync` orchestrates, per changed skill, the full pipeline described in PLAN.md:

    detect → deterministic gate → advisory scan → reconcile drift → adapt (patch)
           → verify preservation → deterministic validate → PR

with two non-PR exits that protect the repo:

- **quarantine** — the deterministic security gate fails. The skill is NOT adapted,
  an issue is opened with the suspicious diff plus the extracted commands/URLs, and
  the pin stays at its OLD sha.
- **invalid** — the adapted `SKILL.md` fails deterministic validation. No PR is
  opened, an issue is filed, nothing is written, and the pin stays put.

The load-bearing invariant: a pin's `synced_sha` is bumped ONLY on a successful PR.
The mirror, `SKILL.md`, `.generated` snapshot, enriched `adaptation.md`, and the
sha bump are all written together, just before the PR is published, so they land in
the same commit. Everything that touches git/claude/gh goes through an injected
port, so the whole pipeline runs against fakes in tests.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from skillsync.config import Config, SkillPin, save_config, skill_dest
from skillsync.layout import (
    SkillLayout,
    mirror_files,
    read_skill,
    write_text,
)
from skillsync.pr import build_pr, publish_pr
from skillsync.ports.gh import GhPort
from skillsync.ports.git import GitPort
from skillsync.ports.llm import LLMPort
from skillsync.stages.adapt import AdaptResult, adapt
from skillsync.stages.detect import ChangeSet, detect
from skillsync.stages.gate import DEFAULT_MAX_FILE_BYTES, GateResult, run_gate
from skillsync.stages.llm_scan import AdvisoryVerdict, advisory_scan
from skillsync.stages.reconcile import detect_drift, fold_back, verify_preserved
from skillsync.stages.validate import validate_skill

# Default model for every agentic step (PLAN.md: Opus for all of them).
_DEFAULT_MODEL = "opus"

# The flag raised when post-fold-back verification cannot confirm a hand-edit.
_NOT_PRESERVED_FLAG = "⚠ hand-edit may not be preserved"

# Placeholder advisory verdict used when `--skip-advisory` turns the scan off but a
# PR is still opened: the body must be honest that no scan ran rather than implying a
# clean one did.
_SKIPPED_ADVISORY = AdvisoryVerdict(
    risk="low",
    rationale="advisory scan skipped (--skip-advisory); not run for this skill",
    findings=[],
)

Status = Literal["pr", "local", "quarantined", "invalid", "skipped"]


@dataclass(frozen=True)
class SyncOptions:
    """Per-run stage toggles for `run_sync` (the deterministic gate always runs).

    `open_pr` is the only switch that touches git/GitHub: when False (the CLI's
    `--no-pr`) the pipeline still adapts, writes the artifacts to the working tree,
    and bumps `synced_sha`, but stops before the branch/commit/PR so the generated
    files can be inspected and linked locally. The other three turn off optional
    stages — the advisory LLM scan, the drift reconcile + preservation verify, and
    the blocking validation — for faster, quota-light local iteration. `adapt` and
    the deterministic security gate cannot be skipped.
    """

    open_pr: bool = True
    run_advisory: bool = True
    run_reconcile: bool = True
    run_validate: bool = True


@dataclass
class SyncOutcome:
    """The result of running the pipeline over one skill.

    `status` is the terminal outcome; `url` is the PR or issue URL when one was
    opened (None for a skip); `detail` is a short human-readable summary.
    """

    name: str
    skill_path: str
    status: Status
    url: str | None = None
    detail: str = ""
    flags: list[str] = field(default_factory=list)


def run_sync(
    config: Config,
    root: Path,
    *,
    git: GitPort,
    llm: LLMPort,
    gh: GhPort,
    only: str | None = None,
    model: str = _DEFAULT_MODEL,
    options: SyncOptions | None = None,
) -> list[SyncOutcome]:
    """Run the full sync pipeline over every changed, non-held skill in `config`.

    Detects upstream changes, then for each changed skill runs the gate, advisory
    scan, drift reconcile, adapt, preservation verify, and validate stages, opening
    a PR on success or an issue on quarantine/validation failure. `only` restricts
    the run to the skill of that folder name. `options` (see `SyncOptions`) toggles
    individual stages and the PR step — e.g. `open_pr=False` for a local run that
    writes the adapted artifacts to the working tree without opening a PR. The
    matching pins in `config` are mutated — and the config saved to
    `root/sources.yaml` — whenever the artifacts are written (a PR or a local run).

    Returns one `SyncOutcome` per processed skill (a skill filtered out by `only`
    produces no outcome).
    """
    options = options or SyncOptions()
    pins = _pins_by_path(config)
    outcomes: list[SyncOutcome] = []
    for changeset in detect(config, git, root):
        if only is not None and changeset.name != only:
            continue
        source_repo, source_ref, pin, dest = pins[changeset.skill_path]
        outcomes.append(
            _sync_one(
                config,
                root,
                changeset,
                source_repo,
                source_ref,
                pin,
                dest,
                git=git,
                llm=llm,
                gh=gh,
                model=model,
                options=options,
            )
        )
    return outcomes


def _pins_by_path(config: Config) -> dict[str, tuple[str, str, SkillPin, str]]:
    """Index every pin by subtree path → (repo, ref, pin, dest) for detect matchback."""
    index: dict[str, tuple[str, str, SkillPin, str]] = {}
    for source in config.sources:
        for pin in source.skills:
            index[pin.path] = (source.repo, source.ref, pin, skill_dest(source, pin))
    return index


def _sync_one(
    config: Config,
    root: Path,
    changeset: ChangeSet,
    repo: str,
    ref: str,
    pin: SkillPin,
    dest: str,
    *,
    git: GitPort,
    llm: LLMPort,
    gh: GhPort,
    model: str,
    options: SyncOptions,
) -> SyncOutcome:
    """Run the pipeline for a single skill and return its terminal outcome."""
    if changeset.kind == "none":
        return SyncOutcome(
            name=changeset.name,
            skill_path=changeset.skill_path,
            status="skipped",
            detail="no upstream change",
        )

    layout = SkillLayout.resolve(root, changeset.skill_path, dest=dest)

    # Adaptation is opt-in: a skill is adapted only when it has an adaptation.md on
    # disk. Without one, leave it entirely untouched (no mirror, no LLM, no PR, sha
    # frozen) until the author opts in by adding adaptation rules.
    if not layout.adaptation_path.exists():
        return SyncOutcome(
            name=changeset.name,
            skill_path=changeset.skill_path,
            status="skipped",
            detail="no adaptation.md (adaptation is opt-in); skill left untouched",
        )

    # Read the new upstream subtree — the gate's scan surface and the mirror source.
    repo_path = git.mirror(repo, ref)
    new_files = git.read_subtree_files(repo_path, ref, changeset.skill_path)

    # 1. Deterministic security gate — runs BEFORE any agent reads upstream. This is
    #    the load-bearing gate and is never skippable, even on a local run.
    gate = run_gate(changeset, new_files)
    if not gate.passed:
        return _quarantine(changeset, gate, gh, root)

    # 2. Advisory LLM scan (defense-in-depth annotation, never a gate). Optional.
    advisory = (
        advisory_scan(changeset.diff, llm, model)
        if options.run_advisory
        else _SKIPPED_ADVISORY
    )

    # 3. Reconcile any hand-edit drift into the adaptation rules. Optional.
    skill_files = read_skill(layout)
    adaptation_text = skill_files.adaptation or ""
    drift = detect_drift(skill_files) if options.run_reconcile else None
    adaptation_summary: str | None = None
    if drift is not None:
        folded = fold_back(adaptation_text, drift, llm, model=model)
        adaptation_text = folded.new_adaptation_text
        adaptation_summary = folded.summary

    # 4. Adapt — patch for an incremental change, full for a re-onboard.
    mode = "full" if changeset.kind == "reonboard" else "patch"
    adapt_result = adapt(
        layout, changeset, new_files, adaptation_text, llm, mode=mode, model=model
    )

    # 5. Verify the hand-edit's intent survived (only when fold-back ran).
    if drift is not None:
        verdict = verify_preserved(drift, adapt_result.skill_md_text, llm, model=model)
        if not verdict.preserved:
            adapt_result.flags.append(f"{_NOT_PRESERVED_FLAG}: {verdict.note}")

    # 6. Deterministic validate — blocks the PR on a non-loadable skill. Optional:
    #    a local run may skip it to inspect even a malformed generation.
    if options.run_validate:
        validation = validate_skill(
            layout, adapt_result.skill_md_text, DEFAULT_MAX_FILE_BYTES
        )
        if not validation.passed:
            return _invalid(changeset, validation.errors, gh, root)

    # 7. Commit the artifacts and bump the pin. The artifacts land in the working
    #    tree on every successful run; the sha bump records the new sync point.
    _write_artifacts(layout, new_files, adapt_result, adaptation_text, drift)
    pin.synced_sha = changeset.to_sha
    save_config(config, root / "sources.yaml")

    # 8. Open the PR — unless this is a local (`--no-pr`) run, which stops here and
    #    leaves the adapted files uncommitted in the working tree for inspection.
    if not options.open_pr:
        return SyncOutcome(
            name=changeset.name,
            skill_path=changeset.skill_path,
            status="local",
            detail="adapted locally; no PR opened (artifacts left in the working tree)",
            flags=list(adapt_result.flags),
        )

    skill_pr = build_pr(
        changeset, gate, advisory, adapt_result, adaptation_summary=adaptation_summary
    )
    url = publish_pr(skill_pr, gh, root)
    return SyncOutcome(
        name=changeset.name,
        skill_path=changeset.skill_path,
        status="pr",
        url=url,
        detail=skill_pr.title,
        flags=list(adapt_result.flags),
    )


def _write_artifacts(
    layout: SkillLayout,
    new_files: dict[str, str],
    adapt_result: AdaptResult,
    adaptation_text: str,
    drift: str | None,
) -> None:
    """Write the upstream mirror, SKILL.md, snapshot, and (if folded) adaptation.md."""
    mirror_files(new_files, layout.upstream_dir)
    write_text(layout.skill_md_path, adapt_result.skill_md_text)
    write_text(layout.generated_skill_md_path, adapt_result.snapshot_text)
    if drift is not None:
        write_text(layout.adaptation_path, adaptation_text)


def _quarantine(
    changeset: ChangeSet, gate: GateResult, gh: GhPort, root: Path
) -> SyncOutcome:
    """Open a quarantine issue for a gate failure and leave the pin untouched."""
    title = f"skillsync quarantine: {changeset.name} failed the security gate"
    body = _quarantine_body(changeset, gate)
    url = gh.open_issue(root, title, body, ["skillsync", "quarantine"])
    return SyncOutcome(
        name=changeset.name,
        skill_path=changeset.skill_path,
        status="quarantined",
        url=url,
        detail="security gate failed; skill left pinned at the old sha",
    )


def _invalid(
    changeset: ChangeSet, errors: list[str], gh: GhPort, root: Path
) -> SyncOutcome:
    """Open an issue for a validation failure; no PR, no writes, no sha bump."""
    title = f"skillsync invalid: {changeset.name} failed validation"
    body = _invalid_body(changeset, errors)
    url = gh.open_issue(root, title, body, ["skillsync", "invalid"])
    return SyncOutcome(
        name=changeset.name,
        skill_path=changeset.skill_path,
        status="invalid",
        url=url,
        detail="adapted SKILL.md failed validation; no PR opened",
    )


def _quarantine_body(changeset: ChangeSet, gate: GateResult) -> str:
    """Render the quarantine issue body: findings, extracted cmds/URLs, raw diff."""
    findings = "\n".join(
        f"- `{f.severity}` {f.kind} ({f.file}): {f.detail}" for f in gate.findings
    ) or "- none"
    commands = "\n".join(f"- `{c}`" for c in gate.commands) or "- none"
    urls = "\n".join(f"- `{u}`" for u in gate.urls) or "- none"
    return (
        f"The security gate failed for `{changeset.name}` "
        f"(`{changeset.skill_path}`). The skill stays pinned at "
        f"`{_short(changeset.from_sha)}`; it was NOT adapted.\n\n"
        f"## Gate findings\n{findings}\n\n"
        f"## Extracted commands\n{commands}\n\n"
        f"## Extracted URLs\n{urls}\n\n"
        "## Raw upstream diff\n```diff\n"
        f"{changeset.diff.strip()}\n```\n"
    )


def _invalid_body(changeset: ChangeSet, errors: list[str]) -> str:
    """Render the validation-failure issue body: the errors and the raw diff."""
    error_lines = "\n".join(f"- {error}" for error in errors) or "- none"
    return (
        f"The adapted `SKILL.md` for `{changeset.name}` "
        f"(`{changeset.skill_path}`) failed validation, so no PR was opened and the "
        f"pin stays at `{_short(changeset.from_sha)}`.\n\n"
        f"## Validation errors\n{error_lines}\n\n"
        "## Raw upstream diff\n```diff\n"
        f"{changeset.diff.strip()}\n```\n"
    )


def _short(sha: str | None) -> str:
    """Abbreviate a SHA to 7 chars; render a missing SHA as `(none)`."""
    return "(none)" if sha is None else sha[:7]
