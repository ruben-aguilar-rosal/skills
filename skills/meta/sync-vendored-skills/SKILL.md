---
name: sync-vendored-skills
description: User wants to update/sync the vendored skills in this repo to their latest upstream (e.g. "check for upstream updates", "sync the skills", "matt pocock has changes"). Detects upstream changes, re-vendors each verbatim through the security gate, triages new findings and upstream renames with human judgment, and lands everything in ONE PR. Use for the recurring update pass; use vendor-remote-skills to onboard a brand-new upstream skill.
metadata:
  source: ruben-aguilar-rosal/skills
  labels: meta,skills,tooling
  deprecated: "false"
---

# Syncing Vendored Skills

## Objective

Update the already-vendored skills to their latest upstream. The `skillsync` CLI
is the engine, but the update pass has **edge cases that need a session's
judgment**, not just the CLI:

- **`skillsync sync` does NOT touch vendored skills.** It only processes *adapted*
  skills (those with an `adaptation.md`). A verbatim-vendored skill is re-vendored
  by **re-running `skillsync add`**, which re-mirrors at HEAD, re-runs the security
  gate, and bumps the pin on a pass. This is the single most important fact here.
- **Upstream renames/removals** (`to-issues`→`to-tickets`) surface as a `removed`
  change. The CLI can't decide adopt-vs-drop — you do.
- **New security-gate findings** on a bumped skill need a human to read the flagged
  line and judge false-positive vs real before any `accept_findings`.
- **One PR, not N.** `add --no-pr` writes to the working tree; you bundle the whole
  batch into a single branch + PR.

Companion skill: **`vendor-remote-skills`** onboards a *new* upstream skill. This
skill is the recurring *update* of ones already tracked.

## Prerequisites (verify FIRST — a skipped check causes the worst failure mode)

- **`skillspector` must be on PATH.** The gate is fail-safe: if the scanner can't
  run, EVERY skill quarantines and files a GitHub issue. A batch then spews dozens
  of bogus quarantine issues. It installs to `~/.local/bin` (uv tool), which is
  often *not* on a non-interactive PATH. Check: `command -v skillspector`. Install:
  `uv tool install git+https://github.com/NVIDIA/SkillSpector` (it is NOT on PyPI).
  The bundled `revendor.sh` hard-prepends `~/.local/bin` and aborts if the scanner
  is still missing — use it rather than a hand-rolled loop.
- **Private upstreams need git auth.** `detect` aborts on the first unreachable
  repo. If a source 404s (lost org access), it can't be synced — convert it to a
  local skill instead (drop the source from `sources.yaml`, keep the folder, delete
  its `.upstream/`). Run `gh auth setup-git` once so HTTPS mirror clones authenticate.
- **Run through the project venv** (`.venv/bin/...` or `uv run`). Sourcing the venv
  activate script can clobber PATH in a subshell; the scripts call the venv binary
  by absolute path to avoid that.

## LLM MUST

- **Detect first, report by source.** Run `skillsync detect` (or the bundled
  `map_changes.py` for the actionable TSV). Group the changed/new/removed skills by
  upstream repo and show the user the scope before doing anything.
- **Re-vendor with `add --no-pr`, never `sync`.** For each changed skill:
  `uv run skillsync add <repo> <skill-path> --no-pr`. The existing pin is reused, so
  `dest` and prior `accept_findings` are preserved. Batch it with `revendor.sh`
  (stdin = `map_changes.py` output) so the PATH is correct and outcomes are logged.
- **Read every NEW blocking finding before accepting it.** A bumped skill can trip a
  HIGH/CRITICAL beyond what its pin already accepts. Use `triage_finding.py <upstream
  dir>` to print the exact flagged line + snippet. Only after judging it a false
  positive, add the rule id to that pin's `accept_findings` and re-run `add`. State
  the justification in the PR. **A genuinely suspicious finding is a STOP — surface
  it, do not vendor.** Never blanket-accept; never accept unread.
- **Handle renames/removals as a decision, not a skip.** A `removed` skill means its
  upstream subtree lost its SKILL.md (renamed or deleted). Confirm by listing the
  upstream folder. If renamed, ask the user whether to adopt the new name: adopt =
  `add` the new path (+`--dest`), then delete the stale pin and folder. If genuinely
  gone, drop the pin and folder (or `skillsync ignore` if it was a watch discovery).
- **`accept_invalid` for the referenced-file false positive.** Validation flags any
  path that *looks* like a bundled file but is only prose or a template placeholder
  (`edit src/auth.ts:42`, `[title](link)`, "see docs/agents/x.md"). Confirm the path
  isn't a real shipped file, then set `accept_invalid: true` on the pin. Also required
  when frontmatter `name` ≠ folder name.
