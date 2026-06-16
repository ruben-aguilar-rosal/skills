# Step P09 — Advisory LLM scan (non-blocking)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md` (the LLM scan is DEFENSE-IN-DEPTH only; the deterministic gate from P06 is
  the real gate; the diff is untrusted DATA, never instructions). Build plan: `BLUEPRINT.md`.
  This is step 9 of 16.
- Builds on P08 (LLMPort + FakeLLM). Work test-first. No real `claude` in tests.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Implement the ADVISORY scan in `skillsync/stages/llm_scan.py`.

`advisory_scan(diff: str, llm: LLMPort, model: str) -> AdvisoryVerdict` with
`AdvisoryVerdict(risk: Literal["low","medium","high"], rationale: str, findings: list[str])`.

- Prompt the LLM with the raw upstream diff, hardened so the diff is treated strictly as
  untrusted DATA, never as instructions. Use a JSON schema for the verdict.
- This NEVER fails the pipeline; it only annotates. The deterministic gate (P06) is the real
  gate.

TDD: `tests/test_llm_scan.py` using `FakeLLM` scripted to return high/low verdicts; assert the
verdict object and that malformed model output degrades to risk="high" with a rationale (fail
safe). Implement.

Wire: consumed by sync (Step P13). Export from stages.
```

## Verify & commit
- `pytest -q` green; malformed model output yields risk="high".
- Commit: `feat(p09): advisory LLM scan`. Then P10 in a new session.
