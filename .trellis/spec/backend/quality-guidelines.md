# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

Current backend quality is enforced mostly by code shape and tests rather than a
large static-analysis toolchain. The dominant patterns are: thin FastAPI
routers, explicit service/repository boundaries, Pydantic contracts, and
behavior-preserving characterization tests for legacy conversion code.

---

## Forbidden Patterns

- Do not put new business workflow logic directly into `app/main.py` or
  `app/api/v1/router.py`.
- Do not bypass `FileJobRepository` with direct JSON file edits from routers or
  services.
- Do not return ad hoc dictionaries from API handlers when a schema already
  exists in a resource module under `app/schemas/` or the `api_v1.py`
  compatibility facade.
- Do not introduce a second testing style casually. The repo currently uses
  `unittest`/`TestCase`; mixing in pytest fixtures and markers without a broader
  migration plan adds maintenance friction.
- Do not catch broad `Exception` in normal-path business logic unless the block
  is a top-level guard that logs and re-raises or a cleanup block that re-raises.

---

## Required Patterns

- New HTTP endpoints should follow the existing dependency pattern:
  `runtime: AppRuntime = Depends(get_runtime)` and `trace_id: str = Depends(get_trace_id)`
  when request tracing matters.
- Keep routers thin:
  - parse/normalize request input
  - call a service
  - map service/domain records into response schemas
- If one resource router becomes too large, split it into nearby responsibility
  modules while preserving a single resource-level aggregator and unchanged
  external route contracts.
- Put persistence behind repository methods or protocols. `JobQueryService` and
  `JobLifecycleService` already depend on repository protocols; reuse that seam
  before adding direct storage calls elsewhere.
- Use Pydantic or dataclass models for structured records instead of untyped
  nested dictionaries passed across layers.
- When a job lifecycle change is added, update all affected state outputs:
  job record, stage message (if applicable), emitted event, and tests.
- Follow the existing file prelude convention: `from __future__ import annotations`
  appears across backend modules and tests.
- If a second caller needs a router-local helper, stop reusing a private
  underscore function across routers and extract a shared mapper/helper at a
  neutral layer such as a presenter/helper companion module.

---

## Testing Requirements

- Use the project conda interpreter for backend tests and verification:
  `/Users/sc/miniconda3/envs/md2word/bin/python`. Do not use the macOS system
  `python3` for normal `unittest` runs because it may not have project
  dependencies such as `PyYAML`.
- API and orchestration changes should add or update coverage in
  `tests/test_fastapi_jobs_backend.py`.
- Legacy conversion/runtime changes should preserve or extend the existing
  `test_*_characterization.py` coverage instead of rewriting behavior silently.
- Preferred testing patterns in this repo:
  - `unittest.TestCase` or equivalent
  - `tempfile.TemporaryDirectory()` for isolated filesystem state
  - `fastapi.testclient.TestClient` for API calls
  - local fake adapters such as `FakeMinerUClient` and `FakeConversionService`
- Cover both success and failure paths when status transitions are involved.
  Existing tests assert 200/201 flows as well as 400/403/409/503 failures.
- Minimal verification usually means a targeted `unittest` module, not a broad
  whole-repo run. Example targets:
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_translation_runtime_characterization`
- Before release, run
  `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`.
  The current release check includes the OpenAPI snapshot comparison. If it
  fails after an intentional API change, regenerate `docs/api/openapi.json`
  with the project conda interpreter:
  `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`.

---

## Code Review Checklist

- Is the new code in the right layer (`router`, `service`, `repository`,
  `core`, `client`) instead of growing a god module?
- Does every new job-state transition update the corresponding persisted event
  trail and status/progress fields?
- If the change touches callback or background flow, did it preserve
  `trace_id` propagation through request, event, and log layers?
- Are `HTTPException` status codes specific and aligned with existing API
  semantics?
- If storage behavior changed, were `job_models`, repository logic, and tests
  updated together?
- Did the change preserve current logging style with `trace_id` and other
  operational identifiers, without leaking secrets or payload bodies?
