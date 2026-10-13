# CON-101 Commit plan（未执行）

建议单个逻辑提交：`fix(document-jobs): close product modes and direct AI boundaries`。

仅包含下列已核对的 29 个路径；`.gitignore` 为已有用户改动，排除。没有执行 git add/commit/push，也不归档。实际分支 md2word/CON-101，manifest review、Trellis in_progress，等待人工验收与提交授权。

- `.trellis/spec/backend/document-job-mode-contract.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/check.jsonl`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/commit-plan.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/design.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/implement.jsonl`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/implement.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/planning-validation.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/prd.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/research/current-behavior.md`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/task.json`
- `.trellis/tasks/10-12-con-101-product-mode-ui-copy/validation.md`
- `.trellis/tasks/10-12-datasheet-docx-delivery-quality/task.json`
- `app/domains/document_jobs/schemas.py`
- `app/domains/document_jobs/service.py`
- `app/domains/translation/modes.py`
- `docs/api/document-jobs.md`
- `docs/api/openapi.json`
- `docs/implementation/codex-task-manifest.yaml`
- `frontend/src/api/types.ts`
- `frontend/src/components/PdfUploadPanel.vue`
- `frontend/src/pages/JobDetailPage.vue`
- `frontend/src/utils/documentJobConfig.test.ts`
- `frontend/src/utils/documentJobConfig.ts`
- `frontend/src/utils/format.test.ts`
- `frontend/src/utils/format.ts`
- `frontend/tests/smoke/core-flow.spec.ts`
- `tests/test_document_job_modes.py`

验证与残余风险见 [validation.md](validation.md)。全量 smoke 中原有页面样式 mock 缺口与审计 config 漂移如实记录，未作为通过；后续任务只列出，不实现。

## 2026-10-12 提交授权与顺序

用户当前消息已确认上述 29 路径的 commit plan。先提交实现、Spec 与人工验收记录；再用 `task.py archive --no-commit` 归档当前子任务，显式提交归档移动及路径更新；最后用 `add_session.py --no-commit` 记录工作提交并显式提交 journal。两个脚本默认可能自动生成 bookkeeping commit，本轮关闭自动提交以核对准确文件列表。`.gitignore` 保持排除，不 push；实际提交哈希与归档结果在后续收尾记录中补充。

## 实际工作提交与归档

工作提交：`e2f7243dca64ed2996b794b2e6e56e5608df0f93`，已按上述 29 个路径执行。任务归档到 `.trellis/tasks/archive/2026-10/10-12-con-101-product-mode-ui-copy`，状态 completed；原路径清单记录工作提交时的位置。归档提交只包含任务目录移动、归档后的本任务记录/context 和 manifest 路径更新；随后 journal 提交只包含开发者 777 的 session/index。不 push。
