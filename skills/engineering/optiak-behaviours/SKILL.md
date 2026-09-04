---
name: optiak-behaviours
description: >
  How to work and what to write into the code at Optiak: comments that last, no tracker keys in
  source, no explanation nobody needed, and what counts as evidence that infrastructure works.
  Use before editing code, when writing or reading a comment or a docstring, and when reviewing
  a diff for breaches.
---

# optiak-behaviours

Failure modes that coding agents repeat. Each one is cheap to prevent and expensive to clean up
later, because it survives review and lands in the repository.

Two readers:

1. **The implementing agent**, which follows every rule while it works.
2. **The behaviour reviewer**, a separate agent that reads the finished diff and reports each
   breach. It reads only this file, so write the rule out. Nothing here can be inferred.

Text style is `optiak-writing`. Where work goes is `optiak-tracker`.

## How you work

Four rules, before any of the behaviours below.

- **Surface assumptions.** State them. Ask only when the ambiguity changes the solution.
- **Smallest correct solution.** No speculative work. Reuse what is here, then the standard
  library, then an installed dependency.
- **Surgical changes.** Fix the root cause. Match local style. Leave unrelated code alone.
- **Name the check.** Define how you will know it works, then run it. Report a failure plainly.

## How to add a behaviour

Open a pull request on this file. An entry needs a stable id, the rule in one sentence, why it
costs something, what to do instead, and what is explicitly allowed. The last part matters most:
a rule with no boundary gets applied where it does not belong, and then gets ignored everywhere.

---

## B1 — Comments that do not last

**Rule.** Write a comment only for what will still be true in a year. Never narrate the
change you are making.

**Why.** A comment that describes an edit becomes a lie as soon as the next edit lands.
Nobody deletes it, because nobody can tell whether it still matters. The file then carries
a history that git already holds, and readers learn to skip comments entirely — which
costs you the comments that were worth reading.

**Do not write.**

- A changelog: "was 3, now 4", "renamed from `foo`", "removed the retry".
- The fix you just applied: "fixed the bug where the token expired".
- What the code already says: `# increment the counter` above `counter += 1`.
- A note to a future reader about work in progress: "temporary", "for now", "clean up
  later" — with no statement of the condition that would make it removable.

**Write instead.** The constraint, the reason, or the consequence:

- Why a non-obvious choice is the right one, so nobody undoes it: *"4 hours. Long enough
  for one ticket. A stolen credential expires soon."*
- The trap a reader would otherwise fall into: *"The action does not accept a resource, so
  the resource must be `*`."*
- The invariant a change would break: *"kms.tf declares this data source."*

**Allowed.** A comment about a fix, when the fix is not self-evident and someone would
plausibly revert it. Explain the trap, not the history: *"`|| true`: a plain assignment
from a failing command aborts under `set -e`."*

**Check yourself.** Would this comment make sense to somebody opening the file for the
first time, who knows nothing about your change? If not, delete it.

**Related.** `ponytail` (do not write what is not needed), `i-have-adhd` (lead with the
point), `B6` (one meaning per word, short sentences), `B4` (this rule decides
whether a comment should exist; `B4` decides how much of it should).

---

## B2 — Issue-tracker references in code or documentation

**Rule.** Never put an issue-tracker key or link in code, in a comment, or in
documentation. State the condition, constraint or consequence the ticket stands for.

**Why.** A ticket closes, gets renamed, or is superseded, and the reference becomes a dead
end for the reader who follows it. A forward reference — "OPT-123 will fix this" — goes
stale the moment that work lands, and it will not be revisited. Identifiers rot. Comments
should not.

**Do not write.**

```python
# OPT-1234: skip validation until the migration lands
# see https://linear.app/optiak/issue/OPT-1234
```

**Write instead.**

```python
# Validation runs against the new column only. Remove this branch once every row
# has been backfilled and the old column is dropped.
```

The second version tells the reader what to check and when the code can go. The first
sends them to a tracker to find that out, if the ticket still exists.

**Where attribution belongs.** Commit messages and pull request descriptions. Both are
expected to age, both are read in the context of the change, and neither is read as
current documentation.

**Allowed.**

- In-repo paths and filenames. They move with the code, so they stay true.
- A ticket key used as a **placeholder in a usage example**, where it shows the shape of
  an argument rather than pointing at real work: `optiak-sandbox start OPT-870`,
  `linear issue view OPT-870`. Nobody follows these as references.
