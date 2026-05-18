# Term rule and template APIs

## Goal

Reference the architecture patterns in `/Users/sc/PycharmProjects/create_pdf`,
summarize the reusable design, and define how `md2word` should improve its
term-rule and template APIs.

## Confirmed Facts

- `create_pdf` has already evolved these domains into explicit backend resource
  areas:
  - `templates`
  - `term-rules`
  - `term-rule-categories`
  - supporting admin/query/audit services and persistent stores
- In `create_pdf`, template management is not just a read-only metadata view:
  it has `GET/POST/PUT/PATCH/DELETE`, default-template switching, file replace,
  version fields, and a dedicated `TemplateService` plus `TemplateRecord`.
- In `create_pdf`, term rules are not just a static YAML file:
  they have category/rule models, CRUD, import/validate/export/simulate/sync,
  bootstrap-from-seed behavior, runtime YAML export, and repository-backed
  storage.
- `create_pdf` explicitly separates:
  - versioned assets such as `templates/` and `template_configs/`
  - runtime assets such as `data/term_rules.json`, `data/templates.json`, and
    `data/config/runtime_subscripts_dictionary.yaml`
- `md2word` currently exposes only a read-only templates API:
  - `GET /api/v1/templates`
  - `GET /api/v1/templates/{template_id}`
  - `GET /api/v1/templates/{template_id}/download`
- `md2word` templates API is backed by `app/services/templates/read_service.py`
  and currently only supports a single built-in default template plus metadata
  for the bound layout/subscript YAML files.
- `md2word` currently has no term-rule API surface, no term-rule service, and
  no term-rule repository. The terminology source is still a versioned file:
  `template_configs/subscripts_dictionary.yaml`.
- Existing docs in `md2word` state this limitation explicitly:
  the backend currently has no template CRUD and no term-rule CRUD; templates
  and YAML files are still treated as versioned assets.
- `md2word` already has a generic admin capability boundary in the backend:
  `ADMIN_TOKEN` exists in settings and `require_admin_access()` already exists
  in `app/api/dependencies.py`, even though current jobs ops are intentionally
  not gated by it.
- The chosen target scope is a layered middle ground rather than full parity
  with `create_pdf`:
  - `term_rule` should become a first-class API/resource area with at least
    `list/detail/import-validate/import/export/simulate/sync runtime file`
  - `templates` should advance to `multi-template visible + default switch +
    download + detail metadata`
  - full template CRUD (`create/update/replace/delete/version`) stays out of
    scope for this iteration
- The chosen auth boundary is:
  - read/query/preview endpoints stay open or keep the current ordinary-access
    posture
  - mutating endpoints use the existing `X-Admin-Token` / `require_admin_access`
    boundary
- For templates, the chosen near-term direction is:
  - template assets remain versioned repository assets
  - a versioned manifest/bootstrap source exposes multiple visible templates
  - runtime state only needs to track which template is currently the default
  - full runtime template inventory and CRUD stay out of scope for now
  - jobs creation should accept any visible + enabled `template_id`
  - when `template_id` is omitted, jobs fall back to the current runtime
    default template
- A key implementation constraint is already visible in current `md2word`
  code: `render_config_runtime.TerminologyReplacer` still directly consumes the
  legacy `subscript_rules` YAML shape, while `create_pdf` uses a normalized
  term-rule store and exports runtime YAML from that source of truth.
- The chosen term-rule truth direction is:
  - introduce a normalized v2 term-rule manifest as the versioned authoring
    source
  - export the current legacy `subscript_rules` YAML shape for conversion
    runtime compatibility
  - avoid keeping the legacy YAML structure as the long-term authoring truth
- The chosen category boundary is lightweight:
  - categories should be visible as read-only metadata
  - categories should not get write APIs in this iteration
  - expose a dedicated read-only `GET /api/v1/term-rule-categories`
    endpoint instead of only embedding category metadata inside rule payloads
- Additional evidence from `create_pdf` now clarifies its persistence split:
  - runtime repository/store is the live mutable source used by APIs
  - versioned bootstrap seed initializes or resynchronizes that live source
  - generated runtime YAML remains the file consumed by conversion
- The chosen persistence direction for `md2word` now matches that split:
  - introduce a live runtime term-rule store under `data/`
  - keep the versioned v2 manifest as bootstrap/authoring seed
  - keep generated legacy runtime YAML as the file consumed by conversion
