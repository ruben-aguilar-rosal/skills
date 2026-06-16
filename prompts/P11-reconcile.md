# Step P11 — Drift detection, fold-back & preservation verify

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (hand-edits to SKILL.md are detected as drift vs `.generated/`, folded
  back into adaptation.md, then a verify pass confirms the edit's intent survived regen; if not,
  the PR is flagged). Build plan: `BLUEPRINT.md`. This is step 11 of 16.
- Builds on P04 (SkillFiles) + P08 (LLMPort) + P10 (adapt). Work test-first. No real `claude`.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement RECONCILE in `skillsync/stages/reconcile.py`.

1. `detect_drift(skill_files: SkillFiles) -> str | None` — deterministic diff between on-disk
   SKILL.md and `.generated/SKILL.md`; None if equal/absent. (Unit-test with no LLM.)
2. `fold_back(adaptation_text, drift_diff, llm, model) -> FoldBackResult`
   {new_adaptation_text, summary} — LLM turns the hand-edit drift into additions to
   adaptation.md. JSON schema'd.
3. `verify_preserved(hand_edit_diff, new_skill_md, llm, model) -> PreservationVerdict`
   {preserved: bool, note: str} — after regen, confirm the hand-edit's intent survived; if not,
   surface a flag string.

TDD: `tests/test_reconcile.py`: drift diff math (deterministic), fold_back returns enriched
adaptation (FakeLLM), verify flags non-preserved edits. Implement.

Wire: these compose in sync (Step P13): if drift && changed -> fold_back -> adapt -> verify;
verify failure appends a "⚠ hand-edit may not be preserved" flag to AdaptResult.flags.
```

## Verify & commit
- `pytest -q` green; non-preserved edit produces the flag.
- Commit: `feat(p11): drift detection, fold-back & verify`. Then P12 in a new session.
