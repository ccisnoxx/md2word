# CON-103/104 基线整合记录

状态：已完成依赖整合（仅整合已验收基线，未提交）

## 授权与来源

- CON-103 业务提交：`bd828da4e3a3025856afd758e0b0a686ff6ccb72`。
- CON-103 复核/文档提交：`80b82dbc0bf388c97b4f5b8d8e6654625cad9186`，其实施基线为 `75d0a07c481aa3f79feb8dc5f18c17065c922f1b`。
- CON-104 业务提交：`48c9402f6ed7ece4871c3ec3ca28a6a6f20920a6`。
- 用户已授权将上述已验收源码、测试、必要 Spec/API 文档及 CON-103 原有 schema bootstrap 整合到当前 TR-406 候选；不导入 task/archive/journal/manifest/backlog/prompt 历史改动，不连接生产数据库，不提交或 push。

## 当前整合边界

已保留当前候选已有的 TR-403 evidence、脱敏、唯一物理身份与 CON-102 receipt/stage/原子 retry 代码。`workflow.py` 由其他代理维护，不覆盖。现有局部 TR-406 仓储端口和 execution 接线只做手工兼容整合。

CON-103 的持久化投影形状是 `quality_status`、`review_status`、`delivery_status`、`quality_summary` 四列；SQLite 通过幂等列维护，MySQL 复用 schema maintenance，未增加 TR-406 DDL。CON-104 只复用已验收的下载/发布资格合同，不新增发布 endpoint。

## 已执行的整合

已从验收提交逐路径核对并手工应用以下路径：

- 领域合同：`app/domains/document_jobs/delivery_state.py`、`models.py`、`result_state.py`、`repository.py`、`schemas.py`、`router.py`、`service.py`、`incidents.py`。
- 持久化与 bootstrap：`app/infrastructure/persistence/file/document_jobs.py`、`sqlite/document_jobs.py`、`sqlite/schema.py`、`mysql/document_jobs.py`、`mysql/schema.py`；状态列为 `quality_status`、`review_status`、`delivery_status`、`quality_summary_json`，payload 仍是权威，未新增 TR-406 DDL。
- 迁移与测试：`scripts/ops/migrate_document_job_state.py`，`tests/test_document_job_delivery_state.py`、`test_document_job_delivery_state_api.py`、`test_document_job_delivery_state_migration.py`、`test_document_job_download_availability.py`、`test_document_job_download_availability_api.py`；fake MySQL 的状态列/投影测试接线补齐。
- API/错误/文档：`app/api/errors.py`、`app/core/errors.py`、`docs/api/document-jobs.md`、生成的 `docs/api/openapi.json`、相关 backend/frontend Spec、`docs/runbooks/backend.md` 与 `docs/implementation/rollout-and-migration.md`、`scripts/ops/check_release.py`。
- 前端：`frontend/src/api/types.ts`、`components/JobActions.vue`、`components/JobTable.vue`、`pages/JobDetailPage.vue`、`pages/JobsPage.vue`、`utils/download.ts`、`utils/format.ts` 与其 CON-104 单测。下载提示消费当次签发分类/warning，publish 只展示后端资格和禁用原因；没有自行放开发布。

手工整合时未覆盖当前 `workflow.py`、TR-403 evidence/脱敏/唯一物理身份、CON-102 receipt/stage/原子 retry、已有 execution 新逻辑或其他代理文件。前端相关基线已应用并释放前端所有权；后端状态/下载合同整合也已完成，可由主会话开始 TR-406 核心代码边界工作。

## 验证

真实通过结果：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_delivery_state tests.test_document_job_delivery_state_api tests.test_document_job_delivery_state_migration tests.test_document_job_download_availability tests.test_document_job_download_availability_api`：48 项通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_integrity_execution tests.test_document_ir_translation tests.test_generated_artifact_identity tests.test_document_job_modes tests.test_document_job_execution_stages tests.test_document_job_result_persistence`：84 项通过，保留 TR-403 迟到代/物理字节与 CON-102 receipt 断言。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability`：3 项通过。
- `cd frontend && npm run test:unit -- --run src/utils/format.test.ts`：15 项通过；`npm run build`：通过（仅保留现有第三方 PURE 注释和 chunk 大小警告）。
- `.venv/bin/python scripts/ops/export_openapi.py --check`：通过，164 paths/323 schemas，快照无差异。
- `.venv/bin/python scripts/ops/check_release.py`：通过，OpenAPI、frontend contract、smoke mock 和 targeted unittest gate 均通过。

一次较宽的 `tests.test_database_job_repository tests.test_fastapi_jobs_backend` 运行暴露了当前并行 workflow/既有测试基线的若干失败（回调 404、默认模板版本和旧动作/fixture 断言等），不属于 CON-103/104 定向合同；本整合未改 `workflow.py` 或擅自修复这些范围外失败。真实 MySQL/InnoDB 并发/DDL、部署文件系统锁、生产写者和线上发布门仍 pending，未连接生产、未运行外部写者。

## 宽回归失败证据归档（只读定位）

以下证据来自上一轮实际运行的命令：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_database_job_repository tests.test_fastapi_jobs_backend
Ran 233 tests in 27.833s
FAILED (failures=8, errors=5)
```

