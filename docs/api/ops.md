# Ops Recovery Actions API

## Scope

`/api/v1/ops/recovery-actions` provides an Admin-only, read-only recovery action registry and exact-target preview contract.

It does not execute recovery, cancellation, provider calls, alert delivery, cleanup, scheduler loops, physical deletion, S3 deletion, MinerU recovery, translation providers, or Word generation.

## Endpoints

### `GET /api/v1/ops/recovery-actions`

Returns the current recovery action registry and a safety object.

Each action includes:

- stable identity: `action_id`, `label`, `category`, `target_type`
- availability and routing: `available`, `known_gaps`, `suggested_route`
- gates: `requires_admin`, `requires_reason`, `requires_confirmation`, `dry_run_supported`
- risk flags: `mutates_metadata`, `mutates_queue`, `calls_provider`, `sends_notification`, `deletes_data`
- audit contract: `audit_action`

Candidate-only actions such as provider cancellation, alert delivery, and automated cleanup execution are listed with `available=false` until their execution contracts are implemented and reviewed.

### `POST /api/v1/ops/recovery-actions/preview`

Request:

```json
{
  "action_id": "document_job.retry",
  "target_type": "document_job",
  "target_id": "docjob_123"
}
```

Response includes:

- `eligible`
- `missing_gates`
- safe target summary
- risk flags
- audit action
- safety metadata proving no execution or mutation occurred

Unknown actions return `404`. Mismatched `target_type` returns `400`.

## Safety Contract

The registry and preview endpoints return:

```json
{
  "read_only": true,
  "execution_performed": false,
  "metadata_mutated": false,
  "queue_mutated": false,
  "provider_calls_executed": false,
  "notification_delivery_executed": false,
  "cleanup_executed": false,
  "delete_executed": false,
  "audit_events_written": false
}
```

Preview reads only metadata repositories. It does not call `stage_service`, `stage_dispatcher`, lifecycle execution services, provider clients, file delete services, or notification integrations.
