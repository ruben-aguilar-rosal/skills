---
name: aily-logs
description: |
  Investigate Aily tenant logs across three sources: S3 cluster logs (aily-logs
  CLI), Datadog (API), and CloudWatch EKS control-plane logs. Use when
  investigating pod/container logs, historical cluster logs, Kubernetes component
  errors (scheduler, API server, etcd, kubelet), Datadog events/metrics/monitors,
  or when the user asks to inspect logs for a tenant, namespace, app, pod,
  container, timestamp, incident, Jira ticket, or deployment issue.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# aily-logs

Investigate Aily tenant logs from three sources depending on the issue type.

## Which log source to use

| What you're looking for | Source |
|-------------------------|--------|
| Application / pod logs (app crashes, errors, request traces) | S3 via `aily-logs` CLI |
| Pod lifecycle events (OOMKill, probe failures, eviction), metrics, APM | Datadog |
| Kubernetes control-plane events (scheduler, API server, controller-manager, etcd, kubelet, CNI, CSI) | CloudWatch (`/aws/eks/$tenant-prod/cluster`) |

If fluent-bit is not yet deployed for the tenant (see `aily-context` skill for status),
S3 logs will be empty — fall back to Datadog or live `kubectl logs`.

---

## S3 logs — `aily-logs` CLI

Use `aily-logs` to inspect historical Kubernetes logs from discovered
`aily-*-cluster-logs` S3 buckets.

### Installation

Use the CLI directly when installed:

```bash
aily-logs --tenant infrastructure --namespace karpenter --since 30m --limit 20
```

If `aily-logs` is not installed, install globally with `uv`:

```bash
# 1. Verify the repo exists
ls ~/Aily/Repositories/aily-devops-tools/scripts/python/aily_logs/

# 2. Pull latest from main
git -C ~/Aily/Repositories/aily-devops-tools pull origin main

# 3. Install globally
cd ~/Aily/Repositories/aily-devops-tools/scripts/python/aily_logs
uv tool install .

# 4. Confirm
aily-logs --version
```

If running from source without installing:

```bash
cd scripts/python/aily_logs
uv run aily-logs --tenant infrastructure --namespace karpenter --since 30m --limit 20
```

If running from Docker:

```bash
docker run --rm --platform linux/amd64 \
  -v "$HOME/.aws:/home/ailylogs/.aws:ro" \
  -e AWS_PROFILE=aws-infrastructure \
  258781458051.dkr.ecr.eu-central-1.amazonaws.com/aily-logs:0.1.0 \
  --profile aws-infrastructure --tenant infrastructure --namespace karpenter --since 30m --limit 20
```

### Memory and performance warning

aily-logs uses DuckDB with httpfs to stream gzipped NDJSON files from S3.
**Actual process memory can reach 32GB+ on wide queries** because DuckDB's
`ORDER BY ts LIMIT N` forces a full scan before applying the limit.

**Rules to avoid OOM:**

1. **Always specify `--app`** — without it, every app partition in the namespace is scanned.
2. **For runner pods**, derive `--app` from the pod name by stripping `-runner-<hash>`:
   - Pod `aily-runner-data-hqc78-runner-pgpf6` → `--app aily-runner-data-hqc78`
3. **Always use `--from`/`--to`** with the tightest window you know.
4. **Start with `--limit 20`** and increase only if needed.
5. **Always use `--grep`** to pre-filter in DuckDB.
6. **Never use `--wide-scan`** unless absolutely necessary.
7. **Kill and retry** (`Ctrl-C`) if memory climbs — then retry with a tighter window.

The S3 `app=` partition label may not match the pod name exactly. Always
discover it first:

```bash
aily-logs --tenant infrastructure-prod --namespace arc-runners --list-apps
```

### Workflow

1. Pick the tenant alias with `--tenant`. Use `aily-logs --list-tenants` when unsure.
   Use `aily-logs --refresh-cache --list-tenants` after profile or bucket changes.
   Preferred explicit aliases: `coreproduct-prod`, `coreproduct-dev`, `shared-prod`,
   `shared-dev`, `infrastructure-prod`, `infrastructure-dev`.
2. Prefer narrow queries: `--namespace`, `--app`, `--pod`, `--container`,
   `--since`, `--around`, or `--from`/`--to`, and a small `--limit`.
3. Discover partitions before broad searches:

   ```bash
   aily-logs --tenant infrastructure --list-namespaces
   aily-logs --tenant infrastructure --namespace kube-system --list-apps
   ```

