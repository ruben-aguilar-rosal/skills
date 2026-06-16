# Step P15 — regen & reprofile commands

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (`regen` rebuilds a SKILL.md from current upstream+adaptation; `reprofile`
  re-bakes the current profile.md into every adaptation.md and regenerates, one PR per skill —
  the propagation lever for stack/tone changes across self-contained adaptation files). Build
  plan: `BLUEPRINT.md`. This is step 15 of 16.
- Builds on adapt (P10), validate (P07), PR (P12), config/profile (P02). Work test-first with
  fakes. Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add two LLM-backed maintenance commands, reusing the adapt stage and LLM port.

- `skillsync regen <name> [--force]` in `skillsync/commands/regen.py`: regenerate SKILL.md from
  the CURRENT on-disk upstream + adaptation.md. `--force` => mode="full"; without it, re-apply
  adaptation to current upstream (full is fine here since there's no new diff). Validate; write
  SKILL.md + .generated; open a PR (branch `skillsync/regen-<name>`).
- `skillsync reprofile` in `skillsync/commands/reprofile.py`: for every skill, an LLM pass
  re-bakes the current `profile.md` into each `adaptation.md` (JSON schema {adaptation_md}),
  then regenerates each SKILL.md, validates, and opens ONE PR per skill (reuse build_pr).

TDD: `tests/test_regen.py` and `tests/test_reprofile.py` with fakes: regen writes new SKILL.md
+ snapshot + PR; reprofile updates every adaptation.md and opens a PR per skill; validation
failure blocks that skill's PR. Implement.
```

## Verify & commit
- `pytest -q` green; validation failure blocks that skill's PR in both commands.
- Commit: `feat(p15): regen & reprofile commands`. Then P16 in a new session.
