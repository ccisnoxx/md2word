# P1 Translation QA Governance Beta

## Goal

Advance `en2zh_pdf_to_word` from an experimental entry point to a beta workflow for technical datasheet / electronics documents. The beta must produce Chinese Word output and provide enough QA evidence, terminology governance, manual review, and online validation artifacts for an internal admin to sign off.

## Current Facts

- P0 Word delivery quality is treated as established by hostdzire evidence: Golden Sample preflight `ok=true`, 4/4 Golden Sample regression succeeded, admin manual signoff `valid=true`, and `p0_release_ready=true`.
- P1 must not rework P0 renderer quality. It may reuse P0 DOCX quality evidence when translation output needs Word delivery proof.
- The current public workflow is `Files + Document Jobs`; legacy `/api/v1/jobs` is not the P1 integration surface.
- `en2zh_pdf_to_word` already exists in backend models, API schemas, execution, frontend upload mode, QA queue/detail pages, Translation Profile, Translation Term Set, and Term Proposal management.
- Production baseline remains MySQL + Celery + single worker for internal company use.
- Local validation must not start local frontend/backend or connect local MySQL/Redis. Full-chain validation runs on hostdzire.
- Golden Sample / P1 sample source, reviewer, and final signoff are admin-managed.
- Current P1 fixture manifest has one synthetic smoke PDF and pending real datasheet samples.

## Requirements

- Keep the product scope limited to technical datasheet / electronics documents.
- Make `en2zh_pdf_to_word` beta executable and reviewable in production with MySQL + Celery single-worker deployment.
- Preserve P0 Word quality boundaries: generated DOCX must remain editable and pass reused DOCX evidence checks, but P1 work should focus on translation evidence and governance.
- Provide reviewer-facing translation QA evidence:
  - bound Translation Profile and Translation Term Set/version;
  - translated DocumentIR and generated Word artifact availability;
  - AI call log availability without full text leakage;
  - optional debug archive availability, expiry, and source/AI/final text comparison when explicitly enabled;
  - terminology hit traces and evidence availability status.
- Keep `debug_full_text` off by default and expose it only as a controlled QA/debug option.
- Support the governance loop from QA to translation term proposal, admin approval, draft/preflight/diff, publish default, and rerun/clone with the current published defaults.
- Add P1-specific online regression and signoff evidence without mixing it into the P0 Golden Sample runner.
- Update README/docs/runbooks/API docs so P1 beta behavior, limits, and validation steps are clear.
- Record stage evidence and remaining risk after each implementation stage.

## Acceptance Criteria

- Task setup:
  - [ ] This PRD exists under a dedicated P1 Trellis task.
  - [ ] Relevant Trellis specs and thinking guides have been read before code changes.
- En2zh execution:
  - [ ] `en2zh_pdf_to_word` job succeeds in unit/eager tests and records profile/term resource snapshots.
  - [ ] Translation failures produce explicit errors and AI call audit evidence without full text leakage.
  - [ ] Over-limit translation inputs fail explicitly or are handled by a documented bounded strategy; no silent truncation.
- QA evidence:
  - [ ] QA detail shows whether source comparison is available and why not when unavailable.
  - [ ] Debug archive behavior is controlled by request/config, has expiry, and is visible in QA evidence.
  - [ ] QA status updates do not write source text or translated full text into audit events.
- Terminology governance:
  - [ ] Operator can create a translation term proposal from QA context with observed job/file/version.
  - [ ] Admin can approve or approve-and-publish and then verify a new job binds the updated default term version.
- Frontend:
  - [ ] `en2zh_pdf_to_word` remains disabled when readiness says unavailable.
  - [ ] `debug_full_text` is only available for the translation beta flow and is clearly permission controlled.
  - [ ] QA and governance pages expose evidence without adding a generic PDF platform surface.
- Docs and validation:
  - [ ] P1 regression docs/scripts define smoke and formal beta gates.
  - [ ] Local checks are limited to static/unit checks that do not require services.
  - [ ] Hostdzire verification plan covers MySQL + Celery full-chain validation and produces `p1_beta_ready=true` only after admin signoff.