- Additional evidence from `create_pdf` import behavior:
  - import validates YAML and then saves the parsed store as the new live truth
  - sync-files only pushes current live truth back to seed/runtime files
  - conversion still reads only the generated runtime YAML, not the seed file
- The chosen import semantic for `md2word` is whole-store replacement:
  - `term-rules import` replaces the entire live runtime store with the parsed
    validated ruleset
  - `term-rules import` should not attempt incremental merge/update behavior in
    this iteration
- A key current `md2word` implementation gap for the templates scope is that
  `app/conversion/entrypoint.py` still hardcodes
  `settings.default_template_path` and `settings.subscript_config_path` into
  `ConversionRequest`; supporting selectable templates and runtime term-rule
  YAML will require an explicit runtime-resolution step rather than continued
  direct reads from static settings.
- The working tree already contains unfinished refactor changes from another
  task, so this brainstorm should first converge on architecture and scope
  before any new implementation starts.

## Requirements

- Summarize the reusable architecture patterns from `create_pdf` that are
  actually relevant to `md2word`.
- Define a target scope for `md2word` term-rule APIs.
- Define a target scope for `md2word` template APIs.
- Keep the design grounded in current `md2word` architecture instead of copying
  `create_pdf` wholesale.
- Separate what should remain versioned assets from what should become runtime
  state or admin-managed data.
- Reuse existing backend capability boundaries where they fit instead of
  inventing a parallel auth or management model.
- Preserve compatibility between the eventual term-rule API source of truth and
  the existing conversion runtime, whether through a compatibility codec or a
  runtime export step.
- Use the normalized v2 term-rule manifest as the versioned/user-facing source
  of truth, and treat the legacy `subscript_rules` file as a generated runtime
  artifact.
- For term rules, separate three layers explicitly:
  - versioned seed/authoring manifest
  - live runtime store mutated by APIs
  - generated compatibility YAML consumed by conversion
- Keep import semantics simple and explicit: importing a validated ruleset
  replaces live runtime truth instead of merging incrementally.
- Keep category support intentionally narrow in this iteration: readable for
  filtering/display/import validation, but not independently editable.
- Expose category metadata through a dedicated read-only endpoint so the
  term-rule domain is explicit and frontends can filter without inferring
  categories from rules.
- For templates, prefer the smallest design that supports multi-template
  visibility and default switching without prematurely introducing a full
  managed template storage domain.
- Make richer templates behavior product-real rather than purely informational:
  visible enabled templates should be selectable by jobs creation.

## Acceptance Criteria

- [ ] PRD records the current-state gap between `create_pdf` and `md2word`.
- [ ] Reusable architecture patterns from `create_pdf` are identified.
- [ ] A clear target level for `md2word` term-rule APIs is chosen.
- [ ] A clear target level for `md2word` template APIs is chosen.
- [ ] The planning output defines which new endpoints are read-only and which
  are mutating/admin-scoped.
- [ ] The planning output explains how term-rule API truth maps to the existing
  runtime replacement file consumed by conversion.
- [ ] The planning output makes v2 manifest truth and legacy runtime export an
  explicit architectural boundary, not just an implementation detail.
- [ ] The planning output explains whether `md2word` introduces a live runtime
  term-rule store distinct from the versioned v2 bootstrap/authoring manifest.
- [ ] The planning output defines whether term-rule import replaces the live
  store wholesale or merges incrementally.
- [ ] The planning output states whole-store replacement as the chosen import
  contract.
- [ ] The planning output explains how multi-template visibility works from a
  versioned manifest/bootstrap source while default selection persists in
  runtime state.
- [ ] The planning output explains how jobs resolve explicit `template_id`
  versus runtime default template fallback.
- [ ] The planning output explains how conversion stops hardcoding static
  template/term-rule config paths and instead resolves runtime-selected assets.
- [ ] If the target is larger than a small read-only enhancement, `design.md`
  and `implement.md` will be required before implementation.

## Likely Out Of Scope

- Blindly cloning the entire `create_pdf` backend structure into `md2word`.
- Mixing this new feature planning with the currently unfinished job-flow
  refactor implementation.
- Reworking the full conversion pipeline during this task unless term-rule or
  template API scope proves it is required.

## Open Questions

- None at the PRD level. Next step is drafting `design.md` and `implement.md`.

## Notes

- Planning is in progress via `trellis-brainstorm`.
