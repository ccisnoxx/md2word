---
doc_type: dev-guide
slug: document-ir-v2
component: pdf-to-word-backend
status: draft
summary: DocumentIR v2 layout-aware schema contract for MinerU to Word rendering.
tags: [document-ir, mineru, parser, renderer, layout]
last_reviewed: 2026-06-01
---

# DocumentIR v2

DocumentIR v2 extends the P0 v1 contract with layout facts from MinerU. The
renderer still owns Word-specific style decisions; v2 only stores parser facts
that are needed to build a layout plan.

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

## Translation Constraint

DocumentIR translation may rewrite text fields, list items, and table HTML text
nodes. It must preserve page records, block IDs, block order, layout, captions,
footnotes, and asset references.
