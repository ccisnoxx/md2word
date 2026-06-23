# Component PDF Regression Governance

## Goal

Build phase 3 of the md2word/md2word_main workflow: a repeatable regression and
sample-governance system for electronic component PDFs. The system must sit on
top of the phase 2 single source of truth, where `/Users/sc/PycharmProjects/md2word/app/conversion`
owns conversion code and `md2word_main` is only a thin local debug shell and
sample-asset source.

## What I Already Know

- `md2word` is the official conversion code source.
- `md2word_main` has been migrated to a thin shell; active duplicate
  `app`, `cli_core`, and `resources` directories are gone.
- Existing P0 golden samples live under `tests/fixtures/golden_samples/` and
  focus on release acceptance for canonical OPA228 PDFs.
- Existing P1 translation samples live under `tests/fixtures/p1_translation_samples/`
  and focus on en2zh translation acceptance.
- Phase 3 needs a separate component PDF sample suite organized by brand and
  component category, with MinerU result packages as the local regression input.

## Requirements

- Add a versioned sample directory for electronic component PDF regression,
  organized by brand and category.
- Add a manifest with metadata for each sample: id, brand, category, product,
  source status, source PDF reference, MinerU package path, tags, regression
  settings, and manual acceptance focus.
- Add a deterministic way to scaffold or add a new MinerU sample from local
  development into the governed sample suite.
- Add a minimal local regression runner that converts enabled MinerU package
  samples through `app/conversion` and writes DOCX/report artifacts under
  `tests/tmp/`.
- Add an automated manifest/regression test that runs without real MinerU,
  network services, MySQL, Redis/Celery, OpenAI, or browsers.
- Add an acceptance record template for manual layout review.
- Add developer documentation that fixes the workflow:
  local issue discovery -> add sample -> fix `app/conversion` -> run regression
  -> update manual acceptance record.
- Keep P0 golden sample and P1 translation sample suites intact; this task adds
  a component-regression suite, not a release gate replacement.

## Acceptance Criteria

- [ ] `tests/fixtures/component_pdf_samples/` exists with README, manifest,
  acceptance template, and brand/category sample directories.
- [ ] The manifest contains at least one runnable small MinerU fixture organized
  by brand/category.
- [ ] A dev script validates/scaffolds component samples and supports adding a
  MinerU package from local paths.
- [ ] A dev regression runner converts enabled component samples to DOCX and
  writes machine-readable and markdown reports.
- [ ] Unit tests validate manifest contracts, add-sample/scaffold behavior, and
  the minimal local regression entrypoint.
- [ ] Docs describe how future brand/category samples should be added and
  reviewed.
- [ ] Targeted validation passes.

## Definition Of Done

- Tests added or updated for new scripts and manifest contracts.
- No rendering refactor unless a new test exposes a direct defect.
- Generated outputs remain under `tests/tmp/`.
- Docs/specs updated where the new workflow becomes a future convention.
- `git diff --check` and targeted unittests pass.

## Technical Approach

Create a new `component_pdf_samples` fixture suite rather than extending P0 or
P1 manifests. Keep the first runnable sample intentionally small and committed
as a minimized MinerU package so local tests are deterministic. Add two dev
scripts:

- `scripts/dev/manage_component_pdf_samples.py` for manifest validation and
  adding/scaffolding local MinerU packages.
- `scripts/dev/run_component_pdf_regression.py` for local DOCX regression runs.

The runner must import the official conversion runtime only. It must not call
or import `md2word_main/mineru_to_docx.py`.

## Out Of Scope

- No broad rendering/layout refactor.
- No real MinerU execution.
- No online API, worker, database, browser, or OpenAI integration.
- No committing proprietary/customer PDFs.
- No replacing the P0 golden sample release gate.

## Technical Notes

- Existing relevant files inspected:
  - `tests/fixtures/golden_samples/manifest.yaml`
  - `tests/test_golden_sample_manifest.py`
  - `tests/fixtures/p1_translation_samples/manifest.yaml`
  - `tests/test_p1_translation_sample_manifest.py`
  - `scripts/ops/run_golden_sample_regression.py`
  - `scripts/dev/audit_conversion_sandbox.py`
  - `docs/dev/local-conversion-sandbox.md`
- Backend spec applies because new dev scripts and tests live in `scripts/dev/`
  and `tests/`.
