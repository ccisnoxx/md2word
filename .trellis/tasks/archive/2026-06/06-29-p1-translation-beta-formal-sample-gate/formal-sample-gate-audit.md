# P1 formal sample gate audit

## Current Status

Status: passed with warning. Hostdzire P1 formal en2zh regression passed on release `20d496e`, admin manual translation-quality signoff is valid, and Acceptance Center run `acceptance_p1_translation_current` is synced and approved. The latest P1 risk remains `warning` because the small formal sample set did not reproduce live truncation.

## Source Evidence

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Task | `.trellis/tasks/06-29-p1-translation-beta-formal-sample-gate/` |
| Original preflight command | `P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight --preflight-output tests/tmp/p1_translation_runs/formal-preflight-20260629.json` |
| Credential handling | `P1_TRANSLATION_PASSWORD` and `P1_TRANSLATION_BEARER_TOKEN` were explicitly empty for this local preflight, so no secret was read or stored. |
| Original preflight report | `tests/tmp/p1_translation_runs/formal-preflight-20260629.json` |
| Original preflight overall | `ok=false` |
| Latest local preflight report | `tests/tmp/p1_translation_runs/formal-preflight-20260629-samples-ready.json` |
| Latest local preflight overall | `ok=false` because local credentials were intentionally absent. |
| Latest manifest preflight | `ok=true`; `available_samples=3`; `required_samples=3`; `missing_pdf_files=[]`. |
| Manifest path | `tests/fixtures/p1_translation_samples/manifest.yaml` |
| Available formal samples before user decision | `1` |
| Available formal samples after manifest update | `3` |
| Required formal samples | `3` |
| Missing available PDF files | none |
| Final formal sample files | `OPA228_P1.pdf`, `OPA228_P2.pdf`, `OPA228_P7.pdf` |
| Out-of-scope offered sample | `диод анод сверху.pdf` is Russian and remains outside this en2zh P1 gate. |

## Blockers

| Blocker | Meaning | Gate impact |
| --- | --- | --- |
| `p1_available_sample_count_below_required` | Original blocker from the first local preflight: formal mode required 3 available samples, but the manifest exposed only `p1-en-001`. | Resolved by user decision and manifest update. |
| `p1_auth_missing` | No admin password or bearer token was supplied for this local preflight. | Runtime validation and job creation were intentionally not attempted. |
| `p1_runtime_unreachable` | Runtime preflight could not authenticate because credentials were intentionally absent. | Remaining blocker for local-only evidence; rerun on hostdzire with credentials. |

## Latest Local Preflight

The latest local formal preflight was rerun after the manifest update:

```bash
P1_TRANSLATION_FORMAL=1 \
P1_TRANSLATION_PASSWORD= \
P1_TRANSLATION_BEARER_TOKEN= \
.venv/bin/python scripts/ops/run_p1_translation_regression.py \
  --preflight \
  --preflight-output tests/tmp/p1_translation_runs/formal-preflight-20260629-samples-ready.json
```

Result:

- `manifest` check passed with 3 available samples and 0 missing PDFs.
- `auth` check failed with `p1_auth_missing` because credentials were intentionally absent.
- `runtime` check failed with `p1_runtime_unreachable` because the preflight could not authenticate without credentials.

This confirms the sample gate is no longer the blocker.

## Hostdzire Formal Regression Attempt

The first hostdzire formal regression used `OPA228_P1.pdf`, `OPA228_P2.pdf`, and `OPA228_P6.pdf` from the existing Golden Sample fixture set.

| Field | Result |
| --- | --- |
| Release | `/root/md2word-releases/20d496e` |
| Preflight report | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/formal-preflight-20260629-hostdzire.json` |
| Regression run dir | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/20260629T083230Z` |
| Automated jobs | 3/3 succeeded; 3/3 DOCX openable; 3/3 QA evidence available; 3/3 translation batch diagnostics available. |
| Gate result | `p1_beta_ready=false`; blocker `p1_automated_chain_target_not_met`. |
| Root cause | The original expected terms were inherited from synthetic/pending sample placeholders and did not match the selected OPA228 pages. `OPA228_P2.pdf` and `OPA228_P6.pdf` did not contain the declared governed en2zh terms. |
| Operational note | A temporary Celery worker was started for `document-translation-batches` because the deployed worker listens only to `document-jobs`; without it, the first job stayed in `ir_converting` with a queued translation batch. |

The formal sample manifest was adjusted after this run: `OPA228_P7.pdf` replaces `OPA228_P6.pdf` to cover the Electrical Characteristics page and `expected_terms` now reflect terms actually present in the selected PDF pages.

## Final Hostdzire Formal Run

Executed on: 2026-06-29

