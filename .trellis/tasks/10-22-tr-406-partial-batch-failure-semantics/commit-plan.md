# TR-406 Commit Plan

日期：2026-10-22。用户已明确“TR-406 验收通过”，本轮只编制提交计划；暂不 stage、commit、push、归档或记录会话。此计划不授予提交权限，也不修改已验收业务候选。

当前分支：`codex/tr-406-partial-batch-failure-semantics`；HEAD：`596a2de7ed29edb7fdb378d91c17bda09b7f1066`。建议顺序执行两笔业务提交，历史来源和本次任务记录分开处理。下列路径是 Git 提交范围字面量，均相对于仓库根目录。

## 1. 依赖基线整合提交

建议消息：`feat(document-jobs): integrate CON-102/103/104 baselines`

- 来源：CON-102 `52810b6` / `4d30682`；CON-103 `bd828da`，以 `80b82db` 的已验收复核记录为依据；CON-104 `48c9402`。TR-403 已在当前 HEAD 祖先中，保留其合同，不重复移入历史提交。
- 内容：阶段/receipt/结果身份/原子用户 retry；质量、复核、交付状态；下载分类和发布可用性；相应三 adapter、前端、测试和必要 API/Spec/运行文档。
- 包含用户追加授权的 CON-103 原有 SQLite/MySQL schema bootstrap 及迁移脚本；不增加 TR-406 新 DDL，不执行生产迁移。
- 包含 TR-403 迟到 Word 测试向 CON-102 result candidate/receipt 边界适配的测试改动，保留真实字节、checksum 和唯一物理身份断言。
- 不包含 TR-406 reducer、批次原子端口/停止闸门、partial 失败语义、execution DTO 和对应新测试。也不带入来源提交中的父任务、旧任务 archive/journal/manifest/backlog/prompt 变更。
- 共享路径在本提交只装入依赖合同和必要兼容整合；不能把当前文件整份归入依赖提交。

涉及路径（60个，包含19个需与下一提交按内容拆分的共享路径）：

```text
.trellis/spec/backend/database-guidelines.md
.trellis/spec/backend/document-job-mode-contract.md
.trellis/spec/backend/error-handling.md
.trellis/spec/backend/index.md
.trellis/spec/frontend/index.md
app/api/errors.py
app/core/errors.py
app/domains/document_jobs/delivery_state.py
app/domains/document_jobs/execution.py
app/domains/document_jobs/incidents.py
app/domains/document_jobs/models.py
app/domains/document_jobs/repository.py
app/domains/document_jobs/result_state.py
app/domains/document_jobs/router.py
app/domains/document_jobs/schemas.py
app/domains/document_jobs/service.py
app/domains/files/repository.py
app/domains/files/result_registration.py
app/domains/files/retention.py
app/domains/files/router.py
app/domains/files/service.py
app/infrastructure/persistence/file/document_jobs.py
app/infrastructure/persistence/file/files.py
app/infrastructure/persistence/file/record_lock.py
app/infrastructure/persistence/mysql/document_jobs.py
app/infrastructure/persistence/mysql/files.py
app/infrastructure/persistence/mysql/schema.py
app/infrastructure/persistence/sqlite/backend.py
app/infrastructure/persistence/sqlite/document_jobs.py
app/infrastructure/persistence/sqlite/files.py
app/infrastructure/persistence/sqlite/schema.py
docs/api/document-jobs.md
docs/api/openapi.json
docs/implementation/rollout-and-migration.md
docs/runbooks/backend.md
frontend/src/api/types.ts
frontend/src/components/JobActions.vue
frontend/src/components/JobTable.vue
frontend/src/pages/IncidentTriagePage.vue
frontend/src/pages/JobDetailPage.vue
frontend/src/pages/JobsPage.vue
frontend/src/utils/download.ts
frontend/src/utils/format.test.ts
frontend/src/utils/format.ts
frontend/src/utils/incidents.test.ts
frontend/src/utils/incidents.ts
frontend/tests/smoke/core-flow.spec.ts
frontend/tests/smoke/incident-triage.spec.ts
scripts/ops/check_release.py
scripts/ops/migrate_document_job_state.py
tests/test_database_job_repository.py
tests/test_document_job_delivery_state.py
tests/test_document_job_delivery_state_api.py
tests/test_document_job_delivery_state_migration.py
tests/test_document_job_download_availability.py
tests/test_document_job_download_availability_api.py
tests/test_document_job_execution_stages.py
tests/test_document_job_result_persistence.py
tests/test_fastapi_jobs_backend.py
tests/test_translation_integrity_execution.py
```

