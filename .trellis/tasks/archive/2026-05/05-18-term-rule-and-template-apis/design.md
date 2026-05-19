# Term Rule And Template APIs Design

## Summary

This task brings `md2word` partway toward the resource-oriented backend shape
already proven in `create_pdf`, but stops well short of cloning its entire
surface. The resulting design introduces:

- a first-class `term-rules` domain with a normalized v2 manifest as the
  versioned authoring seed, a live runtime store under `data/`, and generated
  legacy runtime YAML for the conversion pipeline
- a lightweight read-only `term-rule-categories` resource
- a richer `templates` domain driven by a versioned manifest plus a tiny runtime
  default-template state file
- jobs that can choose any visible+enabled template by `template_id`, while
  still falling back to the current runtime default template when omitted

The design explicitly preserves the current conversion runtime compatibility by
continuing to feed it a legacy `subscript_rules` YAML file.

## Scope

In scope:

- `term-rules` list/detail/export/simulate/import-validate/import/sync-files`
- read-only `term-rule-categories`
- multi-template visibility, template detail, template download, default-template
  switching
- jobs accepting visible+enabled `template_id`
- runtime resolution of selected template and runtime term-rule YAML into the
  conversion request path

Out of scope:

- template create/update/replace/delete/versioning APIs
- term-rule category write APIs
- rule-by-rule create/update/delete APIs
- replacing the conversion runtime so it reads v2 manifests directly
- mixing this work with the unfinished backend job-flow refactor task

## Reusable Patterns From `create_pdf`

The parts worth carrying over are architectural, not literal:

1. Resource domains should have explicit router/service/repository boundaries.
2. Versioned assets and runtime mutable state should be separate.
3. Term-rule authoring truth, live runtime truth, and conversion-consumable YAML
   should be treated as different layers with explicit sync edges.
4. Import should validate first, then replace live truth wholesale if accepted.
5. `sync-files` is for aligning seed/runtime files with current live truth; it
   is not the primary mutating path and does not change what conversion reads.

The parts not copied wholesale:

- full template CRUD
- term-rule category CRUD
- admin audit/service lattice
- database-capable repository factory

## Proposed `md2word` Architecture

### 1. Term-Rule Domain

#### 1.1 Three-Layer Boundary

Use three explicit representations:

1. **Versioned seed / authoring manifest**
   - proposed path: `template_configs/term_rules.v2.yaml`
   - checked into git
   - manually maintained baseline
   - uses normalized v2 shape (`schema_version`, `categories`, `rules`)

2. **Live runtime store**
   - proposed path: `data/config/term_rules_store.json`
   - file-backed mutable truth used by APIs
   - whole-store replacement on import

3. **Generated compatibility runtime YAML**
   - proposed path: `data/config/runtime_subscripts_dictionary.yaml`
   - generated from the live runtime store
   - consumed by the existing conversion runtime

`template_configs/subscripts_dictionary.yaml` stops being the long-term authoring
truth. It becomes either deprecated compatibility input or a fallback only until
the new runtime export path is wired through all call sites.

#### 1.2 API Surface

Read-only/open:

- `GET /api/v1/term-rule-categories`
- `GET /api/v1/term-rules`
- `GET /api/v1/term-rules/{rule_id}`
- `GET /api/v1/term-rules/export`
- `POST /api/v1/term-rules/simulate`
- `POST /api/v1/term-rules/import/validate`

Admin-only:

- `POST /api/v1/term-rules/import`
- `POST /api/v1/term-rules/sync-files`

#### 1.3 Category Boundary

Categories are a read-only resource in this iteration:

- exposed via dedicated `GET /term-rule-categories`
- used for filtering, display, and import validation
- not individually editable through the API

This keeps the term-rule domain explicit for frontend consumers without opening
the larger problem of runtime category editing versus versioned manifest
ownership.

#### 1.4 Services And Repositories

Add a local term-rules package similar in shape to `create_pdf`, but smaller:

- `app/core/rule_models.py`
  - `TermRuleCategoryRecord`
  - `TermRuleRecord`
  - `TermRuleSegmentRecord`
  - `TermRulesStore`
- `app/repositories/file_term_rule_repository.py`
  - file-backed live runtime store at `data/config/term_rules_store.json`
- `app/services/term_rules/yaml_codec.py`
  - validate v2 and optionally read legacy-compatible input
  - export legacy runtime YAML
- `app/services/term_rules/service.py`
  - list/query/get/export/simulate/import/apply store
- `app/services/term_rules/import_validation.py`
  - separate report object for validate-before-import
- `app/services/term_rules/sync_files.py`
  - write live truth back to seed and runtime YAML
- `app/services/term_rules/bootstrap.py`
  - if live store is empty, initialize it from the versioned v2 seed and emit
    runtime YAML

#### 1.5 Import Semantics

Import contract:

- payload is v2 YAML text
- validate first
- if accepted, replace the entire live runtime store
- after replacement, regenerate runtime compatibility YAML

No incremental merge/update semantics in this iteration.

### 2. Template Domain

#### 2.1 Split Versioned Catalog From Runtime Default State

Templates do not become a full managed runtime inventory yet.

Use:

1. **Versioned template manifest / bootstrap catalog**
   - proposed path: `template_configs/templates_manifest.yaml`
   - checked into git
   - enumerates visible templates and their metadata

2. **Runtime default-template state**
   - proposed path: `data/config/template_state.json`
   - stores at minimum the current `default_template_id`

The template files themselves remain versioned assets under `template/` or
`templates/`.

#### 2.2 Manifest Shape

Each template manifest entry should minimally carry:

- `id`
- `name`
- `description`
- `enabled`
- `is_default_seed` or a designated default marker
- `template_path`
- `layout_config_path`

`subscript_config` should no longer represent per-template rule truth. Since
term rules become a global runtime-managed domain, templates should not imply
they own their own independent term-rule inventory. The existing response field
can continue to expose the currently bound runtime compatibility YAML metadata,
but design and docs should clarify that this is a shared runtime dependency, not
template-owned authoring state.

#### 2.3 API Surface

Read-only/open:

- `GET /api/v1/templates`
- `GET /api/v1/templates/{template_id}`
- `GET /api/v1/templates/{template_id}/download`

Admin-only:

- `PATCH /api/v1/templates/{template_id}/default`

No template CRUD beyond default switching in this iteration.

#### 2.4 Services And State

Evolve `app/services/templates/read_service.py` into a catalog-oriented service
or introduce a nearby companion service such as:

- `TemplateCatalogService`
  - load manifest
  - load runtime default state
  - list visible templates
  - resolve selected template assets
  - set runtime default

This can stay file-backed and local to `app/services/templates/`, without
inventing a broad storage framework.

### 3. Jobs / Conversion Integration

#### 3.1 Jobs Input Contract

`jobs` ingest should change from:

- only accepting `None` or `default`

to:

- accepting any visible+enabled template `id`
- treating omitted `template_id` as “use current runtime default template”

If a template is unknown or disabled, return `400`.

#### 3.2 Job Persistence

Existing `JobRecord.template_id` is already enough to persist the selected
template id for this iteration.

No additional template version or template path fields are required yet.

#### 3.3 Conversion Request Resolution

Current problem:

- `app/conversion/entrypoint.py` hardcodes `settings.default_template_path`
  and `settings.subscript_config_path`

Required change:

- introduce a runtime-aware resolution step before building
  `ConversionRequest`
- selected template path should come from template catalog resolution
- subscript config path should point to generated runtime
  `data/config/runtime_subscripts_dictionary.yaml`

This can be solved by either:

1. extending `build_job_conversion_request()` to receive resolved paths, or
2. adding a small orchestration helper/service that resolves template + term-rule
   runtime assets, then calls into the existing conversion entrypoint contract

The second option is cleaner if we want to keep `ConversionRequest` construction
pure and explicit.

### 4. Runtime Wiring

`AppRuntime` and `build_runtime()` should add:

- term-rule repository/service/bootstrap/import-validation/sync services
- template catalog/default-state service

During runtime construction:

- bootstrap live term-rule store from v2 seed if empty
- export runtime compatibility YAML if missing or after bootstrap
- load template manifest and runtime default state

This should be explicit in startup wiring, not hidden in random request paths.

### 5. Docs And API Contracts

Update:

- `docs/api/templates.md`
- add `docs/api/term-rules.md`
- add `docs/api/term-rule-categories.md`
- update backend architecture/dev docs to explain:
  - versioned v2 manifest vs live store vs runtime compatibility YAML
  - template manifest vs runtime default state
  - admin-only write operations

## Compatibility Notes

- Existing read-only templates routes remain, but their payloads may expand from
  one default item to multiple visible items.
- Existing jobs API keeps `template_id` optional; behavior changes from “only
  default allowed” to “optional explicit selection with default fallback”.
- Conversion runtime remains compatible because it still consumes a legacy
  `subscript_rules` YAML file.
- Seed files remain versioned and human-maintained; API mutations target runtime
  data, not git-tracked files.

## Key Risks

1. Template manifest and runtime default can drift if default id points to a
   removed/disabled template.
2. Term-rule runtime YAML generation can diverge from what the current
   `TerminologyReplacer` expects.
3. Import replace semantics can surprise users if not documented clearly.
4. Startup/bootstrap behavior can silently overwrite or regenerate runtime files
   in ways operators do not expect.

## Risk Mitigations

- validate runtime default id against the manifest on load
- keep codec tests that compare generated legacy YAML against current replacer
  expectations
- make import return counts and summaries clearly indicating full replacement
- keep bootstrap limited to “initialize if empty”; do not auto-overwrite a
  non-empty live store from seed

## Rollback Considerations

- If term-rule resource rollout proves too disruptive, revert by:
  - preserving the current versioned legacy YAML path
  - removing runtime store usage from conversion resolution
- If multi-template job selection proves problematic, keep richer templates API
  but restrict jobs back to runtime default while retaining the manifest/state
  machinery

## Success Criteria

- `md2word` has an explicit `term-rules` resource domain with read/admin split
- `md2word` has a read-only `term-rule-categories` endpoint
- `md2word` has multiple visible templates and admin default switching
- `jobs` can run against explicit enabled templates
- conversion consumes generated runtime compatibility YAML rather than only the
  old versioned static file
