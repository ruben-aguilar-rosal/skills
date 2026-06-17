# skillsync Build Runbook

How to build `skillsync` one step at a time, each in its own clean Claude Code session. The
steps are designed for exactly this: small, test-first, each ending green and committed so the
next session starts from a known-good state.

## Why one session per step
- Keeps context small and focused on the current step.
- A fresh session can't be derailed by earlier reasoning or dead ends.
- TDD works best when each step starts from the previous step's committed green state.

## The per-step ritual

For step **N** (P01 → P16, in order):

1. **Start a fresh session** at the repo root: `~/Developer/github/skills`.
2. **Paste the step file** `prompts/PNN-*.md` as your first message. It carries its own
   standing context (links to PLAN.md/BLUEPRINT.md, the global rules) plus the prompt — it is
   self-sufficient; you don't need to paste anything else.
3. Let the agent **write the failing test(s) first**, then implement, then show tests green.
4. **Verify** the step's checklist at the bottom of the file (tests green + the named command
   works).
5. **Commit** with the message suggested in the step file (`feat(pNN): ...`).
6. Update the task: mark task #N done.
7. Close the session. Start the next one.

## Order & dependencies (do not skip ahead)

```
Phase 0  Foundations         P01 scaffold → P02 config
Phase 1  Deterministic core  P03 git port → P04 layout → P05 detect → P06 gate → P07 validate
Phase 2  Agentic core        P08 LLM port → P09 advisory scan → P10 adapt → P11 reconcile
Phase 3  Output & wiring      P12 PR builder → P13 sync → P14 add → P15 regen/reprofile
                              → P16 link/status
```

Each step depends on the ones before it. P13 is the big integration point (wires P05–P12);
don't attempt it until P12 is green.

## Invariants the agent must respect every step
- Tests never touch the network or invoke real `claude` / `gh` — use the fakes in
  `skillsync/testing/fakes.py`.
- Side effects (git, fs, subprocess) stay behind injected ports; the core stays pure-ish.
- The deterministic stages (detect, gate, validate) contain zero LLM calls.
- Every step ends by integrating into the CLI or its caller — no orphaned code.

## Progress tracker

| Step | File | Task | Done |
| ---- | ---- | ---- | ---- |
| P01 | prompts/P01-scaffold.md | #1 | ☑ |
| P02 | prompts/P02-config.md | #2 | ☑ |
| P03 | prompts/P03-git-port.md | #3 | ☑ |
| P04 | prompts/P04-layout.md | #4 | ☑ |
| P05 | prompts/P05-detect.md | #5 | ☑ |
| P06 | prompts/P06-gate.md | #6 | ☑ |
| P07 | prompts/P07-validate.md | #7 | ☑ |
| P08 | prompts/P08-llm-port.md | #8 | ☑ |
| P09 | prompts/P09-advisory-scan.md | #9 | ☑ |
| P10 | prompts/P10-adapt.md | #10 | ☑ |
| P11 | prompts/P11-reconcile.md | #11 | ☐ |
| P12 | prompts/P12-pr-builder.md | #12 | ☐ |
| P13 | prompts/P13-sync.md | #13 | ☐ |
| P14 | prompts/P14-add.md | #14 | ☐ |
| P15 | prompts/P15-regen-reprofile.md | #15 | ☐ |
| P16 | prompts/P16-link-status.md | #16 | ☐ |

The full prompt set also lives in `PROMPTS.md` (single-file view).
