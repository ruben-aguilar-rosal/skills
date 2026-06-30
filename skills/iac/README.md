# Infrastructure-as-Code skills

Vendored, verbatim agent skills for **Terraform** and **Terragrunt**. Committed verbatim (no LLM
adaptation) and pinned by commit SHA in `sources.yaml`.

> Vendored from the same upstream as **`skills/kubernetes`** (Helm/k8s/GitOps) and
> **`skills/observability`** (PromQL/LogQL).

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| DevOps generator/validator skills | [`akin-ozer/cc-devops-skills`](https://github.com/akin-ozer/cc-devops-skills) | `feaf2b2` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/` (the security-gate scan
surface) — do not hand-edit it.

## What each skill does

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `terraform-generator` | `terraform-generator` | Writing/scaffolding Terraform `.tf` HCL — resources, modules, providers, variables, outputs. |
| `terraform-validator` | `terraform-validator` | Validating/linting/planning Terraform; runs `tflint`, `checkov`, `terraform validate`. |
| `terragrunt-generator` | `terragrunt-generator` | Scaffolding Terragrunt HCL — root.hcl, child modules, stacks, multi-env layouts. |
| `terragrunt-validator` | `terragrunt-validator` | Validating/linting/auditing Terragrunt `.hcl`, stacks, modules. |

> Aily relevance: maps onto the `aily-terragrunt` repo and `terraform-modules` work.

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above).
To invoke one explicitly, name it, e.g. *"use `terragrunt-validator` on this stack"*.

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

All four tripped NVIDIA SkillSpector's static gate; **every finding was reviewed and judged benign**:

- **`accept_findings`**:
  - `PE3` (Privilege Escalation): keyword hits on `.env` (Terragrunt example templates / reference
    docs) and `~/.ssh/id_rsa` (a Terraform provider doc example).
  - `RA1` (Rogue Agent): "overwrite existing file" in `terragrunt-validator`'s SKILL.md prose;
    checkov's "Remove Check" uninstall help in `terraform-validator`.
  - `TM1` (Tool Misuse): `--skip-check` / `--check` are checkov's own native flags.
- **`accept_invalid: true`** — carried on all four because each references a bundled example file
  from its SKILL.md, which the validator checks before the files are mirrored into place (a false
  positive).
