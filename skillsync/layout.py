"""Skill layout path model and folder I/O helpers.

`SkillLayout` resolves the on-disk paths for one skill folder under `skills/`.
The read/write helpers are pure functions over `Path` — no git, no network — so
the deterministic stages and the CLI share one vocabulary for skill files.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path


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
    def resolve(cls, repo_root: Path, subtree: str, name: str | None = None) -> "SkillLayout":
        """Build a layout for `subtree`, naming it by its last segment unless overridden."""
        skill_name = name or subtree.rstrip("/").rsplit("/", 1)[-1]
        root = repo_root / "skills" / skill_name
        generated_dir = root / ".generated"
        return cls(
            name=skill_name,
            root=root,
            upstream_dir=root / "upstream",
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


def mirror_files(files: dict[str, str], dest_dir: Path) -> None:
    """Replace `dest_dir` with exactly `files` (relative path -> content).

    Stale files and now-empty directories left by a previous mirror are removed,
    so the destination is an exact image of the new snapshot.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    for rel_path, content in files.items():
        write_text(dest_dir / rel_path, content)


def read_tree(directory: Path) -> dict[str, str]:
    """Return `{relative-path: content}` for every file under `directory`.

    The inverse of `mirror_files`: it reads a previously-mirrored upstream subtree
    back off disk for the regen/reprofile commands, which regenerate from the
    current on-disk mirror rather than re-pulling upstream. Returns `{}` when the
    directory is absent.
    """
    if not directory.is_dir():
        return {}
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.read_text()
    return files


def read_skill(layout: SkillLayout) -> SkillFiles:
    """Read the adaptation, committed SKILL.md, and generated snapshot for a skill."""
    return SkillFiles(
        adaptation=read_text(layout.adaptation_path),
        skill_md=read_text(layout.skill_md_path),
        generated_skill_md=read_text(layout.generated_skill_md_path),
    )


def discover_skills(repo_root: Path) -> list[SkillLayout]:
    """Return a layout for each skill folder under `skills/`, sorted by name."""
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return []
    return [
        SkillLayout.resolve(repo_root, child.name)
        for child in sorted(skills_dir.iterdir(), key=lambda p: p.name)
        if child.is_dir()
    ]
