#!/usr/bin/env bash
#
# Batch re-vendor changed skills, reading `repo<TAB>path[<TAB>kind]` rows on
# stdin (the output of map_changes.py). Each row is re-onboarded verbatim via
# `skillsync add ... --no-pr`, which re-mirrors at HEAD, RE-RUNS THE SECURITY
# GATE, and bumps the pin only on a pass. Results are appended to a TSV so you
# can triage the non-`local` outcomes afterward.
#
# WHY THIS SCRIPT EXISTS (the pitfall it prevents):
#   `skillspector` is installed at ~/.local/bin (uv tool). If it is not on PATH
#   when `add` runs, the security gate is FAIL-SAFE: it quarantines every skill
#   and files a GitHub issue for each. A whole batch then produces dozens of
#   BOGUS quarantine issues. This script hard-prepends ~/.local/bin so the gate
#   can actually execute. Verify once before a batch:  command -v skillspector
#
# Usage (from repo root):
#   map_changes.py | skills/meta/sync-vendored-skills/scripts/revendor.sh
#   # dest override per source is already on each pin, so --dest is not needed
#   # for skills already tracked; it IS needed when adopting a NEW skill path.
#
# Env:
#   RESULTS   output TSV path (default: /tmp/revendor_results.txt)
#   DEST      optional --dest passed to every add (for adopting new skills)
#
set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

RESULTS="${RESULTS:-/tmp/revendor_results.txt}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SS="$ROOT/.venv/bin/skillsync"
[ -x "$SS" ] || SS="skillsync"   # fall back to PATH if no venv binary

if ! command -v skillspector >/dev/null 2>&1; then
  echo "FATAL: skillspector not on PATH — the gate would fail-safe-quarantine" \
       "every skill and file bogus issues. Install: uv tool install" \
       "git+https://github.com/NVIDIA/SkillSpector" >&2
  exit 1
fi

: > "$RESULTS"
cd "$ROOT"

while IFS=$'\t' read -r repo path kind _rest; do
  [ -z "${repo:-}" ] && continue
  args=(add "$repo" "$path" --no-pr)
  [ -n "${DEST:-}" ] && args+=(--dest "$DEST")
  out="$("$SS" "${args[@]}" 2>&1 | tail -1 || true)"
  printf '%s\t%s\t%s\n' "$repo" "$path" "$out" >> "$RESULTS"
  printf '%s\t%s\n' "$path" "$out"
done

echo "--- results written to $RESULTS ---"
echo "outcomes:"
awk -F'\t' '{n=split($3,a," "); print a[2]}' "$RESULTS" | sort | uniq -c
echo "non-local rows need triage (quarantined / invalid):"
grep -vE '\slocal$' "$RESULTS" || echo "  (all local — clean)"
