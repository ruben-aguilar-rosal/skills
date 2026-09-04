---
name: cold-review
description: >
  Cold read of a diff along two axes, each in its own sub-agent with no framing: Behaviour
  (the Optiak standards) and Ponytail (over-engineering). Use after /code-review, before
  opening a pull request, or when the user asks for an unbiased second opinion on a diff.
---

# cold-review

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Behaviour**: does the diff breach an Optiak behaviour?
- **Ponytail**: is the diff longer or cleverer than the job needs?

Both axes run as **parallel sub-agents** so they do not pollute each other's context, then this
skill reports them side by side.

**Framing is what you withhold.** The ticket, the plan, the standards, your account of the work:
each one makes a reviewer agree with you. Neither sub-agent gets any of them.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point: a commit, a branch, a tag, `main`, `HEAD~5`. If they
did not say, ask.

```bash
git rev-parse <fixed-point>
git diff <fixed-point>...HEAD --stat
git log <fixed-point>..HEAD --oneline
```

Three-dot, so the comparison runs against the merge-base. A bad ref or an empty diff fails here,
not inside two sub-agents.

**Done when** the ref resolves and the diff is not empty.

### 2. Spawn both sub-agents in parallel

One message, two `Agent` calls, `subagent_type: general-purpose`.

**Behaviour sub-agent prompt** carries:

- The full diff command and the commit list.
- The brief: "Invoke the `optiak-behaviours`, `optiak-writing` and `optiak-tracker` skills; if the
  Skill tool does not offer them, read `~/.claude/skills/<name>/SKILL.md`. Report every breach as
  one line: the behaviour id, `file:line`, the text at fault, and the replacement you suggest.
  Read the repository where you need to: two `B4` cases are invisible in a diff, being rationale
  duplicated in a file the diff does not touch, and caller-specific detail in a shared module.
  Mark each finding a hard breach or a judgement call. A rule's own **Allowed** list makes it a
  judgement call. Report only a breach you can point at. Under 400 words."

**Ponytail sub-agent prompt** carries:

- The full diff command and the commit list.
- The brief: "Invoke the `ponytail-review` skill and follow it against this diff. Report in its
  format: `<file>:L<line>: <tag> <what>. <replacement>.` Mark each finding a hard breach or a
  judgement call. Skip anything tooling enforces. Under 400 words."

Give neither one the ticket, the plan, the standards, or your summary.

**Done when** both have reported.

### 3. Report

Present the two reports under `## Behaviour` and `## Ponytail`, verbatim or lightly cleaned.

Do **not** merge, dedupe or rerank the findings. The two axes are deliberately separate, so a line
both axes name is printed twice, once under each. See *Why two axes*.

End with one line: the count per axis, and the worst finding **within each axis**. Do not pick a
winner across axes. That is the reranking the separation exists to prevent.

**Done when** both axes have a heading, and neither report has been reordered.

### 4. Verdicts before code

The user answers per finding: **fix**, **drop** or **defer**.

Write no code until they answer. A finding you fix before the verdict is one they never got to
refuse.

- **fix** here, in this diff.
- **drop**, with one clause of why.
- **defer**: run `/file-issue`, report the key.

A finding they question gets the `/pr-review` card, same six fields.

**Done when** every finding carries one of the three verdicts and none has been acted on.

### 5. Apply the fixes

Make every **fix** change. Run the repo's fast checks. Show the user one diff and stop. 🌝

Committing, opening a pull request and merging belong to `/ship`.

**Done when** every **fix** finding is in the working tree, the fast checks are green, and the
user has seen one diff.

## Why two axes

A change can pass one axis and fail the other:

- A diff that breaks no behaviour but hand-rolls what the standard library ships → **Behaviour
  pass, Ponytail fail.**
- A diff that is as short as it can be, carrying a comment that narrates the change → **Ponytail
  pass, Behaviour fail.**

Reporting them separately stops one axis from masking the other.

`/code-review` is the other pair: Standards and Spec. Run it first. It reads the ticket, so it is
the axis that knows what the work was for. This one is the axis that does not.
