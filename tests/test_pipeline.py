"""Tests for the end-to-end SYNC pipeline (`skillsync.pipeline`).

`run_sync` wires the whole pipeline together — detect → gate → advisory →
reconcile → adapt → verify → validate → PR — over each changed skill, driving the
injected `FakeGit` + `FakeLLM` + `FakeGh` so no real git/claude/gh is touched.

These tests cover the full outcome matrix:

- **clean change** → a PR is opened and the pin's `synced_sha` is bumped;
- **gate fail** → the skill is QUARANTINED (issue opened, no adapt, sha unchanged);
- **validate fail** → NO PR, an issue is opened, sha unchanged;
- **drift + change** → fold-back and preservation-verify run on the way to a PR;
- **reonboard** → full-mode generation rather than a patch.

The load-bearing invariant asserted throughout: a pin's `synced_sha` moves ONLY
when a PR is successfully published.
"""

from pathlib import Path

from skillsync.config import Config, SkillPin, Source
from skillsync.layout import SkillLayout, read_text, write_text
from skillsync.pipeline import SyncOutcome, run_sync
from skillsync.ports.llm import LLMResult
from skillsync.testing.fakes import FakeGh, FakeGit, FakeLLM

# --- Scripted LLM substring keys (unique to each stage's prompt template) -------
_ADVISORY_KEY = "security reviewer auditing"
_PATCH_KEY = "Apply the SEMANTIC EQUIVALENT"
_FULL_KEY = "from scratch"
_FOLDBACK_KEY = "fold its INTENT"
_VERIFY_KEY = "Confirm whether the INTENT"

# A clean upstream SKILL.md (valid frontmatter, no secrets / high-risk commands).
_UPSTREAM_OLD = "---\nname: demo\ndescription: An old demo.\n---\n\nOld body line.\n"
_UPSTREAM_NEW = "---\nname: demo\ndescription: A new demo.\n---\n\nNew body line.\n"

# A valid adapted SKILL.md the LLM "returns" — name matches the skill folder.
_ADAPTED_VALID = "---\nname: demo\ndescription: A demo skill.\n---\n\n# demo\nDo the thing.\n"

# An invalid adapted SKILL.md: frontmatter name does not match the folder.
_ADAPTED_INVALID = "---\nname: wrong\ndescription: Bad.\n---\n\n# demo\nDo the thing.\n"


def _advisory(risk: str = "low") -> LLMResult:
    """A scripted advisory-scan verdict."""
    return LLMResult(text="{}", json={"risk": risk, "rationale": "clean", "findings": []})


def _adapt(skill_md: str) -> LLMResult:
    """A scripted adapt result returning `skill_md`."""
    return LLMResult(text="{}", json={"skill_md": skill_md})


def _foldback(new_adaptation: str) -> LLMResult:
    """A scripted fold-back result enriching the adaptation rules."""
    return LLMResult(
        text="{}",
        json={"new_adaptation_text": new_adaptation, "summary": "folded the hand-edit in"},
    )


def _verify(preserved: bool) -> LLMResult:
    """A scripted preservation verdict."""
    return LLMResult(text="{}", json={"preserved": preserved, "note": "checked"})


def _config(synced_sha: str | None) -> Config:
    """A single-source config pinning `skills/demo` at `synced_sha`."""
    return Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[SkillPin(path="skills/demo", synced_sha=synced_sha)],
            )
        ]
    )


def _changed_git() -> FakeGit:
    """A FakeGit with two commits touching `skills/demo`; `main` at the newer one."""
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": _UPSTREAM_OLD})
    git.add_commit("sha2", {"skills/demo/SKILL.md": _UPSTREAM_NEW})
    git.set_ref("main", "sha2")
    return git


def _pin(config: Config) -> SkillPin:
    """The single demo pin in `config`."""
    return config.sources[0].skills[0]


# --- clean change -> PR ---------------------------------------------------------


