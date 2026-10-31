# TR-406 质量复核

日期：2026-10-22。复核对象是当前工作区候选，不改变任务范围、manifest 或既存 dirty 文件。

## Findings（已修复）

- `app/domains/document_jobs/execution.py`：终态 fan-in 在任务 source 指针与当前代批次绑定不一致时，原先可能落为 `oss_failed`；现在按完整性错误收口为 `translation_failed`，真实源件缺失仍保留 `oss_failed`。
- `app/domains/document_jobs/execution.py`：已安装根计划在请求预算预检失败时，原先条件写后返回失败记录，可能被上层误当成已获 lease；现在以已安装计划做条件写，记录 `translation_request_budget_exceeded`，不调用 Provider、无审计正文，并将任务收口。
- `app/domains/document_jobs/execution.py`：预算预检完成失败批次条件写后，`_claim_translation_batch` 现在返回 `None`，上层只重读已收口记录以保持 execute 返回合同，绝不会把失败记录当作已获 lease 的批次继续 Provider。
- `app/domains/document_jobs/execution.py`：成功 CAS 显式透传 `TranslationBatchTreeInvalidError`，避免它先被通用 `ValueError` 存储分支包装，树失效按专码收口而不是 `oss_failed`。
- `app/domains/document_jobs/execution.py`：结果 Artifact 登记补充 SQLite 与 PyMySQL 驱动异常的已知存储包装，未知异常仍向外抛出；审计一次、任务和批次收口为 `oss_failed`，不重调 Provider。
- `app/domains/document_jobs/execution.py`：补充 SQLite 驱动异常和 PyMySQL 模块异常的存储边界识别；批次成功 CAS 或失败状态写入的数据库异常映射为 `oss_failed`，不会被 Provider 失败逻辑重试。新增中文 helper 注释，未泄露异常正文。
- `tests/test_translation_integrity_execution.py`：同步当前合同：预算规划失败阶段为 `translating`，额外未知根先报告 `translation_batch_tree_invalid`。
- `tests/test_translation_batch_failure_semantics.py`：新增旧代 TreeInvalidError 与用户换代交错、预算预检不获 lease、成功 CAS 树失效专码、结果 Artifact SQLite 驱动异常不重试回归。
- `tests/test_translation_batch_repository.py`：新增 file 正常 split 持锁写入期间 snapshot 等待并只返回完整树的回归。
- `app/domains/document_jobs/repository.py` 与 `tests/test_translation_batch_workflow.py`：将本次触及的英文说明改为中文；机器字段、Provider、batch 等协议值保持原样。

## Findings（未修复/待验）

- `tests.test_database_job_repository` 的两个 fake renderer callback 失败未改动。它们在初始 HEAD `596a2de` 的独立回归中已存在，修复会扩大到无关旧 renderer/fixture，故保留并单独报告。
- 真实 MySQL/InnoDB 与部署 FS 锁门未在本地冒充通过；需要部署环境和相应授权才能完成。

## 复核边界与所有候选改动路径

本轮核对的后端源与 adapter 为：`app/api/errors.py`、`app/core/errors.py`、`app/domains/document_jobs/{delivery_state.py,execution.py,incidents.py,models.py,repository.py,result_state.py,router.py,schemas.py,service.py,workflow.py}`、`app/domains/files/{repository.py,result_registration.py,retention.py,router.py,service.py}`、`app/infrastructure/persistence/file/{document_jobs.py,files.py,record_lock.py}`、`app/infrastructure/persistence/mysql/{document_jobs.py,files.py,schema.py}`、`app/infrastructure/persistence/sqlite/{backend.py,document_jobs.py,files.py,schema.py}`、`scripts/ops/{check_release.py,migrate_document_job_state.py}`。

本轮核对的测试为：`tests/test_database_job_repository.py`、`tests/test_fastapi_jobs_backend.py`、`tests/test_translation_integrity_execution.py`、`tests/test_document_job_delivery_state.py`、`tests/test_document_job_delivery_state_api.py`、`tests/test_document_job_delivery_state_migration.py`、`tests/test_document_job_download_availability.py`、`tests/test_document_job_download_availability_api.py`、`tests/test_document_job_execution_stages.py`、`tests/test_document_job_result_persistence.py`、`tests/test_translation_batch_failure_semantics.py`、`tests/test_translation_batch_repository.py`、`tests/test_translation_batch_workflow.py`。

本轮核对的前端为：`frontend/src/api/documentJobs.test.ts`、`frontend/src/api/types.ts`、`frontend/src/components/JobActions.vue`、`frontend/src/components/JobTable.vue`、`frontend/src/pages/{IncidentTriagePage.vue,JobDetailPage.vue,JobsPage.vue}`、`frontend/src/utils/{download.ts,format.test.ts,format.ts,incidents.test.ts,incidents.ts,translationBatches.test.ts,translationBatches.ts}`、`frontend/tests/smoke/{core-flow.spec.ts,incident-triage.spec.ts}`。

本轮核对的文档、Spec 与任务记录为：`docs/api/document-jobs.md`、`docs/api/openapi.json`、`docs/architecture/workflows-and-state-machines.md`、`docs/design/translation-design.md`、`docs/implementation/codex-prompts/CON-104.md`、`docs/implementation/codex-task-backlog.md`、`docs/implementation/codex-task-manifest.yaml`、`docs/implementation/rollout-and-migration.md`、`docs/runbooks/backend.md`、`.trellis/spec/backend/{database-guidelines.md,document-job-mode-contract.md,error-handling.md,index.md,quality-guidelines.md,translation-batch-lifecycle.md,translation-integrity-validator.md}`，以及本任务三件套、依赖整合/验证记录、`quality-validation.md` 和本文。

以下源 hash 用于本轮复审锚定：

| 文件 | SHA-256 |
|---|---|
| `app/domains/document_jobs/execution.py` | `5119d349c638b6e2c590f0154187eeff33f4e71cf18270299c7cc342208c75d2` |
| `app/domains/document_jobs/repository.py` | `769f0deac829416387b933c9aac5d8b8eeec708beef3103bfd278ba45209467f` |
| `app/domains/document_jobs/workflow.py` | `8b9cba3987c0b303a583fe66c5979ab323264b60aeabdfef9ada795b394bebce` |
| `app/infrastructure/persistence/file/document_jobs.py` | `a4c28eea96dca3c2f37d3d8c3e1a71e03f0d916c3b3e0a2bf5399d7dfea90978` |
| `app/infrastructure/persistence/sqlite/document_jobs.py` | `3928dc6babab82d5ca75effcc68249210201757dc308dfaacf10be22a082851c` |
| `app/infrastructure/persistence/mysql/document_jobs.py` | `783c29b05d44a8f0592d7586588fc7b9e6b307595e341061eb08d2ec0ddc161a` |
| `tests/test_translation_batch_failure_semantics.py` | `dbc01050224d34e6b784d217333e214257378856bcbc1b79eb688f6d8483b26c` |
| `tests/test_translation_batch_repository.py` | `f8b204c2fd8147cbded8953f5d60e28b69de0f06d281699f2c8ad41fc75bf026` |

备注：此前用户已有的 workspace journal、父任务删除、归档任务、CON-104 文档和其他未识别 dirty 文件均保留，未由本轮复核覆盖或清理。
