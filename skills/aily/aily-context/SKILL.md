---
name: aily-context
description: |
  Aily Labs organizational context — repo-to-cluster mapping and Terraform module
  ownership. Use whenever a task involves deploying, modifying, or reasoning
  about configuration for a specific tenant/environment (coreproduct-prod,
  coreproduct-dev, shared-dev, shared-prod, infrastructure-dev,
  infrastructure-prod, sandbox01) so the right gitops or terragrunt repo is
  picked. Trigger on any mention of gitops-prod, gitops-dev, gitops-shared,
  gitops-controlplane, aily-terragrunt, terraform-modules, or the tenant names
  above.
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Aily Labs — repo ↔ cluster/tenant mapping

Use this mapping to decide which repo to edit for a given tenant/environment.

## Gitops repos (Kubernetes / ArgoCD / FluxCD)

| Repo | Clusters it manages |
|------|---------------------|
| `gitops-prod` | All **prod** tenant clusters, including `coreproduct-prod`. **Does NOT** manage `shared-prod` or `infrastructure-prod`. |
| `gitops-dev` | `coreproduct-dev` and `sandbox01`. |
| `gitops-shared` | `shared-dev` and `shared-prod`. |
| `gitops-controlplane` | `infrastructure-dev` and `infrastructure-prod`. |

Rule of thumb:
- **coreproduct-{env}** → `gitops-{env}` (prod/dev).
- **Any other prod tenant cluster** → `gitops-prod`.
- **shared-{env}** → `gitops-shared`.
- **infrastructure-{env}** → `gitops-controlplane`.

## Terraform / Terragrunt

- `aily-terragrunt` is the Terragrunt live config. It **imports modules from
  `terraform-modules` for every tenant** — so module changes in
  `terraform-modules` reach all tenants through `aily-terragrunt`.
- Shared/reusable Terragrunt resource definitions live in
  `aily-terragrunt/resources/`.
- Tenant-specific instances live in `aily-terragrunt/terragrunt/` (per-account,
  per-env, per-region).

## Tenants — what counts

Only these tenants are in active scope for cross-tenant work:

- **Prod** (`gitops-prod`): `axelspringer`, `coreproduct`, `demos`, `farmers`,
  `gilead`, `gm`, `jnjapp`, `kering`, `pentest`, `pfizer`, `royalcanin`,
  `sanofi`, `sanofi-ai`, `teva`, `thermofisher`, `wmg`.
- **Dev**: `coreproduct-dev`, `sandbox01` (via `gitops-dev`).
- **Shared**: `shared-dev`, `shared-prod` (via `gitops-shared`).
- **Control plane**: `infrastructure-dev`, `infrastructure-prod` (via
  `gitops-controlplane`).

Tenants to **ignore** in cross-tenant rollouts:

- `azuresandbox` — not in use, do not target.
- `moderna` — being decommissioned.

## Fluent-bit deployment status (as of 2026-04)

- **Deployed**: all prod tenants except `sanofi` and `sanofi-ai`, plus
  `shared-dev`, `shared-prod`, `infrastructure-dev`, `infrastructure-prod`.
- **Not deployed, but planned**: `coreproduct-dev`, `sandbox01` (gitops-dev).
  Needs to be added.
- **Not deployed**: `sanofi`, `sanofi-ai`.

Verify current state with `grep fluent-bit <tenant>/monitoring/kustomization.yaml`
before acting — this list decays.

## Shared AWS accounts (naming collisions)

Several clusters share the same AWS account. Terragrunt path implies separation,
but in the actual AWS account, resource names must be globally unique per
account+region. Watch out for collisions:

- **`coreproduct-prod`, `coreproduct-dev`, `infrastructure-prod`,
  `infrastructure-dev` all live in the SAME AWS account.** When creating
  resources for the `-dev` variants in a region already used by the `-prod`
  variant (typically `eu-central-1`), suffix the resource name with `-dev` (or
  otherwise distinguish) to avoid clashes. Example: `cluster-logs` already
  exists for `coreproduct-prod`; `coreproduct-dev` needs `cluster-logs-dev`.
- When adding any `aws/*` terragrunt resource to a cluster, first check the
  sibling environments in the same account/region for name reuse.

## Shared AWS accounts (operational context)

