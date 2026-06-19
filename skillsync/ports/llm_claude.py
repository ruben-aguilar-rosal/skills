"""Real `LLMPort` implementation invoking headless `claude -p`.

The subprocess is always launched from an args list with `shell=False` and a
timeout — the prompt is passed as a discrete argv element, never interpolated
into a shell string. Output is requested as `--output-format json`; `claude`
wraps the model's answer in a result envelope whose `result` field carries the
text. When a schema is requested, that text is parsed as JSON and validated; a
single retry is attempted before raising `LLMError`.
"""

import json
import subprocess
from collections.abc import Callable

import jsonschema

from skillsync.ports.llm import LLMError, LLMResult

# Default model for agentic steps (PLAN.md: Opus for every agentic step).
_DEFAULT_MODEL = "opus"

_DEFAULT_TIMEOUT = 120

# The default command prefix the prompt/flags are appended to. A single bare
# `claude` resolves on PATH. It is overridable (see `make_llm`) so installs where
# `claude` is a shell function — needing its env set up first — can route through
# an interactive shell, e.g. ["zsh", "-ic", 'claude "$@"', "_"], which keeps the
# prompt a discrete argv element (no shell interpolation, no injection).
_DEFAULT_COMMAND = ["claude"]

# Appended to the prompt when a schema is requested, to coerce JSON-only output.
_JSON_INSTRUCTION = (
    "\n\nRespond with a single JSON object only — no prose, no markdown fences, "
    "no commentary. The object must conform to this JSON schema:\n"
)

# A subprocess runner: takes argv + timeout, returns the completed process. The
# default shells out to `claude`; tests inject a fake to avoid the real CLI.
Runner = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]


def _default_runner(argv: list[str], timeout: int) -> "subprocess.CompletedProcess[str]":
    """Run `argv` with `shell=False`, capturing text output under a timeout."""
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class ClaudeCli:
    """`LLMPort` backed by the local headless `claude -p` CLI."""

    def __init__(
        self,
        runner: Runner | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        command: list[str] | None = None,
    ) -> None:
        """Configure the subprocess `runner`, per-call timeout, and command prefix.

        `command` is the argv prefix the `-p <prompt>`/`--output-format`/`--model`
        arguments are appended to; it defaults to `["claude"]`. Override it to route
        through an interactive shell when `claude` is a shell function rather than a
        bare binary on PATH.
        """
        self._runner = runner or _default_runner
        self._timeout = timeout
        self._command = list(command) if command else list(_DEFAULT_COMMAND)

    def complete(
        self,
        prompt: str,
        *,
        schema: dict | None,
        model: str = _DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> LLMResult:
        """Complete `prompt` via `claude -p`, optionally validating JSON output."""
        full_prompt = prompt
        if schema is not None:
            full_prompt = f"{prompt}{_JSON_INSTRUCTION}{json.dumps(schema)}"

        # One initial attempt plus, for schema'd calls, a single retry.
        attempts = 2 if schema is not None else 1
        last_error: str = ""
        for _ in range(attempts):
            text = self._invoke(full_prompt, model=model, temperature=temperature)
            if schema is None:
                return LLMResult(text=text, json=None)
            try:
                parsed = json.loads(text)
                jsonschema.validate(parsed, schema)
            except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
                last_error = str(exc)
                continue
            return LLMResult(text=text, json=parsed)

        raise LLMError(
            f"claude output failed schema validation after {attempts} attempts: {last_error}"
        )

    def _invoke(self, prompt: str, *, model: str, temperature: float) -> str:
        """Run `claude -p` once and return the result text from its JSON envelope."""
        argv = [*self._command, "-p", prompt, "--output-format", "json"]
        if model:
            argv += ["--model", model]

        try:
            completed = self._runner(argv, self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise LLMError(f"claude timed out after {self._timeout}s") from exc
        except OSError as exc:
            raise LLMError(f"claude could not be executed: {exc}") from exc

        if completed.returncode != 0:
            raise LLMError(
                f"claude failed ({completed.returncode}): {completed.stderr.strip()}"
            )

        return self._unwrap(completed.stdout)

    @staticmethod
    def _unwrap(stdout: str) -> str:
        """Extract the `result` text from the `--output-format json` envelope."""
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise LLMError(f"claude returned non-JSON envelope: {stdout!r}") from exc

        if envelope.get("is_error"):
            raise LLMError(f"claude reported an error: {envelope.get('result')!r}")

        result = envelope.get("result")
        if not isinstance(result, str):
            raise LLMError(f"claude envelope missing string `result`: {envelope!r}")
        return result
