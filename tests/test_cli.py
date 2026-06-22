"""Tests for the skillsync CLI skeleton."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillsync import __version__, cli
from skillsync.cli import app, resolve_claude_command
from skillsync.layout import write_text
from skillsync.ports.llm import LLMResult
from skillsync.stages.gate import GateResult
from skillsync.testing.fakes import FakeGh, FakeGit, FakeLLM, FakeScanner


def _patch_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `make_scanner` at a pass-through FakeScanner (no real SkillSpector)."""
    monkeypatch.setattr(
        cli, "make_scanner", lambda: FakeScanner(GateResult(passed=True, findings=[]))
    )

RUNNER = CliRunner()


def test_resolve_claude_command_defaults_to_none() -> None:
    """With no env override, the bare `claude` default is used (None)."""
    assert resolve_claude_command({}) is None


def test_resolve_claude_command_via_zsh_shorthand() -> None:
    """`SKILLSYNC_CLAUDE_VIA_ZSH=1` yields the canned interactive-zsh prefix."""
    assert resolve_claude_command({"SKILLSYNC_CLAUDE_VIA_ZSH": "1"}) == [
        "zsh",
        "-ic",
        'claude "$@"',
        "_",
    ]


def test_resolve_claude_command_explicit_cmd_wins() -> None:
    """An explicit `SKILLSYNC_CLAUDE_CMD` is shell-split and takes precedence."""
    env = {
        "SKILLSYNC_CLAUDE_CMD": "bash -ic 'claude \"$@\"' _",
        "SKILLSYNC_CLAUDE_VIA_ZSH": "1",
    }
    assert resolve_claude_command(env) == ["bash", "-ic", 'claude "$@"', "_"]


def test_resolve_claude_command_ignores_falsey_zsh_flag() -> None:
    """A non-truthy `SKILLSYNC_CLAUDE_VIA_ZSH` value does not trigger the prefix."""
    assert resolve_claude_command({"SKILLSYNC_CLAUDE_VIA_ZSH": "0"}) is None
    assert resolve_claude_command({"SKILLSYNC_CLAUDE_VIA_ZSH": ""}) is None


def test_version_exits_zero_and_prints_version() -> None:
    """`skillsync version` exits 0 and prints the package version string."""
    result = RUNNER.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def _write_sources(tmp_path: Path, body: str) -> Path:
    """Write a sources.yaml under `tmp_path` and return its path."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(body)
    return config_path


def test_status_reports_sha_drift_and_link_state(tmp_path: Path) -> None:
    """`skillsync status` (offline) reports each skill's sha, drift, and link state."""
    write_text(tmp_path / "skills" / "alpha" / "SKILL.md", "hand-edited")
    write_text(tmp_path / "skills" / "alpha" / ".generated" / "SKILL.md", "generated")
    write_text(tmp_path / "skills" / "beta" / "SKILL.md", "same")
    write_text(tmp_path / "skills" / "beta" / ".generated" / "SKILL.md", "same")
    config_path = _write_sources(
        tmp_path,
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    skills:\n"
        "      - path: skills/alpha\n"
        "        synced_sha: abcdef1234\n"
        "      - path: skills/beta\n"
        "        synced_sha: beef5678\n",
    )

    result = RUNNER.invoke(
        app,
        ["status", "--config", str(config_path), "--root", str(tmp_path), "--offline"],
    )

    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "abcdef1" in result.stdout  # short sha
    assert "drift" in result.stdout
    assert "beta" in result.stdout
    assert "clean" in result.stdout


def test_status_reports_no_skills(tmp_path: Path) -> None:
    """`skillsync status` reports cleanly when no skill folders exist."""
    config_path = _write_sources(tmp_path, "sources: []\n")

    result = RUNNER.invoke(
        app,
        ["status", "--config", str(config_path), "--root", str(tmp_path), "--offline"],
    )

    assert result.exit_code == 0
    assert "no skills" in result.stdout.lower()