| Field | Result |
| --- | --- |
| Release | `/root/md2word-releases/20d496e` |
| Preflight report | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/formal-preflight-20260629-hostdzire-v2.json` |
| Regression run dir | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/20260629T084801Z` |
| Report files | `report.json`, `report.md`, `manual-signoff-template.yaml`, and `manual-signoff.yaml` exist. |
| Configured / available / required samples | 3 / 3 / 3 |
| Formal mode | `true` |
| Automated chain | `automated_chain_met_target=true` |
| Jobs | 3/3 succeeded |
| DOCX | 3/3 openable; generated DOCX files copied back to the host release run dir. |
| QA evidence | 3/3 available; source comparison available; debug full-text archive enabled with one debug archive per sample. |
| Translation batch diagnostics | 3/3 available; no diagnostics blockers; `translation_batch_truncation_not_observed` retained as a warning. |
| Manual signoff | `final_signoff=true`; reviewer role `admin`; reviewer `admin`; signed at `2026-06-29 08:52:45.543065+00:00`. |
| Final P1 result | `p1_beta_ready=true`; `p1_beta_blocker=null`. |

| Sample | File | Job ID | DOCX openable | Term result | Batch result | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `p1-en-001` | `OPA228_P1.pdf` | `docjob_ec55d8dcfc1e` | true | `slew rate`, `quiescent current`; hit rate 1.0 | 1/1 batch succeeded | Pass. |
| `p1-en-002` | `OPA228_P2.pdf` | `docjob_86ee2a4b6081` | true | no governed expected terms on this TOC/revision-history page; hit rate 1.0 | 1/1 batch succeeded | Pass; `docx_manual_list_markers:14` and `docx_unstyled_heading_candidates:18` accepted as non-blocking for P1 beta. |
| `p1-en-003` | `OPA228_P7.pdf` | `docjob_07b2e38608d5` | true | `input offset voltage`; hit rate 1.0 | 1/1 batch succeeded | Pass. |

## Acceptance Center Sync

Executed on: 2026-06-29

| Field | Result |
| --- | --- |
| Run ID | `acceptance_p1_translation_current` |
| Upsert HTTP status | `200` |
| Review HTTP status | `200` |
| Latest summary HTTP status | `200` |
| Title | `P1 translation beta formal run - hostdzire 20d496e` |
| Tier | `P1` |
| Status | `passed` |
| Environment | `hostdzire` |
| Source | `manual_import:p1_translation_formal_run` |
| Report path | `/root/md2word-releases/20d496e/tests/tmp/p1_translation_runs/20260629T084801Z/report.md` |
| Review decision | `approved` |
| P1 latest risk level | `warning` |
| P1 blockers | none |
| P1 warnings | `translation_batch_truncation_not_observed` |
| Latest summary overall status | `blocked` |
| Latest summary blocker count | `1` |
| Latest summary warning count | `3` |

`overall_status=blocked` remains expected after P1 sync because P2 still has unresolved release evidence blockers. It does not indicate a P1 failure.

## Runtime Follow-Up

The deployed worker command currently starts Celery with `-Q document-jobs`, while P1 translation batches are routed to `document-translation-batches`. During this run, the first P1 job reached `ir_converting` with a queued translation batch and did not progress until a temporary worker was started for `document-translation-batches`. The temporary worker was removed after the regression completed.

This is now treated as a follow-up operations/runtime readiness issue: production/staging workers that support P1 translation must consume both `document-jobs` and `document-translation-batches`, or run a dedicated translation-batch worker.

Local fix prepared after the formal run: `scripts/dev/run_document_worker.py` now starts Celery with both configured queues, `/health/ready` exposes `document_jobs_translation_batch_celery_queue`, and Celery-mode readiness/preflight reports `document_jobs_translation_batch_celery_queue_missing` when it is blank. The fix still needs deployment to hostdzire and a runtime smoke/preflight confirmation on the next release.

## Decision Status

The user resolved the sample-source decision on 2026-06-29:

- Use real English datasheets from the existing fixture set for the next P1 step.
- Keep the Russian datasheet out of scope for this en2zh gate.

The operational credential decision was resolved for this run by using hostdzire admin bearer-token auth generated inside the deployed runtime. No token or password value is stored in task evidence.

## Superseded Acceptance Center Import Candidate

This earlier candidate is superseded by the final passing Acceptance Center sync above:

| Field | Suggested value |
| --- | --- |
| Run ID | `acceptance_p1_translation_current` |
| Title | `P1 translation beta formal sample gate - runtime pending` |
| Tier | `P1` |
| Status | `unknown` |
| Environment | `local-preflight` |
| Source | `manual_import:p1_translation_formal_preflight` |
| Report path | `tests/tmp/p1_translation_runs/formal-preflight-20260629.json` |
| Summary | `Formal P1 translation beta manifest now has 3 available English datasheet samples. Runtime/job regression was not attempted because credentials were intentionally absent in local preflight.` |
| Blockers | `p1_auth_missing`, `p1_runtime_unreachable` |
| Warnings | `p1_formal_regression_not_run`, `p1_manual_translation_quality_signoff_not_started` |

This candidate is retained only as historical context for the local-preflight blocked state before hostdzire execution.

## Data Boundary Check

This audit stores only sample counts, report paths, blocker/warning codes, job IDs, file names, and summary verdicts. It does not store raw PDFs, DOCX binaries, full extracted text, prompts, provider responses, JWTs, SSH details, host credentials, bearer tokens, or secret values.
