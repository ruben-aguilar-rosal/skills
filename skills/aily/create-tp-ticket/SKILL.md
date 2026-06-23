---
name: create-tp-ticket
description: >-
  Creates a TP Jira ticket (Story, component Infrastructure) for the infra
  team. Use when the user asks to "file a TP ticket", "create an infra
  story", "open a TP story", or wants to turn a Slack thread or a plain
  request into a TP ticket. Works from a Slack thread URL OR a free-form
  ask — if free-form, the skill asks clarifying questions before drafting.
  Ticket body always contains Context, Goal, Acceptance Criteria sections.
---

# Create TP Infra Ticket

Create a Jira **Story** in project **TP** with component **Infrastructure** via the Jira MCP.

Tickets must be concise. No filler. Every section earns its place; drop optional sections if they add nothing.

## Inputs

One of:
- **Slack thread URL**, e.g. `https://aily-labs.slack.com/archives/C0123ABCD/p1700000000000100`
- **Free-form ask**, e.g. "open a TP to migrate the runner image to ubuntu 24.04"

Optional extras the user may provide alongside either: extra context, design notes, technical details, priority, labels, assignee.

## Workflow

### Step 1 — Detect input mode

- URL matching `https://*.slack.com/archives/…` → **thread mode**
- Anything else → **ask mode**

If the user supplied both a thread URL and extra prose, use thread mode and merge the prose into Context.

### Step 2a — Thread mode: fetch the thread

Parse `channel_id` and `thread_ts` from the URL:
1. `channel_id` = `C…` segment after `/archives/`.
2. `thread_ts`:
   - If the URL has `thread_ts=…` query param, use it verbatim.
   - Otherwise, take the `p<digits>` segment and insert a decimal before the last 6 digits. Example: `p1700000000000100` → `1700000000.000100`.

Fetch replies:

```
mcp__mcp-global-slack__slack_get_thread_replies
  channel_id: <parsed>
  thread_ts:  <parsed>
```

Resolve every distinct `user` id to a display name with `mcp__mcp-global-slack__slack_get_user_profile`. Cache within the run.

If the MCP returns empty or "not in channel", stop and tell the user the bot can't see the thread. Do NOT fabricate content. Offer to fall back to ask mode using whatever prose the user already gave.

From the thread, draft candidate Context / Goal / Acceptance Criteria. If any of the three can't be inferred, flag it and ask the user to fill the gap in step 3.

### Step 2b — Ask mode: clarify

Use a single `AskUserQuestion` call with up to 4 questions to gather missing signal. Skip a question if the user's initial message already answers it.

Ask about:
1. **Context** — what triggered this, what system/repo is affected, any prior work.
2. **Goal** — one-sentence description of success.
3. **Acceptance Criteria** — concrete checks that must pass.
4. **Scope boundaries** — what's out of scope, constraints, dependencies.

Keep questions short. Offer plausible options where you can infer them; otherwise just ask open-ended.

### Step 3 — Draft summary and description

**Summary** — one imperative line, ~80 chars max. The ask, not the narrative.
Examples:
- `Migrate self-hosted runner image to Ubuntu 24.04`
- `Split DBO and IAM-auth postgres roles in SE service DBs`

**Description** — plain text, Jira wiki newlines. Always these three sections, in this order:

```
h2. Context
<2–5 concise lines. Why this ticket exists, what system, what prompted it.>

h2. Goal
<1–2 sentences. What "done" looks like.>

h2. Acceptance Criteria
* <concrete, verifiable check>
* <concrete, verifiable check>
* <concrete, verifiable check>
```

Add these only when they carry real signal:

```
h2. Design notes
<trade-offs, alternatives considered, chosen approach and why>

h2. Technical details
<specific files, modules, endpoints, configs, commands>
```

If a section would just restate Context or Goal, drop it.

If the source was a Slack thread, append at the very end:

```
Slack thread: <original URL>
```

Rules:
- Paraphrase the thread. No raw pastes, no user IDs (resolve to names).
- Bullet lists only when items are genuinely parallel. Prose otherwise.
- No hedging ("we might want to consider possibly…"). State the ask.

### Step 4 — Confirm with the user

Show the drafted summary and description and ask for approval via `AskUserQuestion`:
- "Create ticket as drafted"
- "Edit before creating" (take edits, re-show, re-confirm)
- "Cancel"

Do not proceed without explicit approval.

### Step 5 — Create the ticket

Use the Jira MCP directly:

```
mcp__mcp-global-atlassian__jira_create_issue
  project_key: TP
  summary:     <approved summary>
  issue_type:  Story
  description: <approved description>
  components:  Infrastructure
```

If the user asked for extras, pass them via `additional_fields`:
- priority → `{"priority": {"name": "<name>"}}`
- labels → `{"labels": ["<label>", ...]}`
- assignee → top-level `assignee` arg (email, display name, or account ID)

Capture the returned issue key and URL.

### Step 6 — Offer to post back to Slack (thread mode only)

Skip entirely in ask mode.

In thread mode, ask via `AskUserQuestion` whether to reply in the original thread with the ticket link. If yes:

```
mcp__mcp-global-slack__slack_reply_to_thread
  channel_id: <from step 2a>
  thread_ts:  <from step 2a>
  text: "Filed as <ticket URL>"
```

If no, just print the ticket URL and stop.

## Error handling

- Slack MCP empty / "not in channel" → tell the user; offer ask-mode fallback.
- Jira MCP error → surface the error as-is. Do NOT retry automatically — usually a field-mapping or permissions issue needing human judgment.
- User cancels at step 4 → stop silently. No ticket, no Slack reply.

## Do NOT

- Do not create the ticket without the confirmation step (step 4).
- Do not post to Slack without the confirmation step (step 6).
- Do not invent Context/Goal/AC content when the user didn't provide enough — ask.
- Do not include raw Slack user IDs in the description.
- Do not add Design notes or Technical details just to fill space.
- Do not change component away from `Infrastructure`.
- Do not change issue type away from `Story` unless the user explicitly asked.
