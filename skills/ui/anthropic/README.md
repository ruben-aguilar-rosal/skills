# UI / anthropic skills

Design and creative skills vendored verbatim from
[`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`).

These are the generic, non-Anthropic-specific design skills from Anthropic's public
skill repo. (The Anthropic-specific ones — `brand-guidelines`, `internal-comms` — are
deliberately not vendored.)

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `algorithmic-art` | Generative/algorithmic art with p5.js — flow fields, particle systems, seeded randomness, interactive parameter exploration. |
| `canvas-design` | Beautiful static art as `.png`/`.pdf` via a design philosophy — posters, designs, visual pieces. Ships ~50 bundled fonts. |
| `frontend-design` | Distinctive, intentional visual design when building or reshaping UI — aesthetic direction, typography, non-templated choices. |
| `theme-factory` | Style any artifact (slides, docs, HTML pages) with one of 10 preset themes, or generate a new theme on the fly. |

## How to use them

- **Automatic:** the agent picks a skill up from its `description` — describe the creative
  task ("make generative art", "design a poster", "give this page a theme") and the
  matching skill activates.
- **Explicit:** ask for one by name, e.g. *"use the `algorithmic-art` skill"*.
