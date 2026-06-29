# Acceptance Center P0 evidence sync audit

## Current Status

Status: P0 Golden Sample release evidence for hostdzire release `20d496e` has been synced into Acceptance Center and reviewed as approved.

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

## Latest Summary After Sync

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

## Data Boundary Check

Acceptance Center stores only the evidence summary, report path, blockers, warnings, and review metadata. This sync did not store raw PDFs, DOCX binaries, full extracted text, prompts, provider responses, JWTs, SSH details, host credentials, or secret values.
