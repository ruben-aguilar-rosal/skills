# skills

A personal skill repository that mirrors upstream skill repos (e.g.
[`mattpocock/skills`](https://github.com/mattpocock/skills)), adapts them to my stack
(Jira, product discovery, AWS), security-scans every upstream change with deterministic
tooling, and opens a PR per changed skill for manual approval.

It's a mix of a **deterministic** pipeline (detect upstream changes, security gate, validate
output) and an **agentic** pipeline (adapt skills to my preferences, fold hand-edits back
into rules) driven by headless `claude -p`.

See [`PLAN.md`](./PLAN.md) for the full design and the hardening rationale.

## Layout

```
sources.yaml          # allowlist of upstream repos + skill paths + pinned SHAs
profile.md            # author-time context (stack/tone), baked into each adaptation.md
skills/<name>/        # one folder per skill (the dest dir is configurable, see below)
  .upstream/          # pristine mirror of the whole upstream subtree (never hand-edited)
  adaptation.md       # self-contained adaptation rules — PRESENT only for adapted skills
  SKILL.md            # the committed skill (vendored verbatim, or a patch-generated artifact)
  scripts/ …          # the skill's ship-along files, copied beside SKILL.md so the link works
  .generated/         # snapshot of last agent output (drift detection; adapted skills only)
skillsync/            # the Python CLI (see Architecture below)
```

**Adaptation is opt-in.** A skill is adapted by the LLM only when it has an `adaptation.md`.
Without one it is *vendored* — the upstream `SKILL.md` is mirrored verbatim. `sync` skips a
vendored skill entirely (it's frozen at its pinned sha) until you add an `adaptation.md` and
regen. This keeps quota spend to skills you've explicitly chosen to adapt.

## CLI

Install the package (editable) and the `skillsync` console script is on your path:

```sh
uv pip install -e .          # or: pip install -e .
```

| Command | What it does |
| ------- | ------------ |
| `skillsync add <repo> <skill-path> [--dest <dir>] [--no-pr]` | Onboard a new upstream skill. Default **vendors** it verbatim (no LLM); `--adapt` instead drafts `adaptation.md` from `profile.md` and full-generates `SKILL.md`. `--dest` sets where the skill folder is stored. `--no-pr` writes the skill to the working tree and opens no PR. |
| `skillsync sync [--skill <name>]` | Full pipeline per changed skill: detect → gate → reconcile → patch → verify → validate → PR. Then surfaces watched-folder discoveries (see below). |
| `skillsync sync --no-pr` | Local mode: adapt and write the artifacts to the working tree (and bump the pin) without opening a PR — inspect and play with them first. Pair with `--skip-advisory` / `--skip-reconcile` / `--skip-validate` to turn off optional stages. The security gate and adapt always run. |
| `skillsync discover [--open-issues]` | Preview new/removed skills in watched folders. Read-only by default (prints findings, opens nothing); `--open-issues` files the awareness issues like `sync` does. |
| `skillsync ignore <repo> <skill-path>` | Record a durable "no" for a discovered skill, so future syncs stop surfacing it. The rejection counterpart to `add`. |
| `skillsync regen <name> [--force]` | Regenerate one skill's `SKILL.md` from its on-disk `.upstream/` + `adaptation.md` (a full rebuild; never bumps `synced_sha`). |
| `skillsync reprofile` | Re-bake the current `profile.md` into every skill's `adaptation.md`, one PR per skill. |
| `skillsync link [--dry-run]` | Symlink each `skills/<name>/` into the native skills dir (`$SKILLSYNC_LINK_DIR`, else `~/.claude/skills`). Idempotent; skips non-symlink conflicts. |
| `skillsync status [--offline]` | Per skill: short `synced_sha`, upstream-ahead, `SKILL.md`-vs-`.generated` drift, and link state. |
| `skillsync validate <name>` | Validate a skill's on-disk `SKILL.md` (frontmatter, `name`==dir, size, referenced files). |
| `skillsync detect` | Detect upstream changes per skill and print a name → kind table. |

`skillsync --help` lists everything; `config-check` and `version` are utility commands.

### Watching a folder of skills

`sources.yaml` tracks one skill per pin — each with its own `synced_sha`, drift check, and
PR. To follow an upstream *folder* of skills without listing each by hand, add a `watch`
entry. On every `sync`, skillsync lists the skill folders under it and **surfaces** (never
auto-onboards) anything not already tracked:

```yaml
sources:
  - repo: mattpocock/skills
    ref: main
    watch:                        # folders to discover skills in
      - engineering/
    ignore:                       # discovered paths you've rejected (a durable "no")
      - engineering/experimental
    skills:                       # the tracked units — one pin per skill, as always
      - path: engineering/to-issues
        synced_sha: a1b2c3d
```

When a new skill appears under a watched folder, `sync` opens a single **awareness issue**
(idempotent — no duplicates across runs) telling you to either:

- **adopt** it — `skillsync add mattpocock/skills engineering/foo` (the normal onboarding:
  draft + full-generate + PR), or
- **reject** it — `skillsync ignore mattpocock/skills engineering/foo` (adds it to `ignore`).

A tracked skill that disappears upstream (deleted/renamed) is surfaced the same way. Adoption
is always explicit, so Opus quota is only ever spent on skills you've chosen.

To preview discoveries without filing anything, run `skillsync discover` — it prints the new
and removed skills and opens nothing (add `--open-issues` to file them on demand).

### Where skills are stored (`dest`)

By default a skill folder lands in `skills/<name>/`. Set `dest` to store a source's skills
elsewhere, with a per-skill `dest` override to group skills from different repos together. The
skill's own name is always appended to the `dest`:

```yaml
sources:
  - repo: Aily-Labs/aily-devops-tools
    ref: main
    dest: skills/aily                 # this source's skills → skills/aily/<name>/
    skills:
      - path: .claude/skills/aily-context
        synced_sha: a1b2c3d            # → skills/aily/aily-context/
      - path: .claude/skills/some-tool
        synced_sha: e4f5g6h
        dest: skills/tools             # per-skill override → skills/tools/some-tool/
```

`skillsync add <repo> <path> --dest skills/aily` records the `dest` on the new pin for you.
`status` and `link` read the configured `dest`, so skills are found wherever they live.

### Cost framing

`$0 API cost`, but agentic steps consume Claude Code **subscription quota** (they compete with
interactive usage). Patch-based generation keeps token use modest. Model: Opus for every
agentic step.

### Invoking `claude`

The agentic steps (`add`, `sync`, `regen`, `reprofile`) shell out to headless `claude -p`. By
default skillsync runs a bare `claude` on `PATH`. If your `claude` is a **shell function**
(e.g. it exports Bedrock/model env vars before calling the real binary), a non-shell
subprocess can't see it — so route the call through your shell:

```sh
export SKILLSYNC_CLAUDE_VIA_ZSH=1     # canned: zsh -ic 'claude "$@"' _
```

For a different shell or a custom invocation, set `SKILLSYNC_CLAUDE_CMD` to an explicit prefix
instead (shell-split; it takes precedence over the shorthand):

```sh
export SKILLSYNC_CLAUDE_CMD='bash -ic '\''claude "$@"'\'' _'
```

skillsync appends `-p <prompt> --output-format json --model …` to whichever it resolves; the
prompt stays a discrete argv element (no shell interpolation). The deterministic commands
(`detect`, `discover`, `status`, `link`, `validate`, `ignore`) never call `claude`.

## Consumption

Personal use via symlink into the native skills dir:

```sh
skillsync link    # skills/<name> -> ~/.claude/skills/<name>
```

## Architecture

**Functional core, imperative shell.** Stages are pure-ish functions over data objects;
all side effects (git, filesystem, `claude -p`, `gh`) live behind injected **ports** so the
core never shells out directly.

```
skillsync/
  cli.py            # Typer entry point — thin command wrappers that assemble ports + call the core
  config.py         # sources.yaml model (load/save) + profile.md reader
  layout.py         # SkillLayout path model + skill-folder read/write helpers
  pipeline.py       # `sync` orchestration: wires the full per-skill pipeline
  pr.py             # PR builder: branch + commit + PR-body assembly
  commands/         # add, regen, reprofile, link, status (orchestrators over stages + ports)
  stages/           # detect, gate, validate (deterministic); adapt, llm_scan, reconcile (agentic)
  ports/            # GitPort/GhPort/LLMPort protocols + their real CLI adapters
  testing/fakes.py  # in-memory FakeGit / FakeGh / FakeLLM backing the same port contracts
```

Invariants:

- The deterministic stages (`detect`, `gate`, `validate`) contain **zero** LLM calls and are
  fully reproducible.
- Stages return structured results (dataclasses); they never `sys.exit`.
- Every side effect goes through a port, so the whole pipeline runs against fakes in tests —
  no test touches the network or invokes real `claude`/`gh`.

## Pipeline (per `sync` run)

```
detect → security gate (deterministic) → reconcile drift → adapt (patch)
       → verify preservation → validate (deterministic) → PR
```

The committed `SKILL.md` is a build artifact but is also hand-editable: a hand-edit shows up
as drift (`SKILL.md` vs `.generated/SKILL.md`) and is folded back into `adaptation.md` so it
survives future generations. A failed security gate or validation opens an issue instead of a
PR. See [`PLAN.md`](./PLAN.md) for the full step-by-step.

## Development

Python 3.12+. Tests are `pytest`, test-first, and run entirely against the in-memory fakes:

```sh
uv pip install -e '.[dev]'
pytest -q
```

Agent workflow conventions (issue tracker, triage labels, domain docs) live in
[`docs/agents/`](./docs/agents/) and are summarized in [`CLAUDE.md`](./CLAUDE.md).
