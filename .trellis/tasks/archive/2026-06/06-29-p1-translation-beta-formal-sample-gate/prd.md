# P1 translation beta formal sample gate

## Goal

补齐 P1 翻译 beta 的正式样本门槛和回归证据，让 en2zh PDF-to-Word beta 能被判断为可内测、受阻或需要继续修复。

## Evidence

- `README.md` defines P1 as an en2zh PDF-to-Word beta focused on translation QA, terminology governance, human review, and evidence loops.
- `tests/fixtures/p1_translation_samples/manifest.yaml` targets 3 samples but currently has only `p1-en-001` available; `p1-en-002` and `p1-en-003` are `pending_pdf`.
- `scripts/ops/run_p1_translation_regression.py` is the existing P1 regression entrypoint.
- `.trellis/tasks/06-26-translation-provider-batching-recovery-phase-3/` owns long-PDF provider batch validation and must be coordinated with this task.

## Requirements

- R1. Obtain two additional real English datasheet samples or record a user-approved replacement standard.
- R2. Run the formal P1 regression only when the sample manifest and environment are ready.
- R3. Record translation QA, terminology, structure, editable DOCX, and manual review outcomes.
- R4. Keep sample/report artifacts redacted according to existing docs and task rules.
- R5. Do not reimplement provider batch recovery work already owned by the existing Phase 3 task.

## Acceptance Criteria

- [ ] The P1 sample manifest contains 3 available formal samples, or a documented user decision explains the approved substitute sample set.
- [ ] Formal P1 regression runs with the intended gate flag/environment and records job IDs, terminal states, DOCX output, and report path.
- [ ] Each sample records term hit, structure invariant, editable Word, and manual translation-quality verdicts.
- [ ] Failed or blocked samples produce explicit blockers with enough evidence for follow-up triage.
- [ ] Acceptance Center or the release evidence flow receives a P1 latest-summary-compatible result.

## User Decision Needed

- The user must decide whether the missing two samples come from real private datasheets, newly added repo fixtures, or an explicitly accepted substitute sample set.

## Out Of Scope

- Supporting zh2en, zh2ru, generic translation directions, or non-datasheet PDF classes.
- Rebuilding translation provider batching/fan-in logic.
- Making batch-level retry/cancel/requeue write operations.
