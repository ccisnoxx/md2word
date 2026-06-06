# File retention policy CRUD governance design

## Current State

Phase 4 already has metadata retention planning, mark-expired, and a protected physical-delete safety contract:

- `FileUploadService` creates `document_files` and assigns `expires_at`.
- `DocumentFileRetentionPlanner` reads persisted `expires_at` and can mark uploaded expired metadata as `expired`.
- Physical delete remains a separate Admin-only manual workflow with dry-run, reason, exact confirmation, local-path containment checks, metadata preservation, and compact audit.

Before this task, retention duration came only from runtime setting `oss_file_retention_days`. There was no Admin-governed policy model.

## Design Decision

Add a dedicated file-retention policy domain instead of reusing generic resource versions.

Reasons:

- Policy resolution is file-domain specific and must integrate with upload expiration.
- Impact preview needs to scan `document_files`.
- All configured persistence backends need equivalent behavior: file, sqlite, and mysql.
- The existing audit model is compact and can record policy actions without a structured-details migration.

## Policy Model

Module: `app/domains/files/retention_policy.py`.

`FileRetentionPolicyRecord` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `policy_id` | string | Stable ID, generated as `retpol_<hex>`. |
| `name` | string | Admin-facing name. |
| `status` | `draft` / `published` / `disabled` | No hard delete. |
| `scope_type` | `global` / `file_type` | First implementation supports both. |
| `file_type` | nullable string | Required for `scope_type=file_type`; forbidden for `global`. |
| `retention_days` | int | Valid range `1..3650`. |
| `description` | nullable string | Optional human explanation. |
| `is_default` | bool | Published default policy for the same scope. |
| `created_by` / `updated_by` | nullable string | Actor IDs. |
| `created_at` / `updated_at` | datetime | UTC timestamps. |
| `published_by` / `published_at` | nullable | Publish actor and time. |
| `disabled_by` / `disabled_at` | nullable | Disable actor and time. |
| `reason` | nullable string | Latest lifecycle reason. |

Validation lives in the domain record/service so all persistence backends share the same constraints.

## Effective Policy Resolution

Resolution order:

1. Published default file-type policy matching the file type.
2. Published default global policy.
3. Runtime fallback `settings.oss_file_retention_days`.

Publishing a draft makes it the default for its scope and clears `is_default` on other policies with the same scope. `set-default` can switch between published policies in the same scope. Disabled policies are never effective.

This avoids ambiguous “newest wins” behavior and keeps rollback explicit.

## API Contract

All routes are Admin-only and mounted before `/{file_id}` under `/api/v1/files`.

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/retention/policies` | List policies plus effective policy summary per file type. |
| `POST` | `/retention/policies` | Create draft policy. |
| `GET` | `/retention/policies/{policy_id}` | Read policy detail and derived fields. |
| `PATCH` | `/retention/policies/{policy_id}` | Update draft policy only. |
| `POST` | `/retention/policies/{policy_id}/impact-preview` | Dry-run projected impact against current files. |
| `POST` | `/retention/policies/{policy_id}/publish` | Publish draft with required reason and make it default for scope. |
| `POST` | `/retention/policies/{policy_id}/set-default` | Make an existing published policy the default for scope. |
| `POST` | `/retention/policies/{policy_id}/disable` | Disable draft or published policy with required reason. |

Router responsibilities:

- Enforce Admin-only access with existing auth helpers.
- Translate request schemas to service calls.
- Record audit events for writes.
- Keep impact preview read-only.

Service responsibilities:

- Validate lifecycle transitions.
- Validate scope/file-type constraints.
- Resolve effective policy and fallback.
- Build impact preview without mutation.
- Preserve historical `expires_at`.

## Persistence

Add `FileRetentionPolicyRepositoryProtocol` with:

- `create_policy(record)`
- `get_policy(policy_id)`
- `list_policies()`
- `update_policy(policy_id, **patch)`

Adapters:

- file backend: `var/config/file_retention_policies.json`.
- sqlite backend: `file_retention_policies` table storing JSON payload plus timestamps.
- mysql backend: `file_retention_policies` table storing JSON payload plus timestamps.

This mirrors current document-file payload storage and keeps backend behavior additive.

## Upload Integration

`FileUploadService` receives a narrow `retention_days_resolver: Callable[[str], int]`.

Behavior:

- `create_upload_authorization()` resolves days for `source_pdf`.
- `register_generated_content()` resolves days for the generated file type when `expires_at` is not explicitly passed.
- Explicit `expires_at` remains authoritative.
- If no matching published default policy exists, resolver returns `oss_file_retention_days`.

The upload service stays decoupled from policy repositories and policy lifecycle rules.

## Impact Preview

`impact-preview` scans current `document_files` and returns:

- files matching the candidate policy scope.
- current `expires_at`.
- projected `expires_at = created_at + retention_days`.
- projected expired state at preview time.
- totals by status, file type, and storage provider.

It does not:

- mutate policy records.
- mutate `document_files`.
- mark expired.
- execute or prepare physical deletion.
- write audit by default.

## Audit

Compact audit actions:

- `file.retention_policy_create`
- `file.retention_policy_update`
- `file.retention_policy_publish`
- `file.retention_policy_set_default`
- `file.retention_policy_disable`

Reason text includes policy ID, scope, retention days, and human reason where required. It must not include object keys, local paths, file content, credentials, prompts, tokens, or preview payloads.

## Frontend Design

Reuse `/system-status/file-retention` and add a policy governance section above the existing retention candidate controls.

UI capabilities:

- effective policy summary.
- policy list table.
- create/edit draft dialog.
- impact preview panel.
- publish, set-default, and disable actions with required reason.

Safety copy and layout:

- State that policy changes affect new files only.
- Keep policy controls separate from physical delete controls.
- Do not auto-select delete candidates after impact preview.

## Compatibility

- Existing retention plan, mark-expired, and physical-delete APIs remain compatible.
- Existing files keep their persisted `expires_at`.
- `oss_file_retention_days` remains fallback and rollback path.
- No conversion, parsing, translation, or Word generation contract changes.

## Risks And Follow-ups

- Impact preview scans all document files; acceptable for manual Admin governance, not for scheduled high-volume cleanup.
- Historical files will not reflect new policies until a future explicit backfill safety-contract task exists.
- Audit remains compact text; compliance-grade structured details remain a separate audit-migration task.
- Policy uniqueness is service-enforced through default switching, not database uniqueness constraints.
