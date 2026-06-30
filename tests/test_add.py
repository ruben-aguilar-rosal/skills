"""Tests for the ADD (onboarding) command (`skillsync.commands.add`).

`run_add` onboards a brand-new upstream skill end-to-end, driving the injected
`FakeGit` + `FakeLLM` + `FakeGh` so no real git/claude/gh is touched. These tests
cover the onboarding outcome matrix:

- **happy path** → the pin is appended to sources.yaml (synced_sha bumped to HEAD
  only on success), a self-contained `adaptation.md` is DRAFTED from `profile.md`
  (baked in verbatim) plus the upstream SKILL.md, the first `SKILL.md` is generated
  in FULL mode, validated, and shipped as a PR labelled `onboarding`;
- **gate fail** → the skill is QUARANTINED before any agent reads upstream (issue,
  no draft, no generation, no PR), and the pin is left unsynced;
- **validate fail** → an issue is opened, no PR, nothing is written, pin unsynced.
"""

from pathlib import Path

from skillsync.commands.add import (
    AddOutcome,
    _invalid_body,
    _quarantine_body,
    run_add,
)
from skillsync.config import Config, SkillPin, Source, load_config
from skillsync.layout import SkillLayout, read_text
from skillsync.ports.llm import LLMResult
from skillsync.stages.gate import GateResult
from skillsync.testing.fakes import FakeGh, FakeGit, FakeLLM, FakeScanner


def _clean() -> FakeScanner:
    """A scanner that passes (no findings); the gate is exercised in its own tests."""
    return FakeScanner(GateResult(passed=True, findings=[]))


def _critical_scanner() -> FakeScanner:
    """A scanner returning a CRITICAL finding (quarantines the onboarding)."""
    return FakeScanner.from_issues(
        score=60,
        severity="CRITICAL",
        issues=[
            {
                "id": "PI-001",
                "severity": "CRITICAL",
                "location": {"file": "SKILL.md"},
                "explanation": "embedded prompt injection",
            }
        ],
    )

# --- Scripted LLM substring keys (unique to each stage's prompt template) -------
_ADVISORY_KEY = "security reviewer auditing"
_DRAFT_KEY = "drafting a self-contained"
_FULL_KEY = "from scratch"

# A clean upstream SKILL.md (valid frontmatter, no secrets / high-risk commands).
_UPSTREAM = (
    "---\nname: demo\ndescription: Turn notes into issues.\n---\n\n"
    "# demo\nCreate a GitHub issue from the selected notes.\n"
)

# The author profile, baked verbatim into the drafted adaptation.md.
_PROFILE = "Use Jira project TP. AWS profile aws-infrastructure. Terse tone.\n"

# What the draft LLM call "returns": a self-contained adaptation.md.
_DRAFTED_ADAPTATION = (
    "Use Jira project TP. AWS profile aws-infrastructure. Terse tone.\n\n"
    "Adapt issue creation to file Jira issues in project TP.\n"
)

# A valid full-generated SKILL.md — frontmatter name matches the skill folder.
_ADAPTED_VALID = (
    "---\nname: demo\ndescription: Turn notes into Jira issues.\n---\n\n"
    "# demo\nFile a Jira issue in project TP from the selected notes.\n"
)

# An invalid full-generated SKILL.md: frontmatter name does not match the folder.
_ADAPTED_INVALID = (
    "---\nname: wrong\ndescription: Bad.\n---\n\n# demo\nDo the thing.\n"
)


def _advisory(risk: str = "low") -> LLMResult:
    """A scripted advisory-scan verdict."""
    return LLMResult(text="{}", json={"risk": risk, "rationale": "clean", "findings": []})


def _draft(adaptation_md: str = _DRAFTED_ADAPTATION) -> LLMResult:
    """A scripted adaptation.md draft result."""
    return LLMResult(text="{}", json={"adaptation_md": adaptation_md})


def _full(skill_md: str) -> LLMResult:
    """A scripted full-mode adapt result returning `skill_md`."""
    return LLMResult(text="{}", json={"skill_md": skill_md})


def _git(skill_md: str = _UPSTREAM) -> FakeGit:
    """A FakeGit with one commit holding `skills/demo`; `main` points at it."""
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": skill_md})
    git.set_ref("main", "sha1")
    return git


def _write_profile(root: Path) -> None:
    """Write the author profile.md the draft step bakes in verbatim."""
    (root / "profile.md").write_text(_PROFILE)


def _pin(config: Config, path: str = "skills/demo") -> SkillPin:
    """Return the pin for `path` across all sources, or raise if absent."""
    for source in config.sources:
        for pin in source.skills:
            if pin.path == path:
                return pin
    raise AssertionError(f"no pin for {path}")


# --- vendor by default (no adaptation) ------------------------------------------


