---
name: infra-triage
description: |
  First-pass triage of on-call incidents, Jira APS tickets, and GitHub Actions
  failures for Aily infrastructure. Trigger whenever the user asks for help
  investigating an APS ticket, a tenant incident, a broken deployment, a
  failing kustomization, a crashlooping pod, 5xx on an endpoint, a GitHub
  Actions workflow failure, a GHA runner that lost communication or was
  cancelled, a self-hosted runner pod dying, "troubleshoot this GHA/workflow/
  run", a GitHub Actions URL (github.com/.../actions/runs/...), or any
  similar on-call or CI/CD signal. Read the ticket via the `jira` skill,
  identify the tenant/cluster via `aily-context`, pull obvious signals
  (kubectl get/describe/logs, flux get, Datadog, aily-logs), and produce a
  human-readable triage summary. Strictly read-only against clusters, AWS, GitHub, and Git: never
  applies, never pushes, never transitions tickets.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Infrastructure triage workflow

Investigation-only. No applies, no PRs, no ticket transitions, no mutations
of any kind on clusters, AWS, GitHub, or Git.

## Inputs

- A Jira ticket key (e.g. `APS-10123`), a GHA URL
  (e.g. `https://github.com/Aily-Labs/aily-data/actions/runs/12345`), or a
  free-form description of the problem.
- `~/.claude/.env` — Jira, Datadog, and Confluence credentials.

## Load skills at the start

Always load these before starting:
- **`aily-logs`** — Datadog, S3, CloudWatch commands and credentials
- **`aily-context`** — tenant→repo mapping, cluster naming, runner conventions

## Preconditions

```bash
grep '^\[profile' ~/.aws/config    # discover real AWS profile names; never guess
kubectl config current-context     # confirm right cluster context
```

If kubectl context doesn't match the target tenant, ask the user to switch —
do not run `kubectl config use-context` yourself.

If any `aws` command fails with SSO expiry, stop and tell the user:
> "Run `aws sso login --profile <profile>` then let me know when done."

## Workflow

### Step 1 — Understand the problem

If given a Jira ticket: read it via the `jira` skill.
Extract: summary, description, priority, labels, `Tenants 3.0` field, Aily
Component, linked Datadog monitors or Sentry issues. Remember the APS
numeric-id workaround for JSM.

If given a GHA URL or free-form description: proceed to Step 2 directly.

Identify: tenant, service, environment, approximate failure time.

### Step 2 — GitHub Actions failures

Use this when the signal involves a GHA URL, "runner lost communication",
"runner disconnected", or a job that died mid-run.

**2a. Verify gh auth:**
```bash
gh auth status   # must show ✓ Logged in; stop if not
```

**2b. Find the correct failing job (programmatic — do not grep log output for runner name):**
```bash
gh api repos/<org>/<repo>/actions/runs/<run-id>/jobs 2>&1 | python3 -c "
import json,sys
d=json.load(sys.stdin)
for job in d.get('jobs',[]):
    if job.get('conclusion') == 'failure' and job.get('runner_name'):
        print('job_id:', job['id'])
        print('job_name:', job['name'])
        print('runner_name:', job['runner_name'])
        print('started_at:', job['started_at'])
        print('completed_at:', job['completed_at'])
        print()
"
```

Then confirm by checking steps — a runner-death job has steps ending in `null`:
```bash
gh api repos/<org>/<repo>/actions/jobs/<job-id> 2>&1 | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('runner:', d.get('runner_name'))
print('start:', d.get('started_at'), 'end:', d.get('completed_at'))
for s in d.get('steps',[]): print(s.get('conclusion','null'), s['name'])
"
```

Orchestrator jobs (watcher scripts) fail because a child failed — all their
steps complete. Runner-death jobs have `null` steps at the end.

Set `JOB_START` and `JOB_END` from `started_at` / `completed_at`.

**2c. Classify before any cluster investigation:**

| Signal | Classification | Action |
|---|---|---|
| Runner died mid-job, `null` steps, "lost communication" | **Infra** | Continue to Step 3 immediately |
| Runner completed, job exited with a clear error message | **Code/config** | Report the error, stop — no cluster queries |
| Partial output then silence, unclear | **Ambiguous** | Ask user before proceeding |

