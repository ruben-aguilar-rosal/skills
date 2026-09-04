---
name: pr-review
description: >
  Work the review on open pull requests: green the checks, triage every unresolved comment one
  at a time, build the approved fixes as one commit, and draft the replies. Use when review
  comments or bot findings have landed, when checks are red, or when the user asks what to do
  about feedback on a pull request.
---

# pr-review

One **round** over the whole stack. At most two commits: one greens the checks, one carries every
approved fix.

Rules and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).

Run it again when new comments land. It reads only **unresolved** threads and keeps no state.

The user's calls, handed over rather than taken: **posting replies**, **resolving threads**,
**marking a pull request ready**, **merging**.

## 1. Find the pull requests

```bash
gh stack view --json 2>/dev/null || gh pr list --head "$(git branch --show-current)" --json number,title,isDraft
```

Work bottom-up: the layer nearest the trunk first.

**Done when** you have an ordered list of pull request numbers.

## 2. Green the checks

```bash
gh pr checks <n> --watch --interval 30
gh run view <run-id> --log-failed
```

Fix the cause. Reproduce locally where you can. Show the user the diff and wait. On their word: one
commit, push.

Make a check pass by fixing the code it tests. A flaky check, or one already failing on the default
branch, goes to the user by name.

**Done when** every pull request reports all checks green, or the user has taken a named failure.

## 3. Collect the threads

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$pr:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$pr){
    reviewThreads(first:100){ nodes{ id isResolved isOutdated path line
      comments(first:10){ nodes{ author{login} body url } } } }
    comments(first:50){ nodes{ author{login} body url } } } } }
' -F owner=<owner> -F repo=<repo> -F pr=<n>
```

Keep threads where `isResolved` is false. Add top-level `comments`; GitHub cannot mark those
resolved, so they reappear each run until the user drops one.

Number them, bottom layer first. Copilot, Aikido and people go in one list.

Show the user the **count only**, on one line: `12 unresolved: PR 947 x3, PR 948 x2, PR 950 x7.`
The contents belong to step 4, one at a time.

**Done when** you hold the ordered list, and the user has seen the count and nothing else.

## 4. One card, one verdict, repeat

A loop. One pass per item.

**Your message ends with the card.** Nothing follows it: no second card, no summary, no next steps.

- **4a.** Print the card for the next item.
- **4b.** Stop. Wait for the verdict.
- **4c.** Acknowledge in one line. Go to 4a.

Write no code anywhere in this step. Bots repeat themselves and separate fixes often merge into one.

```
(#4 of 12)  PR 102 - src/api/routes.py:88 - Copilot

What happens
  <one or two sentences>

Why it is bad
  <one or two sentences>

Example
  <a line of input and what it does, or up to 8 lines of code>

How likely
  <Low | Medium | High>. <one clause>

Is the fix worth it
  <Yes | No>. <one clause>

Suggestion
  <the concrete change, with a file and line>
```

Near 120 words. Your own read of the code decides "is the fix worth it". A finding you cannot
confirm by reading the code is a question for the user.

`nit:` means optional. `question:` wants an answer, not a change.

Three verdicts:

1. **fix** here, in this pull request.
2. **drop** it, with a reply.
3. **defer** it. Run `/file-issue`, then reply with the key it returns.

Where the workspace holds a `FOLLOW-UPS.md`, each verdict also gets an entry. `optiak-tracker`
`B3` has the rule.

**Done when** every numbered item from step 3 has one of the three verdicts. Twelve items take
twelve messages. Reaching this in one message means the loop was skipped, not finished.

## 5. Build the fixes

Take the **fix** items. Where two want the same change, make it once.

Each fix lands in the layer that **owns** the code, often below the layer whose review raised it.
`gh stack view --json` and `git log --all -- <path>` name the owner.

```bash
gh stack checkout <owning layer>
# edit, then:
git add <paths> && git commit -m "<type>: <what changed>"
gh stack rebase --upstack
gh stack push
```

Run the repo's checks once over the finished set, plus the hook check from `../ship-stack/SKILL.md`
step 2. Fold any rewrite into the same commit. Show the user one diff and wait. On their word:
commit, rebase, push.

One commit for the round. Two only when the fixes are unrelated.

**Done when** every **fix** item is in a commit, the checks are green, and the stack is pushed.

## 6. Draft the replies, one at a time

A loop, like step 4. One reply per item from step 3, same order.

**Your message ends with the reply.** Nothing follows it: no second reply, no summary.

- **6a.** Print the item line, the thread URL, and the reply. Nothing else.
- **6b.** Stop. Wait.
- **6c.** Rejected: rewrite. Go to 6b.
- **6d.** Approved: copy it, say so, stop. On their word, go to 6a.

Under 50 words. State the decision and stop. Run each reply through `unslop` and
`asd-ste100-skill` before printing.

```
(#3 of 12)  PR 947 - src/api/routes.py:88
https://github.com/<owner>/<repo>/pull/947#discussion_r123456789

Fixed in 4a91c2c. The guard is added. A test covers the empty case.
```

Copy with a quoted heredoc, so no backtick or `$` expands:

```bash
pbcopy <<'REPLY'
Fixed in 4a91c2c. The guard is added. A test covers the empty case.
REPLY
```

Copy the reply text only: no item line, no URL, no code fence. The clipboard holds one reply, so
never copy ahead.

**Done when** every item from step 3 has been copied or dropped. Twelve items take twelve messages.

## 7. Hand back

Short, with emoji: 🌝

- Checks, per pull request.
- Counts: fixed, dropped, deferred. Ticket keys filed.
- Anything escalated, with the reason.
- The user's three jobs: paste the replies, resolve those threads, mark the clean pull requests
  ready.

A pull request is clean when its checks are green and no thread is unresolved. Name the clean ones.
🤝
