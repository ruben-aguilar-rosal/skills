# Author profile — Ruben Aguilar

Author-time context for skill adaptation. This file is read ONLY by the drafting /
reprofile agent and baked **verbatim** into each skill's `adaptation.md`; the generator
never reads it directly. Keep it factual, terse, and stack-specific.

## Role & stack

Platform / infrastructure engineer at **Aily Labs**. Day-to-day work is AWS, Kubernetes
(EKS), Terraform/Terragrunt, GitOps (ArgoCD / FluxCD), and CI on self-hosted GitHub Actions
runners. Strong preference for **gitops/PR-driven change** over imperative mutation.

## Tone & output preferences

- Terse, operational, table-first. Lead with the lookup/decision, push narrative to the end.
- Precision of identifiers (repo names, tenant names, cluster names, AWS profiles) matters
  more than prose — a wrong identifier is worse than no answer.
- Prefer concrete commands over description. Date-stamp volatile facts and tell the agent to
  re-verify them rather than trust them.
- Default to read-only / non-destructive actions; require explicit confirmation before
  anything disruptive.

## Jira

- Instance: `https://ailylabs.atlassian.net` — user `ruben.aguilar@ailylabs.com`.
- Projects: **TP** (Tech Platform, id 10047), **TI** (TechPlatform Initiatives, 10125),
  **AIS** (Aily Internal Support, 10853), **APS** (Application Support, 10193).
- When a skill files or references work items, default to the **TP** project unless the task
  clearly belongs to another.

## Observability

- **Datadog**: EU tenant — `datadoghq.eu`.
- Kubernetes control-plane logs in CloudWatch at `/aws/eks/<tenant>-<env>/cluster`.

## AWS accounts (each has its own config profile)

| Account | Profile | Purpose |
|---------|---------|---------|
| Management | `ailylabs` | Root org account |
| aws-infrastructure | `aws-infrastructure` | Main dev account; tenants **coreproduct** (dev) and **infrastructure** (restricted: identity service, fasttrack control plane, Kestra) |
| aws-shared | `aws-shared` | Shared services across company and tenants |
| aws-sandbox01 | `aws-sandbox01` | Testing / scratch resources |
| aws-backups | `aws-backups` | Backup storage (sensitive) |
| Tenant accounts | `aws-<tenant>` | Per-client accounts |

Note: `coreproduct-prod`, `coreproduct-dev`, `infrastructure-prod`, and `infrastructure-dev`
share the **same** AWS account — watch for resource-name collisions per account+region.

## Kubernetes clusters

- Naming convention: `<tenant>-<env>`.
- aws-shared: `shared-dev`, `shared-prod`.
- aws-infrastructure: `coreproduct-dev`, `coreproduct-prod`, `infrastructure-dev`,
  `infrastructure-prod`.
- Client tenants: generally only `<tenant>-prod`.

## Key internal services

- **Fasttrack** — control plane (infrastructure tenant).
- **Identity Service** — restricted (infrastructure tenant).
- **Kestra** — infrastructure job automation (infrastructure tenant).

## Working conventions (apply to action skills)

- **Always open a PR** for changes to `gitops-*`, `aily-terragrunt`, and `terraform-modules`;
  never commit directly to `main`/`master`. Feature branch + PR even for one-line changes.
- **Never `kubectl delete`** cluster resources to force a config pickup / restart / reconcile.
  Prefer `kubectl rollout restart`, `flux reconcile kustomization`, `argocd app sync`, or
  fixing the gitops source. Read-only kubectl (`get`/`describe`/`logs`/`top`/`events`) is fine.
