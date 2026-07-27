---
name: "linear"
description: "CLI for Linear. Use whenever an agent needs to create, query, update, or link Linear issues, projects, or documents from the terminal, look up team/user/workflow-state info, or run a raw GraphQL query against the Linear API — even if the user just says 'file a Linear issue' or 'check my Linear tickets' without naming the CLI."
---

# linear — The Linear CLI

Unofficial but full-featured CLI for Linear. Wraps the Linear GraphQL API with git/branch-aware
helpers on top (e.g. resolving the current issue from the branch name).

- **Repo**: https://github.com/schpet/linear-cli
- **Author**: schpet

## Prerequisites

`linear --version` — if missing, tell the user to install it: `brew install schpet/tap/linear`.
`linear auth whoami` — if it fails, tell the user to run `linear auth login`. Credentials live in
the system keyring, not a config file; `linear auth list` shows configured workspaces.

Every command accepts `--workspace <slug>` to target a workspace other than the default.

## Running non-interactively

This skill names commands, not their full flag sets — run `linear <command> --help` to get the
flags before composing a non-trivial invocation. The ones that matter outside a TTY:

- **`--no-interactive`** on `linear issue create`: fail on a missing field instead of prompting
  for it. Pass every field you intend to set as a flag. (`issue update` takes flags only and
  never prompts, so it needs no equivalent.)
- **`--no-pager`** on `issue mine`, `issue query`, and `issue view`: these page long output
  automatically.
- **`-j`/`--json`** on `issue view` and `issue query` for machine-readable output. Other list
  commands (`issue mine`, `project list`, `team list`, …) print human-formatted text only — use
  `linear api` when you need structured data they don't expose.
- **`--description-file <path>`** instead of `-d/--description` on `issue create`/`update` for
  anything multi-line or markdown, avoiding shell-quoting breakage.

Discover the values that name-based flags expect rather than guessing them: `linear team states`
for `--state`, `linear label list` for `--label`, `linear user list` for `--assignee`.

## Key Commands

### Issues (`linear issue` / `linear i`)

```bash
linear issue mine                    # list your issues (aliases: list, l)
linear issue query                   # query issues with structured filters (alias: q)
linear issue create                  # create an issue (interactive prompts for missing fields)
linear issue view ENG-123            # view issue details (alias: v; default action)
linear issue update ENG-123          # update fields on an issue
linear issue delete ENG-123          # delete an issue (alias: d)

linear issue comment add ENG-123     # add a comment or reply (--attach renders images inline)
linear issue comment list ENG-123    # list comments on an issue
linear issue comment update <id>     # edit a comment (also: delete <id>)

# Git-branch-aware helpers — infer the issue from the current branch when the
# branch name embeds an issue id (e.g. eng-123-fix-thing):
linear issue id                      # print the issue id for the current branch
linear issue title                   # print just the title
linear issue url                     # print the issue URL
linear issue describe                # print the title plus a Linear-issue trailer (for commit messages)
linear issue start ENG-123           # start work on an issue
linear issue pull-request ENG-123    # create a GitHub PR pre-filled with issue details (alias: pr)
linear issue commits ENG-123         # show all commits for an issue (jj/Jujutsu only)

linear issue attach ENG-123 ./file   # attach a file as a sidebar link (not inline)
linear issue link ENG-123 https://... # link a URL to an issue
linear issue relation                # manage issue relations/dependencies
linear issue agent-session           # manage agent sessions for an issue
```

### Teams, users, labels (`team`/`t`, `user`/`u`, `label`/`l`)

```bash
linear team list                     # list teams
linear team create                   # also: delete <teamKey>
linear team id                       # print the configured team id
linear team members [teamKey]        # list team members
linear team states [teamKey]         # list workflow states — the names -s/--state accepts
linear team autolinks                # configure GitHub repo autolinks for this team's prefix
linear user list
linear label list                    # also: create, delete <nameOrId>
```

### Projects, cycles, milestones, initiatives

```bash
linear project list                  # alias: p
linear project-update create         # post a project status update (alias: pu)
linear cycle list                    # alias: cy
linear milestone list                # alias: m
linear initiative list               # alias: init
linear initiative-update create      # alias: iu
```

### Documents (`document` / `docs` / `doc`)

```bash
linear document list                 # alias: l
linear document view <id>            # alias: v
linear document create               # alias: c
linear document update <documentId>  # alias: u
linear document delete [documentId]  # move a document to trash (alias: d)
```

### Raw API access

```bash
linear schema                        # print the full GraphQL schema to stdout
linear api '{ viewer { id name } }'  # run a raw GraphQL query
linear api query.graphql --variable key=value --paginate
```

`linear api` accepts `--variable key=value` (repeatable, coerces booleans/numbers/null,
`@file` reads a value from a path), `--variables-json '{...}'`, `--paginate` (auto-paginate a
connection via cursor pagination), and `--silent` (suppress output, exit code still reflects
errors). Use `linear schema` first to look up field/type names before writing a query.

### Per-project config

```bash
linear config                        # interactively generate .linear.toml
```

`.linear.toml` in a project root can pin things like the default team, so issue lookups and
`linear issue create` don't need `--workspace`/team flags repeated on every call.

## Notes

- The git-branch-aware commands (`id`, `title`, `url`, `describe`, `start`, `pull-request`,
  `commits`) infer the issue from the current branch only when its name embeds a Linear issue
  id (e.g. `eng-123-...`) — otherwise pass the issue id explicitly.
- Aliases are listed inline with each command above. Write commands out in full when explaining
  them, so `linear project-update` reads as itself rather than as `linear pu`.
