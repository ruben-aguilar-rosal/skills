---
name: jira
description: |
  Interact with Aily Labs' Jira (Atlassian) via REST API — read, update,
  transition, comment, link issues, search with JQL, and read Confluence
  pages. Trigger on any mention of Jira ticket keys (APS-, TP-, and similar
  project prefixes), requests to transition/comment/link/assign a ticket,
  JQL searches, or Confluence page reads. Credentials live in
  ~/.claude/.env (JIRA_USERNAME, JIRA_API_TOKEN, CONFLUENCE_USERNAME,
  CONFLUENCE_API_TOKEN). Also includes the APS Service Management
  workaround (use numeric issue IDs, not keys).
allowed-tools:
  - Bash
  - Read
  - Write
---

# Jira

Interact with Jira (Atlassian) using the REST API. Supports reading, updating, transitioning, linking, and commenting on Jira issues, plus Confluence page reads.

## Authentication

Credentials are stored in `~/.claude/.env`. Read this file to get:
- `JIRA_USERNAME` - email for basic auth
- `JIRA_API_TOKEN` - API token for basic auth

Base URL: `https://ailylabs.atlassian.net`

Use basic auth with curl:
```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" "https://ailylabs.atlassian.net/rest/api/3/..."
```

## Usage

The argument `$ARGUMENTS` contains the user's request. Parse it to determine the action.

### Common Operations

**Get issue details:**
```bash
curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/issue/KEY-123?fields=summary,status,description,assignee,priority"
```

**Search issues (JQL):**
```bash
curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/search/jql?jql=project%3D%22APS%22+AND+status%3DOpen&fields=key,summary,status&maxResults=50"
```

**Get available transitions:**
```bash
curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/issue/KEY-123/transitions"
```

**Transition an issue:**
```bash
curl -s -u "$AUTH" -X POST "https://ailylabs.atlassian.net/rest/api/3/issue/KEY-123/transitions" -H "Content-Type: application/json" -d '{"transition":{"id":"2"}}'
```

**Add a comment (Atlassian Document Format):**
```bash
curl -s -u "$AUTH" -X POST "https://ailylabs.atlassian.net/rest/api/3/issue/KEY-123/comment" -H "Content-Type: application/json" -d '{
  "body":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"Comment text here"}]}]}
}'
```

**Link issues:**
```bash
curl -s -u "$AUTH" -X POST "https://ailylabs.atlassian.net/rest/api/3/issueLink" -H "Content-Type: application/json" -d '{
  "type":{"name":"Duplicate"},
  "inwardIssue":{"key":"KEY-456"},
  "outwardIssue":{"key":"KEY-123"}
}'
```

**Assign issue:**
```bash
curl -s -u "$AUTH" -X PUT "https://ailylabs.atlassian.net/rest/api/3/issue/KEY-123/assignee" -H "Content-Type: application/json" -d '{"accountId":"user-account-id"}'
```

**Read Confluence page:**
```bash
curl -s -u "$AUTH" "https://ailylabs.atlassian.net/wiki/api/v2/pages/{PAGE_ID}?body-format=storage"
```

## Instructions

1. Read credentials from `~/.claude/.env` at the start
2. Parse `$ARGUMENTS` to understand what the user wants
3. Execute the appropriate Jira API calls
4. Present results concisely
5. For bulk operations, show progress
6. Always confirm before making destructive or bulk changes unless the user has been explicit

## Known Jira Projects

- **APS**: Aily Platform Support (service desk) — see "APS Service Desk" section below
- **TP**: Tech Platform (software)

## Common Transition IDs (APS project)

These may vary - always verify with the transitions endpoint first:
- `2`: Open → In Progress
- `5`: In Progress → Done
- `6`: In Progress → Rejected

## APS Service Desk — API Access Workaround

**CRITICAL**: APS is a Jira Service Management (JSM) project. The direct issue REST API (`/rest/api/3/issue/APS-XXXX`) returns "Issue does not exist" even though you have access. This is a JSM permission quirk.

