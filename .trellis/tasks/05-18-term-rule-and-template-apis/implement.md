# Term Rule And Template APIs Implementation Plan

## Scope

Implement the approved layered target:

- normalized v2 term-rule seed manifest
- live runtime term-rule store + generated compatibility YAML
- read-only category endpoint
- richer templates catalog backed by versioned manifest + runtime default state
- jobs template selection by `template_id`

## Ordered Checklist

### 1. Add term-rule core models and file repository

Files:

- create `app/core/rule_models.py`
- extend `app/repositories/protocols.py`
- create `app/repositories/file_term_rule_repository.py`

Goals:

- establish live runtime store shape under `data/config/term_rules_store.json`
- define normalized category/rule/segment/store contracts

Validation:

- model/repository unit coverage or focused service tests
- repository file round-trip works

### 2. Add term-rule codec, bootstrap, validation, and sync services

Files:

- create `app/services/term_rules/yaml_codec.py`
- create `app/services/term_rules/service.py`
- create `app/services/term_rules/import_validation.py`
- create `app/services/term_rules/sync_files.py`
- create `app/services/term_rules/bootstrap.py`

Goals:

- validate/export normalized v2 YAML
- generate legacy runtime YAML for the current conversion runtime
- bootstrap live store from versioned seed when empty
- keep import semantics as whole-store replacement

Validation:

- tests for:
  - valid v2 parse
  - invalid import report
  - export to legacy runtime YAML expected by current replacer
  - bootstrap-if-empty behavior

### 3. Add term-rule API surfaces

Files:

- create `app/api/v1/routers/term_rule_categories.py`
- create `app/api/v1/routers/term_rules.py`
- update `app/api/v1/router.py`
- extend `app/schemas/api_v1.py`
- add service getters/admin guards as needed in `app/api/dependencies.py`

Goals:

- expose:
  - `GET /term-rule-categories`
  - `GET /term-rules`
  - `GET /term-rules/{id}`
  - `GET /term-rules/export`
  - `POST /term-rules/simulate`
  - `POST /term-rules/import/validate`
  - `POST /term-rules/import` (admin)
  - `POST /term-rules/sync-files` (admin)

Validation:

- focused API tests for read/admin split
- import validate -> import -> export -> sync behavior

### 4. Introduce template manifest + runtime default state

Files:

- create versioned template manifest file (path decided in design)
- create `app/core/template_models.py` or extend current template schema layer
- create file-backed runtime default-state repository or lightweight state
  helper
- evolve `app/services/templates/read_service.py` into catalog/default-aware
  service or add a nearby companion service

Goals:

- list multiple templates from versioned manifest
- persist current default template in runtime state
- expose enough metadata for list/detail/download/default switch

Validation:

- tests for:
  - manifest load
  - default fallback when runtime state missing
  - invalid default state handling
  - `PATCH /templates/{id}/default` admin behavior

### 5. Wire template selection into jobs and conversion resolution

Files:

- update `app/api/v1/routers/jobs_ingest.py`
- update `app/services/jobs/command.py` if needed
- update `app/conversion/entrypoint.py`
  or add a nearby resolution/orchestration helper
- update `app/main.py`
- update `app/core/runtime.py`
- possibly extend response schemas/docs if selected template metadata surfaces
  further

Goals:

- allow `template_id` for any visible+enabled template
- keep omission => runtime default fallback
- resolve selected template path and generated runtime term-rule YAML path
  before conversion

Validation:

- API tests for:
  - valid non-default `template_id`
  - omitted `template_id` uses runtime default
  - disabled/unknown template rejected
  - existing direct/default flows still work

### 6. Add documentation and spec alignment

Files:

- `docs/api/templates.md`
- add `docs/api/term-rules.md`
- add `docs/api/term-rule-categories.md`
- update dev/architecture docs
- update `.trellis/spec/backend/*` if new stable conventions emerge

Goals:

- document three-layer term-rule boundary
- document template manifest + runtime default split
- document admin-only write interfaces

Validation:

- docs are consistent with implemented routes and payloads

## Validation Commands

Primary:

- `python3 -m unittest tests.test_fastapi_jobs_backend`

Likely additional focused modules to add/run:

- `python3 -m unittest tests.test_term_rule_api`
- `python3 -m unittest tests.test_template_catalog_api`
- `python3 -m unittest tests.test_render_config_characterization`
- `python3 -m unittest tests.test_text_render_characterization`

If the default interpreter lacks runtime deps, use the project’s validated
environment interpreter consistent with existing local project guidance.

## Risky Files

- `app/api/dependencies.py`
- `app/api/v1/router.py`
- `app/api/v1/routers/jobs_ingest.py`
- `app/conversion/entrypoint.py`
- `render_config_runtime.py`
- `app/main.py`
- `app/core/runtime.py`
- `app/schemas/api_v1.py`

## Review Gates Before `task.py start`

- Confirm the term-rule v2 seed path and template manifest path.
- Confirm runtime files under `data/config/` are acceptable.
- Confirm whole-store replacement import semantics are acceptable.
- Confirm read/admin split for term-rule and template endpoints is acceptable.
- Confirm jobs should truly honor explicit `template_id` and not just default.