## 2. TR-406 实现及本任务验收记录提交

建议消息：`fix(translation): enforce terminal batch failure semantics (TR-406)`

- 内容：唯一 generation reducer；完整根集合安装/验证；同 job 原子 claim、attempt/lease/预算、split、回收和快照；终态优先与 AC12/13 故障窗口幂等收口；partial 隔离、跨代 retry 和迟到结果保护。
- 包含仓储/Artifact I/O、Provider 与树错误的正确归属、安全事件及一次真实调用审计；包含独立复审发现的最终三个修复和回归。
- 包含 translation-batches execution/叶子投影、UI 自动重试/终败/停止展示与旧响应保护、相关 OpenAPI、设计/状态机/Spec 和测试。
- 包含本任务目录内的规划、授权、整合、实现、验证、复审、原始 HEAD 失败复现与保护记录，以及本计划。当前已有36个任务文件，加本计划共37个；不把 `/tmp` 截图/trace、样本运行目录或外部快照复制进提交。
- manifest 仅提交 TR-406 区块。提交 blob 以 HEAD 版本为底移植本任务区块；其他区块原有未提交改动留在工作树，不能整文件 stage 当前 manifest。
- 后续若获提交授权，任务记录将如实标记本轮人工验收已通过；本计划不包含 task archive/add_session，不借此推进其他任务。

业务/测试/文档增量路径（30个，其中19个与上一提交共享）：

```text
.trellis/spec/backend/database-guidelines.md
.trellis/spec/backend/error-handling.md
.trellis/spec/backend/index.md
.trellis/spec/backend/translation-batch-lifecycle.md
.trellis/spec/backend/translation-integrity-validator.md
app/domains/document_jobs/execution.py
app/domains/document_jobs/repository.py
app/domains/document_jobs/router.py
app/domains/document_jobs/schemas.py
app/domains/document_jobs/service.py
app/domains/document_jobs/workflow.py
app/infrastructure/persistence/file/document_jobs.py
app/infrastructure/persistence/mysql/document_jobs.py
app/infrastructure/persistence/sqlite/document_jobs.py
docs/api/document-jobs.md
docs/api/openapi.json
docs/architecture/workflows-and-state-machines.md
docs/design/translation-design.md
frontend/src/api/documentJobs.test.ts
frontend/src/api/types.ts
frontend/src/pages/JobDetailPage.vue
frontend/src/utils/translationBatches.test.ts
frontend/src/utils/translationBatches.ts
frontend/tests/smoke/core-flow.spec.ts
tests/test_database_job_repository.py
tests/test_fastapi_jobs_backend.py
tests/test_translation_batch_failure_semantics.py
tests/test_translation_batch_repository.py
tests/test_translation_batch_workflow.py
tests/test_translation_integrity_execution.py
```

另包含：

```text
.trellis/tasks/10-22-tr-406-partial-batch-failure-semantics/**
docs/implementation/codex-task-manifest.yaml   # 仅 TR-406 区块
```

## 3. 共享路径的拆分方法

以下19个路径在两笔提交出现，表示同文件内容分层，不是重复提交同一改动：

```text
.trellis/spec/backend/database-guidelines.md
.trellis/spec/backend/error-handling.md
.trellis/spec/backend/index.md
app/domains/document_jobs/execution.py
app/domains/document_jobs/repository.py
app/domains/document_jobs/router.py
app/domains/document_jobs/schemas.py
app/domains/document_jobs/service.py
app/infrastructure/persistence/file/document_jobs.py
app/infrastructure/persistence/mysql/document_jobs.py
app/infrastructure/persistence/sqlite/document_jobs.py
docs/api/document-jobs.md
docs/api/openapi.json
frontend/src/api/types.ts
frontend/src/pages/JobDetailPage.vue
frontend/tests/smoke/core-flow.spec.ts
tests/test_database_job_repository.py
tests/test_fastapi_jobs_backend.py
tests/test_translation_integrity_execution.py
```

