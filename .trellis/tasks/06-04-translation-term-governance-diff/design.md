# Translation Term Governance Diff Design

## Current State

Completed Translation Term Set capabilities:

- `TranslationTermSetVersionService` manages list/detail/draft/import/export,
  publish, set-default, rollback, and archive primitives.
- `sets_router.py` exposes the Translation Term Set management API.
- `TranslationTermSetPage.vue` exposes Admin CSV import/export, draft summary,
  validation findings, published versions, default switching, and rollback.
- `TranslationTermProposalService` supports proposal create, approve,
  approve-and-publish, reject, and conflict detection during approval.
- Existing proposal conflict responses are currently string-based for
  Translation Term Proposals, unlike the more structured Term Rule proposal
  conflict responses.

Missing governance surface:

- No stable Translation Term Set diff contract.
- No dedicated publish preflight API that combines validation and diff summary.
- No read-only pending-proposal compatibility preview before Admin clicks
  approve.
- No field-level before/after display for Translation Term Set draft changes.

## Scope

Implement read-only governance visibility first:

1. Version diff
   - Compare a base version to a target version.
   - Default base: current default version.
   - Default target: current draft.
   - Return summary and field-level changes.

2. Publish preflight
   - Evaluate target entries with existing validation.
   - Include diff summary and blocking reasons.
   - Do not publish or mutate draft.

3. Proposal compatibility preview
   - Evaluate pending Translation Term Proposals against current draft/default.
   - Return compatible/warning/conflict status and structured findings.
   - Do not approve, reject, publish, or rebase proposals.

4. Frontend workbench
   - Extend `TranslationTermSetPage.vue` with diff, preflight, and proposal
     compatibility sections.
   - Link conflicted proposals to existing proposal review UI.
   - Keep CSV import/export/publish/default/rollback flows intact.

Out of scope:

- Per-entry Translation Term CRUD.
- Batch approve/reject/publish mutation APIs.
- Automatic conflict rebase or merge strategy selection.
- New file upload, physical deletion, or retention operations.
- Changes to document job creation, retry, resource snapshot, or translation
  execution.

## Backend API Design

### `GET /api/v1/translation-term-sets/{set_id}/diff`

Query parameters:

| Parameter | Default | Notes |
|---|---|---|
| `base_version` | current default version | Must be an existing version. |
| `target_version` | `draft` | Must be `draft` or an existing published version. |

Response sketch:

```json
{
  "set_id": "translation-terms-en2zh",
  "language_pair": "en2zh",
  "base_version": "v1",
  "target_version": "draft",
  "summary": {
    "added": 1,
    "removed": 1,
    "changed": 2,
    "unchanged": 10,
    "total_before": 13,
    "total_after": 13
  },
  "items": [
    {
      "kind": "changed",
      "normalized_source_term": "adc",
      "source_term": "ADC",
      "changed_fields": ["target_term", "note"],
      "before": {"source_term": "ADC", "target_term": "模数转换器"},
      "after": {"source_term": "ADC", "target_term": "模拟数字转换器"}
    }
  ]
}
```

Proposed schemas:

- `TranslationTermSetDiffSummaryResponse`
- `TranslationTermSetDiffEntryResponse`
- `TranslationTermSetDiffResponse`

Implementation location:

- Add dataclasses and pure diff helpers to
  `app/domains/translation/term_set_version_service.py`.
- Add schema models to `app/domains/translation/schemas.py`.
- Add router endpoint to `app/domains/translation/sets_router.py`.

### `GET /api/v1/translation-term-sets/{set_id}/preflight`

Query parameters:

| Parameter | Default | Notes |
|---|---|---|
| `base_version` | current default version | Used for diff summary. |
| `target_version` | `draft` | First implementation should target draft. |

Response sketch:

```json
{
  "set_id": "translation-terms-en2zh",
  "language_pair": "en2zh",
  "base_version": "v1",
  "target_version": "draft",
  "publish_blocked": false,
  "blocking_reasons": [],
  "validation": {"valid": true, "errors": [], "warnings": []},
  "diff_summary": {"added": 1, "removed": 0, "changed": 1, "unchanged": 10}
}
```

Preflight rules:

- Validation errors block publish.
- Missing base or target version returns `404`.
- Non-MySQL service returns existing `503`.
- `no_actual_changes` should appear as warning, not error, matching current
  validation semantics.

### `GET /api/v1/translation-term-sets/{set_id}/proposal-compatibility`

Query parameters:

| Parameter | Default | Notes |
|---|---|---|
| `status` | `pending` | First implementation only needs pending. |

Response sketch:

```json
{
  "set_id": "translation-terms-en2zh",
  "language_pair": "en2zh",
  "items": [
    {
      "proposal_id": "ttp_abc",
      "status": "compatible",
      "observed_version": "v1",
      "change_count": 2,
      "conflicts": [],
      "warnings": [
        {
          "code": "stale_observed_version",
          "message": "证据版本和当前版本不同: observed=v1 current=v2",
          "normalized_source_term": null
        }
      ]
    }
  ],
  "summary": {"compatible": 1, "warning": 1, "conflict": 1}
}
```

Compatibility evaluation should reuse proposal validation and conflict logic,
but must be side-effect free. If private helpers need to be shared, extract a
small service method rather than calling underscore methods from routers.

## Frontend Design

Extend `TranslationTermSetPage.vue`:

- Add a diff/preflight section near the Draft summary.
- Show summary cards for added/removed/changed/unchanged.
- Show a table of diff items with kind, source term, changed fields, before,
  and after values.
- Show preflight validation as the current validation table plus
  `publish_blocked` and blocking reasons.
- Add a pending proposal compatibility section:
  - compatible count
  - warning count
  - conflict count
  - proposal ID/source term/observed version/status
  - link to existing proposal review tab

Do not add row-level edit controls. Do not add batch approve/reject controls in
this task.

## Data Model

No database migration is required.

Diff/preflight/proposal compatibility responses are derived from existing
Translation Term Set versions, draft entries, and proposal records.

## Compatibility

- Existing endpoints remain unchanged.
- Existing CSV format remains unchanged.
- Existing job resource snapshot binding remains unchanged.
- Existing proposal approve/reject behavior remains unchanged.
- Frontend should continue to handle `503`, `404`, and `400` with the existing
  error display pattern.

## Risks

- Diff responses can become large. The first implementation can return full
  diff for MVP; pagination/filtering should be a later task if needed.
- Proposal compatibility currently has string conflict information. To avoid
  brittle frontend parsing, backend should return structured finding items.
- Sharing proposal conflict logic may tempt direct reuse of private helpers.
  Prefer a service-level read-only preview method.

## Closeout Status

The reviewed first slice has been implemented:

- Admin-only read-only diff endpoint.
- Admin-only read-only preflight endpoint.
- Admin-only read-only proposal compatibility endpoint.
- Frontend display in `TranslationTermSetPage`.
- Existing proposal review tab routing support.

Batch mutation, automatic rebase, conflict resolution, and row-level
Translation Term CRUD remain out of scope.
