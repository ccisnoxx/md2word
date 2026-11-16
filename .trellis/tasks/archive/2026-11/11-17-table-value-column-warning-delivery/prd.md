# 参数表未决数值列以警告交付

## 目标

普通文档转换遇到 MIN/TYP/MAX、LOW/HIGH 等数值跨列疑点时，继续生成可下载的内部 DOCX，并保留供人工确认的质量证据。

## 产品合同

- 新的 `table-validator/v3` 数值跨列 finding 记为 `warning`。包括 `row_ambiguous`、`source_pair_unverified`、`pdf_observation_unavailable` 在内的取证不足保留源跨度，并提供人工复核标记和原因。
- 自动取证及人工核定按可核定的规则身份识别候选。已由 Word 实物认证修正的 finding 退出活动 flags，原发现和修正证据可追溯。
- 未决 finding 需要审批人通过 `acknowledged_table_semantics_report_sha256` 显式确认当前报告。确认后可批准，质量为 `warning` 的结果满足原有发布条件即可正式发布。
- 无效人工核定请求在新代接纳前拒绝，上一代 DOCX 继续可下载。
- 系统完整性错误沿用原失败合同。范围限于表格语义与证据，不改动普通 PDF→DOCX 主流程，不增加在线编辑器或迁移历史报告。

## 验收

- 使用真实 Poppler 与正式 Worker 生成带 `row_ambiguous` 原因的 DOCX，检查 `succeeded/completed`、`quality_status=warning`、人工复核标记和内部下载字节。
- 验证取证不可用和同源不足时仍交付 DOCX 并保留警告。
- 未确认报告或提供旧摘要时批准被拒，确认当前摘要后批准及发布成功。
- 自动及人工修正后的实际 Word 单元格为独立 `gridSpan=1`，修正证据保留，原 finding 不再活动。
- 无效人工核定请求被拒，代次、当前文件标识与可下载 DOCX 字节保持一致。完整性负例维持失败。
