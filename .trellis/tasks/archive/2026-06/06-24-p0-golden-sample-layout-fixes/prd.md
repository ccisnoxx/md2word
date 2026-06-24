# Fix P0 Golden Sample Page Orientation And Caption Classification

## Goal

Restore P0 Golden Sample layout behavior so formal PDF-to-Word output stays close to the source PDF page orientation and uses source-layout evidence before formatting text as a table caption. The immediate failures are `gs-006` and `gs-008` from run `20260624T083505Z`: both source PDFs are portrait pages, but the generated DOCX uses A4 landscape; `gs-008` also centers a condition sentence as a table caption even though it reads as normal body/context text in the source PDF.

## What I Already Know

* User requirement: prefer "close to original PDF page orientation / normal A4 portrait"; do not change portrait PDF pages to landscape just because tables are wide.
* User requirement: text such as `at TA = +25°C, VS = ±5 V to ±15 V, VCM = VOUT = VS / 2, and RL = 10 kΩ connected to VS / 2 (unless otherwise noted)` should render as normal body/context text, not centered table caption, unless the source PDF layout supports caption treatment.
* Source PDFs are portrait Letter pages:
  * `OPA228_P6.pdf`: `612 x 792 pts (letter)`, rotation 0.
  * `OPA228_P7.pdf`: `612 x 792 pts (letter)`, rotation 0.
* Generated DOCX page sizes from OOXML:
  * `gs-003`, `gs-004`: `11906 x 16838 twips` = A4 portrait.
  * `gs-006`, `gs-008`: `16838 x 11906 twips` = A4 landscape.
* Rendered PDFs confirm the same:
  * `gs-006`, `gs-008`: `841.89 x 595.304 pts (A4)` = A4 landscape.
* `gs-006` and `gs-008` are tagged `wide_table` in `tests/fixtures/golden_samples/manifest.yaml`.
* `app/services/renderer/word_renderer.py::_layout_page_requires_landscape` currently returns `True` for any page containing a table block whose layout `column_hint == "wide"`.
* `tests/test_document_ir_word_renderer_layout.py::test_render_to_bytes_uses_landscape_section_for_wide_table_page` currently codifies that wide-table pages become landscape.
* In `gs-008`, the condition sentence is paragraph 2 with `jc=center`; it appears immediately before the table.
* `app/services/renderer/table_renderer.py::_render_table_captions` renders every `block.captions` entry using `caption` style, and `resources/template_configs/datasheet_template.yaml` sets `caption.alignment: center`.
* `app/services/document_ir/mineru_converter.py::_captions` collects any `caption` field from the raw table block and binds it to the table without checking whether the source-layout position/semantics actually indicate a caption.

## Requirements

* Preserve source page orientation for normal portrait technical datasheet pages. A portrait PDF page should produce A4 portrait DOCX output unless the source page itself is landscape.
* Do not use automatic landscape orientation as the default wide-table fix for P0 Golden Samples.
* Keep wide tables editable in Word while fitting inside A4 portrait page width through table layout strategies such as column width distribution, wrapping, smaller table font, or other portrait-safe formatting.
* Classify table captions using source evidence, not only text presence in MinerU `caption` fields.
* Render table-related condition/context sentences as normal left/justified body text when they are not true captions in the source PDF.
* Keep centered caption styling only for actual figure/table captions or title-like labels supported by MinerU structure plus layout evidence.
* Preserve existing formal chain path: `document_jobs -> MinerUToDocumentIRService -> DocumentIRWordRenderer`.

## Acceptance Criteria

* [ ] `gs-006` generated DOCX uses A4 portrait, not landscape.
* [ ] `gs-008` generated DOCX uses A4 portrait, not landscape.
* [ ] `gs-008` condition sentence beginning `at TA = +25°C...` is rendered as body/context text, not centered caption.
* [ ] Wide tables remain editable Word tables, not screenshots.
* [ ] P0 Golden Sample regression still reaches 4/4 automated success after the fix.
* [ ] Standard render PNG/PDF evidence for `gs-006` and `gs-008` shows no obvious clipping, overlap, or unreadable table collapse.
* [ ] Unit tests cover portrait preservation for wide tables and caption/body classification for table-adjacent condition text.
* [ ] Existing caption tests are adjusted so true captions still render with caption styling.

## Definition Of Done

* Targeted renderer/converter tests updated and passing.
* Formal-chain document job tests updated or added if behavior crosses `document_jobs`.
* P0 Golden Sample hostdzire validation rerun after implementation.
* New run evidence includes report, generated DOCX, standard render PNG/PDF, and admin signoff notes for any remaining quality flags.
* Documentation/spec updated if this changes the renderer parity contract.

## Out Of Scope

* No expansion beyond the 4 canonical OPA228 P0 Golden Samples.
* No image-only fallback for tables.
* No broad redesign of MinerU parsing or table extraction.
* No unrelated typography/theme cleanup.
* No committing generated DOCX, PNG, PDF, trace, real keys, or customer/private files.

## Technical Notes

* Current run evidence:
  * Local ignored copy: `tests/tmp/hostdzire_golden_sample_runs/20260624T083505Z/`
  * Hostdzire run dir: `/root/md2word-releases/ecbd335e/tests/tmp/golden_sample_runs/20260624T083505Z`
* Likely implementation area:
  * `app/services/renderer/word_renderer.py`
  * `app/services/document_ir/mineru_converter.py`
  * `app/services/renderer/table_renderer.py`
  * `app/conversion/docx_rules/mineru_content.py`
  * `resources/template_configs/datasheet_template.yaml` only if style mapping needs adjustment
* Likely tests:
  * `tests/test_document_ir_word_renderer_layout.py`
  * `tests/test_document_ir_mineru_converter_layout.py`
  * selected `tests/test_fastapi_jobs_backend.py` document job formal-chain tests

## Open Question

* Scope decision: should the portrait-preservation rule apply globally to the formal DocumentIR renderer, or only to P0 Golden Sample/direct datasheet mode?
