# Step P13 — sync command (full pipeline wiring)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (pipeline: detect → deterministic gate → reconcile → adapt(patch) → verify
  → deterministic validate → PR; gate fail = quarantine at old sha; validate fail = no PR +
  issue; sha bumps ONLY on a successful PR). Build plan: `BLUEPRINT.md`. This is step 13 of 16
  — the integration step that wires P05–P12 together.
- All prior stages exist and are green. Work test-first with FakeGit + FakeLLM + FakeGh.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Wire the end-to-end SYNC pipeline in `skillsync/pipeline.py` and expose `skillsync sync`.

`run_sync(config, root, *, git, llm, gh, only=None) -> list[SyncOutcome]` orchestrating, per
changed skill:
  detect -> if kind none: skip
         -> read new upstream files -> run_gate
            -> gate fail: QUARANTINE (no adapt; produce a quarantine SkillPR/issue with the
               suspicious diff + findings; skill stays pinned at old sha) and continue
            -> gate pass: advisory_scan (annotate)
               -> detect_drift; if drift && changed: fold_back (update adaptation.md)
               -> adapt(mode="patch" for changed / "full" for reonboard)
               -> if folded: verify_preserved -> maybe flag
               -> validate_skill: fail -> NO PR, emit issue; pass -> write upstream mirror,
                  SKILL.md, .generated snapshot, bump synced_sha in config
               -> build_pr -> publish_pr
Return structured outcomes (pr_url | quarantined | invalid | skipped) per skill.

`skillsync sync [--skill NAME]` assembles real GitCli/ClaudeCli/GhCli (Opus, temp 0) and calls
run_sync, printing a summary table.

TDD: `tests/test_pipeline.py` with FakeGit + FakeLLM + FakeGh covering the full matrix: clean
change -> PR; gate fail -> quarantine, sha unchanged; validate fail -> no PR + issue; drift +
change -> fold_back + verify path; reonboard -> full mode. Assert config sha is bumped ONLY on
successful PR. Implement until all green.
```

## Verify & commit
- `pytest -q` green across the full matrix; sha bump only on successful PR.
- Commit: `feat(p13): sync pipeline end-to-end`. Then P14 in a new session.
