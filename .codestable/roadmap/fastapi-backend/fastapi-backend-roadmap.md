---
doc_type: roadmap
slug: fastapi-backend
status: completed
created: 2026-05-18
last_reviewed: 2026-06-02
tags: [fastapi, backend, jobs, conversion, docx, restored]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service, conversion-flow, app-conversion-internal]
---

# FastAPI 后端产品化历史路线

## 1. 背景

本 roadmap 是对历史 `.codestable/roadmap/fastapi-backend/` 的恢复和校准。历史文档在 `b1ec44a` 前存在，当前 HEAD 被删除；但 `.codestable/architecture/ARCHITECTURE.md` 和 `backend-fastapi-service.md` 仍引用本路线，因此需要恢复为可检索的完成态规划档案。

本路线描述的是早期后端产品化：从本地转换工具演进为 `FastAPI + jobs + conversion library + artifact 下载` 的服务化后端。

## 2. 范围与明确不做

覆盖：

- `/api/v1/jobs` legacy MinerU zip 后处理入口。
- `app/conversion/` 服务化边界。
- job、event、file、stage message 的 file-backed 初始持久化。
- `direct` / `en2zh` 后处理能力。
- 模板只读、health、events、retry/cancel/cleanup 等基础后端表面。

明确不做：

- 不把当前 `document_jobs` PDF -> Word 主链路继续塞回本历史 roadmap。
- 不在本 roadmap 内新增前端、Golden Sample 或质量硬化任务。
- 不恢复旧的 `app/schemas` / `app/repositories` 目录口径；当前真实结构以 `.codestable/architecture/` 和 `.trellis/spec/backend/` 为准。

## 3. 模块拆分

```text
fastapi-backend
├── API / Jobs：legacy /api/v1/jobs 任务入口、查询、事件和下载
├── Conversion Library：app/conversion 后端转换入口
├── Repository / Stage：file-backed job/event/file/stage 持久化
├── Template / Health：模板只读与 readiness
└── Ops：retry、cancel、cleanup、日志和文档
```

## 4. 接口契约

- `POST /api/v1/jobs` 接收 MinerU 输出 zip，不接原始 PDF。
- `GET /api/v1/jobs*` 查询 legacy job 状态、事件、产物和下载。
- `GET /api/v1/health/live|ready|metrics` 暴露运行状态。
- `ConversionService.convert(request)` 是后端调用 conversion 的服务边界。
- artifact 对外只暴露逻辑路径、alias、download 入口，不暴露本地绝对路径。

## 5. 子 feature 清单

| slug | 状态 | 说明 |
|---|---|---|
| backend-minimal-direct-conversion | done | 建立 FastAPI app、file job repository、上传 MinerU zip 后台直出 DOCX 的最小闭环 |
| conversion-library-boundary | done | 把转换入口拆到 `app/conversion/`，供后端稳定调用 |
| job-artifact-contract | done | 固定 legacy job artifact 合同和下载边界 |
| translation-en2zh-api | done | 接入 legacy `translation_mode=en2zh` |
| template-config-read-api | done | 提供模板和渲染配置只读入口 |
| admin-ops-and-events | done | 补齐 retry、cancel、cleanup、events |
| runtime-observability-and-docs | done | 固定 health、日志和运行文档 |
| pdf-mineru-ingestion-spike | done | 结论是 PDF 在线解析应独立路线推进 |

最小闭环已完成：合法 MinerU zip 可通过 legacy jobs 入口生成并下载 DOCX。

## 6. 排期状态

本路线已完成。当前 2-4 周交付不再扩展 legacy `/api/v1/jobs` 后台功能，优先服务 `document_jobs` PDF -> Word 主链路质量硬化。

## 7. 观察项

- 当前真实后端已迁移到 domain-first 布局，历史文档里的 `app/api/v1/routers/jobs.py`、`app/services/jobs/*` 等早期路径只作为历史语义参考。
- `fastapi-backend-acceptance.md` 恢复为摘要版，避免 architecture 断链。
- PDF 在线链路和 `document_jobs` 后续质量工作归入 `pdf-to-word-delivery-hardening`。

## 8. 变更日志

- 2026-06-02：恢复并校准历史 roadmap，标记为 completed；作为 architecture 引用和历史规划档案保留。
