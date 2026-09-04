---
name: clear-triage
description: >
  Bring a Linear ticket in Triage up to the Optiak standard and move it to Backlog: fill the
  missing fields, write the Done when, then move it on approval. Use when a ticket sits in
  Triage, when the Triage queue needs draining, or when the user asks whether a ticket is ready
  to pick up.
---

# clear-triage

Triage is where a ticket waits. This skill is how it leaves.

`optiak-tracker` holds the five conditions and the fields. `/file-issue` holds the body format
and the EARS shapes. This file holds the **gate**: read, fill, approve, move.

One ticket per pass. A queue is passes in a row.

## 1. Take the queue

A key given is that ticket, whatever state it is in. No key is the whole Triage queue.

```bash
linear issue query --team OPT --state triage --limit 0
```

Print the keys in the order you will work them, oldest first. Bot-filed tickets, such as a
dependency upgrade or a scanner finding, go last.

**Done when** the list of keys is printed and the user has not renamed the order.

## 2. Read the ticket against the five conditions

```bash
linear issue view OPT-936
```

One row per condition from `optiak-tracker`. `missing` is a value.

```
Priority   3 Medium
Estimate   missing
Project    missing
Type       Bug
Done when  missing
```

**Done when** all five rows carry a value or the word `missing`.

## 3. Fill the gaps

Only the `missing` rows. A row that already has a value is somebody's decision; leave it.

- **`Done when` missing.** Run `/file-issue` steps 2 to 5 on the existing body: verify every
  claim against the code, size it, draft `Why` / `Scope` / `Done when` / `Out of scope`, lint it.
  Keep the reporter's words where they are checkable.
- **Estimate missing.** Points per `optiak-tracker`. At 5 or more, propose the split instead and
  stop at step 4 with the split as the proposal.
- **Project missing.** `linear project list --team OPT`. Propose one; the user names it at
  step 4. Unplanned work is usually OE Backlog.
- **`Type` missing.** One of `Bug`, `Feature`, `Improvement`, `Chore`.
- **Priority missing.** Propose one, with one clause naming who is blocked. `1 Urgent` is the
  user's call; propose it and let them say the word.

A ticket you cannot bring up to standard keeps its place. Name it, say which condition you could
not answer and what you would need, and move to the next key.

**Done when** every `missing` row carries a proposed value, or the ticket is named as blocked.

## 4. Show the card, then stop

`/file-issue` step 6's card, plus what changes:

```
Changes    Estimate  missing → 2
           Project   missing → OE Backlog
           Done when missing → 3 lines, below
State      Triage → Backlog
```

**Your message ends with the card.** Wait for the word.

**Done when** the user has answered.

## 5. Apply and move, in one call

```bash
linear issue update OPT-936 --description-file /tmp/ticket.md \
  --project "<project>" --label "<Type>" --priority <n> --estimate <n> \
  --state Backlog
```

The state moves in the same call as the fields, so no pass leaves a Backlog ticket that fails a
condition.

A ticket already past Triage keeps its state: drop `--state` and set the fields only. Somebody
scheduled it, and that is their call.

**Done when** `linear issue view OPT-936` shows `Backlog` and all five conditions filled.

## 6. Next, or report

More keys left: go to step 2 with the next one.

The queue is done: one line per ticket, the key, the new state, and the conditions you filled.
Then the tickets still in Triage and what each one is waiting on. 🎫

A label that repeats a field, such as a `P0` or `P1` label next to the priority field, goes in the
report as a note. Retiring a label is the user's call.
