---
doc_type: test-template
slug: p1-translation-acceptance-record-template
component: pdf-to-word-translation
status: current
summary: P1 英文 PDF 英译中实验链路人工验收记录模板。
tags: [testing, translation, p1, document-ir]
last_reviewed: 2026-05-30
---

# P1 翻译质量验收记录模板

## 回归批次

| 字段 | 值 |
|---|---|
| 执行时间 |  |
| 后端版本/commit |  |
| API 地址 |  |
| Worker 模式 |  |
| MinerU 配置 |  |
| Translation provider |  |
| 术语版本 |  |
| 模板版本 |  |
| 样本总数 |  |
| 成功数 |  |
| 失败数 |  |
| 是否允许全文调试归档 |  |

## 样本记录

| 样本 ID | 文件名 | job_id | 状态 | 失败阶段/错误码 | 术语命中 | 结构不变性 | Word 可打开 | 可编辑 | AI 审计脱敏 | 调试归档过期 | 人工质量反馈 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p1-en-001 | en-datasheet-smoke.pdf |  |  |  |  |  |  |  |  |  |  |  |
| p1-en-002 | en-typical-opamp-datasheet.pdf |  |  |  |  |  |  |  |  |  |  |  |
| p1-en-003 | en-power-management-datasheet.pdf |  |  |  |  |  |  |  |  |  |  |  |

## 判定规则

- `通过`：任务成功，中文 DocumentIR 和 Word 可生成，术语基本命中，结构顺序、块类型、公式和资产引用未被翻译链路破坏。
- `条件通过`：核心链路成功，但存在少量术语、语序或排版问题，需要在备注中记录。
- `失败`：任务失败、Word 损坏、结构大面积错乱、术语明显不一致，或 AI 审计/调试归档违反脱敏与过期要求。
