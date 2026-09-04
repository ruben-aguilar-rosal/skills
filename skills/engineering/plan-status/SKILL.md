---
name: plan-status
description: >
  Status board for a plan: the overview, its Linear tickets with a one-line description, the
  blocking graph, and what can be picked next. Use when the user asks where a plan stands, what
  is left, what is ready, what is blocked, or asks to check a plan file against Linear.
---

# plan-status

A plan file holds the reasoning. Linear holds state and blocking relations. This skill reads both
and prints one board.

Scope is **pending** unless the user asks for `all`. Pending is every ticket not Done and not
Canceled.

`status.py` does the query, the graph and the frontier. Read the plan file for the parts a graph
cannot carry.

## 1. Find the plan and its tracker

A path given is the plan. A topic given resolves under `~/Developer/optiak/plans/`. Neither given
means ask which plan, listing what is there.

```bash
ls ~/Developer/optiak/plans/*.md
grep -n 'Last updated\|Tracking:' <plan>
```

The `Tracking:` line carries the Linear project URL and the milestone name. The project id is the
last hyphenated segment of the project slug: `platform-core-8d64c4c8c464` is `8d64c4c8c464`.

No `Tracking:` line means the plan is not landed in Linear. Print the overview from step 2, say
which tickets the file names, and stop. `/land-tickets` is the next step there.

**Done when** the project id and the milestone name are both quoted back.

## 2. Print the overview

Five lines at most, from the plan file: what the work changes, what is in flight, what the
critical path is, and the `Last updated` date.

The plan file is the only source for these. A number you take from it carries its date.

**Done when** a reader who has never opened the plan knows what it is for.

## 3. Run the board

```bash
python3 <skill-dir>/status.py \
  --project 8d64c4c8c464 \
  --milestone "Analytics on Redshift - Feature Parity & Cutover" \
  --scope pending
```

Print its output as it comes. It is already a table, a graph and a frontier.

**Done when** the three sections are printed and the milestone name matched issues.

## 4. Check the pickable list against the plan's prose

A ticket with no open blocker can still be gated by a sentence somebody wrote instead of a
relation. Grep the plan for every key the script called pickable.

```bash
grep -n 'OPT-810\|OPT-819\|OPT-828' <plan>
```

Read what the file says about each. A gate written as prose moves that key out of `pickable` and
into a **gated** list, with the sentence and its date beside it.

**Done when** every pickable key has been searched, and each gated one carries its sentence.

## 5. Name the next one

One ticket, with one clause of reasoning: the critical path, or the risk that is live now.

```
Next: OPT-819 — head of the critical path, 821 and 822 sit behind it.
```

**Done when** exactly one key is named.

## 6. Report the drift

The plan file's own state tables go stale. One line per disagreement between the file and Linear:
a state, a count, a priority, an estimate, or an edge in the sequence block.

```
§3  OPT-1029 reads Triage in Linear, the file does not list it
§4  file says 30 issues, 11 pending; Linear says 32 and 13
```

No disagreement is one line saying so. Editing the plan file is a separate ask. 🌝

**Done when** every difference is listed, or the file and Linear agree.
