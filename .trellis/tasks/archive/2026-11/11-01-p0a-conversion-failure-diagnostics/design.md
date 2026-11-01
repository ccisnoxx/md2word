# P0a 技术设计

## 1. 基线与责任边界

- 基线：`origin/main` `90ebb407`。
- 报告生产与脱敏 owner 不变：`artifact_validator.py` 生成报告，`execution._worker_failure_evidence` → `build_renderer_event_summary` 在写事件前白名单脱敏，`_record_event` 为含 `mineru_validation` 的 payload 附加 `retry_count`。
- 新增读侧投影 owner：`app/domains/document_jobs/failure_diagnostic.py` 的纯函数 `project_failure_diagnostic(job, events)`。详情路由与异常中心诊断共用，前端只消费投影结果，不解析事件 payload。
- 分类 owner 仍为 `DocumentJobIncidentService._classify_failure`。

## 2. 投影规则

输入：任务记录与该任务全部事件。

1. `job.status != "failed"` → `None`。
2. 按 `created_at` 倒序找第一条 `event_type == "stage_failed"`、`payload.retry_count` 为整数且等于 `job.retry_count`、`payload.mineru_validation` 为 dict 的事件；无则 `None`。缺 `retry_count` 的历史事件不猜代数。
3. 报告 `can_convert is False` 且 `first_fatal` 为 dict，且 `first_fatal.code` 为非空字符串；否则 `None`。
4. 页码：`page_index` 为非负 int 时 `+1`；否则 `None` 且 `scope="document"`。
5. 受影响页：`blockers` 中 `stops_conversion is True` 且 `page_index` 为非负 int 的去重升序 `+1`；若 `first_fatal` 有页码也并入。
6. `reason`：`first_fatal.facts.reason` 为字符串时取值，否则 `None`。`source_type`、`json_pointer` 同样只接受字符串。
7. 计数：`fatal_count`、`warning_count` 取 int，否则 0；`details_truncated` 取 bool，否则 `False`。
8. `stage` 取事件 `stage`。

事件 payload 写入时已按 `REPORT_CODES`/`REPORT_REASONS`/受控 source type 白名单过滤；读侧只做类型收窄，不复制白名单，避免两处漂移。

## 3. API 合同

```python
class DocumentJobFailureDiagnosticResponse(BaseModel):
    source: Literal["mineru_validation"]
    stage: str
    scope: Literal["page", "document"]
    page_number: int | None
    source_type: str | None
    json_pointer: str | None
    reason_code: str
    reason: str | None
    affected_page_numbers: list[int]
    fatal_count: int
    warning_count: int
    details_truncated: bool
```

- `DocumentJobResponse.failure_diagnostic: DocumentJobFailureDiagnosticResponse | None = None`；仅 `GET /document-jobs/{id}` 在任务失败时读取事件并填充。
- `DocumentJobIncidentDiagnosticResponse.failure_diagnostic`：复用诊断接口已加载的全部事件（截取最近 8 条之前）计算。
- 新增字段均可空，旧客户端忽略即可；OpenAPI 通过 `scripts/ops/export_openapi.py` 更新。

## 4. 异常分类

在超时判断之后、关键词启发式之前：

```python
if job.status == "failed" and job.error_code in TRANSLATION_ERROR_CODES:
    return "translation_failed"
if job.status == "failed" and job.error_code in CONVERSION_ERROR_CODES:
    return "conversion_failed"
```

- `CONVERSION_ERROR_CODES = {"mineru_failed", "document_ir_failed", "render_failed"}`，`TRANSLATION_ERROR_CODES = {"translation_failed", "translation_fan_in_mismatch"}`。历史 `ir_converting + translation_failed` 仍归翻译失败。
- 其余错误码（`oss_failed`、`document_job_worker_failed`、`document_job_invalid_input` 等）沿用原规则；移除翻译分支里对 `ir_converting` 阶段的无条件匹配。

## 5. 前端

- `frontend/src/api/types.ts` 增加 `DocumentJobFailureDiagnostic` 类型与两个可空字段。
- 新增 `frontend/src/utils/failureDiagnostic.ts`：`failureDiagnosticLines(diagnostic)` 生成展示行（定位、原因、受影响页、截断提示），详情页失败摘要与异常中心抽屉“关键证据”区共用，单测覆盖页级、文档级和截断。

## 6. 兼容、风险与回滚

- 无存储、迁移、状态机或执行行为变化；回滚即回退代码。
- 详情接口在失败任务上多一次事件列表读取；列表接口不变。
- 分类变化只影响异常中心 `failure_type` 投影与筛选结果，不影响重试资格。
