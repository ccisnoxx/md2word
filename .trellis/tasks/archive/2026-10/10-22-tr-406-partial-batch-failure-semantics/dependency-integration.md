# CON-102 依赖整合记录

## 基线与范围

- 已验收基线：`52810b61adef98ca424cdd8b2b677991dc222cce`（CON-102 第一提交）与 `4d3068260c7fe5b1dab2ef46bfeb83f8963e98dc`（第二提交）。
- 当前整合基线：TR-403 checkout，HEAD `596a2de`，TR-403 祖先 `f46a3bc`。
- 未 cherry-pick、未 commit、未 stage、未 push；保留现有 dirty 与父任务删除、archive、manifest、workspace journal 修改。
- 未导入 CON-103 最新 `75d0a07..80b82` 或 CON-104 `48c9402`。当前 checkout 仍保留已有 draft QA/download 行为；`delivery_state.py`、相关 delivery/download 测试等最新合同不在本次依赖范围。

## 已应用路径

### CON-102 前端基线（已释放所有权）

已应用第一提交对应的前端类型、事件/阶段展示、格式化工具、incident 页面和 smoke 测试：

- `frontend/src/api/types.ts`
- `frontend/src/pages/IncidentTriagePage.vue`
- `frontend/src/pages/JobDetailPage.vue`
- `frontend/src/utils/format.ts`、`format.test.ts`
- `frontend/src/utils/incidents.ts`、`incidents.test.ts`
- `frontend/tests/smoke/core-flow.spec.ts`
- `frontend/tests/smoke/incident-triage.spec.ts`

这些文件已完成本次基线整合；后续 TR-406 前端实现可直接接手，我不再写 `frontend/**`。

### CON-102 后端/适配器基线

已应用第一提交的 document job/file 领域模型、repository/service、事件、结果状态、结果候选登记、record lock，以及 file/SQLite/MySQL 持久化适配器路径。新增路径包括：

- `app/domains/document_jobs/result_state.py`
- `app/domains/files/result_registration.py`
- `app/infrastructure/persistence/file/record_lock.py`

已应用第二提交的 `tests/test_document_job_execution_stages.py`、`tests/test_document_job_result_persistence.py`，并整合 `tests/test_database_job_repository.py`、`tests/test_fastapi_jobs_backend.py` 的非冲突改动。

`docs/api/document-jobs.md` 与后端 database/mode/error-handling/index Spec 已同步 CON-102 阶段、receipt、原子物化和错误归属合同。

## execution.py 冲突处理

`app/domains/document_jobs/execution.py` 同时包含 CON-102 新阶段/receipt 逻辑与 TR-403 完整性、证据、脱敏和唯一物理身份逻辑，未直接覆盖旧文件。手工整合保留了以下 TR-403 合同：

- source/translated DocumentIR 的归属、代次、checksum、角色和不可变证据校验；
- provider batch 的 integrity binding、恢复校验、审计与脱敏错误消息；
- quality checking 前的 renderer evidence 与生成物唯一身份；
- prepared result receipt 的 CAS、物化和失败时 receipt 保留；
- `_mark_failed` 的 no-prepared-result/expected receipt 约束。

补入的 CON-102 行为包括 `translating`、`translation_validating`、`quality_checking` 阶段恢复、空翻译计划、fan-in 失败归属、阶段事件耗时，以及阶段推进后事件追加失败的已提交阶段收尾。恢复入口会在已有成功叶批次时主动完成 fan-in；旧代 batch 在阶段事件失败、代数变化后不能继续 claim/provider/audit。

## 验证

通过：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_job_execution_stages \
  tests.test_document_job_result_persistence
Ran 39 tests in 22.165s
OK
```

通过：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q app tests
git diff --check
```

TR-403 targeted integrity/mode/translation run：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity_execution \
  tests.test_document_job_modes \
  tests.test_document_ir_translation
```

结果为 `Ran 38 tests in 3.017s`，全部通过。兼容测试中的 `generated_word` 延迟分支已改为 mock 当前 `register_result_candidate`，并在 `prepare_document_job_result` receipt CAS 边界记录旧代拒绝；source、translated 和 generated_word 三个延迟写入分支都保留了胜出代完成、历史 source/target/DOCX 字节与 checksum、唯一物理 object_key 以及旧代 CAS/receipt 拒绝断言。

单独重跑 `tests.test_translation_integrity_execution`：`Ran 10 tests in 0.734s`，全部通过。

## TR-406 可接手边界

后续 TR-406 代码可以以当前 CON-102 阶段、批次、fan-in、receipt 和持久化适配器为基线，继续修改 `execution.py` 的 partial-batch failure semantics。前端 CON-102 基线已应用并释放。不要假设 CON-103 的 published quality 状态或 CON-104 的 download/publish availability 已经存在；它们属于主会话协调的后续依赖整合范围。

开发者可见文字/文档本次新增或调整均使用中文；机器字段、阶段值、错误码和 API 字段保持原协议形式。
