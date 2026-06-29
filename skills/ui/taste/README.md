# UI / taste skills

Frontend **design-taste** skills vendored from
[`leonxlnx/taste-skill`](https://github.com/leonxlnx/taste-skill) (synced at
`06d6028`). Each skill is copied **verbatim** from upstream — the `.upstream/` folder
beside each `SKILL.md` is the pristine mirror used by the security scan; never hand-edit
it.

These are anti-slop design skills: they steer the agent away from generic, templated
"AI-looking" interfaces toward intentional, high-craft frontend output.

## Skills in this folder

| Folder | Skill id (`name`) | Use it for |
|---|---|---|
| `taste-skill/` | `design-taste-frontend` | Landing pages, portfolios, redesigns — reads the brief, infers a design direction, ships non-templated UIs. The general-purpose entry point. |
| `soft-skill/` | `high-end-visual-design` | Making a site feel **expensive**: agency-grade fonts, spacing, shadows, cards, motion; blocks cheap defaults. |
| `minimalist-skill/` | `minimalist-ui` | Clean editorial interfaces — warm monochrome, typographic contrast, flat bento grids, muted pastels. No gradients/heavy shadows. |
| `brutalist-skill/` | `industrial-brutalist-ui` | Raw mechanical look — Swiss print × military-terminal aesthetics, rigid grids, extreme type contrast. Good for data-heavy dashboards/editorial. |
| `redesign-skill/` | `redesign-existing-projects` | Upgrading an **existing** site/app: audits current design, removes generic AI patterns, applies premium standards without breaking functionality. |

> The agent loads a skill by its **`name`** (the `id` column), not the folder name — the
> two differ here because that is how upstream ships them.

## How to use them

- **Automatic:** the agent picks a skill up from its `description` (the trigger text in
  each `SKILL.md` frontmatter). Describe the design task — "build me a premium landing
  page", "redesign this app to look less generic" — and the matching skill activates.
- **Explicit:** ask for one by id, e.g. *"use the `minimalist-ui` skill"* or
  *"apply `redesign-existing-projects` to this project"*.
- **Pick by intent:** start from `design-taste-frontend` for new pages; reach for
  `high-end-visual-design`, `minimalist-ui`, or `industrial-brutalist-ui` when you want a
  specific aesthetic; use `redesign-existing-projects` when working on an existing
  codebase.

### Activate locally

Vendored skills are not linked into your Claude config by default. To symlink every
configured skill (including these) into `~/.claude/skills`:

```bash
uv run skillsync link
```

## Updating

These skills track upstream via `sources.yaml` (source `leonxlnx/taste-skill`,
`dest: skills/ui/taste`). To pull upstream changes:

```bash
uv run skillsync sync --skill taste-skill   # or omit --skill to sync all
```

Recorded gate overrides on these pins (see `sources.yaml`):

- **`accept_invalid` on all five** — each upstream `name` differs from its folder name, so
  the verbatim copy fails the `name == folder` validation rule by design.
- **`accept_findings: [P2]` on `taste-skill`** — SkillSpector flags a HIGH "Hidden
  Instructions"; reviewed as a false positive (a benign image-asset workflow rule that
  leaves a labeled `<!-- TODO -->` placeholder and asks the user to provide images).

A newly-introduced finding still blocks a future sync — these acceptances are scoped to
the exact rule IDs above.
