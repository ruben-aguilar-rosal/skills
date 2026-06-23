"""Tests for the REGEN command (`skillsync.commands.regen`).

`run_regen` rebuilds a skill's `SKILL.md` from the CURRENT on-disk upstream mirror
plus the current `adaptation.md` — it does NOT re-pull upstream — then validates,
writes the artifacts, and opens a PR on a `skillsync/regen-<name>` branch. These
tests drive the injected `FakeLLM` + `FakeGh` so no real claude/gh is touched:

- **happy path** → full-mode regeneration produces a new SKILL.md + snapshot and a
  PR on the `skillsync/regen-<name>` branch labelled `regen`;
- **`--force`** → still a full regeneration (there is no new diff to patch);
- **validate fail** → an issue is opened, no PR, nothing is written, no sha change.
"""

from pathlib import Path

from skillsync.commands.regen import RegenOutcome, run_regen
from skillsync.config import Config, SkillPin, Source
from skillsync.layout import SkillLayout, read_text, write_text
from skillsync.ports.llm import LLMResult
from skillsync.testing.fakes import FakeGh, FakeLLM

# --- Scripted LLM substring keys (unique to each stage's prompt template) -------
_FULL_KEY = "from scratch"

# The on-disk upstream mirror content (already vetted at sync/add time).
_UPSTREAM = (
    "---\nname: demo\ndescription: Turn notes into issues.\n---\n\n"
    "# demo\nCreate a GitHub issue from the selected notes.\n"
)

# The current self-contained adaptation.md the regen reads.
_ADAPTATION = (
    "Use Jira project TP. Terse tone.\n\nFile issues in project TP.\n"
)

# A valid full-generated SKILL.md — frontmatter name matches the skill folder.
_REGENERATED_VALID = (
    "---\nname: demo\ndescription: Turn notes into Jira issues.\n---\n\n"
    "# demo\nFile a Jira issue in project TP from the selected notes.\n"
)

# An invalid full-generated SKILL.md: frontmatter name does not match the folder.
_REGENERATED_INVALID = (
    "---\nname: wrong\ndescription: Bad.\n---\n\n# demo\nDo the thing.\n"
)


def _full(skill_md: str) -> LLMResult:
    """A scripted full-mode adapt result returning `skill_md`."""
    return LLMResult(text="{}", json={"skill_md": skill_md})


def _config() -> Config:
    """A config holding one tracked pin for `skills/demo`, synced at `sha1`."""
    return Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[SkillPin(path="skills/demo", synced_sha="sha1")],
            )
        ]
    )


def _seed_skill(root: Path, *, adaptation: str = _ADAPTATION) -> SkillLayout:
    """Lay down an on-disk skill: upstream mirror + adaptation.md + a prior SKILL.md."""
    layout = SkillLayout.resolve(root, "skills/demo")
    write_text(layout.upstream_dir / "SKILL.md", _UPSTREAM)
    write_text(layout.adaptation_path, adaptation)
    write_text(layout.skill_md_path, "---\nname: demo\ndescription: old.\n---\n\nold\n")
    return layout


# --- happy path -----------------------------------------------------------------


def test_regen_writes_skill_snapshot_and_opens_pr(tmp_path: Path) -> None:
    """A clean regen full-generates SKILL.md + snapshot and opens a regen PR."""
    config = _config()
    layout = _seed_skill(tmp_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_VALID)})
    gh = FakeGh()

    outcome = run_regen(config, tmp_path, "demo", llm=llm, gh=gh)

    assert isinstance(outcome, RegenOutcome)
    assert outcome.status == "pr"
    assert outcome.url is not None
    # The new SKILL.md and its snapshot are written from the regenerated text.
    assert read_text(layout.skill_md_path) == _REGENERATED_VALID
    assert read_text(layout.generated_skill_md_path) == _REGENERATED_VALID
    # A PR was opened on the regen branch.
    open_pr = next(c for c in gh.calls if c.method == "open_pr")
    assert open_pr.args[1] == "skillsync/regen-demo"


def test_regen_regenerates_from_on_disk_upstream_and_adaptation(tmp_path: Path) -> None:
    """Full-mode regeneration reads the on-disk upstream mirror and adaptation.md."""
    config = _config()
    _seed_skill(tmp_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_VALID)})

    run_regen(config, tmp_path, "demo", llm=llm, gh=FakeGh())

    full_call = next(c for c in llm.calls if _FULL_KEY in c.prompt)
    # The on-disk upstream mirror is the generation source...
    assert "Create a GitHub issue from the selected notes." in full_call.prompt
    # ...and the current adaptation.md drives the adaptation.
    assert "File issues in project TP." in full_call.prompt


def test_regen_pr_carries_regen_label(tmp_path: Path) -> None:
    """The regen PR is labelled `regen` so the PR list distinguishes a regeneration."""
    config = _config()
    _seed_skill(tmp_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_VALID)})
    gh = FakeGh()

    run_regen(config, tmp_path, "demo", llm=llm, gh=gh)

    open_pr = next(c for c in gh.calls if c.method == "open_pr")
    assert "regen" in open_pr.args[4]


def test_regen_force_still_full_generates(tmp_path: Path) -> None:
    """`--force` regeneration is a full generation (no new diff to patch)."""
    config = _config()
    _seed_skill(tmp_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_VALID)})

    outcome = run_regen(config, tmp_path, "demo", llm=llm, gh=FakeGh(), force=True)

    assert outcome.status == "pr"
    # Full-mode (from scratch) generation was used, not a patch.
    assert any(_FULL_KEY in c.prompt for c in llm.calls)


def test_regen_does_not_bump_synced_sha(tmp_path: Path) -> None:
    """Regen never moves the pin: there is no new upstream to sync to."""
    config = _config()
    _seed_skill(tmp_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_VALID)})

    run_regen(config, tmp_path, "demo", llm=llm, gh=FakeGh())

    assert config.sources[0].skills[0].synced_sha == "sha1"


# --- validate fail -> no PR + issue ---------------------------------------------


def test_regen_validate_fail_emits_issue_and_no_pr(tmp_path: Path) -> None:
    """A regenerated SKILL.md that fails validation blocks the PR and opens an issue."""
    config = _config()
    layout = _seed_skill(tmp_path)
    prior_skill_md = read_text(layout.skill_md_path)
    llm = FakeLLM({_FULL_KEY: _full(_REGENERATED_INVALID)})
    gh = FakeGh()

    outcome = run_regen(config, tmp_path, "demo", llm=llm, gh=gh)

    assert outcome.status == "invalid"
    assert any(c.method == "open_issue" for c in gh.calls)
    assert not any(c.method == "open_pr" for c in gh.calls)
    # Nothing was overwritten — the prior SKILL.md stays on disk.
    assert read_text(layout.skill_md_path) == prior_skill_md
