---
name: skill-creator
description: Guidance for creating new `.claude/skills/` domain skill files for Aily
  Labs, focusing on SKILL.md structure, frontmatter, bundled resources, and writing
  style.
metadata:
  source: aily-ai-tools/packages/aily-llm-resources
  labels: ai,ds,saas,default
  deprecated: 'false'
---

# Skills Authoring Guidelines

Purpose: keep all new `.claude/skills/` domain files compact, consistent, and machine-usable while giving the LLM enough signal to act correctly.

Scope: use this guide when creating new skill directories under `.claude/skills/`. Existing skills should not be rewritten just to conform, unless there is an explicit refactor request.

## Skill Structure

Every skill lives in its own directory:

```
.claude/skills/<skill-name>/
├── SKILL.md              # required — frontmatter + instructions
└── references/           # optional — supporting files loaded on demand
    ├── some-guide.md
    └── example.py
```

### SKILL.md Frontmatter

Every `SKILL.md` must open with a YAML frontmatter block:

```yaml
---
name: <skill-name>          # matches the directory name
description: <trigger text> # one line; drives when the skill is activated
metadata:
  source: <org>/<repository>
  labels: ai,ds            # comma-separated audience labels used by the sync workflow
  deprecated: "false"      # string flag used for sync exclusion and downstream cleanup
---
```

If adding the skill inside `packages/aily-llm-resources/aily_llm_resources/.claude/skills`, set `source` to exactly `aily-ai-tools/packages/aily-llm-resources`. For any other repository, use `<org>/<repository>`.

The sync workflow reads `description`, `metadata.labels`, and `metadata.deprecated` from frontmatter. `description` is the text copied into generated `AGENTS.md`. Write it as a trigger sentence: describe the situation where this skill should activate, not just what it covers. Be specific and slightly "pushy" so the LLM picks it up reliably.

Bad: `Guidance for logging.`
Good: `User needs to instrument logging, choose log levels, structure log output, or integrate logging frameworks.`

### Frontmatter Semantics

- `description`: one-line trigger text shown in generated `AGENTS.md`.
- `metadata.labels`: comma-separated audience bundles used by the sync workflow to decide whether a repo should receive the skill. Use `all` to sync the skill to every repo regardless of that repo's requested labels.
- `metadata.deprecated`: string lifecycle flag. Deprecated skills are excluded from new syncs and removed from downstream repos.
- `metadata.source`: traceability field for the origin repository.

### Deprecation Rule

When retiring a centralized skill:

1. Do not delete the skill directory immediately.
2. Change `metadata.deprecated` from `"false"` to `"true"`.
3. Keep the directory in place for at least one sync cycle so downstream repos can remove their stale copies.
4. Delete the directory only after the cleanup sync has run.

This is required because downstream cleanup relies on the deprecated skill still being discoverable by the shared workflow.

## Core Principles

- **Single responsibility**: each skill covers one domain (e.g., logging, CLI, airflow-dag), not a mix of topics.
- **Instruction-first**: write for an LLM, not for humans browsing docs. Use direct, imperative language.
- **Minimal but complete**: capture the smallest set of rules that reliably shapes behavior; avoid long tutorials or narrative.
- **Explain the why**: for non-obvious rules, briefly state the reason — it helps the LLM apply the rule correctly in edge cases.

## Length & Content

- Token budget: aim for ~400–1000 tokens (roughly 300–750 words) in `SKILL.md`.
- If a draft is longer, review for repetition or low-value detail and tighten while preserving key rules.
- Prefer short sections and bullet lists over long paragraphs.
- For richer content (e.g., reference docs, large examples, scripts), place them in `references/` and link from `SKILL.md` rather than embedding inline.

Recommended section order (adapt as needed):
1. `## Objective` – what this skill covers and when it applies (3–5 lines).
2. `## LLM MUST` – non-negotiable rules, each as a short bullet.
3. `## LLM SHOULD` – strong preferences and patterns, but not hard constraints.
4. `## Examples (Minimal)` – at most one or two small examples (≤ 20 lines each) illustrating the key pattern.
5. `## Anti-Patterns` – a few bullets of what to avoid in this domain.

## Writing Style

- Be explicit and concrete: say exactly what the LLM should do, when, and how.
- Avoid repetition: if a rule is already covered by `AGENTS.md` or another skill, reference it instead of restating it.
- Use consistent terminology across skills (`LLM`, `skill`, `caller`, `frontmatter`).
- Prefer constraints over philosophy: specify formats, sections, and behaviors rather than abstract principles.
- Avoid excessive `ALWAYS`/`NEVER` capitalization — explain reasoning instead.

## Registering a New Skill

1. Create `.claude/skills/<skill-name>/SKILL.md` with valid frontmatter including a non-empty `description`.
2. Set `metadata.labels` to the audience bundles that should receive the skill as a comma-separated string.
3. Set `metadata.deprecated: "false"` for active skills.

The pre-commit hook (`scripts/new_rule.py`) will reject a commit if the required frontmatter fields are missing or invalid.

## Maintenance

- Before adding a new skill, check whether an existing one already covers the domain — extend or reference it instead of duplicating.
- Periodically prune outdated rules to keep the skill library focused on active conventions.
- When a skill interacts with others, state it explicitly (e.g., "Use in addition to `python-general` for data pipelines").
