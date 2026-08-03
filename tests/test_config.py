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
    skill_dest,
    skill_name,
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


def test_load_config_parses_watch_and_ignore(tmp_path: Path) -> None:
    """`watch` and `ignore` folder lists are read onto the Source."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    watch:\n"
        "      - engineering/\n"
        "    ignore:\n"
        "      - engineering/experimental\n"
        "    skills:\n"
        "      - path: engineering/to-issues\n"
        "        synced_sha: abc\n"
    )

    source = load_config(config_path).sources[0]

    assert source.watch == ["engineering/"]
    assert source.ignore == ["engineering/experimental"]


def test_load_config_watch_and_ignore_default_empty(tmp_path: Path) -> None:
    """A source without watch/ignore keys gets empty lists, not None."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n  - repo: owner/repo\n    ref: main\n    skills: []\n"
    )

    source = load_config(config_path).sources[0]

    assert source.watch == []
    assert source.ignore == []


def test_save_then_load_round_trips_watch_and_ignore(tmp_path: Path) -> None:
    """watch/ignore survive a save → load round-trip."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[SkillPin(path="a/one", synced_sha="abc")],
                watch=["a/"],
                ignore=["a/skip"],
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


def test_load_config_parses_dest_on_source_and_skill(tmp_path: Path) -> None:
    """`dest` is read onto the Source (default) and the SkillPin (override)."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    dest: skills/aily\n"
        "    skills:\n"
        "      - path: a/one\n"
        "        synced_sha: abc\n"
        "      - path: a/two\n"
        "        synced_sha: def\n"
        "        dest: skills/aws\n"
    )

    source = load_config(config_path).sources[0]

    assert source.dest == "skills/aily"
    assert source.skills[0].dest is None
    assert source.skills[1].dest == "skills/aws"


def test_dest_defaults_none_and_round_trips(tmp_path: Path) -> None:
    """`dest` defaults to None and survives a save → load round-trip when set."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path="a/one", synced_sha="abc"),
                    SkillPin(path="a/two", synced_sha="def", dest="skills/aws"),
                ],
                dest="skills/aily",
            )
        ]
    )
    config_path = tmp_path / "sources.yaml"

    save_config(config, config_path)

    assert load_config(config_path) == config


def test_skill_dest_resolves_precedence() -> None:
    """`skill_dest` prefers the pin's dest, then the source's, then 'skills'."""
    source = Source(repo="r", ref="main", skills=[], dest="skills/aily")
    assert skill_dest(source, SkillPin(path="a/x", synced_sha=None)) == "skills/aily"
    assert (
        skill_dest(source, SkillPin(path="a/x", synced_sha=None, dest="skills/aws"))
        == "skills/aws"
    )
    bare = Source(repo="r", ref="main", skills=[])
    assert skill_dest(bare, SkillPin(path="a/x", synced_sha=None)) == "skills"


def test_accept_fields_default_and_round_trip(tmp_path: Path) -> None:
    """`accept_findings`/`accept_invalid` default empty/False and survive save→load."""
    config = Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path="a/plain", synced_sha="x"),
                    SkillPin(
                        path="a/jira",
                        synced_sha="y",
                        accept_findings=["P1", "SC2"],
                        accept_invalid=True,
                    ),
                ],
            )
        ]
    )
    config_path = tmp_path / "sources.yaml"

    save_config(config, config_path)
    reloaded = load_config(config_path)

    assert reloaded == config
    assert reloaded.sources[0].skills[0].accept_findings == []
    assert reloaded.sources[0].skills[0].accept_invalid is False
    assert reloaded.sources[0].skills[1].accept_findings == ["P1", "SC2"]
    assert reloaded.sources[0].skills[1].accept_invalid is True


def test_load_profile_reads_file(tmp_path: Path) -> None:
    """`load_profile` returns the file contents when present."""
    profile_path = tmp_path / "profile.md"
    profile_path.write_text("# My profile\n")

    assert load_profile(profile_path) == "# My profile\n"


def test_load_profile_missing_returns_empty(tmp_path: Path) -> None:
    """`load_profile` returns an empty string when the file is absent."""
    assert load_profile(tmp_path / "absent.md") == ""


# --- skill_name: the local folder name for a pin --------------------------------


def test_skill_name_defaults_to_path_basename() -> None:
    """Without an override a pin is named by its subtree's last segment."""
    assert skill_name(SkillPin(path="skills/engineering/tdd", synced_sha=None)) == "tdd"


def test_skill_name_prefers_explicit_name() -> None:
    """An explicit `name` overrides the path basename."""
    pin = SkillPin(path="skills/engineering/tdd", synced_sha=None, name="my-tdd")

    assert skill_name(pin) == "my-tdd"


def test_skill_name_raises_for_root_pin_without_name() -> None:
    """A root-path pin has no basename to fall back on, so it must be named."""
    with pytest.raises(ConfigError, match="repo root"):
        skill_name(SkillPin(path=".", synced_sha=None))


def test_skill_name_resolves_root_pin_with_name() -> None:
    """A named root pin resolves to that name."""
    pin = SkillPin(path=".", synced_sha=None, name="asd-ste100")

    assert skill_name(pin) == "asd-ste100"


def test_name_round_trips_through_save_and_load(tmp_path: Path) -> None:
    """A pin's `name` survives a save/load cycle of sources.yaml."""
    path = tmp_path / "sources.yaml"
    pin = SkillPin(
        path=".", synced_sha="sha1", dest="skills/productivity", name="asd-ste100"
    )
    save_config(Config(sources=[Source(repo="o/r", ref="master", skills=[pin])]), path)

    reloaded = load_config(path)

    assert reloaded.sources[0].skills[0].name == "asd-ste100"
    assert reloaded.warnings == []


def test_name_is_omitted_when_unset(tmp_path: Path) -> None:
    """A pin with no `name` does not gain a null key on save."""
    path = tmp_path / "sources.yaml"
    pin = SkillPin(path="skills/demo", synced_sha="sha1")
    save_config(Config(sources=[Source(repo="o/r", ref="main", skills=[pin])]), path)

    assert "name:" not in path.read_text()
