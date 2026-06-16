# Step P05 — Detect stage

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md`. Build plan & conventions: `BLUEPRINT.md`. This is step 5 of 16.
- Builds on P02 (config) + P03 (GitPort) + P04 (layout), all green. Work test-first.
- This is a DETERMINISTIC stage — zero LLM. Drive tests with `FakeGit`.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement the deterministic DETECT stage in `skillsync/stages/detect.py`.

`detect(config: Config, git: GitPort, root: Path) -> list[ChangeSet]` where
`ChangeSet(skill_path, name, kind, from_sha, to_sha, diff, changed_files)` and
`kind ∈ {"none","changed","reonboard"}`.

Logic per non-held SkillPin:
- mirror+fetch the source ref; compute `to_sha = head_sha`.
- if `synced_sha is None` -> kind="reonboard" (new skill), diff = full content.
- elif not `is_ancestor(synced_sha, ref)` -> kind="reonboard" (history rewritten); record a flag.
- else diff_subtree(synced_sha..ref, subtree); empty -> "none", else "changed".

TDD: `tests/test_detect.py` driven entirely by `FakeGit`, covering: no change, normal change,
new skill (None sha), rewritten-history reonboard, and `hold=True` skipped. Implement.

Wire: add a `skillsync detect` command that prints a table of skill -> kind using the real
`GitCli`. The CliRunner test injects `FakeGit` via a dependency-injection seam (a factory
function the command calls).
```

## Verify & commit
- `pytest -q` green; `skillsync detect` prints a kind table.
- Commit: `feat(p05): detect stage`. Then P06 in a new session.
