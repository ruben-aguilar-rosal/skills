# skillsync — Code-Generation Prompts (TDD)

A sequence of prompts for a code-generation LLM. Each is self-contained, builds on the prior
step, is implemented test-first, and ends by wiring into the existing code. See
[`BLUEPRINT.md`](./BLUEPRINT.md) for the chunking rationale and [`PLAN.md`](./PLAN.md) for the
design. One task exists per prompt.

Global rules given to the generator for every prompt:
- Python 3.12+, `pytest`, type hints + docstrings (`python-standards`).
- Functional core / imperative shell: side effects (git, fs, subprocess) behind injected ports.
- Write the failing test(s) first, then the implementation, then show both green.
- No network, no real `claude`/`gh` in tests — use fakes.
- End each step by integrating the new code into the CLI or its caller; leave nothing orphaned.

---

## Prompt 1 — Project scaffold & CLI skeleton

```text
Create the Python project scaffold for a CLI tool named `skillsync` inside the existing repo
(package dir `skillsync/`). Use Python 3.12+, PEP 621 `pyproject.toml`, and `pytest`.

Requirements:
- `pyproject.toml` defining the package `skillsync`, a console-script entry point
  `skillsync = "skillsync.cli:app"`, and dev dependency `pytest`. Use `typer` for the CLI.
- `skillsync/__init__.py` exposing `__version__`.
- `skillsync/cli.py` with a `typer` app exposing one command: `version`, printing the version.
- `tests/test_cli.py` using typer's `CliRunner` to assert `skillsync version` exits 0 and
  prints the version string.
- A `README` note in the package is not needed; the repo README already exists.

TDD: write `tests/test_cli.py` first (it will fail to import), then implement until green.
Show the test run output. Do not add any other commands yet.
```

---

## Prompt 2 — Config layer (`sources.yaml` + `profile.md`)

```text
Add the configuration layer to `skillsync`.

Data model (use dataclasses in `skillsync/config.py`):
- `SkillPin(path: str, synced_sha: str | None, hold: bool = False)`
- `Source(repo: str, ref: str, skills: list[SkillPin])`
- `Config(sources: list[Source])`

Functions:
- `load_config(path: Path) -> Config` — parse `sources.yaml` (use `pyyaml`; add it as a dep).
- `save_config(config: Config, path: Path) -> None` — round-trip safe; stable key order.
- `load_profile(path: Path) -> str` — read `profile.md`; return "" if absent.

Rules:
- Missing `sources.yaml` -> raise a typed `ConfigError` with a helpful message.
- Unknown YAML keys -> ignored but a warning is collected (return-and-log pattern, no print
  in the core).

TDD: write `tests/test_config.py` covering load, save round-trip (load(save(c)) == c), missing
file, and `hold`/`synced_sha=None` defaults, using `tmp_path`. Then implement.

Wire: add a hidden/no-op `skillsync config-check` command that loads `sources.yaml` from the
repo root and prints the count of sources/skills, so the layer is reachable from the CLI.
```

---

## Prompt 3 — Git I/O port

```text
Add a git port that the deterministic stages will depend on, with a real implementation and a
fake for tests.

In `skillsync/ports/git.py` define a `GitPort` Protocol:
- `mirror(repo: str, ref: str) -> Path` — ensure a local bare/working mirror of `repo`,
  fetch `ref`, return the checkout path.
- `head_sha(repo_path: Path, ref: str) -> str`
- `is_ancestor(repo_path: Path, ancestor_sha: str, ref: str) -> bool`
- `diff_subtree(repo_path: Path, from_sha: str | None, ref: str, subtree: str) -> str`
  (unified diff limited to `subtree`; `from_sha=None` => full content as added).
- `list_subtree_files(repo_path: Path, ref: str, subtree: str) -> list[str]`

Provide `GitCli(GitPort)` in `skillsync/ports/git_cli.py` shelling out to `git` via
`subprocess.run` (no shell=True; args list). Provide `FakeGit(GitPort)` in
`skillsync/testing/fakes.py` backed by an in-memory dict of {sha: {path: content}} and a
linear history, enough to exercise ancestor/diff logic.

TDD: write `tests/test_git_cli.py` that initializes a real temp git repo (allowed — local
git, no network) with two commits touching a subtree, and asserts `diff_subtree`,
`is_ancestor`, `head_sha`. Also `tests/test_fake_git.py` asserting the fake matches the same
contract for the cases the stages need. Implement until green.

Do not wire into a CLI command yet — this is infrastructure consumed by Prompt 5.
```

