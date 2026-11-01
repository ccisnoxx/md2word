# P0a：转换失败页码与原因诊断展示

## 目标与业务结果

MinerU 产物验证失败时，用户和技术运营在任务详情页、异常中心诊断抽屉中能直接看到首个失败页、受影响页、错误代码和原因，不必下载 MinerU ZIP 对照；同时纠正异常中心对转换失败的误分类。本任务只暴露已有诊断，不改变任何转换行为。

## 背景与真源

- `MinerUValidationReport` 已含 `first_fatal`（`page_index`、`source_type`、`json_pointer`、`code`、`facts.reason`）、blocker 明细与计数。
- Worker 失败时，报告经 `build_renderer_event_summary` 白名单脱敏后写入当前代 `stage_failed.payload.mineru_validation`，并附 `retry_count`。
- 任务主记录只保留 `error_code=document_ir_failed` 与笼统 `error_message`；异常中心事件摘要丢弃 payload，前端未消费该报告。
- 异常中心 `_classify_failure` 将翻译模式下 `failed_stage=ir_converting` 一律归为 `translation_failed`；`artifact_missing` 关键词含 `missing`，使 `missing_image_asset` 等验证失败被误归为产物缺失。

## 范围与要求

1. 后端新增严格的失败诊断投影 `failure_diagnostic`：
   - 仅当任务 `status=failed`，且存在当前代（`payload.retry_count == job.retry_count`）`stage_failed` 事件携带 `mineru_validation`、其 `can_convert=false` 且有 `first_fatal` 时产生；否则为 `null`。
   - 字段：来源、失败阶段、范围（`page`/`document`）、首个失败页码（1 起始）、来源块类型、JSON 指针、原因代码、原因、受影响页码列表（1 起始、去重升序）、致命问题数、警告数、明细是否截断。
   - 首个失败无页码时范围为 `document`、页码为 `null`，不得伪造第 1 页。
2. `GET /api/v1/document-jobs/{job_id}` 返回 `failure_diagnostic`；列表等其他使用 `DocumentJobResponse` 的接口保持 `null`，不新增逐行事件查询。
3. `GET /api/v1/document-job-incidents/{job_id}/diagnostics` 顶层返回同一 `failure_diagnostic`。
4. 异常分类：失败任务的明确错误码优先于关键词启发式——`mineru_failed`/`document_ir_failed`/`render_failed` 归 `conversion_failed`，`translation_failed`/`translation_fan_in_mismatch` 归 `translation_failed`；其余保持既有规则。
5. 前端详情页失败摘要与异常中心诊断抽屉展示上述诊断；明细截断时明确提示受影响页列表可能不完整。

## 非目标

- 不改变 MinerU 校验、图片处理、IR 转换、渲染与质量门禁行为，不放宽任何安全校验。
- 不新增 `conversion-diagnostics/v1` 文件、总页数/通过页数统计（扁平 content_list 报告不记录可靠页数，不推测）。
- 不改变 `error_code`、`failed_stage`、重试与筛选合同；不新增数据库字段、迁移或回填。
- 不投影 `DocumentIntegrityError`、`TablePlaceholderError` 等非 MinerU 验证失败的定位（它们没有页级报告时为 `null`）。

## 验收条件

- AC1：页级 MinerU 验证失败的任务，详情接口与诊断接口返回首个失败页码（`page_index+1`）、原因代码、原因、受影响页码。
- AC2：文档级失败（如 ZIP 限额、路径非法）返回 `scope=document`、`page_number=null`，前端显示“无法定位到单页”。
- AC3：旧代事件、非 `stage_failed` 事件、无 `retry_count` 的旧事件、可转换报告、非失败任务均不产生诊断。
- AC4：诊断只含白名单字段与类型，不含正文、服务器路径、object key 或未知字段。
- AC5：翻译模式任务以 `document_ir_failed` 失败时归 `conversion_failed`；错误消息含 `missing_image_asset` 的转换失败不再归 `artifact_missing`；既有异常中心测试保持通过。
- AC6：前端详情页与诊断抽屉展示页码/原因/受影响页，截断提示可见；前端单测与构建通过。
- AC7：OpenAPI 快照由现有生成器更新并通过一致性检查。

## 不变量

- 诊断数据只来源于已写入事件的脱敏报告，读取时再次按类型与白名单收窄。
- 内部 `page_index` 保持 0 起始，仅 API 展示字段为 1 起始。
- GET 不写存储。
