# P0 Golden Sample release evidence closure implementation plan

## Review Gate

- [x] User reviews `prd.md`, `design.md`, and this `implement.md`.
- [x] After approval, run:

```bash
python3 .trellis/scripts/task.py start 06-29-p0-golden-sample-release-evidence-closure
```

Do not start implementation before the review gate is approved.

## Phase 1: Local Evidence Prep

- [x] Confirm the working tree only contains expected Trellis planning files before starting operational work:

```bash
git status --short --branch
```

- [x] Run local checks that do not start real services:

```bash
git diff --check
.venv/bin/python -m unittest \
  tests.test_golden_sample_manifest \
  tests.test_openapi_export.OpenAPIExportTests.test_golden_sample_preflight_release_check_requires_admin_and_p0_runtime
```

- [x] Confirm the manifest still contains exactly the 4 P0 canonical samples:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml
data = yaml.safe_load(Path("tests/fixtures/golden_samples/manifest.yaml").read_text())
print([item["id"] for item in data["samples"] if item.get("enabled", True)])
PY
```

Stop if the manifest, script contract, or local checks disagree with the PRD.

## Phase 2: Hostdzire Release Selection

- [x] Identify the target commit/full SHA and release directory on hostdzire.
- [x] Confirm the target commit is the intended code version and is available to the hostdzire release flow.
- [x] Preserve `.env`, `deploy/auth_internal_users.json`, runtime volumes, and generated output directories during release setup.
- [x] Record only non-sensitive deployment identifiers in task-local notes: target commit, short SHA, release directory basename, deployment id, and timestamp.

Use the release flow in `docs/deploy/online-first-validation-workflow.md`. Do not print or commit credentials, IPs, private key paths, or `VPS.txt` contents.

## Phase 3: Runtime And Preflight Gate

- [x] On hostdzire, confirm API/worker/container baseline:

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
docker compose --env-file .env -f docker/prod/docker-compose.yml logs --tail=120 api worker
```

- [x] Check local hostdzire API readiness:

```bash
export API_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}"
curl -fsS "${API_BASE_URL}/api/v1/health/live"
curl -fsS "${API_BASE_URL}/api/v1/health/ready"
curl -fsS "${API_BASE_URL}/api/v1/health/metrics"
```

- [x] Run release check with Golden Sample preflight:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url "http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

Stop if preflight reports any unexplained blocker. Record blockers instead of continuing to real conversion.

## Phase 4: Real Golden Sample Regression

- [x] Run the 4-sample regression on hostdzire:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

- [x] Capture the generated `run_dir`.
- [x] Confirm `report.json`, `report.md`, `manual-signoff-template.yaml`, and DOCX outputs exist.
- [x] Confirm the report records 4 configured/matched/runnable samples.
- [x] Confirm each sample has job id, terminal status, DOCX openability, and quality evidence.

If any job fails, preserve the run directory and record the blocker. Do not retry in-place or edit the report.

## Phase 5: Admin Review And Signoff

- [x] Admin opens all 4 generated DOCX files from the same `run_dir`.
- [x] Admin reviews sample-specific focus areas:
  - `gs-003`: two-column order, Features/Applications/Description, figure, Device Information table.
  - `gs-004`: TOC leaders/page numbers, Revision History, lists, header/footer boundaries.
  - `gs-006`: Thermal Information tables, symbols/units, footnotes and reading order.
  - `gs-008`: Electrical Characteristics wide table, units, special symbols, editable table fit.
- [x] If standard-render visual evidence is produced, store it next to the run evidence but do not commit it.
- [x] Admin copies `manual-signoff-template.yaml` to `manual-signoff.yaml`, fills reviewer metadata, sets `final_signoff: true`, and records per-sample verdicts/notes.
- [x] Apply signoff:

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

Signoff is valid only if the command exits successfully and `report.json` / `report.md` show `p0_release_ready=true`.

## Phase 6: Evidence Backfill

- [x] Add task-local evidence notes, for example `acceptance-audit.md`, with:
  - target commit/deployment id
  - hostdzire release directory basename
  - preflight result path and blockers
  - run id and report path
  - sample status table
  - admin reviewer/signoff timestamp
  - final `p0_release_ready` value
  - Acceptance Center handoff fields
- [x] Update `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` with the current run conclusion.
- [x] If P0 failed, document the blocker and next implementation task candidate instead of weakening acceptance.
- [x] Do not commit generated binaries, screenshots, private host details, credentials, signed URLs, or `tests/tmp/golden_sample_runs/`.

## Validation Before Finish

- [x] Validate task context files:

```bash
python3 .trellis/scripts/task.py validate 06-29-p0-golden-sample-release-evidence-closure
```

- [x] Run final text/static checks:

```bash
git diff --check
```

- [x] If docs were changed, confirm links and commands remain consistent with:
  - `README.md`
  - `docs/deploy/online-first-validation-workflow.md`
  - `docs/testing/pdf-to-word-p0-integration-guide.md`
  - `tests/fixtures/golden_samples/acceptance-record-template.md`

## Stop Conditions

- Hostdzire credentials or runtime access are unavailable.
- `/health/ready` or Golden Sample preflight has unexplained blockers.
- Any of the 4 canonical samples is missing.
- Any sample fails without a current accepted remediation plan.
- Admin signoff is missing or invalid.
- The next step would require conversion/rendering code changes.

When a stop condition occurs, record the blocker and keep `p0_release_ready=false`.
