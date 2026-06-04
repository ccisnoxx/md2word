# Job context proposals design

## Current State

`JobDetailPage` already shows task lifecycle actions, file/result summaries, event timeline, and resource snapshot labels. It does not expose proposal creation.

`TermProposalsPage` already supports Term Rule Proposal creation and both Term Rule / Translation Term Proposal review queues. The Term Rule form currently only exposes `source_job_id`; the API/types already support richer context. Translation Term Proposal has list/review actions but no create form in the frontend.

Backend changes are not required for the minimum scope because existing proposal schemas and services already persist the necessary source job/file and observed version fields.

## Scope

Implement a small frontend-only flow:

1. Add a task-context proposal card/section to `JobDetailPage`.
2. Route from job detail to `TermProposalsPage` with query parameters that encode current job context.
3. Extend `TermProposalsPage` to initialize the correct create tab from query parameters.
4. Add hidden/read-only context fields to Term Rule Proposal submission payload.
5. Add a lightweight Translation Term Proposal create tab.
6. Add source job links in proposal tables/details.

## Involved Files

- `frontend/src/pages/JobDetailPage.vue`
  - Add proposal entry UI.
  - Build context query from `job`, `source_file_id`, and `request_snapshot.resources` / `request_snapshot.term_assets`.
- `frontend/src/pages/TermProposalsPage.vue`
  - Read query params.
  - Prefill Term Rule Proposal context fields.
  - Add lightweight Translation Term Proposal create form.
  - Submit context fields through existing API wrappers.
  - Render source job links in detail panes.
- `frontend/src/components/TermProposalTable.vue`
  - Add source job column with optional route link.
  - Include `published` status label.
- `frontend/src/components/TranslationTermProposalTable.vue`
  - Add source job column with optional route link.
- `frontend/src/api/types.ts`
  - No expected change; current types already include required proposal fields.
- `frontend/src/api/termProposals.ts`
  - No expected change; current wrappers already expose create/list/review APIs.

## API Changes

No backend API change is planned.

Existing API usage:

- `POST /api/v1/term-rule-proposals`
  - Include already-supported fields:
    - `source_job_id`
    - `source_file_id`
    - `observed_term_rule_set_id`
    - `observed_term_rule_version`
    - optional `page_number`, `context_before`, `context_after` when the form has them
- `POST /api/v1/translation-term-proposals`
  - Include already-supported fields:
    - `source_job_id`
    - `source_file_id`
    - `observed_translation_term_set_id`
    - `observed_translation_term_version`
    - `changes`

## Page Changes

### Job Detail

Add a compact section near the existing overview/files areas:

- Title: task-context proposal.
- Button: create Term Rule Proposal.
- Button: create Translation Term Proposal, visible only for `en2zh_pdf_to_word`.
- Context summary: current job id, source file id, bound term rule set, and bound translation term set when present.

The buttons navigate to:

- `/term-proposals?tab=new&source_job_id=...&source_file_id=...&observed_term_rule_set_id=...&observed_term_rule_version=...`
- `/term-proposals?tab=translation-new&source_job_id=...&source_file_id=...&observed_translation_term_set_id=...&observed_translation_term_version=...`

### Term Proposals

Term Rule Proposal:

- Keep the existing create/update/disable form.
- Add a context block when `source_job_id` is present.
- Include `source_file_id`, observed term rule set id/version, and optional page/context fields in the create payload.

Translation Term Proposal:

- Add a new `translation-new` tab.
- Support one change per submission with fields:
  - action: add/update/delete
  - source term
  - target term, required for add and optional for update
  - note/reason
- Use `language_pair: "en2zh"` by default.
- Submit to existing `translationTermProposalsApi.create`.

Review:

- Source job displays as a link to `/jobs/{source_job_id}` in both Term Rule and Translation Term Proposal details.
- Tables gain a source job column for quick triage.

## Data Flow

```text
JobDetailPage job/request_snapshot
  -> query params
  -> TermProposalsPage create form state
  -> existing proposal create API
  -> existing proposal list/review API
  -> proposal tables/details with source job links
```

## Tradeoffs

- Use query params instead of a new global store. This keeps the flow bookmarkable and avoids introducing state management for one handoff.
- Do not add backend fields. The existing contract already carries enough context for Phase 1.
- Do not automatically extract source text. That belongs to later translation QA / result traceability work.
- Keep the translation proposal form intentionally small so it is not a Translation Term Set management workbench.

## Rollback

The implementation is frontend-only. Rollback is limited to reverting the affected Vue component changes; persisted proposal data remains compatible because existing backend fields are used.
