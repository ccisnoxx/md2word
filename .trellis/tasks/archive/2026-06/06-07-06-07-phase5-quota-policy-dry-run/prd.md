# Phase 5 quota policy dry run

## Goal

Add a quota policy dry-run contract for upload authorization readiness so Admins can see whether a proposed upload would warn or block under staged policy settings before any real upload-blocking behavior exists.

## Requirements

- Add staged quota policy settings for:
  - policy enabled flag;
  - dry-run mode flag;
  - quota bytes;
  - warning threshold ratio;
  - block threshold ratio.
- Add an Admin-only dry-run API that accepts a proposed upload size and optional file metadata, reads current `document_files` metadata usage, and returns:
  - current used bytes;
  - projected used bytes after the proposed upload;
  - usage ratios;
  - `would_warn`;
  - `would_block`;
  - blocking/warning reasons;
  - explicit safety flags.
- The dry-run API must not:
  - create `document_files`;
  - upload file content;
  - write audit events;
  - block real upload authorization;
  - delete files;
  - call S3/provider/external systems;
  - run pdf-mineru parsing, translation, or Word generation.
- Add frontend controls on the Admin file retention/storage page to run quota policy dry-run and inspect the result.
- Keep existing upload behavior unchanged even when the staged policy reports `would_block=true`.
- Update API docs and OpenAPI snapshot.

## Acceptance Criteria

- [ ] Admin can call quota policy dry-run and receive deterministic `would_warn` / `would_block` results.
- [ ] Operator/non-admin users cannot call the dry-run API.
- [ ] Dry-run response includes safety flags proving no enforcement, upload creation, audit write, deletion, provider call, or external call occurred.
- [ ] Real `POST /api/v1/files/upload-url` remains governed only by existing upload validation and is not blocked by staged quota policy.
- [ ] Frontend build passes and the File Retention page exposes a quota dry-run panel.
- [ ] Targeted backend tests and OpenAPI export/test pass.

## Notes

- This task is integration-readiness only. Actual upload blocking requires a later task with explicit approval, override/grace semantics, and audit behavior.
