# CFM TIPs tool catalog

59 read-only tools, dispatched by `run_cfm.py <tool> [--arg k=v] [--json '{...}']`.
`*` marks a **required** argument. Run `run_cfm.py --list` for the live schema (the
authoritative source if upstream changes).

Common optional args across tools: `region` (defaults to the credential's default
region), `lookback_period_days` / `lookback_days`, `output_format`. Region-scoped tools
(EC2, EBS, RDS, Lambda, NAT, most CloudWatch) analyze **one region per call** — loop over
regions if the account spans several.

## Cost analysis & existing recommendations

Start here — AWS often already computed the savings.

| Tool | Key args | Returns |
|---|---|---|
| `get_cost_explorer_data` | `start_date*`, `end_date*`, `granularity`, `metrics`, `group_by` | Cost Explorer cost/usage; group_by SERVICE to find cost drivers |
| `list_coh_enrollment` | `include_organization_info` | Cost Optimization Hub enrollment status |
| `get_coh_recommendations` | `group_by`, `include_all_recommendations`, `max_results`, `order_by` | Cost Optimization Hub recommendations + savings |
| `get_compute_optimizer_recommendations` | `resource_type` | Compute Optimizer rightsizing findings |
| `get_trusted_advisor_checks` | `check_categories` | Trusted Advisor checks across pillars |
| `get_performance_insights_metrics` | `db_instance_identifier*`, `start_time`, `end_time` | RDS Performance Insights metrics |
| `comprehensive_analysis` | `region`, `services`, `lookback_period_days`, `output_format` | Multi-service sweep (EC2/EBS/RDS/Lambda/CloudTrail/S3/CloudWatch) |

## EC2 (18 tools, region-scoped)

| Tool | Key args | Returns |
|---|---|---|
| `ec2_rightsizing` | `region`, `lookback_period_days`, `cpu_threshold` | Underutilized instances + rightsizing |
| `ec2_report` | `region`, `include_cost_analysis`, `output_format` | Detailed rightsizing report |
| `ec2_comprehensive_report` | `region` | All EC2 playbooks combined |
| `ec2_stopped_instances` | `region`, `min_stopped_days` | Long-stopped instances to terminate |
| `ec2_unattached_eips` | `region` | Unattached Elastic IPs (billed) |
| `ec2_old_generation` | `region` | Old-generation families to upgrade |
| `ec2_detailed_monitoring` | `region` | Instances missing detailed monitoring |
| `ec2_graviton_compatible` | `region` | Graviton-migration candidates |
| `ec2_burstable_analysis` | `region`, `lookback_period_days` | T-family credit usage analysis |
| `ec2_spot_opportunities` | `region` | Spot-suitable instances |
| `ec2_unused_reservations` | `region` | Unused On-Demand Capacity Reservations |
| `ec2_scheduling_opportunities` | `region` | Start/stop scheduling candidates |
| `ec2_commitment_plans` | `region` | RI / Savings Plans opportunities |
| `ec2_governance_violations` | `region` | Tagging/policy non-compliance |

## EBS (region-scoped)

| Tool | Key args | Returns |
|---|---|---|
| `ebs_optimization` | `region`, `lookback_period_days` | Unused + underutilized volumes |
| `ebs_unused` | `region`, `min_age_days` | Unattached volumes to delete |
| `ebs_report` | `region`, `output_format` | EBS report with savings |

## RDS (region-scoped)

| Tool | Key args | Returns |
|---|---|---|
| `rds_optimization` | `region`, `lookback_period_days` | Underutilized DBs |
| `rds_idle` | `region`, `lookback_period_days`, `connection_threshold` | Idle instances (low connections) |
| `rds_report` | `region`, `output_format` | RDS report with recommendations |

## Lambda (region-scoped)

| Tool | Key args | Returns |
|---|---|---|
| `lambda_optimization` | `region`, `lookback_period_days` | Overprovisioned functions |
| `lambda_unused` | `region`, `lookback_period_days`, `max_invocations` | Rarely-invoked functions |
| `lambda_report` | `region`, `output_format` | Lambda report with savings |