**Code/config failures: stop here, surface the error, do not query clusters.**

### Step 3 — Cluster investigation (infra failures only)

ALL Aily self-hosted runners are on `infrastructure-prod`, namespace
`arc-runners`, regardless of which repo or team the workflow belongs to.

**Source priority — always in this order:**

**3a. Datadog Events — always start here** (fastest, zero local memory, shows pod death reason).

**Two separate APIs — use them in order:**

**API 1 — Events v2 (pod-specific, low noise): use this first when you have the pod name.**

The v2 API accepts `filter[query]=pod_name:<pod>` which maps directly to the
Datadog Events Explorer query. Returns only events for that pod (~10–20 events
for a typical runner lifecycle) rather than 1000+ namespace-wide events.

- Timestamps are **ISO8601** (not epoch seconds)
- Returns `data[]` array (not `events[]`)
- `filter[query]` uses the same syntax as the Datadog UI

```bash
source ~/.claude/.env
# Use JOB_START - 1h and JOB_END + 1h as ISO8601 strings

curl -s -G "https://api.${DATADOG_SITE}/api/v2/events" \
  --data-urlencode "filter[query]=pod_name:<full-pod-name>" \
  --data-urlencode "filter[from]=<JOB_START_MINUS_1H>" \
  --data-urlencode "filter[to]=<JOB_END_PLUS_1H>" \
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

**What to look for:**
- `Killing` / `Unhealthy` events — read the message; it explains why Kubernetes acted
- `OOMKilled` → pod hit memory limit
- `Evicted` → node under resource pressure

**API 2 — Events v1 (Karpenter / scale-set-wide): use for node-level events.**

The v1 API uses **epoch seconds** (not ISO8601).

**CRITICAL — epoch must be UTC. Never use Python's naive `datetime.timestamp()`
— it returns local-time epoch. Always use the `date` command:**

```bash
source ~/.claude/.env
END_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<JOB_END>" "+%s" 2>/dev/null || date -u -d "<JOB_END>" "+%s")
START_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<JOB_START>" "+%s" 2>/dev/null || date -u -d "<JOB_START>" "+%s")

# Karpenter — spot interruption or node disruption
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

# Memory metrics — did the pod climb to its limit?
QUERY="max:kubernetes.memory.usage_pct{kube_cluster_name:infrastructure-prod,kube_namespace:arc-runners,pod_name:<pod>}"
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${QUERY}'))")
curl -s "https://api.${DATADOG_SITE}/api/v1/query?from=${START_EPOCH}&to=${END_EPOCH}&query=${ENCODED}" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" | \
  python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
series=d.get('series',[])
if not series: print('No memory metric data'); sys.exit()
for ts,val in series[0].get('pointlist',[]):
    t=datetime.datetime.utcfromtimestamp(ts/1000).strftime('%H:%M:%SZ')
    print(f'{t}  {val:.1f}%' if val else f'{t}  no data')
"
```

**Fallback — v1 Events when pod name unknown (high-noise, use only if v2 returns 0):**

`arc-runners` produces 1000+ events per hour. The v1 `tags=pod_name:X` filter
silently returns 0. Use a ±5 min window and filter in Python by scale-set prefix:

```bash
END_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "<JOB_END>" "+%s" 2>/dev/null || date -u -d "<JOB_END>" "+%s")
START_TIGHT=$((END_EPOCH - 300))
END_TIGHT=$((END_EPOCH + 300))

curl -s "https://api.${DATADOG_SITE}/api/v1/events?start=${START_TIGHT}&end=${END_TIGHT}&tags=kube_cluster_name:infrastructure-prod,kube_namespace:arc-runners" \
  -H "DD-API-KEY: ${DATADOG_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" | \
  python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
