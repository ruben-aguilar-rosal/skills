---
name: taco-procedure
description: |
  TACO procedure for Critical Production Infrastructure changes at Aily Labs.
  MANDATORY whenever a contributor is preparing, reviewing, merging, or applying
  a PR that touches gitops-prod, gitops-controlplane, gitops-shared,
  aily-terragrunt (especially resources/), or terraform-modules. Also trigger
  on any change touching prod tenants (coreproduct-prod, shared-prod,
  infrastructure-prod), stateful resources (RDS, ElastiCache, S3, EBS, EFS,
  RabbitMQ, prevent_destroy), shared infra (VPC, IAM, KMS, DNS, ingress,
  secrets, IRSA), or destroy/replace operations on live resources. If in doubt,
  treat as Critical and load this skill.
metadata:
  source: https://ailylabs.atlassian.net/wiki/spaces/AIL/pages/4067262532
  jira: TP-3379
  labels: infra, gitops, production, taco
  deprecated: 'false'
---

# TACO — Production Impacting Infrastructure Changes

Source of truth:
- Procedure: https://ailylabs.atlassian.net/wiki/spaces/AIL/pages/4067262532
- **Critical paths**: the `.criticalpaths` file at each repo root (gitignore
  syntax) — this is the authoritative list, not prose in this skill.
- **PR checklist**: the canonical `pr-template.md` shipped with the `taco-utils`
  CI image. The section headers below match it **exactly** — CI parses them.

This procedure is **mandatory** for every Critical change. The only exception
is the documented break-glass path during an active P0 / P1.

## How CI enforces this (so guidance matches the gate)

The `Validate Critical Paths` workflow (`.github/workflows/taco-checks.yaml`,
backed by `aily-shared-workflows`) runs on every PR:

1. `detect_critical_paths.py` matches changed files against `.criticalpaths`.
   If nothing matches, the PR is **not Critical** — no TACO body required.
2. If a critical path is touched, `check_pr_taco.py` parses the PR body:
   - **Section missing** → CI **appends the TACO template** to the description
     and **pings the author** (exit 2). Don't wait for this — fill it upfront.
   - **Section present but still contains `REPLACE:`** (or empty) → fails
     (exit 1). Every `REPLACE:` placeholder must be replaced.
   - **All five sections filled** → pass.

So: a PR that touches `.criticalpaths` patterns **cannot merge** without all
five TACO sections filled. Guide contributors to exactly that state.

## Scope — what is Critical here

A PR is **Critical** if a changed file matches `.criticalpaths`. In
`aily-terragrunt` that currently covers:

- **EKS** cluster/provisioning: `resources/aws/eks`,
  `terragrunt/saas/*/prod/*/aws/eks/tenant`
- **ElastiCache / Redis** (tenant + Langfuse): `resources/aws/elasticache/*`,
  `terragrunt/saas/*/prod/*/aws/elasticache/tenant`
- **RDS** (analytics + shared-tools tenant): `resources/aws/rds/instance/*`,
  `terragrunt/saas/*/prod/*/aws/rds/instance/analytics`,
  `terragrunt/aily/infrastructure/prod/*/aws/rds/instance/tenant`
- **RabbitMQ** (HA, in infrastructure env): `resources/aws/rabbitmq/*`,
  `terragrunt/saas/*/infrastructure/*/aws/rabbitmq`
- **IRSA** single-points-of-failure: `resources/eks/irsa/*`,
  `terragrunt/saas/*/prod/*/eks/irsa/{data-api,aily-super-agent,aily-super-agent-mcp}`

Beyond what `.criticalpaths` lists, also treat as Critical (and consider adding
a pattern) any change that:

- Touches `gitops-controlplane` / `gitops-shared` (cross-tenant platform),
  `gitops-prod`, or `terraform-modules`.
- Modifies `aily-terragrunt/resources/` — reused across tenants, so blast
  radius is all tenants.
- Hits **stateful** resources or anything with a `prevent_destroy` lifecycle.
- Touches **shared infra**: VPC, subnets, IAM, KMS, DNS, certificates, secrets
  backends, ingress controllers.
- Requires a **destroy/replace** on a live resource.
- Has an outcome the plan can't fully predict (provider upgrades, CRD changes,
  Helm major versions, AMI rotations).

**If in doubt, treat it as Critical.**

### Repos in scope and blast radius

| Repo | What it affects | Blast radius |
|------|------------------|--------------|
| `gitops-prod` | All prod tenant clusters; coreproduct-prod, demos | One tenant — or many if shared overlay |
| `gitops-controlplane` | `infrastructure-prod` (control plane) | All tenants |
| `gitops-shared` | `shared-prod` (SaaS plane) | All tenants |
| `aily-terragrunt` | Terragrunt live config; `resources/` reused across tenants | All tenants |
| `terraform-modules` | Module source for all of the above | All tenants |

