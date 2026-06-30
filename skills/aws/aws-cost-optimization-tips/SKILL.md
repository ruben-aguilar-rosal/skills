---
name: aws-cost-optimization-tips
description: >
  Run AWS Cloud Financial Management (CFM) cost-optimization analyses directly as
  scripts — no MCP server. Wraps the 59 read-only "TIPs" runbooks from
  aws-samples/sample-cfm-tips-mcp (EC2/EBS/RDS/Lambda/S3/CloudWatch/CloudTrail/NAT
  rightsizing, unused-resource detection, Savings Plans/RI analysis, Cost Explorer,
  Cost Optimization Hub, Compute Optimizer, Trusted Advisor) behind one CLI. Use when
  the user wants to find AWS savings, right-size resources, hunt unused/idle resources,
  evaluate commitment plans, or produce a cost-optimization report for an account or
  region. Do NOT use to MODIFY resources — every tool is read-only and emits
  recommendations only.
version: 1
---

# AWS Cost Optimization (CFM TIPs)

## Overview

[`aws-samples/sample-cfm-tips-mcp`](https://github.com/aws-samples/sample-cfm-tips-mcp)
packages AWS's Cloud Financial Management Technical Implementation Playbooks (TIPs) as
59 read-only analysis tools. Upstream ships them behind an MCP server, but the server is
only a transport: every tool is dispatched by a single coroutine,
`mcp_server_with_runbooks.call_tool(name, arguments)`, that returns plain JSON.

This skill calls that coroutine **directly** via `scripts/run_cfm.py`, so analyses run as
ordinary scripts — no MCP server, no MCP client. The agent picks a tool, runs it, reads
the JSON, and turns the findings into Well-Architected cost recommendations.

The runner is **self-contained**: on first run it clones the upstream repo into a managed,
git-ignored `vendor/` dir, builds its own virtualenv, installs the dependencies, and
re-execs itself with that interpreter. No manual setup — just run it with any Python 3.11+.

**Read-only guarantee:** all 59 tools only call `Describe`/`List`/`Get` AWS APIs and
return recommendations. None create, modify, or delete resources. Acting on a
recommendation (releasing an EIP, deleting a volume, buying a Savings Plan) is a
separate, manual step the user performs.

## Setup

None required. The first invocation bootstraps everything (git clone + venv + deps) and
may take a minute; later runs are instant. Needs Python 3.11+, `git`, and network access
on first run. Knobs and the IAM permissions are in [references/setup.md](references/setup.md).

Quick check before any analysis:

```bash
RUN="python3 skills/aws/aws-cost-optimization-tips/scripts/run_cfm.py"

# 1. List tools (first run bootstraps; prints progress to stderr)
$RUN --list | head -3

# 2. Credentials resolve to the account you intend to analyze
AWS_PROFILE=<profile> aws sts get-caller-identity
```

You MUST confirm `aws sts get-caller-identity` shows the intended account before running
analyses; cost tools span many services and the wrong profile gives misleading results.

## Running a tool

```bash
RUN="python3 skills/aws/aws-cost-optimization-tips/scripts/run_cfm.py"

# List every tool with its argument schema
$RUN --list

# Scalar args (auto-typed: bool/int/float/str)
AWS_PROFILE=<profile> $RUN s3_quick_analysis --arg region=eu-west-1

# Arrays / objects / nested args via --json
AWS_PROFILE=<profile> $RUN get_cost_explorer_data \
  --json '{"start_date":"2026-06-01","end_date":"2026-06-30","granularity":"MONTHLY","group_by":[{"Type":"DIMENSION","Key":"SERVICE"}]}'
```

- Credentials come from the ambient environment (`AWS_PROFILE`, env vars, or role) —
  exactly like the AWS CLI. Always set/confirm the profile for the target account.
- Most tools default to the credential's default region; pass `--arg region=<region>` to
  be explicit, or run per-region for region-scoped tools (EC2/EBS/RDS/Lambda/NAT).
- Output is the raw JSON payload. Read `data`, `count`, `total_monthly_cost`, and
  `recommendations`; summarize for the user rather than dumping the whole blob.

The full tool catalog (names, args, what each returns, which need a `region`) is in
[references/tools.md](references/tools.md).

## Recommended workflow

Match depth to the request. For "find savings in this account":

1. **Snapshot the spend.** `comprehensive_analysis` for a multi-service sweep, or
   `get_cost_explorer_data` grouped by `SERVICE` to see where money goes. For S3 alone,
   `s3_quick_analysis` is a ~30s starting point.
2. **Pull existing recommendations.** `get_coh_recommendations` (Cost Optimization Hub),
   `get_compute_optimizer_recommendations`, `get_trusted_advisor_checks` — AWS has often
   already computed savings; surface those first.
3. **Quick wins / waste.** `ec2_stopped_instances`, `ec2_unattached_eips`, `ebs_unused`,
   `lambda_unused`, `rds_idle`, `nat_gateway_unused`, `s3_multipart_cleanup`. These are
   the lowest-risk, highest-clarity deletions.
4. **Right-sizing.** `ec2_rightsizing`, `ebs_optimization`, `rds_optimization`,
   `lambda_optimization`, `ec2_graviton_compatible`, `ec2_burstable_analysis`.
5. **Commitment planning.** `ec2_commitment_plans`, `database_savings_plans_analysis`,
   `ec2_spot_opportunities` — only after rightsizing, since commitments lock in size.
6. **Observability/network spend.** `cloudwatch_general_spend_analysis` (then
   logs/metrics/alarms variants), `nat_gateway_optimization`,
   `run_cloudtrail_trails_analysis`.
7. **Report & prioritize.** Use the `*_report` / `*_comprehensive_report` tools or
   synthesize the JSON into a ranked list: estimated monthly savings × effort × risk.
   Tie each recommendation back to the Well-Architected Cost Optimization pillar.

Always present **estimated savings, the resources involved, and the manual action
required**, and flag anything stateful or production-facing as needing change control
before the user acts on it.
