---
name: start-ticket
description: >
  Build the Orca workspace for a Linear ticket and hand it to a working agent: clone the
  repositories the ticket names, open an Orca group with a folder workspace linked to the
  issue, and start optiak-work inside it. Use when starting or picking up a
  ticket, when setting up a workspace for one, or when a planning session lands a ticket set
  and one of them begins now.
---

# start-ticket

A Linear key becomes a **workspace**: one folder, one clone per repository, and a **main agent**
running in an Orca folder workspace that spans the lot.

You bring judgement — which repositories, what to call the group. `scripts/optiak_workspace.py`
brings the mechanics.

Runs from anywhere, including a planning session that has just filed the ticket.

## 1. Read the ticket

```bash
orca linear issue OPT-1102 --full --json
```

Scope is the section that matters: it names the files, and the files name the repositories.

A Scope that names no file means the ticket is not ready. Run `/clear-triage` on it and stop.

**Done when** Why, Scope and Done when have been read.

## 2. Name the repositories

One repository per line of Scope that touches code. Bare names mean the `optiak` org; write
`owner/name` for anything else.

Name only what the Scope justifies. A spare clone is a place the main agent wanders into.

**Done when** every repository traces back to a named Scope line, and every code-touching Scope
line has a repository.

## 3. Choose the label

Two to four words for the sidebar. The key is prefixed for you, so the group reads
`OPT-1102 - DBT Tables`.

| Ticket title | Label |
| --- | --- |
| Point the dbt models at the zero-ETL events table | `DBT Tables` |
| Add ECS deployment monitoring to the platform | `ECS Monitoring` |
| Fix the Redshift connection pool leak | `Pool Leak` |

State the label to the user before you build anything. They read it every day.

**Done when** the label is under five words and names the work.

## 4. Build the workspace

```bash
python3 ~/.claude/skills/start-ticket/scripts/optiak_workspace.py OPT-1102 \
  --label "DBT Tables" \
  --repo optiak --repo iac-infra \
  --json
```

Clones each repository, runs `optiak-repo-setup` over all of them in one call, creates the
group, and creates the folder workspace linked to the issue. It prints `path` and
`worktreeSelector`.

The clones are not registered as Orca projects. The folder workspace spans the whole folder, so
the main agent reads every repository from there, and the sidebar stays at one row per ticket.

Re-running reuses the group, the workspace and any clone already on disk, so a retry after a
failed clone is safe.

**Done when** the script exits 0 and you hold its `worktreeSelector` and `path`.

## 5. Start the main agent

```bash
orca terminal create \
  --worktree folder:331f9b38-... \
  --title "OPT-1102" \
  --command "optiak-work OPT-1102 --workspace /Users/raguilar/Developer/optiak/workspace-opt-1102" \
  --focus
```

`--workspace` tells `optiak-work` the checkout is done, so the session opens on the ticket.
Everything else about `optiak-work` holds: the behaviour rules stay pinned in the system
prompt, and `optiak-work OPT-1102 --continue` resumes this session in the same folder.

Append `--plan <name>` when the ticket has a plan, and `--base <ticket-or-repo=ref>` when it
branches off other work. Both are `optiak-work` arguments; `optiak-work --help` is the source
of truth.

Pass the plan by its bare filename, `--plan analytics-plan.md`. `optiak-work` resolves it under
the plans folder, so a full path repeats what the command already knows.

Keep `--focus` when the user asked to start now; drop it to leave them where they are.

**Done when** the terminal handle comes back.

## 6. Report and hand over

```
OPT-1102  Point the dbt models at the zero-ETL events table
Group     OPT-1102 - DBT Tables
Repos     optiak, iac-infra
Agent     running in ~/Developer/optiak/workspace-opt-1102
Editor    zw OPT-1102
```

`zw` is the shell command that opens the workspace folder in Zed. Name it in the report so the
user has it to hand; leave it to them to run.

The main agent shows its own plan card next and waits. Return control to the user there.

**Done when** the card is printed and the turn ends.

## The private surface

Orca publishes no CLI command for groups or folder workspaces. The script reaches the runtime
socket directly, using the one-line JSON protocol the `orca` CLI itself uses and the token in
`~/Library/Application Support/Orca/orca-runtime.json`. Methods: `projectGroup.list`,
`projectGroup.create`, `folderWorkspace.list`, `folderWorkspace.create`.

An Orca release can change them. The script raises on the first bad reply rather than half-build
a workspace, and the clones survive on disk either way.

When a group or workspace call fails, tell the user plainly. The clones are on disk and usable
straight away with `zw OPT-1102`, so the work is not blocked — only the Orca row is missing.