4. Use `--around <ISO8601>` for incidents with a known timestamp, or
   `--from`/`--to` for exact ranges.
5. Use `--grep` for message filtering and `--json` when parsing output.

### Credentials

- Local SSO: `aws sso login --profile <profile>` for profiles with access to
  cluster log buckets. Profile names are discovered, not hardcoded.
- Docker with local SSO: mount `$HOME/.aws`; pass `--profile` to restrict discovery.
- Runtime credentials (env, ECS, IRSA): pass `--profile none` and prefer `--bucket`.

```bash
aws sso login --profile aws-infrastructure
aily-logs --tenant infrastructure --namespace kube-system --since 15m --limit 20
```

### Query examples

```bash
aily-logs --refresh-cache --list-tenants

# Runner pods — always derive --app from pod name
aily-logs --tenant infrastructure-prod --namespace arc-runners \
  --app aily-runner-data-hqc78 --pod pgpf6 \
  --from 2026-05-06T10:06:00Z --to 2026-05-06T10:40:00Z \
  --grep '(?i)error|kill|oom|memory|fatal' --limit 30

# Karpenter
aily-logs --tenant infrastructure-prod --namespace karpenter \
  --from 2026-04-29T08:00:00Z --to 2026-04-29T08:30:00Z --limit 100

# Ingress errors
aily-logs --tenant infrastructure-prod --namespace nginx-ingress-external \
  --app ingress-nginx --grep '(?i)error|timeout|upstream' --since 1h --limit 100

# Service pods (shared app label)
aily-logs --tenant coreproduct-prod --namespace prod \
  --app saas-backend --pod mobile-bff --since 24h --limit 100

# Known incident time
aily-logs --tenant infrastructure-prod --namespace arc-runners \
  --pod aily-runner-python --around 2026-04-22T11:30:00Z --around-window 20
```

---

## Datadog

**Read-only — ONLY GET operations. NEVER create, update, delete, or mutate any
Datadog resource. If a task would require a write, stop and ask the user.**

**Never print or expand credential values.** Always `source ~/.claude/.env` and
use `${DATADOG_API_KEY}`, `${DATADOG_APP_KEY}`, `${DATADOG_SITE}` directly in
the same shell invocation as the curl call.

Credentials in `~/.claude/.env`:

```bash
source ~/.claude/.env
# Provides: DATADOG_API_KEY, DATADOG_APP_KEY, DATADOG_SITE (e.g. datadoghq.eu)
```

Datadog has three separate stores:

- **Events v2 API** (`/api/v2/events`) — pod lifecycle events filtered by pod name.
  Use this first for any runner/pod investigation. ISO8601 timestamps.
- **Events v1 API** (`/api/v1/events`) — namespace-wide events, Karpenter.
  Epoch seconds. High noise on `arc-runners` (1000+/hr).
- **Logs API** (`/api/v2/logs/events/search`) — container stdout/stderr. ISO8601.
- **Metrics API** (`/api/v1/query`) — CPU/memory time series. Epoch seconds.

### Events v2 — pod-specific (use this first)

Filters by `pod_name:X` — same query as the Datadog Events Explorer UI.
Returns ~10–20 events for a typical pod lifecycle. ISO8601 timestamps.

```bash
source ~/.claude/.env
curl -s -G "https://api.${DATADOG_SITE}/api/v2/events" \
  --data-urlencode "filter[query]=pod_name:<full-pod-name>" \
  --data-urlencode "filter[from]=<from-ISO8601>" \
  --data-urlencode "filter[to]=<to-ISO8601>" \
  -d "page[limit]=50" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" | \
  python3 -c "
import json,sys
d=json.load(sys.stdin)
events=d.get('data',[])
print('Total events:', len(events))
for e in events:
    attrs=e.get('attributes',{})
    ts=attrs.get('timestamp','?')
    msg=str(attrs.get('message','') or attrs.get('text',''))
    print(f'{ts} | {msg[:300]}')
    print()
"
```

### Events v1 — Karpenter / namespace-wide (fallback)

Uses **epoch seconds** (not ISO8601).

**CRITICAL — epoch must be UTC. Never use Python's naive `datetime.timestamp()`
— it returns local-time epoch. Always use the `date` command:**

