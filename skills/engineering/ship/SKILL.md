---
name: ship
description: Commit, push, and open a PR using conventional commits and a standard branch flow. Use when the user asks to "ship", commit and open a PR, push changes and create a pull request, or wraps up work that should land as a PR. Accepts an optional Jira ticket key (e.g. TP-1234).
---

# Ship — Conventional Commit + Branch + PR

Ship the current changes: create a conventional commit, push a feature branch, and open a GitHub PR.

## Conventions

### Commit messages
- **Format**: Single-line conventional commit: `<type>(<scope>): <description>`
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`
- **Scope**: Optional, short module/area name (e.g. `api`, `auth`, `docs`)
- **Description**: Imperative mood, lowercase, no period, under 72 chars total
- **Co-author**: Always append the co-author trailer on a separate line
- Examples:
  - `feat(api): add webhook retry logic`
  - `fix(auth): handle expired refresh tokens`
  - `docs: add platform specification`

### Branch naming
- **Format**: `<ticket-key>/<slug>` where slug is a short kebab-case summary
- If a Jira ticket key is provided (via argument or detected from context), prefix the branch with it
- Examples: `tp-3079/define-scope`, `ais-42/fix-login-redirect`
- If no ticket: use `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, etc. matching the commit type

### PR creation
- **Title**: Same as the commit message (the conventional commit line)
- **Body**: Use this template:

```
## Summary
<1-3 bullet points describing what changed and why>

## Jira
<Link to Jira ticket if available, otherwise omit this section>

## Test plan
<Bulleted checklist of how to verify the changes>
```

- **Base branch**: `main` (unless the repo uses a different default)
- If the Jira ticket key is available, include it in the PR title as a suffix: `docs: add platform specification [TP-3079]`

## Steps

1. **Gather context** (run in parallel):
   - `git status` to see current changes
   - `git diff HEAD` to see what will be committed
   - `git log --oneline -5` to see recent commits
   - `git branch --show-current` to check current branch
   - `git remote show origin | grep 'HEAD branch'` to detect the default branch

2. **Determine ticket key**:
   - Use the provided argument if given
   - Otherwise check the current branch name for a ticket pattern (e.g. `tp-3079/...`)
   - Otherwise check recent conversation context
   - If none found, proceed without a ticket key

3. **Create branch** (if still on default branch):
   - Derive the branch name from the ticket key and a slug summarizing the changes
   - `git checkout -b <branch-name>`

4. **Stage and commit**:
   - Stage relevant files (prefer explicit file paths over `git add -A`)
   - Do NOT stage files that look like secrets (.env, credentials, tokens)
   - Write the conventional commit message as a single line
   - Always include the co-author trailer:
     ```
     Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
     ```

5. **Push and create PR**:
   - `git push -u origin <branch-name>`
   - Create PR with `gh pr create` using the title and body format above
   - Return the PR URL to the user

## Important
- If there are no changes to commit, tell the user and stop
- Never force-push or amend existing commits
- Never push directly to the default branch
- If a branch already exists with the right name and we're on it, skip branch creation
- Ask the user before proceeding if anything looks ambiguous (e.g. mixed unrelated changes)
