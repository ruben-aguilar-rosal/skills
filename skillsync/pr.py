"""PR output layer — assemble and publish one PR per changed skill.

`build_pr` is a pure function that turns the pipeline's results into a `SkillPR`:
a `skillsync/<name>` branch, a title, a body, and review labels. The body is the
human-review surface, so it always reproduces the RAW upstream diff alongside the
gate's extracted commands and URLs — adaptation runs downstream of the diff and
can never launder a threat past the reviewer (PLAN.md hardening decision 2).

`publish_pr` drives a `GhPort` to realise the PR: create the branch, commit the
working tree, and open the PR — in that order. All git/gh contact lives behind the
port, so the assembly logic is testable without touching real `git`/`gh`.
"""

from dataclasses import dataclass, field
from pathlib import Path

from skillsync.ports.gh import GhPort
from skillsync.stages.adapt import AdaptResult
from skillsync.stages.detect import ChangeSet
from skillsync.stages.gate import GateResult
from skillsync.stages.llm_scan import AdvisoryVerdict

# Branch prefix for every sync PR (PLAN.md: branch `skillsync/<skill-name>`).
_BRANCH_PREFIX = "skillsync"

# Fixed label applied to every sync PR, plus the advisory-risk label prefix.
_BASE_LABEL = "skillsync"
_RISK_LABEL_PREFIX = "advisory-risk"


@dataclass(frozen=True)
class SkillPR:
    """An assembled, not-yet-published PR for one changed skill.

    `branch` is the `skillsync/<name>` head branch; `title` and `body` are the PR
    text; `labels` are the review labels. `commit_message` is what `publish_pr`
    commits the working tree under before opening the PR.
    """

    name: str
    branch: str
    title: str
    body: str
    commit_message: str
    labels: list[str] = field(default_factory=list)


def build_pr(
    changeset: ChangeSet,
    gate: GateResult,
    advisory: AdvisoryVerdict,
    adapt_result: AdaptResult,
    *,
    adaptation_summary: str | None = None,
    extra_labels: list[str] | None = None,
) -> SkillPR:
    """Assemble a `SkillPR` from the pipeline results for one changed skill.

    The body is built to be the complete human-review surface: the raw upstream
    diff, the gate's extracted commands and URLs, the advisory verdict, the sha
    bump, the adaptation.md change summary, and any review flags. Nothing about the
    body depends on the adapted output — the raw diff is always shown verbatim.
    `extra_labels` are appended to the review labels (e.g. `onboarding` for a
    first-time `skillsync add`).
    """
    name = changeset.name
    branch = f"{_BRANCH_PREFIX}/{name}"
    title = f"skillsync: update {name} ({_short(changeset.from_sha)}→{_short(changeset.to_sha)})"
    flags = _collect_flags(changeset, adapt_result)
    body = _build_body(changeset, gate, advisory, adaptation_summary, flags)
    return SkillPR(
        name=name,
        branch=branch,
        title=title,
        body=body,
        commit_message=f"skillsync: adapt {name} to {_short(changeset.to_sha)}",
        labels=_build_labels(advisory, flags, extra_labels or []),
    )


def publish_pr(skill_pr: SkillPR, gh: GhPort, root: Path) -> str:
    """Realise `skill_pr` via the `GhPort`: branch -> commit -> open PR.

    Creates the `skillsync/<name>` branch, commits the working tree under the PR's
    commit message, then opens the PR. Returns the PR URL the port reports.
    """
    gh.create_branch(root, skill_pr.branch)
    gh.commit_all(root, skill_pr.commit_message)
    return gh.open_pr(
        root, skill_pr.branch, skill_pr.title, skill_pr.body, skill_pr.labels
    )


def _collect_flags(changeset: ChangeSet, adapt_result: AdaptResult) -> list[str]:
    """Gather review flags from the change set and adapt result (dedup, ordered)."""
    flags: list[str] = []
    if changeset.rewritten_history:
        flags.append("upstream rewrote history — review carefully")
    for flag in adapt_result.flags:
        if flag not in flags:
            flags.append(flag)
    return flags


def _build_labels(
    advisory: AdvisoryVerdict, flags: list[str], extra_labels: list[str]
) -> list[str]:
    """Build the review labels: base, advisory risk, a flag marker, and any extras."""
    labels = [_BASE_LABEL, f"{_RISK_LABEL_PREFIX}-{advisory.risk}"]
    if flags:
        labels.append("needs-attention")
    for label in extra_labels:
        if label not in labels:
            labels.append(label)
    return labels


def _build_body(
    changeset: ChangeSet,
    gate: GateResult,
    advisory: AdvisoryVerdict,
    adaptation_summary: str | None,
    flags: list[str],
) -> str:
    """Render the full PR body markdown from the pipeline results."""
    sections: list[str] = []

    if flags:
        sections.append("## ⚠ Flags\n" + "\n".join(f"- {flag}" for flag in flags))

    sections.append(
        "## Sync\n"
        f"- skill: `{changeset.name}` (`{changeset.skill_path}`)\n"
        f"- kind: `{changeset.kind}`\n"
        f"- sha: `{_short(changeset.from_sha)}` → `{_short(changeset.to_sha)}`"
    )

    sections.append(
        "## Security gate\n"
        f"- result: **{'PASS' if gate.passed else 'FAIL'}**\n"
        + _findings_lines(gate)
    )

    sections.append(
        "## Advisory scan\n"
        f"- risk: **{advisory.risk}**\n"
        f"- rationale: {advisory.rationale}\n"
        + _advisory_findings_lines(advisory)
    )

    sections.append("## Extracted commands\n" + _code_list(gate.commands))
    sections.append("## Extracted URLs\n" + _code_list(gate.urls))

    if adaptation_summary:
        sections.append("## adaptation.md changes\n" + adaptation_summary)

    sections.append(
        "## Raw upstream diff\n"
        "Shown verbatim — adaptation runs downstream and cannot launder it.\n\n"
        "```diff\n" + changeset.diff.strip() + "\n```"
    )

    return "\n\n".join(sections) + "\n"


def _findings_lines(gate: GateResult) -> str:
    """Render gate findings as bullet lines, or a 'none' marker when empty."""
    if not gate.findings:
        return "- findings: none"
    return "\n".join(
        f"- `{f.severity}` {f.kind} ({f.file}): {f.detail}" for f in gate.findings
    )


def _advisory_findings_lines(advisory: AdvisoryVerdict) -> str:
    """Render advisory findings as bullet lines, or a 'none' marker when empty."""
    if not advisory.findings:
        return "- findings: none"
    return "\n".join(f"- {finding}" for finding in advisory.findings)


def _code_list(items: list[str]) -> str:
    """Render `items` as inline-code bullet lines, or a 'none' marker when empty."""
    if not items:
        return "- none"
    return "\n".join(f"- `{item}`" for item in items)


def _short(sha: str | None) -> str:
    """Abbreviate a SHA to 7 chars; render a missing SHA as `(none)`."""
    if sha is None:
        return "(none)"
    return sha[:7]
