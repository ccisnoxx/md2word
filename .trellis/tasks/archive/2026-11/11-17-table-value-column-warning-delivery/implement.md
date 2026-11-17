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
- 上述 P7 定向用例使用留存回包、真实 Poppler、本地 Worker、测试仓储和预览替身。两项定向用例完成后，已另行补验 P7 的本地批准与正式发布 API。 [本地回放](#真实-p7-审批发布本地回放)
- 本次修复只运行上述两个目标。未运行全仓回归、完整发布检查或 CI。

## 真实 P7 审批发布本地回放

在 `main@74157997` 上复核原 PDF 和留存 MinerU ZIP 的 SHA-256，随后只启动一份 P7 本地任务。复用现有 `worker_case` 的隔离运行时与资源快照，使用真实 Poppler、留存回包和预览替身。批准与发布调用正式 HTTP 路由。未调用 unittest 入口或既有测试方法。

### 实际执行的命令

从仓库根目录运行。夹具将生成的文件与测试状态存放在自建临时目录，断言结果输出到终端。

<details>
<summary>展开完整回放命令</summary>

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from hashlib import sha256
from pathlib import Path
import subprocess

def require(condition, problem):
    if not condition:
        raise SystemExit(problem)

def describe(response):
    try:
        reason = response.json().get("error", {}).get("reason_code")
    except ValueError:
        reason = None
    return f"HTTP {response.status_code}" + (f"，{reason}" if reason else "")

def repository_state():
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"]),
        subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"]),
    )

source_path = Path("mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb/bb850108-9783-4a28-8523-9b115319bd47_origin.pdf")
package_path = Path("/tmp/md2word-rollout5.roi2be/evidence/live-gs-008-returned.zip")
source = source_path.read_bytes()
package = package_path.read_bytes()
require(sha256(source).hexdigest() == "24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3",
        "P7 原 PDF 摘要变化，停止回放。")
require(sha256(package).hexdigest() == "5de05d59fdacea166361bde14625ff8045350b0aefc894a923ff181a030fe033",
        "P7 留存 ZIP 摘要变化，停止回放。")
before = repository_state()
require(not before[1], "工作区或暂存区状态已变化，停止回放。")