- **Pre-seed the pin before re-running `add`** when you add `accept_findings` /
  `accept_invalid` — `add` reuses the existing pin rather than duplicating it.
- **Verify before committing.** `skillsync status` (every synced skill reads
  `upstream=synced clean`), diff a couple of `SKILL.md` against upstream to confirm
  verbatim, and run `pytest -q` (the CLI's own tests must stay green).
- **One PR off `main`.** Branch `chore/sync-upstream-<date>`. The PR body lists: which
  skills bumped, every rename adopted/dropped, and every new `accept_findings` /
  `accept_invalid` with its one-line justification.
- **Clean up bogus artifacts you create.** If a misfire files quarantine issues
  (e.g. scanner-not-on-PATH), close them with a comment saying why they were false,
  before re-running. Don't leave a trail of bogus issues.

## LLM SHOULD

- Prefer batching a whole source at a time; it keeps the PR reviewable by upstream.
- Note that newly-adopted skills are not installed; suggest
  `uv run skillsync install --skill-set <category>` after merge. Existing installs go stale
  on every sync, so the same command refreshes them (`--dry-run` first shows what changed).
- Flag brand-new upstream skills you did NOT adopt (they surface as watch
  discoveries) so the user can decide separately — don't silently pull them in.
- Keep commits factual and mirror the existing `chore: sync ...` style.

## Procedure (reference)

```bash
# 0. prerequisites
command -v skillspector || uv tool install git+https://github.com/NVIDIA/SkillSpector
gh auth setup-git                      # once, so HTTPS mirror clones authenticate

S=skills/meta/sync-vendored-skills/scripts

# 1. detect + map to repo/path/kind (actionable rows only)
.venv/bin/python $S/map_changes.py | tee /tmp/changes.tsv
#   kind == removed  -> a rename/deletion; inspect upstream and decide (step 4)

# 2. batch re-vendor changed skills into the working tree (ONE commit later)
grep -P '\tchanged$' /tmp/changes.tsv | $S/revendor.sh
#   review the printed "non-local" rows: quarantined (new finding) or invalid

# 3. triage each non-local outcome — READ the flagged content
git clone --depth 1 https://github.com/<owner>/<repo>.git /tmp/<repo>   # scan surface
.venv/bin/python $S/triage_finding.py /tmp/<repo>/<skill-subpath>
#   false positive? add the rule id to that pin's accept_findings (or accept_invalid
#   for a prose "referenced file"), then re-run: uv run skillsync add <repo> <path> --no-pr
#   suspicious? STOP and surface to the user.

# 4. renames: adopt new name, drop the old pin+folder
uv run skillsync add <repo> <new-skill-path> --dest skills/<category> --no-pr
#   then remove the stale pin from sources.yaml and: rm -rf skills/<category>/<old-name>

# 5. verify
uv run skillsync status            # every synced skill: upstream=synced clean
uv run skillsync config-check      # sources.yaml parses
.venv/bin/python -m pytest -q      # CLI tests green

# 6. one PR off main
git checkout -b chore/sync-upstream-$(cat /tmp/date)   # pass date in; no clock in scripts
git add -A && git commit && gh pr create --base main ...
```

## Scripts

- `scripts/map_changes.py` — runs skillsync's own `detect` and prints
  `repo <TAB> path <TAB> kind` for every skill needing action (`--repo` to scope).
- `scripts/revendor.sh` — reads those rows on stdin, re-vendors each via
  `add --no-pr` with `skillspector` guaranteed on PATH, logs outcomes, and lists the
  rows that need triage. Aborts if the scanner is missing.
- `scripts/triage_finding.py` — prints the exact flagged line + snippet behind each
  blocking gate finding for a skill dir, so you judge false-positive vs real without
  guessing.

## Anti-Patterns

- Running `skillsync sync` and concluding "nothing changed" — it SKIPS vendored
  skills by design. Use `add` to re-vendor them.
- Batch-running the gate without `skillspector` on PATH — fail-safe quarantines the
  whole batch and files bogus issues.
- Accepting a new HIGH/CRITICAL finding without reading the flagged line, or
  blanket-accepting findings across a batch.
- Treating a `removed`/renamed skill as an error to skip instead of an adopt-vs-drop
  decision.
- Opening one PR per changed skill (dozens of PRs) instead of one batched PR off `main`.
- Sourcing `.venv/bin/activate` inside a helper subshell (clobbers PATH); call the
  venv binary by absolute path.
- Leaving bogus quarantine issues open after a misfire.
