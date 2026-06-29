# P0 Golden Sample release evidence closure

## Goal

完成最新 hostdzire P0 Golden Sample 正式回归和 admin signoff，让 P0 PDF-to-Word 发布状态可以基于当前证据判断，而不是依赖历史说明或本地 targeted checks。

## Evidence

- `README.md` defines the P0 Files + Document Jobs flow and Golden Sample quality gate.
- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` says the latest formal hostdzire regression and admin signoff are still pending.
- `docs/deploy/online-first-validation-workflow.md` says full release evidence must be collected on hostdzire/staging, not local-only.
- `tests/fixtures/golden_samples/manifest.yaml` defines the 4 canonical OPA228 samples: `gs-003`, `gs-004`, `gs-006`, and `gs-008`.
- `scripts/ops/run_golden_sample_regression.py` already supports preflight, real regression, report generation, manual signoff template generation, and signoff application.
- `tests/fixtures/golden_samples/acceptance-record-template.md` defines the admin signoff fields and pass/fail rules.

## Confirmed Facts

- P0 scope is limited to technical datasheets/electronic documents and does not expand to generic PDF conversion.
- The current release cannot claim `p0_release_ready=true` until the latest hostdzire run completes with admin signoff.
- Local checks are supporting evidence only; full API, Worker, MySQL, Redis/Celery, MinerU, and Golden Sample conversion evidence must come from hostdzire or equivalent staging.
- The regression script writes `report.json`, `report.md`, `manual-signoff-template.yaml`, downloaded DOCX files, and machine-readable DOCX quality evidence under `tests/tmp/golden_sample_runs/<run_id>/`.
- Admin signoff must be applied to the same run directory; old run evidence or historical signoff must not be reused as current release proof.

## Requirements

- R1. Run the existing P0 preflight and Golden Sample flow on hostdzire or an equivalent staging environment.
- R2. Cover the 4 canonical OPA228 Golden Sample PDFs and record job-level evidence.
- R3. Require admin manual signoff before considering P0 release-ready.
- R4. Do not broaden the quality target beyond technical datasheets/electronic documents.
- R5. Record blockers and warnings without committing private PDFs, generated customer files, secrets, or signed URLs.
- R6. Preserve failed run directories and evidence; do not overwrite or edit a failed run into a success record.
- R7. If the run exposes a conversion/rendering defect, record the blocker and stop this evidence task unless a separate implementation fix is approved.
- R8. Keep Acceptance Center import/sync work as a handoff to `06-29-acceptance-center-release-evidence-sync`; this task only produces current P0 evidence and a clear report path.

## Acceptance Criteria

- [ ] P0 preflight reports no release-blocking runtime, deployment, auth, worker, storage, MinerU, or sample availability blockers.
- [ ] All 4 Golden Sample jobs reach succeeded or have explicit blocker records with job IDs and failure evidence.
- [ ] Each successful sample has downloadable DOCX evidence plus report/visual or quality-flag evidence suitable for admin review.
- [ ] Admin manual signoff is recorded with reviewer identity, timestamp, sample verdicts, and any accepted deviations.
- [ ] The resulting report clearly states whether `p0_release_ready` is true or false and why.
- [ ] Task-local evidence notes identify the hostdzire release/deployment, run id, report path, sample status table, and handoff fields for Acceptance Center sync.

## Out Of Scope

- Fixing discovered rendering bugs in this task unless a separate implementation slice is approved.
- Adding new Golden Sample documents.
- Changing P1 translation, P2 ops, or frontend IA behavior.
- Importing or redesigning Acceptance Center records beyond producing the P0 evidence handoff.
- Committing generated DOCX, rendered screenshots, private credentials, signed URLs, or remote host details.