---

## Prompt 4 — Skill layout & folder I/O

```text
Add `skillsync/layout.py` with a `SkillLayout` dataclass that, given the repo root and a skill
name, resolves: `root`, `upstream_dir`, `adaptation_path`, `skill_md_path`,
`generated_dir`, `generated_skill_md_path`. Skill name derives from the upstream subtree's
last path segment unless overridden.

Add pure helpers:
- `read_text(path) -> str | None`
- `write_text(path, text) -> None` (creates parent dirs)
- `mirror_files(files: dict[str, str], dest_dir: Path) -> None` (replaces dest contents)
- `read_skill(layout) -> SkillFiles` dataclass {adaptation, skill_md, generated_skill_md}
  (each `str | None`).

TDD: `tests/test_layout.py` using `tmp_path` to assert path resolution, mirror replaces stale
files, and read_skill returns None for absent files. Implement.

Wire: extend `skillsync status` (create it as a real command now) to list skill folders found
under `skills/` and whether each has adaptation/SKILL/generated present. Test the command with
CliRunner against a `tmp_path` repo.
```

---

## Prompt 5 — Detect stage

```text
Implement the deterministic DETECT stage in `skillsync/stages/detect.py`.

`detect(config: Config, git: GitPort, root: Path) -> list[ChangeSet]` where
`ChangeSet(skill_path, name, kind, from_sha, to_sha, diff, changed_files)` and
`kind ∈ {"none","changed","reonboard"}`.

Logic per non-held SkillPin:
- mirror+fetch the source ref; compute `to_sha = head_sha`.
- if `synced_sha is None` -> kind="reonboard" (new skill), diff = full content.
- elif not `is_ancestor(synced_sha, ref)` -> kind="reonboard" (history rewritten), flag it.
- else diff_subtree(synced_sha..ref, subtree); empty -> "none", else "changed".

TDD: `tests/test_detect.py` driven entirely by `FakeGit`, covering: no change, normal change,
new skill (None sha), and rewritten-history reonboard, plus `hold=True` skipped. Implement.

Wire: add `skillsync detect` command that prints a table of skill -> kind using the real
`GitCli`. CliRunner test can inject `FakeGit` via a dependency-injection seam (factory
function the command calls).
```

---

## Prompt 6 — Security gate (deterministic)

```text
Implement the deterministic SECURITY GATE in `skillsync/stages/gate.py`.

`run_gate(changeset: ChangeSet, files: dict[str,str]) -> GateResult` where
`GateResult(passed, findings: list[Finding], commands: list[str], urls: list[str])` and
`Finding(severity, kind, detail, file)`.

Checks (all deterministic, no LLM), build in this TDD order:
1. Size/frontmatter limits: each file <= configurable byte cap; SKILL.md frontmatter parses
   as YAML and has `name` + `description`. Violations -> findings; oversize -> fail.
2. Command extractor: scan shell/py files and fenced code blocks; extract candidate commands
   (lines invoking curl/wget/bash/eval/base64/rm -rf/etc.) into `commands`. Extraction never
   fails the gate by itself — it surfaces for human view — but a curated high-risk pattern
   list (e.g. `curl ... | sh`, reverse-shell, secret-path reads) -> fail.
3. URL extractor: collect all http(s) URLs into `urls`.
4. Secret scan: regex set for common credential shapes (AWS keys, tokens, private keys).
   Any hit -> fail.

`passed = no failing finding`. Pure function over the file contents (caller supplies them).

TDD: `tests/test_gate.py` with fixtures: clean skill (pass), embedded `curl | sh` (fail +
command surfaced), AWS-key-looking string (fail), oversize file (fail), benign URLs
(pass + urls collected). Implement.

Wire: no command yet; this is consumed by the sync pipeline (Prompt 13). Export from the
stages package.
```

