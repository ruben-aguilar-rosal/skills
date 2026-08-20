# SRE skills

Vendored, verbatim agent skills for **Site Reliability Engineering** — incident response, on-call,
and postmortems. Committed verbatim (no LLM adaptation) and pinned by commit SHA in `sources.yaml`.

> Related categories: **`skills/observability`** (metrics/logs/traces + SLOs), **`skills/kubernetes`**
> (cluster ops), and **`skills/iac`** (Terraform/Terragrunt). For Aily-specific on-call/triage
> tooling, see the `infra-triage` and `review-before-ticket` skills under **`skills/aily`**.

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| Multi-harness agent marketplace | [`wshobson/agents`](https://github.com/wshobson/agents) | `5cc2549` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/` (the security-gate scan
surface) — do not hand-edit it.

## What each skill does

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `postmortem-writing` | `postmortem-writing` | Writing blameless postmortems — root cause analysis, timelines, action items; conducting incident reviews. |
| `incident-runbook-templates` | `incident-runbook-templates` | Creating structured incident-response runbooks — step-by-step procedures, escalation paths, recovery actions. |
| `on-call-handoff-patterns` | `on-call-handoff-patterns` | On-call shift handoffs — context transfer, escalation procedures, documentation. |

> Aily relevance: complements the Aily on-call/APS workflow (`infra-triage`,
> `review-before-ticket`) with general SRE practice for postmortems, runbooks, and handoffs.

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above).
To invoke one explicitly, name it, e.g. *"use `postmortem-writing` for this incident review"*.

Vendored skills are **not installed** by default. Activate them under `~/.agents/skills`
and `~/.claude/skills`:

```bash
uv run skillsync install --skill-set sre
```

## Updating

```bash
uv run skillsync sync     # pull upstream changes for the pinned skills
uv run skillsync status   # per-skill synced SHA, drift, and link state
```

### Gate overrides carried on these pins

All three were run through NVIDIA SkillSpector. `postmortem-writing` and `on-call-handoff-patterns`
passed clean (`SAFE`, score 0).

`incident-runbook-templates` surfaced only **MEDIUM** findings (no HIGH/CRITICAL, so the gate does
not block) — all benign example content in its runbook *template*: `curl -X POST https://api.company.com/...`
and `https://api.stripe.com/` are placeholder endpoints/dependencies (E1, "data exfiltration"),
and "skip verification" is runbook prose (EA2, "excessive agency"). No `accept_findings` needed.

**`accept_invalid: true`** is carried on all three because each references a bundled or illustrative
file from its SKILL.md (`references/details.md`, plus cross-skill links like
`../../skills/incident-classification/SKILL.md` and example wiki paths like
`internal-wiki/deployment-runbook`), which the validator checks before the bundled files are
mirrored into place — a false positive.