def test_link_symlinks_skills_into_target_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync link` symlinks each skill into the env-overridden target dir."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "# demo\n")
    target = tmp_path / "claude_skills"
    monkeypatch.setenv("SKILLSYNC_LINK_DIR", str(target))

    # No config at this path → link falls back to scanning the default skills/ dir.
    result = RUNNER.invoke(
        app, ["link", "--root", str(tmp_path), "--config", str(tmp_path / "none.yaml")]
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert (target / "demo").is_symlink()


def test_link_dry_run_makes_no_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync link --dry-run` prints the plan without touching the filesystem."""
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", "# demo\n")
    target = tmp_path / "claude_skills"
    monkeypatch.setenv("SKILLSYNC_LINK_DIR", str(target))

    result = RUNNER.invoke(
        app,
        ["link", "--root", str(tmp_path), "--config", str(tmp_path / "none.yaml"), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "would create" in result.stdout
    assert not target.exists()


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
    _patch_scanner(monkeypatch)
    upstream_old = "---\nname: demo\ndescription: Old.\n---\n\nold\n"
    upstream_new = "---\nname: demo\ndescription: New.\n---\n\nnew\n"
    adapted = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nbody\n"

    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream_old})
    git.add_commit("sha2", {"skills/demo/SKILL.md": upstream_new})
    git.set_ref("main", "sha2")
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", upstream_old)
    write_text(tmp_path / "skills" / "demo" / "adaptation.md", "Target TP.")
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


def test_sync_no_pr_adapts_locally_without_opening_a_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync sync --no-pr` writes adapted artifacts locally and opens no PR."""
    _patch_scanner(monkeypatch)
    upstream_old = "---\nname: demo\ndescription: Old.\n---\n\nold\n"
    upstream_new = "---\nname: demo\ndescription: New.\n---\n\nnew\n"
    adapted = "---\nname: demo\ndescription: A demo.\n---\n\n# demo\nbody\n"

    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream_old})
    git.add_commit("sha2", {"skills/demo/SKILL.md": upstream_new})
    git.set_ref("main", "sha2")
    write_text(tmp_path / "skills" / "demo" / "SKILL.md", upstream_old)
    write_text(tmp_path / "skills" / "demo" / "adaptation.md", "Target TP.")
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
    gh = FakeGh()
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: gh)

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
        app, ["sync", "--config", str(config_path), "--root", str(tmp_path), "--no-pr"]
    )

    assert result.exit_code == 0
    assert "local" in result.stdout
    # The adapted SKILL.md is in the working tree, but no PR was opened.
    assert (tmp_path / "skills" / "demo" / "SKILL.md").read_text() == adapted
    assert not any(c.method == "open_pr" for c in gh.calls)


