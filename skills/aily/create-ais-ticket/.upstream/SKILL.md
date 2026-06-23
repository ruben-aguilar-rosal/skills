---
name: create-ais-ticket
description: >-
  Creates an AIS Jira support ticket from a Slack thread. Use when the user asks
  to "file an AIS ticket", "raise an infra ticket", "create a support ticket",
  or passes a Slack thread link and wants it turned into a Jira ticket for the
  infra team. Reads the thread via the Slack MCP, drafts a summary and
  description, confirms with the user, then runs the bundled create_ais_ticket.py.
---

# Create AIS Support Ticket from Slack Thread

Turn a Slack thread into a Jira ticket in the **AIS** service desk (serviceDeskId=104, requestTypeId=927 — "Infrastructure request or guidance").

## Inputs

- **Required**: a Slack thread URL, e.g.
  - Top of thread: `https://aily-labs.slack.com/archives/C0123ABCD/p1700000000000100`
  - Reply in thread: `https://aily-labs.slack.com/archives/C0123ABCD/p1700001111222333?thread_ts=1700000000.000100&cid=C0123ABCD`
- **Optional**: extra context the user wants included in the ticket description.
- **Optional**: urgency override — `Low`, `Medium`, or `High`. Default is `Medium`.

## Prerequisites

The bundled script (`~/.claude/skills/create-ais-ticket/scripts/create_ais_ticket.py`) needs these env vars to be exported in the current shell:

- `JIRA_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

If a ticket-creation call fails with an auth error, verify those are set before retrying.

## Workflow

### Step 1 — Parse the Slack URL

Extract `channel_id` and `thread_ts`:

1. `channel_id` = the `C…` segment after `/archives/`.
2. `thread_ts`:
   - If the URL has a `thread_ts=…` query param, use it verbatim.
   - Otherwise, take the `p<digits>` segment from the path and insert a decimal point before the last 6 digits. Example: `p1700000000000100` → `1700000000.000100`.

If the URL is a permalink to a single message that is NOT a thread, passing that message's ts as `thread_ts` to `slack_get_thread_replies` still works — it returns just the one message.

### Step 2 — Fetch the thread

```
mcp__mcp-global-slack__slack_get_thread_replies
  channel_id: <from step 1>
  thread_ts:  <from step 1>
```

For every distinct `user` id in the replies, resolve a human-readable name:

```
mcp__mcp-global-slack__slack_get_user_profile
  user_id: <id>
```

Cache within this run so each user is only fetched once.

If the MCP returns an error like "not in channel" or an empty payload, stop and tell the user — the Slack bot likely isn't a member of that channel. Do NOT fabricate thread content.

### Step 3 — Draft summary and description

**Summary** — one imperative line, ~80 chars max. Capture the ask, not the symptom narrative. Examples:
- `Grant the data-normalizer role access to Textract`
- `Investigate intermittent 5xx from aily-agent in sanofi prod`

**Description** — plain text (Jira wiki renders links and newlines). Structure:

```
<1–2 sentence problem statement>

Context from Slack thread:
- <reporter>: <paraphrased message>
- <reporter>: <paraphrased message>
...

<Any extra context the user provided>

Slack thread: <original URL>
```

Rules:
- Paraphrase, don't paste raw JSON or verbatim noisy messages. Keep signal.
- Always end with `Slack thread: <url>` on its own line.
- If the user passed extra context alongside the URL, merge it under its own paragraph above the Slack link.

### Step 4 — Confirm with the user

Show the drafted summary and description and ask for approval. Use `AskUserQuestion` with options like:
- "Create ticket as drafted"
- "Edit before creating" (then take their edits and re-confirm)
- "Cancel"

Do not proceed to step 5 without explicit approval.

### Step 5 — Create the ticket

Run the existing script via `uv` (it's a PEP 723 inline-metadata script — `uv` resolves its deps automatically). Shell-quote carefully; the description will contain newlines.

```bash
uv run ~/.claude/skills/create-ais-ticket/scripts/create_ais_ticket.py \
  --summary "<approved summary>" \
  --description "<approved description>"
```

Pass `--urgency <Low|Medium|High>` **only** if the user explicitly overrode the default.

The script prints two lines on success:
```
Created: AIS-<n>
<JIRA_URL>/browse/AIS-<n>
```

Capture the issue key and URL from stdout.

### Step 6 — Offer to post back to Slack

Ask the user (via `AskUserQuestion`) whether to reply in the original Slack thread with the ticket link. If yes:

```
mcp__mcp-global-slack__slack_reply_to_thread
  channel_id: <from step 1>
  thread_ts:  <from step 1>
  text: "Filed as <ticket URL>"
```

If no, just report the ticket URL in the terminal and stop.

## Error handling

- Slack MCP returns no messages → tell the user the bot can't see the thread; ask for summary/description manually if they still want to file the ticket.
- Script exits non-zero → surface the stderr to the user as-is; do NOT retry automatically (failures are usually auth or field-mapping issues that need human judgment).
- User cancels at step 4 → stop silently, no ticket, no Slack reply.

## Do NOT

- Do not create the ticket without the confirmation step (step 4).
- Do not post to Slack without the confirmation step (step 6).
- Do not guess `channel_id` or `thread_ts` — parse them from the URL.
- Do not change urgency away from Medium unless the user asked.
- Do not include raw Slack user IDs (`U0ABCDEF`) in the description; always resolve to display names.
