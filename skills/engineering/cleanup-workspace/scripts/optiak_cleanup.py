#!/usr/bin/env python3
"""Tear down an Optiak ticket workspace: archive the loose files, then remove everything.

Refuses to touch a workspace whose clones still hold work: uncommitted changes, untracked
files, unpushed commits or stashes all stop the run and are reported. --force overrides.

Loose files at the workspace root (FOLLOW-UPS.md, NOTES.md, spike scripts, logs) move to
~/Developer/optiak/workspace-archive/<ticket>/ before anything is deleted. A name already in
the archive is kept: the incoming file lands beside it with a numeric suffix.

Orca state comes off through the runtime socket, the same private surface start-ticket uses.
Order matters: every terminal tab belonging to a clone is closed first, because repo.rm leaves
its tabs behind and Orca then draws each orphan tab as an unnamed "Unknown" row. Then repo.rm
per clone, then projectGroup.delete, which takes the folder workspace with it.

--prune-orphans is the repair pass for rows an earlier removal already stranded. It edits the
saved state directly, so it refuses to run while Orca is open.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RUNTIME_META = Path.home() / "Library/Application Support/Orca/orca-runtime.json"
ORCA_DATA = (Path.home()
             / "Library/Application Support/Orca/profiles/local-default/orca-data.json")
DEVELOPER_ROOT = Path.home() / "Developer/optiak"
ARCHIVE_ROOT = DEVELOPER_ROOT / "workspace-archive"
SESSION_DIR = Path.home() / ".claude/optiak-work"
IGNORED_NAMES = {".DS_Store"}
SESSION_TAB_SECTIONS = ("tabsByWorktree", "unifiedTabs", "tabGroups")


class Fail(Exception):
    pass


# ── Orca runtime ────────────────────────────────────────────────────────────────
# Twin of the client in the start-ticket skill: one JSON line in, one JSON line out.

def rpc(method: str, params: dict | None = None) -> dict:
    if not RUNTIME_META.exists():
        raise Fail(f"Orca is not running: no {RUNTIME_META}. Start it with 'orca open'.")
    meta = json.loads(RUNTIME_META.read_text())
    try:
        endpoint = next(t["endpoint"] for t in meta["transports"] if t["kind"] == "unix")
    except StopIteration:
        raise Fail("Orca runtime exposes no unix transport.")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(120)
    try:
        sock.connect(endpoint)
        request = {"id": f"optiak-cleanup-{os.getpid()}", "authToken": meta["authToken"],
                   "method": method, "params": params}
        sock.sendall((json.dumps(request) + "\n").encode())
        buffer = b""
        while True:
            if b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if line.strip():
                    frame = json.loads(line)
                    if "_keepalive" in frame:
                        continue
                    if not frame.get("ok"):
                        error = frame.get("error", {})
                        raise Fail(f"{method}: {error.get('code')}: {error.get('message')}")
                    return frame["result"]
                continue
            chunk = sock.recv(65536)
            if not chunk:
                raise Fail(f"{method}: Orca closed the connection without a reply.")
            buffer += chunk
    finally:
        sock.close()


# ── git ─────────────────────────────────────────────────────────────────────────

def git(clone: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=clone, capture_output=True, text=True)
    if result.returncode != 0:
        raise Fail(f"git {' '.join(args)} in {clone.name}: {result.stderr.strip()}")
    return result.stdout.strip()


def unsaved_work(clone: Path) -> list[str]:
    """Every reason this clone still holds something worth keeping."""
    problems = []

    dirty = git(clone, "status", "--porcelain")
    if dirty:
        problems.append(f"{len(dirty.splitlines())} uncommitted or untracked file(s)")

    if git(clone, "stash", "list"):
        problems.append("stashed changes")

    refs = git(clone, "for-each-ref", "--format=%(refname:short)\t%(upstream:short)\t%(upstream:track)",
               "refs/heads")
    for line in filter(None, refs.splitlines()):
        branch, _, rest = line.partition("\t")
        upstream, _, track = rest.partition("\t")
        if not upstream:
            problems.append(f"branch '{branch}' was never pushed")
        elif "ahead" in track:
            problems.append(f"branch '{branch}' is {track.strip('[]')}")

    return problems


# ── steps ───────────────────────────────────────────────────────────────────────

def find_group(workspace: Path) -> dict | None:
    for group in rpc("projectGroup.list")["groups"]:
        if group.get("parentPath") == str(workspace):
            return group
    return None


def member_repos(group_id: str) -> list[dict]:
    return [r for r in rpc("repo.list")["repos"] if r.get("projectGroupId") == group_id]


def close_tabs(repo_id: str, dry_run: bool) -> int:
    """Close every terminal tab of a repo. repo.rm strands the ones left open."""
    listing = subprocess.run(["orca", "terminal", "list", "--json"],
                             capture_output=True, text=True)
    if listing.returncode != 0:
        raise Fail(f"orca terminal list failed: {listing.stderr.strip()}")
    handles = [t["handle"] for t in json.loads(listing.stdout)["result"]["terminals"]
               if (t.get("worktreeId") or "").startswith(f"{repo_id}::")]
    if not dry_run:
        for handle in handles:
            subprocess.run(["orca", "terminal", "close", "--terminal", handle, "--tab",
                            "--json"], capture_output=True)
    return len(handles)


def archive(workspace: Path, clones: set[str], ticket: str, dry_run: bool) -> list[str]:
    loose = [p for p in sorted(workspace.iterdir())
             if p.name not in clones and p.name not in IGNORED_NAMES]

    # A directory that is neither a known clone nor a git repo is something this script cannot
    # classify. Moving a whole tree on a guess is worse than stopping.
    strays = [p for p in loose if p.is_dir()]
    if strays:
        raise Fail("unrecognised director"
                   + ("ies" if len(strays) > 1 else "y")
                   + f" at the workspace root: {', '.join(p.name for p in strays)}. "
                     "Move what matters to the root as files, delete the rest, then run again.")
    if not loose:
        return []

    destination = ARCHIVE_ROOT / ticket.lower()
    moved = []
    for source in loose:
        target = destination / source.name
        suffix = 2
        while target.exists():
            target = destination / f"{source.stem}.{suffix}{source.suffix}"
            suffix += 1
        moved.append(f"{source.name} -> {target.relative_to(ARCHIVE_ROOT)}")
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    return moved


def prune_orphans(dry_run: bool) -> int:
    """Drop saved tab entries whose checkout is gone: the 'Unknown' sidebar rows.

    Orca owns this file while it runs and would overwrite the edit, so this only runs with the
    app closed. Startup then reads the pruned state.
    """
    if RUNTIME_META.exists():
        raise Fail("Orca is running. Quit it first, then run --prune-orphans.")
    if not ORCA_DATA.exists():
        raise Fail(f"no Orca state at {ORCA_DATA}")

    data = json.loads(ORCA_DATA.read_text())
    session = data.get("workspaceSession") or {}
    removed = 0
    for name in SESSION_TAB_SECTIONS:
        section = session.get(name)
        if not isinstance(section, dict):
            continue
        for key in list(section):
            path = key.split("::", 1)[1].split("::")[0] if "::" in key else ""
            if path and not os.path.isdir(path):
                print(f"  {name}: {Path(path).name}")
                del section[key]
                removed += 1

    if removed and not dry_run:
        backup = ORCA_DATA.with_suffix(".json.pre-prune")
        shutil.copy2(ORCA_DATA, backup)
        ORCA_DATA.write_text(json.dumps(data, indent=2))
        print(f"  backup: {backup}")
    return removed


# ── entry point ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="optiak_cleanup.py",
        description="Archive a ticket workspace and remove it from disk and from Orca.",
        epilog="example: optiak_cleanup.py OPT-1102 --dry-run")
    parser.add_argument("ticket", nargs="?", help="Linear key, such as OPT-1102")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report every change and make none")
    parser.add_argument("--force", action="store_true",
                        help="Remove the workspace even when a clone holds unsaved work")
    parser.add_argument("--prune-orphans", action="store_true",
                        help="Repair pass: drop saved tab entries for checkouts that are gone, "
                             "which is what Orca draws as 'Unknown' rows. Needs Orca closed.")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args()

    if args.prune_orphans:
        removed = prune_orphans(args.dry_run)
        verb = "would drop" if args.dry_run else "dropped"
        print(f"{verb} {removed} orphan tab entr" + ("y" if removed == 1 else "ies"))
        if removed:
            print("Reopen Orca; the Unknown rows are gone.")
        return 0

    if not args.ticket:
        parser.error("a ticket is required unless --prune-orphans is given")

    ticket = args.ticket.upper()
    workspace = DEVELOPER_ROOT / f"workspace-{ticket.lower()}"
    if not workspace.is_dir():
        raise Fail(f"no workspace at {workspace}")

    group = find_group(workspace)
    repos = member_repos(group["id"]) if group else []
    clones = {Path(r["path"]).name for r in repos}
    # A clone Orca never learned about still counts as a clone, not a loose file.
    clones |= {p.name for p in workspace.iterdir() if (p / ".git").exists()}

    # 1. Refuse a workspace that still holds work.
    blocked = {}
    for name in sorted(clones):
        problems = unsaved_work(workspace / name)
        if problems:
            blocked[name] = problems
    if blocked and not args.force:
        print(f"{ticket} still holds work:\n", file=sys.stderr)
        for name, problems in blocked.items():
            print(f"  {name}", file=sys.stderr)
            for problem in problems:
                print(f"    - {problem}", file=sys.stderr)
        print("\nPush or discard it, then run again. --force removes it anyway.",
              file=sys.stderr)
        return 2

    # 2. Archive the loose files before anything is destroyed.
    moved = archive(workspace, clones, ticket, args.dry_run)

    # 3. Orca state: terminals, then repos, then the group (which takes the folder
    #    workspace with it).
    folder_workspaces = [w for w in rpc("folderWorkspace.list")["folderWorkspaces"]
                         if group and w.get("projectGroupId") == group["id"]]
    closed = 0
    if not args.dry_run:
        for folder_workspace in folder_workspaces:
            subprocess.run(["orca", "terminal", "stop", "--worktree",
                            f"folder:{folder_workspace['id']}", "--json"],
                           capture_output=True)
        for repo in repos:
            closed += close_tabs(repo["id"], args.dry_run)
            rpc("repo.rm", {"repo": f"id:{repo['id']}"})
        if group:
            rpc("projectGroup.delete", {"groupId": group["id"]})

        # 4. Disk, then the saved optiak-work session, which now points nowhere.
        shutil.rmtree(workspace)
        for leftover in (SESSION_DIR / ticket.lower(), SESSION_DIR / f"{ticket.lower()}.dir"):
            leftover.unlink(missing_ok=True)

    result = {"ticket": ticket, "dryRun": args.dry_run, "path": str(workspace),
              "archived": moved, "repos": sorted(clones),
              "group": group["name"] if group else None,
              "folderWorkspaces": [w["name"] for w in folder_workspaces],
              "forcedOverUnsavedWork": sorted(blocked) if args.force else []}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        head = "would remove" if args.dry_run else "removed"
        print(f"{ticket} {head} {workspace}")
        print(f"  repos     {', '.join(result['repos']) or 'none'}")
        print(f"  group     {result['group'] or 'none registered'}")
        print(f"  archived  {len(moved)} file(s)")
        for line in moved:
            print(f"            {line}")
        if result["forcedOverUnsavedWork"]:
            print(f"  FORCED over unsaved work in "
                  f"{', '.join(result['forcedOverUnsavedWork'])}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as error:
        print(f"optiak_cleanup: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
