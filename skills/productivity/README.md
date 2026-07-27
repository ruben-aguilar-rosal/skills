# Productivity skills

Productivity skills vendored verbatim from:

- [`mattpocock/skills`](https://github.com/mattpocock/skills) (`skills/productivity/`, synced at `6eeb81b`)
- [`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`) — `doc-coauthoring`, `web-artifacts-builder`
- [`ayghri/i-have-adhd`](https://github.com/ayghri/i-have-adhd) (synced at `72c33ee`) — `i-have-adhd`
- [`composio-community/awesome-agent-clis`](https://github.com/composio-community/awesome-agent-clis) (synced at `9f765d2`) — `ntn`

These are thinking/working aids: stress-testing plans, co-authoring docs, building rich
web artifacts, handing off context, and learning.

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `doc-coauthoring` | Structured workflow for co-authoring docs, proposals, specs, decision docs. *(anthropics)* |
| `grill-me` | A relentless plan/design interview (user-invoked). |
| `grilling` | Interview you relentlessly to stress-test a plan or design before building. |
| `handoff` | Compact the current conversation into a handoff doc for another agent. |
| `humanizer` | Edit prose to remove AI-writing tells while preserving its intended voice. |
| `i-have-adhd` | Shape output for an ADHD reader: lead with the next action, number steps, restate state each turn, suppress tangents, give concrete time estimates. *(ayghri)* |
| `linear` | Linear CLI reference: manage issues, projects, teams, cycles, milestones, documents, and raw GraphQL queries from the terminal. Hand-authored (not vendored). |
| `ntn` | Notion CLI reference: authenticate, call the Notion API, upload files, manage Workers. Frontmatter `name` is `Notion CLI (ntn)`. *(composio-community)* |
| `perplexity-search` | Research current web information with the local Perplexity CLI through the direct API or OpenRouter. |
| `teach` | Teach you a new skill or concept within this workspace. |
| `web-artifacts-builder` | Build elaborate multi-component claude.ai HTML artifacts (React, Tailwind, shadcn/ui) — good for interactive web reports. *(anthropics)* |
| `writing-great-skills` | Reference for writing and editing skills well. |

## How to use them

- **Automatic:** `grilling`, `doc-coauthoring`, and `web-artifacts-builder` activate from
  their `description` (a "grill" phrase, a doc-writing request, or a complex-artifact ask).
  `i-have-adhd` also self-activates — its `description` triggers on *any* message, so it
  shapes output broadly once linked; disable it if you don't want that. `ntn` activates when
  an agent needs to work with the Notion API/Workers/file uploads via the CLI.
  `perplexity-search` activates for research, investigation, web search, current-information,
  fact-checking, source-comparison, and citation-gathering requests. `linear` activates when
  an agent needs to create/query/update Linear issues, projects, teams, or documents via the CLI.
- **Explicit:** the rest are `disable-model-invocation` — invoke them yourself, e.g.
  *"use the `handoff` skill"* or `/teach`.
- Run `uv run skillsync link` to symlink vendored skills into `~/.claude/skills` so they
  become active. Vendored skills are `unlinked` by default.

## Gate overrides

- `i-have-adhd` carries `accept_invalid: true`. The validator flags `src/auth.ts` as a
  missing referenced file, but that path only appears as an illustrative example inside the
  skill's prose (`edit src/auth.ts:42`) — it is not a bundled file. SkillSpector scored the
  skill `0` / SAFE with zero findings.
- `ntn` carries `accept_invalid: true`. Its frontmatter `name` (`Notion CLI (ntn)`) differs
  from its folder name (`ntn`), which fails the folder/name validation. SkillSpector scored
  the skill `0` / SAFE with zero findings — the mismatch is cosmetic, not a security issue.

## Updating

Run `uv run skillsync sync` to pull upstream changes for the vendored skills above. The
`accept_invalid`/`accept_findings` overrides noted here are carried on each skill's pin in
`sources.yaml` and persist across re-syncs.