```bash
source ~/.claude/.env
END_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<to>" "+%s" 2>/dev/null || date -u -d "<to>" "+%s")
START_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<from>" "+%s" 2>/dev/null || date -u -d "<from>" "+%s")

curl -s "https://api.${DATADOG_SITE}/api/v1/events?start=${START_EPOCH}&end=${END_EPOCH}&tags=kube_cluster_name:infrastructure-prod,kube_namespace:karpenter" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" | \
  python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
for e in d.get('events',[]):
    ts=e.get('date_happened','')
    t=datetime.datetime.utcfromtimestamp(ts).strftime('%H:%M:%SZ') if ts else '?'
    print(t, e.get('title',''), e.get('text','')[:200])
"
```

**Note:** On `arc-runners`, the v1 `tags=pod_name:X` filter silently returns 0.
Use the v2 API for pod-specific queries. For namespace-wide v1 queries, use a
tight window (±5 min) and filter in Python by pod/scale-set name.

### Logs API — container stdout/stderr

```bash
source ~/.claude/.env
curl -s -X POST "https://api.${DATADOG_SITE}/api/v2/logs/events/search" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "query": "kube_cluster_name:infrastructure-prod kube_namespace:arc-runners",
      "from": "<from-ISO8601>",
      "to": "<to-ISO8601>"
    },
    "page": { "limit": 50 }
  }'
```

Useful filter tags: `kube_cluster_name`, `kube_namespace`, `kube_deployment`,
`service`, `pod_name`, `container_name`.

### Metrics API — CPU / memory time series

```bash
source ~/.claude/.env
END_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<to>" "+%s" 2>/dev/null || date -u -d "<to>" "+%s")
START_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<from>" "+%s" 2>/dev/null || date -u -d "<from>" "+%s")

# Memory usage for a pod — did it climb to its limit?
curl -s "https://api.${DATADOG_SITE}/api/v1/query?from=${START_EPOCH}&to=${END_EPOCH}&query=max:kubernetes.memory.usage{kube_cluster_name:infrastructure-prod,kube_namespace:arc-runners,pod_name:<pod>}" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" | \
  python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
series=d.get('series',[])
if not series: print('No data'); sys.exit()
for ts,val in series[0].get('pointlist',[])[-10:]:
    t=datetime.datetime.utcfromtimestamp(ts/1000).strftime('%H:%M:%SZ')
    print(f'{t}  {val/1024/1024:.1f} MiB' if val else f'{t}  no data')
"
```

Useful metrics:

| Metric | What it tells you |
|---|---|
| `kubernetes.memory.usage` | Actual memory used by pod |
| `kubernetes.memory.usage_pct` | % of limit — climbing to 100% = OOM incoming |
| `kubernetes.cpu.usage.total` | CPU usage (nanocores) |
| `kubernetes.cpu.throttled` | CPU throttling — high = starvation |

---

## CloudWatch — EKS control-plane logs

Use for Kubernetes component issues (scheduler, API server, controller-manager,
etcd). These logs will NOT appear in S3 or Datadog.

Each tenant EKS cluster writes control-plane logs to:
```
/aws/eks/$tenant-prod/cluster
```

**Read-only — only `aws logs` describe/get/filter commands. Never put-log-events,
create-log-group, or any mutating call.**

```bash
# Discover log streams
aws logs describe-log-streams \
  --log-group-name /aws/eks/infrastructure-prod/cluster \
  --profile aws-infrastructure \
  --order-by LastEventTime --descending --max-items 20

# Filter by pattern — timestamps are epoch milliseconds
aws logs filter-log-events \
  --log-group-name /aws/eks/infrastructure-prod/cluster \
  --filter-pattern "ERROR" \
  --start-time $(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<from>" "+%s000" 2>/dev/null) \
  --profile aws-infrastructure
```

---

## Pod manifest lookup

When you need to understand a pod's config (resources, probes, env vars, image)
during a triage, the manifest lives in a gitops repo:

| Tenant cluster | Gitops repo |
|----------------|-------------|
| All prod tenants | `gitops-prod` |
| `coreproduct-prod` | `gitops-prod` |
| `infrastructure-prod` / `infrastructure-dev` | `gitops-controlplane` |
| `shared-prod` / `shared-dev` | `gitops-shared` |
| `coreproduct-dev` / `sandbox01` | `gitops-dev` |

---

## Reporting

- Summarize relevant log lines with timestamps, pod/container, and why they matter.
- Do not paste large raw logs unless the user asks.
- Redact tokens, passwords, API keys, and customer-sensitive payloads before sharing.
- Mention the exact query used when reporting findings.
