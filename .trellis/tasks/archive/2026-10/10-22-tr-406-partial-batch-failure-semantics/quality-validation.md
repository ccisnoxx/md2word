# TR-406 质量验证记录

日期：2026-10-22。本文记录冻结候选上的真实命令、数量和验证边界；未运行生产写者、真实 Provider、VPS 或外部数据库。

## 定向后端验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_workflow tests.test_translation_batch_repository tests.test_translation_batch_failure_semantics`：42 项通过（workflow 11、repository 11、failure semantics 20）。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_workflow tests.test_translation_batch_repository tests.test_translation_batch_failure_semantics tests.test_translation_integrity_execution tests.test_document_ir_translation tests.test_generated_artifact_identity tests.test_document_job_modes tests.test_document_job_execution_stages tests.test_document_job_result_persistence`：126 项通过。
  - integrity execution 10、document IR translation 17、artifact identity 7、job modes 11、execution stages 19、result persistence 20。
  - 覆盖 AC12 双初始化 barrier、file 正常 split 写入期间 snapshot 等待、file 中断残树、SQLite rollback、fake MySQL 锁序、AC13 终态 CAS 重放、R6 旧代 TreeInvalidError 换代交错、预算预检不获 lease、成功 CAS 树失效专码、结果 Artifact SQLite 驱动异常、普通竞争、partial 不发布和 SQLite 驱动异常不进入 Provider 重试。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_failure_semantics tests.test_translation_integrity_execution`：30 项通过，确认预算失败的 `_claim` 返回 `None` 同时保留 execute 既有失败批次返回合同。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest` 加载的 FastAPI 失败/split/retry/debug/下载/QA/direct/action 选择器：12 项通过；另行执行 QA、workbench、direct QA、incident、available actions：5 项通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_delivery_state tests.test_document_job_delivery_state_api tests.test_document_job_delivery_state_migration tests.test_document_job_download_availability tests.test_document_job_download_availability_api tests.test_document_job_result_persistence`：68 项通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_database_job_repository`：16 项中 14 项通过、2 项失败。失败是 `test_document_jobs_api_pdf_callback_flow_uses_database_repository` 与 `...uses_mysql_repository` 的旧 fake renderer 回调断言；`research/original-head-regression.md` 已在初始 HEAD `596a2de` 的独立 checkout 复现同样失败，未将其归因于 TR-406，也未修改真实 IR/渲染逻辑。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile ...`（本轮 execution、repository、workflow、三 adapter 与定向测试路径）：通过；`git diff --check`：通过。项目没有独立 ruff/mypy/pyright 配置，未伪造不存在的 lint/type-check 门。

## API、release 和前端

- `.venv/bin/python scripts/ops/export_openapi.py --check`：通过，`164` paths、`324` schemas，`changed: False`。
- `.venv/bin/python scripts/ops/check_release.py`：通过；OpenAPI、frontend contract、frontend smoke mock、聚合 targeted unittest 均为 `ok=True`，其中聚合 targeted unittest 为 36 个 target。
- `.venv/bin/python scripts/ops/export_openapi.py --check`（最终源码变更后再次执行）：通过，`164` paths、`324` schemas，`changed: False`。
- 前端既有未变输入证据复用：`npm run test:unit` 152 项通过，`npm run build`（含 `vue-tsc --noEmit`）通过，翻译批次 mock smoke 通过；完成态提示文案只做定向修正，8 项相关 unit 通过。未重新启动后端或重复无变化的浏览器截图。
- component/direct 样本证据复用：OPA228 component `1/1`、direct phase2-core `5/5`、P0 `0`；样本报告中的既有 P1 标题 flags 与 `phase3_entry_ready=false` 保留为既有 backlog，不扩大本任务。

## 未验门与边界

- 真实 MySQL/InnoDB 并发、断连恢复、部署文件系统跨进程锁、真实 Provider、S3/线上 API、生产写者启用、LibreOffice/Word 人工签字仍未验证；fake MySQL/本地 SQLite/file 证据不能替代这些门。
- 未提交、未 push、未 archive、未 add_session；未连接生产、VPS 或 Provider。
