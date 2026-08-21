---
name: ship
description: >
  Ship finished work: route to the phase that comes next. Use when the user says ship,
  wants finished work opened as a pull request, or asks what to do next on an open one.
---

# ship

A map. Name the phase, start **one** skill, stop. Never chain into the phase after it.

Rules and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).

## 1. Read the state

```bash
git branch --show-current
git status --porcelain
gh stack view --json 2>/dev/null; echo "stack_exit=$?"
gh pr list --head "$(git branch --show-current)" --json number,state,isDraft
```

`gh stack view` exits 2 when the branch is in no stack. Branch on the exit code.

**Done when** you can name the phase from the table without guessing.

## 2. Start that one skill

| State | Skill |
|---|---|
| Commits on one branch, no stack, no PR | `/split-pr` |
| A stack exists, no PRs yet | `/ship-stack` |
| One branch, no stack, no PR, `/split-pr` already said it fits | `/ship-stack` |
| Any PR open on this branch or stack | `/pr-review` |
| Nothing committed | Say so. Stop. |

Uncommitted changes belong to the phase you are entering. Report them and let it handle them.

**Done when** exactly one skill has started and this file has stopped.

## Guardrails

The user's calls, handed over rather than taken:

- **Merging.** Report that a PR is mergeable; let them press it.
- **Marking a PR ready for review.**
- **Posting a comment or resolving a thread.** Draft, print, let them paste.
- **The default branch** takes no direct commits.

## Report

The phase and why, in two sentences. Then start the skill. Plain words, emoji. 🌝
