# skills

A personal skill repository that mirrors upstream skill repos (e.g.
[`mattpocock/skills`](https://github.com/mattpocock/skills)), adapts them to my stack
(Jira, product discovery, AWS), security-scans every upstream change with deterministic
tooling, and opens a PR per changed skill for manual approval.

It's a mix of a **deterministic** pipeline (detect upstream changes, security gate, validate
output) and an **agentic** pipeline (adapt skills to my preferences, fold hand-edits back
into rules) driven by headless `claude -p`.

See [`PLAN.md`](./PLAN.md) for the full design.

## Status

🚧 Design complete, implementation pending. The `skillsync/` CLI is not built yet.

## Layout

```
sources.yaml         # allowlist of upstream repos + skill paths + pinned SHAs
profile.md           # author-time context (stack/tone), baked into each adaptation.md
skills/<name>/        # one folder per synced+adapted skill
  upstream/          # pristine mirror of the whole upstream subtree (never hand-edited)
  adaptation.md      # self-contained adaptation rules
  SKILL.md           # build artifact (patch-generated, committed for diff review)
  .generated/        # snapshot of last agent output (drift detection)
skillsync/           # Python CLI
```

## Consumption

Personal use via symlink into the native skills dir:

```
skillsync link    # ln -s skills/<name> -> ~/.claude/skills/<name>
```
