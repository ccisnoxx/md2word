# 新建 direct 任务按原文语言绑定 MinerU

## 目标

新建原文 PDF 转 Word（`direct`）任务时，用用户显式选择的原文语言解析 PDF，并将原文转换成可编辑 DOCX。

## 要求

- `document_language` 的 `zh`、`en`、`ru` 分别绑定 MinerU v4 的 `ch`、`en`、`east_slavic`。`auto` 沿用 `MINERU_LANGUAGE` 和既有别名映射。
- 创建时在版本化资源或兼容快照中固定语言，Worker 提交时使用绑定值。
- direct 跳过翻译。翻译模式、既有任务、克隆、重试和环境配置校验沿用既有合同。

## 验收标准

- [x] 两种快照入口覆盖四种原文语言选择。创建后变更配置，实际序列化请求仍使用绑定值。
- [x] 中文、英文 PDF 各执行一次真实 MinerU direct 转换，快照与实际请求语言分别是 `ch`、`en`，任务完成且没有翻译阶段、批次或调用。
- [x] WPS 打开两份 DOCX，每份编辑原文正文和一个表格单元格，保存副本，关闭并重开，确认四处改动保留。

验证详情见[验收记录](validation.md)。
