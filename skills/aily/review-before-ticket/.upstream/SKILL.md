---
name: review-before-ticket
description: |
  Verify infrastructure changes are deployed and healthy before transitioning
  a Jira ticket to Done or In Review. Runs kubectl and aws-cli checks against
  the relevant cluster(s) — deployment rollout, pod health, recent events,
  log errors, GitOps reconciliation, AWS resource status, and PR merge state.
  Trigger when about to close or review-transition a Jira ticket that involved
  infra/platform changes (APS-, TP- prefixes). Blocks transition on failures.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Review Before Ticket Transition

Verify that infrastructure changes are deployed and healthy before transitioning a Jira ticket to **Done** or **In Review**. Runs kubectl and aws-cli checks against the relevant cluster(s) to confirm the fix is live and working.

## Usage

```text
/review-before-ticket APS-10045
/review-before-ticket APS-10045 --cluster coreproduct-prod
/review-before-ticket APS-10045 --skip-aws
```

The argument `$ARGUMENTS` contains the ticket key and optional flags.

## Your Task

### Phase 1 — Gather context

1. **Read Jira credentials** from `~/.claude/.env` (`JIRA_USERNAME`, `JIRA_API_TOKEN`).

2. **Fetch the ticket** using the APS numeric-ID workaround (search by key, extract numeric `id`):
   ```bash
   curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/search/jql?jql=key=$TICKET_KEY&fields=key,summary,status,description,customfield_10002,components,labels,comment&expand=transitions&maxResults=1"
   ```

3. **Extract from the ticket:**
   - Current status and available transitions
   - Summary and description (what was the issue, what was the fix)
   - Components / labels (hint at which service, tenant, or cluster)
   - Recent comments (may contain PR links, deployment details, or cluster references)

4. **Determine target clusters and namespaces.** Use these heuristics (priority order):
   - If `--cluster <name>` was passed in `$ARGUMENTS`, use that.
   - If ticket components/labels mention a specific tenant or cluster, use those.
   - If ticket comments reference a gitops repo (`gitops-prod`, `gitops-dev`, `gitops-shared`, `gitops-controlplane`), infer the cluster from the aily-context mapping.
   - If the ticket references a PR, inspect the PR's target repo to infer the cluster.
   - If none of the above, **ask the user** which cluster(s) to verify against.

5. **Determine what to check.** Parse the ticket description and comments for:
   - Service/deployment names
   - Namespace
   - Terraform resources or AWS resource names
   - Helm releases or Kustomization names
   - ConfigMap/Secret changes

### Phase 2 — Kubernetes health checks

Run the following checks against each identified cluster. Summarize results per check.

**2a. Deployment / Pod status**
```bash
kubectl --context <cluster> -n <namespace> get deployment <name> -o wide
kubectl --context <cluster> -n <namespace> rollout status deployment/<name> --timeout=10s
kubectl --context <cluster> -n <namespace> get pods -l app=<name> -o wide
```
- Verify: all replicas ready, no CrashLoopBackOff, no pending pods, image tag matches expected version.

**2b. Recent events**
```bash
kubectl --context <cluster> -n <namespace> get events --sort-by='.lastTimestamp' --field-selector involvedObject.name=<name> | tail -20
```
- Verify: no Warning events in the last 30 minutes.

**2c. Recent logs (error scan)**
```bash
kubectl --context <cluster> -n <namespace> logs deployment/<name> --since=15m --tail=100 | grep -iE 'error|exception|fatal|panic|critical' | head -20
```
- Verify: no critical errors in recent logs.

**2d. GitOps reconciliation (Flux / ArgoCD)**
```bash
# Flux
kubectl --context <cluster> get kustomization -A | grep -i <name-or-namespace>
flux get kustomization <name> --context <cluster>

# ArgoCD (if applicable)
kubectl --context <cluster> -n argocd get application -l app.kubernetes.io/name=<name> -o wide
```
- Verify: kustomization/application is `Ready=True`, last applied revision matches expected commit.

**2e. Service / Ingress reachability**
```bash
kubectl --context <cluster> -n <namespace> get svc <name>
kubectl --context <cluster> -n <namespace> get ingress -l app=<name>
```
- Verify: endpoints populated, no missing backends.

### Phase 3 — AWS health checks (skip if `--skip-aws`)