**Workaround — use numeric issue IDs from search:**

1. **Search** works normally via JQL (returns issue keys and numeric IDs):
   ```bash
   curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/search/jql?jql=project%3D%22APS%22+AND+key+%3E%3D+APS-10027+AND+key+%3C%3D+APS-10121&fields=key,status,summary&maxResults=100"
   ```

2. **Extract the numeric `id`** from each issue in the search results (e.g., `"id": "288478"` for APS-10027).

3. **Use the numeric ID** for transitions, comments, and updates (NOT the issue key):
   ```bash
   # Transition using numeric ID
   curl -s -X POST -u "$AUTH" -H "Content-Type: application/json" \
     -d '{"transition":{"id":"2"}}' \
     "https://ailylabs.atlassian.net/rest/api/3/issue/288478/transitions"

   # Add comment using numeric ID
   curl -s -X POST -u "$AUTH" -H "Content-Type: application/json" \
     -d @comment.json \
     "https://ailylabs.atlassian.net/rest/api/3/issue/288478/comment"
   ```

4. **Get transitions** via search expand (since direct transitions endpoint also fails):
   ```bash
   curl -s -u "$AUTH" "https://ailylabs.atlassian.net/rest/api/3/search/jql?jql=key+%3E%3D+APS-10027+AND+key+%3C%3D+APS-10027&fields=key,status&expand=transitions&maxResults=1"
   ```

### Bulk operations pattern

For processing many APS tickets at once:
1. Search with JQL to get all matching issues (key, numeric id, status)
2. Save results to a temp file: `id|key|status` per line
3. Loop through the file, using numeric IDs for all API calls
4. Report success/failure counts at the end

## APS Service Desk — Modus Operandi

Reference: https://ailylabs.atlassian.net/wiki/spaces/AIL/pages/3876847644

### Ticket Classification

- **P3-P4**: Portal tickets (reported by users)
- **P2-P4**: Observability tickets (from monitors)

### Auto-Assignment by Source

- **service-support-qa** → reported by a user
- **service-support-mobile** → originating from Sentry
- **service-support-be** → originating from DataDog BE monitors
- **service-support-data** → originating from DataDog Data/BE monitors, Normalization, or QA-Agent
- **service-support-infra** → originating from DataDog Infra monitors

### The Process

1. **Transition to In Progress**
2. **Add a "Reply to Customer"** comment informing the team is investigating
3. **Triage the ticket:**
   - Confirm the incident
   - Ensure fields are correct: Tenants 3.0, Aily Component, Priority
   - If Priority is changed, add a "Reply to Customer" explaining the rationale
   - Reassign to the right QA team member
   - Perform preliminary checks to identify the source
4. **Escalation:**
   - If NOT P2-P4 → change Team to `on-call-app` (auto-assigns to `on-call-app-primary`)
   - If P2-P4 → continue
5. **Resolution:**
   - **Incident not confirmed** → Transition to **Rejected** + Reply to Customer explaining reason
   - **More info needed** → Transition to **Blocked** + Reply to Customer specifying missing details
     - No response in 7 days → send reminder
     - No response in 14 days → Reject with closure comment
   - **Can provide workaround only** → Transition to **Delegate to Dev team** (clones to component team's board) + Close APS ticket with Reply to Customer including: root cause, workaround, confirmation permanent fix in progress
   - **Can provide fix** → Close APS ticket with Reply to Customer including: root cause, fix details

### Important Notes

- If the **Organizations** field is populated, the client can see the ticket — be professional
- **Customer communication is critical**: if fix not delivered within 24 hours, provide daily status updates
- When transitioning to **Done** or **Rejected**, use **"Reply to Customer"** (internal notes are not visible to clients)
- **Never close a ticket before a workaround or fix is deployed to production**
- **Blocked** status should ONLY be used for "More information needed" (point 5.b)
