"""Tests for the LLM port: `FakeLLM` scripting and `ClaudeCli` argv/JSON handling.

`FakeLLM` returns deterministic scripted responses keyed by a prompt substring and
records every call. `ClaudeCli` is exercised with an injected fake subprocess
runner — no test ever invokes the real `claude` executable.
"""

import json
import subprocess

import pytest

from skillsync.ports.llm import LLMError, LLMPort, LLMResult
from skillsync.ports.llm_claude import ClaudeCli
from skillsync.testing.fakes import FakeLLM

# A minimal JSON schema reused across the schema-validation tests.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "safe": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["safe", "reason"],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------- #
# FakeLLM
# --------------------------------------------------------------------------- #


def test_fake_satisfies_protocol() -> None:
    """`FakeLLM` is a structural `LLMPort`."""
    assert isinstance(FakeLLM(), LLMPort)


def test_fake_routes_by_prompt_substring() -> None:
    """A scripted response is returned for the matching prompt substring."""
    fake = FakeLLM(
        {
            "scan this": LLMResult(text="all clear", json=None),
            "adapt that": LLMResult(text="patched", json=None),
        }
    )

    assert fake.complete(
        "please scan this diff", schema=None, model="opus", temperature=0.0
    ).text == "all clear"
    assert fake.complete(
        "now adapt that skill", schema=None, model="opus", temperature=0.0
    ).text == "patched"


def test_fake_unmatched_prompt_raises() -> None:
    """A prompt that matches no scripted key surfaces as an LLMError."""
    fake = FakeLLM({"scan this": LLMResult(text="ok", json=None)})

    with pytest.raises(LLMError):
        fake.complete("totally different request", schema=None, model="opus", temperature=0.0)


def test_fake_records_each_call() -> None:
    """Every call's prompt, model, and temperature is recorded in order."""
    fake = FakeLLM({"hi": LLMResult(text="hello", json=None)})

    fake.complete("hi there", schema=None, model="opus", temperature=0.0)
    fake.complete("hi again", schema=None, model="sonnet", temperature=0.7)

    assert [(c.prompt, c.model, c.temperature) for c in fake.calls] == [
        ("hi there", "opus", 0.0),
        ("hi again", "sonnet", 0.7),
    ]


def test_fake_schema_validation_passes_for_valid_json() -> None:
    """When a scripted JSON payload satisfies the schema, it is returned."""
    fake = FakeLLM(
        {"verdict": LLMResult(text="{}", json={"safe": True, "reason": "clean"})}
    )

    result = fake.complete(
        "give me a verdict", schema=VERDICT_SCHEMA, model="opus", temperature=0.0
    )

    assert result.json == {"safe": True, "reason": "clean"}


def test_fake_schema_validation_fails_for_invalid_json() -> None:
    """A scripted payload that violates the schema raises LLMError."""
    fake = FakeLLM(
        {"verdict": LLMResult(text="{}", json={"safe": "not-a-bool"})}
    )

    with pytest.raises(LLMError):
        fake.complete(
            "give me a verdict", schema=VERDICT_SCHEMA, model="opus", temperature=0.0
        )


# --------------------------------------------------------------------------- #
# ClaudeCli — argv construction & JSON parsing (injected fake runner)
# --------------------------------------------------------------------------- #


def _envelope(result_text: str, *, is_error: bool = False) -> str:
    """Build a `claude -p --output-format json` stdout envelope."""
    return json.dumps(
        {"type": "result", "subtype": "success", "is_error": is_error, "result": result_text}
    )


class _RecordingRunner:
    """A fake subprocess runner that records argv and returns scripted stdout."""

    def __init__(self, stdouts: list[str], returncode: int = 0) -> None:
        self.stdouts = list(stdouts)
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        stdout = self.stdouts.pop(0) if self.stdouts else ""
        return subprocess.CompletedProcess(argv, self.returncode, stdout=stdout, stderr="")


