"""Tests for the RECONCILE stage (`skillsync.stages.reconcile`).

Reconcile handles HAND-EDITS to the committed `SKILL.md`. Three pieces:

- `detect_drift` is DETERMINISTIC (no LLM): a unified diff between the on-disk
  `SKILL.md` and the last agent snapshot in `.generated/SKILL.md`; `None` when they
  match or either is absent.
- `fold_back` asks the LLM to turn that drift into ADDITIONS to `adaptation.md`, so
  the hand-edit survives the next generation (schema-constrained, temperature 0).
- `verify_preserved` asks the LLM, after regeneration, whether the hand-edit's intent
  survived; a non-preserved verdict is what the pipeline turns into a review flag.

These tests drive `FakeLLM` with scripted responses — no real `claude` is invoked.
"""

from skillsync.layout import SkillFiles
from skillsync.ports.llm import LLMResult
from skillsync.stages.reconcile import (
    FOLDBACK_SCHEMA,
    PRESERVATION_SCHEMA,
    FoldBackResult,
    PreservationVerdict,
    detect_drift,
    fold_back,
    verify_preserved,
)
from skillsync.testing.fakes import FakeLLM

GENERATED_SKILL_MD = """\
---
name: to-issues
description: Turn notes into Jira issues.
---

Create a TP Jira issue from the selected notes.
"""

# The hand-edited committed SKILL.md: a human added a line about linking to an epic.
HAND_EDITED_SKILL_MD = """\
---
name: to-issues
description: Turn notes into Jira issues.
---

Create a TP Jira issue from the selected notes.
Always link the new issue to its tracking epic.
"""

ADAPTATION_TEXT = "Target Jira, not GitHub. Use the TP project. Keep the tone terse."

ENRICHED_ADAPTATION = (
    ADAPTATION_TEXT + "\n\n## Hand-edit folded back\n"
    "Always link a newly created issue to its tracking epic.\n"
)


def test_detect_drift_returns_none_when_equal() -> None:
    """No drift when the committed SKILL.md matches the last snapshot."""
    files = SkillFiles(
        adaptation=ADAPTATION_TEXT,
        skill_md=GENERATED_SKILL_MD,
        generated_skill_md=GENERATED_SKILL_MD,
    )
    assert detect_drift(files) is None


def test_detect_drift_returns_none_when_snapshot_absent() -> None:
    """No drift to fold back when there is no `.generated` snapshot to compare."""
    files = SkillFiles(
        adaptation=ADAPTATION_TEXT,
        skill_md=HAND_EDITED_SKILL_MD,
        generated_skill_md=None,
    )
    assert detect_drift(files) is None


def test_detect_drift_returns_none_when_skill_md_absent() -> None:
    """No drift when there is no committed SKILL.md on disk."""
    files = SkillFiles(
        adaptation=ADAPTATION_TEXT,
        skill_md=None,
        generated_skill_md=GENERATED_SKILL_MD,
    )
    assert detect_drift(files) is None


def test_detect_drift_diffs_snapshot_against_committed() -> None:
    """A hand-edit yields a unified diff from snapshot to the committed file."""
    files = SkillFiles(
        adaptation=ADAPTATION_TEXT,
        skill_md=HAND_EDITED_SKILL_MD,
        generated_skill_md=GENERATED_SKILL_MD,
    )
    drift = detect_drift(files)

    assert drift is not None
    # The added hand-edit line shows as an addition; nothing was removed.
    assert "+Always link the new issue to its tracking epic." in drift
    removals = [
        line
        for line in drift.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    assert removals == []


def test_detect_drift_is_deterministic() -> None:
    """The drift diff is reproducible across calls (no LLM, no nondeterminism)."""
    files = SkillFiles(
        adaptation=ADAPTATION_TEXT,
        skill_md=HAND_EDITED_SKILL_MD,
        generated_skill_md=GENERATED_SKILL_MD,
    )
    assert detect_drift(files) == detect_drift(files)


def test_fold_back_returns_enriched_adaptation() -> None:
    """fold_back returns the LLM's enriched adaptation text and a summary."""
    drift = detect_drift(
        SkillFiles(None, HAND_EDITED_SKILL_MD, GENERATED_SKILL_MD)
    )
    assert drift is not None
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={
                    "new_adaptation_text": ENRICHED_ADAPTATION,
                    "summary": "Added a rule to link issues to their tracking epic.",
                },
            )
        }
    )

    result = fold_back(ADAPTATION_TEXT, drift, fake, model="opus")

    assert isinstance(result, FoldBackResult)
    assert result.new_adaptation_text == ENRICHED_ADAPTATION
    assert "epic" in result.summary