## S3 (11 tools)

| Tool | Key args | Returns |
|---|---|---|
| `s3_quick_analysis` | `region` | ~30s: top spenders, multipart, governance |
| `s3_general_spend_analysis` | `region`, `lookback_months`, `include_trends`, `detailed_breakdown` | Spend patterns + trends |
| `s3_comprehensive_analysis` | `region`, `bucket_names`, `output_format` | Full cost analysis |
| `s3_comprehensive_optimization_tool` | many (see `--list`) | All 8 S3 analyses in parallel, orchestrated |
| `s3_bucket_analysis` | `bucket_names*`, `region` | Per-bucket optimization |
| `s3_storage_class_selection` | `access_frequency`, `retrieval_time_tolerance`, `durability_requirement`, `data_size_gb`, `retention_period_days` | Best storage class for NEW data |
| `s3_storage_class_validation` | `region`, `bucket_names`, `lookback_days`, `min_object_size_mb` | Existing data in the right class? |
| `s3_archive_optimization` | `region`, `bucket_names`, `min_age_days`, `archive_tier_preference` | Glacier/archive opportunities |
| `s3_api_cost_minimization` | `region`, `bucket_names`, `lookback_days`, `request_threshold` | Reduce request charges |
| `s3_multipart_cleanup` | `region`, `bucket_names`, `min_age_days` | Incomplete multipart uploads (waste) |
| `s3_governance_check` | `region`, `bucket_names`, `check_tagging`, `check_lifecycle_policies`, `check_versioning` | Cost-control / governance gaps |

## CloudWatch (8 tools)

| Tool | Key args | Returns |
|---|---|---|
| `cloudwatch_general_spend_analysis` | `region`, `lookback_days`, `page`, `page_size` | Spend across logs/metrics/alarms/dashboards |
| `cloudwatch_logs_optimization` | `region`, `lookback_days`, ... | Log retention/ingestion savings |
| `cloudwatch_metrics_optimization` | `region`, `lookback_days`, ... | Custom-metric cost savings |
| `cloudwatch_alarms_and_dashboards_optimization` | `region`, `lookback_days`, ... | Alarm/dashboard efficiency |
| `cloudwatch_comprehensive_optimization_tool` | `region`, `lookback_days`, `detail_level`, ... | Unified, orchestrated CW analysis |
| `get_cloudwatch_cost_estimate` | `region`, `analysis_type`, `lookback_days` | Cost of running the analysis itself |
| `validate_cloudwatch_cost_preferences` | `region`, `cost_preferences` | Validate cost-preference config |
| `query_cloudwatch_analysis_results` | `region`, `query`, `limit` | SQL over stored CW analysis results |

## CloudTrail

| Tool | Key args | Returns |
|---|---|---|
| `get_management_trails` | `region` | Management trails inventory |
| `run_cloudtrail_trails_analysis` | `region` | Trail optimization analysis |
| `generate_cloudtrail_report` | `region`, `output_format` | CloudTrail optimization report |

## NAT Gateway (region-scoped)

| Tool | Key args | Returns |
|---|---|---|
| `nat_gateway_optimization` | `region`, `data_transfer_threshold_gb`, `lookback_days` | Underutilized + redundant + unused |
| `nat_gateway_underutilized` | `region`, `data_transfer_threshold_gb`, `lookback_days`, `zero_cost_mode` | Low-traffic NAT GWs |
| `nat_gateway_redundant` | `region` | Multiple NAT GWs in same AZ |
| `nat_gateway_unused` | `region` | NAT GWs not referenced by any route table |

## Database Savings Plans

| Tool | Key args | Returns |
|---|---|---|
| `database_savings_plans_analysis` | `region`, `lookback_period_days`, `services`, `include_ri_comparison` | DB Savings Plans recommendations |
| `database_savings_plans_existing_analysis` | `region`, `lookback_period_days` | Utilization/coverage of existing plans |
| `database_savings_plans_purchase_analyzer` | `hourly_commitment*`, `commitment_term`, `payment_option`, `region`, `adjusted_usage_projection` | Model a custom commitment scenario |
