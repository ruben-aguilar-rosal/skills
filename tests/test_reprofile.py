"""Tests for the REPROFILE command (`skillsync.commands.reprofile`).

`run_reprofile` is the propagation lever for stack/tone changes: for every skill it
runs an LLM pass that re-bakes the CURRENT `profile.md` into that skill's
self-contained `adaptation.md`, regenerates `SKILL.md` (full mode) from the on-disk
upstream mirror + the re-baked adaptation, validates, and opens ONE PR per skill.
These tests drive the injected `FakeLLM` + `FakeGh`:

- **happy path** → every adaptation.md is re-baked and one PR opens per skill,
  labelled `reprofile`;
- **validate fail** → that skill's PR is blocked (issue, no PR, nothing written),
  while the other skills still ship.
"""

from pathlib import Path

from skillsync.commands.reprofile import ReprofileOutcome, run_reprofile
from skillsync.config import Config, SkillPin, Source
from skillsync.layout import SkillLayout, read_text, write_text
from skillsync.ports.llm import LLMResult
from skillsync.testing.fakes import FakeGh, FakeLLM

# --- Scripted LLM substring keys ------------------------------------------------
_REBAKE_KEY = "re-baking the author profile"
_FULL_KEY = "from scratch"

# The current author profile.md, re-baked into every adaptation.md.
_PROFILE = "Use Jira project TP. AWS profile aws-infrastructure. Terse tone.\n"

# The re-baked adaptation.md the LLM "returns" (carries a recognizable marker).
_REBAKED_ADAPTATION = (
    "Use Jira project TP. AWS profile aws-infrastructure. Terse tone.\n\n"
    "REBAKED-V2: adapt to project TP.\n"
)


def _valid_skill_md(name: str) -> str:
    """A valid full-generated SKILL.md whose frontmatter name matches its folder."""
    return (
        f"---\nname: {name}\ndescription: A {name} skill.\n---\n\n"
        f"# {name}\nFile a Jira issue in project TP.\n"
    )


def _full(skill_md: str) -> LLMResult:
    """A scripted full-mode adapt result returning `skill_md`."""
    return LLMResult(text="{}", json={"skill_md": skill_md})


def _rebake(adaptation_md: str = _REBAKED_ADAPTATION) -> LLMResult:
    """A scripted re-bake result returning the updated adaptation.md."""
    return LLMResult(text="{}", json={"adaptation_md": adaptation_md})


def _seed_skill(root: Path, name: str, *, marker: str) -> SkillLayout:
    """Lay down an on-disk skill: upstream mirror (carrying `marker`) + adaptation.md."""
    layout = SkillLayout.resolve(root, name)
    upstream = (
        f"---\nname: {name}\ndescription: Upstream {name}.\n---\n\n"
        f"# {name}\n{marker} — create a GitHub issue.\n"
    )
    write_text(layout.upstream_dir / "SKILL.md", upstream)
    write_text(layout.adaptation_path, f"Old profile. Adapt {name}.\n")
    write_text(layout.skill_md_path, _valid_skill_md(name))
    return layout


def _config(*names: str) -> Config:
    """A config pinning each named skill under one source, synced at `sha1`."""
    return Config(
        sources=[
            Source(
                repo="owner/repo",
                ref="main",
                skills=[
                    SkillPin(path=f"skills/{name}", synced_sha="sha1") for name in names
                ],
            )
        ]
    )


# --- happy path -----------------------------------------------------------------


