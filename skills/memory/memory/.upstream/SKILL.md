---
name: memory
description: "Read from and write to the agentic-os memory vault — a markdown-in-git personal knowledge base (the agentic-os-memory repo). Use whenever an agent needs durable context or must persist findings: reading the knowledge wiki, loop reports, meetings, projects, notes, or captured sources; searching the vault for prior context; or writing/appending notes, reports, or distilled knowledge. Teaches the four-zone taxonomy, the frontmatter schema, the [[wikilink]] provenance graph, index navigation, and the MemoryStore read/write/append contract every writer must honor."
---

# memory — the agentic-os memory vault

The durable knowledge spine for agentic-os. **Markdown-in-git**: plain `.md` files an agent reads
and writes via native file tools; git gives history, sync, and portability. The vault is a
**library accessed by external agents** — you do not run *inside* it, you read and write it from
wherever you are. Resolve its root from **`$MEMORY_DIR`** (default
`~/Developer/github/agentic-os-memory`).

This vault is **OKF-v0.1-compatible** (Google Cloud's Open Knowledge Format): markdown concepts +
YAML frontmatter + a link graph, `type` as the one required field, file-path as concept ID. We
*align* with OKF; we take **no dependency** on it.

---

## The four zones

Memory is four zones. **`wiki/` is the source of truth for agents** — distilled, crafted concepts
you read to get *context*. The other three are feeder/capture zones. **Access is intent-driven** —
there is no forced funnel through the wiki. Pick the zone by what you're looking for:

| Looking for… | Go to | Zone |
|--------------|-------|------|
| a concept / "how do we handle X" | `wiki/` | **Wiki** (distilled source-of-truth) |
| a specific loop report (support load, finops…) | `reports/<loop>/<window>/` | **Loop-memory** |
| a Maestro daily digest | `briefings/` | **Loop-memory** |
| a meeting, project, area, note, journal entry | `meetings/ projects/ areas/ notes/ journal/` | **PARA** (second brain) |
| a saved article / video (external material) | `sources/` | **Capture** |
| unprocessed intake | `inbox/` | **Capture** |
| a global/personal decision | `decisions/` | (spine-adjacent) |

**Routing heuristic:** conceptual "how do we…" questions → **start in `wiki/`**; it links to its
source meetings/reports/sources via provenance, so you can trace any claim down. Need the *raw
artifact* (the actual report data, the meeting record) → go **straight to that zone's `index.md`**.
A topic may exist both raw (a meeting, an article) and distilled (a wiki concept) — prefer the wiki
for the answer, follow provenance for the evidence.

### Zone intents (keep these crisp)

- **`wiki/`** — distilled concepts (Karpathy stage 2). The sink; everything feeds it. Each concept
  carries provenance back to where it was captured. One file = one concept; the **file path is the
  concept ID**.
- **PARA** — human-authored second brain. `projects/` (active efforts), `areas/` (ongoing
  responsibilities), `notes/` (durable notes), `meetings/` (records), `journal/` (daily log).
  Enriches the wiki; separate zone.
- **Loop-memory** — machine-written. `reports/<loop>/<window>/` (time-scoped loop output),
  `briefings/` (Maestro digests).
- **`sources/`** — durable library of external material (articles, videos, papers) worth keeping.
  Destiny is **distillation into `wiki/`**; the source is retained as provenance.
- **`inbox/`** — ephemeral, unclassified intake **processed by the human** (emails, tasks, project
  seeds). Gets *emptied* — items route out to their real home.

> **"raw" is not one folder.** It is all feeder origins (`sources/`, `inbox/`, a meeting, a report).
> `wiki/` is the distilled truth. `raw → wiki → outputs` is a discipline inside the flow, not a
> top-level shape.

---

## Navigation: index at every level

Every directory has an **`index.md`** (lowercase, `type: index`) — a **pure structural map** of its
subtree (a table of what's here + one-line descriptions). On entry:

1. read the **root `index.md`** (what zones exist),
2. read the target zone's / subtree's **`index.md`**,
3. read the cheap **`summary.md`** (loop-memory) or the concept,
4. open a **full artifact** (`*-bundle.html`, a source doc) only when you need deep detail.

This progressive disclosure is what keeps token cost down — **the power is the map, not the files.**
An `index.md` carries no routing intelligence (that policy lives here, in this skill); it is just a
current, terse table. When you write a file, you **update its enclosing `index.md`** (see the write
contract).

---

## Frontmatter schema

Every file has YAML frontmatter. **Core + per-type extension**: a small required core on every
file, plus recommended fields per `type`.

### Required core (every file)

```yaml
---
type: <one of the vocabulary below>   # REQUIRED (OKF's one hard rule)
title: <human/agent display string>   # REQUIRED
updated: YYYY-MM-DD                    # REQUIRED — freshness signal; ALWAYS YYYY-MM-DD
---
```

- **`updated` is always `YYYY-MM-DD`.** Sub-day precision goes in the body (e.g. a run-log), never
  the frontmatter.
- **File path = concept ID.** Do **not** add an `id`/`slug` field.
- **`tags` is optional** — do not force it (avoids `tags: []` noise).

### The `type` vocabulary (open enum)

Reuse these names; do **not** invent synonyms. The enum is **open** — a genuinely new use case may
introduce a new `type` (document it here when you do), but an unknown type is never *rejected*.

```
index      wiki       report     run-log    briefing
project    area       note       meeting    journal
source     inbox      decision
```

### Per-type recommended extension fields

| `type` | Recommended fields |
|--------|--------------------|
| `wiki` | `sources` (provenance `[[wikilinks]]`), `status`, `tags` |
| `report` | `window`, `sources` (data origins), `outcome`, `tags` |
| `run-log` | `window` |
| `meeting` | `created`, `date`, `attendees`, `distilled_to` |
| `journal` | `created`, `date` |
| `source` | `created`, `url`, `medium` (article\|video\|paper\|…), `distilled_to`, `tags` |
| `inbox` | `created`, `status` (`unprocessed`\|`triaged`\|`routed`), routing `[[wikilink]]` once routed |
| `project` / `area` / `note` | `status`, `tags`, `distilled_to` |
| `index` | (core only) |

---

## Links & provenance — `[[wikilinks]]` everywhere

Use **`[[wikilinks]]`** for all links — both frontmatter provenance fields and prose "see also"
cross-references. (Obsidian-native → free backlinks in the app; greppable for agents.)

**Provenance is two-way.** When you **distill** knowledge from a feeder into the wiki, write *both*
directions:

- on the **wiki concept** — where it came from:
  ```yaml
  sources: ["[[meetings/2026-06-finops]]", "[[sources/some-finops-article]]"]
  ```
- on the **feeder** (meeting / report / source) — what it produced:
  ```yaml
  distilled_to: ["[[wiki/finops]]"]
  ```

Provenance lives in **frontmatter** (structured, greppable without parsing prose, survives edits).
This is the graph agents traverse to trace a claim to its evidence. Casual associative links go in
**prose** as `[[wikilinks]]`.

---

## MemoryStore contract

Agents touch memory **only** through this shape. In M1 it is a **discipline** satisfied by native
file tools over the vault — there is no code yet (the first code impl lands at M3+, when a
non-interactive loop must write memory without a session driving it; still markdown-in-git).

```
read(path)   -> str          # read a note/artifact under $MEMORY_DIR
write(path, content)         # create/replace a file (with valid frontmatter)
append(path, content)        # append to a file (e.g. a run-log)
```

### Write obligations — machine writers MUST, on every write

1. **Frontmatter** — valid core (`type`/`title`/`updated`) + the type's recommended extension fields.
2. **Index maintenance** — update the enclosing folder's `index.md` (add/refresh the row). Writing
   into a folder that doesn't exist yet → **create the folder *and* its `index.md`** (see
   folder-onboarding).
3. **Provenance** — if you distilled from a source/meeting/report, write the two-way `[[wikilink]]`
   (`sources` here, `distilled_to` there).
4. **Commit + push** — one commit per logical write, to the private remote:
   ```
   cd "$MEMORY_DIR" && git add -A && git commit -m "<zone>: <what> (<outcome>)" && git push
   ```

### Human writers — best-effort

Human writes (via Obsidian/editor) are rare and optimize for friction-free capture. Frontmatter,
index rows, and backlinks are best-effort; a future **gardener agent** reconciles. Messy in, agent
tidies.

---

## Opening a new folder (folder-onboarding)

Folders are created **lazily** — only when real content lands, never as empty scaffolding. To open
one:

1. create the directory,
2. write its **`index.md`** (the guide: what goes here, its `type`(s), how to use it),
3. ensure its `type`(s) are in the vocabulary above (add + document if new),
4. *optionally* author a **per-zone skill** when the workflow is worth encoding (e.g. a `meetings`
   skill with the note template + distill-to-wiki steps).

This root `memory` skill is the entry point; per-zone skills are added as each use case opens.

---

## Sensitivity

- The vault is a **private** repo and holds real operational data — never make it public. On a job
  switch, delete it; the *structure* is portable, the *data* is not.
- **Sanitized vs deep tier** (loop-memory): `summary.md` / `run-log.md` / `index.md` carry metrics,
  counts, categories, outcomes — **no** verbatim ticket text, chat messages, or personal names.
  Raw data lives only in the deep-tier artifact (`<source>-bundle.html`).
- **Never copy client/loop data into the `agentic-os` spine repo.** Sensitive data lives only here
  and in the loop's own repo.
