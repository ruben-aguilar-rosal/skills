# AWS skills

AWS service skills vendored verbatim from
[`aws/agent-toolkit-for-aws`](https://github.com/aws/agent-toolkit-for-aws) (synced at
`f2feb06`), AWS's official Agent Toolkit — the tools, knowledge, and guardrails AI
coding agents need to work with AWS.

This is a **curated subset** (44 of ~86 upstream skills): the core services, networking,
operations, EC2, the databases/storage we actually run, and the data-lake/analytics set.
Niche skills were deliberately skipped (see *Not vendored* below).

## Skills in this folder

### Core (13)
| Skill | Use it for |
|---|---|
| `amazon-bedrock` | Generative AI on Bedrock — Converse/InvokeModel, RAG with Knowledge Bases, agents. |
| `aws-billing-and-cost-management` | Analyze costs, find savings, manage budgets, evaluate Savings Plans. |
| `aws-blocks` | Build full-stack apps with AWS Blocks (Infrastructure-from-Code). |
| `aws-cdk` | Author, deploy, troubleshoot infra with CDK (TypeScript/Python). |
| `aws-cloudformation` | Author, validate, troubleshoot CloudFormation templates with secure defaults. |
| `aws-containers` | Deploy/operate containers on ECS, Fargate, ECR. |
| `aws-iam` | Verified corrections for IAM behaviors agents get wrong. |
| `aws-messaging-and-streaming` | SQS, SNS, EventBridge, Kinesis messaging/streaming. |
| `aws-observability` | CloudWatch Log Insights, metrics, alarms, Application Signals. |
| `aws-sdk-js-v3-usage` | AWS SDK for JavaScript v3 patterns. |
| `aws-sdk-python-usage` | AWS SDK for Python (boto3/botocore) patterns. |
| `aws-serverless` | Lambda, API Gateway, Step Functions — build/deploy/debug/optimize. |
| `signing-in-to-aws` | Get AWS credentials for CLI/SDK access (`aws login`, SSO). |

### Networking & content delivery (5)
| Skill | Use it for |
|---|---|
| `configuring-vpc-endpoints-for-private-aws-service-access` | Interface/gateway VPC endpoints via PrivateLink. |
| `connecting-vpcs-with-peering` | VPC peering for direct private connectivity. |
| `creating-production-vpc-multi-az` | Production VPC with public/private subnets across AZs. |
| `enabling-lambda-vpc-internet-access` | NAT Gateway so VPC Lambdas reach the internet. |
| `routing-traffic-with-route53-and-cloudfront` | Route 53 → CloudFront with a custom domain. |

### Operations (3)
| Skill | Use it for |
|---|---|
| `setting-up-cloudtrail-multi-region` | Multi-region CloudTrail with S3 + CloudWatch Logs. |
| `setting-up-cloudwatch-alarm-notifications` | CloudWatch alarm → SNS notification channels. |
| `troubleshooting-application-failures` | Diagnose failing apps via CloudWatch log analysis. |

### EC2 (3)
| Skill | Use it for |
|---|---|
| `creating-ec2-image-builder-pipeline` | Build/distribute custom AMIs with Image Builder. |
| `launching-ec2-instance-with-best-practices` | Launch EC2 with secure, cost-efficient defaults. |
| `setting-up-ec2-instance-profiles` | Attach IAM roles to EC2 via instance profiles. |

### Database (5)
| Skill | Use it for |
|---|---|
| `amazon-aurora-mysql` | Create/modify/advise on Aurora MySQL clusters. |
| `amazon-aurora-postgresql` | Create/modify/advise on Aurora PostgreSQL clusters. |
| `amazon-elasticache` | Caching with ElastiCache (Valkey/Redis) — latency, read bottlenecks, throttling. |
| `creating-amazon-aurora-db-cluster-with-instances` | Full Aurora cluster + instance provisioning. |
| `exporting-rds-to-s3` | Export RDS/Aurora snapshots to S3 as Parquet. |

### Storage (5)
| Skill | Use it for |
|---|---|
| `creating-data-lake-table` | Managed Iceberg tables via Amazon S3 Tables. |
| `securing-s3-buckets` | Secure S3 buckets — access control, encryption, best practices. |
| `storing-and-querying-vectors` | Vector embeddings with Amazon S3 Vectors. |
| `troubleshooting-efs` | Diagnose EFS mount failures / NFS timeouts. |
| `troubleshooting-s3-files` | Diagnose S3 mount/access issues. |

### Analytics & data lake (8)
| Skill | Use it for |
|---|---|
| `amazon-opensearch-service` | OpenSearch Service/Serverless — migration, ops, search. |
| `connecting-to-data-source` | AWS Glue connections to JDBC databases. |
| `exploring-data-catalog` | Inventory/audit the Glue Data Catalog. |
| `finding-data-lake-assets` | Resolve data-lake asset references across Glue/S3. |
| `ingesting-into-data-lake` | Import data into the data lake (S3, JDBC, uploads). |
| `managing-amazon-msk` | Operate Amazon MSK provisioned clusters. |
| `migrate-to-msk` | Migrate self-managed Kafka to MSK Express. |
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

Skipped as out of scope / niche: `rds-db2` (ships `curl … | bash` from a URL shortener),
`amazon-keyspaces`, `amazon-documentdb`, `aws-sdk-swift-usage`,
`developing-applications-on-managed-service-for-apache-flink`, `aws-cleanrooms`,
`querying-aws-sagemaker-catalog`. The `plugins/` tree (AI-agent-building and
DevSecOps-agent sets) was also left out of this pass.
