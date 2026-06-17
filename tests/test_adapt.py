"""Tests for the ADAPT stage (`skillsync.stages.adapt`).

Adapt is the agentic step that turns an upstream change into a new `SKILL.md`.
The DEFAULT is PATCH mode: the LLM applies the semantic equivalent of the upstream
diff to the EXISTING `SKILL.md`, guided by `adaptation.md`, at temperature 0 — the
minimal edit that keeps PR diffs legible. FULL mode regenerates from scratch and is
reserved for onboarding / `regen --force`. These tests drive `FakeLLM` with scripted
responses and assert the snapshot equals the output and the model/temperature are
passed through — without ever invoking the real `claude` executable.
"""

from pathlib import Path

from skillsync.layout import SkillLayout, write_text
from skillsync.ports.llm import LLMResult
from skillsync.stages.adapt import ADAPT_SCHEMA, AdaptResult, adapt
from skillsync.stages.detect import ChangeSet
from skillsync.testing.fakes import FakeLLM

EXISTING_SKILL_MD = """\
---
name: to-issues
description: Turn notes into issues.
---

Create a GitHub issue from the selected notes.
"""

UPSTREAM_DIFF = (
    "--- a/SKILL.md\n"
    "+++ b/SKILL.md\n"
    "@@\n"
    "-Create a GitHub issue from the selected notes.\n"
    "+Create a GitHub issue, then link it to a tracking epic.\n"
)

ADAPTATION_TEXT = "Target Jira, not GitHub. Use the TP project. Keep the tone terse."

NEW_UPSTREAM_FILES = {
    "SKILL.md": (
        "---\nname: to-issues\ndescription: Turn notes into issues.\n---\n\n"
        "Create a GitHub issue, then link it to a tracking epic.\n"
    ),
    "scripts/open.sh": "#!/usr/bin/env bash\ngh issue create\n",
}

PATCHED_OUTPUT = """\
---
name: to-issues
description: Turn notes into Jira issues.
---

Create a TP Jira issue, then link it to a tracking epic.
"""

GENERATED_OUTPUT = """\
---
name: to-issues
description: Turn notes into Jira issues.
---

Create a TP Jira issue, then link it to a tracking epic. (generated)
"""


def _changeset(kind: str = "changed", *, rewritten: bool = False) -> ChangeSet:
    """Build a minimal `ChangeSet` carrying the upstream diff under test."""
    return ChangeSet(
        skill_path="engineering/to-issues",
        name="to-issues",
        kind=kind,  # type: ignore[arg-type]
        from_sha="old" if kind == "changed" else None,
        to_sha="new",
        diff=UPSTREAM_DIFF,
        changed_files=["SKILL.md"],
        rewritten_history=rewritten,
    )


def _layout(tmp_path: Path, *, with_skill_md: bool = True) -> SkillLayout:
    """Resolve a layout under `tmp_path`, optionally seeding the committed SKILL.md."""
    layout = SkillLayout.resolve(tmp_path, "engineering/to-issues")
    if with_skill_md:
        write_text(layout.skill_md_path, EXISTING_SKILL_MD)
    return layout


def test_patch_mode_edits_existing_skill_md(tmp_path: Path) -> None:
    """Patch mode returns the LLM's edited SKILL.md and snapshots it verbatim."""
    layout = _layout(tmp_path)
    fake = FakeLLM({UPSTREAM_DIFF: LLMResult(text="{}", json={"skill_md": PATCHED_OUTPUT})})

    result = adapt(
        layout, _changeset(), NEW_UPSTREAM_FILES, ADAPTATION_TEXT, fake, mode="patch"
    )

    assert isinstance(result, AdaptResult)
    assert result.skill_md_text == PATCHED_OUTPUT
    # The snapshot written to .generated/SKILL.md is exactly the produced text.
    assert result.snapshot_text == PATCHED_OUTPUT
    assert result.flags == []


