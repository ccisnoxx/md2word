# Translation Term Governance Diff

## Goal

Add a focused Translation Term Set governance workbench for Admins to inspect
draft-vs-version diffs, run publish preflight, and preview pending proposal
compatibility before manual review.

This task continues the completed Translation Term Set management and hardening
work. It must stay review-first and non-destructive: show what would change,
why publish is safe or blocked, and which pending proposals may conflict, but
do not introduce per-row Translation Term CRUD or automatic conflict rebase.

## Requirements

- Users
  - Admin: reviews draft changes, pending Translation Term Proposals, and
    publish readiness from one Translation Term Set governance surface.
  - Operator: continues to submit Translation Term Proposals from job context;
    this task does not add new Operator mutation capability.
  - QA/Ops: can verify that default-version changes still affect only future
    jobs and that existing job resource snapshots remain immutable.
- Backend API
  - Add a read-only diff contract for a Translation Term Set target version
    against a base version.
  - Default comparison should be current default version vs current draft.
  - Return summary counts and field-level changed entries.
  - Add a read-only preflight contract that combines current draft validation,
    diff summary, and publish-blocking reasons.
  - Add a read-only proposal compatibility preview for pending Translation Term
    Proposals against the current draft/default context.
  - Preserve existing import/export/publish/set-default/rollback contracts.
  - Preserve existing job creation and retry resource snapshot binding.
- Frontend
  - Reuse `TranslationTermSetPage`.
  - Add diff/preflight sections that Admins can scan before publishing.
  - Show added, removed, and changed terms with before/after values and changed
    field names.
  - Show pending proposals grouped as compatible, warning, or conflict where
    backend can determine that safely.
  - Link to existing proposal review flows rather than adding a new batch
    mutation workflow in this task.
- Documentation/tests
  - Update API docs and OpenAPI snapshot for new read-only contracts.
  - Add targeted backend API/service tests for diff, preflight, proposal
    compatibility, missing version, and non-MySQL `503`.
  - Run frontend build after TypeScript/page changes.
- Constraints
  - Keep changes small and local to Translation Term Set service/router,
    schemas, docs, existing page/API wrapper, and tests.
  - Use structured response models; do not return ad hoc dicts from routers.
  - Use existing validation semantics where possible.
  - Do not run pdf-mineru parsing, translation provider calls, or Word
    generation.

## Acceptance Criteria

- [x] Admin can view current default-vs-draft diff for a Translation Term Set.
- [x] Diff response contains summary counts for added, removed, changed, and
      unchanged terms.
- [x] Changed terms include `before`, `after`, and `changed_fields`.
- [x] Admin can run a read-only preflight that reports validation errors,
      warnings, diff summary, and whether publish should be blocked.
- [x] Pending Translation Term Proposals can be previewed against current draft
      without changing proposal status or draft entries.
- [x] Proposal compatibility preview uses structured conflict/warning items, not
      only free-text strings.
- [x] Frontend displays diff and preflight in `TranslationTermSetPage` without
      adding per-row CRUD controls.
- [x] Existing CSV import/export/publish/set-default/rollback behaviors remain
      unchanged.
- [x] Existing job creation/retry binding to Translation Term Set versions
      remains unchanged.
- [x] API docs, OpenAPI snapshot, backend tests, and frontend build are updated
      or verified.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Recommended first implementation slice: read-only diff + preflight +
  proposal compatibility preview. Batch approve/reject, automatic rebase, and
  row-level CRUD should remain separate follow-up tasks.
- Completion status: first implementation slice completed on 2026-06-04.