events=d.get('events',[])
print('Total events in window:', len(events))
SCALE_SET='<scale-set-prefix>'  # e.g. aily-runner-data-hqc78 (strip -runner-<hash> suffix)
signals=['oomkill','evict','liveness','unhealthy','timed out','kill','terminat','backoff']
for e in sorted(events, key=lambda x: x.get('date_happened',0)):
    title=e.get('title','')
    text=e.get('text','')
    combined=(title+text).lower()
    if SCALE_SET in title or SCALE_SET in text or any(s in combined for s in signals):
        ts=e.get('date_happened','')
        t=datetime.datetime.utcfromtimestamp(ts).strftime('%H:%M:%SZ') if ts else '?'
        print(f'{t} | {title} | {text[:300]}')
        print()
"
```

**3b. aily-logs (S3) — only if Datadog didn't surface the root cause.**

Use for actual container stdout/stderr (what the app printed before dying).
**Wide queries cause 32GB+ RAM usage — always specify `--app`.**

The S3 `app=` partition label may not match the pod name exactly. Always
discover it first:
```bash
aily-logs --tenant infrastructure-prod --namespace arc-runners --list-apps
```
For runner pods, strip the `-runner-<hash>` suffix to derive the app name:
`aily-runner-data-hqc78-runner-pgpf6` → `--app aily-runner-data-hqc78`

```bash
aily-logs --tenant infrastructure-prod \
  --namespace arc-runners \
  --app <app-from-list-apps> \
  --pod <pod-suffix> \
  --from <JOB_START> --to <JOB_END+30m> \
  --grep '(?i)error|kill|oom|memory|fatal|signal|terminat' \
  --limit 30
```

Kill immediately (`Ctrl-C`) if memory climbs. Retry with narrower window.

**3c. kubectl — only for live/recent state (events expire after ~1h).**
```bash
kubectl --context infrastructure-prod get pod <pod> -n arc-runners -o wide
kubectl --context infrastructure-prod describe pod <pod> -n arc-runners
kubectl --context infrastructure-prod get node <node>
kubectl --context infrastructure-prod describe node <node>
```

### Step 4 — General cluster investigation (non-GHA incidents)

```bash
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail -40
kubectl get pods -n <ns> -o wide
kubectl describe pod <pod>
flux get kustomizations -A | rg <service>
flux get helmreleases -A  | rg <service>
```

Scan `runbooks/` for files matching the failure signature (`oom.md`, `5xx.md`,
`crashloop.md`, `latency.md`). If no runbook matches, say so explicitly.

### Step 5 — Match to root cause

| Signal | Root cause |
|---|---|
| `Killing` / `Unhealthy` Datadog event | Read the event message — it states the reason (probe failure, OOM, eviction) |
| `OOMKilled` in Events or kubectl describe | Pod ran out of memory |
| `Evicted` in Events | Node under resource pressure |
| Karpenter `terminat`/`disrupt` near `JOB_END` | Spot interruption or scale-down |
| Nothing found anywhere | Node terminated before logs flushed; check CloudWatch `/aws/eks/infrastructure-prod/cluster` |

### Step 6 — Summary and output

Draft the summary:
```
TRIAGE <run-id or ticket> CONFIRMED/NOT CONFIRMED/NEED MORE INFO
<one-line failure signature>

<evidence — timestamps, pod, key log lines>
<root cause — one sentence>
<proposed fix — prose, no diffs>
```

If a Jira ticket was the input:
1. Run the draft through the `humanizer` skill — direct, specific, no AI filler.
2. Post the humanized comment via the `jira` skill (one comment per run).

If no Jira ticket (GHA URL or free-form): present findings directly, then ask
**"Do you want to investigate further?"** before doing anything else.

## Guardrails

Read-only only. No exceptions.

- **Cluster**: only `get`, `describe`, `logs`, `top`, `events` — no `apply`, `delete`, `edit`, `patch`, `exec`, `port-forward`
- **Flux/Helm**: no `reconcile`, `suspend`, `resume`, `install`, `upgrade`
- **AWS**: no write verbs, no `terragrunt`/`terraform apply`
- **Git/GitHub**: no `commit`, `push`, `pr create/merge`
- **Jira**: comments only, no transitions or field edits
- **Datadog**: GET/read only — no create, update, delete on any resource
- **Secret hygiene**: strip tokens and API keys from any output before quoting in Jira comments