try:
    from tests.test_online_table_value_pdf_binding import OnlineTableValuePdfBindingTests

    fixture = OnlineTableValuePdfBindingTests()
    with fixture.worker_case(package, source, filename="OPA228_P7.pdf") as (runtime, _, job, client, owner, admin):
        url = f"/api/v1/document-jobs/{job.id}"
        tables = client.get(f"{url}/quality/tables", headers=owner)
        require(tables.status_code == 200, f"读取当前报告失败，{describe(tables)}。")
        payload = tables.json()
        waiting = [row for item in payload["items"] for row in item["unresolved_value_columns"]]
        report_hash = payload["report"]["report_sha256"]
        require((job.status, job.stage, job.quality_status, len(waiting)) == ("succeeded", "completed", "warning", 13)
                and {row["reason_code"] for row in waiting} == {"row_ambiguous"}
                and all(row["manual_review_required"] is True for row in waiting),
                "P7 任务状态或当前 13 项未决定位与预期不符。")
        require(payload["source"]["generation"] == job.retry_count
                and payload["source"]["result_file_id"] == job.result_file_id,
                "当前表格报告与 P7 主件不匹配。")
        result = runtime.document_file_repository.get_document_file(job.result_file_id)
        word = runtime.file_upload_service.read_file_content(result)
        word_hash = "sha256:" + sha256(word).hexdigest()
        require(result.checksum_sha256 == word_hash, "登记主件的 DOCX 摘要与实际字节不一致。")
        print(f"1. 通过。P7 succeeded/completed，整体 warning，13 项 row_ambiguous 均需人工复核。当前报告 SHA-256 {report_hash}", flush=True)

        review_request = {"status": "approved", "expected_source": fixture.review_source(client, owner, url)}
        denied = client.patch(f"{url}/review", headers=owner, json=review_request)
        require(denied.status_code == 409 and denied.json()["error"]["reason_code"] == "table_semantics_confirmation_required",
                f"缺少报告确认时的结果不符合预期，{describe(denied)}。")
        print("2. 通过。未确认报告时批准返回 HTTP 409，table_semantics_confirmation_required。", flush=True)

        approved = client.patch(f"{url}/review", headers=owner,
            json={**review_request, "acknowledged_table_semantics_report_sha256": report_hash})
        require(approved.status_code == 200, f"确认当前报告后批准失败，{describe(approved)}。")
        review = approved.json()["review"]
        binding = review["binding"]
        require(review["status"] == "approved" and binding["result_file_id"] == job.result_file_id
                and binding["result_sha256"] == word_hash
                and binding["acknowledged_table_semantics_report_sha256"] == report_hash,
                "批准记录与同一 DOCX 或当前报告摘要不匹配。")
        print("3. 通过。携带当前报告摘要后批准返回 HTTP 200，状态 approved，确认摘要与主件绑定已核对。", flush=True)

        published = fixture.try_publish(client, admin, url)
        require(published.status_code == 201, f"管理员发布失败，{describe(published)}。")
        publication = published.json()["publication"]
        current = runtime.document_job_repository.get_document_job(job.id)
        require(current.quality_status == "warning" and current.delivery_status == "published"
                and current.current_publication_id == publication["publication_id"]
                and publication["job_id"] == job.id and publication["generation"] == job.retry_count
                and current.result_file_id == publication["result_file_id"] == job.result_file_id
                and publication["result_sha256"] == word_hash
                and publication["review_record_id"] == review["current_record_id"],
                "发布记录与当前批准或同一主 DOCX 未对上。")
        print(f"4. 通过。管理员发布返回 HTTP 201，状态 published，质量仍为 warning。发布记录的主 DOCX ID 与 SHA-256 和批准前一致。DOCX {word_hash}", flush=True)
finally:
    require(repository_state() == before, "回放结束后仓库状态发生变化，需核对。")
    print("仓库 HEAD、工作区和暂存区状态与回放前一致。", flush=True)
PY
```

</details>

### 实测结果

| 步骤 | 实测结果 |
| --- | --- |
| 读取当前表格报告 | HTTP 200，任务为 `succeeded/completed`、整体 `warning`。同代主件的报告返回 13 项未决定位，均为 `row_ambiguous` 且标记 `manual_review_required`。 |
| 缺少报告确认时批准 | HTTP 409，原因码为 `table_semantics_confirmation_required`。 |
| 确认当前报告后批准 | HTTP 200，状态为 `approved`。批准记录的确认摘要等于当前报告 SHA-256，主 DOCX 文件 ID 和摘要与批准前一致。 |
| 管理员发布 | HTTP 201，交付状态为 `published`，整体质量仍为 `warning`。发布记录引用本次批准，任务、代次、主 DOCX 文件 ID 和实读 SHA-256 一致。 |

- 当前报告 SHA-256 为 `65a8136f4cbe556774169749c6544315b0bb1eff5928c64e9af6242ca2a3878e`。
- 主 DOCX SHA-256 为 `dc64c2d32272e8e19d2e05a4cc8ffd1a98058f7a5bccb8ee933f25eb02e06280`。
- 仅回放一次，退出码为 0。回放前后仓库 HEAD、工作区和暂存区一致。

### 更新后的未验证范围

- 真实 P7 的当前报告确认、批准和发布 API 已通过隔离本地回放。发布后的最终件签发和下载本轮未执行。此前已核对的是内部主件下载。
- 真实 MySQL、生产 MinerU 新提交、在线 Worker、部署环境、实际预览后端以及 Word/WPS 视觉效果仍未验证。全仓回归、完整发布检查和 CI 未运行。嵌字体 LOW/HIGH 继续复用此前的通过记录。