该命令的输出只存在于当次 `functions.exec` 终端结果，没有保存为独立日志文件，因此本记录不虚构日志路径。按输出中的实际 selector、位置和断言归档如下；这些是运行时观测，不将未知根因归类为 workflow、fixture 或初始 HEAD 已有问题：

### Errors（5）

| Selector | 运行时证据 |
| --- | --- |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_failed_mineru_callback_is_queued_then_worker_marks_failed` | `tests/test_fastapi_jobs_backend.py:9505`，`create_response.json()["job_id"]` 抛出 `KeyError: 'job_id'`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_invalid_callback_checksum_leaves_no_callback_message` | `tests/test_fastapi_jobs_backend.py:9557`，`create_response.json()["job_id"]` 抛出 `KeyError: 'job_id'`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker` | `tests/test_fastapi_jobs_backend.py:9391`，`create_response.json()["job_id"]` 抛出 `KeyError: 'job_id'`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_queues_before_worker_completes_parse` | `tests/test_fastapi_jobs_backend.py:9303`，`create_response.json()["job_id"]` 抛出 `KeyError: 'job_id'`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_ignores_queued_callback_after_cancel` | `tests/test_fastapi_jobs_backend.py:9450`，`create_response.json()["job_id"]` 抛出 `KeyError: 'job_id'`。 |

### Failures（8）

| Selector | 运行时证据 |
| --- | --- |
| `tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_pdf_callback_flow_uses_database_repository` | `tests/test_database_job_repository.py:1907`，`self.assertEqual(worker_result.status, "succeeded")` 失败；实际值为 `"failed"`。 |
| `tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_pdf_callback_flow_uses_mysql_repository` | `tests/test_database_job_repository.py:1979`，`self.assertEqual(worker_result.status, "succeeded")` 失败；实际值为 `"failed"`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_callback_rejects_non_parsing_job_status` | 断言期望 `response.status_code == 400`，实际为 `404`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_config_summary_lists_options_for_operator_and_admin` | `tests/test_fastapi_jobs_backend.py:7358`，期望包含 `"default@1"`，实际选项只有 `['default@2']`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics` | 期望 `payload["total"] == 4`，实际为 `3`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker` | 期望 QA summary 为 `{"unreviewed": 0, "approved": 1, "needs_fix": 1, "blocked": 1}`，实际为 `{"unreviewed": 3, "approved": 0, "needs_fix": 0, "blocked": 0}`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability` | 期望 actions 集合为 `{"download", "retry", "cancel", "archive", "unarchive", "clone", "delete"}`，实际集合额外包含 `"publish"`。 |
| `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets` | 期望 `word_file.metadata["template_version_id"] == "default@1"`，实际为 `"default@2"`。 |

### HEAD 来源和当前候选状态

只读执行 `git show HEAD:tests/test_fastapi_jobs_backend.py` 与 `git show HEAD:tests/test_database_job_repository.py` 确认，上述 13 个 selector 在初始 HEAD（`596a2de`）均已存在；这只证明测试入口存在，不证明干净 HEAD 能复现上述运行时结果，故根因保持未分类。`git show` 定位到的初始 HEAD 行号为：`test_document_job_config_summary_lists_options_for_operator_and_admin`=`7302`、`test_document_job_list_supports_workbench_filters_without_running_worker`=`7683`、`test_document_job_response_includes_server_action_availability`=`7929`、`test_document_job_incident_queue_filters_priority_and_diagnostics`=`7982`、五个 MinerU callback selector（队列、去重、取消后忽略、失败、checksum）依次为 `9278/9366/9425/9481/9533`、`test_document_job_worker_saves_mineru_raw_ir_and_image_assets`=`9619`、`test_callback_rejects_non_parsing_job_status`=`15803`；repository 两项依次为 `1815/1880`。

随后已验收 CON-103 基线的测试接线在当前候选中更新了列表、incident 和 action 的状态合同：列表 fixture 补充 `review_status` 并改为 `unreviewed=1, approved=0, needs_fix=1, blocked=1`；incident fixture 补充 blocked review 状态；action 集合加入 `publish`。这三项（`test_document_job_list_supports_workbench_filters_without_running_worker`、`test_document_job_incident_queue_filters_priority_and_diagnostics`、`test_document_job_response_includes_server_action_availability`）之后已单独实测通过，宽回归中的对应三条结果属于更新前观测，不能当作当前候选失败。没有对宽模块重跑，以免与并行 TR-406 修改互相污染。

其余十项（五个 callback `KeyError`、两个 database/MySQL callback worker status、non-parsing callback `404`、config `default@1/default@2`、worker `default@1/default@2`）没有在本轮报告中找到足以确认根因的干净 HEAD 复现或稳定修复证据；它们继续标记为待候选稳定后的定向诊断，不归因于纯 reducer workflow，也不声称是原 HEAD 的 preexisting failure。
