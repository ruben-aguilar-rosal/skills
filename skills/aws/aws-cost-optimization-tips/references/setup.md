# Setup & IAM

This skill drives the upstream repo's code without running its MCP server. The runner is
**self-contained** — it bootstraps everything on first use.

## Zero-setup bootstrap

On the first invocation `run_cfm.py`:

1. Clones `aws-samples/sample-cfm-tips-mcp` (shallow) into a managed, git-ignored dir:
   `skills/aws/aws-cost-optimization-tips/vendor/sample-cfm-tips-mcp/`.
2. Creates a dedicated virtualenv there (`vendor/.../.venv`) from whatever Python 3.11+
   you launched it with.
3. Installs `requirements.txt` **plus `mcp`** (the repo imports `mcp` everywhere but omits
   it from `requirements.txt`; its `setup.py` declares `required_packages = ['boto3', 'mcp']`).
4. Re-execs itself with the venv interpreter and runs the requested tool.

Progress streams to stderr. Subsequent runs detect the venv and skip straight to
execution. Prerequisites for that first run: Python 3.11+, `git`, and network access.

```bash
# Just run it — no prior setup:
python3 skills/aws/aws-cost-optimization-tips/scripts/run_cfm.py --list
```

## Knobs

| Env / flag | Effect |
|---|---|
| `CFM_TIPS_HOME=<path>` | Use an existing clone at `<path>` (skips cloning). Takes precedence. |
| `--home <path>` | Same as `CFM_TIPS_HOME`, per-invocation. |
| `CFM_TIPS_REPO=<url>` | Clone from a fork/mirror instead of aws-samples. |
| `CFM_TIPS_REF=<ref>` | Check out a tag/branch/commit after cloning (default: `main`). |
| `--no-bootstrap` | Never clone/install; fail with manual instructions if anything is missing. |

To point at an existing clone instead of the managed one, set `CFM_TIPS_HOME=<path>`.

**Updating:** `git -C skills/aws/aws-cost-optimization-tips/vendor/sample-cfm-tips-mcp pull`.
The runner reuses the repo's own `call_tool` dispatch and `list_tools`, so new/renamed
tools appear automatically after a pull — no change to this skill. To rebuild from
scratch, delete the `vendor/` dir and run again.

## AWS credentials

Credentials resolve from the ambient environment, identical to the AWS CLI:
`AWS_PROFILE`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, or an instance/SSO role.

Always confirm the target account before analyzing:

```bash
AWS_PROFILE=<profile> aws sts get-caller-identity
```

For multi-account analysis, run the tools once per profile. Cost Explorer / Cost
Optimization Hub data is account-scoped (or org-scoped from the management/payer account).

## 4. IAM permissions (read-only)

All tools call only `Describe`/`List`/`Get` APIs. The principal needs read access across
the analyzed services. Actions used (from the upstream `cross-account-role.yaml`):

```
ce:GetCostAndUsage, ce:GetCostForecast, ce:GetSavingsPlansUtilization,
ce:GetSavingsPlansCoverage, ce:GetReservationUtilization, ce:GetReservationCoverage,
ce:GetUsageReport, ce:GetCostCategories, ce:ListCostAllocationTags,
ce:ListCostCategoryDefinitions,
cost-optimization-hub:ListEnrollmentStatuses, cost-optimization-hub:ListRecommendations,
cost-optimization-hub:GetRecommendation, cost-optimization-hub:ListRecommendationSummaries,
cost-optimization-hub:GetRecommendationSummary,
cost-optimization-hub:GetSavingsPlansRecommendations,
compute-optimizer:GetEnrollmentStatus, compute-optimizer:GetEC2InstanceRecommendations,
compute-optimizer:GetEBSVolumeRecommendations,
compute-optimizer:GetLambdaFunctionRecommendations,
compute-optimizer:GetAutoScalingGroupRecommendations,
compute-optimizer:GetECSServiceRecommendations,
compute-optimizer:GetRecommendationSummaries,
trustedadvisor:DescribeCheckItems, trustedadvisor:DescribeCheckResult,
trustedadvisor:ListChecks, trustedadvisor:ListRecommendations,
trustedadvisor:GetRecommendation,
support:DescribeTrustedAdvisorChecks, support:DescribeTrustedAdvisorCheckResult,
support:RefreshTrustedAdvisorCheck, support:DescribeSeverityLevels,
ec2:Describe* (Instances, Volumes, Addresses, NatGateways, ReservedInstances,
  SpotInstanceRequests, CapacityReservations, RouteTables, ...),
ebs (covered by ec2:Describe*),
rds:DescribeDBInstances, rds:DescribeDBClusters, rds:DescribeDBSnapshots,
rds:DescribeDBClusterSnapshots, rds:DescribeReservedDBInstances,
rds:DescribeReservedDBInstancesOfferings,
lambda:ListFunctions, lambda:GetFunction, lambda:GetFunctionConfiguration,
lambda:ListTags, lambda:ListProvisionedConcurrencyConfigs,
cloudwatch:GetMetricStatistics, cloudwatch:GetMetricData, cloudwatch:ListMetrics,
cloudwatch:DescribeAlarms, cloudwatch:DescribeAlarmsForMetric, cloudwatch:ListDashboards,
cloudwatch:GetDashboard,
logs:DescribeLogGroups, logs:DescribeLogStreams, logs:DescribeMetricFilters,
logs:GetLogGroupFields, logs:ListLogAnomalyDetectors, logs:ListAnomalies,
pi:GetResourceMetrics, pi:DescribeDimensionKeys, pi:GetDimensionKeyDetails,
pi:ListAvailableResourceMetrics,
pricing:GetProducts, pricing:DescribeServices, pricing:GetAttributeValues,
cloudtrail:DescribeTrails, cloudtrail:ListTrails, cloudtrail:GetTrail,
cloudtrail:GetTrailStatus, cloudtrail:GetEventSelectors, cloudtrail:GetInsightSelectors,
cloudtrail:LookupEvents,
savingsplans:DescribeSavingsPlans, savingsplans:DescribeSavingsPlansOfferingRates,
savingsplans:DescribeSavingsPlansOfferings,
s3:ListAllMyBuckets, s3:GetBucketLocation, s3:GetBucketLifecycleConfiguration,
s3:ListBucket, s3:GetBucketTagging, s3:GetBucketVersioning (and related read APIs),
sts:GetCallerIdentity, iam:ListRoleTags
```

A wildcard read-only policy (`ce:Get*`, `ec2:Describe*`, `s3:List*`, `s3:Get*`, etc. on
`Resource: "*"`) is the simplest grant; the upstream README calls this
`CFMTipsComprehensiveReadOnly`. Cost Explorer, Cost Optimization Hub, and Compute
Optimizer must be **enabled** in the account for those tools to return data.

## Notes

- The repo writes a `logs/` directory and reads relative paths; `run_cfm.py` `chdir`s into
  `CFM_TIPS_HOME` so this is contained to the clone.
- Some tools store intermediate results (e.g. CloudWatch analysis) under the clone for
  `query_cloudwatch_analysis_results` to query later.
