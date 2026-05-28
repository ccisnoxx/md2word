---
doc_type: dev-guide
slug: backend-dev-docs-index
component: backend-docs
status: current
summary: 当前 md2word_file FastAPI 后端开发文档索引，说明先看哪份、遇到什么问题再看哪份。
tags: [backend, docs, onboarding, index]
last_reviewed: 2026-05-28
---

# 后端开发文档索引

## 推荐阅读顺序

1. [backend-local-setup-and-architecture.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-setup-and-architecture.md)
2. [backend-architecture-baseline-and-issues.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-architecture-baseline-and-issues.md)
3. [backend-pdf-online-completion-change-summary.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-pdf-online-completion-change-summary.md)
4. [backend-local-minimal-env-and-commands.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-minimal-env-and-commands.md)
5. [runtime-observability-and-health.md](/Users/sc/MinerU/md2word_file/docs/dev/runtime-observability-and-health.md)
6. [runbook.md](/Users/sc/MinerU/md2word_file/docs/runbook.md)
7. API 细节查 [jobs.md](/Users/sc/MinerU/md2word_file/docs/api/jobs.md)、[mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md)、[health.md](/Users/sc/MinerU/md2word_file/docs/api/health.md) 和 [templates.md](/Users/sc/MinerU/md2word_file/docs/api/templates.md)

## 文档分工

| 文档 | 适合什么时候看 | 解决什么问题 |
|---|---|---|
| [backend-local-setup-and-architecture.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-setup-and-architecture.md) | 第一次接手仓库 | 现在的 FastAPI 后端结构是什么、主链路怎么走 |
| [backend-architecture-baseline-and-issues.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-architecture-baseline-and-issues.md) | 要开始做架构设计、功能收口或结构优化 | 正式梳理当前后端的静态分层、动态 job 生命周期和优先级问题清单 |
| [backend-pdf-online-completion-change-summary.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-pdf-online-completion-change-summary.md) | 要对外说明这轮行为变化，或查看已拍板的 API 决策 | 总结 PDF 在线链路从 callback 停在 parsed 到自动完成 completed 的变化，以及 `parsed_result_package` / `parsed` 的对外定位 |
| [backend-local-minimal-env-and-commands.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-minimal-env-and-commands.md) | 只想先跑起来 | 最小 `.env`、启动命令、健康检查怎么打 |
| [runtime-observability-and-health.md](/Users/sc/MinerU/md2word_file/docs/dev/runtime-observability-and-health.md) | 遇到链路卡住或要排障 | 日志分层、health 字段、后台 stage 怎么观察 |
| [runbook.md](/Users/sc/MinerU/md2word_file/docs/runbook.md) | 日常联调或本地运维 | 真实上传、重试、取消、清理本地文件 |
| [jobs.md](/Users/sc/MinerU/md2word_file/docs/api/jobs.md) | 联调前端或脚本调用方 | jobs 合同、下载入口、运维动作 |
| [mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md) | 联调 MinerU callback | callback 鉴权、checksum、allowlist 和状态推进 |
| [health.md](/Users/sc/MinerU/md2word_file/docs/api/health.md) | 看实例是否 ready | health/live、health/ready 的精确定义 |
| [templates.md](/Users/sc/MinerU/md2word_file/docs/api/templates.md) | 需要读取默认模板和绑定配置 | 默认模板、layout YAML、subscript YAML 的只读元数据 |
