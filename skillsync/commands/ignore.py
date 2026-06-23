"""IGNORE command — record a durable "no" for a discovered skill.

`run_ignore` is the rejection half of the `watch`-folder feature, the counterpart to
`skillsync add`. When discovery surfaces a new upstream skill you don't want, this
appends its path to the matching source's `ignore` list in `sources.yaml`, so the
discovery stage stops surfacing it. It is deterministic and filesystem-only — no
git, LLM, or gh — and idempotent: ignoring an already-ignored path is a no-op.
"""

from pathlib import Path

from skillsync.config import Config, save_config


class IgnoreError(Exception):
    """Raised when the skill cannot be ignored (e.g. its repo isn't configured)."""


def run_ignore(config: Config, config_path: Path, repo: str, skill_path: str) -> None:
    """Add `skill_path` to `repo`'s ignore list and persist `config` to `config_path`.

    Finds the source for `repo`, appends the normalized `skill_path` to its `ignore`
    list if not already present, and saves the config. Raises `IgnoreError` when no
    source matches `repo` — ignoring a path under an unconfigured repo is a mistake
    worth surfacing rather than silently creating a dangling entry.
    """
    source = next((s for s in config.sources if s.repo == repo), None)
    if source is None:
        raise IgnoreError(
            f"no source for repo {repo!r} in the config; add it (or a skill from it) "
            "before ignoring a path under it"
        )
    normalized = skill_path.rstrip("/")
    if normalized not in source.ignore:
        source.ignore.append(normalized)
    save_config(config, config_path)
