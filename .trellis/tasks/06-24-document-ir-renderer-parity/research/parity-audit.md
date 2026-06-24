# DocumentIR renderer parity audit

## Formal chain

The formal API chain is:

`document_jobs -> MinerUToDocumentIRService -> document_ir_v2.json -> build_layout_plan -> DocumentIRWordRenderer -> generated_word metadata`.

The renderer is called from `DocumentJobExecutionService` and currently records
`renderer_mode`, layout counts, `layout_quality_flags`, `docx_quality`, and
`quality_flags` in generated Word metadata.

## Local runtime capabilities to align

The local `app/conversion/runtime_*` path already contains mature rules for:

* nested `content_list_v2.json` parsing, legacy content-list parsing, and
  `middle/layout.json` page/visual metadata extraction;
* table placeholder continuation collection and visual metadata backfill;
* formula normalization including TeX wrappers, Greek symbols, degree/micro
  symbols, overline, and leading superscript fragments;
* TOC detection, TOC dot leaders, source-positioned two-column TOC, and TOC
  continuation pages;
* Word heading/list rendering, cover title detection, and product intro
  extraction;
* table caption/footnote rendering, section-like caption style selection,
  header repeat/no-split rows, merge fallback, long simple tables, page-flow
  estimates, and wide table handling;
* runtime terminology/subscript YAML replacement;
* English document style overrides.

## Formal chain gaps

The formal converter currently captures useful v2 layout facts, captions,
footnotes, assets, page size, column hints, and continuation heights, but it is
weaker than the local runtime for nested MinerU v2 content, middle visual
backfill, TOC list splitting, footnote fragment merge, and table placeholder
handling across pages.

The formal renderer already covers basic heading/list/formula/table/image
semantics and some v2 layout planning, but it lacks formal subscript config
input, complete runtime formula parity, long-table/page-flow parity, TOC
two-column page handling, dense-section page breaks, and some table/caption
policy parity.

## Migration boundary

Pure decisions should be shared under a conversion/docx rules package. The
formal renderer should keep only python-docx/OOXML writing and DocumentIR adapter
logic. The formal `DocumentIR` schema should remain stable unless a required
source fact has no existing representation.