- A ticket key a **tool requires**, such as a branch name that lets the tracker link the
  pull request.

**Check yourself.** Am I telling the reader something, or am I telling them where to go
and ask? Only the first belongs in the repository.

---

## B4 — Explanation nobody needed

**Rule.** Explain only what a reader cannot get from the code in front of them, and
explain it once.

**Why.** Over-explaining costs what having no comments costs. A reader who hits three
sentences restating the line above learns to skim, and skims past the one paragraph that
was worth reading. Duplicated rationale also has to be maintained in every copy, the
copies drift, and then nobody can tell which is current. Prose in a shared module about
one caller's setup is simply wrong for the second caller.

**Do not write.**

- A comment announcing an absence: *"this stack holds no database SQL"*, *"the module
  runs no SQL, and neither does the caller"*. Nothing being there is already visible.
- A restatement of the adjacent declaration — a call-site comment paraphrasing the
  variable's own description.
- The same rationale in more than one file. Pick the file the reader is in at the moment
  the question occurs to them.
- Caller-specific detail in a shared module's documentation. A Glue module explaining
  Redshift privileges is wrong for the caller that queries with Athena.
- The evidence for a decision at the length you gathered it. The measurement convinced
  you; the reader needs the conclusion and the command to re-check it.

**Write instead.** Length in proportion to how surprising the fact is: a clause for a
convention, a sentence for a trap, plus the check that tells a reader whether it still
applies. The argument itself belongs in the pull request or in `FOLLOW-UPS.md`, both of
which are read once, in context, and are expected to age.

**Allowed.**

- A genuinely non-obvious trap, at whatever length it takes to state — B1 asks for this.
- One canonical explanation of a decision someone would otherwise undo, in one place,
  with other sites pointing at it only if they must point at all.
- A measured number where the number is the constraint: *"2s connect, 5s read: a wedged
  call outlives the whole shutdown sequence."*

**Check yourself.** Would somebody who did not just do this work do anything differently
because of this sentence? And does the fact already appear elsewhere in the diff? Cut on
either answer.

**Related.** `ponytail` (do not write what is not needed), `i-have-adhd` (lead with the
point), `B6` (short sentences), `B1` (which governs whether a comment
should exist at all; this one governs how much of it should).

---

## B7 — Infrastructure changed with no evidence it works

**Rule.** An infrastructure change is proven by a real resource in staging answering a call. Get
there through the repository's own wrapper, and name the call that proves it in the ticket's
`Done when`.

**Why.** Terraform that parses is not a working stack. `validate` checks syntax and provider
schema, so it cannot tell you the role has the permission, the stream reaches its destination or
the alarm fires. A `.tftest.hcl` asserts against a mocked provider, which is a model of the cloud
rather than the cloud. Staging is the cheapest place where the real answer exists.

**Do not run.**

- Bare `terraform plan`, `init`, `validate` or `apply` where a wrapper exists. The wrapper
  resolves the profile, checks it against the expected account id, renews the SSO and secret
  sessions, reads the stack's variables and runs `init` first. Called directly, terraform either
  fails on credentials or succeeds against the wrong account.
- `apply` on a shared environment before the user says so. Staging is shared, and somebody else
  is reading it right now.
- A red test as the first step of an infra ticket. There is nothing to fail: the loop is change,
  plan, apply, observe.

**Run instead.** `make help` lists what the repository has. Where the targets exist:

```bash
make fmt   env=<env>
make plan  env=<env>     # the change list, plus findings ranked against the branch diff
make apply env=<env>     # ask first
```

Then confirm the resource behaves as promised, with a read-only call: `aws`, `curl`, a query
against the service. That command is the evidence.

**Allowed.**

- A repository with no wrapper. Its pull request runs the plan in CI and posts it as a comment;
  that comment is the plan you read, and the merge is what applies.
- Reading state and outputs directly: `plan`, `output`, `state list`, `state show`. They change
  nothing.
- Shipping an infra change whose staging check has to wait, when the user says so. Say which
  observation is still outstanding, so it does not get lost.

**Check yourself.** If somebody asks how you know this works, is the answer a command they can
re-run against a real environment? A file that passed is not that answer.

**Related.** `tdd` (the red → green loop, which this replaces for infra code), `B3` (an
observation you could not make yet is a follow-up entry).