def test_sync_surfaces_watched_folder_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync sync` surfaces a new watched-folder skill as an awareness issue."""
    upstream = "---\nname: demo\ndescription: D.\n---\n\nbody\n"
    git = FakeGit()
    # The watched folder holds two skills; only `demo` is pinned, `extra` is new.
    git.add_commit(
        "sha1",
        {"eng/demo/SKILL.md": upstream, "eng/extra/SKILL.md": upstream},
    )
    git.set_ref("main", "sha1")
    gh = FakeGh()
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: FakeLLM({}))
    monkeypatch.setattr(cli, "make_gh", lambda: gh)

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    watch:\n"
        "      - eng/\n"
        "    skills:\n"
        "      - path: eng/demo\n"
        "        synced_sha: sha1\n"  # already synced -> no adapt work
    )

    result = RUNNER.invoke(
        app, ["sync", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "eng/extra" in result.stdout
    assert any(
        c.method == "open_issue" and "eng/extra" in c.args[1] for c in gh.calls
    )


def _watch_config(tmp_path: Path) -> tuple[Path, FakeGit]:
    """A config watching `eng/` with `eng/demo` pinned and `eng/extra` undiscovered."""
    upstream = "---\nname: demo\ndescription: D.\n---\n\nbody\n"
    git = FakeGit()
    git.add_commit(
        "sha1", {"eng/demo/SKILL.md": upstream, "eng/extra/SKILL.md": upstream}
    )
    git.set_ref("main", "sha1")
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    watch:\n"
        "      - eng/\n"
        "    skills:\n"
        "      - path: eng/demo\n"
        "        synced_sha: sha1\n"
    )
    return config_path, git


def test_discover_prints_findings_without_opening_issues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync discover` lists new watched-folder skills and opens nothing."""
    config_path, git = _watch_config(tmp_path)
    gh = FakeGh()
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_gh", lambda: gh)

    result = RUNNER.invoke(
        app, ["discover", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "eng/extra" in result.stdout
    assert "new" in result.stdout
    # Read-only: nothing was filed.
    assert gh.calls == []


def test_discover_reports_nothing_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync discover` reports cleanly when everything is already tracked."""
    upstream = "---\nname: demo\ndescription: D.\n---\n\nbody\n"
    git = FakeGit()
    git.add_commit("sha1", {"eng/demo/SKILL.md": upstream})
    git.set_ref("main", "sha1")
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n"
        "  - repo: owner/repo\n"
        "    ref: main\n"
        "    watch:\n"
        "      - eng/\n"
        "    skills:\n"
        "      - path: eng/demo\n"
        "        synced_sha: sha1\n"
    )
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    result = RUNNER.invoke(
        app, ["discover", "--config", str(config_path), "--root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "no" in result.stdout.lower()


def test_discover_open_issues_flag_files_awareness_issues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync discover --open-issues` files the awareness issues like sync does."""
    config_path, git = _watch_config(tmp_path)
    gh = FakeGh()
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_gh", lambda: gh)

    result = RUNNER.invoke(
        app,
        [
            "discover",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--open-issues",
        ],
    )

    assert result.exit_code == 0
    assert "eng/extra" in result.stdout
    assert any(
        c.method == "open_issue" and "eng/extra" in c.args[1] for c in gh.calls
    )


def test_ignore_appends_to_ignore_list(tmp_path: Path) -> None:
    """`skillsync ignore` records the path so discovery stops surfacing it."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n  - repo: owner/repo\n    ref: main\n    skills: []\n"
    )

    result = RUNNER.invoke(
        app, ["ignore", "owner/repo", "eng/extra", "--config", str(config_path)]
    )

    assert result.exit_code == 0
    from skillsync.config import load_config

    assert load_config(config_path).sources[0].ignore == ["eng/extra"]


def test_ignore_unknown_repo_exits_one(tmp_path: Path) -> None:
    """`skillsync ignore` for an unconfigured repo exits 1 with a message."""
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        "sources:\n  - repo: owner/repo\n    ref: main\n    skills: []\n"
    )

    result = RUNNER.invoke(
        app, ["ignore", "other/repo", "eng/extra", "--config", str(config_path)]
    )

    assert result.exit_code == 1
    assert "other/repo" in result.output


def test_add_vendors_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync add` (no --adapt) vendors verbatim with no LLM and opens a PR."""
    _patch_scanner(monkeypatch)
    upstream = (
        "---\nname: demo\ndescription: Notes to issues.\n---\n\n# demo\nMake an issue.\n"
    )
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream})
    git.set_ref("main", "sha1")
    llm = FakeLLM({})  # vendoring must not call the LLM
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: llm)
    monkeypatch.setattr(cli, "make_gh", lambda: FakeGh())

    config_path = tmp_path / "sources.yaml"
    config_path.write_text("sources: []\n")

    result = RUNNER.invoke(
        app,
        ["add", "owner/repo", "skills/demo", "--config", str(config_path), "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout
    assert llm.calls == []
    # Vendored verbatim, no adaptation.md.
    assert (tmp_path / "skills" / "demo" / "SKILL.md").read_text() == upstream
    assert not (tmp_path / "skills" / "demo" / "adaptation.md").exists()


def test_add_no_pr_writes_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync add --no-pr` vendors to the working tree and opens no PR."""
    _patch_scanner(monkeypatch)
    upstream = "---\nname: demo\ndescription: D.\n---\n\n# demo\nbody\n"
    git = FakeGit()
    git.add_commit("sha1", {"skills/demo/SKILL.md": upstream})
    git.set_ref("main", "sha1")
    gh = FakeGh()
    monkeypatch.setattr(cli, "make_git", lambda: git)
    monkeypatch.setattr(cli, "make_llm", lambda: FakeLLM({}))
    monkeypatch.setattr(cli, "make_gh", lambda: gh)

    config_path = tmp_path / "sources.yaml"
    config_path.write_text("sources: []\n")

    result = RUNNER.invoke(
        app,
        ["add", "owner/repo", "skills/demo", "--no-pr", "--config", str(config_path), "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "local" in result.stdout
    assert (tmp_path / "skills" / "demo" / "SKILL.md").read_text() == upstream
    assert not any(c.method == "open_pr" for c in gh.calls)


def test_add_adapt_flag_drafts_and_generates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`skillsync add --adapt` drafts adaptation.md and full-generates via the LLM."""
    _patch_scanner(monkeypatch)
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
            "--adapt",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "pr" in result.stdout
    assert (tmp_path / "skills" / "demo" / "adaptation.md").exists()


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
