---
doc_type: design
task: 05-31-project-directory-restructure
status: draft
scope: repository directory restructure, app domain-first candidate layout, and staged persistence architecture cleanup
---

# Project directory restructure design

## 1. Design intent

This refactor makes the repository layout express ownership directly:

- root contains project metadata and tool-required dot directories only
- `resources/` contains versioned non-code input assets
- `var/` contains local mutable runtime state and remains ignored
- `scripts/dev/` contains direct local process runners
- `scripts/ops/` contains operational checks, exports, migrations, and backfills
- `tests/fixtures/` contains test sample assets
- `app/` remains the primary Python package, but moves toward domain-first
  ownership for business code

The product behavior contract stays stable: HTTP routes and payload contracts
should not change, conversion output should not change, and API/worker process
semantics should not change. File paths, import paths, config defaults, docs,
and local commands may change to match the new structure.

## 2. Target repository layout

```text
.
├── app/
├── deploy/
│   ├── env/
│   ├── hosts/
│   └── nginx/
├── docker/
│   ├── dev/
│   └── prod/
├── docs/
│   ├── api/
│   ├── archive/
│   │   └── planning/
│   ├── deploy/
│   ├── dev/
│   ├── runbooks/
│   └── testing/
├── resources/
│   ├── prompts/
│   ├── template_configs/
│   ├── templates/
│   └── term_rules/
├── scripts/
│   ├── dev/
│   └── ops/
├── tests/
│   ├── fixtures/
│   └── tmp/
└── var/
    ├── config/
    ├── jobs/
    ├── object_artifacts/
    ├── stage_messages/
    └── tmp/
```

Root-level tool convention directories such as `.claude/`, `.cursor/`,
`.codestable/`, `.trellis/`, `.idea/`, and VCS/config files stay at root.

No compatibility shims should be added for old root paths. The implementation
updates code, tests, docs, and defaults to the new paths directly.

## 3. Target app layout

```text
app/
├── api/
│   ├── dependencies.py
│   ├── errors.py
│   └── v1/
│       └── router.py
├── clients/
├── conversion/
├── core/
├── domains/
│   ├── audit/
│   ├── document_jobs/
│   ├── files/
│   ├── jobs/
│   ├── resources/
│   ├── templates/
│   ├── term_rules/
│   └── translation/
├── infrastructure/
│   └── persistence/
│       ├── file/
│       ├── mysql/
│       └── sqlite/
└── workers/
```

Layer ownership:

- `app/api/`: HTTP composition, version aggregation, shared dependencies, and
  error mapping only.
- `app/domains/<domain>/`: domain models, request/response schemas, router
  implementation, services, and repository ports for that domain.
- `app/infrastructure/persistence/`: backend-specific repository adapters and
  schema/bootstrap code.
- `app/core/`: cross-domain primitives only, such as config, logging, base
  errors, time/id helpers if needed.
- `app/conversion/`: top-level conversion engine/library, not owned by a job
  domain.
- `app/workers/`: process and queue composition layer.
- `app/clients/`: outbound protocol clients for external services.

`app/schemas/` and all-purpose repository adapters are not part of the final
target layout.

## 4. Staged migration

All nine findings from the scan remain in scope for the larger restructure.
Implementation approval is phase-gated: Phase 1 is the first slice to prepare,
and every later phase requires a separate review before code moves.

### Phase 1: Root and asset layout

Child task: `.trellis/tasks/05-31-phase-1-root-resources-runtime-layout`.

Move root process entrypoints to `scripts/dev/`, move conversion runtime config
to `app/conversion/runtime_config.py`, consolidate versioned assets under
`resources/`, rename runtime state root from `data/` to `var/`, move test
fixtures under `tests/fixtures/`, and reorganize docs/deploy layout.

This phase should not move business packages under `app/domains/` yet. Its goal
is to remove root-level noise and path ambiguity before app internals are
rewired.

### Phase 2: `files` domain sample

Create `app/domains/files/` and move the files resource implementation into it:

```text
app/domains/files/
├── __init__.py
├── models.py
├── repository.py
├── router.py
├── schemas.py
├── service.py
├── retention.py
└── validation.py
```

`app/api/v1/router.py` includes `app.domains.files.router`. This phase proves
the domain-first pattern before migrating larger domains.

### Phase 3: Persistence architecture

Replace all-purpose metadata adapters with domain ports plus backend-specific
adapters:

```text
app/infrastructure/persistence/
├── file/
│   ├── audit.py
│   ├── document_jobs.py
│   ├── files.py
│   ├── jobs.py
│   ├── resources.py
│   └── stage_messages.py
├── sqlite/
│   ├── audit.py
│   ├── document_jobs.py
│   ├── files.py
│   ├── jobs.py
│   ├── resources.py
│   ├── schema.py
│   └── stage_messages.py
└── mysql/
    ├── audit.py
    ├── document_jobs.py
    ├── files.py
    ├── jobs.py
    ├── resources.py
    ├── schema.py
    └── stage_messages.py
```

The runtime wiring in `app/main.py` may still compose several adapters into
the service graph, but no single class should own every metadata port.

### Phase 4: Remaining domains

Migrate domains in small slices after `files` proves the pattern:

- `audit`
- `resources`
- `document_jobs`
- `jobs`
- `templates`
- `term_rules`
- `translation`

Each slice moves its models, schemas, services, router implementation, and
repository port. Each slice must have its own validation checkpoint.

### Phase 5: Cleanup and spec update

Delete obsolete packages after references are removed:

- `app/schemas/`
- domain model files remaining in `app/core/`
- all-purpose repository adapters under `app/repositories/`
- obsolete directory rules in `.trellis/spec/backend/directory-structure.md`

Update `.codestable/architecture/` after the code structure is stable.

## 5. Invariants

- No root-level compatibility shim for old `run_*.py`, `config.py`,
  `template_configs/`, `template/`, `prompt/`, or `data/` paths.
- No HTTP path, method, status code, or response payload change unless a later
  explicit feature/issue task approves it.
- OpenAPI may be regenerated, but differences should be limited to schema
  ordering/module metadata and must be reviewed.
- Conversion characterization tests must continue to pass.
- Worker import/startup paths must remain PyCharm-friendly and require no
  mandatory CLI arguments.
- `var/` and `tests/tmp/` must stay ignored.
- Historical docs may move to archive; current docs must point to new paths.

## 6. Main risks

- Import churn across `app/core`, `app/schemas`, and services can hide behavior
  changes if moved too broadly in one step.
- Persistence split touches file/sqlite/mysql and can break runtime wiring even
  when domain code compiles.
- Resource path migration can miss manifest defaults or docs that tests do not
  cover.
- OpenAPI changes need careful review to distinguish harmless generated-order
  drift from real contract drift.

## 7. Design checkpoints

- Phase 1 can start after this design and `implement.md` are reviewed.
- Phase 2 requires confirming the exact `files` package module names before
  editing code.
- Phase 3 requires a focused persistence design note if splitting adapters
  exposes transaction or schema bootstrap questions.
- Phases 4 and 5 should not start until the `files` sample and persistence split
  are validated.
