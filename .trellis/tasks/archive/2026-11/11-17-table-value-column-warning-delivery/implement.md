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

## PR #80 后续补验与 P7 基础质量修复

在 `main@2699eec2` 上用已核对 SHA-256 的本地真实 P7 原件和留存 MinerU ZIP 补验。首次补跑两套夹具时，嵌字体 LOW/HIGH 通过。P7 已生成 DOCX 并通过表框、单元格与 13 项未决定位断言，整体质量仍为 `pending`。原用例先断言整体质量，这次未发起 P7 下载请求。

基础质量将标题、页眉页脚页码的分栏候选及已写入 Word 的表格条件绑定计作未分类风险，产生 `base_risk_unclassified`。修复限定在含已认证数值列证据的 v3 原生表结果。使用同代完整渲染计划和 Word 实物记录，对账按计划处置的装饰块、实际写入单栏的标题及已写入同表的全部派生条件段落。首节计划可以继承模板栏数，因此按实际 Word 同节栏数确认单栏。未对账的提示仍参与基础质量分级。

### 实际执行的定向验证

从仓库根目录运行以下两个指定用例。首轮通过 Python 包装器核对夹具摘要后调用相同的两个 unittest 目标，最终复验直接使用以下命令。测试输出使用测试自建临时目录。

```sh
PYTHONDONTWRITEBYTECODE=1 \
MD2WORD_TABLE_VALUE_P7_PDF="$PWD/mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb/bb850108-9783-4a28-8523-9b115319bd47_origin.pdf" \
MD2WORD_TABLE_VALUE_P7_ZIP=/tmp/md2word-rollout5.roi2be/evidence/live-gs-008-returned.zip \
.venv/bin/python -m unittest -v \
  tests.test_online_table_value_pdf_binding.OnlineTableValuePdfBindingTests.test_retained_p7_real_package_certifies_word_after_table_edge_recovery \
  tests.test_document_job_list_query_v2_service.DocumentJobListV2PublicationTests.test_modern_table_layout_risk_remains_pending_and_cannot_publish
```

- 首轮布局风险负例通过。真实 P7 已通过内部下载与 13 项未决定位核对，整体质量仍为 `pending`，基础质量显示 `unknown_flag_count=1`。确认是首节计划栏数为 `inherit` 后，改用获认证的实际 Word 栏数。
- 最终复验退出码为 0，2 项通过，0 项跳过，耗时 2.754 秒。P7 成功完成，整体质量为 `warning`，质量接口保留 13 项 `row_ambiguous` 定位及 `manual_review_required`，内部签发与 HTTP 下载均返回 200，下载 DOCX 字节与登记主件完全一致。现有布局风险负例仍为 `pending` 且发布不可用。
- `git diff --check` 通过。

### 复用结果及未验证范围

- 嵌字体 LOW/HIGH 的通过来自修复前的补验，覆盖异摘要逐页同源及同包新代批准发布。本次复用该记录，修复后未重跑 LOW/HIGH。
- P7 此次使用留存回包、真实 Poppler、本地 Worker、测试仓储和预览替身。未对这份 P7 执行批准或正式发布，未验证真实 MySQL、生产 MinerU、在线 Worker、部署或实际预览后端，以及 Word/WPS 视觉效果。
- 本次修复只运行上述两个目标。未运行全仓回归、完整发布检查或 CI。