---

## Prompt 7 — Validate stage (deterministic)

```text
Implement the deterministic VALIDATE stage in `skillsync/stages/validate.py`.

`validate_skill(layout: SkillLayout, skill_md_text: str, byte_cap: int) -> ValidationResult`
with `ValidationResult(passed, errors: list[str])`.

Checks:
- YAML frontmatter parses; has non-empty `name` and `description`.
- `name` equals the skill folder name.
- size <= byte_cap.
- every relative path referenced in the body (links, `scripts/x.sh`) exists under the skill
  folder.

TDD: `tests/test_validate.py` covering pass, missing description, name/dir mismatch, broken
relative reference, oversize. Implement.

Wire: add `skillsync validate <skill-name>` command that reads the on-disk SKILL.md and prints
PASS/errors, exit code 1 on failure. CliRunner test against a `tmp_path` skill folder.
```

---

## Prompt 8 — LLM client port (`claude -p`)

```text
Add the LLM port used by the agentic stages.

In `skillsync/ports/llm.py` define `LLMPort` Protocol:
- `complete(prompt: str, *, schema: dict | None, model: str, temperature: float) -> LLMResult`
  where `LLMResult(text: str, json: dict | None)`.

Provide `ClaudeCli(LLMPort)` in `skillsync/ports/llm_claude.py` that invokes
`claude -p <prompt> --output-format json [--model ...]` via `subprocess.run` (args list,
timeout, no shell). When `schema` is given, instruct JSON-only output and parse/validate it
against the schema (use `jsonschema`); retry once on parse failure, then raise `LLMError`.

Provide `FakeLLM(LLMPort)` in `skillsync/testing/fakes.py` that returns scripted responses
keyed by a substring of the prompt (so tests are deterministic).

TDD: `tests/test_llm_fake.py` asserting schema validation passes/fails correctly and scripted
routing works. For `ClaudeCli`, unit-test the argv construction and JSON parsing by injecting
a fake `subprocess` runner (do NOT call real claude). Implement.

Wire: infrastructure for Prompts 9–11.
```

---

## Prompt 9 — Advisory LLM scan (non-blocking)

```text
Implement the ADVISORY scan in `skillsync/stages/llm_scan.py`.

`advisory_scan(diff: str, llm: LLMPort, model: str) -> AdvisoryVerdict` with
`AdvisoryVerdict(risk: Literal["low","medium","high"], rationale: str, findings: list[str])`.

- Prompt the LLM with the raw upstream diff, hardened so the diff is treated strictly as
  untrusted DATA, never as instructions. Use a JSON schema for the verdict.
- This NEVER fails the pipeline; it only annotates. The deterministic gate (Prompt 6) is the
  real gate.

TDD: `tests/test_llm_scan.py` using `FakeLLM` scripted to return high/low verdicts; assert the
verdict object and that malformed model output degrades to risk="high" with a rationale (fail
safe). Implement.

Wire: consumed by sync (Prompt 13). Export from stages.
```

---

## Prompt 10 — Adapt stage (patch-based generation)

