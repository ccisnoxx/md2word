# Acceptance Center release evidence sync audit

## Current Status

Status: current P0, P1, and P2 release evidence has been synced into Acceptance Center and reviewed as approved. Latest summary has no blockers; it remains `needs_attention` only because P1/P2 warnings are still visible.

## Source Evidence

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Source task | `.trellis/tasks/06-29-p0-golden-sample-release-evidence-closure/acceptance-audit.md` |
| Release | `/root/md2word-releases/20d496e` |
| Commit | `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3` |
| Deployment ID | `hostdzire-20260629T070215Z-20d496e` |
| Golden Sample run directory | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z` |
| Golden Sample report | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z/report.md` |
| Automated regression | 4/4 succeeded; 4/4 DOCX openable; pass rate 100%. |
| Admin manual signoff | `final_signoff=true`; `p0_release_ready=true`; signed at `2026-06-29T07:16:05Z`. |
| Accepted non-blocking flags | `gs-004` retained `docx_manual_list_markers:10` and `docx_unstyled_heading_candidates:17`, accepted by admin notes as non-blocking. |

## Acceptance Center Sync

Executed on: 2026-06-29

| Field | Result |
| --- | --- |
| API route used | Acceptance Center admin API through the running hostdzire API container. |
| Run ID | `acceptance_p0_golden_sample_current` |
| Upsert HTTP status | `200` |
| Review HTTP status | `200` |
| Detail HTTP status | `200` |
| Latest summary HTTP status | `200` |
| Title | `P0 Golden Sample release evidence - hostdzire 20d496e` |
| Tier | `P0` |
| Status | `passed` |
| Environment | `hostdzire` |
| Source | `manual_import:p0_golden_sample_run` |
| Report path | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z/report.md` |
| Started at | `2026-06-29T07:05:06Z` |
| Finished at | `2026-06-29T07:16:05Z` |
| Blockers | none |
| Warnings | none |
| Reviewer | `admin-20260531` |
| Review decision | `approved` |
| Reviewed at | `2026-06-29T07:31:22.813484Z` |
| Updated at | `2026-06-29T07:31:22.813490Z` |

The synced summary records that hostdzire release `20d496e` passed P0 Golden Sample with 4/4 successful jobs, 4/4 manually opened DOCX files, admin manual signoff, and `p0_release_ready=true`.

## Latest Summary After P0 Sync

| Summary field | Result |
| --- | --- |
| Generated at | `2026-06-29T07:31:22.988032Z` |
| P0 latest run | `acceptance_p0_golden_sample_current` |
| P0 latest status | `passed` |
| P0 risk level | `success` |
| P0 blockers | none |
| P0 warnings | none |
| Latest reviewed run | `acceptance_p0_golden_sample_current` |
| Latest reviewed decision | `approved` |
| Missing tiers | none |
| Overall status | `blocked` |
| Blocker count | `3` |
| Warning count | `4` |

`overall_status=blocked` is expected after this P0-only sync because P1/P2 latest records still carry blockers or warnings. It does not indicate a P0 failure.

## P1 Acceptance Center Sync

P1 evidence was synced by `.trellis/tasks/06-29-p1-translation-beta-formal-sample-gate/formal-sample-gate-audit.md`.

| Field | Result |
| --- | --- |
| Run ID | `acceptance_p1_translation_current` |
| Tier | `P1` |
| Status | `passed` |
| Environment | `hostdzire` |
| Source | `manual_import:p1_translation_formal_run` |
| Report path | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/20260629T084801Z/report.md` |
| Review decision | `approved` |
| Latest risk level | `warning` |
| Blockers | none |
| Warnings | `translation_batch_truncation_not_observed` |

The warning is retained because the formal sample set did not reproduce live truncation. It does not block P1 acceptance.

## P2 Acceptance Center Sync

P2 evidence was synced by `.trellis/tasks/archive/2026-06/06-29-ops-gate-and-recovery-readiness/p2-ops-readiness-audit.md` after deploying hostdzire release `a2bf3e1`.

| Field | Result |
| --- | --- |
| Current runtime release | `/root/md2word-releases/a2bf3e1` |
| Deployment ID | `hostdzire-20260630T022658Z-a2bf3e1` |
| Run ID | `acceptance_p2_online_gate_current` |
| Tier | `P2` |
| Status | `passed` |
| Review decision | `approved` |
| Reviewer | `admin` |
| P2 online gate report | `/app/tests/tmp/p2_online_runs/20260630T023020Z/report.md` |
| Updated at | `2026-06-30T02:31:04.968600Z` |
| Blockers | none |
| Warnings | `document_jobs_failed_present` |

The P2 online gate passed live, ready, metrics, ops-alerts, public ingress, release check, P0 preflight, and P1 preflight. The remaining warning reflects existing failed job history surfaced by ops alerts; it is not a P2 blocker.

## Final Latest Summary

Queried from hostdzire Acceptance Center on 2026-06-30 after P2 sync:

| Summary field | Result |
| --- | --- |
| Generated at | `2026-06-30T02:40:07.267954Z` |
| Missing tiers | none |
| Overall status | `needs_attention` |
| Blocker count | `0` |
| Warning count | `2` |
| Latest reviewed run | `acceptance_p2_online_gate_current` |
| Latest reviewed decision | `approved` |
| P0 latest run | `acceptance_p0_golden_sample_current` |
| P0 latest status / decision / risk | `passed` / `approved` / `success` |
| P0 blockers / warnings | none / none |
| P1 latest run | `acceptance_p1_translation_current` |
| P1 latest status / decision / risk | `passed` / `approved` / `warning` |
| P1 blockers / warnings | none / `translation_batch_truncation_not_observed` |
| P2 latest run | `acceptance_p2_online_gate_current` |
| P2 latest status / decision / risk | `passed` / `approved` / `warning` |
| P2 blockers / warnings | none / `document_jobs_failed_present` |

This satisfies the release evidence sync goal: Acceptance Center no longer relies on starter summaries for P0/P1/P2, and the latest summary keeps current blockers and warnings visible instead of silently promoting review metadata into passed evidence.

## Data Boundary Check

Acceptance Center stores only the evidence summary, report path, blockers, warnings, and review metadata. This sync did not store raw PDFs, DOCX binaries, full extracted text, prompts, provider responses, JWTs, SSH details, host credentials, bearer tokens, or secret values.
