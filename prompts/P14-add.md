# Step P14 — add (onboarding) command

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (onboarding: append a pin with synced_sha=None, gate, DRAFT adaptation.md
  from profile.md baked verbatim + upstream, full-mode generate, validate, open PR with an
  onboarding label). Build plan: `BLUEPRINT.md`. This is step 14 of 16.
- Builds on config (P02), gate (P06), LLM (P08), adapt (P10), validate (P07), PR (P12), and the
  pipeline helpers (P13), all green. Work test-first with fakes.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement onboarding in `skillsync/commands/add.py` and `skillsync add <repo> <skill-path>`.

Flow:
- Append a new SkillPin (synced_sha=None, hold=False) under the matching/new Source in
  sources.yaml (save_config).
- Mirror upstream; run_gate; if fail -> quarantine and stop.
- DRAFT adaptation.md: an LLM call that reads `profile.md` (baked verbatim) + upstream SKILL.md
  and proposes a self-contained adaptation.md (JSON schema {adaptation_md}).
- adapt(mode="full") to produce the first SKILL.md; validate; write upstream mirror +
  adaptation.md + SKILL.md + .generated; set synced_sha to current head.
- build_pr/publish_pr with an "onboarding" label.

TDD: `tests/test_add.py` (FakeGit/LLM/Gh): asserts sources.yaml gains the pin, adaptation.md
drafted from profile, full-mode SKILL.md generated, validated, PR opened. Gate-fail path stops
before drafting. Implement, reusing P06/P08/P10/P12 and the config layer.
```

## Verify & commit
- `pytest -q` green; gate-fail stops before drafting; pin + PR created on success.
- Commit: `feat(p14): add/onboarding command`.
- Mark P14 ☑ in `RUNBOOK.md`'s progress tracker (separate `docs(p14): ...` commit). Then P15 in a new session.
