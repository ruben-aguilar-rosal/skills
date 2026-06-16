# skillsync — Implementation Blueprint

Build plan for the `skillsync` CLI described in [`PLAN.md`](./PLAN.md). Test-driven,
incremental. Each step is independently testable and ends by wiring into what exists. No
orphaned code.

## Conventions for the whole build

- **Language/runtime:** Python 3.12+, packaged with `pyproject.toml` (PEP 621). Follow the
  `python-standards` skill (type hints, docstrings, naming).
- **Testing:** `pytest`. Pure logic is unit-tested. Anything touching git, the filesystem,
  `claude -p`, or `gh` is behind a thin **port** (protocol/interface) so tests inject a fake.
  No test hits the network or the real Claude/gh.
- **Architecture:** functional core, imperative shell. Stages are pure-ish functions over
  data objects; side effects (git, fs, subprocess) live in injected adapters.
- **CLI:** `typer` (or `argparse` if dependencies must stay minimal). Commands are thin
  wrappers that assemble adapters and call the core.
- **Errors:** stages return structured results (dataclasses), never `sys.exit` from the core.
- **Determinism:** the deterministic stages (detect, security gate, validate) contain zero
  LLM calls and are fully reproducible in tests.

## Data model (shared vocabulary)

- `Source` — one upstream repo: `repo`, `ref`, list of `SkillPin`.
- `SkillPin` — `path`, `synced_sha`, `hold`.
- `SkillLayout` — resolves the on-disk paths for a skill folder: `upstream/`,
  `adaptation.md`, `SKILL.md`, `.generated/SKILL.md`.
- `ChangeSet` — result of detect: per skill, `kind` ∈ {none, changed, re-onboard}, the diff,
  changed file list, old/new SHA.
- `GateResult` — `passed: bool`, `findings: [Finding]`, extracted `commands`, `urls`.
- `ValidationResult` — `passed: bool`, `errors: [str]`.
- `AdaptResult` — new `SKILL.md` text, snapshot text, `foldback` (optional), `flags: [str]`.
- `SkillPR` — branch name, title, body, files to commit.

## Pipeline (from PLAN.md)

```
detect → security gate (deterministic) → reconcile drift → adapt (patch)
       → verify preservation → validate (deterministic) → PR
```

---

## Chunking (Phase → Steps)

### Phase 0 — Foundations
- **P1** Project scaffold + CLI skeleton + test harness
- **P2** Config layer: `sources.yaml` model + load/save, `profile.md` reader

### Phase 1 — Deterministic core (no LLM)
- **P3** Git I/O port: mirror clone, fetch, subtree diff, ancestor check
- **P4** `SkillLayout` path model + skill-folder read/write helpers
- **P5** Detect stage: per-skill change detection + history-rewrite → re-onboard
- **P6** Security gate: secret scan + command/URL extractor + frontmatter/size limits
- **P7** Validate stage: frontmatter schema, name==dir, size ceiling, referenced files exist

### Phase 2 — Agentic core
- **P8** LLM client port: `claude -p` subprocess, JSON-schema'd output, model/temp control
- **P9** Advisory LLM scan (defense-in-depth, non-blocking)
- **P10** Adapt stage: patch-based generation + `.generated/` snapshot write
- **P11** Drift detection + fold-back into `adaptation.md` + preservation verify

### Phase 3 — Output & orchestration
- **P12** PR builder: branch + commit + PR body assembly via `gh` port
- **P13** `sync` command: wire the full pipeline end-to-end
- **P14** `add` (onboarding) command: full-generation path
- **P15** `regen` + `reprofile` commands (reuse adapt/LLM)
- **P16** `link` + `status` commands (deterministic, filesystem only)

Each step's prompt lives in `PROMPTS.md`.
