---
doc_type: dev-guide
slug: document-ir-v2
component: pdf-to-word-backend
status: current
summary: DocumentIR v2 layout-aware schema contract for MinerU to Word rendering.
tags: [document-ir, mineru, parser, renderer, layout]
last_reviewed: 2026-06-03
---

# DocumentIR v2

DocumentIR v2 extends the P0 v1 contract with layout facts from MinerU. It keeps
parser facts separate from Word output decisions: the renderer owns Word-specific
styles and editable OOXML semantics, while v2 provides the fields needed to make
those decisions deterministic.

## Compatibility

- Existing `document-ir/v1` artifacts remain valid.
- New readers default missing `pages`, `layout`, `captions`, and `footnotes` to
  empty values.
- The v1 sequential renderer path remains the fallback when layout fields are
  missing.

## Root

- `schema_version`: `document-ir/v1` or `document-ir/v2`
- `metadata`: existing job/source/parser metadata
- `pages`: v2 page coordinate spaces
- `blocks`: ordered content blocks
- `assets`: external assets referenced by blocks
- `quality_flags`: parser/conversion warnings

## Pages

Each page stores MinerU coordinate-space facts:

- `index`: zero-based page index
- `width`, `height`: page size when available
- `coordinate_unit`: fixed `mineru`
- `metadata`: extra parser facts

## Block Layout

Each block may include `layout`:

- `page_index`: source page
- `bbox`: `(x1, y1, x2, y2)` in the page's MinerU coordinate space
- `role`: `body`, `page_header`, `page_footer`, or `page_number`
- `source_index`: original source order on the page
- `continuation_heights`: table continuation heights collected from later pages
- `column_hint`: optional `left`, `right`, or `wide`

Blocks also support `captions` and `footnotes` lists so visual annotations are
not collapsed into `text` or unstructured metadata.

## Renderer Semantic Consumption

The Word renderer consumes existing v1/v2 fields for editable output semantics:

- `type=heading` plus `level` maps to Word `Heading 1` / `Heading 2` /
  `Heading 3`, or a template-configured named style.
- `type=list` plus `list_items` maps to real Word numbering after common MinerU
  bullet markers are removed from visible text.
- `type=formula` uses `latex` first, then `text`, and normalizes common TeX
  fragments before rich text rendering.
- `type=table` uses `html` for the editable Word table. `captions` render before
  the table and `footnotes` render after it as table notes.
- Formula-like text in table cells and table notes is normalized before rendering
  when it matches supported simple TeX patterns.

These renderer semantics do not add new DocumentIR block types or change stored
artifact contracts. They also do not claim full visual layout recovery for TOC
leaders, complete landscape sections, long-table pagination, or formal Golden
Sample P0 quality pass.

## Translation Constraint

DocumentIR translation may rewrite text fields, list items, and table HTML text
nodes. It must preserve page records, block IDs, block order, layout, captions,
footnotes, and asset references.
