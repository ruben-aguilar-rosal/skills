# skills

Personal skill repository: mirror upstream skill repos, security-scan changes, and
agentically adapt them to my stack. See `PLAN.md` for the design.

## Agent skills

### Issue tracker

Issues live in Jira project **TP** (Tech Platform), managed with the `jira` CLI. PRDs live
in **TI** Product Discovery (Polaris), managed via the Atlassian MCP tools / REST. See
`docs/agents/issue-tracker.md`.

### Triage labels

Four Jira labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`) plus
`wontfix` → the `Rejected` status on TP. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root (created lazily). See
`docs/agents/domain.md`.
