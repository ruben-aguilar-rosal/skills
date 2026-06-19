---
name: aily-context
description: |
  Aily Labs organizational context — repo-to-cluster mapping, AWS account/profile
  names, and Terraform module ownership. Use whenever a task involves deploying,
  modifying, or reasoning about configuration for a specific tenant/environment
  (coreproduct-prod, coreproduct-dev, shared-dev, shared-prod, infrastructure-dev,
  infrastructure-prod, sandbox01) so the right gitops or terragrunt repo, cluster,
  and AWS account is picked. Trigger on any mention of gitops-prod, gitops-dev,
  gitops-shared, gitops-controlplane, aily-terragrunt, terraform-modules, the
  tenant names above, or the AWS profiles ailylabs / aws-shared / aws-infrastructure
  / aws-backups / aws-sandbox01. Read-only reference skill — informs decisions,
  never makes changes.
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Aily Labs — repo ↔ cluster/tenant/account mapping

Read-only lookup skill. Pick the right repo + cluster + AWS account **before** any
downstream action skill acts. This skill does not edit anything; changes go through
the PR discipline below, enforced by the action skill that does the work.

## Repo ↔ cluster decision table (start here)

| Repo | Clusters it manages |
|------|---------------------|
| `gitops-prod` | All **prod** tenant clusters, including `coreproduct-prod`. **Does NOT** manage `shared-prod` or `infrastructure-prod`. |
| `gitops-dev` | `coreproduct-dev` and `sandbox01`. |
| `gitops-shared` | `shared-dev` and `shared-prod`. |
| `gitops-controlplane` | `infrastructure-dev` and `infrastructure-prod`. |

Rule of thumb:
- **coreproduct-{env}** → `gitops-{env}` (prod/dev).
- **Any other prod tenant cluster** → `gitops-prod` (NOT `shared-prod` / `infrastructure-prod`).
- **shared-{env}** → `gitops-shared`.
- **infrastructure-{env}** → `gitops-controlplane`.

## Terraform / Terragrunt

| Repo | What it holds |
|------|---------------|
| `aily-terragrunt` | Terragrunt live config. **Imports modules from `terraform-modules` for every tenant** — module changes reach all tenants through here. |
| `aily-terragrunt/resources/` | Shared/reusable Terragrunt resource definitions. |
| `aily-terragrunt/terragrunt/` | Tenant-specific instances (per-account, per-env, per-region). |
| `terraform-modules` | Cross-tenant module source. |

Cross-tenant infra change → almost always lives in `terraform-modules`, rolled out via `aily-terragrunt`.

## AWS accounts / profiles (canonical)

Each account has its own AWS config profile. These profile names are authoritative.

| Account | Profile | Purpose |
|---------|---------|---------|
| Management (root org) | `ailylabs` | Organization governance / audit / Control-Tower-style ops. |
| aws-infrastructure | `aws-infrastructure` | Main dev account. Tenants **coreproduct** (dev) and **infrastructure** (restricted: identity service, fasttrack control plane, Kestra). |
| aws-shared | `aws-shared` | Shared services across company and tenants. |
| aws-sandbox01 | `aws-sandbox01` | Testing / scratch resources. |
| aws-backups | `aws-backups` | Backup storage (sensitive). |
| Tenant accounts | `aws-<tenant>` | Per-client accounts. |

Rules of thumb:
- Runtime tenant resources → start in the tenant account (`aws-<tenant>`).
- Organization governance / audit trails → `ailylabs` (Management/root).
- **Centralized log retention** may live in a shared account — confirm whether it is
  `aws-shared` or `aws-backups`. There is **no separate `aws-logs` profile** in the
  standard config, and the root account's profile is `ailylabs`, **not** `aws-management`.
  Re-verify before assuming. (Upstream referenced `aws-logs` / `aws-management`; those
  names do not exist in this config — flagged here rather than silently mapped.)

## Same-account naming collisions (critical)

**`coreproduct-prod`, `coreproduct-dev`, `infrastructure-prod`, and `infrastructure-dev`
all live in the SAME AWS account.** Terragrunt paths imply separation, but in the actual
account, resource names must be globally unique per **account + region**.

- When creating resources for a `-dev` variant in a region already used by the `-prod`
  variant (typically `eu-central-1`), suffix the name with `-dev` (or otherwise
  distinguish) to avoid clashes. Example: `cluster-logs` already exists for
  `coreproduct-prod`; `coreproduct-dev` needs `cluster-logs-dev`.
- Before adding any `aws/*` terragrunt resource to a cluster, **check the sibling
  environments in the same account/region for name reuse.**

## EKS cluster naming + observability identifiers

Cluster name is `<tenant>-<env>` (e.g. `axelspringer-prod`, `gilead-prod`,
`infrastructure-prod`, `shared-prod`, `coreproduct-dev`). It drives:

- **CloudWatch log group**: `/aws/eks/<tenant>-<env>/cluster`
- **Datadog tag**: `kube_cluster_name:<tenant>-<env>` — Datadog is the **EU tenant,
  `datadoghq.eu`**.
- **kubeconfig context**: typically matches the cluster name.

## GitHub Actions self-hosted runners

