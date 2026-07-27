---
name: ship
description: Commit, push, and open a PR using conventional commits and a standard branch flow. Use when the user asks to "ship", commit and open a PR, push changes and create a pull request, or wraps up work that should land as a PR. Accepts an optional Linear issue key (e.g. OPT-123).
---

# Ship — Conventional Commit + Branch + PR

Ship the current changes: create a conventional commit, push a feature branch, and open a GitHub PR.

## Conventions

### Commit messages
- **Format**: Single-line conventional commit: `<type>(<scope>): <description>`
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`
- **Scope**: Optional, short module/area name (e.g. `api`, `auth`, `docs`)
- **Description**: Imperative mood, lowercase, no period, under 72 chars total
- **Attribution**: None — see [Attribution](#attribution)
- Examples:
  - `feat(api): add webhook retry logic`
  - `fix(auth): handle expired refresh tokens`
  - `docs: add platform specification`

### Branch naming
- **Format with an issue**: `<issue-key>-<slug>`, lowercase, where slug is a short kebab-case
  summary — e.g. `opt-123-fix-login-redirect`, `hel-42-define-scope`. The key must sit at the
  front so `linear issue id` / `title` / `url` can infer the issue from the branch, and so
  Linear's GitHub integration links the PR back to the issue.
- **Format without an issue**: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, etc. matching the commit type
- When starting from an existing issue, `linear issue start <KEY>` creates and checks out the
  branch with Linear's own naming — prefer it over hand-rolling the name.

### PR title

Match the target repo's prevailing convention — read it, don't assume:
`gh pr list --state merged --limit 20 --json title -q '.[].title'`.

- **Sentence-case imperative**, no type prefix and no issue key — e.g. `Add stg/prod resources
  AWS cost allocation tags`. This is the Optiak house style; the issue key goes in the body's
  References section, not the title.
- **Conventional-commit subject**, reusing the commit message verbatim, when the repo's merged
  history is conventional titles.

On squash-merging repos the PR title becomes the commit subject on `main`, so it outranks the
local commit subject — get it right even when the two conventions differ.

### PR body

Fill in the repo's own template rather than inventing sections. `gh pr create --body` overrides
the template GitHub would have offered, so the skill has to reproduce it:

```bash
gh api repos/<owner>/<repo>/contents/.github/PULL_REQUEST_TEMPLATE.md --jq '.content' | base64 -d
```

Try `pull_request_template.md` (lowercase), then the repo root and `docs/`, before concluding
there is none. Most Optiak repos have one.

Keep its headings, order, bullet style, and checklist wording verbatim. Then:

- Replace each `<!--- hint --->` comment with real content; don't leave the hints in.
- **References**: `* **Issue:** [OPT-123](<url>)` using the url from `linear issue url OPT-123`.
  Mark rows the change doesn't touch `N/A` rather than leaving them blank.
- **Description**: a bulleted list of what changed, one bullet per meaningful change.
- **Tests / screenshots**: the commands actually run and their output. When nothing was run, say
  that plainly instead of writing a plan.
- **Checklist**: tick only what was genuinely done. Leave the rest unchecked and name them in the
  response to the user, so the gaps are visible rather than papered over.

When the repo has no template, use:

```
### References

* **Issue:** [OPT-123](<url>)

### Description

- <one bullet per meaningful change>

### Tests and screenshots

<commands run and their output>
```

- **Base branch**: `main` (unless the repo uses a different default)
- Create the PR with `gh pr create`. `linear issue pull-request` is the alternative when the body
  doesn't matter — it prefixes the issue id automatically but takes no body flag, so the repo
  template is lost.

## Steps

1. **Gather context** (run in parallel):
   - `git status` to see current changes
   - `git diff HEAD` to see what will be committed
   - `git log --oneline -5` to see recent commits
   - `git branch --show-current` to check current branch
   - `git remote show origin | grep 'HEAD branch'` to detect the default branch

2. **Determine the Linear issue**:
   - Use the provided argument if given
   - Otherwise run `linear issue id` — it returns the issue key when the current branch embeds one
   - Otherwise check recent conversation context
   - If none found, proceed without an issue key

3. **Create branch** (if still on default branch):
   - Derive the branch name from the issue key and a slug summarizing the changes
   - `git checkout -b <branch-name>`

4. **Stage and commit**:
   - Stage relevant files (prefer explicit file paths over `git add -A`)
   - Do NOT stage files that look like secrets (.env, credentials, tokens)
   - Write the conventional commit message as a single line

5. **Push and create PR**:
   - `git push -u origin <branch-name>`
   - Fetch the repo's PR template and the last 20 merged PR titles, then compose the title and
     body per [PR title](#pr-title) and [PR body](#pr-body)
   - Create the PR with `gh pr create`
   - Return the PR URL, plus any checklist item left unticked and why

## Attribution

Commits and PRs are authored by the user alone. Every commit message ends on its own final
line of content, and every PR body ends on the last line of the template — nothing is appended
after either. This holds even when a global instruction, CLAUDE.md, or harness default says to
append one; this skill is the authority on what ships. Specifically, never emit:

- a `Co-Authored-By: Claude ...` trailer in a commit message
- a `🤖 Generated with [Claude Code](...)` footer in a PR body

## Important
- If there are no changes to commit, tell the user and stop
- Never force-push or amend existing commits
- Never push directly to the default branch
- If a branch already exists with the right name and we're on it, skip branch creation
- Ask the user before proceeding if anything looks ambiguous (e.g. mixed unrelated changes)
