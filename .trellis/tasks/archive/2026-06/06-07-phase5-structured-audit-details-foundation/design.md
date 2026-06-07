# Phase 5 structured audit details foundation design

## Scope

Backend additive slice.

Files expected to change:

- `app/domains/audit/models.py`
- `app/domains/audit/service.py`
- `app/domains/audit/schemas.py`
- `app/domains/audit/query.py`
- `app/domains/audit/router.py`
- `app/domains/ops/router.py`
- `frontend/src/api/types.ts` if frontend schema typing needs to match API.
- `tests/test_fastapi_jobs_backend.py`
- `tests/test_database_job_repository.py` if repository contract coverage needs a details assertion.
- `docs/api/openapi.json` if OpenAPI snapshot is refreshed.

No database DDL migration is needed because all audit repositories store the full `AuditEvent` payload as JSON:

- file: `audit_events.jsonl`
- sqlite: `audit_events.payload`
- mysql: `audit_events.payload`

## Data Contract

Add:

```python
AuditDetailsValue = str | int | float | bool | None | list["AuditDetailsValue"] | dict[str, "AuditDetailsValue"]
AuditDetails = dict[str, AuditDetailsValue]
AuditEvent.details: AuditDetails | None = None
```

Rules:

- `details=None` remains the default for old and simple events.
- Details must be JSON-serializable and safe for Admin audit APIs.
- Empty details normalize to `None`.
- Preserve `reason` as the human compact summary and backward-compatible CSV column.

## API Contract

`AuditEventResponse` adds:

```json
"details": {"...": "..."} | null
```

CSV export keeps existing columns and appends:

```text
details_json
```

`details_json` is generated with sorted keys and compact separators. Empty details export as an empty string.

## Query Behavior

`q` search continues to search existing fields and additionally searches serialized details JSON. Exact filters remain unchanged.

## Audit Write Details

### Alert delivery fake

Write details only when the existing fake-send path writes an audit event:

- `delivery_id`
- `action_mode`
- `channel`
- `dedupe_window_minutes`
- `requested_alert_codes`
- `totals`
- `items` with alert code, outcome, dedupe key, audit flag, severity/source/title
- `safety`

No Slack/email/webhook destination, secret, payload body, or external response is recorded.

### Provider cancellation fake

Write details only when the existing fake-cancel path writes an audit event:

- `provider`
- `target`
- `provider_operation`
- `eligible`
- `outcome`
- `dedupe_key`
- `dedupe_window_minutes`
- `missing_gates`
- `safety`

No provider credentials, callback seed, real provider response body, local paths, or file/object content is recorded.

### Audit export

Write export governance details:

- exported/matched counts.
- truncation and max rows.
- sort.
- filters.
- columns.

## Compatibility

- Existing JSON events without `details` validate because the field is optional.
- Existing consumers that ignore unknown response fields are unaffected.
- CSV consumers keep existing columns by name and receive one appended column.
- Existing compact `reason` values stay unchanged.

## Risks

- Details can become a dumping ground for sensitive payloads. This slice only writes curated details in three controlled call sites.
- CSV export size can grow. This slice writes compact JSON and retains `max_rows`.
- OpenAPI changes require frontend type alignment and snapshot refresh if release checks compare the schema.
