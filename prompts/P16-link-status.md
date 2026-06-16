# Step P16 — link & status commands (final wiring)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (consumption is via symlink into `~/.claude/skills`; status reports
  sha/drift/link state). Build plan: `BLUEPRINT.md`. This is the FINAL step, 16 of 16.
- Builds on layout (P04), config (P02), git (P03). Work test-first; deterministic — no LLM.
  Point the symlink target dir at `tmp_path` in tests (env override).
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Finish the CLI surface with two deterministic commands.

- `skillsync link [--dry-run]` in `skillsync/commands/link.py`: for each skill folder under
  `skills/`, create/refresh a symlink `~/.claude/skills/<name>` -> the skill folder. Use a
  configurable target dir (env override for tests). Skip + warn on conflicting non-symlink
  paths; `--dry-run` prints planned actions only.
- `skillsync status` (extend the earlier version): show, per skill, its synced_sha (short),
  whether upstream is ahead (via GitPort, optional/offline-tolerant), drift present? (SKILL.md
  vs .generated), and link state.

TDD: `tests/test_link.py` pointing the target dir at `tmp_path`: asserts symlink creation,
idempotent re-run, conflict skip, dry-run makes no changes. `tests/test_status.py` asserts the
status rows for a fixture repo with/without drift. Implement.

Final wiring check: ensure `skillsync --help` lists add, sync, regen, reprofile, link, status,
validate, detect; every command is reachable and covered by at least one CliRunner test.
```

## Verify & commit
- `pytest -q` green; `skillsync --help` lists all 8 commands; link is idempotent.
- Commit: `feat(p16): link & status commands`.
- Mark P16 ☑ in `RUNBOOK.md`'s progress tracker (separate `docs(p16): ...` commit). Build complete.