def test_reprofile_rebakes_every_adaptation_and_opens_one_pr_each(tmp_path: Path) -> None:
    """Re-bakes each adaptation.md and opens exactly one PR per skill."""
    (tmp_path / "profile.md").write_text(_PROFILE)
    demo = _seed_skill(tmp_path, "demo", marker="MARKER_DEMO")
    gamma = _seed_skill(tmp_path, "gamma", marker="MARKER_GAMMA")
    config = _config("demo", "gamma")
    llm = FakeLLM(
        {
            _REBAKE_KEY: _rebake(),
            "MARKER_DEMO": _full(_valid_skill_md("demo")),
            "MARKER_GAMMA": _full(_valid_skill_md("gamma")),
        }
    )
    gh = FakeGh()

    outcomes = run_reprofile(config, tmp_path, llm=llm, gh=gh)

    assert [o.status for o in outcomes] == ["pr", "pr"]
    # Every adaptation.md was re-baked on disk.
    assert read_text(demo.adaptation_path) == _REBAKED_ADAPTATION
    assert read_text(gamma.adaptation_path) == _REBAKED_ADAPTATION
    # One PR per skill.
    assert sum(1 for c in gh.calls if c.method == "open_pr") == 2


def test_reprofile_bakes_profile_into_rebake_prompt(tmp_path: Path) -> None:
    """The re-bake prompt carries profile.md verbatim and the current adaptation.md."""
    (tmp_path / "profile.md").write_text(_PROFILE)
    _seed_skill(tmp_path, "demo", marker="MARKER_DEMO")
    config = _config("demo")
    llm = FakeLLM({_REBAKE_KEY: _rebake(), "MARKER_DEMO": _full(_valid_skill_md("demo"))})

    run_reprofile(config, tmp_path, llm=llm, gh=FakeGh())

    rebake_call = next(c for c in llm.calls if _REBAKE_KEY in c.prompt)
    assert "Use Jira project TP." in rebake_call.prompt
    assert "Adapt demo." in rebake_call.prompt


def test_reprofile_pr_carries_reprofile_label(tmp_path: Path) -> None:
    """Each reprofile PR is labelled `reprofile`."""
    (tmp_path / "profile.md").write_text(_PROFILE)
    _seed_skill(tmp_path, "demo", marker="MARKER_DEMO")
    config = _config("demo")
    llm = FakeLLM({_REBAKE_KEY: _rebake(), "MARKER_DEMO": _full(_valid_skill_md("demo"))})
    gh = FakeGh()

    run_reprofile(config, tmp_path, llm=llm, gh=gh)

    open_pr = next(c for c in gh.calls if c.method == "open_pr")
    assert "reprofile" in open_pr.args[4]


# --- validate fail -> blocks only that skill's PR -------------------------------


def test_reprofile_validate_fail_blocks_only_that_skill(tmp_path: Path) -> None:
    """A skill whose regenerated SKILL.md fails validation is blocked; others ship."""
    (tmp_path / "profile.md").write_text(_PROFILE)
    good = _seed_skill(tmp_path, "demo", marker="MARKER_DEMO")
    bad = _seed_skill(tmp_path, "gamma", marker="MARKER_GAMMA")
    bad_adaptation_before = read_text(bad.adaptation_path)
    config = _config("demo", "gamma")
    # gamma regenerates an invalid SKILL.md (frontmatter name != folder).
    invalid = "---\nname: wrong\ndescription: Bad.\n---\n\n# gamma\nbody\n"
    llm = FakeLLM(
        {
            _REBAKE_KEY: _rebake(),
            "MARKER_DEMO": _full(_valid_skill_md("demo")),
            "MARKER_GAMMA": _full(invalid),
        }
    )
    gh = FakeGh()

    outcomes = run_reprofile(config, tmp_path, llm=llm, gh=gh)

    by_name = {o.name: o for o in outcomes}
    assert by_name["demo"].status == "pr"
    assert by_name["gamma"].status == "invalid"
    # Only the good skill opened a PR; the bad one opened an issue.
    assert sum(1 for c in gh.calls if c.method == "open_pr") == 1
    assert any(c.method == "open_issue" for c in gh.calls)
    # The blocked skill's adaptation.md was NOT overwritten.
    assert read_text(bad.adaptation_path) == bad_adaptation_before
    # The good skill's adaptation.md WAS re-baked.
    assert read_text(good.adaptation_path) == _REBAKED_ADAPTATION
