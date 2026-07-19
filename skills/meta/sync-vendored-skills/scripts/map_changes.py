#!/usr/bin/env python3
"""Detect upstream changes and print a TSV the batch re-vendor consumes.

Runs skillsync's own `detect` stage (so the logic never drifts from the CLI),
then maps each changed/new/removed skill *folder name* back to the
`repo<TAB>skill_path<TAB>kind` its pin records. That mapping is what `add`
needs (it takes repo + subpath, not the folder name).

Usage (from the repo root):
    .venv/bin/python skills/meta/sync-vendored-skills/scripts/map_changes.py
    # or restrict to one source repo:
    .venv/bin/python .../map_changes.py --repo mattpocock/skills

Output columns: repo <TAB> skill_path <TAB> kind
`kind` is skillsync's own classification: `changed`, `new`, `removed`, ... .
A `removed` row is the rename/deletion signal — the pin's upstream subtree no
longer has a SKILL.md; decide adopt-renamed vs drop (see the SKILL.md).
Only rows needing action are printed; unchanged skills are omitted.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", help="only report skills from this source repo")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument(
        "--config", default="sources.yaml", help="path to sources.yaml"
    )
    args = ap.parse_args()

    try:
        from skillsync.config import load_config
        from skillsync.ports.git_cli import GitCli
        from skillsync.stages.detect import detect
    except ImportError:
        sys.stderr.write(
            "skillsync not importable — run via the project venv:\n"
            "  .venv/bin/python <this script>\n"
        )
        return 2

    cfg = load_config(Path(args.config))
    changes = detect(cfg, GitCli(), Path(args.root))

    # index folder-name -> (repo, path) from the config so we can map back
    index: dict[str, tuple[str, str]] = {}
    for src in cfg.sources:
        if args.repo and src.repo != args.repo:
            continue
        for pin in src.skills:
            name = pin.path.rstrip("/").rsplit("/", 1)[-1]
            index[name] = (src.repo, pin.path)

    rows = 0
    for c in changes:
        if c.kind == "none":
            continue
        hit = index.get(c.name)
        if hit is None:
            continue  # filtered out by --repo, or not a tracked pin
        repo, path = hit
        sys.stdout.write(f"{repo}\t{path}\t{c.kind}\n")
        rows += 1

    sys.stderr.write(f"{rows} skill(s) need action\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
