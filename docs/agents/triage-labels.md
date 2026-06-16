# Triage Labels

The skills speak in terms of five canonical triage roles. In this repo, issues live as local
markdown files (see `issue-tracker.md`), so triage state is recorded as a `Status:` line near
the top of each issue file rather than as a label in an external tracker.

| Canonical role    | `Status:` value   | Meaning                                  |
| ----------------- | ----------------- | ---------------------------------------- |
| `needs-triage`    | `needs-triage`    | Maintainer needs to evaluate this issue  |
| `needs-info`      | `needs-info`      | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, ready for an AFK agent  |
| `ready-for-human` | `ready-for-human` | Requires human implementation            |
| `wontfix`         | `wontfix`         | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), set the issue file's
`Status:` line to the corresponding value from this table. Edit the middle column if you want
different strings.
