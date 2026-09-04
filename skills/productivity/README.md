# Productivity skills

Productivity skills vendored verbatim from:

- [`mattpocock/skills`](https://github.com/mattpocock/skills) (`skills/productivity/`, synced at `6eeb81b`)
- [`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`) — `doc-coauthoring`, `web-artifacts-builder`
- [`ayghri/i-have-adhd`](https://github.com/ayghri/i-have-adhd) (synced at `72c33ee`) — `i-have-adhd`
- [`composio-community/awesome-agent-clis`](https://github.com/composio-community/awesome-agent-clis) (synced at `9f765d2`) — `ntn`
- [`danyuchn/asd-ste100-skill`](https://github.com/danyuchn/asd-ste100-skill) (`master`, synced at `8564f89`) — `asd-ste100-skill`
- [`cursor/plugins`](https://github.com/cursor/plugins) (`pstack/skills/`, synced at `fd6dd6f`) — `unslop`
- [`humanlayer/skills`](https://github.com/humanlayer/skills) (`plugins/show-me/`, synced at `3c26291`) — `show-me`

These are thinking/working aids: stress-testing plans, co-authoring docs, building rich
web artifacts, handing off context, and learning.

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `asd-ste100-skill` | Rewrite dense or ambiguous English into ASD-STE100 Simplified Technical English — one meaning per word, active voice, simple tenses, short sentences — with a before/after table naming the rule each rewrite fixes. Aimed at text another agent or a translation pipeline has to parse. Frontmatter `name` is `Simplified Technical English (ASD-STE100)`. *(danyuchn)* |
| `doc-coauthoring` | Structured workflow for co-authoring docs, proposals, specs, decision docs. *(anthropics)* |
| `grill-me` | A relentless plan/design interview (user-invoked). |
| `grilling` | Interview you relentlessly to stress-test a plan or design before building. |
| `handoff` | Compact the current conversation into a handoff doc for another agent. |
| `humanizer` | Edit prose to remove AI-writing tells while preserving its intended voice. |
| `i-have-adhd` | Shape output for an ADHD reader: lead with the next action, number steps, restate state each turn, suppress tangents, give concrete time estimates. *(ayghri)* |
| `linear` | Linear CLI reference: manage issues, projects, teams, cycles, milestones, documents, and raw GraphQL queries from the terminal. Hand-authored (not vendored). |
| `ntn` | Notion CLI reference: authenticate, call the Notion API, upload files, manage Workers. Frontmatter `name` is `Notion CLI (ntn)`. *(composio-community)* |
| `perplexity-search` | Research current web information with the local Perplexity CLI through the direct API or OpenRouter. |
| `show-me` | Explain the current topic visually instead of in prose: pseudocode, call trees, ASCII box/flow diagrams, type sketches, or a focused HTML artifact. Picks the smallest view that makes the point. *(humanlayer)* |
| `teach` | Teach you a new skill or concept within this workspace. |
| `unslop` | Cut AI tells from writing: puffery, AI vocabulary, em dashes, rule-of-three, inline-header lists, passive voice, filler. 31 numbered patterns plus an "add soul" pass (have opinions, vary rhythm, be specific). Overlaps `humanizer` — `unslop` is the terser checklist and bans em dashes outright. *(cursor)* |
| `web-artifacts-builder` | Build elaborate multi-component claude.ai HTML artifacts (React, Tailwind, shadcn/ui) — good for interactive web reports. *(anthropics)* |
| `writing-great-skills` | Reference for writing and editing skills well. |

## How to use them

- **Automatic:** `grilling`, `doc-coauthoring`, and `web-artifacts-builder` activate from
  their `description` (a "grill" phrase, a doc-writing request, or a complex-artifact ask).
  `i-have-adhd` also self-activates — its `description` triggers on *any* message, so it
  shapes output broadly once installed; disable it if you don't want that. `ntn` activates when
  an agent needs to work with the Notion API/Workers/file uploads via the CLI.
  `perplexity-search` activates for research, investigation, web search, current-information,
  fact-checking, source-comparison, and citation-gathering requests. `linear` activates when
  an agent needs to create/query/update Linear issues, projects, teams, or documents via the CLI.
  `asd-ste100-skill` activates on "simplify this" / "STE100 rewrite" and when agent output
  reads as hard to parse. It is deliberately flat and literal — don't point it at creative or
  marketing copy, where voice is the point.
  `unslop` is also broadly self-activating: its `description` reads *"Must always apply"*,
  so it shapes prose on every writing task once installed. Disable it, or keep `humanizer`
  instead, if you don't want two overlapping de-slop passes running at once.
  `show-me` activates when you ask to see, sketch, draw, or visualise the thing under
  discussion, and it is safe to invoke by hand as `/show-me`.
- **Explicit:** the rest are `disable-model-invocation` — invoke them yourself, e.g.
  *"use the `handoff` skill"* or `/teach`.
- Run `uv run skillsync install --skill-set productivity` to copy these skills into
  `~/.agents/skills` and `~/.claude/skills` so they become active. Skills are not installed
  by default.

## Gate overrides

- `i-have-adhd` carries `accept_invalid: true`. The validator flags `src/auth.ts` as a
  missing referenced file, but that path only appears as an illustrative example inside the
  skill's prose (`edit src/auth.ts:42`) — it is not a bundled file. SkillSpector scored the
  skill `0` / SAFE with zero findings.
- `ntn` carries `accept_invalid: true`. Its frontmatter `name` (`Notion CLI (ntn)`) differs
  from its folder name (`ntn`), which fails the folder/name validation. SkillSpector scored
  the skill `0` / SAFE with zero findings — the mismatch is cosmetic, not a security issue.
- `asd-ste100-skill` carries `accept_invalid: true` and `accept_findings: [P5]`.
  `accept_invalid` is the same cosmetic mismatch as `ntn`: the frontmatter `name`
  (`Simplified Technical English (ASD-STE100)`) is not its folder name. `P5` is a CRITICAL
  "Harmful Content Injection" hit on the literal string *"kill people"* at `README.md:9` —
  the sentence is *"STE exists because a misread instruction on an aircraft can kill people"*,
  descriptive prose explaining why the standard exists, not an instruction to anyone. The
  skill ships five markdown files, no executable scripts and no network calls.

  This is also the repo's first **root-level** upstream: the repo *is* the skill, with
  `SKILL.md` at the top rather than in a subfolder, so its pin is `path: .` plus an explicit
  `name:` naming the local folder.
- `show-me` carries no overrides. Its folder name matches its frontmatter `name` and
  SkillSpector scored it `0` / SAFE with zero findings (one markdown file, no scripts,
  no network calls).
- `unslop` carries no overrides. Its folder name matches its frontmatter `name` and
  SkillSpector scored it `0` / SAFE with zero findings (one markdown file, no scripts).

## Updating

Run `uv run skillsync sync` to pull upstream changes for the vendored skills above. The
`accept_invalid`/`accept_findings` overrides noted here are carried on each skill's pin in
`sources.yaml` and persist across re-syncs.
