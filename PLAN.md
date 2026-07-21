# skills — Sync & Adapt Pipeline: Design Plan (hardened)

A personal skill repository that mirrors upstream skill repos (e.g. `mattpocock/skills`),
adapts them to Ruben's stack (Jira, product discovery, AWS), security-scans every upstream
change with **deterministic** tooling, and opens a PR per changed skill for manual approval.

Repo location: `~/Developer/github/skills`
Implementation: Python CLI (`skillsync`) — consistent with `python-standards`.
Agentic steps invoke headless **`claude -p`**.
**Cost framing:** `$0 API cost`, but **consumes Claude Code subscription quota** (competes
with interactive usage). Patch-based generation keeps token use modest.
Model: **Opus for every agentic step** (quality over token savings).

---

## Core model — "Regenerate from rules", but PATCH-based by default

Each skill is a folder. The committed `SKILL.md` is a build artifact. On an upstream change
the agent applies the **semantic equivalent of just the upstream delta** to the existing
`SKILL.md` (minimal edit, `temperature 0`) — NOT a full rewrite. Full regeneration happens
only on first onboarding or explicit `skillsync regen --force`. This keeps PR diffs legible.
No 3-way merges.

```
skills/<skill-name>/
  upstream/            # pristine mirror of the WHOLE skill subtree (NEVER hand-edited)
    SKILL.md
    scripts/*.sh, *.py # every helper script the skill ships
    references/, assets/ ...
  adaptation.md        # self-contained rules: your stack/tone (baked in) + skill-specific intent
  SKILL.md             # build artifact; COMMITTED so each PR shows a real before/after diff
  .generated/          # snapshot of exactly what the agent last produced (drift detection)
    SKILL.md
```

- `SKILL.md` is committed (diff review) **and** hand-editable. Manual edits are detected as
  drift and **folded back** into `adaptation.md` so they survive future generations.
- `adaptation.md` is **self-contained** — it embeds your stack/tone verbatim, no shared
  runtime dependency. The generator reads only `adaptation.md`.
- `upstream/` mirrors the **entire skill subtree** — it is the security surface for the scan.

---

## Repo-root files

```
~/Developer/github/skills/
  sources.yaml         # allowlist: which upstream repos + skill paths + pinned SHAs
  profile.md           # AUTHOR-TIME context (Jira, AWS, discovery, tone). Read ONLY by the
                       # drafting/reprofile agent; baked verbatim into each adaptation.md.
                       # The generator NEVER reads this file at generation time.
  skills/<name>/...
  skillsync/           # Python CLI package
    cli.py detect.py scan.py adapt.py foldback.py validate.py reprofile.py llm.py gitio.py
  README.md
```

### `sources.yaml` shape
```yaml
sources:
  - repo: mattpocock/skills
    ref: main                      # ref = WHAT to fetch
    skills:
      - path: engineering/to-issues
        synced_sha: a1b2c3d        # synced_sha = last-seen point
        hold: false                # optional: pin back / exclude from sync
```

---

## Pipeline (per sync run)

