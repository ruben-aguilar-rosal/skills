#!/usr/bin/env python3
"""Show the exact flagged content behind a skillspector gate finding.

The quarantine issue lists rule IDs and one-line explanations, but you must
NEVER accept a finding without reading the actual flagged line. This prints,
per HIGH/CRITICAL (blocking) finding, the rule id, file:line, the matched
token, and the surrounding code snippet skillspector captured — enough to
judge false-positive vs real without leaving the terminal.

Usage:
    triage_finding.py <skill-dir>              # all blocking findings
    triage_finding.py <skill-dir> --all        # include MEDIUM/LOW too

<skill-dir> is the upstream copy you cloned to /tmp (the scan surface), e.g.
    /tmp/mp-check/skills/engineering/to-tickets

Requires `skillspector` on PATH (uv tool install puts it at ~/.local/bin).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

BLOCKING = {"HIGH", "CRITICAL"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("skill_dir")
    ap.add_argument(
        "--all", action="store_true", help="include non-blocking findings"
    )
    args = ap.parse_args()

    # make sure the uv-tool bin dir is reachable
    os.environ["PATH"] = (
        os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", "")
    )

    try:
        proc = subprocess.run(
            ["skillspector", "scan", args.skill_dir, "--no-llm", "--format", "json"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "skillspector not found on PATH. Install:\n"
            "  uv tool install git+https://github.com/NVIDIA/SkillSpector\n"
        )
        return 2

    if not proc.stdout.strip():
        sys.stderr.write(f"no scanner output (exit {proc.returncode}):\n{proc.stderr}\n")
        return 2

    data = json.loads(proc.stdout)
    ra = data.get("risk_assessment", {})
    print(
        f"overall: score={ra.get('score')} severity={ra.get('severity')} "
        f"recommendation={ra.get('recommendation')}\n"
    )

    shown = 0
    for i in data.get("issues", []):
        sev = i.get("severity")
        if not args.all and sev not in BLOCKING:
            continue
        loc = i.get("location", {})
        f = loc.get("file") or loc.get("file_path", "?")
        line = loc.get("start_line")
        blocking = " [BLOCKING]" if sev in BLOCKING else ""
        print(f"=== {i.get('id')} {sev}{blocking}  {f}:{line} ===")
        print(f"  category : {i.get('category')} / {i.get('pattern','')}")
        print(f"  matched  : {i.get('finding')!r}")
        snippet = i.get("code_snippet") or i.get("explanation", "")
        if snippet:
            for ln in str(snippet).splitlines()[:8]:
                print(f"    | {ln}")
        print(f"  rule id to accept if benign:  {i.get('id')}")
        print()
        shown += 1

    if shown == 0:
        print("no blocking findings." if not args.all else "no findings.")
    else:
        print(
            f"{shown} finding(s). If benign, record narrowly:\n"
            "  accept_findings: [<rule_id>]   on that skill's pin in sources.yaml\n"
            "and state the justification in the PR. A suspicious finding is a STOP."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
