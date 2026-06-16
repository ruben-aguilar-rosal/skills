# Issue tracker: Jira

Issues for this repo live in Jira on the **Tech Platform (TP)** project:
https://ailylabs.atlassian.net/jira/software/c/projects/TP

PRDs live in **Product Discovery (TI / Polaris)**:
https://ailylabs.atlassian.net/jira/polaris/projects/TI

Use the [`jira` CLI](https://github.com/ankitpokhrel/jira-cli) for TP. One-time setup:
`jira init` (needs a Jira API token; config is written to `~/.config/.jira/.config.yml`,
token read from the `JIRA_API_TOKEN` env var).

## Conventions (TP — issues)

- **Create an issue**: `jira issue create -p TP -t Task -s "<summary>" -b "<body>" --no-input`
  (issue types: `Task`, `Story`, `Bug`).
- **Read an issue**: `jira issue view TP-1234 --comments 10 --plain`
- **List issues**: `jira issue list -p TP -s "<status>" --plain` (filter by label with `-l <label>`)
- **Comment**: `jira issue comment add TP-1234 "<body>"`
- **Apply a label**: `jira issue edit TP-1234 --label "<label>" --no-input`
  (remove via `--label "-<label>"` or the web UI)
- **Move status / reject**: `jira issue move TP-1234 "Done"` (or `"Rejected"`, `"In Progress"`, …)

Workflow statuses on TP: `Backlog` → `To Do`/`Open` → `In Progress` → `In Review` → `Done`
(also `On Hold`, `Rejected`).

Infer the project from the `-p TP` flag; the CLI targets the configured instance.

## PRDs (TI — Product Discovery / Polaris)

⚠ `jira-cli` does **not** support Polaris / Product Discovery boards. For PRDs, create an
**Idea** in TI via the Atlassian MCP tools (`jira_create_issue` with `project_key=TI`,
`issue_type=Idea`) or the Jira REST API. TI statuses run `Discovery` → `Ready for delivery`.

## When a skill says "publish to the issue tracker"

Create a TP issue: `jira issue create -p TP -t <Task|Story|Bug> -s "<summary>" -b "<body>" --no-input`.

## When a skill says "fetch the relevant ticket"

Run `jira issue view <KEY> --comments 10 --plain`.

## When a skill says "create a PRD"

Create an Idea in TI Product Discovery (see above) — not via the `jira` CLI.