def test_add_vendors_verbatim_without_llm(tmp_path: Path) -> None:
    """Plain `add` vendors the upstream SKILL.md verbatim — no LLM, no adaptation.md."""
    config = Config(sources=[])
    git = _git()
    llm = FakeLLM({})  # any LLM call would raise — none should happen
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=git, llm=llm, gh=gh, scanner=_clean()
    )

    assert outcome.status == "pr"
    assert llm.calls == []  # vendoring never touches the LLM
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    # SKILL.md is the upstream copied verbatim; the mirror holds it too.
    assert read_text(layout.skill_md_path) == _UPSTREAM
    assert read_text(layout.upstream_dir / "SKILL.md") == _UPSTREAM
    # No adaptation.md and no generated snapshot were written (adaptation is opt-in).
    assert read_text(layout.adaptation_path) is None
    assert read_text(layout.generated_skill_md_path) is None
    # The pin still lands and bumps to HEAD on success.
    assert _pin(config).synced_sha == "sha1"


def test_add_vendor_pr_is_labelled_vendored(tmp_path: Path) -> None:
    """A vendored onboarding PR carries a `vendored` label, not `onboarding`."""
    config = Config(sources=[])
    gh = FakeGh()

    run_add(config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=FakeLLM({}), gh=gh, scanner=_clean())

    labels = next(c for c in gh.calls if c.method == "open_pr").args[4]
    assert "vendored" in labels


def test_add_vendor_copies_ship_along_scripts(tmp_path: Path) -> None:
    """A vendored skill's scripts land beside SKILL.md, not only in the .upstream mirror."""
    config = Config(sources=[])
    git = FakeGit()
    git.add_commit(
        "sha1",
        {
            "skills/demo/SKILL.md": _UPSTREAM,
            "skills/demo/scripts/run.py": "print('go')\n",
        },
    )
    git.set_ref("main", "sha1")

    run_add(config, tmp_path, "owner/repo", "skills/demo", git=git, llm=FakeLLM({}), gh=FakeGh(), scanner=_clean())

    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    # The script the skill ships sits in the skill folder root (so the link works)...
    assert read_text(layout.root / "scripts" / "run.py") == "print('go')\n"
    # ...and also in the pristine .upstream mirror (the security surface).
    assert read_text(layout.upstream_dir / "scripts" / "run.py") == "print('go')\n"


def test_add_no_pr_writes_locally_without_a_pr(tmp_path: Path) -> None:
    """`open_pr=False` vendors the skill to the working tree and opens no PR."""
    config = Config(sources=[])
    git = _git()
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=git, llm=FakeLLM({}), gh=gh, scanner=_clean(),
        open_pr=False,
    )

    assert outcome.status == "local"
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    # The skill landed in the working tree...
    assert read_text(layout.skill_md_path) == _UPSTREAM
    # ...the pin bumped...
    assert _pin(config).synced_sha == "sha1"
    # ...but git/GitHub was never touched.
    assert gh.calls == []


def test_add_no_pr_adapt_writes_locally(tmp_path: Path) -> None:
    """`open_pr=False` with `--adapt` generates locally and opens no PR."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=gh, scanner=_clean(),
        adapt=True, open_pr=False,
    )

    assert outcome.status == "local"
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    assert read_text(layout.skill_md_path) == _ADAPTED_VALID
    assert read_text(layout.adaptation_path) == _DRAFTED_ADAPTATION
    assert gh.calls == []


def test_add_vendor_still_quarantines_on_gate_fail(tmp_path: Path) -> None:
    """Vendoring still runs the security gate — a CRITICAL finding quarantines, no PR."""
    config = Config(sources=[])
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=FakeLLM({}), gh=gh,
        scanner=_critical_scanner(),
    )

    assert outcome.status == "quarantined"
    assert not any(c.method == "open_pr" for c in gh.calls)


# --- happy path (--adapt) -------------------------------------------------------


def test_add_onboards_and_opens_pr(tmp_path: Path) -> None:
    """`add --adapt` drafts adaptation.md, full-generates, validates, opens a PR."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    git = _git()
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=git, llm=llm, gh=gh, adapt=True, scanner=_clean()
    )

    assert isinstance(outcome, AddOutcome)
    assert outcome.status == "pr"
    assert outcome.url is not None
    assert any(c.method == "open_pr" for c in gh.calls)


def test_add_appends_pin_and_bumps_sha_on_success(tmp_path: Path) -> None:
    """The pin lands in sources.yaml and its synced_sha moves to HEAD only on success."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )

    run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=FakeGh(), adapt=True, scanner=_clean()
    )

    # The in-memory config gained the pin, bumped to the upstream HEAD.
    pin = _pin(config)
    assert pin.synced_sha == "sha1"
    # ...and it was persisted to sources.yaml on disk.
    reloaded = load_config(tmp_path / "sources.yaml")
    assert reloaded.sources[0].repo == "owner/repo"
    assert _pin(reloaded).synced_sha == "sha1"


def test_add_drafts_adaptation_from_profile_and_upstream(tmp_path: Path) -> None:
    """The draft prompt bakes profile.md in verbatim and reads the upstream SKILL.md."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )

    run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=FakeGh(), adapt=True, scanner=_clean()
    )

    draft_call = next(c for c in llm.calls if _DRAFT_KEY in c.prompt)
    # profile.md content is baked into the draft prompt verbatim...
    assert "Use Jira project TP." in draft_call.prompt
    # ...alongside the upstream SKILL.md the draft is derived from.
    assert "Create a GitHub issue from the selected notes." in draft_call.prompt
    # The drafted adaptation.md is written to disk.
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    assert read_text(layout.adaptation_path) == _DRAFTED_ADAPTATION


