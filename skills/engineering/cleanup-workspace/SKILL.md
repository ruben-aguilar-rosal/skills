---
name: cleanup-workspace
description: >
  Tear down a finished Optiak ticket workspace: archive FOLLOW-UPS.md and the other loose files
  to workspace-archive, remove the clones, the Orca group and the folder workspace, and delete
  the folder. Also repairs "Unknown" rows left in the Orca sidebar. Use when a ticket is merged
  or dropped, when a workspace is finished with, or when workspace folders have piled up under
  ~/Developer/optiak.
---

# cleanup-workspace

The reverse of `/start-ticket`. A finished **workspace** becomes an archive folder and nothing
else.

You bring judgement — is this ticket really done, and is anything in there worth keeping.
`scripts/optiak_cleanup.py` brings the mechanics, and refuses to run over unsaved work.

## 1. Confirm the ticket is finished

```bash
orca linear issue OPT-1102 --json
ls -d ~/Developer/optiak/workspace-*
```

`Done` or `Canceled` means clean up. Anything earlier means ask the user first and say which
state it is in.

**Done when** the ticket state is known and, for a ticket short of Done, the user has said to
go ahead.

## 2. Look before you delete

```bash
python3 ~/.claude/skills/cleanup-workspace/scripts/optiak_cleanup.py OPT-1102 --dry-run
```

Reports every file it would archive, every clone, and the Orca group it would remove. Changes
nothing.

Read the archive list. Anything worth keeping that sits **inside** a clone rather than at the
workspace root is invisible to the script — move it to the workspace root now so it gets
archived.

**Done when** the dry run has been read and every file worth keeping sits at the workspace root.

## 3. Clear the two things that stop the run

**Unsaved work.** Uncommitted changes, untracked files, stashes, or a branch that is unpushed or
ahead of its upstream:

```
OPT-1102 still holds work:

  optiak
    - 3 uncommitted or untracked file(s)
    - branch 'opt-1102-dbt' is ahead 2
```

Show the user that list and let them choose: push it, discard it, or move the files to the
workspace root so they get archived.

`--force` removes the workspace anyway. Reach for it only when the user says the work is
disposable, and name what is being thrown away when you do.

**An unrecognised directory.** A folder at the workspace root that is neither a registered clone
nor a git repo:

```
unrecognised directory at the workspace root: optiak
```

The script stops rather than move a whole tree on a guess. Look inside it, move what matters to
the root as files, delete the rest.

**Done when** the dry run reports neither, or the user has chosen `--force` knowing what it
discards.

## 4. Remove it

```bash
python3 ~/.claude/skills/cleanup-workspace/scripts/optiak_cleanup.py OPT-1102
```

In order: archive the loose files to `~/Developer/optiak/workspace-archive/opt-1102/`, stop the
folder-workspace terminals, close every terminal tab belonging to each clone, remove each clone
from Orca, delete the group (which takes the folder workspace with it), delete the folder, and
drop the saved `optiak-work` session so `--continue` cannot point at a folder that is gone.

An archive name that already exists is kept: the incoming file lands beside it as
`FOLLOW-UPS.2.md`.

**Done when** the script exits 0.

## 5. Report

```
OPT-1102  removed ~/Developer/optiak/workspace-opt-1102
Archived  FOLLOW-UPS.md, NOTES.md  ->  workspace-archive/opt-1102/
Orca      group "OPT-1102 - DBT Tables" and its folder workspace
```

**Done when** the card is printed.

## "Unknown" rows in the sidebar

Only workspaces built before `/start-ticket` stopped registering clones as Orca projects have
any to remove, and only those leave rows. Expect one **Unknown** row per clone removed, and say
so in the report; a user who is not warned reads it as a failed cleanup. A workspace with no
registered clones leaves none.

Orca's sidebar keeps drawing a project row after `repo.rm` takes the project away over the
runtime socket. The row is a drawing artefact: `repo.list`, `projectGroup.list` and the saved
`orca-data.json` all agree the project is gone, measured after every cleanup. Restarting Orca
clears the rows, and nothing short of that does.

Sometimes the removal also strands a tab entry in the saved state, which survives a restart.
Repair those with the app closed:

```bash
python3 ~/.claude/skills/cleanup-workspace/scripts/optiak_cleanup.py --prune-orphans --dry-run
python3 ~/.claude/skills/cleanup-workspace/scripts/optiak_cleanup.py --prune-orphans
```

Orca owns `orca-data.json` while it runs and would write over the edit, so the script refuses
while the app is open. It backs the file up to `orca-data.json.pre-prune` before writing.

Reach for it only when the dry run finds stale keys. Rows with none behind them need a restart,
not a prune, and the sequence costs the user their running sessions: quit Orca, run the prune,
reopen Orca.

## The private surface

Orca publishes no CLI command for removing a group or a folder workspace. The script reaches the
runtime socket directly, the same way `/start-ticket` does. Methods: `projectGroup.list`,
`repo.list`, `repo.rm`, `folderWorkspace.list`, `projectGroup.delete`.

`projectGroup.delete` cascades: it removes the group **and** its folder workspaces, and sets
`projectGroupId` to null on member repos rather than removing them. So the repos come off first
and the group last.

Tabs are closed before `repo.rm` because a tab left open can survive in the saved state as an
orphan key. That is hygiene, not a cure for the **Unknown** rows: those appear with the tabs
already closed. Ruled out by measurement on Orca 1.4.190 — the order of `repo.rm` against
`projectGroup.delete`, `repo.reorder`, a no-op `repo.update`, and Cmd-R, which Orca does not
bind.

An Orca release can change any of this. The script raises on the first bad reply, and it
archives before it destroys, so a failure mid-run leaves the clones on disk.
