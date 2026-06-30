# Document skills

Office-document skills vendored verbatim from
[`anthropics/skills`](https://github.com/anthropics/skills) (synced at `3541475`).

These create, read, and edit `.docx`/`.pptx`/`.xlsx`/`.pdf` files. They bundle a
`scripts/office/` toolkit (LibreOffice helpers + OOXML schemas).

> **Overlap note:** the installed `document-skills` plugin also provides docx/pdf/pptx/xlsx.
> These are a repo-pinned copy; if both are linked, expect duplicate skills by the same
> `name` and pick which to activate.

## Skills in this folder

| Folder / id (`name`) | Use it for |
|---|---|
| `docx` | Create/read/edit Word documents — formatting, TOC, headings, images, tracked changes, comments, find-and-replace. |
| `pdf` | Anything with PDFs — extract text/tables, merge/split, rotate, watermark, fill forms, encrypt/decrypt, OCR. |
| `pptx` | Create/read/edit PowerPoint decks — slides, layouts, templates, speaker notes, comments; combine/split. |
| `xlsx` | Create/read/edit spreadsheets (`.xlsx`/`.xlsm`/`.csv`/`.tsv`) — formulas, formatting, charts, cleaning messy data. |

## How to use them

- **Automatic:** the agent picks a skill up from its `description` — reference a file by
  name or ask for a Word/PDF/deck/spreadsheet deliverable and the matching skill activates.
- **Explicit:** ask for one by name, e.g. *"use the `xlsx` skill"*.
