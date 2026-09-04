# Measure the diff

The number that decides whether work fits one pull request. `/ship` reads it to route;
`/split-pr` reads it to decide whether a stack is needed at all.

**The limit is 400 added and 400 removed**, counting nothing generated.

## The commands

```bash
git fetch origin
BASE=$(git remote show origin | sed -n 's/.*HEAD branch: //p')

GEN='uv.lock|pnpm-lock.yaml|package-lock.json|poetry.lock|.terraform.lock.hcl|go.sum'

# committed, plus staged and unstaged
{ git diff --numstat origin/$BASE...HEAD; git diff --numstat HEAD; } \
  | grep -Ev "($GEN)$" | awk '{a+=$1; r+=$2} END{printf "tracked   +%d -%d\n", a, r}'

# files git has never seen count as added lines
git ls-files --others --exclude-standard | grep -Ev "($GEN)$" \
  | tr '\n' '\0' | xargs -0 -r cat | wc -l \
  | awk '{printf "untracked +%d -0\n", $1}'
```

Add the two `+` numbers together, and the two `-` numbers together. That pair is the size.

## What the commands cover, and why each part is there

- **`origin/$BASE...HEAD`** is the committed work, against the merge base.
- **`git diff HEAD`** is staged and unstaged work. A fast ship happens before the commit, so
  leaving this out reports a branch as empty while the change sits in the working tree.
- **`git ls-files --others`** is a new file. Neither diff above can see one, and a new file is
  usually the largest thing in a diff.
- **`$GEN`** drops lock files. A dependency bump rewrites thousands of lines that nobody reads,
  and it would send every bump to `/split-pr`.

A rename shows as `0 0 old => new` and costs nothing. That is correct.

## Report it like this

```
tracked   +60 -26
untracked +1197 -0
total     +1257 -26   → over 400, needs a stack
```
