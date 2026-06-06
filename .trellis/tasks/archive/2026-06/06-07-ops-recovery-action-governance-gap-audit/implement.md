# Ops recovery action governance gap audit implementation plan

## Checklist

1. Confirm planning-only scope
   - Verify worktree is clean before creating the task.
   - Confirm no active Trellis task.
   - Create `ops-recovery-action-governance-gap-audit`.

2. Gather evidence
   - Review Phase 4 roadmap scope.
   - Review archived `ops-alerting-and-recovery-readiness`.
   - Review archived `file-retention-scheduled-cleanup-readonly-plan`.
   - Review archived `file-retention-physical-delete-safety-contract`.
   - Review archived `audit-log-export-governance`.
   - Review `document_jobs` retry/cancel/archive behavior.
   - Review legacy `jobs` retry/cancel/recover/cleanup behavior.
   - Review `MinerUClient` local provider capability.

3. Write planning artifacts
   - Replace template `prd.md`.
   - Add `design.md` with gap matrix, risk taxonomy, safety contract, and follow-up task map.
   - Add `implement.md`.
   - Replace template `implement.jsonl` and `check.jsonl` with real spec/research context.

4. Validate planning state
   - Run `python3 ./.trellis/scripts/task.py validate 06-07-ops-recovery-action-governance-gap-audit`.
   - Run `git diff --check`.
   - Confirm `task.json.status` remains `planning`.
   - Confirm no production code is modified.

## Validation Commands

```bash
python3 ./.trellis/scripts/task.py validate 06-07-ops-recovery-action-governance-gap-audit
git diff --check
python3 ./.trellis/scripts/task.py current --source
git status --short
```

## Observed Validation

- PASS: `python3 ./.trellis/scripts/task.py validate 06-07-ops-recovery-action-governance-gap-audit`
- PASS: `git diff --check`
- OBSERVED: `python3 ./.trellis/scripts/task.py current --source` reports `.trellis/tasks/06-07-ops-recovery-action-governance-gap-audit`.
- OBSERVED: `git status --short` shows only the new planning task directory.

## Non-Execution Reminder

Do not run `task.py start`.

Do not run pdf-mineru parsing, real translation providers, Word generation, provider cancellation, alert delivery, scheduler loops, automated cleanup execution, physical deletion, S3 deletion, or provider recovery calls.

## Review Gate

After validation, stop for user review. The recommended next implementation slice is `ops-recovery-action-safety-registry`, but this task must not implement it.