def test_fold_back_uses_temperature_zero_model_and_schema() -> None:
    """fold_back runs deterministically with the requested model and schema."""
    drift = detect_drift(
        SkillFiles(None, HAND_EDITED_SKILL_MD, GENERATED_SKILL_MD)
    )
    assert drift is not None
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={"new_adaptation_text": ENRICHED_ADAPTATION, "summary": "x"},
            )
        }
    )

    fold_back(ADAPTATION_TEXT, drift, fake, model="opus")

    call = fake.calls[0]
    assert call.temperature == 0.0
    assert call.model == "opus"
    assert call.schema == FOLDBACK_SCHEMA


def test_fold_back_prompt_carries_adaptation_and_drift_as_untrusted() -> None:
    """The fold-back prompt embeds the current adaptation and the drift as data."""
    drift = detect_drift(
        SkillFiles(None, HAND_EDITED_SKILL_MD, GENERATED_SKILL_MD)
    )
    assert drift is not None
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={"new_adaptation_text": ENRICHED_ADAPTATION, "summary": "x"},
            )
        }
    )

    fold_back(ADAPTATION_TEXT, drift, fake, model="opus")

    prompt = fake.calls[0].prompt
    assert ADAPTATION_TEXT in prompt
    assert drift in prompt
    assert "untrusted" in prompt.lower()


def test_verify_preserved_true_for_surviving_edit() -> None:
    """A preserved hand-edit yields preserved=True with an explanatory note."""
    hand_edit_diff = "+Always link the new issue to its tracking epic.\n"
    regenerated = HAND_EDITED_SKILL_MD  # the regen kept the epic line
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={"preserved": True, "note": "The epic-linking line is present."},
            )
        }
    )

    verdict = verify_preserved(hand_edit_diff, regenerated, fake, model="opus")

    assert isinstance(verdict, PreservationVerdict)
    assert verdict.preserved is True
    assert verdict.note


def test_verify_preserved_flags_non_preserved_edit() -> None:
    """A dropped hand-edit yields preserved=False so the pipeline can flag it."""
    hand_edit_diff = "+Always link the new issue to its tracking epic.\n"
    regenerated = GENERATED_SKILL_MD  # the regen dropped the epic line
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={
                    "preserved": False,
                    "note": "The epic-linking line is missing from the output.",
                },
            )
        }
    )

    verdict = verify_preserved(hand_edit_diff, regenerated, fake, model="opus")

    assert verdict.preserved is False
    assert verdict.note


def test_verify_preserved_fails_safe_on_llm_error() -> None:
    """When the verifier cannot get a verdict, it conservatively flags non-preserved."""
    fake = FakeLLM({})  # no scripted response -> LLMError inside verify

    verdict = verify_preserved("+something\n", GENERATED_SKILL_MD, fake, model="opus")

    assert verdict.preserved is False
    assert verdict.note


def test_verify_preserved_uses_schema_and_temperature_zero() -> None:
    """verify_preserved runs deterministically with the preservation schema."""
    fake = FakeLLM(
        {
            "tracking epic": LLMResult(
                text="{}",
                json={"preserved": True, "note": "ok"},
            )
        }
    )

    verify_preserved("+tracking epic\n", HAND_EDITED_SKILL_MD, fake, model="opus")

    call = fake.calls[0]
    assert call.temperature == 0.0
    assert call.schema == PRESERVATION_SCHEMA
