"""In-memory fakes for skillsync ports.

`FakeGit` backs `GitPort` with a linear commit history and per-commit content
snapshots, enough to exercise the ancestor/diff/listing logic the deterministic
stages rely on — without touching disk or the network. `FakeLLM` backs `LLMPort`
with scripted, deterministic responses keyed by a prompt substring, recording
every call so agentic stages can be tested without invoking real `claude`.
"""

import difflib
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from skillsync.ports.git import GitError
from skillsync.ports.llm import LLMError, LLMResult
from skillsync.ports.scanner import ScanError
from skillsync.stages.gate import Finding, GateResult
from skillsync.subtree import subtree_prefix

_EMPTY_TREE = "<empty>"


class FakeGit:
    """`GitPort` backed by `{sha: {path: content}}` and a linear history."""

    def __init__(self) -> None:
        """Start with an empty history, no commits, and no refs."""
        self._history: list[str] = []
        self._snapshots: dict[str, dict[str, str | bytes]] = {}
        self._refs: dict[str, str] = {}

    def add_commit(self, sha: str, files: dict[str, str | bytes]) -> None:
        """Append a commit `sha` with a full file snapshot to the linear history."""
        if sha in self._snapshots:
            raise ValueError(f"duplicate commit sha: {sha}")
        self._history.append(sha)
        self._snapshots[sha] = dict(files)

    def set_ref(self, name: str, sha: str) -> None:
        """Point ref `name` at an existing commit `sha`."""
        if sha not in self._snapshots:
            raise ValueError(f"unknown commit sha: {sha}")
        self._refs[name] = sha

    def mirror(self, repo: str, ref: str) -> Path:
        """Return a synthetic checkout path; no I/O is performed."""
        self.head_sha(Path("/fake"), ref)  # validate the ref exists
        return Path("/fake/mirrors") / repo.replace("/", "__")

    def remote_head(self, repo: str, ref: str) -> str:
        """Resolve `ref` to a SHA without 'fetching' — same source as `head_sha`."""
        return self._resolve(ref)

    def head_sha(self, repo_path: Path, ref: str) -> str:
        """Resolve `ref` (a ref name or a known sha) to a commit SHA."""
        return self._resolve(ref)

    def is_ancestor(self, repo_path: Path, ancestor_sha: str, ref: str) -> bool:
        """Return True if `ancestor_sha` precedes `ref` in the linear history."""
        ancestor = self._resolve(ancestor_sha)
        target = self._resolve(ref)
        return self._history.index(ancestor) <= self._history.index(target)

    def diff_subtree(
        self, repo_path: Path, from_sha: str | None, ref: str, subtree: str
    ) -> str:
        """Unified diff of `subtree` from `from_sha` (or nothing) to `ref`."""
        old = {} if from_sha is None else self._subtree_files(self._resolve(from_sha), subtree)
        new = self._subtree_files(self._resolve(ref), subtree)

        chunks: list[str] = []
        for path in sorted(set(old) | set(new)):
            old_lines = old.get(path, "").splitlines(keepends=True)
            new_lines = new.get(path, "").splitlines(keepends=True)
            if old_lines == new_lines:
                continue
            from_label = "/dev/null" if path not in old else f"a/{path}"
            to_label = "/dev/null" if path not in new else f"b/{path}"
            chunks.extend(
                difflib.unified_diff(
                    old_lines, new_lines, fromfile=from_label, tofile=to_label
                )
            )
        return "".join(chunks)

    def list_subtree_files(self, repo_path: Path, ref: str, subtree: str) -> list[str]:
        """List subtree-relative file paths present under `subtree` at `ref`."""
        return sorted(self._subtree_files(self._resolve(ref), subtree))

    def read_subtree_files(
        self, repo_path: Path, ref: str, subtree: str
    ) -> dict[str, str | bytes]:
        """Return `{subtree-relative-path: content}` for files under `subtree` at `ref`."""
        return self._subtree_files(self._resolve(ref), subtree)

    def _resolve(self, ref: str) -> str:
        """Resolve a ref name or raw sha to a known commit sha, or raise GitError."""
        if ref in self._refs:
            return self._refs[ref]
        if ref in self._snapshots:
            return ref
        raise GitError(f"unknown ref or sha: {ref}")

    def _subtree_files(self, sha: str, subtree: str) -> dict[str, str | bytes]:
        """Return `{subtree-relative-path: content}` for files under `subtree` at `sha`."""
        prefix = subtree_prefix(subtree)
        return {
            path[len(prefix) :]: content
            for path, content in self._snapshots[sha].items()
            if path.startswith(prefix)
        }


@dataclass(frozen=True)
class LLMCall:
    """A single recorded `FakeLLM.complete` invocation."""

    prompt: str
    model: str
    temperature: float
    schema: dict | None


