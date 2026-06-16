# Step P02 — Config layer (sources.yaml + profile.md)

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md`. Build plan & conventions: `BLUEPRINT.md`. This is step 2 of 16.
- Builds on P01 (scaffold + typer CLI, green). Work test-first.
- Functional core / imperative shell; no print in the core (return-and-log). No network in tests.
- Python 3.12+, `pytest`, type hints + docstrings.

## Prompt
```text
Add the configuration layer to `skillsync`.

Data model (dataclasses in `skillsync/config.py`):
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

Wire: add a `skillsync config-check` command that loads `sources.yaml` from the repo root and
prints the count of sources/skills, so the layer is reachable from the CLI.
```

## Verify & commit
- `pytest -q` green; `skillsync config-check` runs against a sample `sources.yaml`.
- Commit: `feat(p02): config layer (sources.yaml + profile.md)`. Then P03 in a new session.
