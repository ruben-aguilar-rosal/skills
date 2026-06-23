"""Security-scan port — the load-bearing security gate over an upstream subtree.

skillsync delegates its blocking security check to NVIDIA's SkillSpector
(https://github.com/NVIDIA/SkillSpector), an external scanner that detects skill
vulnerabilities (prompt injection, data exfiltration, excessive agency, …). The
`ScannerPort` contract is "scan a skill directory, return a `GateResult`"; the real
adapter (`SkillSpectorCli`) shells out to `skillspector`, and a `FakeScanner` backs
the same contract in tests.

`scan_subtree` is the gate the pipeline calls: it materializes the (pristine,
pre-adaptation) upstream subtree to a temp dir, scans it, and folds the verdict into
the shared `GateResult`. Two hardening rules:

1. **CRITICAL or HIGH blocks.** Any finding at those severities fails the gate
   (quarantine); MEDIUM/LOW are surfaced for the PR but do not block.
2. **Fail safe.** If the scanner cannot run (not installed, bad output, crash), the
   gate FAILS — a security control that silently no-ops is worse than a loud block.
"""

import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from skillsync.layout import write_text
from skillsync.stages.detect import ChangeSet
from skillsync.stages.gate import Finding, GateResult

# SkillSpector severities that block the pipeline (quarantine the skill).
_BLOCKING_SEVERITIES = frozenset({"CRITICAL", "HIGH"})


class ScanError(Exception):
    """Raised when the scanner cannot produce a verdict (missing, timeout, bad output)."""


@runtime_checkable
class ScannerPort(Protocol):
    """Scan a skill directory and return a `GateResult` (findings + pass/fail).

    `passed` reflects the scanner's own gating, but skillsync re-derives the block
    decision from finding severities in `scan_subtree`, so an adapter only needs to
    populate `findings` faithfully and may leave `passed` as a best effort.
    """

    def scan(self, skill_dir: Path) -> GateResult:
        """Scan the skill folder at `skill_dir`; raise `ScanError` if it cannot run."""
        ...


def scan_subtree(
    scanner: ScannerPort,
    changeset: ChangeSet,
    files: dict[str, str],
    accepted: list[str] | None = None,
) -> GateResult:
    """Materialize `files` to a temp dir, scan it, and return the gate verdict.

    The block decision is skillsync's, not the scanner's: the gate fails iff a
    CRITICAL/HIGH finding (mapped to `fail` by the adapter) remains. `accepted` lists
    rule IDs the author has reviewed and accepted — a blocking finding with one of
    those IDs is demoted to a `warn` (still surfaced in the PR, no longer blocking),
    so accepting `P1` does not blanket-accept a freshly-introduced finding.

    A `ScanError` is converted into a failing `GateResult` (fail-safe quarantine)
    rather than propagating, so a missing or broken scanner stops the skill instead
    of waving it through.
    """
    accepted_ids = set(accepted or [])
    try:
        with tempfile.TemporaryDirectory(prefix="skillsync-scan-") as tmp:
            tmp_dir = Path(tmp)
            for rel_path, content in files.items():
                write_text(tmp_dir / rel_path, content)
            result = scanner.scan(tmp_dir)
    except ScanError as exc:
        return _fail_safe(changeset, exc)

    findings = [_apply_acceptance(f, accepted_ids) for f in result.findings]
    # The adapter maps CRITICAL/HIGH issues to `fail`; after acceptance, the gate
    # fails iff a non-accepted blocking finding remains.
    blocked = any(finding.severity == "fail" for finding in findings)
    return GateResult(
        passed=not blocked,
        findings=findings,
        commands=result.commands,
        urls=result.urls,
    )


def _apply_acceptance(finding: Finding, accepted_ids: set[str]) -> Finding:
    """Demote an accepted blocking finding to a non-blocking annotation."""
    if finding.severity == "fail" and finding.kind in accepted_ids:
        return Finding(
            severity="warn",
            kind=finding.kind,
            detail=f"{finding.detail} (accepted via accept_findings)",
            file=finding.file,
        )
    return finding


def _fail_safe(changeset: ChangeSet, exc: ScanError) -> GateResult:
    """Build the conservative failing verdict used when the scanner can't be trusted."""
    return GateResult(
        passed=False,
        findings=[
            Finding(
                severity="fail",
                kind="scanner_unavailable",
                detail=(
                    f"security scan could not run for {changeset.name}: {exc}; "
                    "fail-safe quarantine (install SkillSpector or fix the scanner)"
                ),
                file=changeset.skill_path,
            )
        ],
    )
