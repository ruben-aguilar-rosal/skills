"""Tests for the IGNORE command (`skillsync.commands.ignore`).

`run_ignore` records a durable "no" for a discovered skill: it appends the path to
the matching source's `ignore` list in `sources.yaml` so discovery stops surfacing
it. It is deterministic, filesystem-only (no git/LLM/gh), and idempotent.
"""

from pathlib import Path

import pytest

from skillsync.commands.ignore import IgnoreError, run_ignore
from skillsync.config import Config, SkillPin, Source, load_config, save_config


def _write_config(tmp_path: Path, source: Source) -> Path:
    """Persist a one-source config and return the sources.yaml path."""
    path = tmp_path / "sources.yaml"
    save_config(Config(sources=[source]), path)
    return path


def test_ignore_appends_path_to_source(tmp_path: Path) -> None:
    """`run_ignore` adds the path to the matching source's ignore list and persists it."""
    path = _write_config(tmp_path, Source(repo="owner/repo", ref="main", skills=[]))

    run_ignore(load_config(path), path, "owner/repo", "eng/extra")

    assert load_config(path).sources[0].ignore == ["eng/extra"]


def test_ignore_is_idempotent(tmp_path: Path) -> None:
    """Ignoring the same path twice leaves a single entry."""
    path = _write_config(
        tmp_path, Source(repo="owner/repo", ref="main", skills=[], ignore=["eng/extra"])
    )

    run_ignore(load_config(path), path, "owner/repo", "eng/extra")

    assert load_config(path).sources[0].ignore == ["eng/extra"]


def test_ignore_unknown_repo_raises(tmp_path: Path) -> None:
    """Ignoring a path under an unconfigured repo raises a typed error."""
    path = _write_config(tmp_path, Source(repo="owner/repo", ref="main", skills=[]))

    with pytest.raises(IgnoreError, match="other/repo"):
        run_ignore(load_config(path), path, "other/repo", "eng/extra")


def test_ignore_normalizes_trailing_slash(tmp_path: Path) -> None:
    """A trailing slash on the path does not create a duplicate ignore entry."""
    path = _write_config(
        tmp_path, Source(repo="owner/repo", ref="main", skills=[], ignore=["eng/extra"])
    )

    run_ignore(load_config(path), path, "owner/repo", "eng/extra/")

    assert load_config(path).sources[0].ignore == ["eng/extra"]
