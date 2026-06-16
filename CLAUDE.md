# skills

Personal skill repository: mirror upstream skill repos, security-scan changes, and
agentically adapt them to my stack. See `PLAN.md` for the design.

## Agent skills

### Issue tracker

Issues and PRDs live as local markdown files under `.scratch/<feature-slug>/`. See
`docs/agents/issue-tracker.md`.

### Triage labels

Triage state is a `Status:` line in each issue file, using the five canonical role strings
(`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root (created lazily). See
`docs/agents/domain.md`.
