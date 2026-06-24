# DocumentIR renderer parity migration

## Goal

Migrate the mature local MinerU -> DOCX layout and semantic rendering rules from
the local `app/conversion/runtime_*` path into the formal
`document_jobs -> DocumentIR -> app/services/renderer/DocumentIRWordRenderer`
chain. The formal API path must reach parity for the current P0 Golden Sample
canonical suite instead of proving quality only through sandbox/local runtime
outputs.

## Requirements

* Keep public HTTP APIs, database schemas, persistence adapters, and document job
  workflow states stable.
* Preserve `DocumentIR` v2 as the formal interchange shape. Add fields only when
  existing facts cannot represent the required renderer behavior.
* Extract shared pure rules for text semantics, formula normalization,
  terminology/subscript replacement, MinerU content extraction, table decisions,
  and layout/page-flow heuristics so the local runtime and formal renderer stop
  drifting.
* Keep python-docx and OOXML writing responsibilities inside
  `app/services/renderer`.
* Make `DocumentJobExecutionService` pass formal renderer options, including the
  active subscript config path and document language.
* Extend formal DocumentIR conversion so nested `content_list_v2.json`,
  `middle.json` / `layout.json`, page decorations, visual metadata, table
  placeholders, captions, footnotes, and continuations survive into DocumentIR.
* Extend `DocumentIRWordRenderer` so formal generated DOCX covers heading, real
  Word lists, TOC dot leaders, formulas/symbols, captions/notes, editable
  tables, long/wide tables, page orientation, two-column regions, and image/table
  binding.
* Surface renderer and quality evidence through existing generated Word metadata
  keys such as `renderer_mode`, `layout_quality_flags`, `docx_quality`, and
  `quality_flags`.

## Acceptance Criteria

* [ ] Formal document job conversion handles both nested MinerU v2 pages and
      legacy flat content lists.
* [ ] Formal generated DOCX applies runtime subscript terminology rules.
* [ ] Formal generated DOCX has Word heading styles, real numbering, TOC tab
      leaders, and no manual-list/unstyled-heading regressions for covered
      samples.
* [ ] Formal generated DOCX has no LaTeX residue for covered formula/symbol
      samples, including overline, leading superscript, theta/psi/mu/degree, and
      sqrt cases.
* [ ] Caption-before-table/image, footnote-after-table/image, table header
      repeat/no-split, merge fallback, long table, and wide table behavior are
      covered by tests.
* [ ] Document job regression tests prove the behavior through
      `/api/v1/document-jobs`, not only direct renderer or local runtime calls.
* [ ] Targeted backend tests pass, including DocumentIR converter tests,
      DocumentIR renderer tests, document_jobs regressions, and local runtime
      characterization tests affected by shared-rule extraction.
* [ ] P0 Golden Sample acceptance path remains
      `scripts/ops/run_golden_sample_regression.py` against the formal API path.

## Definition of Done

* Tests added or updated for shared rules, DocumentIR conversion, renderer
  behavior, document_jobs integration, and relevant quality flags.
* Targeted test commands run and pass, or any skipped command is explicitly
  justified.
* No committed `tests/tmp`, generated DOCX/PDF/PNG, local API keys, or customer
  artifacts.
* Diff reviewed for duplicated rules, silent fallbacks, hidden second sources of
  truth, broad exception swallowing, and unrelated refactors.
* Trellis specs updated only if the implementation creates durable new backend
  conventions.

## Technical Approach

Implement this in small slices:

1. Add focused failing tests for current parity gaps.
2. Extract shared pure-rule modules under `app/conversion/docx_rules`.
3. Update local runtime modules and formal renderer modules to consume the shared
   rules.
4. Improve formal MinerU -> DocumentIR conversion for nested v2 and middle/layout
   metadata parity.
5. Add renderer options and wire document_jobs to pass subscript config and
   document language.
6. Extend renderer OOXML writing for missing parity behavior.
7. Run targeted and release-relevant tests, then fix regressions.

## Decision (ADR-lite)

**Context**: The previous phases hardened local runtime output, but P0 Golden
Sample reports still classify the formal API path as a pipeline parity gap.
Duplicating fixes separately in local runtime and formal renderer would preserve
drift.

**Decision**: Use shared pure-rule modules for cross-path semantics and keep
format-specific writing in the formal renderer. The formal document job path is
the acceptance path.

**Consequences**: The migration touches multiple layers but avoids public API or
schema churn. Runtime characterization tests must continue to pass after shared
rule extraction, proving the local path remains compatible.

## Out of Scope

* New public API routes, request/response fields, persistence schemas, or job
  workflow states.
* Rebuilding the Word template, changing Golden Sample PDFs, adding new P0
  samples, or committing generated acceptance artifacts.
* Replacing MinerU, translation providers, or the existing `python-docx` renderer
  stack.
* Frontend changes.

## Technical Notes

* Formal chain: `app/domains/document_jobs/execution.py` reads DocumentIR and
  calls `DocumentIRWordRenderer.render_to_bytes`.
* Formal DocumentIR converter: `app/services/document_ir/mineru_converter.py`
  and `app/services/document_ir/layout_signals.py`.
* Formal renderer: `app/services/renderer/word_renderer.py`,
  `text_renderer.py`, `table_renderer.py`, `image_renderer.py`,
  `layout_plan.py`, `template_config.py`, and `docx_quality.py`.
* Local mature rules: `app/conversion/runtime/input_adapter_runtime.py`,
  `page_layout_runtime.py`, `page_flow_runtime.py`, `text_rendering.py`,
  `render_config_runtime.py`, `table_render_runtime.py`, and
  `table_long_renderer.py`.
* P0 Golden Sample suite:
  `tests/fixtures/golden_samples/manifest.yaml` with `gs-003`, `gs-004`,
  `gs-006`, and `gs-008`.