All Aily self-hosted runner configuration lives in **`gitops-controlplane`** (manages
`infrastructure-prod` and `infrastructure-dev`).

- **Namespace**: `arc-runners` on `infrastructure-prod` — all runner pods land here
  regardless of which repo/team the workflow belongs to.
- **Pod naming**: `aily-runner-<scale-set>-<hash>-runner-<hash>`
  (e.g. `aily-runner-data-hqc78-runner-7ntzc`).
- **Pod name source**: visible in the GitHub Actions "Set up Job" step log of the
  failing run, or via `gh api .../jobs`.
- **Scale-set name**: strip the `-runner-<hash>` suffix from the pod name to get the
  scale-set prefix used for S3 log partitions and Datadog text filtering
  (`aily-runner-data-hqc78-runner-pgpf6` → `aily-runner-data-hqc78`).
- **ARC controller**: runs in the `arc-runners` namespace.
- **Karpenter** manages the nodes runners land on — check it when a runner disappears
  mid-job (spot interruption / eviction).

## Log investigation (handoff)

For reading logs or debugging a running workload, use the **`aily-logs`** skill. Sources:

- **S3** (`aily-logs` CLI) — application and pod logs.
- **Datadog** (`datadoghq.eu`) — events, metrics, APM, monitors.
- **CloudWatch** (`/aws/eks/<tenant>-<env>/cluster`) — Kubernetes control-plane only.

Do not duplicate `aily-logs` content here.

---

## Volatile state — re-verify against the live repo, not this table

Trust the gitops repo, not the lists below, for membership questions. These decay.

### Tenants in active scope (verify before a cross-tenant rollout)

- **Prod** (`gitops-prod`): `axelspringer`, `coreproduct`, `demos`, `farmers`, `gilead`,
  `gm`, `jnjapp`, `kering`, `pentest`, `pfizer`, `royalcanin`, `sanofi`, `sanofi-ai`,
  `teva`, `thermofisher`, `wmg`.
- **Dev**: `coreproduct-dev`, `sandbox01` (via `gitops-dev`).
- **Shared**: `shared-dev`, `shared-prod` (via `gitops-shared`).
- **Control plane**: `infrastructure-dev`, `infrastructure-prod` (via `gitops-controlplane`).

**Ignore in cross-tenant rollouts:** `azuresandbox` (not in use, do not target);
`moderna` (being decommissioned). Verify against the live gitops repo before acting.

### Fluent-bit deployment status (as of 2026-04)

- **Deployed**: all prod tenants except `sanofi` and `sanofi-ai`, plus `shared-dev`,
  `shared-prod`, `infrastructure-dev`, `infrastructure-prod`.
- **Not deployed, but planned**: `coreproduct-dev`, `sandbox01` (`gitops-dev`).
- **Not deployed**: `sanofi`, `sanofi-ai`.

Re-verify before acting — this list decays:
`grep fluent-bit <tenant>/monitoring/kustomization.yaml`

---

## Hard constraints

### PR discipline (critical)

**Always open a PR** for any change to `gitops-*`, `aily-terragrunt`, or
`terraform-modules`. Never commit directly to `main`/`master` in these repos. Feature
branch + PR even for one-line changes.

### kubectl constraints (critical)

**Never run `kubectl delete` against cluster resources to force a config pickup,
restart, or reconcile.** This includes pods, deployments, replicasets, statefulsets,
configmaps, secrets, ingresses, services, and any CRD instance (Kustomizations,
HelmReleases, Applications, etc.).

**Why:** deletes are disruptive (brief downtime, dropped connections, pending
reconciliation state), the platform already has graceful equivalents, and a forced
delete masks the real failure — if a rollout or GitOps reconcile isn't picking up a
change, the root cause matters.

**Preferred remedies, in order:**

1. Config not picked up → `kubectl rollout restart deployment/<name>` and wait. Do **not** delete pods to speed it up.
2. Flux/ArgoCD reconcile stuck → `flux reconcile kustomization <name>` / `argocd app sync`. Do **not** suspend Flux kustomizations or delete the CR.
3. Stale resource → fix the source (gitops repo / terragrunt) and let the controller reconcile. Do **not** hand-delete the live object.

A genuine delete (decommissioning a resource) requires **explicit user confirmation**
and should go through the gitops path.

Read-only kubectl (`get`, `describe`, `logs`, `top`, `events`) is always fine.

---

## How to apply

1. Identify the **target tenant + environment** from the request.
2. Pick the repo from the decision table at the top.
3. Resolve the AWS account/profile from the canonical table; if it touches centralized
   logging or governance, confirm the account rather than guessing.
4. Before creating any `aws/*` terragrunt resource, check sibling envs in the same
   account/region for name collisions.
5. Re-verify any volatile fact (tenant membership, fluent-bit status) against the live
   repo before acting.
6. Hand the actual change to the downstream action skill — it opens a PR and never
   uses `kubectl delete` to force reconciliation.

When upstream context and these identifiers disagree (notably AWS account/profile
names), state the discrepancy explicitly rather than picking one silently. If a task
needs a work item filed, default to Jira project **TP** (id 10047) on
`https://ailylabs.atlassian.net`.
