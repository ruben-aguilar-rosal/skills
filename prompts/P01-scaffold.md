# Step P01 — Project scaffold & CLI skeleton

> Open a **fresh session** at the repo root and paste everything below.

## Standing context (read first)
- Design: `PLAN.md`. Build plan & conventions: `BLUEPRINT.md`. This is step 1 of 16.
- Work test-first. Functional core / imperative shell: side effects (git, fs, subprocess)
  behind injected ports. No network, no real `claude`/`gh` in tests — use fakes.
- Python 3.12+, `pytest`, type hints + docstrings (`python-standards`).
- End the step by integrating the new code into the CLI; leave nothing orphaned.

## Prompt
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

TDD: write `tests/test_cli.py` first (it will fail to import), then implement until green.
Show the test run output. Do not add any other commands yet.
```

## Verify & commit
- `pytest -q` is green; `skillsync version` runs.
- Commit: `feat(p01): project scaffold + CLI skeleton`. Then start P02 in a new session.