def test_patch_mode_uses_temperature_zero_and_model(tmp_path: Path) -> None:
    """Patch mode is deterministic: temperature 0, the requested model, the schema."""
    layout = _layout(tmp_path)
    fake = FakeLLM({UPSTREAM_DIFF: LLMResult(text="{}", json={"skill_md": PATCHED_OUTPUT})})

    adapt(
        layout,
        _changeset(),
        NEW_UPSTREAM_FILES,
        ADAPTATION_TEXT,
        fake,
        mode="patch",
        model="opus",
    )

    call = fake.calls[0]
    assert call.temperature == 0.0
    assert call.model == "opus"
    assert call.schema == ADAPT_SCHEMA


def test_patch_prompt_carries_existing_diff_and_adaptation(tmp_path: Path) -> None:
    """The patch prompt embeds the existing SKILL.md, the diff, and adaptation rules."""
    layout = _layout(tmp_path)
    fake = FakeLLM({UPSTREAM_DIFF: LLMResult(text="{}", json={"skill_md": PATCHED_OUTPUT})})

    adapt(layout, _changeset(), NEW_UPSTREAM_FILES, ADAPTATION_TEXT, fake, mode="patch")

    prompt = fake.calls[0].prompt
    assert EXISTING_SKILL_MD in prompt
    assert UPSTREAM_DIFF in prompt
    assert ADAPTATION_TEXT in prompt
    # Upstream content is fenced as untrusted data, never as instructions.
    assert "untrusted" in prompt.lower()


def test_full_mode_generates_from_upstream(tmp_path: Path) -> None:
    """Full mode regenerates from scratch and snapshots the produced text."""
    layout = _layout(tmp_path)
    fake = FakeLLM(
        {"scripts/open.sh": LLMResult(text="{}", json={"skill_md": GENERATED_OUTPUT})}
    )

    result = adapt(
        layout,
        _changeset(kind="reonboard"),
        NEW_UPSTREAM_FILES,
        ADAPTATION_TEXT,
        fake,
        mode="full",
    )

    assert result.skill_md_text == GENERATED_OUTPUT
    assert result.snapshot_text == GENERATED_OUTPUT


def test_full_prompt_carries_upstream_files_and_adaptation(tmp_path: Path) -> None:
    """The full prompt embeds every upstream file's path/content and adaptation rules."""
    layout = _layout(tmp_path)
    fake = FakeLLM(
        {"scripts/open.sh": LLMResult(text="{}", json={"skill_md": GENERATED_OUTPUT})}
    )

    adapt(
        layout,
        _changeset(kind="reonboard"),
        NEW_UPSTREAM_FILES,
        ADAPTATION_TEXT,
        fake,
        mode="full",
    )

    prompt = fake.calls[0].prompt
    for rel_path, content in NEW_UPSTREAM_FILES.items():
        assert rel_path in prompt
        assert content in prompt
    assert ADAPTATION_TEXT in prompt
    assert fake.calls[0].temperature == 0.0


def test_patch_without_existing_skill_md_falls_back_to_full(tmp_path: Path) -> None:
    """With no SKILL.md to patch, patch mode regenerates and flags the fallback."""
    layout = _layout(tmp_path, with_skill_md=False)
    fake = FakeLLM(
        {"scripts/open.sh": LLMResult(text="{}", json={"skill_md": GENERATED_OUTPUT})}
    )

    result = adapt(
        layout, _changeset(), NEW_UPSTREAM_FILES, ADAPTATION_TEXT, fake, mode="patch"
    )

    assert result.skill_md_text == GENERATED_OUTPUT
    assert any("scratch" in flag.lower() or "full" in flag.lower() for flag in result.flags)


def test_rewritten_history_is_flagged(tmp_path: Path) -> None:
    """A history-rewrite re-onboard surfaces a loud review flag on the result."""
    layout = _layout(tmp_path, with_skill_md=False)
    fake = FakeLLM(
        {"scripts/open.sh": LLMResult(text="{}", json={"skill_md": GENERATED_OUTPUT})}
    )

    result = adapt(
        layout,
        _changeset(kind="reonboard", rewritten=True),
        NEW_UPSTREAM_FILES,
        ADAPTATION_TEXT,
        fake,
        mode="full",
    )

    assert any("history" in flag.lower() for flag in result.flags)
