---
doc_type: roadmap-draft
slug: pdf-mineru-ingestion-spike
status: archived
summary: 历史 spike 结论摘要：PDF 在线 MinerU 解析应独立于 fastapi-backend 路线推进。
last_reviewed: 2026-06-02
tags: [mineru, pdf, spike, restored]
---

# PDF MinerU Ingestion Spike

历史结论：`fastapi-backend` 的最小产品化闭环是 MinerU zip 后处理；原始 PDF 上传、MinerU 提交、callback、结果恢复和安全护栏需要单独规划。

后续实际已经形成 `mineru-online-ingestion` 与 `document_jobs` 两条相关能力线。当前交付优先级不是继续扩展在线解析后台功能，而是基于已落地链路做 PDF -> Word 质量硬化和 Golden Sample 验收。
