"""ACCEPT command — record reviewed-and-accepted security findings / invalid skills.

`run_accept` is the override lever for the blocking gate and validate stage. When a
skill quarantines (CRITICAL/HIGH SkillSpector findings) or fails validation, the run
files an issue and stops; there is deliberately no blanket bypass. Instead, after
reviewing the issue, the author records a NARROW acceptance on the pin in
`sources.yaml`:

- `--findings P1,SC2` appends those SkillSpector rule IDs to `accept_findings`, so
  those specific findings stop blocking — a freshly-introduced finding still does.
- `--invalid` sets `accept_invalid`, so a validation failure ships a flagged PR
  instead of an issue.

It is deterministic and filesystem-only (no git/LLM/gh) and idempotent. It only
edits the config; the author re-runs `add`/`sync` to ship the now-accepted skill.
"""

from pathlib import Path

from skillsync.config import Config, SkillPin, save_config


class AcceptError(Exception):
    """Raised when the acceptance can't be recorded (no matching pin, or a no-op call)."""


def run_accept(
    config: Config,
    config_path: Path,
    repo: str,
    skill_path: str,
    *,
    findings: list[str] | None = None,
    invalid: bool = False,
) -> None:
    """Record accepted `findings` and/or `invalid` on `repo`/`skill_path`'s pin.

    Merges `findings` into the pin's `accept_findings` (de-duplicated, order
    preserved) and, when `invalid` is true, sets `accept_invalid`. Persists the
    config. Raises `AcceptError` if no pin matches `repo`/`skill_path`, or if the
    call would accept nothing (neither findings nor invalid).
    """
    findings = findings or []
    if not findings and not invalid:
        raise AcceptError(
            "nothing to accept: pass --findings <ids> and/or --invalid"
        )

    pin = _find_pin(config, repo, skill_path)
    if pin is None:
        raise AcceptError(
            f"no pin for {skill_path!r} under repo {repo!r} in the config; "
            "onboard it (skillsync add) before accepting findings for it"
        )

    for rule_id in findings:
        if rule_id not in pin.accept_findings:
            pin.accept_findings.append(rule_id)
    if invalid:
        pin.accept_invalid = True

    save_config(config, config_path)


def _find_pin(config: Config, repo: str, skill_path: str) -> SkillPin | None:
    """Return the pin for `repo`/`skill_path`, or None if no source/pin matches."""
    normalized = skill_path.rstrip("/")
    for source in config.sources:
        if source.repo != repo:
            continue
        for pin in source.skills:
            if pin.path.rstrip("/") == normalized:
                return pin
    return None