```text
Implement the ADAPT stage in `skillsync/stages/adapt.py`.

`adapt(layout, changeset, new_upstream_files, adaptation_text, llm, *, mode) -> AdaptResult`
with `mode ∈ {"patch","full"}` and
`AdaptResult(skill_md_text, snapshot_text, flags: list[str])`.

- mode="patch" (default for "changed"): prompt the LLM to apply the SEMANTIC EQUIVALENT of the
  upstream diff to the EXISTING SKILL.md, guided by adaptation.md, temperature 0. Output via
  JSON schema {skill_md: str}.
- mode="full" (onboarding / regen --force): generate SKILL.md from scratch from new upstream +
  adaptation.md.
- `snapshot_text` == the produced skill_md (to be written to `.generated/SKILL.md`).

TDD: `tests/test_adapt.py` with `FakeLLM`: patch mode returns edited text given a diff; full
mode returns generated text; assert snapshot equals output and temperature/model passed
through (assert on the fake's recorded call). Implement.

Wire: consumed by sync/add/regen. Export.
```

---

## Prompt 11 — Drift detection, fold-back & preservation verify

```text
Implement RECONCILE in `skillsync/stages/reconcile.py`, building on Prompts 4, 8, 10.

1. `detect_drift(skill_files: SkillFiles) -> str | None` — deterministic diff between
   on-disk SKILL.md and `.generated/SKILL.md`; None if equal/absent. (Unit-test with no LLM.)
2. `fold_back(adaptation_text, drift_diff, llm, model) -> FoldBackResult`
   {new_adaptation_text, summary} — LLM turns the hand-edit drift into additions to
   adaptation.md. JSON schema'd.
3. `verify_preserved(hand_edit_diff, new_skill_md, llm, model) -> PreservationVerdict`
   {preserved: bool, note: str} — after regen, confirm the hand-edit's intent survived; if
   not, surface a flag string.

TDD: `tests/test_reconcile.py`: drift diff math (deterministic), fold_back returns enriched
adaptation (FakeLLM), verify flags non-preserved edits. Implement.

Wire: these compose in sync (Prompt 13): if drift && changed -> fold_back -> adapt -> verify;
verify failure appends a "⚠ hand-edit may not be preserved" flag to AdaptResult.flags.
```

---

## Prompt 12 — PR builder (`gh` port)

```text
Add the PR output layer.

In `skillsync/ports/gh.py` define `GhPort` Protocol:
- `current_branch(root) -> str`
- `create_branch(root, name) -> None`
- `commit_all(root, message) -> None`
- `open_pr(root, branch, title, body, labels) -> str` (returns PR URL)

Provide `GhCli(GhPort)` (uses `git` + `gh pr create`, args list) and `FakeGh(GhPort)`
(records calls) in testing/fakes.

Add `skillsync/pr.py`:
- `build_pr(changeset, gate, advisory, adapt_result) -> SkillPR` assembling branch
  `skillsync/<name>`, title, and a body containing: the RAW upstream diff, extracted
  commands/URLs, advisory verdict, sha bump, adaptation.md change summary, and any flags.
- `publish_pr(skill_pr, gh: GhPort, root) -> str`.

TDD: `tests/test_pr.py` asserting body contains the raw diff + extracted commands + flags, and
that publish drives the GhPort calls in order (branch -> commit -> open_pr) via `FakeGh`.
Implement. Wire: consumed by sync.
```

---

## Prompt 13 — `sync` command (full pipeline wiring)

```text
Wire the end-to-end SYNC pipeline in `skillsync/pipeline.py` and expose `skillsync sync`.

`run_sync(config, root, *, git, llm, gh, only=None) -> list[SyncOutcome]` orchestrating, per
changed skill:
  detect -> if kind none: skip
         -> read new upstream files -> run_gate
            -> gate fail: QUARANTINE (no adapt; produce a quarantine SkillPR/issue with the
               suspicious diff + findings; skill stays pinned at old sha) and continue
            -> gate pass: advisory_scan (annotate)
               -> detect_drift; if drift && changed: fold_back (update adaptation.md)
               -> adapt(mode="patch" for changed / "full" for reonboard)
               -> if folded: verify_preserved -> maybe flag
               -> validate_skill: fail -> NO PR, emit issue; pass -> write upstream mirror,
                  SKILL.md, .generated snapshot, bump synced_sha in config
               -> build_pr -> publish_pr
Return structured outcomes (pr_url | quarantined | invalid | skipped) per skill.

`skillsync sync [--skill NAME]` assembles real GitCli/ClaudeCli/GhCli (Opus, temp 0) and calls
run_sync, printing a summary table.

TDD: `tests/test_pipeline.py` with FakeGit + FakeLLM + FakeGh covering the full matrix: clean
change -> PR; gate fail -> quarantine, sha unchanged; validate fail -> no PR + issue; drift +
change -> fold_back + verify path; reonboard -> full mode. Assert config sha is bumped ONLY on
successful PR. Implement until all green.
```

