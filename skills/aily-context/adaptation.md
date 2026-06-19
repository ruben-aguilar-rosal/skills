# Adaptation guidance — `aily-context`

This file is the ONLY context the generator reads. It is self-contained: the author
profile below is baked in verbatim, followed by concrete, skill-specific instructions for
adapting the upstream `aily-context` skill to this author's stack and tone.

---

## Author profile — Ruben Aguilar (verbatim)

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
| --- | --- | --- |
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

---

## What this skill is

`aily-context` is a **reference / lookup** skill, not an action skill. It maps tenant +
environment → the correct gitops/terragrunt repo, records cross-account naming-collision
hazards, fluent-bit deployment state, EKS naming conventions, ARC self-hosted runner
layout, and the PR / `kubectl delete` discipline. It is read-only (`allowed-tools: Read,
Grep, Glob`) and exists so other skills and the agent pick the right repo/cluster/account
before acting.

Because this skill is *already* Aily-specific and authored against the same environment as
the profile above, adaptation is mostly **reconciliation and hardening**, not rewriting.
The upstream content is authoritative on repo↔cluster mapping; the profile is authoritative
on AWS account/profile names. Where they disagree, flag it — do not silently pick one.

## Adaptation directives

1. **Keep the skill read-only.** Preserve `allowed-tools: Read, Grep, Glob`. This skill
   informs decisions; it must not gain Bash/Edit/Write. Any "do the change" lives in the
   downstream action skill, governed by the PR discipline below.

2. **Preserve the repo↔cluster mapping table verbatim in structure.** Lead with it. The
   decision table is the entire value of the skill — keep it first, keep it as a table:
   - `coreproduct-{env}` → `gitops-{env}`
   - any other prod tenant cluster → `gitops-prod` (NOT `shared-prod` / `infrastructure-prod`)
   - `shared-{env}` → `gitops-shared`
   - `infrastructure-{env}` → `gitops-controlplane`

3. **Reconcile AWS account names — this is the most important correction.** The upstream
   text references `aws-management` and `aws-logs` as shared accounts. The author profile's
   canonical account/profile list is: `ailylabs` (Management/root), `aws-infrastructure`,
   `aws-shared`, `aws-sandbox01`, `aws-backups`, and per-tenant `aws-<tenant>`. There is
   **no `aws-logs` profile in the author's list** and the root org account's profile is
   `ailylabs`, not `aws-management`. In the adapted skill:
   - Use the author's profile names as canonical (`ailylabs`, `aws-shared`, `aws-backups`,
     etc.).
   - Where upstream says "centralized logging context (`aws-logs`)", rewrite as: "centralized
     log retention may live in a shared account — confirm whether it is `aws-shared` or
     `aws-backups`; there is no separate `aws-logs` profile in the standard config. Re-verify
     before assuming." Do not invent an `aws-logs` profile.
   - Map "organization governance / audit" to the `ailylabs` (Management/root) account.

4. **Keep and reinforce the same-account collision warning.** It matches the profile note
   verbatim: `coreproduct-prod`, `coreproduct-dev`, `infrastructure-prod`,
   `infrastructure-dev` share ONE AWS account. Keep the concrete example (`cluster-logs` vs
   `cluster-logs-dev` in `eu-central-1`) and the rule "check sibling envs in the same
   account/region for name reuse before adding any `aws/*` terragrunt resource."

5. **Date-stamp and quarantine all volatile state.** Per the author's tone preference,
   anything that decays must carry a date and a re-verify command:
   - The fluent-bit deployment status is stamped `as of 2026-04`. Keep the stamp and keep
     the verify command: `grep fluent-bit <tenant>/monitoring/kustomization.yaml`.
   - The active-tenant list and ignore-list (`azuresandbox` not in use, `moderna`
     decommissioning) are volatile — mark them "verify against the live gitops repo before a
     cross-tenant rollout."
   - Tell the agent explicitly: trust the repo, not this table, for membership questions.

6. **Keep the PR discipline section as a hard constraint, aligned to the profile.** Always
   open a PR for `gitops-*`, `aily-terragrunt`, `terraform-modules`; never commit to
   `main`/`master`; feature branch even for one-liners. This is identical to the author's
   working conventions — keep it prominent.

7. **Keep the `kubectl delete` prohibition as a hard constraint.** Never `kubectl delete`
   to force a config pickup/restart/reconcile (pods, deployments, RS, STS, configmaps,
   secrets, ingresses, services, or any CRD instance incl. Kustomizations/HelmReleases/
   Applications). Preferred remedies, in order: `kubectl rollout restart deployment/<name>`;
   `flux reconcile kustomization <name>` / `argocd app sync`; fix the gitops/terragrunt
   source and let the controller reconcile. A genuine delete (decommissioning) requires
   explicit user confirmation and should go through the gitops path. Read-only kubectl
   (`get`/`describe`/`logs`/`top`/`events`) is always fine.

8. **EKS naming + observability identifiers — keep exact and cross-link the profile.**
   Cluster name is `<tenant>-<env>` (e.g. `axelspringer-prod`, `coreproduct-dev`). It drives:
   - CloudWatch log group `/aws/eks/<tenant>-<env>/cluster` (matches profile).
   - Datadog tag `kube_cluster_name:<tenant>-<env>` — and Datadog is the **EU tenant
     `datadoghq.eu`** (from profile; add this, upstream omits the site).
   - kubeconfig context (typically matches the cluster name).

9. **GitHub Actions self-hosted runners — keep the operational detail.** Runner config
   lives in `gitops-controlplane`; pods land in namespace `arc-runners` on
   `infrastructure-prod`; pod naming `aily-runner-<scale-set>-<hash>-runner-<hash>`; strip
   `-runner-<hash>` to get the scale-set prefix (used for S3 log partitions and Datadog text
   filtering); ARC controller in `arc-runners`; Karpenter manages the nodes (check on
   mid-job runner disappearance — spot interruption/eviction). This matches the author's
   self-hosted-runner CI stack — preserve verbatim.

10. **Cross-link the log-investigation handoff.** Keep the pointer that log/debug tasks use
    the `aily-logs` skill (S3 via `aily-logs` CLI; Datadog for events/metrics/APM/monitors;
    CloudWatch for control-plane only). Do not duplicate that skill's content here.

11. **Jira default.** This skill does not file work items, but if adaptation adds any
    "file a ticket" affordance, default to project **TP** (id 10047) on
    `https://ailylabs.atlassian.net`.

## Tone for the generated skill

Table-first, terse, operational. Lead with the repo↔cluster decision table; push the
narrative (rules of thumb, rationale, "why") to the end. Favor exact identifiers over prose.
Every volatile fact carries a date and a `grep`/lookup command to re-verify it. Default to
read-only; surface a confirmation gate before anything disruptive. When upstream and this
profile disagree on an identifier (notably the AWS account/profile names in directive 3),
state the discrepancy explicitly rather than guessing.