## Out of Scope

- Generic PDF translation.
- Additional language pairs beyond `electronics-en2zh`.
- Online DOCX editing or segment-level human edit writeback.
- External customer portal, multi-tenant self-service, billing, SSO, or customer roles.
- Rebuilding P0 Golden Sample / renderer quality line.
- Multi-worker production semantics.
- Prompt editor or full translation platform governance beyond the beta loop.

## Technical Approach

- Work through the existing Document Jobs path: file upload, `DocumentJobExecutionService`, DocumentIR translation, audit artifact persistence, Word rendering, and QA retrieval.
- Reuse existing Translation Profile, Translation Term Set, and Term Proposal services instead of adding parallel governance logic.
- Treat `ai_call_log` as the durable metadata evidence and `ai_debug_archive` as short-lived full-text debug evidence.
- Prefer explicit readiness/errors over hidden fallbacks. If translation provider/profile/term assets are unavailable, fail or disable the beta path visibly.
- Add P1 regression as a separate ops surface so P0 release evidence remains stable.
- Keep frontend additions within existing pages: upload panel, QA queue/detail, term proposal review, and translation settings.

## Decision (ADR-lite)

**Context**: P0 proved Word delivery quality for direct conversion, while P1 needs a translation QA/governance loop without becoming a large translation platform.

**Decision**: Build a narrow `electronics-en2zh` beta using existing Document Jobs, Translation Profile, Term Set, Term Proposal, QA pages, and artifact evidence. P1 validation uses a separate regression/signoff gate and reuses P0 DOCX checks only as supporting evidence.

**Consequences**: The beta is internally useful and auditable, but intentionally lacks online editing, multi-language support, customer-facing workflows, and advanced automatic translation scoring.

## Implementation Plan

1. Task and evidence baseline:
   - Create this P1 task, record current-state research, read specs, and start the task.
   - Update docs that still conflict with user-provided P0 completion evidence.
2. QA evidence hardening:
   - Strengthen backend QA summaries and frontend evidence display where current artifacts are ambiguous.
   - Add controlled `debug_full_text` creation flow for P1 review.
3. Translation execution guardrails:
   - Verify profile/term snapshots, provider readiness, max page/char limits, and failure audit behavior.
   - Add or update unit tests for source comparison, debug archive, and no-full-text audit guarantees.
4. Governance loop:
   - Verify QA-to-term-proposal context, admin approve/publish, and rerun/clone with latest term defaults.
   - Close any gaps in APIs, frontend state, and tests.
5. Regression and docs:
   - Add P1-specific regression/signoff artifacts and docs.
   - Run local unit/static checks only.
   - Prepare hostdzire validation commands and evidence checklist.

## Technical Notes

- Relevant docs: `README.md`, `docs/runbooks/internal-portal.md`, `docs/deploy/online-first-validation-workflow.md`, `docs/api/document-jobs.md`, `docs/api/translation-profiles.md`, `docs/api/translation-term-sets.md`, `docs/api/translation-term-proposals.md`, `tests/fixtures/p1_translation_samples/`.
- Relevant backend areas: `app/domains/document_jobs/`, `app/domains/translation/`, `app/main.py`, `app/core/config.py`, `scripts/ops/`.
- Relevant frontend areas: `frontend/src/components/PdfUploadPanel.vue`, `frontend/src/pages/TranslationQaQueuePage.vue`, `frontend/src/pages/TranslationResultQaPage.vue`, `frontend/src/pages/TermProposalsPage.vue`, `frontend/src/pages/TranslationTermSetPage.vue`, `frontend/src/api/documentJobs.ts`, `frontend/src/types.ts`.
- Read before coding: `.trellis/spec/backend/index.md`, `.trellis/spec/guides/index.md`, `.trellis/spec/guides/cross-layer-thinking-guide.md`, `.trellis/spec/guides/code-reuse-thinking-guide.md`.
