"""Tests for the SkillSpector security-scan port.

`scan_subtree` is the gate skillsync runs over an upstream subtree: it materializes
the files to a temp dir, hands the dir to a `ScannerPort`, and folds the result into
a `GateResult`. It BLOCKS (failing GateResult) when any finding is CRITICAL or HIGH,
and FAIL-SAFES to a blocking result when the scanner can't run. `SkillSpectorCli` is
exercised with an injected fake subprocess runner — the real `skillspector` binary is
never invoked.
"""

import json
import subprocess
from pathlib import Path

import pytest

from skillsync.ports.scanner import ScanError, ScannerPort, scan_subtree
from skillsync.ports.scanner_cli import SkillSpectorCli
from skillsync.stages.detect import ChangeSet
from skillsync.stages.gate import GateResult
from skillsync.testing.fakes import FakeScanner


def _changeset() -> ChangeSet:
    """A minimal reonboard changeset for a `demo` skill."""
    return ChangeSet(
        skill_path="skills/demo",
        name="demo",
        kind="reonboard",
        from_sha=None,
        to_sha="sha1",
        diff="",
        changed_files=["SKILL.md"],
    )


def _finding(severity: str, rule_id: str = "R1") -> dict:
    """One SkillSpector `issues[]` entry in its JSON `to_dict` shape."""
    return {
        "id": rule_id,
        "category": "prompt_injection",
        "severity": severity,
        "confidence": 0.9,
        "location": {"file": "SKILL.md", "start_line": 3, "end_line": None},
        "explanation": f"a {severity} issue",
    }


# --- scan_subtree: blocking semantics -------------------------------------------


def test_scan_subtree_passes_clean_skill(tmp_path: Path) -> None:
    """No findings → the gate passes."""
    scanner = FakeScanner(GateResult(passed=True, findings=[]))

    result = scan_subtree(scanner, _changeset(), {"SKILL.md": "# demo\n"})

    assert result.passed is True


def test_scan_subtree_blocks_on_critical(tmp_path: Path) -> None:
    """A CRITICAL finding fails the gate."""
    scanner = FakeScanner.from_issues(score=60, severity="CRITICAL", issues=[_finding("CRITICAL")])

    result = scan_subtree(scanner, _changeset(), {"SKILL.md": "x"})

    assert result.passed is False
    assert any(f.severity == "fail" for f in result.findings)


def test_scan_subtree_blocks_on_high(tmp_path: Path) -> None:
    """A single HIGH finding fails the gate (stricter than score>50)."""
    scanner = FakeScanner.from_issues(score=25, severity="MEDIUM", issues=[_finding("HIGH")])

    result = scan_subtree(scanner, _changeset(), {"SKILL.md": "x"})

    assert result.passed is False


def test_scan_subtree_allows_medium_and_low(tmp_path: Path) -> None:
    """MEDIUM/LOW findings are surfaced but do not block."""
    scanner = FakeScanner.from_issues(
        score=15, severity="LOW", issues=[_finding("MEDIUM"), _finding("LOW")]
    )

    result = scan_subtree(scanner, _changeset(), {"SKILL.md": "x"})

    assert result.passed is True
    # The findings are still carried for the PR body.
    assert len(result.findings) == 2


def test_scan_subtree_fail_safe_quarantines_on_scan_error(tmp_path: Path) -> None:
    """A scanner that raises ScanError fails the gate (fail-safe, never silent)."""
    scanner = FakeScanner(error=ScanError("skillspector not installed"))

    result = scan_subtree(scanner, _changeset(), {"SKILL.md": "x"})

    assert result.passed is False
    assert any("skillspector" in f.detail.lower() for f in result.findings)


def test_scan_subtree_materializes_files_for_the_scanner(tmp_path: Path) -> None:
    """The subtree files are written to a real dir the scanner receives."""
    scanner = FakeScanner(GateResult(passed=True, findings=[]))

    scan_subtree(scanner, _changeset(), {"SKILL.md": "# demo\n", "scripts/run.py": "x"})

    # The fake recorded a directory that actually contained the files at scan time.
    assert scanner.scanned_files == {"SKILL.md": "# demo\n", "scripts/run.py": "x"}


# --- SkillSpectorCli: argv + JSON parsing (injected runner) ---------------------


class _Runner:
    """A fake subprocess runner returning a scripted CompletedProcess."""

    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, self.returncode, stdout=self.stdout, stderr="")


def _report(issues: list[dict], score: int = 0, severity: str = "LOW") -> str:
    """A SkillSpector `--format json` report body."""
    return json.dumps(
        {
            "skill": {"name": "demo"},
            "risk_assessment": {"score": score, "severity": severity, "recommendation": "SAFE"},
            "issues": issues,
        }
    )


def test_cli_builds_no_llm_json_argv(tmp_path: Path) -> None:
    """The adapter invokes `skillspector scan <dir> --no-llm --format json`."""
    runner = _Runner(_report([]))
    cli = SkillSpectorCli(runner=runner)

    cli.scan(tmp_path / "skill")

    argv = runner.calls[0]
    assert argv[:2] == ["skillspector", "scan"]
    assert str(tmp_path / "skill") in argv
    assert "--no-llm" in argv
    assert argv[argv.index("--format") + 1] == "json"


def test_cli_maps_issues_to_findings(tmp_path: Path) -> None:
    """Each JSON issue becomes a Finding with its severity, rule, file, and explanation."""
    runner = _Runner(_report([_finding("HIGH", "PI-001")], score=25, severity="MEDIUM"))
    cli = SkillSpectorCli(runner=runner)

    result = cli.scan(tmp_path)

    assert isinstance(result, GateResult)
    [finding] = result.findings
    assert finding.kind == "PI-001"
    assert finding.file == "SKILL.md"
    assert "HIGH" in finding.detail or "high" in finding.detail.lower()


def test_cli_raises_scan_error_on_unparseable_output(tmp_path: Path) -> None:
    """Non-JSON output raises ScanError (which the gate turns into a fail-safe block)."""
    runner = _Runner("not json", returncode=0)
    cli = SkillSpectorCli(runner=runner)

    with pytest.raises(ScanError):
        cli.scan(tmp_path)


def test_cli_tolerates_exit_code_one(tmp_path: Path) -> None:
    """Exit 1 (risk_score>50) is a normal 'findings present' result, not an error."""
    runner = _Runner(_report([_finding("CRITICAL")], score=60, severity="HIGH"), returncode=1)
    cli = SkillSpectorCli(runner=runner)

    result = cli.scan(tmp_path)

    assert len(result.findings) == 1


def test_cli_raises_on_error_exit_code_two(tmp_path: Path) -> None:
    """Exit 2 is SkillSpector's error code → ScanError."""
    runner = _Runner("", returncode=2)
    cli = SkillSpectorCli(runner=runner)

    with pytest.raises(ScanError):
        cli.scan(tmp_path)


def test_fake_scanner_satisfies_protocol() -> None:
    """`FakeScanner` is a structural `ScannerPort`."""
    assert isinstance(FakeScanner(GateResult(passed=True)), ScannerPort)
