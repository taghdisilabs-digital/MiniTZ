# 51 — Markdown & Notes Workspace

## Purpose
A first-class Biella workspace for Markdown, plain-text notes, project instructions, implementation notes, research notes, and durable technical writing. The workspace must behave like an engineering tool, not a generic note pad.

## Required detailed content
1. **File tree & collections** — project-scoped `.md`, `.txt`, `.json`, `.yaml`, `.toml`, and note collections with folder hierarchy, pinned files, recent files, and source-path display.
2. **Markdown source editor** — syntax highlighting, line numbers, headings, lists, tables, code fences, task checkboxes, links, images, footnotes, front matter, and search/replace.
3. **Rendered preview** — side-by-side and single-pane preview modes, heading anchors, code highlighting, tables, callouts, internal links, and responsive layout preview.
4. **Document outline** — live H1–H6 tree, symbol navigation, section collapse, heading reorder, section word/token counts, and unresolved-link warnings.
5. **Backlinks & relationships** — inbound links, outbound links, related documents, tags, project scope, source provenance, and knowledge-link candidates.
6. **Metadata inspector** — filename, exact path, size, modified time, content digest, project namespace, document type, owner/source, status, and revision identity.
7. **Version history & autosave** — revision timeline, compare, restore, branch/current version indicators, autosave state, dirty-state indicator, and explicit save/export.
8. **Search & statistics** — full-text search, regex, tag filters, word count, token estimate, headings, links, code blocks, unresolved references, and document health.

## Core interactions
- Open multiple documents in tabs without losing unsaved state.
- Toggle source / preview / split modes.
- Navigate from outline or backlinks directly to exact sections.
- Preserve exact source bytes when a document is treated as evidence.
- Keep Project notes separate from Engine knowledge and Historical Evidence.

## Implementation data model
- `document_id`
- `project_id`
- `logical_path`
- `content_digest`
- `revision_id`
- `document_kind`
- `scope`
- `tags[]`
- `links[]`
- `source_ref`
- `modified_at`

## Visual requirements — BIELLA VISUAL LOCK
Transparent background. Deep graphite/navy component surfaces. Biella violet dominant accent. Electric cyan secondary accent. Green/amber/red only for semantic status. Thin precision borders, subtle glass, restrained bloom, compact technical typography, dense production-workstation layout, modular implementation-ready panels.

## Acceptance
The tablet should visibly contain at least the eight detailed modules above and look like a real Markdown/engineering documentation surface that could be implemented directly in Biella Engine.
