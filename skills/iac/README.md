# Infrastructure-as-Code skills

Vendored, verbatim agent skills for **Terraform** and **Terragrunt**. Committed verbatim (no LLM
adaptation) and pinned by commit SHA in `sources.yaml`.

> Related categories: **`skills/kubernetes`** (Helm/k8s/GitOps), **`skills/observability`**
> (PromQL/LogQL + Prometheus/Grafana), and **`skills/sre`** (incident response / on-call).

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| HashiCorp official agent skills | [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) | `339a113` | per upstream |
| DevOps generator/validator skills | [`akin-ozer/cc-devops-skills`](https://github.com/akin-ozer/cc-devops-skills) | `feaf2b2` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/` (the security-gate scan
surface) — do not hand-edit it.

## What each skill does

### Terraform — official HashiCorp (`hashicorp/agent-skills`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `terraform-style-guide` | `terraform-style-guide` | Writing/reviewing HCL to HashiCorp's official style conventions and best practices. |
| `terraform-test` | `terraform-test` | Writing and running Terraform tests — `.tftest.hcl` files, test scenarios, mock providers, CI. |
| `terraform-search-import` | `terraform-search-import` | Discovering existing cloud resources via Terraform Search and bulk-importing them into management. |
| `refactor-module` | `refactor-module` | Transforming monolithic configs into reusable modules per HashiCorp module design principles. |

### Terraform / Terragrunt — community (`akin-ozer/cc-devops-skills`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `terraform-generator` | `terraform-generator` | Writing/scaffolding Terraform `.tf` HCL — resources, modules, providers, variables, outputs. |
| `terraform-validator` | `terraform-validator` | Validating/linting/planning Terraform; runs `tflint`, `checkov`, `terraform validate`. |
| `terragrunt-generator` | `terragrunt-generator` | Scaffolding Terragrunt HCL — root.hcl, child modules, stacks, multi-env layouts. |
| `terragrunt-validator` | `terragrunt-validator` | Validating/linting/auditing Terragrunt `.hcl`, stacks, modules. |

> Aily relevance: maps onto the `aily-terragrunt` repo and `terraform-modules` work. No dedicated
> Terragrunt skill exists upstream; since Terragrunt wraps Terraform/OpenTofu, the HashiCorp
> Terraform skills (style guide, testing, refactoring) apply to Terragrunt-managed code too.

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above).
To invoke one explicitly, name it, e.g. *"use `refactor-module` to break this up"*.

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

All skills were run through NVIDIA SkillSpector; **every finding was reviewed and judged benign**.

**HashiCorp skills** — all passed the gate clean (`SAFE`, score 0). `accept_invalid: true` is carried
on `terraform-test`, `terraform-search-import`, and `refactor-module` because each references a
bundled file (`references/*.md`, `examples/`) from its SKILL.md, which the validator checks before
the files are mirrored into place (a false positive). `terraform-style-guide` validates clean and
carries no override.

**akin-ozer skills**:

- **`accept_findings`**:
  - `PE3` (Privilege Escalation): keyword hits on `.env` (Terragrunt example templates / reference
    docs) and `~/.ssh/id_rsa` (a Terraform provider doc example).
  - `RA1` (Rogue Agent): "overwrite existing file" in `terragrunt-validator`'s SKILL.md prose;
    checkov's "Remove Check" uninstall help in `terraform-validator`.
  - `TM1` (Tool Misuse): `--skip-check` / `--check` are checkov's own native flags.
- **`accept_invalid: true`** — carried on all four because each references a bundled example file
  from its SKILL.md (same validator-ordering false positive as above).
