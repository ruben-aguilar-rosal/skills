"""Upstream subtree path vocabulary — pure string helpers, no git, no I/O.

A pin's `path` names a subtree inside its upstream repo. Usually that is a nested
folder (`skills/engineering/tdd`), but it may also be the repo ROOT — a repo that
*is* one skill, with `SKILL.md` at the top level, written as `.` (or an empty
string).

The root case breaks the naive `path + "/"` and `path.rsplit("/")[-1]` idioms:
`./SKILL.md` is a relative path git rejects against a bare mirror, and `.` is not a
usable folder name. These helpers are the single place that normalization lives, so
detect, the git port, and the layout join all agree on it.

Note the root subtree normalizes THREE different ways, which is exactly why this
is centralized: as a git pathspec it is `.` (git rejects an empty pathspec), as a
path prefix it is `""` (so joins yield `SKILL.md`, not `./SKILL.md`), and as a
folder name it is `""` (there is none — the caller must supply one).
"""

# Subtree spellings that mean "the whole repo".
_ROOT_SPELLINGS = {"", "."}


def subtree_pathspec(subtree: str) -> str:
    """Return `subtree` as a git pathspec, `"."` for the repo root.

    Git rejects an empty pathspec (`fatal: empty string is not a valid pathspec`),
    so the root spells as `.` here — the opposite of `subtree_prefix`, which must
    yield `""` for the same input.
    """
    cleaned = subtree.strip().rstrip("/")
    return "." if cleaned in _ROOT_SPELLINGS else cleaned


def subtree_prefix(subtree: str) -> str:
    """Return the repo-relative path prefix for `subtree`, `""` for the repo root.

    Joining this onto a subtree-relative path yields the repo-relative path, so a
    root subtree yields the path unchanged (`SKILL.md`, never `./SKILL.md`).
    """
    cleaned = subtree.strip().rstrip("/")
    return "" if cleaned in _ROOT_SPELLINGS else cleaned + "/"


def subtree_basename(subtree: str) -> str:
    """Return `subtree`'s last path segment, or `""` for the repo root.

    The default local folder name for a skill. The empty return is meaningful: a
    root subtree has no name of its own, so the caller must supply one.
    """
    cleaned = subtree.strip().rstrip("/")
    if cleaned in _ROOT_SPELLINGS:
        return ""
    return cleaned.rsplit("/", 1)[-1]