Only run these if the ticket involves AWS/Terraform resources.

**3a. Resource existence**
```bash
# Adapt to actual resource type
aws s3api head-bucket --bucket <bucket-name> 2>&1
aws rds describe-db-instances --db-instance-identifier <name> --query 'DBInstances[0].DBInstanceStatus'
aws ecs describe-services --cluster <cluster> --services <name> --query 'services[0].status'
aws lambda get-function --function-name <name> --query 'Configuration.State'
```

**3b. CloudWatch alarms**
```bash
aws cloudwatch describe-alarms --alarm-name-prefix <service-prefix> --state-value ALARM --query 'MetricAlarms[].AlarmName'
```
- Verify: no active alarms related to the service.

**3c. Recent CloudWatch errors (if log group known)**
```bash
aws logs filter-log-events --log-group-name <group> --start-time $(date -d '15 minutes ago' +%s000) --filter-pattern "ERROR" --limit 10
```

### Phase 4 — PR / merge verification

If ticket comments contain a PR link:
```bash
gh pr view <pr-number> -R <owner/repo> --json state,mergedAt,mergeCommit,headRefName
```
- Verify: PR is merged, not just approved.

### Phase 5 — Verdict

Present a summary table:

```text
+-----------------------------------+--------+
| Check                             | Result |
+-----------------------------------+--------+
| Deployment rollout complete       |   /    |
| All pods healthy                  |   /    |
| No warning events                 |   /    |
| No critical log errors            |   /    |
| GitOps reconciliation Ready       |   /    |
| Service endpoints populated       |   /    |
| AWS resources healthy             |   /    |
| No CloudWatch alarms              |   /    |
| PR merged                         |   /    |
+-----------------------------------+--------+
```

Only include rows for checks that were actually executed (skip irrelevant ones).

**Decision logic:**
- **All green** -> Recommend transition. Ask user: "All checks passed. Proceed to transition $TICKET to [Done/In Review]?"
- **Warnings only** (minor log errors, non-critical events) -> Show warnings, recommend transition with caveats. Ask user to confirm.
- **Any red** -> **Do NOT transition.** Explain which checks failed and suggest next steps.

### Phase 6 — Transition (only if user confirms)

If the user confirms, transition the ticket using the Jira REST API:
- Use the numeric ID obtained in Phase 1.
- Use the appropriate transition ID (get from the `transitions` expand in the search).
- If transitioning to Done, add a "Reply to Customer" comment summarizing the fix and verification results.

```bash
# Transition
curl -s -X POST -u "$AUTH" -H "Content-Type: application/json" \
  -d '{"transition":{"id":"<TRANSITION_ID>"}}' \
  "https://ailylabs.atlassian.net/rest/api/3/issue/<NUMERIC_ID>/transitions"

# Reply to Customer comment (for Done transitions)
curl -s -X POST -u "$AUTH" -H "Content-Type: application/json" \
  -d '{"body":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"<summary>"}]}]}}' \
  "https://ailylabs.atlassian.net/rest/api/3/issue/<NUMERIC_ID>/comment"
```

## Important Rules

- **Never transition on red checks.** If any critical check fails, block the transition and explain why.
- **Always confirm with the user** before executing the Jira transition.
- **Use read-only kubectl** (get, describe, logs, rollout status). Never modify cluster state.
- **Adapt checks to context.** Not every check applies to every ticket. Skip irrelevant checks rather than running them and reporting false failures.
- **If cluster context is ambiguous**, ask the user. Don't guess.
- **APS tickets require the numeric ID workaround** — never use the issue key directly for API mutations.
- **Reply to Customer** is mandatory when transitioning to Done (client-visible tickets need closure communication).

## Error Handling

- **kubectl context not found**: "Cluster context `<name>` not found in kubeconfig. Available contexts: ..." (list them with `kubectl config get-contexts -o name`)
- **AWS credentials expired**: "AWS session expired. Run `aws sso login --profile <profile>` to refresh."
- **Jira auth failure**: "Jira authentication failed. Check credentials in `~/.claude/.env`."
- **Ticket not found**: "Could not find ticket `$ARGUMENTS` in Jira. Verify the key is correct."
- **No deployment info**: "Could not determine which deployment to check from the ticket. Please specify: `/review-before-ticket APS-XXXXX --cluster <cluster> --namespace <ns> --deployment <name>`"