---

## Prompt 14 — `add` (onboarding) command

```text
Implement onboarding in `skillsync/commands/add.py` and `skillsync add <repo> <skill-path>`.

Flow:
- Append a new SkillPin (synced_sha=None, hold=False) under the matching/new Source in
  sources.yaml (save_config).
- Mirror upstream; run_gate; if fail -> quarantine and stop.
- DRAFT adaptation.md: an LLM call that reads `profile.md` (baked verbatim) + upstream SKILL.md
  and proposes a self-contained adaptation.md (JSON schema {adaptation_md}).
- adapt(mode="full") to produce the first SKILL.md; validate; write upstream mirror +
  adaptation.md + SKILL.md + .generated; set synced_sha to current head.
- build_pr/publish_pr with an "onboarding" label.

TDD: `tests/test_add.py` (FakeGit/LLM/Gh): asserts sources.yaml gains the pin, adaptation.md
drafted from profile, full-mode SKILL.md generated, validated, PR opened. Gate-fail path stops
before drafting. Implement, reusing Prompts 6/8/10/12/the config layer.
```

---

## Prompt 15 — `regen` and `reprofile` commands

```text
Add two LLM-backed maintenance commands, reusing the adapt stage and LLM port.

- `skillsync regen <name> [--force]` in `skillsync/commands/regen.py`: regenerate SKILL.md
  from the CURRENT on-disk upstream + adaptation.md. `--force` => mode="full"; without it,
  re-apply adaptation to current upstream (full is fine here since there's no new diff).
  Validate; write SKILL.md + .generated; open a PR (branch `skillsync/regen-<name>`).
- `skillsync reprofile` in `skillsync/commands/reprofile.py`: for every skill, an LLM pass
  re-bakes the current `profile.md` into each `adaptation.md` (JSON schema {adaptation_md}),
  then regenerates each SKILL.md, validates, and opens ONE PR per skill (reuse build_pr).

TDD: `tests/test_regen.py` and `tests/test_reprofile.py` with fakes: regen writes new SKILL.md
+ snapshot + PR; reprofile updates every adaptation.md and opens a PR per skill; validation
failure blocks that skill's PR. Implement.
```

---

## Prompt 16 — `link` and `status` (deterministic, filesystem only)

```text
Finish the CLI surface with two deterministic commands.

- `skillsync link [--dry-run]` in `skillsync/commands/link.py`: for each skill folder under
  `skills/`, create/refresh a symlink `~/.claude/skills/<name>` -> the skill folder. Use a
  configurable target dir (env override for tests). Skip + warn on conflicting non-symlink
  paths; `--dry-run` prints planned actions only.
- `skillsync status` (extend the earlier version): show, per skill, its synced_sha (short),
  whether upstream is ahead (via GitPort, optional/offline-tolerant), drift present?
  (SKILL.md vs .generated), and link state.

TDD: `tests/test_link.py` pointing the target dir at `tmp_path`: asserts symlink creation,
idempotent re-run, conflict skip, dry-run makes no changes. `tests/test_status.py` asserts the
status rows for a fixture repo with/without drift. Implement.

Final wiring check: ensure `skillsync --help` lists add, sync, regen, reprofile, link, status,
validate, detect; every command is reachable and covered by at least one CliRunner test.
```
