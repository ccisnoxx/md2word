# Acceptance Center release evidence sync

## Goal

让 Acceptance Center 明确展示当前 P0/P1/P2 release evidence 状态，避免历史 starter summaries 或人工 review 被误读为最新发布通过证据。

## Evidence

- `docs/api/acceptance.md` defines Acceptance Center as an admin-only evidence index and says starter summaries must be replaced by current reports.
- `app/domains/acceptance/defaults.py` seeds historical/unknown summaries, including P1/P2 blockers.
- `frontend/src/pages/AcceptanceCenterPage.vue` already exposes runs, latest summary, review drawer, and manual registration flows.

## Requirements

- R1. Preserve Acceptance Center as an evidence index; do not store binary PDFs/DOCX, full text, prompts, responses, JWTs, or secrets.
- R2. Ensure latest-summary is derived from current evidence and cannot silently promote unknown/failed records to passed.
- R3. Keep P0/P1/P2 blockers and warnings visible to admin reviewers.
- R4. Support manual registration of externally generated hostdzire/staging reports.
- R5. Keep API docs, frontend display, and backend behavior aligned.

## Acceptance Criteria

- [ ] Latest summary clearly distinguishes current passed, failed, and unknown states for P0, P1, and P2.
- [ ] Historical starter summaries are visible as historical evidence but cannot be mistaken for the current release result.
- [ ] Review actions cannot convert an unknown or failed run into passed without a real passed evidence record.
- [ ] Frontend Acceptance Center shows evidence path, blockers, warnings, reviewer, and review status for each relevant run.
- [ ] API documentation and test coverage reflect the final fields and state-transition behavior.

## Out Of Scope

- Storing raw files or sensitive provider/debug artifacts.
- Building a full release-management product.
- Replacing the P0/P1/P2 validation scripts themselves.
