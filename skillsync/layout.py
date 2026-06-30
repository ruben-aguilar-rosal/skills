"""Skill layout path model and folder I/O helpers.

`SkillLayout` resolves the on-disk paths for one skill folder under `skills/`.
The read/write helpers are pure functions over `Path` — no git, no network — so
the deterministic stages and the CLI share one vocabulary for skill files.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillsync.config import Config


@dataclass(frozen=True)
class SkillLayout:
    """Resolved on-disk paths for one skill folder under `skills/<name>/`."""

    name: str
    root: Path
    upstream_dir: Path
    adaptation_path: Path
    skill_md_path: Path
    generated_dir: Path
    generated_skill_md_path: Path

    @classmethod
    def resolve(
        cls,
        repo_root: Path,
        subtree: str,
        name: str | None = None,
        dest: str = "skills",
    ) -> "SkillLayout":
        """Build a layout for `subtree`, naming it by its last segment unless overridden.

        `dest` is the parent dir (relative to `repo_root`) the skill folder lives
        under; it defaults to `skills`, so the folder is `<dest>/<name>/`.
        """
        skill_name = name or subtree.rstrip("/").rsplit("/", 1)[-1]
        root = repo_root / dest / skill_name
        generated_dir = root / ".generated"
        return cls(
            name=skill_name,
            root=root,
            upstream_dir=root / ".upstream",
            adaptation_path=root / "adaptation.md",
            skill_md_path=root / "SKILL.md",
            generated_dir=generated_dir,
            generated_skill_md_path=generated_dir / "SKILL.md",
        )


@dataclass
class SkillFiles:
    """The three hand-/agent-owned skill files; each `None` when absent on disk."""

    adaptation: str | None
    skill_md: str | None
    generated_skill_md: str | None


def read_text(path: Path) -> str | None:
    """Return the file's text, or None if it does not exist."""
    if not path.exists():
        return None
    return path.read_text()


def write_text(path: Path, text: str) -> None:
    """Write `text` to `path`, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_file(path: Path, content: str | bytes) -> None:
    """Write `content` to `path` (text or raw bytes), creating parent dirs as needed.

    The binary-safe sibling of `write_text`: an upstream subtree may ship binary
    aux files (fonts, images, archives), which arrive as `bytes`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def mirror_files(files: dict[str, str | bytes], dest_dir: Path) -> None:
    """Replace `dest_dir` with exactly `files` (relative path -> content).

    Stale files and now-empty directories left by a previous mirror are removed,
    so the destination is an exact image of the new snapshot. Content may be text
    or raw `bytes` (binary blobs are written verbatim).
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    for rel_path, content in files.items():
        write_file(dest_dir / rel_path, content)


def write_aux_files(layout: "SkillLayout", upstream_files: dict[str, str | bytes]) -> None:
    """Lay a skill's ship-along files (everything but SKILL.md) into the skill root.

    The committed/generated `SKILL.md` is owned by the adapt/vendor step; every OTHER
    file the upstream subtree ships — `scripts/`, `references/`, `assets/`, … — is
    copied verbatim alongside it so the linked skill actually works (the script a
    `SKILL.md` references must sit next to it, not only in the `.upstream` mirror).

    Aux files written by a previous sync but absent from `upstream_files` are pruned,
    while the skill-owned paths (`SKILL.md`, `adaptation.md`, `.generated/`,
    `.upstream/`) are always left untouched.
    """
    desired = {rel: content for rel, content in upstream_files.items() if rel != "SKILL.md"}

    for stale in _stale_aux_paths(layout, set(desired)):
        stale.unlink()
    for rel_path, content in desired.items():
        write_file(layout.root / rel_path, content)
    _prune_empty_dirs(layout)


# Top-level skill-folder entries that `write_aux_files` must never write or prune.
_RESERVED_ROOT_NAMES = {"SKILL.md", "adaptation.md", ".generated", ".upstream"}


def _stale_aux_paths(layout: "SkillLayout", desired: set[str]) -> list[Path]:
    """Aux files currently under the skill root that are not in `desired`."""
    if not layout.root.is_dir():
        return []
    stale: list[Path] = []
    for path in layout.root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(layout.root)
        if rel.parts[0] in _RESERVED_ROOT_NAMES:
            continue
        if rel.as_posix() not in desired:
            stale.append(path)
    return stale


def _prune_empty_dirs(layout: "SkillLayout") -> None:
    """Remove now-empty aux directories left under the skill root after pruning."""
    if not layout.root.is_dir():
        return
    for path in sorted(layout.root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if (
            path.is_dir()
            and path.name not in _RESERVED_ROOT_NAMES
            and not any(path.iterdir())
        ):
            path.rmdir()


def read_tree(directory: Path) -> dict[str, str | bytes]:
    """Return `{relative-path: content}` for every file under `directory`.

    The inverse of `mirror_files`: it reads a previously-mirrored upstream subtree
    back off disk for the regen/reprofile commands, which regenerate from the
    current on-disk mirror rather than re-pulling upstream. Text files come back as
    `str`; non-UTF-8 files (binary aux assets) come back as `bytes`. Returns `{}`
    when the directory is absent.
    """
    if not directory.is_dir():
        return {}
    files: dict[str, str | bytes] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            rel = path.relative_to(directory).as_posix()
            raw = path.read_bytes()
            try:
                files[rel] = raw.decode("utf-8")
            except UnicodeDecodeError:
                files[rel] = raw
    return files


def read_skill(layout: SkillLayout) -> SkillFiles:
    """Read the adaptation, committed SKILL.md, and generated snapshot for a skill."""
    return SkillFiles(
        adaptation=read_text(layout.adaptation_path),
        skill_md=read_text(layout.skill_md_path),
        generated_skill_md=read_text(layout.generated_skill_md_path),
    )


def discover_skills(repo_root: Path) -> list[SkillLayout]:
    """Return a layout for each skill folder under `skills/`, sorted by name.

    A filesystem scan of the default `skills/` dir only. With configurable `dest`
    dirs a skill can live elsewhere, so config-driven callers should prefer
    `layouts_from_config`; this remains for the default-layout case.
    """
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return []
    return [
        SkillLayout.resolve(repo_root, child.name)
        for child in sorted(skills_dir.iterdir(), key=lambda p: p.name)
        if child.is_dir()
    ]


def layouts_from_config(config: "Config", repo_root: Path) -> list[SkillLayout]:
    """Return a layout for every pinned skill, resolved under its effective `dest`.

    The config is the source of truth for where each skill is stored, so this is
    the dest-aware replacement for `discover_skills` in commands that already load
    the config (e.g. `link`, `status`). Order follows config order.
    """
    from skillsync.config import skill_dest

    return [
        SkillLayout.resolve(repo_root, pin.path, dest=skill_dest(source, pin))
        for source in config.sources
        for pin in source.skills
    ]
