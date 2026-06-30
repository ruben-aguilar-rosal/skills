# Productivity skills

Productivity skills vendored verbatim from:

- [`mattpocock/skills`](https://github.com/mattpocock/skills) (`skills/productivity/`, synced at `6eeb81b`)
- [`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`) — `doc-coauthoring`, `web-artifacts-builder`

These are thinking/working aids: stress-testing plans, co-authoring docs, building rich
web artifacts, handing off context, and learning.

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `doc-coauthoring` | Structured workflow for co-authoring docs, proposals, specs, decision docs. *(anthropics)* |
| `grill-me` | A relentless plan/design interview (user-invoked). |
| `grilling` | Interview you relentlessly to stress-test a plan or design before building. |
| `handoff` | Compact the current conversation into a handoff doc for another agent. |
| `teach` | Teach you a new skill or concept within this workspace. |
| `web-artifacts-builder` | Build elaborate multi-component claude.ai HTML artifacts (React, Tailwind, shadcn/ui) — good for interactive web reports. *(anthropics)* |
| `writing-great-skills` | Reference for writing and editing skills well. |

## How to use them

- **Automatic:** `grilling`, `doc-coauthoring`, and `web-artifacts-builder` activate from
  their `description` (a "grill" phrase, a doc-writing request, or a complex-artifact ask).
- **Explicit:** the rest are `disable-model-invocation` — invoke them yourself, e.g.
  *"use the `handoff` skill"* or `/teach`.
