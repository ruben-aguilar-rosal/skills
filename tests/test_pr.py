"""Tests for the PR output layer (`skillsync.pr`).

`build_pr` assembles a `SkillPR` (branch, title, body) from the upstream change,
the deterministic gate, the advisory verdict, and the adapt result — the body is
the human-review surface, so these tests assert it carries the RAW upstream diff,
the extracted commands/URLs, the advisory verdict, the sha bump, the adaptation
summary, and any flags. `publish_pr` drives a `GhPort`; the tests assert it issues
the branch -> commit -> open_pr calls in order via `FakeGh`, never touching real
`git`/`gh`.
"""

from skillsync.pr import SkillPR, build_pr, publish_pr
from skillsync.stages.adapt import AdaptResult
from skillsync.stages.detect import ChangeSet
from skillsync.stages.gate import Finding, GateResult
from skillsync.stages.llm_scan import AdvisoryVerdict
from skillsync.testing.fakes import FakeGh

RAW_DIFF = (
    "--- a/SKILL.md\n"
    "+++ b/SKILL.md\n"
    "@@\n"
    "-Create a GitHub issue from the selected notes.\n"
    "+Create a GitHub issue, then link it to a tracking epic.\n"
    "+Run: curl https://example.com/install.sh\n"
)


def _changeset(kind: str = "changed", rewritten: bool = False) -> ChangeSet:
    """A representative change set for the `to-issues` skill."""
    return ChangeSet(
        skill_path="engineering/to-issues",
        name="to-issues",
        kind=kind,  # type: ignore[arg-type]
        from_sha="a1b2c3d",
        to_sha="e4f5a6b",
        diff=RAW_DIFF,
        changed_files=["SKILL.md"],
        rewritten_history=rewritten,
    )


def _gate() -> GateResult:
    """A passing gate result with one extracted command and URL."""
    return GateResult(
        passed=True,
        findings=[Finding(severity="info", kind="note", detail="ok", file="SKILL.md")],
        commands=["curl https://example.com/install.sh"],
        urls=["https://example.com/install.sh"],
    )


def _advisory() -> AdvisoryVerdict:
    """A low-risk advisory verdict."""
    return AdvisoryVerdict(
        risk="low", rationale="no injection found", findings=[]
    )


def _adapt(flags: list[str] | None = None) -> AdaptResult:
    """An adapt result carrying optional review flags."""
    return AdaptResult(
        skill_md_text="# adapted",
        snapshot_text="# adapted",
        flags=flags or [],
    )


def test_branch_is_skillsync_prefixed_by_name() -> None:
    """The branch follows the `skillsync/<name>` convention from PLAN.md."""
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    assert skill_pr.branch == "skillsync/to-issues"


def test_body_contains_raw_upstream_diff() -> None:
    """The raw upstream diff is reproduced verbatim so adaptation can't launder it."""
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    assert RAW_DIFF.strip() in skill_pr.body


def test_body_contains_extracted_commands_and_urls() -> None:
    """The gate's extracted commands and URLs appear for explicit human review."""
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    assert "curl https://example.com/install.sh" in skill_pr.body
    assert "https://example.com/install.sh" in skill_pr.body


def test_body_contains_advisory_verdict() -> None:
    """The advisory risk and rationale are surfaced in the body."""
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    assert "low" in skill_pr.body
    assert "no injection found" in skill_pr.body


def test_body_contains_sha_bump() -> None:
    """The from->to sha bump is shown so the reviewer sees the sync point move."""
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    assert "a1b2c3d" in skill_pr.body
    assert "e4f5a6b" in skill_pr.body


def test_body_contains_adaptation_summary() -> None:
    """A change summary for adaptation.md is included."""
    skill_pr = build_pr(
        _changeset(), _gate(), _advisory(), _adapt(), adaptation_summary="folded in TP rule"
    )

    assert "folded in TP rule" in skill_pr.body


def test_body_contains_flags() -> None:
    """Adapt-result flags are surfaced loudly in the body for human attention."""
    flags = ["⚠ hand-edit may not be preserved"]
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt(flags=flags))

    assert "⚠ hand-edit may not be preserved" in skill_pr.body


def test_history_rewrite_is_flagged_in_body() -> None:
    """A re-onboard from a rewritten history is called out in the body."""
    skill_pr = build_pr(
        _changeset(kind="reonboard", rewritten=True), _gate(), _advisory(), _adapt()
    )

    assert "history" in skill_pr.body.lower()


def test_labels_include_advisory_risk() -> None:
    """High advisory risk produces a review label so the PR list shows the risk."""
    advisory = AdvisoryVerdict(risk="high", rationale="suspicious", findings=["x"])
    skill_pr = build_pr(_changeset(), _gate(), advisory, _adapt())

    assert any("high" in label for label in skill_pr.labels)


def test_publish_drives_gh_calls_in_order() -> None:
    """`publish_pr` issues create_branch -> commit_all -> open_pr in that order."""
    gh = FakeGh()
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    url = publish_pr(skill_pr, gh, root="/repo")  # type: ignore[arg-type]

    methods = [call.method for call in gh.calls]
    assert methods == ["create_branch", "commit_all", "open_pr"]
    assert url == "https://github.com/fake/skills/pull/skillsync/to-issues"


def test_publish_passes_branch_title_body_labels_to_open_pr() -> None:
    """The open_pr call receives the assembled branch, title, body, and labels."""
    gh = FakeGh()
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    publish_pr(skill_pr, gh, root="/repo")  # type: ignore[arg-type]

    open_call = next(c for c in gh.calls if c.method == "open_pr")
    _root, branch, title, body, labels = open_call.args
    assert branch == "skillsync/to-issues"
    assert title == skill_pr.title
    assert body == skill_pr.body
    assert labels == skill_pr.labels


def test_publish_creates_the_skillsync_branch() -> None:
    """The branch created matches the assembled `skillsync/<name>` branch."""
    gh = FakeGh()
    skill_pr = build_pr(_changeset(), _gate(), _advisory(), _adapt())

    publish_pr(skill_pr, gh, root="/repo")  # type: ignore[arg-type]

    create_call = next(c for c in gh.calls if c.method == "create_branch")
    assert create_call.args[1] == "skillsync/to-issues"