def test_add_full_generates_validates_and_writes_artifacts(tmp_path: Path) -> None:
    """Full-mode generation produces SKILL.md; mirror, snapshot, and adaptation are written."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )

    run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=FakeGh(), adapt=True, scanner=_clean()
    )

    # Full-mode (not patch) generation was used.
    assert any(_FULL_KEY in c.prompt for c in llm.calls)
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    assert read_text(layout.skill_md_path) == _ADAPTED_VALID
    assert read_text(layout.generated_skill_md_path) == _ADAPTED_VALID
    # The whole upstream subtree is mirrored verbatim.
    assert read_text(layout.upstream_dir / "SKILL.md") == _UPSTREAM


def test_add_pr_carries_onboarding_label(tmp_path: Path) -> None:
    """The onboarding PR is labelled `onboarding` for the PR list."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )
    gh = FakeGh()

    run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=gh, adapt=True, scanner=_clean()
    )

    open_pr = next(c for c in gh.calls if c.method == "open_pr")
    labels = open_pr.args[4]
    assert "onboarding" in labels


def test_add_creates_new_source_when_repo_absent(tmp_path: Path) -> None:
    """An onboarding for an unseen repo creates a fresh Source carrying the new pin."""
    config = Config(
        sources=[Source(repo="other/repo", ref="main", skills=[])]
    )
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_VALID)}
    )

    run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=FakeGh(), adapt=True, scanner=_clean()
    )

    repos = {source.repo for source in config.sources}
    assert repos == {"other/repo", "owner/repo"}
    assert _pin(config).synced_sha == "sha1"


# --- gate fail -> quarantine ----------------------------------------------------


def test_add_gate_fail_quarantines_before_drafting(tmp_path: Path) -> None:
    """A CRITICAL scanner finding quarantines the skill before any LLM call is made."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM({})  # any LLM call would raise — none should happen
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=gh,
        scanner=_critical_scanner(),
    )

    assert outcome.status == "quarantined"
    assert outcome.url is not None
    assert any(c.method == "open_issue" for c in gh.calls)
    assert not any(c.method == "open_pr" for c in gh.calls)
    # The gate ran BEFORE any agent: neither advisory nor draft was invoked.
    assert llm.calls == []
    # The pin is registered but left unsynced; no adaptation.md was drafted.
    assert _pin(config).synced_sha is None
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    assert read_text(layout.adaptation_path) is None


# --- validate fail -> no PR + issue ---------------------------------------------


def test_add_validate_fail_emits_issue_and_no_pr(tmp_path: Path) -> None:
    """A full-generated SKILL.md that fails validation blocks the PR and opens an issue."""
    config = Config(sources=[])
    _write_profile(tmp_path)
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _DRAFT_KEY: _draft(), _FULL_KEY: _full(_ADAPTED_INVALID)}
    )
    gh = FakeGh()

    outcome = run_add(
        config, tmp_path, "owner/repo", "skills/demo", git=_git(), llm=llm, gh=gh, adapt=True, scanner=_clean()
    )

    assert outcome.status == "invalid"
    assert any(c.method == "open_issue" for c in gh.calls)
    assert not any(c.method == "open_pr" for c in gh.calls)
    # No PR -> the pin stays unsynced and nothing was written to the skill folder.
    assert _pin(config).synced_sha is None
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    assert read_text(layout.skill_md_path) is None


def _huge_changeset() -> "ChangeSet":
    """A change set whose diff dwarfs GitHub's 64KB issue-body cap."""
    from skillsync.stages.detect import ChangeSet

    return ChangeSet(
        skill_path="skills/demo",
        name="demo",
        kind="reonboard",
        from_sha=None,
        to_sha="abc",
        diff="x" * 200_000,
    )


def test_invalid_body_stays_under_github_limit() -> None:
    """A skill with a giant diff yields an issue body within GitHub's 64KB cap."""
    body = _invalid_body(_huge_changeset(), ["referenced file does not exist: a.py"])

    assert len(body) < 65_536
    assert "truncated" in body


def test_quarantine_body_stays_under_github_limit() -> None:
    """The quarantine body also truncates the embedded diff under the cap."""
    body = _quarantine_body(_huge_changeset(), GateResult(passed=False))

    assert len(body) < 65_536
    assert "truncated" in body
