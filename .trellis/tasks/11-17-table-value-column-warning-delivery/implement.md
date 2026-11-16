# 实施与验证

1. 调整表格质量定义和自动取证、人工核定、证据归属判定。
2. 在持久化内容认证中保留原 v3 策略的确定性重算，并为未决数值列增加人工复核投影。
3. 扩充现有 Worker、Word 和交付 API 回归，覆盖新报告、历史报告、无效新代和保留完整性负例。同步 TABLE-005。
4. 运行 `.venv/bin/python -m unittest` 的相关模块，优先覆盖 `tests.test_online_table_value_pdf_binding`、`tests.test_online_table_value_worker`、`tests.test_online_table_value_quality`、`tests.test_online_table_value_admin_api`、`tests.test_table_value_column_review_delivery`、`tests.test_table_value_pdf_binding_delivery`、`tests.test_document_job_list_publish_light_check`，并按实际影响检查其他直接断言。使用 `git diff --check` 复核范围。
5. 回滚以本任务差异为单位，保留历史证据与上一代文件。验收使用本地针对性回归。

## 实际执行的验证

以下命令已在仓库根目录执行。本次补录复用原有日志和结果。

### 主回归

```sh
.venv/bin/python -m unittest \
  tests.test_online_table_value_pdf_binding \
  tests.test_online_table_value_worker \
  tests.test_online_table_value_quality \
  tests.test_online_table_value_admin_api \
  tests.test_online_table_value_generation_store \
  tests.test_table_value_column_review \
  tests.test_table_value_column_review_delivery \
  tests.test_table_value_pdf_binding \
  tests.test_table_value_pdf_binding_delivery \
  tests.test_table_value_pdf_binding_integration \
  tests.test_table_value_pdf_binding_poppler \
  tests.test_parameter_table_value_column_binding \
  tests.test_document_job_list_publish_light_check
```

首次执行运行 77 项，报告 29 条失败（含子用例）和 2 项跳过。失败集中在旧 blocker 断言、夹具含独立的表格引用警告，以及未修正宽表的 `layout_wide_table` 提示使整体质量留在 `pending`。修正相关判定和断言后以同一命令复验，退出码为 0，耗时 30.862 秒，75 项通过、2 项跳过。

### 补充边界回归

```sh
.venv/bin/python -m unittest \
  tests.test_online_table_value_pdf_binding.OnlineTableValuePdfBindingTests.test_persisted_v3_blocker_report_revalidates_with_its_original_policy \
  tests.test_document_job_list_query_v2_service.DocumentJobListV2PublicationTests.test_modern_table_layout_risk_remains_pending_and_cannot_publish \
  tests.test_table_value_column_span \
  tests.test_template_package_validator
```

退出码为 0，16 项通过，耗时 1.357 秒。历史 v3 测试在补充签发及下载字节断言后单独重验，本项与主回归重叠。其余覆盖普通布局风险仍保留原质量判定、历史 v1 规则和损坏或缺部件的 DOCX 模板。

### 合同和差异检查

```sh
.venv/bin/python scripts/ops/export_openapi.py --check
python3 .trellis/scripts/task.py validate .trellis/tasks/11-17-table-value-column-warning-delivery
git diff --check
```

OpenAPI 快照一致，180 条路径、398 个 schema。Trellis 的 `implement.jsonl` 与 `check.jsonl` 分别验证 3 条和 2 条上下文。差异检查通过。

## 验收证据

实际验收通过上述 unittest 调用本地正式 Worker 和 HTTP 路由。可观测场景使用真实 Poppler，观测不可用场景在取证入口注入受控异常。MinerU 回包和发布预览使用测试夹具。

| 场景 | 观测结果 |
| --- | --- |
| 行歧义、同源不足和观测不可用 | 任务为 `succeeded/completed`，整体质量为 `warning`。未决项保留原因和原跨度，文件签发及下载返回 200。 |
| 当前报告确认 | 缺少摘要或摘要过期均返回 409。提交当前报告 SHA-256 后批准返回 200，正式发布返回 201，质量仍为 `warning`。 |
| 自动及人工核定 | 实际 Word 中目标格和释放格均为独立的 `gridSpan=1` 单元格。原 finding 仍在来源验证报告，实物修正证据保留，已修正项退出活动 flags。 |
| 无效人工核定 | 目标表头不匹配，新代请求返回 `409 table_value_column_review_invalid`。当前代次、主件 ID 和重新签发后下载的 DOCX 字节保持一致。 |
| 历史和完整性门禁 | 历史 v3 blocker 报告按保存的原策略复验且 DOCX 仍可下载。错误批次、无效未决定位、实物错列和损坏模板的既有负例仍被拒绝。 |

## 未验证范围

- 跳过嵌字体 LOW/HIGH 同包夹具和保留的真实 P7 样本。对应的本地路径环境变量为 `MD2WORD_TABLE_VALUE_LOW_HIGH_DIR`、`MD2WORD_TABLE_VALUE_P7_PDF` 和 `MD2WORD_TABLE_VALUE_P7_ZIP`。
- 本地回归使用文件与 SQLite 测试仓储。MySQL 用例核对了模拟连接的锁序。本次未连接真实 MySQL、生产 MinerU、在线 Worker 或部署环境，未验证真实预览后端及 Word/WPS 客户端的视觉效果。
- 未运行全仓回归、完整发布检查或 CI。本次仅补录验证记录，未重复执行产品测试。

## 拟提交范围

拟提交一笔 `fix: 允许参数表未决数值列以警告交付`，包含以下 26 个路径。

```text
.trellis/spec/backend/word-generation-rules.md
.trellis/tasks/11-17-table-value-column-warning-delivery/check.jsonl
.trellis/tasks/11-17-table-value-column-warning-delivery/design.md
.trellis/tasks/11-17-table-value-column-warning-delivery/implement.jsonl
.trellis/tasks/11-17-table-value-column-warning-delivery/implement.md
.trellis/tasks/11-17-table-value-column-warning-delivery/prd.md
.trellis/tasks/11-17-table-value-column-warning-delivery/task.json
app/domains/document_jobs/base_quality.py
app/domains/document_jobs/table_evidence.py
app/domains/document_jobs/views/quality_review.py
app/services/document_ir/pdf_value_column_binding.py
app/services/document_ir/pdf_value_column_review_flow.py
app/services/document_ir/table_value_column_review.py
app/services/renderer/content_contract.py
app/services/renderer/render_evidence.py
app/services/renderer/table_content_evidence.py
app/services/tables/evidence.py
app/services/tables/quality.py
docs/api/document-jobs.md
docs/api/openapi.json
tests/test_online_table_value_generation_store.py
tests/test_online_table_value_pdf_binding.py
tests/test_online_table_value_quality.py
tests/test_table_value_pdf_binding.py
tests/test_table_value_pdf_binding_delivery.py
tests/test_table_value_pdf_binding_poppler.py
```

原有暂存删除 `docs/md2word 模板与渲染完整性优化实施清单.md` 单独保留。提交获授权后，用临时 Git index 从当前 HEAD 构造候选，逐项核对上述路径和差异，再提交并仅同步原 index 中本次提交的路径。提交前后核对原暂存删除的记录。本次工作停在提交计划。
