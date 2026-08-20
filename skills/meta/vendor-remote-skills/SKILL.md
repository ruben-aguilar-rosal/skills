---
name: vendor-remote-skills
description: User wants to add/import/vendor one or more skills from a remote GitHub repository into this skills repo (e.g. "add the skills from <repo> into skills/<category>"). Drives the skillsync onboarding pipeline end-to-end, reviews the security gate, writes a category README, and opens a PR.
metadata:
  source: ruben-aguilar-rosal/skills
  labels: meta,skills,tooling
  deprecated: "false"
---

# Vendoring Remote Skills

## Objective

Use this skill when the user asks to bring skills from an upstream GitHub repo into
this repository. The repo's `skillsync` CLI is the onboarding engine: it mirrors the
upstream subtree, runs a deterministic security gate (NVIDIA SkillSpector), validates
the result, and records a pinned entry in `sources.yaml`. This skill is the procedure
wrapped around that CLI — scope, gate review, verification, README, and PR.

Vendor verbatim by default (no LLM adaptation). Only pass `--adapt` if the user asks
for the skill to be rewritten for their stack.

## LLM MUST

- **Inspect upstream first.** Shallow-clone the repo to `/tmp`, list every skill
  (`find ... -name SKILL.md`), and for each candidate print its directory name vs its
  frontmatter `name:` — they often differ and that drives `accept_invalid` (see below).
- **Confirm scope with the user** when the repo ships more than one skill. Do not vendor
  all of them by default; ask which subset and which destination category.
- **Run the security gate before writing anything.** For each skill:
  `skillspector scan <skill-dir> --no-llm --format json`. The JSON has
  `risk_assessment.score` and an `issues[]` list. skillsync blocks on any `HIGH` or
  `CRITICAL` finding.
- **Review every blocking finding by reading the flagged lines** (`location.start_line`).
  Only accept a finding you have judged a false positive, and record it narrowly as
  `accept_findings: [<rule_id>]` on that skill's pin. Never blanket-accept. State in the
  PR why each accepted finding is benign. A genuinely suspicious finding is a STOP —
  surface it to the user, do not vendor.
- **Pre-seed the pin** in `sources.yaml` before running `add` when a skill needs
  `accept_findings` or `accept_invalid` — `skillsync add` reuses an existing pin rather
  than appending a duplicate. Set `synced_sha: null` (unsynced); `add` bumps it.
- **Set `accept_invalid: true`** for any skill whose frontmatter `name` ≠ its folder name
  (validation requires they match). This is the common case — verify it from the upstream
  inspection above.
- **Vendor with `--no-pr`** and group with `--dest` so all skills land under one category
  folder and one commit, instead of stacked per-skill PR branches:
  `uv run skillsync add <owner/repo> <skill-subpath> --dest skills/<category> --no-pr`
  Run each skill on its own; retry individually on transient network/SSL errors (the pin
  stays `synced_sha: null` until it succeeds).
- **Verify before committing.** Run `uv run skillsync status` (every vendored skill must
  read `upstream=synced clean`) and diff each on-disk `SKILL.md` against its upstream copy
  to confirm it is verbatim.
- **Write a `README.md` in the destination category folder** explaining how to use the
  vendored skills (see structure below). This is a required step, not optional.
- **Open one PR** off `main` (not off an unrelated branch). The PR body must list each
  skill, its frontmatter `name`, and every gate override (`accept_invalid`,
  `accept_findings`) with its justification.

## LLM SHOULD

- Branch off `main` with a `chore/vendor-<repo>` or `feat/...` name before committing.
- Mention that vendored skills are not installed; suggest
  `uv run skillsync install --skill-set <category>` to copy them into `~/.agents/skills`
  and `~/.claude/skills`.
- Keep the commit message factual: which skills, which overrides and why (mirror the
  existing `chore: vendor ...` commits).

## Destination README structure

Create `skills/<category>/README.md` covering:

1. **Source & attribution** — upstream repo URL, the synced SHA, and that skills are
   vendored verbatim.
2. **What each skill does** — one row per skill: folder name, frontmatter `name` (the id
   the agent loads), and a one-line trigger description.
3. **How to use** — that the agent auto-loads a skill by its `description`; how to invoke
   explicitly; the `uv run skillsync install --skill-set <category>` step that copies them
   into the agent skills dirs.
4. **Updating** — `uv run skillsync sync` to pull upstream changes; note any
   `accept_findings`/`accept_invalid` carried on the pins and why.

## Procedure (reference)

```bash
# 1. inspect
git clone --depth 1 https://github.com/<owner>/<repo>.git /tmp/<repo>-inspect
find /tmp/<repo>-inspect -name SKILL.md            # list skills
grep -m1 '^name:' /tmp/<repo>-inspect/<path>/SKILL.md   # name vs folder

# 2. gate (per skill) — read flagged lines for any HIGH/CRITICAL
skillspector scan /tmp/<repo>-inspect/<path> --no-llm --format json

# 3. (if overrides needed) pre-seed pin in sources.yaml: synced_sha: null,
#    accept_invalid: true and/or accept_findings: [<id>]

# 4. vendor (per skill)
uv run skillsync add <owner>/<repo> <skill-subpath> --dest skills/<category> --no-pr

# 5. verify
uv run skillsync status            # expect: upstream=synced  clean
uv run skillsync config-check      # sources.yaml parses

# 6. write skills/<category>/README.md, then branch + commit + PR
```

## Anti-Patterns

- Vendoring before the security gate has passed/been reviewed.
- Accepting a blocking finding without reading the actual flagged content.
- Opening five separate PRs for five skills from one repo, or branching off whatever
  branch happens to be checked out instead of `main`.
- Hand-editing files under a skill's `.upstream/` mirror — it is a pristine copy and the
  scan surface.
- Skipping the destination README.
