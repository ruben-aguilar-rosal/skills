# Engineering skills

Engineering workflow skills vendored verbatim from several upstreams:

- [`mattpocock/skills`](https://github.com/mattpocock/skills) (`skills/engineering/`, synced at `6eeb81b`)
- [`multica-ai/andrej-karpathy-skills`](https://github.com/multica-ai/andrej-karpathy-skills) (synced at `2c60614`) — `karpathy-guidelines`
- [`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`) — `mcp-builder`, `webapp-testing`, `skill-creator`
- Personal `git-flow` plugin — `ship`

These cover the build loop: design, plan-to-issues, implement, test, diagnose, build MCP
servers / skills, and the behavioral guidelines that keep changes surgical.

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `ask-matt` | Router that suggests which skill/flow fits your situation. |
| `codebase-design` | Shared vocabulary for designing deep modules and choosing seams. |
| `diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. |
| `domain-modeling` | Build and sharpen a project's domain model / ubiquitous language. |
| `grill-with-docs` | Relentless plan/design interview that also produces ADRs and a glossary. |
| `implement` | Implement a piece of work from a PRD or set of issues. |
| `improve-codebase-architecture` | Scan for deepening opportunities, report as HTML, then grill the chosen one. |
| `karpathy-guidelines` | Behavioral guidelines to reduce common LLM coding mistakes. |
| `mcp-builder` | Build high-quality MCP servers (Python FastMCP or Node/TypeScript SDK). *(anthropics)* |
| `prototype` | Build a throwaway prototype — runnable terminal app or toggleable UI variations. |
| `resolving-merge-conflicts` | Resolve an in-progress git merge/rebase conflict. |
| `ship` | Commit, push, and open a GitHub PR using conventional commits and a standard branch flow. |
| `setup-matt-pocock-skills` | One-time repo setup for the mattpocock skills (issue tracker, triage labels, domain docs). |
| `skill-creator` | Create/edit skills, run evals, benchmark performance, optimize descriptions. *(anthropics)* |
| `tdd` | Test-driven development (red-green-refactor, integration tests). |
| `to-issues` | Break a plan/spec/PRD into independently-grabbable issues (tracer-bullet slices). |
| `to-prd` | Turn the current conversation into a PRD on the issue tracker. |
| `triage` | Move issues and external PRs through a triage state machine into agent-ready briefs. |
| `webapp-testing` | Interact with and test local web apps via Playwright — verify UI, capture screenshots/logs. *(anthropics)* |

> **Note:** `skill-creator` here is the generic anthropics toolkit (create/eval/benchmark);
> there is also a separate Aily-specific `skill-creator` under `skills/aily/`. The two
> share a `name`, so only one can be linked into `~/.claude/skills` at a time.

## How to use them

- **Automatic:** model-invocable skills (e.g. `codebase-design`, `diagnosing-bugs`,
  `domain-modeling`, `tdd`, `resolving-merge-conflicts`, `karpathy-guidelines`,
  `mcp-builder`, `webapp-testing`, `skill-creator`) activate from their `description`.
- **Explicit:** the mattpocock flow skills are `disable-model-invocation` — invoke them
  yourself, e.g. *"use the `implement` skill"* or `/to-prd`. Start from `ask-matt` if
  unsure which fits.
- **First run:** `setup-matt-pocock-skills` configures the repo before first use of the
  mattpocock skills.
