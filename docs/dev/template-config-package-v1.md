---
doc_type: dev-guide
slug: template-config-package-v1
component: pdf-to-word-backend
status: current
summary: Template config package v1 fields used by the DocumentIR Word renderer.
tags: [template-config, renderer, docx]
last_reviewed: 2026-06-03
---

# Template Config Package v1

`template-config/v1` is the P0 configuration package used by the DocumentIR to
Word renderer. It intentionally describes one known company template instead of
trying to auto-adapt arbitrary `.docx` files.

## File Set

- `resources/templates/default/datasheet_template.docx`: base Word template, preserving reusable
  styles, header/footer definitions, and embedded assets.
- `resources/template_configs/datasheet_template.yaml`: structured render configuration.
- `resources/template_configs/templates_manifest.yaml`: read-only seed registry that
  binds a template id to the `.docx` file and YAML config.

## YAML Contract

Required top-level field:

- `schema_version: template-config/v1`

P0 renderer-supported sections:

- `page_setup`: margins plus header/footer distances, in centimeters.
- `header`: optional logo path, logo height, and title text/font.
- `footer`: optional static footer behavior.
- `heading1`, `heading2`, `heading3`: title font, size, spacing, color, and
  alignment. Each heading section may also set `word_style_name` to bind the
  paragraph to an existing Word named style.
- `normal`: default paragraph style.
- `table_content`: editable table cell text style.
- `table_style`: editable table style name and header fill.
- `caption`: image caption style.
- `table_note`: table footnote / note paragraph style.

Paths inside the YAML, such as `header.logo_path`, are resolved relative to the
YAML file directory when they are not absolute.

## Paragraph Style Fields

Paragraph-style sections share the same field set:

- `font_name`
- `font_size`
- `bold`
- `italic`
- `color`
- `alignment`
- `line_spacing`
- `space_before`
- `space_after`
- `first_line_indent_pt`
- `left_indent_pt`
- `right_indent_pt`
- `word_style_name`

`word_style_name` is optional. When present, the renderer first tries to apply
that named Word paragraph style and then applies the direct formatting fields.
If the base DOCX template does not define the named style, rendering continues
with direct formatting only.

## Renderer Semantics

The renderer uses the config package for editable Word semantics, not just
visual formatting:

- Heading blocks use `heading1` / `heading2` / `heading3` direct formatting and
  default to Word `Heading 1` / `Heading 2` / `Heading 3` named styles unless
  `word_style_name` overrides the style name.
- List blocks use real Word numbering; their visible text should not rely on a
  hard-coded bullet prefix.
- Formula text and formula-like table content are normalized before inline rich
  text rendering, so supported subscript and superscript fragments become Word
  runs instead of raw TeX text.
- Table captions use `caption`, are rendered before the editable table, and keep
  with the following table.
- Table footnotes and notes use `table_note` and are rendered after the editable
  table.

## Version Identifier

Jobs bind templates by `template_version_id` in the format:

```text
template_id@version
```

For compatibility, API callers may still pass `template_id`; the backend
resolves it to the current manifest version before persisting the document job.
