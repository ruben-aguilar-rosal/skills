# Step P06 — Security gate (deterministic)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (the deterministic gate is the load-bearing security control; the LLM scan
  in P09 is only advisory). Build plan: `BLUEPRINT.md`. This is step 6 of 16.
- Builds on P05 (ChangeSet). Work test-first. Pure function over file contents — no LLM, no I/O.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement the deterministic SECURITY GATE in `skillsync/stages/gate.py`.

`run_gate(changeset: ChangeSet, files: dict[str,str]) -> GateResult` where
`GateResult(passed, findings: list[Finding], commands: list[str], urls: list[str])` and
`Finding(severity, kind, detail, file)`.

Checks (all deterministic, no LLM), build in this TDD order:
1. Size/frontmatter limits: each file <= configurable byte cap; SKILL.md frontmatter parses
   as YAML and has `name` + `description`. Violations -> findings; oversize -> fail.
2. Command extractor: scan shell/py files and fenced code blocks; extract candidate commands
   (curl/wget/bash/eval/base64/rm -rf/etc.) into `commands`. Extraction alone never fails the
   gate — it surfaces for human view — but a curated high-risk pattern list (e.g. `curl ...| sh`,
   reverse shells, secret-path reads) -> fail.
3. URL extractor: collect all http(s) URLs into `urls`.
4. Secret scan: regex set for common credential shapes (AWS keys, tokens, private keys). Any
   hit -> fail.

`passed = no failing finding`. Pure function over the file contents (caller supplies them).

TDD: `tests/test_gate.py` with fixtures: clean skill (pass), embedded `curl | sh` (fail +
command surfaced), AWS-key-looking string (fail), oversize file (fail), benign URLs (pass +
urls collected). Implement.

Wire: no command yet; this is consumed by the sync pipeline (Step P13). Export from the stages
package.
```

## Verify & commit
- `pytest -q` green; all gate fixtures behave as specified.
- Commit: `feat(p06): deterministic security gate`. Then P07 in a new session.
