"""Tests for the skillsync configuration layer."""

from pathlib import Path

import pytest

from skillsync.config import (
    Config,
    ConfigError,
    SkillPin,
    Source,
    load_config,
    load_profile,
    save_config,
)

SAMPLE_YAML = """\
sources:
  - repo: mattpocock/skills
    ref: main
    skills:
      - path: engineering/to-issues
        synced_sha: a1b2c3d
        hold: false
      - path: engineering/from-issues
        synced_sha: null
"""


def test_load_config_parses_sources_and_skills(tmp_path: Path) -> None:
    """`load_config` reads sources, refs, and skill pins from YAML."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(SAMPLE_YAML)

    config = load_config(config_path)

    assert len(config.sources) == 1
    source = config.sources[0]
    assert source.repo == "mattpocock/skills"
    assert source.ref == "main"
    assert len(source.skills) == 2
    assert source.skills[0] == SkillPin(
        path="engineering/to-issues", synced_sha="a1b2c3d", hold=False
    )


def test_load_config_applies_defaults(tmp_path: Path) -> None:
    """Missing `hold` defaults to False and missing `synced_sha` defaults to None."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(SAMPLE_YAML)

    pin = load_config(config_path).sources[0].skills[1]

    assert pin.path == "engineering/from-issues"
    assert pin.synced_sha is None
    assert pin.hold is False


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    """`load_config(save_config(c))` reproduces the original config."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path="a/one", synced_sha="deadbeef", hold=False),
                    SkillPin(path="b/two", synced_sha=None, hold=True),
                ],
            )
        ]
    )
    config_path = tmp_path / "sources.yaml"

    save_config(config, config_path)

    assert load_config(config_path) == config


def test_load_config_missing_file_raises_config_error(tmp_path: Path) -> None:
    """A missing `sources.yaml` raises a typed ConfigError with a helpful message."""
    missing = tmp_path / "nope.yaml"

    with pytest.raises(ConfigError, match=str(missing)):
        load_config(missing)


def test_load_config_collects_warning_for_unknown_keys(tmp_path: Path) -> None:
    """Unknown YAML keys are ignored but recorded as warnings (no print)."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    mystery: 1\n"
        "    skills:\n"
        "      - path: a/one\n"
        "        synced_sha: abc\n"
        "        bogus: true\n"
    )

    config = load_config(config_path)

    assert config.sources[0].repo == "owner/repo"
    assert any("mystery" in warning for warning in config.warnings)
    assert any("bogus" in warning for warning in config.warnings)


def test_load_profile_reads_file(tmp_path: Path) -> None:
    """`load_profile` returns the file contents when present."""
    profile_path = tmp_path / "profile.md"
    profile_path.write_text("# My profile\n")

    assert load_profile(profile_path) == "# My profile\n"


def test_load_profile_missing_returns_empty(tmp_path: Path) -> None:
    """`load_profile` returns an empty string when the file is absent."""
    assert load_profile(tmp_path / "absent.md") == ""
