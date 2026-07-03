# Kubernetes skills

Vendored, verbatim agent skills for Kubernetes, Helm, and GitOps (Flux CD). Two upstreams feed
this category; every skill is committed **verbatim** (no LLM adaptation) and pinned by commit SHA
in `sources.yaml`.

> Related categories vendored from the same upstreams: **`skills/iac`** (Terraform/Terragrunt) and
> **`skills/observability`** (PromQL/LogQL).

## Source & attribution

| Upstream | Repo | Synced SHA | License |
|----------|------|------------|---------|
| Flux CD GitOps skills | [`fluxcd/agent-skills`](https://github.com/fluxcd/agent-skills) | `9c50a83` | Apache-2.0 |
| DevOps generator/validator skills | [`akin-ozer/cc-devops-skills`](https://github.com/akin-ozer/cc-devops-skills) | `feaf2b2` | per upstream |

Each skill keeps a pristine upstream mirror under `<skill>/.upstream/`, which is the scan surface
for the security gate — do not hand-edit it.

## What each skill does

### Flux CD / GitOps (`fluxcd/agent-skills`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `gitops-cluster-debug` | `gitops-cluster-debug` | Debugging Flux on **live clusters** via the Flux MCP server — failing/stuck resources, reconciliation errors, controller issues, artifact pull failures. **Requires `flux-operator-mcp`.** |
| `gitops-knowledge` | `gitops-knowledge` | Flux concepts and **schema-validated YAML** for any Flux CRD (HelmRelease, Kustomization, GitRepository, OCIRepository, ResourceSet, FluxInstance); bootstrap, multi-tenancy, image automation. |
| `gitops-repo-audit` | `gitops-repo-audit` | Auditing a GitOps **repo's local files** — K8s schema validation, deprecated Flux API detection, RBAC/secrets review, prioritized report. |

### Kubernetes / Helm (`akin-ozer/cc-devops-skills`)

| Folder | Skill `name` | Triggers on |
|--------|--------------|-------------|
| `k8s-debug` | `k8s-debug` | Diagnosing pods — CrashLoopBackOff, Pending, DNS, networking, storage, rollout failures with `kubectl`. |
| `k8s-yaml-generator` | `k8s-yaml-generator` | Generating/scaffolding K8s YAML — Deployment, Service, ConfigMap, Ingress, RBAC, StatefulSet, CRDs. |
| `k8s-yaml-validator` | `k8s-yaml-validator` | Validating/linting/dry-running K8s manifests. |
| `helm-generator` | `helm-generator` | Creating/scaffolding Helm charts — Chart.yaml, values.yaml, templates, helpers. |
| `helm-validator` | `helm-validator` | Validating/linting/auditing Helm charts, values, CRDs, schemas. |

> Aily relevance: `gitops-*` map onto the `gitops-prod`/`gitops-dev`/`gitops-shared` Flux workflows;
> `k8s-*` and `helm-*` onto everyday cluster debugging and chart work.

## How to use

The agent auto-loads a skill when a request matches its `description` (the trigger column above) —
no explicit invocation needed. To invoke one explicitly, name it, e.g. *"use the `k8s-debug` skill
on this CrashLoopBackOff"*.

Vendored skills are **unlinked** by default. To activate them under `~/.claude/skills`:

```bash
uv run skillsync link
```

## Updating

```bash
uv run skillsync sync     # pull upstream changes for the pinned skills
uv run skillsync status   # per-skill synced SHA, drift, and link state
```

### Gate overrides carried on these pins

Every skill tripped NVIDIA SkillSpector's static gate; **all findings were reviewed and judged
benign** before vendoring. Overrides recorded in `sources.yaml`:

- **`accept_findings`** — keyword/heuristic matches with no real risk:
  - `PE3` (Privilege Escalation): hits on the strings `kubeConfig` (a legitimate field in Flux
    HelmRelease/Kustomization CRD schemas), `.env` / `secret.yaml` (in Helm example templates and
    reference docs), and "access tokens" (in security-audit reference prose).
  - `RA1` (Rogue Agent — self-modification): the phrase "overwrite existing file" appears in
    JSON-schema field descriptions and in a generator's help text.
  - `TM1` (Tool Misuse): a `--insecure` TLS path in `k8s-debug`'s `network_debug.sh` is explicitly
    gated behind a flag with a warning (the default path validates the CA); a `rm -f` in
    `helm-generator` deletes the `.bak` file from a prior `sed -i.bak`.
  - `OH1` (Output Handling): `subprocess.run(...)` calls in helper/test scripts that shell out to
    `kubectl` with a fixed arg list (`shell=False`), no user-interpolated string.
- **`accept_invalid: true`** — carried on every skill that references a **bundled file** from its
  `SKILL.md` (e.g. `templates/_helpers.tpl`, `flux-system/gotk-components.yaml`). The validator
  checks referenced paths *before* the bundled files are mirrored into place, so these are false
  positives. `k8s-debug` and `k8s-yaml-generator` validate clean and carry no `accept_invalid`.
