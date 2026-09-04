---
name: split-pr
description: >
  Cut a finished branch into stacked pull requests, each small enough to review. Use when a
  diff is over the size limit, when work mixes several concerns, or when the user asks to
  split, stack, or break up a change for review.
---

# split-pr

Turn one finished branch into an ordered chain of **layers**.

Limits and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).
Layer design: `../gh-stack/references/stack-design.md`. Commands: `../gh-stack/SKILL.md`.

**This skill moves code. It never writes code.** Step 4 proves it.

## 1. Measure

Run the commands in `../ship/references/measure-the-diff.md`. They hold the generated-file list
and count the working tree, which a plain `git diff` against the base does not.

- **400 or under each way:** name the counts, say no stack is needed, stop. The user runs
  `/ship-stack`. `/ship` measures before it routes, so reaching this outcome means they came
  straight to this file.
- **Over, and every changed line is mechanical** (tool rename, formatter, dependency bump): say
  which of the three and ask the user. Their answer decides.

**Done when** the two numbers are posted and you have stopped or moved on.

## 2. Propose the layers

Group files bottom-up: nothing in a layer depends on a layer above it. Types and schema, then core
logic, then routes, then interface, then whole-feature tests.

- One sentence per layer. A layer needing two sentences is two layers.
- Four layers or fewer. A fifth means the ticket wanted splitting.
- A layer that would break its own build merges into its neighbour. Never reorder after the fact,
  never write code. Say the resulting size even when it passes 400.

Print: layer name, one sentence, file count, `+added -removed`.

Branch names: with a Linear key, `<key-lowercase>-<layer-slug>` (`opt-871-schema`). Without,
`<topic>/<concern>`.

**Done when** the user has approved the plan. Gate. Wait.

## 3. Build the stack

Keep the finished branch until step 4 passes.

```bash
gh stack init <layer-1> --remote origin
git checkout <work-branch> -- <paths for layer 1>
git add <paths> && git commit -m "<type>: <what this layer does>"
gh stack add <layer-2>
git checkout <work-branch> -- <paths for layer 2>
git add <paths> && git commit -m "<type>: ..."
```

Stage explicit paths. `git add -A` pulls the next layer's files in.

**Done when** every changed file from step 1 sits in exactly one layer.

## 4. Prove it

```bash
git diff origin/$BASE...<top-layer> > /tmp/stack.diff
git diff origin/$BASE...<work-branch> > /tmp/work.diff
diff /tmp/stack.diff /tmp/work.diff && echo IDENTICAL
```

Anything but `IDENTICAL` means a file was dropped or edited. Find it.

Then run the repo's fast checks (lint, type-check) on each layer bottom-up. A red layer means wrong
order or two layers belong together: report it, let the user choose. Full tests belong to
`/ship-stack`.

**Done when** the diff is identical and every layer's fast checks are green, or the user has
accepted a named exception.

## 5. Report

A table: layer, purpose, `+added -removed`. Then: run `/ship-stack`. Stop. 🧱
