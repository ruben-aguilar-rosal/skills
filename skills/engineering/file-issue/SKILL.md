---
name: file-issue
description: >
  Write and file a Linear ticket to the Optiak standard. Use when work is found and not done
  now: a deferred review comment, a bug seen in passing, a next step out of a plan, or the
  user saying file this, raise a ticket, or open an issue.
---

# file-issue

One ticket per run. It lands in **Triage** and nowhere else.

Rules and their reasons:
[Linear ticket hygiene](https://app.notion.com/p/Linear-ticket-hygiene-3c65b2a0c5b081fdb298e8bf2a907fd6).

The `linear` skill holds the CLI. `optiak-tracker` holds the fields, the projects and the
labels. This file holds how to write one.

The user's calls, handed over rather than taken: **closing or cancelling one**, **deleting one**,
**setting priority 1 Urgent**.

A ticket leaves Triage through `/clear-triage`, which fills the gaps first.

## 1. Name the work

Take it from the conversation, a file the user names, a `defer` verdict in `/pr-review`, or an
existing ticket that does not meet the standard. An existing ticket is an **update**: same
steps, different step 7.

Answer three questions before you write anything:

- What changes? One sentence, present tense.
- Who is blocked, and what breaks in a month if nobody does it?
- Is it a `Bug`, a `Feature`, an `Improvement`, or a `Chore`?

No cost, no ticket. Say so and stop.

**Done when** you can state the change in one sentence under 70 characters.

## 2. Verify every claim about the code

Run the checks. Do not describe code you did not open.

```bash
git rev-parse --short HEAD
git branch --show-current
grep -rn '<symbol>' <path>
```

Build the table. One row per claim. Head it with the commit, never a bare branch name.

```markdown
## Verified against `<short sha>` (`<branch>`)

| Claim | Check | Result |
| -- | -- | -- |
```

A claim you cannot check keeps the word `unverified` next to it. Do not drop it and do not
dress it up.

**Done when** every claim carries a check or the word `unverified`.

## 3. Size it

Estimate in points, per `optiak-tracker`. An agent-pickable ticket is **1, 2 or 3**.

At 5 or more, split it into sub-issues, each with its own `Done when`. File the parent at 0
points and run this skill again per child.

**Done when** the estimate is 3 or less, or the split is listed.

## 4. Draft it

`Bug` takes the bug template. Everything else takes this one.

```markdown
## Why

<Two or three sentences. The cost today.>

## Scope

- <Real paths. One bullet per change.>

## Done when

- [ ] <EARS shape. Answers true or false on its own.>

## Out of scope

- <What a reader would assume is included and is not.>
```

Bug template:

```markdown
## What happens
## Why it is bad
## A bad case
## How likely
## Steps to reproduce
## Expected
## Actual
## Environment
```

Add `## References` for plans, PRs and dashboards. Add `## Open questions` for what the
ticket cannot answer. Add a user story only when a named user role changes what it can do.

Write every `Done when` line in one of the five EARS shapes:

| Shape | Pattern |
| -- | -- |
| Always | The system shall <action> |
| On an event | **When** <trigger>, the system shall <action> |
| During a state | **While** <state>, the system shall <action> |
| On a fault | **If** <condition>, then the system shall <action> |
| Behind a flag | **Where** <feature is on>, the system shall <action> |

Ask for the fault shape every time. It is the one that gets forgotten.

Name the command that proves it: `make lint`, `uv run pytest tests/x`. Skip anything
`CLAUDE.md` or `AGENTS.md` already carries. Attach the screenshot rather than describe it.

**Done when** all four required sections carry content, every `Done when` line answers true
or false, and `Out of scope` is filled in.

## 5. Lint it

```bash
f=/tmp/ticket.md
grep -c '—' $f
grep -o -i -E 'leverage|robust|seamless|comprehensive|holistic|crucial|pivotal|streamline|utilize|facilitate|delve|underscore|landscape' $f
grep -n -E '^#+ *(Overview|Summary|Introduction|Background|Conclusion)' $f
wc -w $f
```

Every count is 0. Word count is under 400, or the excess is tables, commands and output.

Also by eye: the first line does not repeat the title, no number you did not measure,
active voice, one idea per sentence. Emoji are allowed; they must not carry meaning a
field already carries.

**Done when** every check returns 0 and the body carries no prose you cannot check.

## 6. Show the card, then stop

```
<title>

Type       <Bug | Feature | Improvement | Chore>
Labels     <Type, plus at most one from each other group>
Project    ?  <your pick> — <one clause: why this one>
              <two other candidates, or: OE Backlog for unplanned work>
Priority   <1 Urgent | 2 High | 3 Medium | 4 Low>  <one clause: who is blocked>
Estimate   <0 | 1 | 2 | 3>  <one clause>

<the body>
```

**The project is always a question.** Run `linear project list --team OPT` and read what comes
back, because projects get renamed and archived. Offer your pick with the nearest alternatives
and let the user name it. A ticket in the wrong project is invisible to the people who own that
work, and nobody goes looking for it.

Your message ends with the card. Wait for the word.

**Done when** the user has answered, and the answer names the project.

## 7. File it

**A new ticket:**

```bash
linear issue create --no-interactive --team OPT \
  --title "<title>" --description-file /tmp/ticket.md \
  --state Triage --project "<project>" --label "<Type>" [--label "<other>" ...]
```

**An existing ticket**, brought up to standard:

```bash
linear issue update OPT-936 --title "<title>" --description-file /tmp/ticket.md \
  --project "<project>" --label "<Type>" --priority <n> --estimate <n>
```

Leave the state alone on an update. The ticket is somebody's; you are fixing the body and the
fields they approved, not re-triaging their work.

`optiak-tracker` names the team, how the project is picked, and the commands that print the
valid values. Read them; do not guess. Set priority and estimate with `linear issue update`.

**Done when** `linear issue view <key>` shows the approved body, the project, the `Type` label,
the priority and the estimate.

## Report

The identifier, the URL, and the one sentence from step 1. Plain words, emoji. 🎫
