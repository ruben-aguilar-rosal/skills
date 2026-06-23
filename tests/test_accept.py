"""Tests for the ACCEPT command (`skillsync.commands.accept`).

`run_accept` records that the author has reviewed and accepted a skill's blocking
security findings and/or its validation failure, by writing `accept_findings` /
`accept_invalid` onto the matching pin in `sources.yaml`. It is deterministic,
filesystem-only, and idempotent; re-running `add`/`sync` then ships the skill.
"""

from pathlib import Path

import pytest

from skillsync.commands.accept import AcceptError, run_accept
from skillsync.config import Config, SkillPin, Source, load_config, save_config


def _write_config(tmp_path: Path, pin: SkillPin) -> Path:
    """Persist a one-source config with `pin` and return the sources.yaml path."""
    path = tmp_path / "sources.yaml"
    save_config(
        Config(sources=[Source(repo="owner/repo", ref="main", skills=[pin])]), path
    )
    return path


def test_accept_findings_appends_rule_ids(tmp_path: Path) -> None:
    """`run_accept` records the accepted rule IDs on the matching pin."""
    path = _write_config(tmp_path, SkillPin(path="skills/jira", synced_sha="x"))

    run_accept(
        load_config(path), path, "owner/repo", "skills/jira", findings=["P1", "SC2"]
    )

    assert load_config(path).sources[0].skills[0].accept_findings == ["P1", "SC2"]


def test_accept_findings_is_idempotent_and_merges(tmp_path: Path) -> None:
    """Re-accepting merges new rule IDs without duplicating existing ones."""
    path = _write_config(
        tmp_path, SkillPin(path="skills/jira", synced_sha="x", accept_findings=["P1"])
    )

    run_accept(load_config(path), path, "owner/repo", "skills/jira", findings=["P1", "TM2"])

    assert load_config(path).sources[0].skills[0].accept_findings == ["P1", "TM2"]


def test_accept_invalid_sets_flag(tmp_path: Path) -> None:
    """`invalid=True` records acceptance of the validation failure."""
    path = _write_config(tmp_path, SkillPin(path="skills/skill-creator", synced_sha="x"))

    run_accept(load_config(path), path, "owner/repo", "skills/skill-creator", invalid=True)

    assert load_config(path).sources[0].skills[0].accept_invalid is True


def test_accept_both_at_once(tmp_path: Path) -> None:
    """Findings and invalid can be accepted in a single call."""
    path = _write_config(tmp_path, SkillPin(path="skills/jira", synced_sha="x"))

    run_accept(
        load_config(path), path, "owner/repo", "skills/jira",
        findings=["P1"], invalid=True,
    )

    pin = load_config(path).sources[0].skills[0]
    assert pin.accept_findings == ["P1"]
    assert pin.accept_invalid is True


def test_accept_unknown_pin_raises(tmp_path: Path) -> None:
    """Accepting for a path with no matching pin raises a typed error."""
    path = _write_config(tmp_path, SkillPin(path="skills/jira", synced_sha="x"))

    with pytest.raises(AcceptError, match="skills/other"):
        run_accept(load_config(path), path, "owner/repo", "skills/other", findings=["P1"])


def test_accept_nothing_to_do_raises(tmp_path: Path) -> None:
    """A call that accepts neither findings nor invalid is a usage error."""
    path = _write_config(tmp_path, SkillPin(path="skills/jira", synced_sha="x"))

    with pytest.raises(AcceptError, match="nothing"):
        run_accept(load_config(path), path, "owner/repo", "skills/jira")
