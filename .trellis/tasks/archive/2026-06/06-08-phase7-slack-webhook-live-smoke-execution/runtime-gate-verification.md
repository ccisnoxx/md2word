# Phase 7 Slack Webhook Live Smoke Runtime Gate Verification

## Decision

Deferred as `deferred_by_operator_no_send` on 2026-06-09.

This task entered execution, but runtime gates did not pass. No Slack/webhook provider call was made, so this does not count as the approved exactly-one live-smoke send attempt.

The operator later decided not to use Slack webhook delivery for now. Secret injection, authenticated preview, and live send are no longer the next planned actions.

## Approved Contract

- destination id: `ops-slack-primary`
- channel: `slack`
- secret ref name: `OPS_SLACK_WEBHOOK_URL`
- allowed alert code: `stage_spool_failed_messages_present`
- confirmation phrase: `SEND REAL OPS ALERTS`
- maximum live attempts: `1`
- rollback posture: disable real alert delivery flags and remove or rotate the `OPS_SLACK_WEBHOOK_URL` secret ref in the target runtime; do not delete evidence artifacts.

## Runtime Gate Evidence

- Execution task was started before verification.
- Local API health check against `http://127.0.0.1:8000/api/v1/health` failed because no server was accepting connections.
- Runtime construction initially failed because the configured MySQL backend required `PyMySQL`; `PyMySQL 1.2.0` was installed into the `md2word` conda environment.
- Runtime construction still failed before preview because the configured MySQL host `mysql` could not be resolved or reached from this process.
- `OPS_SLACK_WEBHOOK_URL` was not configured in the current process environment; no secret value was read or printed.
- Preview did not complete, so destination, capability, active alert, dedupe, and rate-limit runtime gates were not verified.

## Online Runtime Follow-up

The hostdzire deployment was checked through the existing SSH entrypoint on 2026-06-09.

- Docker deployment exists at `/root/md2word`.
- `md2word-p0-api-1`, `md2word-p0-worker-1`, `md2word-p0-mysql-1`, and `md2word-p0-redis-1` were running; API health at `http://127.0.0.1:18000/api/v1/health/live` returned healthy.
- The deployment directory is not a git checkout; it is a copied source tree.
- The running API image is stale for Phase 7 Slack live smoke: `/api/v1/ops/alert-deliveries/real-send/preview` returned `404`, and `app.domains.ops.real_alert_delivery` was not importable in the API container.
- `OPS_SLACK_WEBHOOK_URL` was missing from `/root/md2word/deploy/p0.env` and from the running API container environment. The local `.env` and local `deploy/p0.env` also did not contain this secret ref.
- No secret value was read, printed, copied, or stored.

## Online Code Deployment Follow-up

Hostdzire code deployment and API rebuild were performed on 2026-06-09, still without any live send.

- A pre-update source backup was created under `/root/md2word-deploy-backups/`.
- Runtime source files and `docker/prod` deployment config were copied to `/root/md2word`; local `.env`, `deploy/p0.env`, runtime data, and internal-user config were not overwritten.
- Rebuild/restart command used the running compose contract: `/root/md2word/docker/prod/docker-compose.yml` with `/root/md2word/.env`.
- `md2word-p0:latest` was rebuilt, and `md2word-p0-api-1` plus `md2word-p0-worker-1` were recreated.
- API, worker, MySQL, and Redis containers were running after restart; API health returned healthy.
- `app.domains.ops.real_alert_delivery` became importable inside the API container.
- Preview endpoint check changed from stale-code `404` to authenticated-route `401`, confirming the route is now present but was not invoked with execution credentials.
- `OPS_SLACK_WEBHOOK_URL` remains missing from the running API container environment, and no real webhook value was found in local or remote configuration searches.
- No provider call was made and no live-smoke attempt was consumed.

## Execution Result

- provider call executed: `false`
- external delivery executed: `false`
- live send attempt consumed: `false`
- secret value disclosed: `false`
- operator decision: `defer_slack_webhook_feature`

## Not Run

- No Slack/webhook live send.
- No direct webhook URL call.
- No provider cancellation.
- No real S3 delete or LocalStack delete.
- No cleanup scheduler execute.
- No conversion main flow.
- No git stage, commit, push, branch switch, archive, or destructive cleanup.

## Deferred Retry Requirements

These steps are no longer active next actions. If the feature is reopened later:

1. Re-approve Slack webhook delivery and exactly-one live-smoke scope.
2. Configure `OPS_SLACK_WEBHOOK_URL` in the active hostdzire runtime env. The current running compose uses `/root/md2word/.env`; `/root/md2word/deploy/p0.env` is not the active env file for `docker/prod/docker-compose.yml`. Do not expose the value.
3. Restart the API container after secret injection and verify the container reports secret-ref presence without printing the value.
4. Re-run preview/runtime gates against `http://127.0.0.1:18000` and verify destination id, capability flags, active alert code, dedupe, rate limit, timeout, confirmation phrase, and secret-ref presence.
5. Only after all gates pass, execute exactly one live send attempt.
