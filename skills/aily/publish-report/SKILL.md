---
name: publish-report
description: Publish or share a Claude Code artifact (an HTML dashboard/report) on the private Aily reports portal by uploading it to S3. Use when asked to publish, share, deploy, or upload an artifact, dashboard, or report to the portal.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Publish a report to the Aily reports portal

Uploads a report artifact to the private, VPN-only reports portal backed by S3.
The portal serves whatever is uploaded under `reports/<category>/<slug>/`.

## How the portal resolves a report

The portal lists one entry per `reports/<category>/<slug>/` and serves its
index object, preferring `bundle.html` then `index.html`. So:

- **Single-file artifact** (`bundle.html`): upload it to
  `reports/<category>/<slug>/bundle.html`.
- **Multi-file artifact** (`dist/` with `index.html` + hashed JS/CSS): sync the
  whole folder to `reports/<category>/<slug>/`, keeping relative paths so the
  app can serve `index.html` and its assets.

## Inputs to collect

1. **Artifact path** — a `bundle.html` file, or a directory (e.g. a Vite
   `dist/`) containing `index.html`.
2. **Category** — the authorization unit (e.g. `aps`, `finops`, `tech-platform`).
   Access to a category is granted by per-category emails and/or Entra groups
   in the portal access map.
3. **Report slug** — kebab-case identifier for this report
   (e.g. `sla-dashboard`, `2026-06-monthly`). Reports with the same slug
   overwrite (bucket versioning keeps history).
4. **Environment** — `dev` or `prod` (default `dev` for first validation).

## Environment → bucket

| env  | AWS profile          | bucket                                |
|------|----------------------|---------------------------------------|
| dev  | `aws-infrastructure` | `aily-infrastructure-dev-reports`     |
| prod | `aws-infrastructure` | `aily-infrastructure-prod-reports`    |

> Confirm the real bucket name with the user / terragrunt outputs before the
> first publish; never guess a bucket that may not exist yet.

## Preconditions

```bash
aws sts get-caller-identity --profile aws-infrastructure >/dev/null 2>&1 \
  || echo "Run: aws sso login --profile aws-infrastructure"
```

If the command fails with SSO expiry, stop and ask the user to run
`aws sso login --profile aws-infrastructure`, then continue.

## Workflow

### Step 1 — Identify the artifact shape

```bash
# If given a directory:
ls -1 "<artifact_dir>"          # expect index.html (+ assets) or bundle.html
# If given a single file: confirm it ends in .html and is self-contained.
```

If the directory has a `dist/` subfolder (Vite/Parcel output), use that as the
upload root. Prefer a single `bundle.html` when both are present, per the
portal convention.

### Step 2 — Confirm category, slug, env

Restate to the user: `env=<dev|prod> category=<category> slug=<slug>` and the
resolved bucket. Get explicit confirmation before any upload to **prod**.

### Step 3 — Upload

Single-file:

```bash
aws s3 cp "<artifact>/bundle.html" \
  "s3://<bucket>/reports/<category>/<slug>/bundle.html" \
  --content-type "text/html" \
  --profile aws-infrastructure
```

Multi-file (sync the folder, set HTML content types, prune removed assets):

```bash
aws s3 sync "<dist_dir>/" \
  "s3://<bucket>/reports/<category>/<slug>/" \
  --delete \
  --profile aws-infrastructure
```

`aws s3 sync` infers most content types; verify `index.html` is served as
`text/html` afterward.

### Step 4 — Verify

```bash
aws s3 ls "s3://<bucket>/reports/<category>/<slug>/" --profile aws-infrastructure
```

Then give the user the URL:

- dev: `https://reports-dev.infrastructure.aily-app.com/c/<category>`
- prod: `https://reports.infrastructure.aily-app.com/c/<category>`

(Access requires the corporate VPN and an email/group entry for the category
in the portal access map.)

### Step 5 — New-category check

If `<category>` was not previously present
(`aws s3 ls s3://<bucket>/reports/` shows it is new), the artifact is uploaded
but **nobody can see it yet**. Tell the user to grant access in the env overlay
access map (`gitops-controlplane/apps/<env>/reports-portal/access-map.yaml`) by
email and/or Entra group, then open a gitops PR:

```yaml
categories:
  <category>:
    emails:
      - "someone@ailylabs.com"
    groups:
      - "<entra-group-object-id>"
```

A bare list of emails also works as shorthand. Once the PR merges and Flux
reconciles, the category appears for the listed users. See `ENTRA-SETUP.md` in
the reports-portal app folder for details.

## Guardrails

- Never upload to the **prod** bucket without explicit user confirmation.
- Never modify objects outside `reports/<category>/<slug>/`.
- Do not create or alter IAM, buckets, or Entra resources from this skill — it
  only uploads artifacts. Infra changes go through terragrunt / gitops PRs.
