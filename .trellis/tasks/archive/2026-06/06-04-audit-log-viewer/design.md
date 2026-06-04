# Audit log viewer design

## Scope

Implement a small, read-only audit event viewer for Admin users.

The feature uses the existing audit domain model:

- `ActorContext`
- `AuditEvent`
- `AuditService`
- `AuditEventRepositoryProtocol`
- file/sqlite/mysql audit repositories

The task does not alter the audit event write contract or persisted schema.

## Current state

Backend:

- `app/domains/audit/models.py` defines `AuditEvent`.
- `app/domains/audit/service.py` records successful audit actions.
- `app/domains/audit/repository.py` exposes `append_audit_event()` and `list_audit_events()`.
- file/sqlite/mysql adapters already persist and list audit events.
- `app/services/health_service.py` already reports `audit_events.total`.
- There is no public audit query router.

Frontend:

- `frontend/src/router/index.ts` already supports Admin-only route metadata.
- `frontend/src/layouts/AppLayout.vue` exposes Admin-only `系统状态`.
- `frontend/src/pages/SystemStatusPage.vue` already shows audit event count from metrics.
- There is no audit event page or API client.

## API changes

Add:

- `GET /api/v1/audit-events`

Auth:

- Requires `require_admin_user`.
- Operator receives the existing `403 role_forbidden` behavior.

Query parameters:

- `page`: integer, default `1`, minimum `1`
- `page_size`: integer, default `50`, minimum `1`, maximum `200`
- `sort`: `created_at_desc` or `created_at_asc`, default `created_at_desc`
- `actor_role`: optional `admin | operator | jobs | anonymous`
- `action`: optional exact action filter
- `target_type`: optional exact target type filter
- `target_id`: optional exact target id filter
- `actor_id`: optional exact actor id filter
- `q`: optional case-insensitive text search across `audit_id`, `actor_id`, `action`, `target_type`, `target_id`, `reason`, `trace_id`
- `created_from`: optional ISO datetime lower bound
- `created_to`: optional ISO datetime upper bound

Response:

- `AuditEventListResponse`
  - `items: AuditEventResponse[]`
  - `page: int`
  - `page_size: int`
  - `total: int`
- `AuditEventResponse`
  - `audit_id`
  - `actor_id`
  - `actor_role`
  - `action`
  - `target_type`
  - `target_id`
  - `reason`
  - `trace_id`
  - `created_at`

## Backend files

Expected implementation files:

- `app/domains/audit/schemas.py`
  - API response schemas and query enum literals.
- `app/domains/audit/query.py`
  - Query object and read-side service that filters/sorts/paginates repository results.
- `app/domains/audit/router.py`
  - Thin FastAPI router mapping query params to the query service.
- `app/api/v1/router.py`
  - Include the new audit router.
- `tests/test_fastapi_jobs_backend.py`
  - Add narrow API tests.

No changes expected:

- Persistence schema files.
- Existing audit write paths.
- Document job execution, MinerU, translation, renderer, artifact storage.

## Frontend files

Expected implementation files:

- `frontend/src/api/types.ts`
  - Add audit response and query types.
- `frontend/src/api/auditEvents.ts`
  - API wrapper for `GET /api/v1/audit-events`.
- `frontend/src/pages/AuditLogPage.vue`
  - Admin-only table, filters, pagination, CSV export, loading/error/empty states.
- `frontend/src/router/index.ts`
  - Add Admin-only route `/system-status/audit-events`.
- `frontend/src/pages/SystemStatusPage.vue`
  - Link from audit event count/status area to the viewer.

No changes expected:

- Job list/detail behavior.
- Upload/retry configuration behavior.
- Term rule CRUD pages.
- File retention mutation behavior.

## Page changes

Add route:

- `/system-status/audit-events`
  - Admin-only.
  - Fits under existing system status / operations area.

UI behavior:

- Filters stay compact and operational: action, role, target type/id, actor id, time range, search.
- Table columns match persisted audit fields.
- CSV export downloads a browser-generated CSV for the currently loaded page only.
- The export action does not call backend mutation APIs and does not create server-side files.

## Security and privacy

- Use Admin-only JWT dependency on the backend.
- Do not expose raw tokens, request payloads, file contents, prompts, or secrets because the persisted model does not contain them.
- Keep free-text search limited to existing audit metadata fields.
- Do not add an audit event when merely viewing audit events; read access is not currently audited elsewhere and adding it would create noisy recursive records.

## Tradeoffs

- The repository contract currently returns all events. For this small internal slice, filtering in a domain query service is acceptable and avoids schema/index migrations.
- The `page_size` cap of 200 limits memory and UI payload size.
- Full filtered dataset export is deferred. Current-page CSV export is enough for first inspection workflows without backend file generation.

## Compatibility

- Existing audit persistence remains valid.
- Existing OpenAPI changes are additive.
- Existing health metrics remain unchanged.
- Frontend Admin route guard follows current router metadata conventions.