def test_clean_change_opens_pr_and_bumps_sha(tmp_path: Path) -> None:
    """A clean upstream change is adapted, validated, and shipped as a PR."""
    config = _config(synced_sha="sha1")
    git = _changed_git()
    # Seed an existing committed SKILL.md so patch mode has something to edit.
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    write_text(layout.skill_md_path, _UPSTREAM_OLD)
    write_text(layout.adaptation_path, "Target the TP project.")
    llm = FakeLLM(
        {_ADVISORY_KEY: _advisory(), _PATCH_KEY: _adapt(_ADAPTED_VALID)}
    )
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert isinstance(outcome, SyncOutcome)
    assert outcome.status == "pr"
    assert outcome.url is not None
    # The sync point moved to the new sha only because a PR was opened.
    assert _pin(config).synced_sha == "sha2"
    assert any(c.method == "open_pr" for c in gh.calls)


def test_clean_change_writes_mirror_skill_and_snapshot(tmp_path: Path) -> None:
    """On success the upstream mirror, SKILL.md, and `.generated` snapshot are written."""
    config = _config(synced_sha="sha1")
    git = _changed_git()
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    write_text(layout.skill_md_path, _UPSTREAM_OLD)
    llm = FakeLLM({_ADVISORY_KEY: _advisory(), _PATCH_KEY: _adapt(_ADAPTED_VALID)})

    run_sync(config, tmp_path, git=git, llm=llm, gh=FakeGh())

    assert read_text(layout.skill_md_path) == _ADAPTED_VALID
    assert read_text(layout.generated_skill_md_path) == _ADAPTED_VALID
    # The whole upstream subtree is mirrored verbatim.
    assert read_text(layout.upstream_dir / "SKILL.md") == _UPSTREAM_NEW


def test_no_change_is_skipped(tmp_path: Path) -> None:
    """A skill with no upstream change is skipped and never reaches the LLM."""
    config = _config(synced_sha="sha2")  # already at HEAD -> kind none
    git = _changed_git()
    llm = FakeLLM({})  # any LLM call would raise
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert [o.status for o in outcomes] == ["skipped"]
    assert llm.calls == []
    assert gh.calls == []
    assert _pin(config).synced_sha == "sha2"


# --- gate fail -> quarantine ----------------------------------------------------


def test_gate_fail_quarantines_without_adapting(tmp_path: Path) -> None:
    """A secret in the upstream change quarantines the skill: issue, no PR, no sha bump."""
    config = _config(synced_sha="sha1")
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": _UPSTREAM_OLD})
    # The new revision smuggles an AWS access key id -> deterministic gate FAIL.
    poisoned = _UPSTREAM_NEW + "\nAKIAIOSFODNN7EXAMPLE\n"
    git.add_commit("sha2", {"skills/demo/SKILL.md": poisoned})
    git.set_ref("main", "sha2")
    llm = FakeLLM({})  # no adapt/advisory should be called on a quarantine
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert [o.status for o in outcomes] == ["quarantined"]
    assert outcomes[0].url is not None  # an issue was opened
    assert any(c.method == "open_issue" for c in gh.calls)
    assert not any(c.method == "open_pr" for c in gh.calls)
    # No adaptation happened — the LLM was never invoked.
    assert llm.calls == []
    # The skill stays pinned at the OLD sha.
    assert _pin(config).synced_sha == "sha1"


# --- validate fail -> no PR + issue ---------------------------------------------


def test_validate_fail_emits_issue_and_no_pr(tmp_path: Path) -> None:
    """An adapted SKILL.md that fails validation blocks the PR and opens an issue."""
    config = _config(synced_sha="sha1")
    git = _changed_git()
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    write_text(layout.skill_md_path, _UPSTREAM_OLD)
    # The adapt step returns a SKILL.md whose name does not match the folder.
    llm = FakeLLM({_ADVISORY_KEY: _advisory(), _PATCH_KEY: _adapt(_ADAPTED_INVALID)})
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert [o.status for o in outcomes] == ["invalid"]
    assert any(c.method == "open_issue" for c in gh.calls)
    assert not any(c.method == "open_pr" for c in gh.calls)
    # No PR -> the sync point does not move.
    assert _pin(config).synced_sha == "sha1"
    # The invalid output was NOT written over the committed SKILL.md.
    assert read_text(layout.skill_md_path) == _UPSTREAM_OLD


# --- drift + change -> fold_back + verify ---------------------------------------


