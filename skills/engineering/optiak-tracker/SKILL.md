---
name: optiak-tracker
description: >
  Where Optiak work is tracked and what a ticket must carry: Linear, team OPT, the linear CLI,
  Triage on entry, a project, an estimate and a Done when in EARS. Use when filing, reading,
  splitting or labelling a ticket, when a review finding is not fixed, and when a skill asks
  where issues live.
---

# optiak-tracker

Where Optiak work is tracked, and what a ticket must carry.

`/file-issue` writes and files one ticket. It holds the templates, the EARS shapes and the
checks. This file holds the facts it works from.

Rules and their reasons: `/Users/raguilar/Developer/optiak/linear-ticket-hygiene.md`.

## Where

Linear. Workspace `optiak`, team `OPT`. Ticket ids read `OPT-<number>`.

The `linear` CLI is installed and authenticated. GitHub Issues are not used here.

```bash
linear issue view OPT-870
linear issue query --team OPT --assignee me
linear project list --team OPT
linear team states
linear label list
```

Read the valid values from those commands. There are two teams, so `--team` is not optional.

Put the ticket id in the branch name and in the commit message. Linear links the work from that.

Pull requests are not a request surface. Work is proposed and tracked in Linear, and a pull
request implements a ticket that already exists.

## What a ticket carries

A ticket found in passing enters **Triage**: a deferred review comment, a bug seen while doing
something else, anything one `/file-issue` run produces.

A ticket leaves Triage for **Backlog** when all five are true:

1. A priority. Not `No priority`.
2. An estimate. One point is one uninterrupted day. An agent-pickable ticket is 1, 2 or 3.
3. A project.
4. A `Type` label: `Bug`, `Feature`, `Improvement` or `Chore`.
5. A `Done when` section, where each line answers true or false on its own.

`/clear-triage` fills the gaps and makes that move, behind one approval. Work that comes out of a
plan already meets all five, so `/land-tickets` files it straight to **Backlog**.

**`Done when` is the spec.** A review checks the diff against that section. Older tickets call it
`Acceptance criteria`; read that as the same section and write the new name.

## State

Who moves a ticket, and when:

| Move | Who |
| -- | -- |
| Triage → Backlog | `/clear-triage`, on the user's approval |
| Backlog or Todo → In Progress | the agent, before the first line of code |
| In Progress → In Review | the pull request, when it opens |
| In Review → Done | the pull request, when it merges |
| anything → Canceled or Duplicate | the user |

```bash
linear issue update OPT-936 --state 'In Progress'
```

**`In Progress` is the one an agent sets.** A ticket sitting in Backlog with a branch and a diff
against it reads as untouched, and the board is how everybody else sees what is being worked.

The pull request owns the two states after it. Setting `In Review` by hand puts a second answer
next to the one the integration writes.

## Project

Every ticket carries one, and the user picks it every time. `linear project list --team OPT`
prints the live list; read it rather than reusing a name you remember, because projects get
renamed and archived.

Work that comes out of a plan or a spec belongs to that work's project. Unplanned work — a
review comment you deferred, a bug you saw in passing — usually goes to **OE Backlog**, slug
`ee7ab66addb6`. Propose it; let the user say the word.

## Labels

- **A field is not a label.** Priority, estimate, state and project are fields. A label that
  repeats a field creates a second answer, and then neither is trusted.
- **One label per group.** A group answers one question. Two labels from one group means two
  tickets.
- **`Type` is the one fixed group.** Required, four values, and it picks the template.
- A date or a release belongs to a project or a milestone.
- A label you cannot define in one line is dead. Retire it.

Some vendored skills carry their own label vocabulary, such as `needs-triage` or
`ready-for-agent`. Those repeat the state field. Set the state.

---

## B3 — A finding you did not fix, with nowhere to go

**Rule.** Every review finding you do not fix gets an entry in `FOLLOW-UPS.md`, with its
disposition and its reasoning. Answering it only in the review thread is not enough.

**Why.** A merged pull request's threads stop being read. Nobody greps them, and the
tracker does not know they exist, so a real defect that somebody correctly judged out of
scope becomes indistinguishable from one nobody noticed.

The reasoning is the perishable part. You hold the whole argument — what you checked, which
alternatives you rejected and why — for as long as you are working the ticket, and then it
is gone. An entry written a day later is a bullet point. An entry written at the moment of
the decision is the argument.

**Do not write.**

- A review reply that settles the matter and leaves no trace anywhere else.
- `TODO` or `FIXME` in the code as the record. It is not tracked, and B2 forbids the
  ticket key that would make it followable.
- An entry with no disposition, or a disposition with no reasoning: *"deferred — out of
  scope"* tells the next reader nothing they could act on or disagree with.
- A `defer` when you cannot actually name the fix. That is a `decide`, and dressing a
  question up as a task means somebody implements your guess a month later, believing it
  was reviewed.

**Write instead.** An entry in `FOLLOW-UPS.md` in that file's format, plus the constraint
next to the code where a reader could otherwise be misled — the constraint, not the ticket
key, per B1 and B2.

**Allowed.**

- Answering in the review thread **as well**. It is the right place to reply to the
  reviewer; it is not a record.
- `fixed` and `false-positive` entries of one line. They die with the pull request, so
  there is nothing to carry forward.
- No entry at all for a finding you fixed **before** anyone reviewed it. This behaviour is
  about findings you leave behind, not about your working notes.

**Check yourself.** Six months from now, with this pull request merged and its threads
unread, how would somebody find out that this is known and deliberate? If the only answer
is "read the review thread", write the entry.

**Related.** `FOLLOW-UPS.md` (the format and the two questions that pick a disposition),
`pr-review` (which puts one verdict on every comment and writes the entry at that moment),
`check-followups.py` (the check that fails while a comment has no entry).
