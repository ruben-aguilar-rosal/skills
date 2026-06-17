"""REGEN command — rebuild a skill's SKILL.md from the CURRENT on-disk sources.

`run_regen` regenerates one skill's `SKILL.md` from the upstream mirror and
`adaptation.md` already on disk — it does NOT re-pull upstream. This is the lever
for re-running generation after you hand-edit an `adaptation.md` (or want a clean
rebuild): there is no new upstream diff, so generation always runs in FULL mode
(`--force` is accepted for symmetry but does not change the mode — a full rebuild
is already what regen does). The produced `SKILL.md` is validated before any PR.

The two outcomes mirror the sync/add pipeline's PR-side exits:

- **pr** — the regenerated `SKILL.md` validates; it and its `.generated` snapshot
  are written and a PR opens on the `skillsync/regen-<name>` branch (labelled
  `regen`). Regen NEVER bumps `synced_sha`: there is no new upstream to sync to.
- **invalid** — the regenerated `SKILL.md` fails validation. No PR opens, nothing
  is written to the skill folder, and an issue is filed.

The shared `regenerate_to_pr` helper (also used by `reprofile`) does the
adapt → validate → write+PR / issue work behind the injected `LLMPort`/`GhPort`,
so the whole flow runs against fakes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from skillsync.config import Config
from skillsync.layout import SkillLayout, mirror_files, read_text, read_tree, write_text
from skillsync.pr import build_pr, publish_pr
from skillsync.ports.gh import GhPort
from skillsync.ports.llm import LLMPort
from skillsync.stages.adapt import AdaptResult, adapt
from skillsync.stages.detect import ChangeSet
from skillsync.stages.gate import DEFAULT_MAX_FILE_BYTES, GateResult
from skillsync.stages.llm_scan import AdvisoryVerdict
from skillsync.stages.validate import validate_skill

# Default model for the agentic regeneration (PLAN.md: Opus for every agentic step).
_DEFAULT_MODEL = "opus"

# Label applied to every regen PR so the PR list distinguishes a maintenance
# rebuild from an incremental upstream sync.
_REGEN_LABEL = "regen"

# A regeneration scans no NEW upstream diff: the on-disk mirror was vetted by the
# gate at sync/add time. These neutral placeholders keep the reused PR body honest
# rather than implying a fresh scan ran.
_CLEAN_GATE = GateResult(passed=True, findings=[], commands=[], urls=[])
_REGEN_ADVISORY = AdvisoryVerdict(
    risk="low",
    rationale=(
        "regeneration from the already-vetted on-disk upstream mirror; "
        "no new upstream diff to scan"
    ),
    findings=[],
)

Status = Literal["pr", "invalid"]


@dataclass
class RegenOutcome:
    """The result of regenerating one skill.

    `status` is the terminal outcome; `url` is the PR or issue URL opened; `detail`
    is a short human-readable summary.
    """

    name: str
    skill_path: str
    status: Status
    url: str | None = None
    detail: str = ""
    flags: list[str] = field(default_factory=list)


def run_regen(
    config: Config,
    root: Path,
    name: str,
    *,
    llm: LLMPort,
    gh: GhPort,
    force: bool = False,
    model: str = _DEFAULT_MODEL,
) -> RegenOutcome:
    """Regenerate `name`'s SKILL.md from its on-disk upstream + adaptation, opening a PR.

    Reads the upstream mirror and `adaptation.md` already under `skills/<name>/`,
    full-generates a fresh `SKILL.md`, validates it, and — on success — writes the
    SKILL.md + snapshot and opens a `skillsync/regen-<name>` PR. `force` is accepted
    for CLI symmetry but does not change the mode (regen is always a full rebuild).
    A validation failure opens an issue and writes nothing. `config` is unused (regen
    never touches the pins) but kept in the signature to match the other commands.
    """
    layout = SkillLayout.resolve(root, name)
    adaptation_text = read_text(layout.adaptation_path) or ""
    upstream_files = read_tree(layout.upstream_dir)

    branch = f"skillsync/regen-{name}"
    title = f"skillsync: regenerate {name}"
    status, url, detail, flags = regenerate_to_pr(
        layout,
        root,
        adaptation_text,
        upstream_files,
        llm=llm,
        gh=gh,
        branch=branch,
        title=title,
        labels=[_REGEN_LABEL],
        kind=_REGEN_LABEL,
        model=model,
    )
    return RegenOutcome(
        name=name,
        skill_path=str(layout.root.relative_to(root)),
        status=status,
        url=url,
        detail=detail,
        flags=flags,
    )


def regenerate_to_pr(
    layout: SkillLayout,
    root: Path,
    adaptation_text: str,
    upstream_files: dict[str, str],
    *,
    llm: LLMPort,
    gh: GhPort,
    branch: str,
    title: str,
    labels: list[str],
    kind: str,
    model: str,
) -> tuple[Status, str | None, str, list[str]]:
    """Full-generate, validate, then write+PR or file an issue. Returns the outcome.

    Shared by `regen` and `reprofile`: both regenerate a `SKILL.md` from the on-disk
    upstream mirror plus a (possibly just-rebaked) `adaptation.md`, in FULL mode.
    On a valid result the SKILL.md + `.generated` snapshot are written and a PR opens
    on `branch` with `title`/`labels`; on a validation failure an issue is filed
    (labelled with `kind`) and nothing is written. Returns `(status, url, detail, flags)`.
    """
    changeset = _regen_changeset(layout, upstream_files)
    adapt_result = adapt(
        layout, changeset, upstream_files, adaptation_text, llm, mode="full", model=model
    )

    validation = validate_skill(
        layout, adapt_result.skill_md_text, DEFAULT_MAX_FILE_BYTES
    )
    if not validation.passed:
        url = _open_invalid_issue(changeset, validation.errors, gh, root, kind)
        return "invalid", url, "regenerated SKILL.md failed validation; no PR opened", []

    _write_artifacts(layout, upstream_files, adapt_result)
    skill_pr = build_pr(
        changeset,
        _CLEAN_GATE,
        _REGEN_ADVISORY,
        adapt_result,
        extra_labels=labels,
        branch=branch,
        title=title,
    )
    url = publish_pr(skill_pr, gh, root)
    return "pr", url, skill_pr.title, list(adapt_result.flags)


def _regen_changeset(layout: SkillLayout, upstream_files: dict[str, str]) -> ChangeSet:
    """Build a synthetic change set for a regeneration (no new upstream diff).

    The `diff` is the current on-disk upstream content, rendered so the reused PR
    body shows reviewers exactly what the SKILL.md was regenerated from.
    """
    diff = "\n".join(
        f"### {path}\n{content}" for path, content in sorted(upstream_files.items())
    )
    return ChangeSet(
        skill_path=f"skills/{layout.name}",
        name=layout.name,
        kind="reonboard",
        from_sha=None,
        to_sha="(regen)",
        diff=diff,
        changed_files=sorted(upstream_files),
    )


def _write_artifacts(
    layout: SkillLayout, upstream_files: dict[str, str], adapt_result: AdaptResult
) -> None:
    """Write the regenerated SKILL.md, its snapshot, and re-mirror the upstream files."""
    mirror_files(upstream_files, layout.upstream_dir)
    write_text(layout.skill_md_path, adapt_result.skill_md_text)
    write_text(layout.generated_skill_md_path, adapt_result.snapshot_text)


def _open_invalid_issue(
    changeset: ChangeSet, errors: list[str], gh: GhPort, root: Path, kind: str
) -> str:
    """File an issue for a regeneration whose SKILL.md failed validation."""
    title = f"skillsync invalid: {kind} of {changeset.name} failed validation"
    error_lines = "\n".join(f"- {error}" for error in errors) or "- none"
    body = (
        f"Regenerating `{changeset.name}` (`{changeset.skill_path}`) during "
        f"`{kind}` produced a `SKILL.md` that failed validation, so no PR was "
        "opened and nothing was written to the skill folder.\n\n"
        f"## Validation errors\n{error_lines}\n"
    )
    return gh.open_issue(root, title, body, ["skillsync", "invalid", kind])
