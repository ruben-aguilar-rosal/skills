---
name: ship-stack
description: >
  Sync, verify, push, and open every pull request as a draft. Use after the layers exist, or
  when a single branch is under the size limit and needs its pull request opened.
---

# ship-stack

Open the draft pull requests, then stop.

Rules and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).

Works on a **stack** or a **single branch**. Same steps; commands differ where marked.

## 1. Sync

```bash
git fetch origin
BASE=$(git remote show origin | sed -n 's/.*HEAD branch: //p')
git rev-list --left-right --count origin/$BASE...HEAD    # "<behind> <ahead>"
```

Zero behind: go to step 2. Otherwise commit first, then integrate:

- **Stack:** `gh stack sync`. On exit 3, read `../gh-stack/references/troubleshooting.md`.
- **Single branch, never pushed:** `git rebase origin/$BASE`.
- **Single branch, already pushed:** `git merge origin/$BASE`. A rebase needs a force-push.

On a conflict, reach for `resolving-merge-conflicts`.

**Done when** zero behind.

## 2. Verify

**Hooks.** A fresh clone has no hook installed, so the formatter never ran.

```bash
if [ -f prek.toml ] || [ -f .pre-commit-config.yaml ]; then
  uvx prek install
  uvx prek run --from-ref origin/$BASE --to-ref HEAD --show-diff-on-failure
fi
```

`prek` is not on the PATH; `uvx` fetches it. Commit anything the hooks rewrite.

**Checks.** Discover them from `package.json` scripts, `Makefile`, `pyproject.toml` and
`.github/workflows/*.yml`. Run the narrowest set covering the diff plus whatever the default branch
moved. Lint and type-check count. Keep the commands and their output for step 5.

A failure caused by the sync belongs to this run. A failure needing someone else's change reworked,
or a design decision, goes to the user.

On a docs-only change, say so instead of inventing a test.

**Done when** hooks are clean or their rewrites committed, every command is recorded with its
output, and failures are fixed or handed over by name.

## 3. Commit what is left

Stage explicit paths. One conventional line: `<type>: <description>`, under 72 characters, lower
case, imperative, no trailing dot. Commits are signed. Nothing is appended: no co-author trailer,
no generated-with footer.

**Done when** `git status --porcelain` is empty.

## 4. Open the drafts

- **Stack:** `gh stack submit --auto --remote origin`.
- **Single branch:** `git push -u origin <branch>` then `gh pr create --draft --base $BASE`.

`gh stack` writes placeholder titles and bodies. Step 5 replaces them.

**Done when** every layer has a pull request number.

## 5. Write the title and body

`--body` overrides the template GitHub would offer, so fetch and reproduce it:

```bash
gh api repos/<owner>/<repo>/contents/.github/PULL_REQUEST_TEMPLATE.md --jq .content | base64 -d
```

Try `pull_request_template.md` lower case, then the repo root and `docs/`.

Per pull request, `gh pr edit <n> --title ... --body-file ...`:

- **Title:** `<type>: <description>`, under 72 characters, lower case, imperative, no trailing dot.
  A scope is allowed and rarely needed. No ticket key. On a stack, say what **that layer** does.
- **References:** `* **Issue:** [OPT-123](<url>)` from `linear issue url OPT-123`. Untouched rows
  get `N/A`.
- **Description:** first sentence says why. Then one bullet per real change. Length per
  `optiak-writing` `B5`.
- **Tests:** the step 2 commands and what they printed.
- **Checklist:** tick only what was done. Name the rest in your report.

Run the title and body through `unslop` and `asd-ste100-skill` before sending. Emoji welcome. 🌝

**Done when** every pull request has a real title and a filled template, no hint comments left.

## 6. Report

Per pull request: number, title, URL, `+added -removed`. Then the user's two jobs: read the drafts,
and run `/pr-review` once checks and bots have reported.

Every pull request stays a draft. 🚀
