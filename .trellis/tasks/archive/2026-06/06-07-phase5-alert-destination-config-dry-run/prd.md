# Phase 5 alert destination config dry run

## Goal

Add a safe, Admin-only alert destination configuration dry-run path so operators can validate staged Slack/email/webhook destination metadata before any real external alert delivery exists.

## Requirements

- Add an additive backend config field for alert destination definitions.
- Add an Admin-only read-only API endpoint under `/api/v1/ops` to dry-run destination configuration.
- The endpoint must:
  - parse destination config from settings.
  - support destination channels `slack`, `email`, and `webhook`.
  - return destination identity, channel, enabled state, target label, allowlist, dedupe window, rate limit, and secret reference name only.
  - never return secret values, webhook URLs, tokens, credentials, provider payloads, local paths, prompt text, file bytes, or full health payloads.
  - optionally evaluate exact active alert codes against each destination allowlist.
  - report config errors as dry-run results instead of causing external side effects.
  - prove via safety metadata that no Slack/email/webhook delivery, provider call, cleanup, delete, conversion workflow, or audit write occurred.
- Add frontend API types/wrapper and an Ops dashboard dry-run panel.
- Update docs/OpenAPI and targeted tests.
- Do not implement real Slack/email/webhook sending.

## Acceptance Criteria

- [ ] `POST /api/v1/ops/alert-destinations/dry-run` is Admin-only and read-only.
- [ ] Empty destination config returns a successful dry-run response with zero destinations and safety flags all false for side effects.
- [ ] Valid destination config returns parsed destinations and allowlist match results for exact requested alert codes.
- [ ] Invalid config returns validation errors in the response without writing audit or raising 500.
- [ ] The endpoint never exposes secret values.
- [ ] Ops dashboard can run destination config dry-run without sending alerts.
- [ ] Targeted backend tests, OpenAPI export/check, frontend build, Trellis validate, `git diff --check`, and browser smoke pass.

## Notes

- This slice is integration readiness only.
- Real external alert delivery remains deferred.