当前整合是手工兼容整合，两个实施快照也包含当时不同进度的 TR-406 工作，不能把任一快照直接冒充纯依赖中间树。获提交授权后，先在隔离临时树按来源提交和整合报告重建“HEAD + 已验收依赖兼容整合”，保留 TR-403；验证该中间树后作为提交1。提交2取该中间树到已验收最终候选的差量，确保合成结果与冻结源码哈希相符。OpenAPI 每个树分别生成/校验，不把最终含 TR-406 DTO 的快照提前放入提交1。

第一提交的拆分中间树尚未单独生成或验证，本轮不声称它已通过。后续对它执行阶段/receipt、质量/下载/迁移、TR-403 完整性和模式等定向兼容检查，并检查前端 build 和 OpenAPI。最终候选已有126项核心兼容、API/状态门、前端152项/build/smoke及release通过；若拆分不改变最终源码，可复用这些证据，否则按实际影响重验。2项已在原始HEAD复现的数据库callback失败继续显式保留，不弱化真实完整性校验以通过。

## 4. 排除并保留的原有改动

以下不进入任一提交，既不恢复、删除，也不借自动 bookkeeping 带入：

- 父任务 `.trellis/tasks/10-12-datasheet-docx-delivery-quality/` 已暂存的6个删除：check.jsonl、design.md、implement.jsonl、implement.md、prd.md、task.json。
- `.trellis/workspace/777/index.md` 和 `.trellis/workspace/777/journal-1.md` 的原有改动。
- `docs/implementation/codex-prompts/CON-104.md` 与 `docs/implementation/codex-task-backlog.md` 的原有改动。
- `.trellis/tasks/archive/2026-10/` 下原有14个未跟踪归档目录、328个文件，包括 CON-102/103/104 和 IR/TAB 任务；已验收源码来源不意味着这些原有 archive 文件可以混入提交。
- `docs/implementation/codex-task-manifest.yaml` 中 TR-406 之外全部原有改动。
- 测试运行目录、浏览器截图/trace、本地临时快照、缓存及其他非本任务新产物。两份已跟踪浏览器生成文件已恢复原始字节，不进入提交。

当前已按初始快照复核：332个非本任务原始dirty文件字节、原index、6个既存删除、HEAD、manifest其他区块和冻结候选hash均保持。

## 5. 后续获授权时的索引与提交检查

- 不使用 `git add -A`、`git add .`、`git commit -a` 或直接提交当前真实index；真实index含用户原有6项删除。
- 使用显式路径/内容允许清单和临时index预览每笔提交，检查 staged blob、完整 diff、OpenAPI及排除清单。每笔提交消息明确来源/任务，不 amend 或改写已有历史。
- 提交后仅同步本次提交路径的索引到新 HEAD，保留未触及条目和原暂存删除；manifest 的其他原有工作树改动继续不入索引。HEAD变化后检查的是原有暂存/未暂存改动语义与字节仍保留，不把旧index整份覆盖到新HEAD制造反向暂存。
- 两笔业务提交结束后检查合成树、最终源码哈希和排除改动，确认工作树只剩明确保留的原有改动。archive/add_session及其自动 bookkeeping 提交不在本计划，push也不在本计划。

计划编制时仅新增本计划文件，没有改业务源码、真实index或HEAD；当时未运行提交、归档、会话记录或push。

## 6. 后续执行授权

2026-10-22，用户明确同意本计划并授权两笔业务提交：先重建并验证纯依赖中间树，再提交TR-406增量；排除保留所有原有未提交改动，核对最终合成与验收候选一致。完成后报告提交哈希，不push、不归档、不记录会话。此授权不扩大上述两笔业务范围。
