---
doc_type: roadmap
slug: mineru-online-ingestion
status: completed
created: 2026-05-18
last_reviewed: 2026-06-02
tags: [mineru, pdf, callback, backend, ingestion, restored]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# MinerU 在线解析历史路线

## 1. 背景

本 roadmap 恢复并校准历史 `mineru-online-ingestion`。旧版 items 中 `mineru-callback-postprocess`、`mineru-result-recovery`、`pdf-ingestion-observability` 仍为 planned；但当前代码、架构和测试已显示 PDF 在线 callback、自动后处理、主动恢复和观测能力已有落地。

因此本次恢复不照搬旧 planned 状态，而是按当前仓库事实校准为 `completed` 历史路线。

## 2. 范围与明确不做

覆盖：

- 原始 PDF 在线提交到 MinerU。
- MinerU callback ingress、安全校验、checksum、host allowlist。
- callback 命中 `done + full_zip_url` 后继续后处理。
- callback 丢失时主动查询恢复。
- health、事件和 API 文档中的在线解析观测口径。

明确不做：

- 不在当前路线继续扩新 MinerU 后台功能。
- 不替代 `document_jobs` PDF -> Word 业务主链路的质量验收。
- 不新增多实例 worker 或 callback 高可用设计。

## 3. 模块拆分

```text
mineru-online-ingestion
├── PDF submission
├── MinerU client
├── callback ingress and guards
├── callback postprocess
├── result recovery
└── observability
```

## 4. 接口契约

- legacy `/api/v1/jobs/pdf` 可提交原始 PDF 到 MinerU。
- `/api/v1/mineru-callbacks/result` 负责 callback 鉴权、payload 归一化、任务匹配和入队。
- callback 匹配优先 `data_id`，再回退 `batch_id`。
- `full_zip_url` 必须满足 https 和 host allowlist。
- 命中结果后复用后处理链路，不实现平行渲染路径。

## 5. 子 feature 清单

| slug | 状态 | 说明 |
|---|---|---|
| pdf-upload-and-mineru-submission | done | 原始 PDF 提交 MinerU，持久化 batch/data/seed |
| mineru-callback-ingress-and-guards | done | callback ingress、安全校验和 URL allowlist |
| mineru-callback-postprocess | done | callback 成功后恢复结果 zip 并继续后处理 |
| mineru-result-recovery | done | callback 丢失后的主动恢复 |
| pdf-ingestion-observability | done | health、事件、错误码和 API 文档观测口径 |

## 6. 排期状态

本路线已完成。当前 2-4 周计划只消费该能力作为 `document_jobs` 主链路的一部分，不继续扩展后台功能。

## 7. 观察项

- `document_jobs` 的业务主链路与 legacy `/jobs/pdf` 并存；后续质量硬化应明确验证哪个入口。
- Golden Sample 回归脚本当前使用 `/api/v1/files` + `/api/v1/document-jobs`，不是 legacy `/jobs/pdf`。
- callback 主链路测试存在，但不能替代真实 MinerU 和 Golden Sample 质量验收。

## 8. 变更日志

- 2026-06-02：恢复并校准历史 roadmap，按当前代码事实把旧 planned 条目收口为 done。
