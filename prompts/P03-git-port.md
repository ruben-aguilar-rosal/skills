# Step P03 — Git I/O port (real + fake)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md`. Build plan & conventions: `BLUEPRINT.md`. This is step 3 of 16.
- Builds on P01–P02 (green). Work test-first. Side effects behind injected ports.
- Subprocess calls use an args list, `shell=False`, with a timeout. No network in tests
  (a real *local* temp git repo is allowed).
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add a git port that the deterministic stages will depend on, with a real implementation and a
fake for tests.

In `skillsync/ports/git.py` define a `GitPort` Protocol:
- `mirror(repo: str, ref: str) -> Path` — ensure a local mirror of `repo`, fetch `ref`,
  return the checkout path.
- `head_sha(repo_path: Path, ref: str) -> str`
- `is_ancestor(repo_path: Path, ancestor_sha: str, ref: str) -> bool`
- `diff_subtree(repo_path: Path, from_sha: str | None, ref: str, subtree: str) -> str`
  (unified diff limited to `subtree`; `from_sha=None` => full content as added).
- `list_subtree_files(repo_path: Path, ref: str, subtree: str) -> list[str]`

Provide `GitCli(GitPort)` in `skillsync/ports/git_cli.py` shelling out to `git` via
`subprocess.run` (args list, no shell). Provide `FakeGit(GitPort)` in
`skillsync/testing/fakes.py` backed by an in-memory dict {sha: {path: content}} and a linear
history, enough to exercise ancestor/diff logic.

TDD: `tests/test_git_cli.py` initializes a real temp git repo (local, no network) with two
commits touching a subtree, and asserts `diff_subtree`, `is_ancestor`, `head_sha`. Also
`tests/test_fake_git.py` asserting the fake matches the same contract for the cases the stages
need. Implement until green.

Do not wire into a CLI command yet — this is infrastructure consumed by Step P05.
```

## Verify & commit
- `pytest -q` green (real-git test + fake-git contract test).
- Commit: `feat(p03): git I/O port (real + fake)`.
- Mark P03 ☑ in `RUNBOOK.md`'s progress tracker (separate `docs(p03): ...` commit). Then P04 in a new session.
