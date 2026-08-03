"""Tests for the upstream subtree path vocabulary.

The interesting case throughout is the repo ROOT — an upstream repo that *is* one
skill, with `SKILL.md` at the top level. It is spelled `.` (or an empty string) and
breaks the naive `path + "/"` / `path.rsplit("/")[-1]` idioms these helpers replace.
"""

import pytest

from skillsync.subtree import subtree_basename, subtree_pathspec, subtree_prefix


@pytest.mark.parametrize("subtree", [".", "", "  ", "./"])
def test_root_subtree_has_empty_prefix(subtree: str) -> None:
    """A root subtree contributes no prefix, so paths stay repo-relative as-is."""
    assert subtree_prefix(subtree) == ""


def test_nested_subtree_prefix_ends_in_slash() -> None:
    """A nested subtree's prefix is the path plus a separator."""
    assert subtree_prefix("skills/engineering/tdd") == "skills/engineering/tdd/"


def test_subtree_prefix_normalizes_trailing_slash() -> None:
    """A trailing slash does not produce a doubled separator."""
    assert subtree_prefix("skills/demo/") == "skills/demo/"


def test_prefix_join_leaves_root_paths_unprefixed() -> None:
    """Joining a root prefix yields `SKILL.md`, never the git-hostile `./SKILL.md`.

    `git show <ref>:./SKILL.md` fails against a bare mirror with "relative path
    syntax can't be used outside working tree", which is the bug this prevents.
    """
    assert subtree_prefix(".") + "SKILL.md" == "SKILL.md"


@pytest.mark.parametrize("subtree", [".", "", "  ", "./"])
def test_root_subtree_pathspec_is_dot(subtree: str) -> None:
    """As a git pathspec the root is `.` — git rejects an empty pathspec outright."""
    assert subtree_pathspec(subtree) == "."


def test_nested_subtree_pathspec_is_the_path() -> None:
    """A nested subtree passes through as its own pathspec, trailing slash trimmed."""
    assert subtree_pathspec("skills/demo/") == "skills/demo"


def test_root_pathspec_and_prefix_disagree_by_design() -> None:
    """The root spells `.` as a pathspec but `""` as a prefix — the whole point."""
    assert subtree_pathspec(".") == "."
    assert subtree_prefix(".") == ""


@pytest.mark.parametrize("subtree", [".", "", "./"])
def test_root_subtree_has_no_basename(subtree: str) -> None:
    """A root subtree has no name of its own — the caller must supply one."""
    assert subtree_basename(subtree) == ""


def test_subtree_basename_is_last_segment() -> None:
    """A nested subtree is named by its last path segment."""
    assert subtree_basename("skills/engineering/tdd") == "tdd"


def test_subtree_basename_ignores_trailing_slash() -> None:
    """A trailing slash does not yield an empty basename."""
    assert subtree_basename("skills/demo/") == "demo"
