# AWS skills

AWS service skills vendored verbatim from
[`aws/agent-toolkit-for-aws`](https://github.com/aws/agent-toolkit-for-aws) (synced at
`f2feb06`), AWS's official Agent Toolkit — the tools, knowledge, and guardrails AI
coding agents need to work with AWS.

This is a **curated subset** (33 of ~86 upstream skills), trimmed to the services this
infra/platform repo actually runs: IAM, networking, observability, EC2, RDS/Aurora
Postgres, ElastiCache, S3, CloudFormation, serverless. Off-stack skills were deliberately
skipped (see *Not vendored* below).

## Skills in this folder

### Core (11)
| Skill | Use it for |
|---|---|
| `aws-iam` | Verified corrections for IAM behaviors agents get wrong. |
| `aws-cloudformation` | Author, validate, troubleshoot CloudFormation templates with secure defaults. |
| `aws-observability` | CloudWatch Log Insights, metrics, alarms, Application Signals. |
| `aws-containers` | Deploy/operate containers on ECS, Fargate, ECR. |
| `aws-serverless` | Lambda, API Gateway, Step Functions — build/deploy/debug/optimize. |
| `aws-billing-and-cost-management` | Analyze costs, find savings, manage budgets, evaluate Savings Plans. |
| `aws-messaging-and-streaming` | SQS, SNS, EventBridge, Kinesis messaging/streaming. |
| `aws-sdk-python-usage` | AWS SDK for Python (boto3/botocore) patterns. |
| `amazon-bedrock` | Generative AI on Bedrock — Converse/InvokeModel, RAG with Knowledge Bases, agents. |
| `signing-in-to-aws` | Get AWS credentials for CLI/SDK access (`aws login`, SSO). |

### Networking & content delivery (5)
| Skill | Use it for |
|---|---|
| `creating-production-vpc-multi-az` | Production VPC with public/private subnets across AZs. |
| `configuring-vpc-endpoints-for-private-aws-service-access` | Interface/gateway VPC endpoints via PrivateLink. |
| `connecting-vpcs-with-peering` | VPC peering for direct private connectivity. |
| `enabling-lambda-vpc-internet-access` | NAT Gateway so VPC Lambdas reach the internet. |
| `routing-traffic-with-route53-and-cloudfront` | Route 53 → CloudFront with a custom domain. |

### Operations (3)
| Skill | Use it for |
|---|---|
| `troubleshooting-application-failures` | Diagnose failing apps via CloudWatch log analysis. |
| `setting-up-cloudwatch-alarm-notifications` | CloudWatch alarm → SNS notification channels. |
| `setting-up-cloudtrail-multi-region` | Multi-region CloudTrail with S3 + CloudWatch Logs. |

### EC2 (3)
| Skill | Use it for |
|---|---|
| `setting-up-ec2-instance-profiles` | Attach IAM roles to EC2 via instance profiles. |
| `launching-ec2-instance-with-best-practices` | Launch EC2 with secure, cost-efficient defaults. |
| `creating-ec2-image-builder-pipeline` | Build/distribute custom AMIs with Image Builder. |

### Database (3)
| Skill | Use it for |
|---|---|
| `amazon-aurora-postgresql` | Create/modify/advise on Aurora PostgreSQL clusters (pgvector, ACU sizing, upgrades). |
| `amazon-elasticache` | Caching with ElastiCache (Valkey/Redis) — latency, read bottlenecks, throttling. |
| `exporting-rds-to-s3` | Export RDS/Aurora snapshots to S3 as Parquet. |

### Storage (5)
| Skill | Use it for |
|---|---|
| `securing-s3-buckets` | Secure S3 buckets — access control, encryption, best practices. |
| `troubleshooting-s3-files` | Diagnose S3 mount/access issues. |
| `troubleshooting-efs` | Diagnose EFS mount failures / NFS timeouts. |
| `creating-data-lake-table` | Managed Iceberg tables via Amazon S3 Tables. |
| `storing-and-querying-vectors` | Vector embeddings with Amazon S3 Vectors. |

### Analytics & data lake (2)
| Skill | Use it for |
|---|---|
| `exploring-data-catalog` | Inventory/audit the Glue Data Catalog. |
| `querying-data-lake` | Athena SQL across Glue/federated catalogs. |

### System tables — querying (2)
| Skill | Use it for |
|---|---|
| `querying-aws-cloudwatch` | SQL over CloudWatch Logs exported as Iceberg in S3 Tables. |
| `querying-aws-s3` | Query S3 object metadata, track bucket activity, audit changes. |

## How to use them

- **Automatic:** the agent picks a skill up from its `description` — mention the AWS
  service or task (e.g. "secure this S3 bucket", "debug the Lambda timeout", "set up a
  multi-AZ VPC") and the matching skill activates.
- **Explicit:** ask for one by name, e.g. *"use the `aws-iam` skill"*.

## Not vendored

Skipped as off-stack or niche for this repo:

- **Security-flagged:** `rds-db2` — ships `curl … | bash` from a URL shortener (the only
  genuine security smell in the toolkit; SC2/TM1/TM2).
- **Wrong engine/runtime:** `amazon-keyspaces` (Cassandra), `amazon-documentdb` (MongoDB),
  `amazon-aurora-mysql`, `creating-amazon-aurora-db-cluster-with-instances` (we run Aurora
  Postgres), `aws-sdk-swift-usage`, `aws-sdk-js-v3-usage` (we write Python).
- **Not our IaC / app model:** `aws-cdk` (we use terragrunt), `aws-blocks`
  (Infrastructure-from-Code framework).
- **Data-engineering / streaming (no current use):** `amazon-opensearch-service`,
  `developing-applications-on-managed-service-for-apache-flink`, `managing-amazon-msk`,
  `migrate-to-msk`, `aws-cleanrooms`, `connecting-to-data-source`,
  `finding-data-lake-assets`, `ingesting-into-data-lake`, `querying-aws-sagemaker-catalog`.

The `plugins/` tree (AI-agent-building and DevSecOps-agent sets) was also left out of this pass.
