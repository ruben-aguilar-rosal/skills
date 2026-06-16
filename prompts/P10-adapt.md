# Step P10 — Adapt stage (patch-based generation)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (patch-based generation is the DEFAULT — apply the semantic equivalent of
  the upstream delta to the existing SKILL.md at temperature 0; full regen only on onboarding
  / `regen --force`. Preserves the diff-review the committed SKILL.md exists for.) Build plan:
  `BLUEPRINT.md`. This is step 10 of 16.
- Builds on P04 (layout) + P08 (LLMPort). Work test-first. No real `claude` in tests.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement the ADAPT stage in `skillsync/stages/adapt.py`.

`adapt(layout, changeset, new_upstream_files, adaptation_text, llm, *, mode) -> AdaptResult`
with `mode ∈ {"patch","full"}` and
`AdaptResult(skill_md_text, snapshot_text, flags: list[str])`.

- mode="patch" (default for "changed"): prompt the LLM to apply the SEMANTIC EQUIVALENT of the
  upstream diff to the EXISTING SKILL.md, guided by adaptation.md, temperature 0. Output via
  JSON schema {skill_md: str}.
- mode="full" (onboarding / regen --force): generate SKILL.md from scratch from new upstream +
  adaptation.md.
- `snapshot_text` == the produced skill_md (to be written to `.generated/SKILL.md`).

TDD: `tests/test_adapt.py` with `FakeLLM`: patch mode returns edited text given a diff; full
mode returns generated text; assert snapshot equals output and temperature/model passed
through (assert on the fake's recorded call). Implement.

Wire: consumed by sync/add/regen. Export.
```

## Verify & commit
- `pytest -q` green; patch mode uses temperature 0 (asserted via FakeLLM record).
- Commit: `feat(p10): adapt stage (patch-based)`. Then P11 in a new session.
