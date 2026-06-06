# Audit log export governance design

## Existing Context

- `GET /api/v1/audit-events` is Admin-only and already supports filters, sort, and pagination.
- `AuditEventQueryService` owns the read-only filtering and sorting logic.
- `AuditLogPage.vue` currently exports only the already-loaded page in the browser.
- Audit events are append-only metadata records; export must not mutate them except for recording the export action itself.

## API Contract

Add:

```text
GET /api/v1/audit-events/export
```

Query parameters:

- `sort`
- `actor_role`
- `action`
- `target_type`
- `target_id`
- `actor_id`
- `q`
- `created_from`
- `created_to`
- `max_rows`, default `1000`, hard cap `10000`

Response:

```json
{
  "manifest": {
    "exported_at": "2026-06-06T00:00:00+00:00",
    "requested_by": "user_admin",
    "actor_role": "admin",
    "sort": "created_at_desc",
    "filters": {},
    "matched_count": 123,
    "exported_count": 1000,
    "max_rows": 1000,
    "truncated": true,
    "columns": ["created_at", "audit_id"],
    "audit_id": "audit_xxx"
  },
  "csv_text": "created_at,audit_id,...\n"
}
```

The actual `columns` list is:

- `created_at`
- `audit_id`
- `actor_role`
- `actor_id`
- `action`
- `target_type`
- `target_id`
- `reason`
- `trace_id`

## Data Flow

```text
HTTP query -> AuditEventQuery -> AuditEventQueryService.export_events()
  -> CSV encoder -> AuditService.record("audit_events.export")
  -> AuditEventExportResponse -> frontend download
```

The export service reuses the existing query matcher and sorter. It does not duplicate filter logic in the router or frontend.

## Governance Rules

- Admin-only via existing `require_admin_user`.
- The export endpoint requires `trace_id` and records it in the audit event.
- `max_rows` is validated at the HTTP boundary.
- The export audit event is written after CSV generation, so it is not included in the exported CSV.
- The response includes `truncated=true` when matched records exceed `max_rows`.
- CSV contains stable metadata fields only and no secrets, payload bodies, local paths, object keys, or file bytes.
- The backend does not write export files; browser download is client-side only.

## Frontend

- Keep the existing "导出当前页" action.
- Add a separate "导出筛选结果" action that calls the backend export endpoint with current filters/sort and a fixed frontend `max_rows` value.
- Display a warning message when the backend returns `truncated=true`.
- Download the returned `csv_text` as a local browser file.

## Compatibility

- Existing list API remains unchanged.
- Export works against file, sqlite, and mysql persistence because it reads through `AuditEventRepositoryProtocol`.
- OpenAPI changes require regenerating `docs/api/openapi.json`.

## Risks

- In-memory export is acceptable for the capped first version; a future async export job should be a separate task if exports become large.
- The export audit event increases the audit total by one after each successful export.
- CSV consumers may expect raw commas/newlines to be escaped; tests must cover this.
