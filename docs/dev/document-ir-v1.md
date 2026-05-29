---
doc_type: dev-guide
slug: document-ir-v1
component: pdf-to-word-backend
status: draft
summary: DocumentIR v1 schema for the P0 MinerU to Word pipeline.
tags: [document-ir, mineru, parser, backend]
last_reviewed: 2026-05-29
---

# DocumentIR v1

DocumentIR v1 is the backend-owned intermediate representation between MinerU
raw output and Word rendering. It is intentionally small for P0: preserve block
order, keep traceable assets, and avoid encoding renderer-only style decisions.

## Root

- `schema_version`: fixed string `document-ir/v1`
- `metadata`: `job_id`, `source_file_id`, `document_language`, parser metadata
- `blocks`: ordered content blocks
- `assets`: external assets referenced by blocks
- `quality_flags`: parser/conversion warnings, for example missing images

## Blocks

Supported P0 block types:

- `heading`: `text`, `level`, optional page/bbox metadata
- `paragraph`: `text`
- `table`: optional `html`, optional caption text
- `image`: `asset_ref`, optional caption text
- `list`: `list_items`
- `formula`: `latex` or fallback text

Each block has a stable `id`, zero-based `order`, and optional `page_index`.

## Assets

Image assets are registered as `document_files` with `file_type=image_asset`.
The IR stores only references:

- `id`: asset id used by `block.asset_ref`
- `source_path`: path inside the MinerU raw result package
- `file_id`, `object_key`, `mime_type`, `checksum_sha256`: filled after upload

The DocumentIR JSON itself is registered as `file_type=document_ir`. MinerU raw
result packages are registered as `file_type=mineru_raw_result`.
