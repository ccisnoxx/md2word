# 实施计划

前置条件：sr-1 已合入当前分支。Python：`.venv/bin/python -m unittest ...`。

## 检查清单

- [ ] 0. 生成 `research/call-graph.md`：列出 `DocumentJobService` 每个方法调用的 `self.*` 方法和属性，以及外部调用方；据此定稿模块归属，必要时修订 design §1。记录定向测试的基线结果。
- [ ] 1. `use_cases/access.py`、`use_cases/action_rules.py`、`use_cases/__init__.py`；`DocumentJobService` 内部改为调用 `access`/`action_rules`（这样后续每一步搬移都不需要再跨类调用私有方法）。检查：`test_document_job_download_availability`、`test_document_job_list_query_v2_service`。提交。
- [ ] 2. 按 design §4 的顺序，逐组迁移 `table_references` → `translation_qa` → `downloads` → `quality_review` → `publication` → `lifecycle_commands` → `submission`。每组：搬移、切换调用点、删除旧方法、运行该组的相关测试类、提交。
- [ ] 3. 迁移 `queries`，修改 `DocumentJobIncidentService` 的注入，`AppRuntime` 字段改名。检查：`test_document_job_incident_publish_light_check`、`test_document_job_list_publish_light_check`。提交。
- [ ] 4. 删除 `service.py`，迁移剩余的模块级类型并更新所有导入方。检查：完整定向测试集合 + `test_openapi_export`。提交。
- [ ] 5. 更新 `directory-structure.md`；运行 `trellis-check`。

## 审查关口

- 每次提交检查 `git diff --color-moved=zebra`：搬移的代码块显示为 moved，非 moved 的改动只能是调用点和 `self.` 前缀的调整。
- 第 4 步之后运行 `rg "document_job_service|DocumentJobService\b" app tests scripts`，结果必须为 0。

## 回滚点

每组一次提交。第 1 步是后续所有步骤的基础，回滚时要按逆序 revert。

## 定向测试集合

`tests.test_fastapi_jobs_backend tests.test_document_job_modes tests.test_document_job_delivery_state_api tests.test_document_job_download_availability tests.test_document_job_download_availability_api tests.test_document_job_list_query_v2_service tests.test_document_job_incident_publish_light_check tests.test_document_job_list_publish_light_check tests.test_translation_batch_failure_semantics tests.test_document_job_result_persistence tests.test_document_job_review_hints tests.test_openapi_export`
