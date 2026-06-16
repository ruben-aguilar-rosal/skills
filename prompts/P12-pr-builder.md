# Step P12 — PR builder (gh port)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (one PR per changed skill; the PR body always shows the RAW upstream diff +
  extracted commands/URLs alongside the adapted output, so adaptation can't launder threats).
  Build plan: `BLUEPRINT.md`. This is step 12 of 16.
- Builds on P05 (ChangeSet), P06 (GateResult), P09 (AdvisoryVerdict), P10 (AdaptResult). Work
  test-first. `gh`/`git` behind a port; NEVER call real `gh` in tests — use FakeGh.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add the PR output layer.

In `skillsync/ports/gh.py` define `GhPort` Protocol:
- `current_branch(root) -> str`
- `create_branch(root, name) -> None`
- `commit_all(root, message) -> None`
- `open_pr(root, branch, title, body, labels) -> str` (returns PR URL)

Provide `GhCli(GhPort)` (uses `git` + `gh pr create`, args list) and `FakeGh(GhPort)` (records
calls) in testing/fakes.

Add `skillsync/pr.py`:
- `build_pr(changeset, gate, advisory, adapt_result) -> SkillPR` assembling branch
  `skillsync/<name>`, title, and a body containing: the RAW upstream diff, extracted
  commands/URLs, advisory verdict, sha bump, adaptation.md change summary, and any flags.
- `publish_pr(skill_pr, gh: GhPort, root) -> str`.

TDD: `tests/test_pr.py` asserting the body contains the raw diff + extracted commands + flags,
and that publish drives the GhPort calls in order (branch -> commit -> open_pr) via `FakeGh`.
Implement. Wire: consumed by sync.
```

## Verify & commit
- `pytest -q` green; PR body includes raw diff + commands + flags; call order asserted.
- Commit: `feat(p12): PR builder (gh port)`. Then P13 in a new session.