Some investigations and operations use centralized/shared AWS accounts in
addition to tenant accounts. Keep this in mind before assuming data only lives
inside the tenant account itself.

- `aws-management`: organization-level/account-level administrative context
  (Control Tower/AFT/governance style operations).
- `aws-logs`: centralized logging context used for cross-account log retention
  and investigations.

Rule of thumb:
- For runtime tenant resources, start in the tenant account.
- For organization governance/audit trails, verify whether the source of truth
  is in shared accounts (especially `aws-management` and `aws-logs`).

## PR discipline (critical)

**Always open a PR** for any change to `gitops-*`, `aily-terragrunt`, or
`terraform-modules`. Never commit directly to `main`/`master` in these repos.
Feature branch + PR even for one-line changes.

## kubectl constraints (critical)

**Never run `kubectl delete` against cluster resources to force a config
pickup, restart, or reconcile.** This includes pods, deployments,
replicasets, statefulsets, configmaps, secrets, ingresses, services, and
any CRD instances (Kustomizations, HelmReleases, Applications, etc.).

**Why:** Deletes are disruptive (brief downtime, dropped connections,
pending reconciliation state) and the platform already has graceful
equivalents. Forcing a delete also masks the real failure — if a rollout
or GitOps reconcile isn't picking up a change, the root cause matters.

**How to apply:**

- Config not picked up → `kubectl rollout restart deployment/<name>` and
  wait. Do **not** delete pods to speed it up.
- Flux/ArgoCD reconcile stuck → trigger a reconcile (`flux reconcile
  kustomization <name>` / `argocd app sync`). Do **not** suspend Flux
  kustomizations or delete the CR.
- Stale resource → fix the source (gitops repo, terragrunt) and let the
  controller reconcile. Do **not** hand-delete the live object.
- If a delete genuinely is the right call (e.g., removing a decommissioned
  resource), confirm with the user first and prefer the gitops path.

Read-only kubectl (`get`, `describe`, `logs`, `top`, `events`) is always
fine.

## EKS cluster naming

Production clusters are named `$tenant-prod` (e.g. `axelspringer-prod`,
`gilead-prod`, `infrastructure-prod`, `shared-prod`). Dev clusters follow
`$tenant-dev` (e.g. `coreproduct-dev`). This name is used in:

- **CloudWatch log group**: `/aws/eks/$tenant-prod/cluster`
- **Datadog tag**: `kube_cluster_name:$tenant-prod`
- **kubeconfig context**: typically matches the cluster name

## GitHub Actions self-hosted runners

All Aily self-hosted runner configuration lives in **`gitops-controlplane`**
(manages `infrastructure-prod` and `infrastructure-dev`).

- **Namespace**: `arc-runners` on `infrastructure-prod` — all runner pods land
  here regardless of which repo or team the workflow belongs to.
- **Pod naming**: `aily-runner-<scale-set>-<hash>-runner-<hash>`
  e.g. `aily-runner-data-hqc78-runner-7ntzc`
- **Pod name source**: visible in the GitHub Actions "Set up Job" step log of
  the failing workflow run, or via `gh api .../jobs` programmatically.
- **ARC controller**: runs in the `arc-runners` namespace
- **Karpenter** manages the nodes runners land on — check it when a runner
  disappears mid-job (spot interruption, eviction)
- **Scale-set name**: strip `-runner-<hash>` suffix from pod name to get the
  scale-set prefix used for S3 log app partitions and Datadog text filtering.
  e.g. `aily-runner-data-hqc78-runner-pgpf6` → scale-set `aily-runner-data-hqc78`

## Log investigation

When a task involves reading logs or debugging a running workload, use the
**aily-logs** skill. It covers three sources:

- **S3** (`aily-logs` CLI) — application and pod logs
- **Datadog** — events, metrics, APM, monitors
- **CloudWatch** (`/aws/eks/$tenant-prod/cluster`) — Kubernetes control-plane only

## How to apply

When the user asks to deploy, change config, add a monitor, tweak a Helm
release, etc., first identify the **target tenant + environment**, then pick
the repo using the table above. If the change is cross-tenant infrastructure
(Terraform modules), it almost always lives in `terraform-modules` and gets
rolled out via `aily-terragrunt`.
