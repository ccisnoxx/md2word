# Current State Research

## Existing P1 Capabilities

- Backend already models `direct_pdf_to_word` and `en2zh_pdf_to_word`.
- Document Jobs execution translates DocumentIR before saving the translated IR and rendering Word.
- Translation audit writes metadata-only `ai_call_log` and optional full-text `ai_debug_archive` with expiry.
- `GET /api/v1/document-jobs/{job_id}/translation-qa` reads existing artifacts and returns QA state, segments, term traces, and AI calls.
- `PATCH /api/v1/document-jobs/{job_id}/translation-qa` updates task-level QA state and avoids storing full text in events.
- Translation Profile, Translation Term Set, and Translation Term Proposal APIs/pages already exist.
- P1 test fixtures include one synthetic smoke sample and a manifest that expects up to three datasheet samples.

## Gaps To Close

- P1 formal sample set is incomplete; current manifest has only one available synthetic sample.
- Frontend upload currently sends `debug_full_text: false`, which prevents source/AI/final comparison in normal QA review.
- QA evidence depends heavily on artifacts; durable SQL term trace persistence exists but is not clearly wired into the main translation execution path.
- Profile limits such as max pages/chars need to be enforced or explicitly documented; silent truncation is not acceptable.
- P1 needs a distinct online regression/signoff path and `p1_beta_ready` evidence, separate from P0 Golden Sample.
- Some docs still reflect pre-P0-completion evidence and need alignment with hostdzire completion facts.

## Constraints

- Do not start local services or connect local MySQL/Redis.
- Do not broaden scope to generic PDF translation.
- Keep P0 Word quality as a dependency/evidence source, not a P1 rebuild target.
- Use MySQL + Celery single worker as production baseline.
- Admin owns sample source, reviewer assignment, and final signoff.