def test_drift_triggers_foldback_and_verify(tmp_path: Path) -> None:
    """A hand-edit drift folds back into adaptation.md and is preservation-verified."""
    config = _config(synced_sha="sha1")
    git = _changed_git()
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    # Snapshot != committed -> drift exists to fold back.
    write_text(layout.generated_skill_md_path, _UPSTREAM_OLD)
    write_text(
        layout.skill_md_path,
        _UPSTREAM_OLD + "Always link the issue to its tracking epic.\n",
    )
    write_text(layout.adaptation_path, "Target the TP project.")
    enriched = "Target the TP project.\n\nAlways link issues to their epic.\n"
    llm = FakeLLM(
        {
            _ADVISORY_KEY: _advisory(),
            _FOLDBACK_KEY: _foldback(enriched),
            _PATCH_KEY: _adapt(_ADAPTED_VALID),
            _VERIFY_KEY: _verify(preserved=True),
        }
    )
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert outcomes[0].status == "pr"
    # Fold-back and preservation-verify both ran.
    prompts = [c.prompt for c in llm.calls]
    assert any(_FOLDBACK_KEY in p for p in prompts)
    assert any(_VERIFY_KEY in p for p in prompts)
    # The enriched adaptation rules were written back on success.
    assert read_text(layout.adaptation_path) == enriched
    assert _pin(config).synced_sha == "sha2"


def test_non_preserved_handedit_flags_pr_but_still_ships(tmp_path: Path) -> None:
    """A non-preserved hand-edit adds a review flag but does not block the PR."""
    config = _config(synced_sha="sha1")
    git = _changed_git()
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    write_text(layout.generated_skill_md_path, _UPSTREAM_OLD)
    write_text(layout.skill_md_path, _UPSTREAM_OLD + "A hand-edited line.\n")
    write_text(layout.adaptation_path, "rules")
    llm = FakeLLM(
        {
            _ADVISORY_KEY: _advisory(),
            _FOLDBACK_KEY: _foldback("rules\n\nmore"),
            _PATCH_KEY: _adapt(_ADAPTED_VALID),
            _VERIFY_KEY: _verify(preserved=False),
        }
    )
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert outcomes[0].status == "pr"
    open_pr = next(c for c in gh.calls if c.method == "open_pr")
    body = open_pr.args[3]
    assert "hand-edit" in body.lower()
    assert _pin(config).synced_sha == "sha2"


# --- reonboard -> full mode -----------------------------------------------------


def test_reonboard_uses_full_generation(tmp_path: Path) -> None:
    """A first onboarding (no synced_sha) generates in FULL mode and opens a PR."""
    config = _config(synced_sha=None)  # never synced -> reonboard
    git = _changed_git()
    # Full mode keys on the full-generation prompt, not the patch prompt.
    llm = FakeLLM({_ADVISORY_KEY: _advisory(), _FULL_KEY: _adapt(_ADAPTED_VALID)})
    gh = FakeGh()

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=gh)

    assert outcomes[0].status == "pr"
    # The full-generation prompt was used (no committed SKILL.md to patch).
    assert any(_FULL_KEY in c.prompt for c in llm.calls)
    assert _pin(config).synced_sha == "sha2"


# --- only filter ----------------------------------------------------------------


def test_only_filters_to_one_skill(tmp_path: Path) -> None:
    """`only` restricts the run to the named skill; others are not processed."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path="skills/demo", synced_sha="sha1"),
                    SkillPin(path="skills/other", synced_sha="sha1"),
                ],
            )
        ]
    )
    git = FakeGit()
    git.add_commit(
        "sha1",
        {"skills/demo/SKILL.md": _UPSTREAM_OLD, "skills/other/SKILL.md": _UPSTREAM_OLD},
    )
    git.add_commit(
        "sha2",
        {"skills/demo/SKILL.md": _UPSTREAM_NEW, "skills/other/SKILL.md": _UPSTREAM_NEW},
    )
    git.set_ref("main", "sha2")
    layout = SkillLayout.resolve(tmp_path, "skills/demo")
    write_text(layout.skill_md_path, _UPSTREAM_OLD)
    llm = FakeLLM({_ADVISORY_KEY: _advisory(), _PATCH_KEY: _adapt(_ADAPTED_VALID)})

    outcomes = run_sync(config, tmp_path, git=git, llm=llm, gh=FakeGh(), only="demo")

    assert [o.name for o in outcomes] == ["demo"]
    assert outcomes[0].status == "pr"
    assert config.sources[0].skills[1].synced_sha == "sha1"  # other untouched