class FakeLLM:
    """`LLMPort` backed by scripted responses keyed by a prompt substring.

    Each key is a substring; the first key found in the prompt selects the
    scripted `LLMResult`. When a schema is supplied at call time, the scripted
    result's `json` payload is validated against it, mirroring `ClaudeCli`.
    """

    def __init__(self, responses: dict[str, LLMResult] | None = None) -> None:
        """Seed scripted `{prompt-substring: LLMResult}` responses; start empty otherwise."""
        self._responses: dict[str, LLMResult] = dict(responses or {})
        self.calls: list[LLMCall] = []

    def complete(
        self,
        prompt: str,
        *,
        schema: dict | None,
        model: str,
        temperature: float,
    ) -> LLMResult:
        """Return the scripted result for the first matching substring key."""
        self.calls.append(LLMCall(prompt, model, temperature, schema))

        result = self._match(prompt)
        if result is None:
            raise LLMError(f"no scripted FakeLLM response matches prompt: {prompt!r}")

        if schema is not None:
            try:
                jsonschema.validate(result.json, schema)
            except jsonschema.ValidationError as exc:
                raise LLMError(
                    f"scripted FakeLLM payload failed schema validation: {exc}"
                ) from exc

        return result

    def _match(self, prompt: str) -> LLMResult | None:
        """Return the scripted result whose key is a substring of `prompt`."""
        for key, result in self._responses.items():
            if key in prompt:
                return result
        return None


@dataclass(frozen=True)
class GhCall:
    """A single recorded `FakeGh` invocation: the method name and its arguments."""

    method: str
    args: tuple


class FakeGh:
    """`GhPort` that records every call in order without touching git or gh.

    `open_pr` returns a synthetic, deterministic URL derived from the branch name.
    `calls` preserves invocation order so tests can assert the
    branch -> commit -> open_pr sequence the PR layer must drive. Opened issues are
    remembered by title so `find_issue` can report a duplicate, mirroring the real
    `GhCli`'s idempotent awareness-issue behaviour.
    """

    def __init__(self, branch: str = "main", pr_url: str | None = None) -> None:
        """Seed the reported current branch and an optional fixed PR URL."""
        self._branch = branch
        self._pr_url = pr_url
        self._issues: dict[str, str] = {}
        self.calls: list[GhCall] = []

    def current_branch(self, root: Path) -> str:
        """Record the call and return the seeded current-branch name."""
        self.calls.append(GhCall("current_branch", (root,)))
        return self._branch

    def create_branch(self, root: Path, name: str) -> None:
        """Record the branch creation and adopt `name` as the current branch."""
        self.calls.append(GhCall("create_branch", (root, name)))
        self._branch = name

    def commit_all(self, root: Path, message: str) -> None:
        """Record the commit and its message."""
        self.calls.append(GhCall("commit_all", (root, message)))

    def open_pr(
        self,
        root: Path,
        branch: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> str:
        """Record the PR open and return a synthetic deterministic PR URL."""
        self.calls.append(GhCall("open_pr", (root, branch, title, body, list(labels))))
        return self._pr_url or f"https://github.com/fake/skills/pull/{branch}"

    def open_issue(
        self, root: Path, title: str, body: str, labels: list[str]
    ) -> str:
        """Record the issue open and return a synthetic deterministic issue URL."""
        self.calls.append(GhCall("open_issue", (root, title, body, list(labels))))
        url = f"https://github.com/fake/skills/issues/{len(self.calls)}"
        self._issues[title] = url
        return url

    def find_issue(self, root: Path, title: str) -> str | None:
        """Record the lookup and return the URL of a previously-opened issue, if any."""
        self.calls.append(GhCall("find_issue", (root, title)))
        return self._issues.get(title)


# SkillSpector severity → skillsync `Finding` severity, mirroring `SkillSpectorCli`.
_SCAN_SEVERITY_MAP = {"CRITICAL": "fail", "HIGH": "fail", "MEDIUM": "warn", "LOW": "info"}


class FakeScanner:
    """`ScannerPort` returning a scripted `GateResult` (or raising a scripted error).

    Records the files present in the scanned directory at call time so tests can
    assert the subtree was materialized. `from_issues` builds the result from
    SkillSpector-shaped `issues[]`, mapping severities exactly as `SkillSpectorCli`
    does, so a test can drive the same blocking logic without the real binary.
    """

    def __init__(
        self, result: GateResult | None = None, *, error: ScanError | None = None
    ) -> None:
        """Seed the scripted scan `result`, or an `error` to raise on scan."""
        self._result = result if result is not None else GateResult(passed=True)
        self._error = error
        self.scanned_files: dict[str, str] = {}

    @classmethod
    def from_issues(
        cls, *, issues: list[dict], score: int = 0, severity: str = "LOW"
    ) -> "FakeScanner":
        """Build a scanner whose result maps SkillSpector-shaped `issues[]` to findings."""
        findings = [
            Finding(
                severity=_SCAN_SEVERITY_MAP.get(
                    str(issue.get("severity", "LOW")).upper(), "info"
                ),
                kind=str(issue.get("id") or "skillspector"),
                detail=f"[{issue.get('severity')}] {issue.get('explanation', '')}",
                file=str((issue.get("location") or {}).get("file") or "SKILL.md"),
            )
            for issue in issues
        ]
        passed = not any(f.severity == "fail" for f in findings)
        return cls(GateResult(passed=passed, findings=findings))

    def scan(self, skill_dir: Path) -> GateResult:
        """Record the directory's files and return the scripted result (or raise)."""
        self.scanned_files = {
            path.relative_to(skill_dir).as_posix(): path.read_text()
            for path in sorted(skill_dir.rglob("*"))
            if path.is_file()
        }
        if self._error is not None:
            raise self._error
        return self._result
