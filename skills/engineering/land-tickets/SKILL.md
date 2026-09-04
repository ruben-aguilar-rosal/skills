---
name: land-tickets
description: >
  Turn a finished local plan into a Linear ticket set with its blocking graph, behind one
  approval. Use when a wayfinder map is clear, when a spec or plan is ready to split into
  tickets, or when local ticket files need to become real Linear issues.
---

# land-tickets

A local plan becomes Linear tickets. One approval covers the whole set.

`optiak-tracker` holds the fields and the projects. `/file-issue` holds the body format and the
create command. This file holds the **set**: the order, the graph, and the gate.

## 1. Read the plan

Find the local artifacts. A wayfinder map and its child tickets, a `to-spec` spec, or
`.scratch/<feature>/issues/*.md` from `to-tickets`.

```bash
ls plan-*/tickets plan-*/findings .scratch/ 2>/dev/null
ls plans/*.md 2>/dev/null
```

A `plan-<topic>/` folder holds `findings/`, `prototypes/`, `tickets/` and a `README.md`.
`plans/*.md` holds a single-file plan.

Nothing local means the plan is still in the conversation. Say so and stop. A plan you cannot
read is a plan you would invent.

**Done when** every source file is named and read.

## 2. Propose the set

Name the project once, above the list. One plan is one project. `linear project list --team OPT`
prints the values.

One line per ticket: title, `Type`, estimate, priority, and the tickets that block it.

```
Project: Model governance

1. feat: add the model-governance reason to the 422 body   Improvement  2  P3  blocked by: -
2. feat: surface the reason in the app settings panel      Improvement  1  P3  blocked by: 1
3. chore: backfill the governance audit log                Chore        1  P4  blocked by: 1
```

Titles follow `optiak-writing`. Estimates follow `optiak-tracker`: 1, 2 or 3, and a 5 splits.
`P1` is the user's call; propose it and let them say the word.

**Done when** the project is named, every ticket has a Type, an estimate, a priority and its
blocking list, and no ticket blocks something below it.

## 3. Draw the graph

Bottom-up, blockers first. The frontier is every ticket whose blockers are all done.

```
1 ─┬─► 2
   └─► 3
```

A cycle is a design error, not a graph. Report it and stop.

**Done when** the graph is printed and it is acyclic.

## 4. Write every body, then gate

Write each body per `/file-issue` steps 2 to 5: verify every claim against the code, size it,
draft `Why` / `Scope` / `Done when` / `Out of scope`, lint it.

Print all of them, in order, in one message. Then stop.

**The graph gate replaces `/file-issue`'s per-ticket card.** The user reads the whole set once.
Do not ask again per ticket.

**Done when** the user has approved the set, the graph and every body.

## 5. Create, in dependency order

Blockers first, so every relation names a ticket that already exists.

The set went through the step 4 gate with all five conditions filled, so it opens in **Backlog**.
Every field is set in the create call, so no ticket exists in Backlog while failing a condition.

```bash
linear issue create --no-interactive --team OPT \
  --title "<title>" --description-file /tmp/ticket.md \
  --state Backlog --project "<project>" --label "<Type>" \
  --priority <n> --estimate <n>
```

Record the key it returns.

Then wire the edges:

```bash
linear issue relation add OPT-937 blocked-by OPT-936
```

Types: `blocked-by`, `blocks`, `related`, `duplicate`. Use `blocked-by`, pointing up the graph.

**Done when** every ticket has a key, every key shows `Backlog` with all five conditions filled,
and `linear issue relation list <key>` shows every edge from step 3.

## 6. Report

The graph again, with real keys. Then the frontier: the tickets whose blockers are all done, so
the user knows which one to start.

```
OPT-936 ─┬─► OPT-937
         └─► OPT-938

Start with: OPT-936
```

Local files keep the reasoning: the measured numbers, the traps, the decisions and why. **Linear
owns state and blocking relations from now on.** A graph left in a local file drifts, and has been
wrong before. Point at the keys, do not re-draw it. 🌝

The user's calls, handed over rather than taken: **setting priority 1 Urgent**, **closing or
cancelling one**, **deleting one**.
