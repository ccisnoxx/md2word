---
doc_type: requirement
slug: fastapi-backend-productization
pitch: 把 MinerU 结果转 DOCX 的能力产品化为可调用、可观察、可运维的 FastAPI 后端
status: current
last_reviewed: 2026-05-18
implemented_by:
  - fastapi-backend
tags: [backend, fastapi, jobs, docx]
---

# FastAPI 后端产品化

## 用户故事

- 作为前端或脚本调用方，我希望上传一个 MinerU 输出 zip 后，通过稳定的 HTTP API 获得任务状态和最终 DOCX，而不是只能手动跑本地脚本。
- 作为需要联调翻译能力的人，我希望同一条任务链路支持 `direct` 和 `en2zh`，并在翻译不可用时提前得到明确错误。
- 作为维护者，我希望通过 `health`、任务事件和本地运维动作判断任务卡在哪一步，并在必要时执行 retry、cancel 或 cleanup。
- 作为集成方，我希望读取默认模板和绑定 YAML 配置的元数据，确认当前服务到底使用哪套模板和版式约束。

## 为什么需要

当前仓库的核心转换能力已经足够强，但原始使用方式偏向本地脚本和人工操作，缺少稳定 API、状态可见性和最小运维闭环。没有后端产品化，这些能力难以被前端、自动化脚本或其他服务可靠复用。

## 怎么解决

提供一个以 `FastAPI + BackgroundTasks + file repository + conversion library` 为核心的后端表面：

- `POST /api/v1/jobs` 接收 MinerU 输出 zip
- `POST /api/v1/jobs/pdf` 接收原始 PDF，并把任务送进 MinerU 进入 `parsing`
- `GET /api/v1/jobs/*` 提供状态、事件、产物和下载入口
- `translation_mode=en2zh` 在同一条任务主链里接入翻译
- `GET /api/v1/templates*` 提供默认模板和绑定配置的只读元数据
- `health/live`、`health/ready` 和本地运维动作提供运行时观测与恢复入口

## 边界

- 当前支持两条入口：
  - 上传 MinerU 输出 zip -> 后处理 -> 生成 DOCX
  - 上传原始 PDF -> 成功提交 MinerU -> 进入 `parsing`
- 当前仍不包含 “PDF -> 在线 MinerU callback 回流 -> 自动生成 DOCX”。
- 当前只支持 file backend，不包含 MySQL / SQLite / OSS 持久化。
- 当前模板接口只读，不支持模板 CRUD。
- 当前术语和版式配置仍以仓库内版本化文件为真源，不提供后台编辑入口。
