# Step P07 — Validate stage (deterministic)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (validate blocks the PR — guarantees a loadable skill). Build plan:
  `BLUEPRINT.md`. This is step 7 of 16.
- Builds on P04 (layout). Work test-first. Deterministic — no LLM.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement the deterministic VALIDATE stage in `skillsync/stages/validate.py`.

`validate_skill(layout: SkillLayout, skill_md_text: str, byte_cap: int) -> ValidationResult`
with `ValidationResult(passed, errors: list[str])`.

Checks:
- YAML frontmatter parses; has non-empty `name` and `description`.
- `name` equals the skill folder name.
- size <= byte_cap.
- every relative path referenced in the body (links, `scripts/x.sh`) exists under the skill
  folder.

TDD: `tests/test_validate.py` covering pass, missing description, name/dir mismatch, broken
relative reference, oversize. Implement.

Wire: add `skillsync validate <skill-name>` command that reads the on-disk SKILL.md and prints
PASS/errors, exit code 1 on failure. CliRunner test against a `tmp_path` skill folder.
```

## Verify & commit
- `pytest -q` green; `skillsync validate <name>` exits 1 on a broken skill.
- Commit: `feat(p07): validate stage`.
- Mark P07 ☑ in `RUNBOOK.md`'s progress tracker (separate `docs(p07): ...` commit). Then P08 in a new session.