def test_claude_argv_includes_prompt_and_json_format() -> None:
    """argv carries `-p <prompt>`, `--output-format json`, and the model flag."""
    runner = _RecordingRunner([_envelope("hello")])
    cli = ClaudeCli(runner=runner)

    result = cli.complete("hi", schema=None, model="opus", temperature=0.0)

    argv = runner.calls[0]
    assert argv[0] == "claude"
    assert "-p" in argv
    assert argv[argv.index("-p") + 1] == "hi"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "opus"
    assert result.text == "hello"
    assert result.json is None


def test_claude_uses_custom_command_prefix() -> None:
    """A custom `command` prefix wraps the prompt/flags instead of bare `claude`."""
    runner = _RecordingRunner([_envelope("hello")])
    cli = ClaudeCli(runner=runner, command=["zsh", "-ic", 'claude "$@"', "_"])

    cli.complete("hi", schema=None, model="opus", temperature=0.0)

    argv = runner.calls[0]
    assert argv[:4] == ["zsh", "-ic", 'claude "$@"', "_"]
    # The skillsync arguments are appended after the prefix, prompt intact as one arg.
    assert argv[4:6] == ["-p", "hi"]
    assert argv[argv.index("--output-format") + 1] == "json"


def test_claude_omits_model_flag_when_model_blank() -> None:
    """No `--model` flag is added when the model is empty."""
    runner = _RecordingRunner([_envelope("hello")])
    cli = ClaudeCli(runner=runner)

    cli.complete("hi", schema=None, model="", temperature=0.0)

    assert "--model" not in runner.calls[0]


def test_claude_parses_and_validates_schema_json() -> None:
    """With a schema, the result text is parsed as JSON and validated."""
    payload = json.dumps({"safe": True, "reason": "clean"})
    runner = _RecordingRunner([_envelope(payload)])
    cli = ClaudeCli(runner=runner)

    result = cli.complete(
        "scan", schema=VERDICT_SCHEMA, model="opus", temperature=0.0
    )

    assert result.json == {"safe": True, "reason": "clean"}


def test_claude_retries_once_then_succeeds_on_bad_json() -> None:
    """A first unparseable response is retried once; the second valid one wins."""
    good = json.dumps({"safe": False, "reason": "leak"})
    runner = _RecordingRunner([_envelope("not json at all"), _envelope(good)])
    cli = ClaudeCli(runner=runner)

    result = cli.complete(
        "scan", schema=VERDICT_SCHEMA, model="opus", temperature=0.0
    )

    assert result.json == {"safe": False, "reason": "leak"}
    assert len(runner.calls) == 2


def test_claude_raises_after_retry_exhausted() -> None:
    """Two consecutive schema failures raise LLMError after the single retry."""
    runner = _RecordingRunner([_envelope("garbage"), _envelope("still garbage")])
    cli = ClaudeCli(runner=runner)

    with pytest.raises(LLMError):
        cli.complete("scan", schema=VERDICT_SCHEMA, model="opus", temperature=0.0)
    assert len(runner.calls) == 2


def test_claude_raises_on_schema_violation_after_retry() -> None:
    """Valid JSON that violates the schema is retried, then raises LLMError."""
    bad = json.dumps({"safe": "nope"})
    runner = _RecordingRunner([_envelope(bad), _envelope(bad)])
    cli = ClaudeCli(runner=runner)

    with pytest.raises(LLMError):
        cli.complete("scan", schema=VERDICT_SCHEMA, model="opus", temperature=0.0)


def test_claude_raises_on_nonzero_exit() -> None:
    """A non-zero subprocess exit surfaces as LLMError."""
    runner = _RecordingRunner([""], returncode=1)
    cli = ClaudeCli(runner=runner)

    with pytest.raises(LLMError):
        cli.complete("hi", schema=None, model="opus", temperature=0.0)


def test_claude_raises_on_error_envelope() -> None:
    """An `is_error` envelope surfaces as LLMError."""
    runner = _RecordingRunner([_envelope("boom", is_error=True)])
    cli = ClaudeCli(runner=runner)

    with pytest.raises(LLMError):
        cli.complete("hi", schema=None, model="opus", temperature=0.0)
