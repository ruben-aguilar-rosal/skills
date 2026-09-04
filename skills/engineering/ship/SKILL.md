---
name: ship
description: >
  Ship finished work: measure the diff, then route to the phase that comes next. Under the size
  limit it opens the pull request itself; over it, it hands to /split-pr. Use when the user says
  ship, wants finished work opened as a pull request, or asks what to do next on an open one.
---

# ship

A map. Name the phase, start **one** skill, stop. Never chain into the phase after it.

Small work skips the stack. Under the size limit this file starts `/ship-stack` itself, so a
two-file change needs one command rather than three.

Rules and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).
Measurement: `references/measure-the-diff.md`.

## 1. Read the state

```bash
git branch --show-current
git status --porcelain
gh stack view --json 2>/dev/null; echo "stack_exit=$?"
gh pr list --head "$(git branch --show-current)" --json number,state,isDraft
```

`gh stack view` exits 2 when the branch is in no stack. Branch on the exit code.

**Done when** you can name the phase from the table in step 3 without guessing.

## 2. Measure, when the branch stands alone

Skip this step when a stack exists or a pull request is open. Those rows need no number.

Run the commands in `references/measure-the-diff.md` and post the pair.

**Done when** the added and removed totals are printed, or the step is named as skipped.

## 3. Start that one skill

| State | What happens |
|---|---|
| One branch, no stack, no PR, **400 or under** each way | Start `/ship-stack` |
| One branch, no stack, no PR, **over 400** either way | Post the counts. Say to run `/split-pr`. Stop. |
| A stack exists, no PRs yet | Start `/ship-stack` |
| Any PR open on this branch or stack | Start `/pr-review` |
| Nothing committed and nothing in the working tree | Say so. Stop. |

Uncommitted changes are part of the size and part of the phase you are entering. `/ship-stack`
step 3 commits them.

An over-400 diff stops here. Cutting layers is the user's call, and `/split-pr` gates on their
approval anyway.

**Done when** exactly one skill has started, or the counts are posted with `/split-pr` named.

## Guardrails

The user's calls, handed over rather than taken:

- **Merging.** Report that a PR is mergeable; let them press it.
- **Marking a PR ready for review.**
- **Posting a comment or resolving a thread.** Draft, print, let them paste.
- **The default branch** takes no direct commits.

## Report

The phase and why, in two sentences. Then start the skill. Plain words, emoji. 🌝
