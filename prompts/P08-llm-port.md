# Step P08 — LLM client port (claude -p)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (agentic steps invoke headless `claude -p`; uses CC subscription quota,
  $0 API). Build plan: `BLUEPRINT.md`. This is step 8 of 16 — the first agentic step.
- Builds on P01–P07 (green). Work test-first. Subprocess via args list, `shell=False`,
  timeout. NEVER call real `claude` in tests — inject a fake subprocess runner / use FakeLLM.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add the LLM port used by the agentic stages.

In `skillsync/ports/llm.py` define `LLMPort` Protocol:
- `complete(prompt: str, *, schema: dict | None, model: str, temperature: float) -> LLMResult`
  where `LLMResult(text: str, json: dict | None)`.

Provide `ClaudeCli(LLMPort)` in `skillsync/ports/llm_claude.py` that invokes
`claude -p <prompt> --output-format json [--model ...]` via `subprocess.run` (args list,
timeout, no shell). When `schema` is given, instruct JSON-only output and parse/validate it
against the schema (use `jsonschema`); retry once on parse failure, then raise `LLMError`.

Provide `FakeLLM(LLMPort)` in `skillsync/testing/fakes.py` returning scripted responses keyed
by a substring of the prompt (deterministic). It records each call (prompt, model, temperature).

TDD: `tests/test_llm_fake.py` asserting schema validation passes/fails correctly and scripted
routing works. For `ClaudeCli`, unit-test the argv construction and JSON parsing by injecting a
fake `subprocess` runner (do NOT call real claude). Implement.

Wire: infrastructure for Steps P09–P11.
```

## Verify & commit
- `pytest -q` green; no test invokes real `claude`.
- Commit: `feat(p08): LLM client port (claude -p)`. Then P09 in a new session.
