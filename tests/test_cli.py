"""Tests for the skillsync CLI skeleton."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillsync import __version__, cli
from skillsync.cli import app
from skillsync.layout import write_text
from skillsync.ports.llm import LLMResult
from skillsync.testing.fakes import FakeGh, FakeGit, FakeLLM

RUNNER = CliRunner()


def test_version_exits_zero_and_prints_version() -> None:
    """`skillsync version` exits 0 and prints the package version string."""
    result = RUNNER.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_status_lists_skill_folders_and_presence(tmp_path: Path) -> None:
    """`skillsync status` lists each skill folder and which files are present."""
    write_text(tmp_path / "skills" / "alpha" / "adaptation.md", "rules")
    write_text(tmp_path / "skills" / "alpha" / "SKILL.md", "skill")
    write_text(tmp_path / "skills" / "alpha" / ".generated" / "SKILL.md", "snap")
    write_text(tmp_path / "skills" / "beta" / "adaptation.md", "rules")

    result = RUNNER.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_status_reports_no_skills(tmp_path: Path) -> None:
    """`skillsync status` reports cleanly when no skill folders exist."""
    result = RUNNER.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "no skills" in result.stdout.lower()


def test_detect_prints_kind_table_with_injected_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync detect` prints a name → kind table using an injected `FakeGit`."""
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": "# Demo\nfirst\n"})
    git.add_commit("sha2", {"skills/demo/SKILL.md": "# Demo\nsecond\n"})
    git.set_ref("main", "sha2")
    monkeypatch.setattr(cli, "make_git", lambda: git)

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/demo\n"
        "        synced_sha: sha1\n"
    )

    result = RUNNER.invoke(app, ["detect", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "changed" in result.stdout


def test_validate_passes_for_well_formed_skill(tmp_path: Path) -> None:
    """`skillsync validate` exits 0 and prints PASS for a loadable skill."""
    skill_md = (
        "---\nname: demo\ndescription: A demo skill.\n---\n\n# demo\nNothing to see.\n"
    )
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", skill_md)

    result = RUNNER.invoke(app, ["validate", "demo", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_validate_exits_one_for_broken_skill(tmp_path: Path) -> None:
    """`skillsync validate` exits 1 and reports the error for a broken skill."""
    # Frontmatter name does not match the folder, and a referenced file is missing.
    skill_md = (
        "---\nname: wrong\ndescription: Bad.\n---\n\n"
        "# demo\nSee [the script](scripts/missing.sh).\n"
    )
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", skill_md)

    result = RUNNER.invoke(app, ["validate", "demo", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "scripts/missing.sh" in result.output


def test_sync_prints_outcome_table_with_injected_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync sync` runs the pipeline with injected fakes and prints outcomes."""
    upstream_old = "---\nname: demo\ndescription: Old.\n---\n\nold\n"
    upstream_new = "---\nname: demo\ndescription: New.\n---\n\nnew\n"
    adapted = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nbody\n"

    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream_old})
    git.add_commit("sha2", {"skills/demo/SKILL.md": upstream_new})
    git.set_ref("main", "sha2")
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", upstream_old)
    llm = FakeLLM(
        {
            "security reviewer auditing": LLMResult(
                text="{}", json={"risk": "low", "rationale": "ok", "findings": []}
            ),
            "Apply the SEMANTIC EQUIVALENT": LLMResult(
                text="{}", json={"skill_md": adapted}
            ),
        }
    )
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/demo\n"
        "        synced_sha: sha1\n"
    )

    result = RUNNER.invoke(
        app, ["sync", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout


def test_add_onboards_skill_with_injected_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync add` onboards a new skill with injected fakes and prints the outcome."""
    upstream = (
        "---\nname: demo\ndescription: Notes to issues.\n---\n\n# demo\nMake an issue.\n"
    )
    adapted = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nFile a Jira issue.\n"

    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream})
    git.set_ref("main", "sha1")
    (tmp_path / "profile.md").write_text("Use Jira project TP.\n")
    llm = FakeLLM(
        {
            "security reviewer auditing": LLMResult(
                text="{}", json={"risk": "low", "rationale": "ok", "findings": []}
            ),
            "drafting a self-contained": LLMResult(
                text="{}", json={"adaptation_md": "Use Jira project TP.\n\nFile in TP.\n"}
            ),
            "from scratch": LLMResult(text="{}", json={"skill_md": adapted}),
        }
    )
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    config_path = tmp_path / "sources.yaml"
    config_path.write_text("sources: []\n")

    result = RUNNER.invoke(
        app,
        [
            "add",
            "owner/repo",
            "skills/demo",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout


def test_regen_regenerates_skill_with_injected_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync regen` rebuilds a skill from on-disk sources and prints the outcome."""
    regenerated = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nFile a Jira issue.\n"
    write_text(
        tmp_path / "skills" / "demo" / "upstream" / "SKILL.md",
        "---\nname: demo\ndescription: Upstream.\n---\n\n# demo\nMake an issue.\n",
    )
    write_text(tmp_path / "skills" / "demo" / "adaptation.md", "Use Jira project TP.\n")
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "old")
    llm = FakeLLM({"from scratch": LLMResult(text="{}", json={"skill_md": regenerated})})
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/demo\n"
        "        synced_sha: sha1\n"
    )

    result = RUNNER.invoke(
        app, ["regen", "demo", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout


def test_reprofile_rebakes_every_skill_with_injected_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync reprofile` re-bakes profile.md into each skill and prints outcomes."""
    regenerated = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nFile a Jira issue.\n"
    write_text(
        tmp_path / "skills" / "demo" / "upstream" / "SKILL.md",
        "---\nname: demo\ndescription: Upstream.\n---\n\n# demo\nMake an issue.\n",
    )
    write_text(tmp_path / "skills" / "demo" / "adaptation.md", "Old profile.\n")
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", regenerated)
    (tmp_path / "profile.md").write_text("Use Jira project TP.\n")
    llm = FakeLLM(
        {
            "re-baking the author profile": LLMResult(
                text="{}", json={"adaptation_md": "Use Jira project TP.\n\nFile in TP.\n"}
            ),
            "from scratch": LLMResult(text="{}", json={"skill_md": regenerated}),
        }
    )
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/demo\n"
        "        synced_sha: sha1\n"
    )

    result = RUNNER.invoke(
        app, ["reprofile", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout
