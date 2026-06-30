#!/usr/bin/env python3
"""
run_cfm.py — run any CFM Tips cost-optimization tool WITHOUT the MCP server.

The aws-samples/sample-cfm-tips-mcp repo wraps ~59 read-only AWS cost-analysis
"runbooks" behind an MCP server. The server is just a transport: every tool is
dispatched by `mcp_server_with_runbooks.call_tool(name, arguments)`, a plain
coroutine that returns the same JSON the MCP client would receive.

This runner imports that coroutine and calls it directly, so the analyses run as
ordinary scripts driven by the agent / CLI — no MCP client, no server process.

SELF-CONTAINED: on first run it bootstraps everything it needs with no manual
setup — clones the upstream repo into a managed, git-ignored `vendor/` dir,
builds a dedicated virtualenv, installs the dependencies, and re-execs itself
with that interpreter. Subsequent runs are instant. It can be invoked with any
Python 3.11+ interpreter.

Usage:
    run_cfm.py <tool_name> [--arg KEY=VALUE ...] [--json '<json-object>']
    run_cfm.py --list                       # list available tools + arg schema
    run_cfm.py s3_quick_analysis --arg region=eu-west-1
    run_cfm.py get_cost_explorer_data \
        --json '{"start_date":"2026-06-01","end_date":"2026-06-30","granularity":"MONTHLY"}'

Arg typing for --arg KEY=VALUE: values are coerced to bool/int/float/JSON when
they parse, else left as a string. Use --json for arrays/objects/nested values.

AWS credentials come from the ambient environment (AWS_PROFILE, env vars, or an
instance/role) exactly like the AWS CLI. All tools are READ-ONLY — they call
Describe/List/Get APIs and return recommendations; they never modify resources.

Environment overrides:
    CFM_TIPS_HOME   path to an existing clone (skips bootstrap, takes precedence)
    CFM_TIPS_REF    git ref/tag/commit to check out after cloning (default: main)
    CFM_TIPS_REPO   clone URL (default: the aws-samples repo)
    --no-bootstrap  fail instead of cloning/installing if anything is missing
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys

REPO_URL = os.environ.get(
    "CFM_TIPS_REPO", "https://github.com/aws-samples/sample-cfm-tips-mcp.git"
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Managed clone lives under the skill's vendor/ dir (git-ignored, see .gitignore).
MANAGED_HOME = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "vendor", "sample-cfm-tips-mcp")
)
REEXEC_FLAG = "CFM_TIPS_REEXEC"


def _venv_python(home: str) -> str:
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python3"
    return os.path.join(home, ".venv", sub, exe)


def _resolve_home() -> str:
    """Pick the clone to use: explicit CFM_TIPS_HOME, else the managed vendor/ dir."""
    env = os.environ.get("CFM_TIPS_HOME")
    if env:
        return os.path.expanduser(env)
    return MANAGED_HOME


def _run(cmd, **kw):
    """Run a subprocess, streaming to stderr so the user sees bootstrap progress."""
    print(f"[cfm-tips bootstrap] $ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, check=True, stdout=sys.stderr, stderr=sys.stderr, **kw)


def _ensure_repo(home: str, allow_bootstrap: bool):
    if os.path.isdir(os.path.join(home, ".git")) or os.path.isfile(
        os.path.join(home, "mcp_server_with_runbooks.py")
    ):
        return
    if not allow_bootstrap:
        sys.exit(
            f"CFM Tips repo not found at {home!r} and --no-bootstrap was given.\n"
            f"Clone it manually: git clone {REPO_URL} {home}"
        )
    os.makedirs(os.path.dirname(home), exist_ok=True)
    _run(["git", "clone", "--depth", "1", REPO_URL, home])
    ref = os.environ.get("CFM_TIPS_REF")
    if ref:
        _run(["git", "-C", home, "fetch", "--depth", "1", "origin", ref])
        _run(["git", "-C", home, "checkout", ref])


def _ensure_venv(home: str, allow_bootstrap: bool):
    vpy = _venv_python(home)
    if os.path.isfile(vpy):
        return vpy
    if not allow_bootstrap:
        sys.exit(
            f"No virtualenv at {os.path.dirname(os.path.dirname(vpy))!r} and "
            f"--no-bootstrap was given.\n"
            f"Create it manually:\n"
            f"  python3 -m venv {home}/.venv\n"
            f"  {home}/.venv/bin/pip install -r {home}/requirements.txt"
        )
    _run([sys.executable, "-m", "venv", os.path.join(home, ".venv")])
    req = os.path.join(home, "requirements.txt")
    _run([vpy, "-m", "pip", "install", "--upgrade", "pip"])
    _run([vpy, "-m", "pip", "install", "-r", req])
    # The repo imports `mcp` everywhere but omits it from requirements.txt
    # (its setup.py declares required_packages = ['boto3', 'mcp']). Install it
    # explicitly so the dispatch coroutine imports without the MCP server.
    _run([vpy, "-m", "pip", "install", "mcp"])
    return vpy


def _deps_importable() -> bool:
    try:
        import mcp.types  # noqa: F401
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


def _bootstrap_and_maybe_reexec(home: str, allow_bootstrap: bool):
    """Make sure the repo + a usable interpreter exist; re-exec into the venv if needed.

    Returns once running under an interpreter that can import the deps and with
    the repo importable on sys.path.
    """
    _ensure_repo(home, allow_bootstrap)

    # If the current interpreter already has the deps, no re-exec needed.
    if _deps_importable():
        return

    if os.environ.get(REEXEC_FLAG):
        # We already re-execed into the venv but deps still won't import — give up.
        sys.exit(
            "CFM Tips dependencies are still not importable after bootstrap.\n"
            f"Inspect {home}/.venv and reinstall: "
            f"{_venv_python(home)} -m pip install -r {home}/requirements.txt"
        )

    vpy = _ensure_venv(home, allow_bootstrap)
    env = dict(os.environ, **{REEXEC_FLAG: "1", "CFM_TIPS_HOME": home})
    os.execve(vpy, [vpy, os.path.abspath(__file__), *sys.argv[1:]], env)


def _coerce(value: str):
    """Best-effort coercion of a --arg string into bool/int/float/JSON/str."""
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    if value and value[0] in "[{\"":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _load_server(home: str):
    sys.path.insert(0, home)
    os.chdir(home)  # the repo writes logs/ and reads relative paths
    import mcp_server_with_runbooks as server  # noqa: E402

    return server


def _print_tools(server):
    tools = asyncio.run(server.list_tools())
    print(f"{len(tools)} tools available:\n")
    for tool in sorted(tools, key=lambda t: t.name):
        schema = tool.inputSchema or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        args = ", ".join(
            f"{k}:{v.get('type', '?')}" + ("*" if k in required else "")
            for k, v in props.items()
        )
        desc = (tool.description or "").strip().splitlines()
        print(f"- {tool.name}({args})")
        if desc:
            print(f"    {desc[0][:140]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a CFM Tips cost-optimization tool directly (no MCP).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", nargs="?", help="Tool name (see --list)")
    parser.add_argument("--list", action="store_true", help="List tools and exit")
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Scalar argument; repeatable. Values are type-coerced.",
    )
    parser.add_argument(
        "--json",
        metavar="OBJECT",
        help="Full arguments object as a JSON string (merged after --arg).",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Path to the sample-cfm-tips-mcp clone (overrides auto-detection).",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Do not auto-clone/auto-install; fail if anything is missing.",
    )
    ns = parser.parse_args()

    if not ns.list and not ns.tool:
        parser.error("a tool name is required (or use --list)")

    home = os.path.expanduser(ns.home) if ns.home else _resolve_home()
    _bootstrap_and_maybe_reexec(home, allow_bootstrap=not ns.no_bootstrap)
    server = _load_server(home)

    if ns.list:
        _print_tools(server)
        return 0

    arguments = {}
    for item in ns.arg:
        if "=" not in item:
            parser.error(f"--arg must be KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        arguments[key] = _coerce(value)
    if ns.json:
        try:
            arguments.update(json.loads(ns.json))
        except json.JSONDecodeError as exc:
            parser.error(f"--json is not valid JSON: {exc}")

    result = asyncio.run(server.call_tool(ns.tool, arguments))

    # call_tool returns List[TextContent]; print the text payloads as-is.
    for block in result:
        text = getattr(block, "text", str(block))
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
