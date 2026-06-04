# Admin Job Configuration

## Goal

Let internal users create and retry document jobs with role-appropriate configuration:
Operator sees the default job configuration summary and submits with defaults; Admin can explicitly select published resource versions for the job without entering full configuration-management CRUD workflows.

## Requirements

- Operator upload flow must keep using defaults. It should show a read-only summary of the effective default resources instead of exposing version selectors.
- Admin upload flow must expose an advanced configuration area for explicit published resource versions:
  - Template Version
  - Term Rule Set Version
  - Translation Term Set Version for `en2zh_pdf_to_word`
  - Translation Profile Version for `en2zh_pdf_to_word`
- Retry flow must preserve the existing default behavior of keeping the failed job's original configuration.
- Admin retry flow must allow a small set of explicit strategies:
  - keep original configuration
  - use latest default term/translation assets where supported by the backend
  - specify published term/translation assets for the retry
- Backend contracts must remain backward compatible for existing job creation and retry payloads that do not include explicit configuration.
- Operator must not be able to select explicit resource versions through API payloads.
- No full Term Rule CRUD workbench, no Translation Term Set management page, no real file deletion, and no main pdf-mineru / translation / Word generation reruns are part of this task.

## Acceptance Criteria

- [x] Operator upload displays an effective default configuration summary and submits without explicit version-selection fields.
- [x] Admin upload can choose published Template, Term Rule Set, Translation Term Set, and Translation Profile versions where applicable, and the created job snapshot reflects those choices.
- [x] Operator API calls that try to select explicit resource versions return `403`.
- [x] Admin retry dialog supports keep-original plus explicit term/translation asset rebinding without changing unrelated job lifecycle behavior.
- [x] Document job detail continues to show the bound configuration snapshot after create/retry.
- [x] New API response models are documented and covered by targeted backend tests.
- [x] Frontend typecheck/build or the smallest available frontend verification passes.
- [x] Targeted backend tests for document-job configuration pass with the project conda interpreter.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Implementation has passed targeted backend tests, OpenAPI export tests, frontend build, Trellis context validation, and `git diff --check`.
