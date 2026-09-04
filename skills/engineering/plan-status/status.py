#!/usr/bin/env python3
"""Print a plan's Linear ticket board: table, blocking graph, frontier.

Reads Linear through the `linear api` CLI. Two queries, because asking for
descriptions and both relation directions at once exceeds Linear's complexity
ceiling.
"""
import argparse, json, re, subprocess, sys

DONE = {"completed", "canceled"}


def query(body):
    r = subprocess.run(["linear", "api", body], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"linear api failed: {r.stderr.strip() or r.stdout.strip()}")
    out = json.loads(r.stdout)
    if "errors" in out:
        sys.exit("linear api: " + out["errors"][0].get("message", "unknown error"))
    return out["data"]["project"]["issues"]["nodes"]


def milestone_filter(name):
    return f'projectMilestone:{{name:{{eq:{json.dumps(name)}}}}},' if name else ""


def gist(text, width=140):
    if not text:
        return "no description"
    lines, hit = text.splitlines(), False
    picked = None
    for ln in lines:
        if ln.startswith("#"):
            low = ln.lower()
            hit = "why" in low or "what happens" in low
            continue
        if hit and ln.strip():
            picked = ln.strip()
            break
    if picked is None:
        for ln in lines:
            s = ln.strip()
            if s and not s.startswith(("#", "|", ">", "`", "-", "*", "[")):
                picked = s
                break
    s = re.sub(r"[*`_]", "", re.sub(r"\s+", " ", picked or "no prose"))
    return s if len(s) <= width else s[: width - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Linear project slug id or UUID")
    ap.add_argument("--milestone", default="", help="milestone name, exact")
    ap.add_argument("--scope", choices=["all", "pending"], default="pending")
    a = ap.parse_args()

    mf = milestone_filter(a.milestone)

    graph = query(f'''{{ project(id:"{a.project}") {{ issues(first:80, filter:{{ {mf} }}) {{
        nodes {{ identifier title priority estimate state {{ name type }}
          inverseRelations(first:15) {{ nodes {{ type issue {{ identifier }} }} }} }} }} }} }}''')
    if not graph:
        sys.exit("no issues matched. Check the project id and the milestone name.")

    state = {n["identifier"]: n for n in graph}
    done = {k for k, n in state.items() if n["state"]["type"] in DONE}
    blockers = {
        n["identifier"]: [r["issue"]["identifier"]
                          for r in n["inverseRelations"]["nodes"] if r["type"] == "blocks"]
        for n in graph
    }

    scope = [n for n in graph if a.scope == "all" or n["identifier"] not in done]
    keys = {n["identifier"] for n in scope}

    gists = {}
    if scope:
        sf = "" if a.scope == "all" else 'state:{type:{nin:["completed","canceled"]}},'
        for n in query(f'''{{ project(id:"{a.project}") {{ issues(first:80, filter:{{ {mf} {sf} }}) {{
            nodes {{ identifier description }} }} }} }}'''):
            gists[n["identifier"]] = gist(n.get("description"))

    order = sorted(scope, key=lambda n: (n["identifier"] in done, len(
        [b for b in blockers[n["identifier"]] if b not in done]), n["identifier"]))

    print(f"## Tickets ({a.scope}: {len(scope)} of {len(graph)})\n")
    print(f"{'KEY':9} {'STATE':12} {'P':3} {'EST':4} DESCRIPTION")
    for n in order:
        k = n["identifier"]
        p = f"P{n['priority']}" if n["priority"] else "-"
        e = str(n["estimate"]) if n["estimate"] is not None else "-"
        print(f"{k:9} {n['state']['name']:12} {p:3} {e:4} {gists.get(k, '')}")

    print(f"\n## Blocking graph\n")
    any_edge = False
    for n in order:
        k = n["identifier"]
        bs = blockers[k]
        if not bs:
            continue
        any_edge = True
        marked = [b + (" ✓" if b in done else " ✗") for b in sorted(bs)]
        print(f"{k} ← {', '.join(marked)}")
    if not any_edge:
        print("no blocking relations on the tickets in scope")
    print("\n✓ done or canceled   ✗ still open")

    free = [n["identifier"] for n in graph
            if n["identifier"] not in done
            and not [b for b in blockers[n["identifier"]] if b not in done]]
    started = [k for k in free if state[k]["state"]["type"] == "started"]
    ready = [k for k in free if state[k]["state"]["type"] != "started"]

    print(f"\n## Frontier\n")
    print("in flight: " + (", ".join(sorted(started)) or "nothing"))
    print("pickable:  " + (", ".join(sorted(ready)) or "nothing"))
    unfilled = [k for k in ready
                if state[k]["estimate"] is None or not state[k]["priority"]]
    if unfilled:
        print("missing a priority or an estimate: " + ", ".join(sorted(unfilled)))


if __name__ == "__main__":
    main()
