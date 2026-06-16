# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the
actual vocabulary used in this repo's issue tracker (Jira project **TP**).

| Canonical role    | In TP                   | Meaning                                  |
| ----------------- | ----------------------- | ---------------------------------------- |
| `needs-triage`    | label `needs-triage`    | Maintainer needs to evaluate this issue  |
| `needs-info`      | label `needs-info`      | Waiting on reporter for more information |
| `ready-for-agent` | label `ready-for-agent` | Fully specified, ready for an AFK agent  |
| `ready-for-human` | label `ready-for-human` | Requires human implementation            |
| `wontfix`         | **status** `Rejected`   | Will not be actioned                     |

Notes:

- `wontfix` is a workflow **status transition**, not a label:
  `jira issue move <KEY> "Rejected"`.
- The other four are Jira **labels**: `jira issue edit <KEY> --label "<name>" --no-input`.
  Jira creates labels on first use — no pre-configuration needed.

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the
corresponding entry from this table. Edit the middle column to match whatever vocabulary you
actually use.
