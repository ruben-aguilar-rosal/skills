"""REPROFILE command — propagate a profile.md change across every skill.

`run_reprofile` is the propagation lever for stack/tone changes (PLAN.md hardening
decision 6). Because each `adaptation.md` is self-contained — the author profile is
baked into it verbatim, not referenced — a `profile.md` edit does not reach the
skills on its own. Reprofile closes that gap: for every tracked skill it runs an LLM
pass that re-bakes the CURRENT `profile.md` into that skill's `adaptation.md`,
regenerates `SKILL.md` from the on-disk upstream mirror + the re-baked adaptation,
validates, and opens ONE PR per skill (labelled `reprofile`).

Per-skill isolation matches the sync pipeline: a skill whose regenerated `SKILL.md`
fails validation is blocked — an issue is filed, no PR opens, and its `adaptation.md`
is left untouched — while every other skill still ships its own PR. The re-baked
`adaptation.md` is written only on the PR path, so a blocked skill is never left in a
half-reprofiled state. All git/claude/gh contact goes through injected ports.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from skillsync.commands.regen import regenerate_to_pr
from skillsync.config import Config, load_profile, skill_dest
from skillsync.layout import SkillLayout, read_text, read_tree, write_text
from skillsync.ports.gh import GhPort
from skillsync.ports.llm import LLMError, LLMPort

# Default model for the agentic re-bake + regeneration (PLAN.md: Opus everywhere).
_DEFAULT_MODEL = "opus"

# Label applied to every reprofile PR so the PR list distinguishes a profile
# propagation from an incremental sync or a one-off regen.
_REPROFILE_LABEL = "reprofile"

# JSON schema the re-bake step's output must satisfy: a single `adaptation_md`
# string. `additionalProperties: False` stops the model smuggling extra fields.
REBAKE_SCHEMA: dict = {
    "type": "object",
    "properties": {"adaptation_md": {"type": "string"}},
    "required": ["adaptation_md"],
    "additionalProperties": False,
}

# The re-bake prompt: rewrite the existing self-contained adaptation.md so it bakes
# in the CURRENT author profile verbatim, preserving the skill-specific guidance.
# Both inputs are author-trusted (no upstream content), so no untrusted markers.
_REBAKE_TEMPLATE = """\
You are re-baking the author profile into a personal skill's self-contained \
`adaptation.md`. The author profile has changed; rewrite the `adaptation.md` so it \
embeds the CURRENT profile below VERBATIM, while preserving all skill-specific \
adaptation guidance the existing file already carries. Update or drop only the parts \
that the profile change makes stale; keep the document self-contained.

Current author profile to bake in verbatim:

{profile}

The existing adaptation.md to re-bake:

{adaptation}

Return JSON matching the schema: \
{{"adaptation_md": "<the full re-baked adaptation.md text>"}}.
"""

Status = Literal["pr", "invalid"]


@dataclass
class ReprofileOutcome:
    """The result of reprofiling one skill.

    `status` is the terminal outcome; `url` is the PR or issue URL opened; `detail`
    is a short human-readable summary.
    """

    name: str
    skill_path: str
    status: Status
    url: str | None = None
    detail: str = ""
    flags: list[str] = field(default_factory=list)


def run_reprofile(
    config: Config,
    root: Path,
    *,
    llm: LLMPort,
    gh: GhPort,
    model: str = _DEFAULT_MODEL,
) -> list[ReprofileOutcome]:
    """Re-bake the current profile.md into every tracked skill and open a PR per skill.

    Reads `profile.md` once, then for each pinned skill in `config` re-bakes its
    `adaptation.md`, regenerates `SKILL.md` from the on-disk upstream mirror, validates,
    and opens a `reprofile`-labelled PR on success. A skill whose regenerated SKILL.md
    fails validation is blocked (issue, no PR, adaptation.md untouched) without
    affecting the others. Returns one `ReprofileOutcome` per tracked skill.
    """
    profile = load_profile(root / "profile.md")
    outcomes: list[ReprofileOutcome] = []
    for skill_path, dest in _tracked_paths(config):
        outcomes.append(
            _reprofile_one(skill_path, dest, root, profile, llm=llm, gh=gh, model=model)
        )
    return outcomes


def _tracked_paths(config: Config) -> list[tuple[str, str]]:
    """Every pinned skill's `(subtree path, dest dir)` across all sources, in order."""
    return [
        (pin.path, skill_dest(source, pin))
        for source in config.sources
        for pin in source.skills
    ]


def _reprofile_one(
    skill_path: str,
    dest: str,
    root: Path,
    profile: str,
    *,
    llm: LLMPort,
    gh: GhPort,
    model: str,
) -> ReprofileOutcome:
    """Re-bake one skill's adaptation.md and regenerate it into a PR (or block it)."""
    layout = SkillLayout.resolve(root, skill_path, dest=dest)
    current_adaptation = read_text(layout.adaptation_path) or ""
    rebaked = _rebake_adaptation(profile, current_adaptation, llm, model)
    upstream_files = read_tree(layout.upstream_dir)

    branch = f"skillsync/reprofile-{layout.name}"
    title = f"skillsync: reprofile {layout.name}"
    status, url, detail, flags = regenerate_to_pr(
        layout,
        root,
        rebaked,
        upstream_files,
        llm=llm,
        gh=gh,
        branch=branch,
        title=title,
        labels=[_REPROFILE_LABEL],
        kind=_REPROFILE_LABEL,
        model=model,
    )

    # Persist the re-baked adaptation.md only on the PR path: a blocked skill must
    # not be left half-reprofiled with a SKILL.md that no longer matches its rules.
    if status == "pr":
        write_text(layout.adaptation_path, rebaked)

    return ReprofileOutcome(
        name=layout.name,
        skill_path=skill_path,
        status=status,
        url=url,
        detail=detail,
        flags=flags,
    )


def _rebake_adaptation(
    profile: str, adaptation: str, llm: LLMPort, model: str
) -> str:
    """Run the LLM re-bake pass, returning the adaptation.md with the profile baked in."""
    prompt = _REBAKE_TEMPLATE.format(profile=profile, adaptation=adaptation)
    result = llm.complete(prompt, schema=REBAKE_SCHEMA, model=model, temperature=0.0)
    if result.json is None:
        raise LLMError("reprofile re-bake step received no JSON payload from the LLM")
    return result.json["adaptation_md"]
