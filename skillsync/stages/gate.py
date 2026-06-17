"""Deterministic SECURITY GATE — the load-bearing security control.

`run_gate` is a pure function over the file contents the caller supplies: it
applies four deterministic checks (size/frontmatter limits, a command extractor
with a curated high-risk list, a URL extractor, and a credential-shape secret
scan) and returns a `GateResult`. No LLM, no I/O. The advisory LLM scan (P09) is
defense-in-depth layered on top of this gate, never a substitute for it.

A finding with `severity == "fail"` fails the gate. Extraction alone — surfacing
commands and URLs for human review in the PR — never fails the gate; only the
curated high-risk patterns and secret hits do.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

import yaml

from skillsync.stages.detect import ChangeSet

Severity = Literal["fail", "warn", "info"]

# Default per-file byte ceiling — an anti-bloat tripwire, overridable by callers.
DEFAULT_MAX_FILE_BYTES = 256 * 1024

# Source-like files whose full contents (not just fenced blocks) are scanned for
# candidate commands.
_SCRIPT_SUFFIXES = (".sh", ".bash", ".zsh", ".py")

# Tokens that mark a line as a candidate command worth surfacing for human view.
_COMMAND_TOKENS = (
    "curl",
    "wget",
    "bash",
    "sh ",
    "eval",
    "base64",
    "rm -rf",
    "chmod",
    "nc ",
    "ncat",
    "python -c",
    "python3 -c",
    "sudo",
)

# Curated high-risk command patterns. A match here -> failing finding. Each entry
# is (compiled regex, human-readable reason).
_HIGH_RISK_COMMANDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba)?sh\b"),
     "pipe-to-shell download executes remote code"),
    (re.compile(r"/dev/tcp/"), "reverse shell via /dev/tcp"),
    (re.compile(r"\bnc(?:at)?\b[^\n]*-e\b"), "netcat reverse shell (-e)"),
    (re.compile(r"\brm\s+-rf\s+(?:/|~|\$HOME)\b"), "recursive delete of a root/home path"),
    (re.compile(r"(?:cat|less|head|tail)\s+[^\n]*"
                r"(?:~/\.aws/credentials|~/\.ssh/|/etc/(?:passwd|shadow)|\.env\b)"),
     "reads a known secret/credential path"),
    (re.compile(r"\b(?:base64\s+-d|base64\s+--decode)\b[^\n|]*\|\s*(?:ba)?sh\b"),
     "base64-decode piped to shell"),
    (re.compile(r"\beval\b[^\n]*\$\((?:curl|wget)\b"),
     "eval of remote-fetched content"),
]

# URL extractor: http(s) URLs, trimmed of trailing punctuation by the matcher.
_URL_RE = re.compile(r"https?://[^\s\"'`<>)\]}]+")

# Credential-shape secret patterns. A match anywhere -> failing finding.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS temporary access key id"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
     "PEM private key block"),
    (re.compile(r"\bghp_[0-9A-Za-z]{36}\b"), "GitHub personal access token"),
    (re.compile(r"\bgho_[0-9A-Za-z]{36}\b"), "GitHub OAuth token"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), "Slack token"),
    (re.compile(r"\bsk-[0-9A-Za-z]{20,}\b"), "API secret key (sk-)"),
    (re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[0-9A-Za-z/+]{40}\b"),
     "AWS secret access key"),
]

# Trailing characters stripped from a captured URL (sentence/markdown punctuation).
_URL_TRAILING = ".,;:!?"


@dataclass
class Finding:
    """One gate observation: its severity, kind, human detail, and source file."""

    severity: Severity
    kind: str
    detail: str
    file: str


@dataclass
class GateResult:
    """The gate verdict: pass/fail plus findings and extracted commands/URLs."""

    passed: bool
    findings: list[Finding] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


def run_gate(
    changeset: ChangeSet,
    files: dict[str, str],
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> GateResult:
    """Run all deterministic security checks over `files`, returning a `GateResult`.

    `changeset` identifies the skill under scan (its name/subtree label findings);
    `files` maps each subtree-relative path to its content. `passed` is true iff no
    finding has `fail` severity.
    """
    findings: list[Finding] = []
    commands: list[str] = []
    urls: set[str] = set()

    for rel_path, content in files.items():
        findings.extend(_check_size(rel_path, content, max_file_bytes))
        file_commands = _extract_commands(content)
        commands.extend(file_commands)
        findings.extend(_check_high_risk(rel_path, file_commands))
        urls.update(_extract_urls(content))
        findings.extend(_scan_secrets(rel_path, content))

    findings.extend(_check_frontmatter(files))

    passed = not any(f.severity == "fail" for f in findings)
    return GateResult(
        passed=passed,
        findings=findings,
        commands=_dedupe(commands),
        urls=sorted(urls),
    )


def _check_size(rel_path: str, content: str, max_file_bytes: int) -> list[Finding]:
    """Flag a file whose UTF-8 byte length exceeds the configured cap as failing."""
    size = len(content.encode("utf-8"))
    if size <= max_file_bytes:
        return []
    return [
        Finding(
            severity="fail",
            kind="oversize",
            detail=f"{size} bytes exceeds cap of {max_file_bytes}",
            file=rel_path,
        )
    ]


def _check_frontmatter(files: dict[str, str]) -> list[Finding]:
    """Verify SKILL.md frontmatter parses as YAML and has `name` + `description`."""
    skill_md = _find_skill_md(files)
    if skill_md is None:
        return []
    rel_path, content = skill_md

    block = _frontmatter_block(content)
    if block is None:
        return [
            Finding(
                severity="fail",
                kind="frontmatter",
                detail="SKILL.md has no YAML frontmatter block",
                file=rel_path,
            )
        ]

    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return [
            Finding(
                severity="fail",
                kind="frontmatter",
                detail=f"frontmatter is not valid YAML: {exc}",
                file=rel_path,
            )
        ]

    if not isinstance(parsed, dict):
        return [
            Finding(
                severity="fail",
                kind="frontmatter",
                detail="frontmatter does not parse to a mapping",
                file=rel_path,
            )
        ]

    missing = [key for key in ("name", "description") if not parsed.get(key)]
    if missing:
        return [
            Finding(
                severity="fail",
                kind="frontmatter",
                detail=f"frontmatter missing required field(s): {', '.join(missing)}",
                file=rel_path,
            )
        ]
    return []


def _extract_commands(content: str) -> list[str]:
    """Pull candidate command lines from script files and fenced code blocks.

    For prose files, only lines inside fenced ``` blocks are considered; lines
    containing a known command token are surfaced. Extraction never fails the gate.
    """
    commands: list[str] = []
    for line in _command_candidate_lines(content):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lowered = stripped.lower()
        if any(token in lowered for token in _COMMAND_TOKENS):
            commands.append(stripped)
    return commands


def _command_candidate_lines(content: str) -> list[str]:
    """Return lines eligible for command scanning: fenced blocks plus shell-y prose."""
    lines: list[str] = []
    in_fence = False
    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        lines.append(line)
    return lines


def _check_high_risk(rel_path: str, commands: list[str]) -> list[Finding]:
    """Match extracted commands against the curated high-risk list -> failing findings."""
    findings: list[Finding] = []
    for command in commands:
        for pattern, reason in _HIGH_RISK_COMMANDS:
            if pattern.search(command):
                findings.append(
                    Finding(
                        severity="fail",
                        kind="high_risk_command",
                        detail=f"{reason}: {command}",
                        file=rel_path,
                    )
                )
                break
    return findings


def _extract_urls(content: str) -> set[str]:
    """Collect all http(s) URLs in `content`, stripped of trailing punctuation."""
    return {match.rstrip(_URL_TRAILING) for match in _URL_RE.findall(content)}


def _scan_secrets(rel_path: str, content: str) -> list[Finding]:
    """Flag any credential-shaped string as a failing secret finding."""
    findings: list[Finding] = []
    for pattern, label in _SECRET_PATTERNS:
        if pattern.search(content):
            findings.append(
                Finding(
                    severity="fail",
                    kind="secret",
                    detail=f"possible {label}",
                    file=rel_path,
                )
            )
    return findings


def _find_skill_md(files: dict[str, str]) -> tuple[str, str] | None:
    """Return the (path, content) of the skill's SKILL.md, or None if absent."""
    for rel_path, content in files.items():
        if rel_path == "SKILL.md" or rel_path.endswith("/SKILL.md"):
            return rel_path, content
    return None


def _frontmatter_block(content: str) -> str | None:
    """Extract the YAML text between the leading `---` fences, or None if absent."""
    if not content.startswith("---"):
        return None
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(body)
        body.append(line)
    return None


def _dedupe(items: list[str]) -> list[str]:
    """Return `items` with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