## The TACO checklist — five sections (exact CI headers)

Reproduce these headers verbatim in the PR body. Replace every `REPLACE: <...>`
with real content. `A - Approval` is the only pre-filled section.

### T - Test
> Sufficient evidence that the change has been tested in a previous environment.

Apply the change in the matching lower environment **first**, then link/describe
the evidence (plan diff, screenshot, successful reconcile, observations):
- `gitops-prod` → `gitops-dev` (`coreproduct-dev` / `sandbox01`)
- `gitops-shared` → `shared-dev`
- `gitops-controlplane` → `infrastructure-dev`
- `aily-terragrunt` / `terraform-modules` → apply against a dev tenant first

### A - Approval
> The changes have been approved.

Implicit in PR approval — but a **Component Owner** approval is required before
scheduling. **Comments ≠ approval.**

### C - Coordinate
> Assess the impact, propose a date/time for the operation, confirmed with the
> Resiliency team and other relevant teams.

State the operation **date and time (with timezone)**. Consider tenant-specific
business-critical windows.

### C - Communicate
> Link to the change-announcement Slack message (or describe the communication).

**Announce ahead (minimum 24h)** in: the affected tenant channel(s), owners of
affected services, and `#infrastructure-platform` for any cross-tenant change
(`terraform-modules`, `gitops-controlplane`, `gitops-shared`,
`aily-terragrunt/resources/`). Announcement must include **what, why, when (tz),
expected impact, rollback ETA, who's driving, PR link.**

### O - Operate
> Operation instructions, validations, and rollback.

Spell out, with focus on application, validation, and rollback:
- Perform the change during the announced window.
- **Rollback plan**: exact revert commit / `terraform apply` to restore prior
  state / kubectl-flux step, with expected rollback time. Rollback PR approval
  is mandatory too.
- **Validate** before and after: QA health checks, Flux reconcile green for
  affected kustomizations/apps, workloads `Ready` (no `CrashLoopBackOff` /
  pending), no change-related error logs, dashboards + DataDog/Sentry monitors
  clean for **15 min** after completion.
- **Do not force**: no `kubectl delete` pods/CRs to speed up reconcile; never
  suspend Flux kustomizations or delete helmreleases/kustomizations.
- **Rollback promptly** if validation fails — do not debug forward on a
  Critical change.
- Post a short follow-up in the announcement channel: ✅ done / ⏪ rolled back,
  with evidence.

## Lifecycle — map each phase to the sections

1. **Prepare**: classify (does any changed file match `.criticalpaths`?). If
   Critical, paste the five-section TACO body **before** opening the PR and fill
   `T - Test` with lower-env evidence + draft the `O - Operate` rollback plan.
2. **Review**: secure `A - Approval` (Component Owner, not just a comment); land
   `C - Coordinate` (window) and `C - Communicate` (Slack link, ≥24h ahead).
3. **Merge**: only once CI's TACO gate is green (all five filled) and approvals
   are in. Never push to `main` directly — always via PR.
4. **Apply / Operate**: execute in the window per `O - Operate`; validate
   before/after; rollback-first on failure; post the follow-up.

## Break-glass (P0 / P1 only)

- Infra on-call may bypass a TACO step during an active incident.
- Document every deviation in the post-mortem.

## Out of scope

- Application-level releases (deployment-job, data-api) owned by product teams —
  pushed directly to main.
- Dev-only changes (`coreproduct-dev`, `sandbox01`, `shared-dev`,
  `infrastructure-dev`) — follow the spirit of TACO, not required.

## PR body weight — match the audience

The full five-section TACO body is for **prod-impacting / critical-path**
changes only. For **`gitops-dev`** and other dev-only changes keep the PR body
lightweight: short summary + what/why + a minimal validation note. Don't
front-load a TACO checklist on a dev PR — dev is the lower env where prod-bound
changes get tested, so the checklist adds noise without value there.

## How to apply this skill

When loaded, before helping a contributor merge/apply a change:

1. **Classify**: check changed files against `.criticalpaths`. State explicitly
   whether the change is Critical and which pattern (or rule above) triggered.
2. **Checklist the PR**: verify all five sections are present **and filled** (no
   `REPLACE:` left) — lower-env evidence, Component-Owner approval, scheduled
   window, ≥24h Slack announcement link, rollback plan. Comments ≠ approval.
3. **Block the merge** until each section is satisfied, or the contributor
   explicitly invokes break-glass (and commits to documenting it in the
   post-mortem).
4. Never propose forcing reconciliation via `kubectl delete`, suspending Flux,
   or deleting helmreleases/kustomizations. Those are explicit don'ts.
5. If validation fails post-apply: **rollback first, debug after.**
