"""Deterministic VALIDATE stage — the final gate before a PR.

`validate_skill` is a pure-ish function over a `SkillLayout` and the SKILL.md
text: it checks the frontmatter schema, that `name` matches the folder, the byte
ceiling, and that every relative path the body references exists on disk. It
touches the filesystem only to test reference existence — no git, no network, no
LLM. A failed validation blocks the PR, guaranteeing a loadable skill.

Callers that validate BEFORE writing the skill's ship-along files pass those
paths as `incoming_files`, so a reference to a file this sync is about to lay
down counts as present. Without it, every newly-added upstream aux file would
fail validation purely because the write had not happened yet.
"""

import re
from dataclasses import dataclass, field

import yaml

from skillsync.layout import SkillLayout

# Markdown inline link target: the text in `[label](target)`. A trailing title
# (`(path "title")`) is trimmed by the caller.
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Inline-code spans (single-backtick). Their content is checked for path shape.
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# A relative-path-shaped token: contains a `/`, ends in a file extension, and is
# made only of path-safe characters.
_REL_PATH_RE = re.compile(r"^[\w][\w./-]*/[\w./-]*\.\w+$")

# Targets that are not relative paths into the skill folder.
_SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "//")


@dataclass
class ValidationResult:
    """The validate verdict: pass/fail plus a list of human-readable errors."""

    passed: bool
    errors: list[str] = field(default_factory=list)


def validate_skill(
    layout: SkillLayout,
    skill_md_text: str,
    byte_cap: int,
    incoming_files: set[str] | None = None,
) -> ValidationResult:
    """Validate a skill's SKILL.md against the loadability rules.

    Checks, in order: the frontmatter parses to a mapping with non-empty `name`
    and `description`; `name` equals `layout.name`; the text is within `byte_cap`
    bytes; and every relative path referenced in the body exists under the skill
    folder — or is listed in `incoming_files`, the set of skill-relative paths the
    caller is about to write. Returns a `ValidationResult` whose `passed` is true
    iff `errors` is empty.
    """
    errors: list[str] = []
    errors.extend(_check_size(skill_md_text, byte_cap))

    frontmatter, body = _split_frontmatter(skill_md_text)
    if frontmatter is None:
        errors.append("SKILL.md has no YAML frontmatter block")
    else:
        errors.extend(_check_frontmatter(frontmatter, layout.name))

    errors.extend(_check_references(body, layout, incoming_files or set()))
    return ValidationResult(passed=not errors, errors=errors)


def _check_size(text: str, byte_cap: int) -> list[str]:
    """Flag a SKILL.md whose UTF-8 byte length exceeds `byte_cap`."""
    size = len(text.encode("utf-8"))
    if size <= byte_cap:
        return []
    return [f"SKILL.md is {size} bytes, exceeding the cap of {byte_cap} bytes"]


def _check_frontmatter(frontmatter: str, expected_name: str) -> list[str]:
    """Verify the frontmatter parses and has a matching `name` + `description`."""
    try:
        parsed = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        return [f"frontmatter is not valid YAML: {exc}"]

    if not isinstance(parsed, dict):
        return ["frontmatter does not parse to a mapping"]

    errors: list[str] = []
    name = parsed.get("name")
    if not name:
        errors.append("frontmatter is missing a non-empty 'name'")
    elif name != expected_name:
        errors.append(
            f"frontmatter 'name' is {name!r} but the skill folder is {expected_name!r}"
        )

    if not parsed.get("description"):
        errors.append("frontmatter is missing a non-empty 'description'")
    return errors


def _check_references(
    body: str, layout: SkillLayout, incoming_files: set[str]
) -> list[str]:
    """Flag referenced paths that are neither on disk nor about to be written."""
    errors: list[str] = []
    for ref in sorted(_referenced_paths(body)):
        if ref in incoming_files or (layout.root / ref).exists():
            continue
        errors.append(f"referenced file does not exist: {ref}")
    return errors


def _referenced_paths(body: str) -> set[str]:
    """Collect relative paths referenced by markdown links and inline-code spans."""
    refs: set[str] = set()
    for target in _MD_LINK_RE.findall(body):
        rel = _as_relative_path(target)
        if rel is not None:
            refs.add(rel)
    for span in _INLINE_CODE_RE.findall(body):
        candidate = span.strip()
        if _REL_PATH_RE.match(candidate):
            refs.add(_normalize(candidate))
    return refs


def _as_relative_path(target: str) -> str | None:
    """Return a normalized relative path for a link target, or None to skip it."""
    target = target.strip()
    if not target or target.lower().startswith(_SKIP_PREFIXES):
        return None
    # Drop any in-page anchor on a relative path (e.g. `doc.md#section`).
    target = target.split("#", 1)[0]
    if not target:
        return None
    return _normalize(target)


def _normalize(path: str) -> str:
    """Strip a leading `./` so references match how files sit under the folder."""
    return path[2:] if path.startswith("./") else path


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split SKILL.md into (frontmatter YAML, body); frontmatter is None if absent."""
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body
    return None, text
