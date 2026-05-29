# Template Config Package v1

`template-config/v1` is the P0 configuration package used by the DocumentIR to
Word renderer. It intentionally describes one known company template instead of
trying to auto-adapt arbitrary `.docx` files.

## File Set

- `template/datasheet_template.docx`: base Word template, preserving reusable
  styles, header/footer definitions, and embedded assets.
- `template_configs/datasheet_template.yaml`: structured render configuration.
- `template_configs/templates_manifest.yaml`: read-only seed registry that
  binds a template id to the `.docx` file and YAML config.

## YAML Contract

Required top-level field:

- `schema_version: template-config/v1`

P0 renderer-supported sections:

- `page_setup`: margins plus header/footer distances, in centimeters.
- `header`: optional logo path, logo height, and title text/font.
- `footer`: optional static footer behavior.
- `heading1`, `heading2`, `heading3`: title font, size, spacing, color, and
  alignment.
- `normal`: default paragraph style.
- `table_content`: editable table cell text style.
- `table_style`: editable table style name and header fill.
- `caption`: image caption style.

Paths inside the YAML, such as `header.logo_path`, are resolved relative to the
YAML file directory when they are not absolute.

## Version Identifier

Jobs bind templates by `template_version_id` in the format:

```text
template_id@version
```

For compatibility, API callers may still pass `template_id`; the backend
resolves it to the current manifest version before persisting the document job.
