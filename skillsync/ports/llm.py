"""LLM port consumed by the agentic stages.

`LLMPort` is the contract the advisory-scan / adapt / reconcile stages depend on.
A real implementation (`ClaudeCli`) shells out to headless `claude -p`; a `FakeLLM`
backs the same contract with scripted, deterministic responses for tests. Stages
depend only on this protocol, never on the `claude` executable.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class LLMError(Exception):
    """Raised when an LLM call fails (bad exit, timeout, unparseable/invalid output)."""


@dataclass(frozen=True)
class LLMResult:
    """The outcome of one completion: raw `text` plus optional parsed `json`.

    `json` is populated only when a schema was requested and the model's output
    parsed and validated against it; otherwise it is `None`.
    """

    text: str
    json: dict | None = None


@runtime_checkable
class LLMPort(Protocol):
    """A single-shot text/JSON completion the agentic stages need."""

    def complete(
        self,
        prompt: str,
        *,
        schema: dict | None,
        model: str,
        temperature: float,
    ) -> LLMResult:
        """Complete `prompt` with `model` at `temperature`.

        When `schema` is given, the implementation must coerce JSON-only output
        and validate it against the schema, raising `LLMError` if it cannot.
        """
        ...
