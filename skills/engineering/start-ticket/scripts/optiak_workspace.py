#!/usr/bin/env python3
"""Bootstrap an Optiak ticket workspace and register it with Orca as a group.

Creates ~/Developer/optiak/workspace-<ticket>/, clones the repositories the ticket
needs into it, prepares each clone with optiak-repo-setup, then tells Orca about it:
one project group, and one folder workspace over that group, linked to the Linear
issue. The folder workspace spans the whole folder, and the main agent runs there.

The clones are deliberately not registered as Orca projects. The agent reads them
from the folder workspace either way, so leaving them out keeps the sidebar to one
row per ticket and keeps repo.rm out of teardown.

The group and folder-workspace calls go through Orca's runtime socket, not the
public `orca` CLI, which has no command for either. That surface is private and can
change between Orca releases; every call fails loud rather than degrading.

Re-running on the same ticket reuses the group, the folder workspace and any clone
that is already there, so it is safe to call twice.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

RUNTIME_META = Path.home() / "Library/Application Support/Orca/orca-runtime.json"
DEVELOPER_ROOT = Path.home() / "Developer/optiak"
SSH_HOST = "github.com-optiak"
DEFAULT_OWNER = "optiak"


class Fail(Exception):
    pass


# ── Orca runtime ────────────────────────────────────────────────────────────────
# One JSON line in, one JSON line out, over the unix socket named in the runtime
# metadata file. Keepalive frames are interleaved and carry no result.

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
        request = {"id": f"optiak-workspace-{os.getpid()}", "authToken": meta["authToken"],
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


# ── shell ───────────────────────────────────────────────────────────────────────

def run(argv: list[str], cwd: Path | None = None) -> None:
    print(f"  $ {' '.join(argv)}", file=sys.stderr)
    result = subprocess.run(argv, cwd=cwd)
    if result.returncode != 0:
        raise Fail(f"command failed ({result.returncode}): {' '.join(argv)}")


# ── ticket ──────────────────────────────────────────────────────────────────────

def read_issue(ticket: str) -> dict:
    result = subprocess.run(["orca", "linear", "issue", ticket, "--json"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise Fail(f"orca linear issue {ticket} failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    if not payload.get("ok"):
        raise Fail(f"orca linear issue {ticket}: {payload.get('error')}")
    return payload["result"]["issue"]


# ── steps ───────────────────────────────────────────────────────────────────────

def clone_repos(workspace: Path, repos: list[str]) -> list[Path]:
    workspace.mkdir(parents=True, exist_ok=True)
    paths = []
    for repo in repos:
        owner, _, name = repo.rpartition("/")
        owner = owner or DEFAULT_OWNER
        target = workspace / name
        if (target / ".git").exists():
            print(f"  {name}: already cloned", file=sys.stderr)
        else:
            run(["git", "clone", f"git@{SSH_HOST}:{owner}/{name}.git", str(target)])
        paths.append(target)
    return paths


def ensure_group(workspace: Path, name: str) -> str:
    """The group carries the folder workspace, and nothing else.

    Registering each clone as an Orca project buys nothing: the main agent spans the whole
    folder and reads every repository from there. It costs, though — teardown then needs
    repo.rm, which strands a nameless row in the Orca sidebar until the app restarts.
    """
    for group in rpc("projectGroup.list")["groups"]:
        if group.get("parentPath") == str(workspace):
            print(f"  group: reusing '{group['name']}'", file=sys.stderr)
            return group["id"]
    result = rpc("projectGroup.create", {"name": name, "parentPath": str(workspace),
                                         "createdFrom": "manual"})
    print(f"  group: created '{name}'", file=sys.stderr)
    return result["group"]["id"]


def ensure_folder_workspace(group_id: str, workspace: Path, name: str, issue: dict) -> str:
    for existing in rpc("folderWorkspace.list")["folderWorkspaces"]:
        if existing.get("projectGroupId") == group_id:
            print(f"  workspace: reusing '{existing['name']}'", file=sys.stderr)
            return existing["id"]
    result = rpc("folderWorkspace.create", {
        "projectGroupId": group_id,
        "name": name,
        "folderPath": str(workspace),
        "createdWithAgent": "claude",
        "linkedTask": {"provider": "linear", "type": "issue", "number": 0,
                       "title": issue["title"], "url": issue["url"],
                       "linearIdentifier": issue["identifier"]},
    })
    print(f"  workspace: created '{name}'", file=sys.stderr)
    return result["folderWorkspace"]["id"]


# ── entry point ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="optiak_workspace.py",
        description="Bootstrap a ticket workspace and register it with Orca as a group.",
        epilog="example: optiak_workspace.py OPT-1102 --label 'DBT Tables' "
               "--repo optiak --repo iac-infra")
    parser.add_argument("ticket", help="Linear key, such as OPT-1102")
    parser.add_argument("--label", required=True,
                        help="Short name for the group, such as 'DBT Tables'")
    parser.add_argument("--repo", action="append", required=True, dest="repos",
                        metavar="REPO", help="Repository to clone; repeats. "
                                             "Bare name means the optiak org.")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args()

    ticket = args.ticket.upper()
    workspace = DEVELOPER_ROOT / f"workspace-{ticket.lower()}"

    issue = read_issue(ticket)
    clones = clone_repos(workspace, args.repos)
    run(["optiak-repo-setup", *[str(p) for p in clones]])
    group_id = ensure_group(workspace, f"{ticket} - {args.label}")
    folder_id = ensure_folder_workspace(group_id, workspace,
                                        f"{ticket} {issue['title']}", issue)

    result = {"ticket": ticket, "path": str(workspace), "groupId": group_id,
              "folderWorkspaceId": folder_id, "worktreeSelector": f"folder:{folder_id}",
              "repos": [p.name for p in clones]}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{ticket} ready at {workspace}")
        print(f"  repos     {', '.join(result['repos'])}")
        print(f"  selector  folder:{folder_id}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as error:
        print(f"optiak_workspace: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