```
1. DETECT (deterministic, free)
   For each allowlisted skill:
     git fetch upstream <ref>
     IF synced_sha is NOT an ancestor of <ref>  (force-push / rebase):
        -> treat as RE-ONBOARD; flag PR loudly: "upstream rewrote history — review carefully"
     ELSE:
        diff  synced_sha..HEAD -- <skill subtree>   (whole subtree)
     no change -> skip

2. SECURITY — DETERMINISTIC GATE (must pass), runs BEFORE any agent reads upstream
   GATE (non-injectable tooling):
     - gitleaks / detect-secrets over the whole subtree (creds, keys, tokens)
     - command + URL EXTRACTOR: pull every shell command & URL out of scripts/prose
       for explicit human view in the PR
     - frontmatter parse + size / file-count ceiling (anti-bloat tripwire)
   ADVISORY (defense-in-depth, NOT the gate):  (Opus, claude -p, JSON verdict)
     - LLM scan for natural-language injection / "ignore prior rules" / subtle exfil
     - prompt hardened: input is untrusted DATA; treated as advisory signal only
   GATE FAIL -> QUARANTINE: do NOT adapt, skill stays pinned at OLD sha,
                open issue/PR with the suspicious diff + extracted cmds/URLs + verdict.

3. RECONCILE drift (if SKILL.md was hand-edited)            (Opus, claude -p)
   drift = diff(SKILL.md, .generated/SKILL.md)
   If drift non-empty AND upstream changed:
     agent turns the drift into proposed adaptation.md additions, folds them in.

4. ADAPT — PATCH-based                                      (Opus, claude -p, temp 0)
   Update upstream/ mirror to new files.
   Apply the SEMANTIC EQUIVALENT of the upstream delta to existing SKILL.md
     (full regen only on onboarding / `regen --force`).
   Write new .generated/SKILL.md snapshot.
   Bump synced_sha in sources.yaml.

5. VERIFY hand-edit preservation (only if fold-back ran)    (Opus, claude -p)
   Check the original hand-edit intent is present in the new output.
     present     -> normal PR
     not present -> PR labeled "⚠ hand-edit may not be preserved" + quote the edit

6. VALIDATE — DETERMINISTIC, BLOCKS PR
   - YAML frontmatter parses; `name` == directory; `description` non-empty
   - byte/size ceiling; referenced scripts/links exist
   FAIL -> no PR; open an issue.   PASS -> open PR.

7. PR — one branch + PR PER changed skill                   (gh)
   branch: skillsync/<skill-name>
   PR body: RAW upstream diff + extracted commands/URLs (shown alongside adapted output),
            scanner verdict, sha bump, adaptation.md changes, any ⚠ flags.
   You approve/merge each independently.
```

### First-time skill onboarding
`skillsync add <repo> <path>` → fetches upstream, runs the security gate, then an agent
**drafts** `adaptation.md` (reading `profile.md`, baking it in) and **fully generates** the
first `SKILL.md` — all in the onboarding PR. You refine the draft and regenerate.

---

## Consumption

Personal use activates selected top-level skill sets in the shared Agent Skills dir:
```
skillsync link --skill-set documents --skill-set engineering --skill-set meta
# ln -s skills/<set> -> ~/.agents/skills/<set>
```
Re-run with the desired selection to remove stale repository-owned category links. No
plugin/marketplace manifest (can be added later if sharing is ever wanted).

---

## CLI surface
```
skillsync add <repo> <skill-path>   # onboard a new upstream skill (draft adaptation + full gen)
skillsync sync [--skill <name>]     # detect -> gate -> reconcile -> patch -> verify -> validate -> PR
skillsync regen <name> [--force]    # regenerate SKILL.md (--force = full rewrite)
skillsync reprofile                 # re-bake current profile.md into every adaptation.md (reviewed PR)
skillsync link --skill-set <name>   # activate a selected set in ~/.agents/skills
skillsync status                    # show drift + pending upstream changes
```

---

## Phasing
- **Phase 1 (now):** local Python CLI, `claude -p`, `gh` PRs. No new secrets; uses CC quota.
- **Phase 2 (optional, later):** thin GitHub Actions cron wrapper calling the same CLI
  (would require an `ANTHROPIC_API_KEY` secret + pay-per-token API billing).

---

## Hardening decisions (from adversarial review)
1. **Patch-based generation by default** — preserves the diff-review the committed SKILL.md exists for.
2. **Deterministic security gate** (gitleaks + cmd/URL extractor + size/frontmatter); LLM scan is advisory only; raw upstream diff always shown in PR so adaptation can't launder threats.
3. **Blocking `validate` stage** — guarantees a loadable skill before any PR opens.
4. **Post-fold-back verification** — flags when a hand-edit may not have survived regeneration.
5. **Honest cost framing** — `$0 API`, consumes CC subscription quota.
6. **`skillsync reprofile`** — propagation lever for stack/tone changes across self-contained adaptation.md files.
7. **History-rewrite handling** — unreachable `synced_sha` → safe re-onboard + loud flag; `ref` = what to fetch, `synced_sha` = last-seen.
8. **Whole-subtree mirror** — the scan's actual security surface; unreferenced new files are not a blind spot.

---

## Open implementation details to settle during build
- Exact `claude -p` invocation flags + JSON schema for the advisory scanner verdict.
- Which deterministic tools to vendor (gitleaks vs detect-secrets; the command/URL extractor).
- `gh` auth assumption (your existing `gh` login).
