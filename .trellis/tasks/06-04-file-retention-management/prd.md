# File retention management

## Goal

Provide a small Admin-only foundation for file retention management without
running conversion jobs and without deleting any physical files or object
storage objects.

This task turns existing retention planning code into an internal workbench
surface: Admin can inspect expired file candidates, understand the retention
policy currently in effect, and optionally mark expired metadata as `expired`.
The feature must stay metadata-only and dry-run-first.

## Requirements

- Users
  - Admin: reviews retention candidates and marks expired metadata when needed.
  - Operator: no access to retention management surfaces.
  - QA/Ops: can use the Admin view to estimate retention impact and confirm no
    destructive cleanup is exposed.
- Scope
  - Add an Admin-only retention plan API for `document_files`.
  - Reuse `DocumentFileRetentionPlanner` and `oss_file_retention_days`.
  - Return totals, generated time, policy days, candidates, and an explicit
    statement that physical deletion is not supported by this endpoint.
  - Add a metadata-only action that marks current candidates from `uploaded` to
    `expired`; it must not delete binaries or object keys.
  - Add a small Admin-only frontend page reachable from the existing system
    status or Admin navigation area.
  - Show retention totals, candidate table, storage provider, size, expiry time,
    job link when present, and clear copy that deletion is not performed.
  - Record an audit event for the metadata marking action if implementation
    adds the action endpoint.
- Non-goals
  - Do not implement physical file deletion.
  - Do not implement retention policy CRUD, cleanup schedules, background
    deletion jobs, storage quota enforcement, cross-task file search, download
    actions, or a full file management library.
  - Do not re-run pdf-mineru parsing, translation, or Word generation flows.
  - Do not change document job creation, retry, cancel, archive, or download
    semantics.
  - Do not implement the term rule CRUD workbench or unrelated roadmap items.
- Constraints
  - Keep changes small and local to the `files` retention surface and one
    Admin page.
  - Preserve existing document file metadata shape unless an additive response
    schema is required.
  - Static `/files/retention/...` routes must be registered before
    `/files/{file_id}` so they are not treated as file IDs.
  - Operator access must return the existing role-forbidden behavior.

## Acceptance Criteria

- [ ] Admin can call a retention plan endpoint and receive current
      `document_files` retention totals plus candidate metadata.
- [ ] Operator cannot call the retention plan or metadata marking endpoint.
- [ ] The retention plan clearly reports that physical deletion is unsupported.
- [ ] Metadata marking changes eligible uploaded files to `expired` only; local
      or object-storage binaries remain untouched.
- [ ] The Admin frontend page displays totals, policy, candidate rows, expiry
      times, size, status, object key, and job link when `job_id` exists.
- [ ] The page contains no file download, physical delete, policy-editing, or
      cleanup schedule controls.
- [ ] Existing upload, document job list/detail/download behavior is unchanged.
- [ ] Minimal backend and frontend verification passes without running
      pdf-mineru parsing, translation, or Word generation.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Current planning status: not approved for implementation yet.
