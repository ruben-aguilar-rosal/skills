# Observability skills

Vendored, verbatim agent skills for authoring **PromQL** (Prometheus Query Language) and **LogQL**
(Grafana Loki's query language). Committed verbatim (no LLM adaptation) and pinned by commit SHA in
`sources.yaml`.

> Vendored from the same upstream as **`skills/kubernetes`** (Helm/k8s/GitOps) and **`skills/iac`**
> (Terraform/Terragrunt). For Datadog-specific tooling, see **`skills/datadog`**.

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| DevOps generator/validator skills | [`akin-ozer/cc-devops-skills`](https://github.com/akin-ozer/cc-devops-skills) | `feaf2b2` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/` (the security-gate scan
surface) — do not hand-edit it.

## What each skill does

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `promql-generator` | `promql-generator` | Writing PromQL queries, metric expressions, alerting rules, recording rules, Prometheus dashboards. |
| `promql-validator` | `promql-validator` | Validating/linting PromQL queries and alerting rules; detects anti-patterns. |
| `logql-generator` | `logql-generator` | Writing LogQL queries, log stream selectors, metric queries, and alerting rules for Grafana Loki. |

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above).
To invoke one explicitly, name it, e.g. *"use `promql-generator` to write a RED-method query"*.

Vendored skills are **unlinked** by default. Activate them under `~/.claude/skills`:

```bash
uv run skillsync link
```

## Updating

```bash
uv run skillsync sync     # pull upstream changes for the pinned skills
uv run skillsync status   # per-skill synced SHA, drift, and link state
```

### Gate overrides carried on these pins

All three tripped NVIDIA SkillSpector's static gate; **every finding was reviewed and judged benign**:

- **`accept_findings`**:
  - `OH1` (Output Handling): a `subprocess.run(...)` call in `promql-validator`'s test script that
    shells out to the local checker with a fixed arg list (`shell=False`), no user-interpolated
    command string.
- **`accept_invalid: true`** — carried on all three because each references a bundled example file
  (or a path-shaped placeholder like `[metric][time_range]`) from its SKILL.md, which the validator
  checks before the files are mirrored into place (a false positive).
