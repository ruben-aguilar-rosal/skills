# Step P04 — Skill layout & folder I/O

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md`. Build plan & conventions: `BLUEPRINT.md`. This is step 4 of 16.
- Builds on P01–P03 (green). Work test-first. No network in tests; use `tmp_path`.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add `skillsync/layout.py` with a `SkillLayout` dataclass that, given the repo root and a skill
name, resolves: `root`, `upstream_dir`, `adaptation_path`, `skill_md_path`, `generated_dir`,
`generated_skill_md_path`. Skill name derives from the upstream subtree's last path segment
unless overridden.

Add pure helpers:
- `read_text(path) -> str | None`
- `write_text(path, text) -> None` (creates parent dirs)
- `mirror_files(files: dict[str, str], dest_dir: Path) -> None` (replaces dest contents)
- `read_skill(layout) -> SkillFiles` dataclass {adaptation, skill_md, generated_skill_md}
  (each `str | None`).

TDD: `tests/test_layout.py` using `tmp_path` to assert path resolution, mirror replaces stale
files, and read_skill returns None for absent files. Implement.

Wire: add a real `skillsync status` command that lists skill folders found under `skills/` and
whether each has adaptation/SKILL/generated present. Test the command with CliRunner against a
`tmp_path` repo.
```

## Verify & commit
- `pytest -q` green; `skillsync status` lists skill folders.
- Commit: `feat(p04): skill layout & folder I/O`.
- Mark P04 ☑ in `RUNBOOK.md`'s progress tracker (separate `docs(p04): ...` commit). Then P05 in a new session.
