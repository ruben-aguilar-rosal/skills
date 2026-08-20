# Observability skills

Vendored, verbatim agent skills for **metrics, logs, and traces** — authoring PromQL/LogQL queries
plus setting up Prometheus, Grafana, distributed tracing, and SLOs. Committed verbatim (no LLM
adaptation) and pinned by commit SHA in `sources.yaml`.

> Related categories: **`skills/kubernetes`** (Helm/k8s/GitOps), **`skills/iac`**
> (Terraform/Terragrunt), and **`skills/sre`** (incident response / on-call). For Datadog-specific
> tooling, see **`skills/datadog`**.

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| DevOps generator/validator skills | [`akin-ozer/cc-devops-skills`](https://github.com/akin-ozer/cc-devops-skills) | `feaf2b2` | per upstream |
| Multi-harness agent marketplace | [`wshobson/agents`](https://github.com/wshobson/agents) | `5cc2549` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/` (the security-gate scan
surface) — do not hand-edit it.

## What each skill does

### Query authoring — PromQL / LogQL (`akin-ozer/cc-devops-skills`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `promql-generator` | `promql-generator` | Writing PromQL queries, metric expressions, alerting rules, recording rules, Prometheus dashboards. |
| `promql-validator` | `promql-validator` | Validating/linting PromQL queries and alerting rules; detects anti-patterns. |
| `logql-generator` | `logql-generator` | Writing LogQL queries, log stream selectors, metric queries, and alerting rules for Grafana Loki. |

> PromQL = Prometheus Query Language; LogQL = Grafana Loki's query language.

### Stack setup & SLOs (`wshobson/agents`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `prometheus-configuration` | `prometheus-configuration` | Setting up Prometheus for metric collection, storage, and monitoring of infra and applications. |
| `grafana-dashboards` | `grafana-dashboards` | Building/managing production Grafana dashboards for real-time visualization of system/app metrics. |
| `distributed-tracing` | `distributed-tracing` | Implementing distributed tracing with Jaeger/Tempo to track requests across microservices. |
| `slo-implementation` | `slo-implementation` | Defining SLIs/SLOs with error budgets and alerting. |

> Query-authoring skills (PromQL/LogQL) write the expressions; the wshobson skills stand up and
> configure the systems those expressions run against.

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above).
To invoke one explicitly, name it, e.g. *"use `promql-generator` to write a RED-method query"* or
*"use `slo-implementation` to define an error budget"*.

Vendored skills are **not installed** by default. Activate them under `~/.agents/skills`
and `~/.claude/skills`:

```bash
uv run skillsync install --skill-set observability
```

## Updating

```bash
uv run skillsync sync     # pull upstream changes for the pinned skills
uv run skillsync status   # per-skill synced SHA, drift, and link state
```

### Gate overrides carried on these pins

All skills were run through NVIDIA SkillSpector; **every finding was reviewed and judged benign**.

**akin-ozer skills**:

- **`accept_findings`** — `OH1` (Output Handling): a `subprocess.run(...)` call in
  `promql-validator`'s test script that shells out to the local checker with a fixed arg list
  (`shell=False`), no user-interpolated command string.
- **`accept_invalid: true`** — carried on all three because each references a bundled example file
  (or a path-shaped placeholder like `[metric][time_range]`) from its SKILL.md, which the validator
  checks before the files are mirrored into place (a false positive).

**wshobson skills** — all four passed the gate clean (`SAFE`, score 0). `accept_invalid: true` is
carried on all four because each references a bundled file (`references/details.md`,
`assets/*.json`) from its SKILL.md, the same validator-ordering false positive.
