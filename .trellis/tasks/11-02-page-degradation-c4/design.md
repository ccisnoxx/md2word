# 技术设计（按推荐决策，确认后细化）

## 1. 降级摘要（`integrity.build_source_integrity`）

- 新增输出 `degraded_pages: [{"page_number": n, "trigger": "validation"|"render", "reason_codes": [...]}]`，由 `metadata.degraded_pages` 派生；原因码只保留受控集合（`DEFERRABLE_ISSUE_CODES` ∪ `{"render_failed"}`），其余丢弃；条数受页数上限约束。
- `renderer/evidence.py` 若对 `source_integrity` 键有白名单校验，同步登记（事件摘要只保留数值，不透传列表）。

## 2. 基础质量（`base_quality`）

- `BaseQualityContribution` 新增 `degraded_pages: list[DegradedPageSummary]`（默认空；`DegradedPageSummary` 为 `extra="forbid"` 的严格模型：`page_number ≥ 1`、`trigger` 枚举、`reason_codes` 受控枚举列表）。
- `derive_base_quality` 从 receipt metadata `source_integrity.degraded_pages` 读取；结构不合法时 `complete=False`，不猜测。
- `project_base_quality` 已整体公开模型字段，无需改动；旧贡献无此字段按默认空读取（字段默认值是模型合同，不是兼容猜测）。

## 3. 异常中心（`incidents.py` + schema）

- `DocumentJobIncidentFailureType` 增加 `page_degraded`。
- `_build_item`：`current_base(job)` 有 `degraded_pages` 且任务成功 → `is_incident=True`；`_classify_failure` 在失败类判定之后返回 `page_degraded`；`retryable=False`；`suggested_action` 为“核对降级页（第 N 页），确认整页图像可接受或修复源文件后新建任务”；`evidence_summary` 追加“降级页：第 N 页（原因）”。
- 优先级取既有阻断类之后、普通 unknown 之前（按现有 `_priority` 规则插入）。

## 4. 翻译（`document_ir_translator.extract_translation_items` 与执行层）

- 跳过 `block.metadata.get("synthetic")` 的块（三个 `_append_*` 的共同入口处判断一次）。
- 执行层组装 `translation_metadata` 时加入 `skipped_degraded_page_numbers`（源 IR `metadata.degraded_pages` 的页码，升序）。
- 复核内容的单元比较基于同一提取函数，源/译文同时跳过，保持一致。

## 5. 前端

- `api/types.ts`：`DocumentJobIncidentFailureType` 加 `page_degraded`；基础质量类型加 `degraded_pages`。
- 新增 `utils/degradedPages.ts`（`degradedPageLines(summary)`）及单测；`JobDetailPage.vue` 在质量区展示；`IncidentTriagePage.vue` / `utils/incidents.ts` 增加类型文案与 tag 颜色。

## 6. 测试

- 后端：`base_quality` 读写降级摘要与非法结构；异常中心收录、筛选、不可重试；翻译提取跳过合成块与 metadata 记录；C1/C3 端到端断言补充详情中的 `degraded_pages`。
- OpenAPI：重新导出快照并通过 `tests.test_openapi_export`。
- 前端：`degradedPages.test.ts`、`incidents.test.ts` 补充；`vue-tsc`/构建按项目脚本。
