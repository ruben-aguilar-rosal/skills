"""Real `ScannerPort` implementation shelling out to NVIDIA SkillSpector.

Invokes `skillspector scan <dir> --no-llm --format json` and maps the JSON report's
`issues[]` into skillsync `Finding`s. `--no-llm` keeps the gate deterministic and
free (skillsync runs its own advisory LLM scan separately). Every subprocess call
uses an args list with `shell=False` and a timeout; nothing is interpolated into a
shell string.

SkillSpector exit codes (from its CLI): 0 = clean, 1 = risk_score > 50 (findings
present — still a valid report on stdout), 2 = error. Only exit 2 (or unparseable
output) is a `ScanError`; exit 1 is a normal findings-present result.
"""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from skillsync.ports.scanner import ScanError
from skillsync.stages.gate import Finding, GateResult

_DEFAULT_TIMEOUT = 300

# SkillSpector severities skillsync blocks on → mapped to `fail`; the rest are
# surfaced for the PR body without blocking.
_SEVERITY_MAP = {
    "CRITICAL": "fail",
    "HIGH": "fail",
    "MEDIUM": "warn",
    "LOW": "info",
}

# SkillSpector's error exit code (1 = findings present but a valid report; 2 = error).
_ERROR_EXIT = 2

# A subprocess runner: takes argv + timeout, returns the completed process. The
# default shells out to `skillspector`; tests inject a fake.
Runner = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]


def _default_runner(argv: list[str], timeout: int) -> "subprocess.CompletedProcess[str]":
    """Run `argv` with `shell=False`, capturing text output under a timeout."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


class SkillSpectorCli:
    """`ScannerPort` backed by the local `skillspector` CLI (static, `--no-llm`)."""

    def __init__(
        self,
        runner: Runner | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        command: list[str] | None = None,
    ) -> None:
        """Configure the subprocess `runner`, per-scan timeout, and command prefix."""
        self._runner = runner or _default_runner
        self._timeout = timeout
        self._command = list(command) if command else ["skillspector"]

    def scan(self, skill_dir: Path) -> GateResult:
        """Run `skillspector scan <dir> --no-llm --format json` and map the report."""
        argv = [*self._command, "scan", str(skill_dir), "--no-llm", "--format", "json"]
        try:
            completed = self._runner(argv, self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise ScanError(f"skillspector timed out after {self._timeout}s") from exc
        except OSError as exc:
            raise ScanError(f"skillspector could not be executed: {exc}") from exc

        if completed.returncode >= _ERROR_EXIT:
            detail = completed.stderr.strip() or completed.stdout.strip() or "(no output)"
            raise ScanError(f"skillspector failed ({completed.returncode}): {detail}")

        return self._parse(completed.stdout)

    @staticmethod
    def _parse(stdout: str) -> GateResult:
        """Map a SkillSpector JSON report into a `GateResult`; raise on bad output."""
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ScanError(f"skillspector returned non-JSON output: {stdout[:200]!r}") from exc

        issues = report.get("issues")
        if not isinstance(issues, list):
            raise ScanError(f"skillspector report has no issues array: {report!r}")

        findings = [_to_finding(issue) for issue in issues]
        passed = not any(f.severity == "fail" for f in findings)
        return GateResult(passed=passed, findings=findings)


def _to_finding(issue: dict) -> Finding:
    """Map one SkillSpector `issues[]` entry to a skillsync `Finding`."""
    severity_label = str(issue.get("severity", "LOW")).upper()
    location = issue.get("location") or {}
    explanation = issue.get("explanation") or issue.get("message") or "(no explanation)"
    category = issue.get("category")
    detail = f"[{severity_label}] {explanation}"
    if category:
        detail = f"[{severity_label}] {category}: {explanation}"
    return Finding(
        severity=_SEVERITY_MAP.get(severity_label, "info"),
        kind=str(issue.get("id") or "skillspector"),
        detail=detail,
        file=str(location.get("file") or "SKILL.md"),
    )
