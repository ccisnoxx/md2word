---
doc_type: dev-guide
slug: backend-dev-docs-index
component: backend-docs
status: current
summary: 当前 md2word_file FastAPI 后端开发文档索引，说明先看哪份、遇到什么问题再看哪份。
tags: [backend, docs, onboarding, index]
last_reviewed: 2026-05-30
---

# 后端开发文档索引

## 推荐阅读顺序

1. [backend-local-setup-and-architecture.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-setup-and-architecture.md)
2. [backend-architecture-baseline-and-issues.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-architecture-baseline-and-issues.md)
3. [backend-design-implementation-plan.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-design-implementation-plan.md)（后续阶段实施入口）
4. [backend-pdf-online-completion-change-summary.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-pdf-online-completion-change-summary.md)
5. [backend-local-minimal-env-and-commands.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-minimal-env-and-commands.md)
6. [runtime-observability-and-health.md](/Users/sc/MinerU/md2word_file/docs/dev/runtime-observability-and-health.md)
7. [term-rule-set-versioning-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/term-rule-set-versioning-guide.md)
8. [translation-profile-and-segment-trace-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-profile-and-segment-trace-guide.md)
9. [translation-terms-v1.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-terms-v1.md)
10. [translation-ai-audit-debug.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-ai-audit-debug.md)
11. [template-config-package-v1.md](/Users/sc/PycharmProjects/md2word/docs/dev/template-config-package-v1.md)
12. [document-ir-v2.md](/Users/sc/PycharmProjects/md2word/docs/dev/document-ir-v2.md)
13. [backend.md](/Users/sc/PycharmProjects/md2word/docs/runbooks/backend.md)
14. API 细节查 [jobs.md](/Users/sc/MinerU/md2word_file/docs/api/jobs.md)、[mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md)、[health.md](/Users/sc/MinerU/md2word_file/docs/api/health.md)、[templates.md](/Users/sc/MinerU/md2word_file/docs/api/templates.md)、[term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md) 和 [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md)

## 文档分工

| 文档 | 适合什么时候看 | 解决什么问题 |
|---|---|---|
| [backend-local-setup-and-architecture.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-setup-and-architecture.md) | 第一次接手仓库 | 现在的 FastAPI 后端结构是什么、主链路怎么走 |
| [backend-architecture-baseline-and-issues.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-architecture-baseline-and-issues.md) | 要开始做架构设计、功能收口或结构优化 | 正式梳理当前后端的静态分层、动态 job 生命周期和优先级问题清单 |
| [backend-design-implementation-plan.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-design-implementation-plan.md) | 要按阶段推进后端整理和实现 | 把后端设计草案拆成可执行 checklist，标明优先级、涉及文件、预期结果和验证方式 |
| [backend-pdf-online-completion-change-summary.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-pdf-online-completion-change-summary.md) | 要对外说明这轮行为变化，或查看已拍板的 API 决策 | 总结 PDF 在线链路从 callback 停在 parsed 到自动完成 completed 的变化，以及 `parsed_result_package` / `parsed` 的对外定位 |
| [backend-local-minimal-env-and-commands.md](/Users/sc/MinerU/md2word_file/docs/dev/backend-local-minimal-env-and-commands.md) | 只想先跑起来 | 最小 `.env`、启动命令、健康检查怎么打 |
| [runtime-observability-and-health.md](/Users/sc/MinerU/md2word_file/docs/dev/runtime-observability-and-health.md) | 遇到链路卡住或要排障 | 日志分层、health 字段、metrics、后台 stage 怎么观察 |
| [term-rule-set-versioning-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/term-rule-set-versioning-guide.md) | 要接入术语规则草稿、发布、设默认或回滚 | Term Rule Set versioned API 的使用步骤、核心概念和 legacy 写保护 |
| [translation-profile-and-segment-trace-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-profile-and-segment-trace-guide.md) | 要接入翻译配置草稿、发布、设默认、回滚或读取翻译 trace | Translation Profile API 的使用步骤、核心概念和 `translation_trace` 产物读取方式 |
| [translation-terms-v1.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-terms-v1.md) | 要接入 P1 DocumentIR 翻译术语表 | 最小 CSV 术语格式、必填字段和 `language_pair@version` 绑定规则 |
| [translation-ai-audit-debug.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-ai-audit-debug.md) | 要排查 P1 AI 调用、审计脱敏或全文调试归档 | `ai_call_log` 元数据审计和 `ai_debug_archive` 1 天全文归档开关规则 |
| [template-config-package-v1.md](/Users/sc/PycharmProjects/md2word/docs/dev/template-config-package-v1.md) | 要调整 P0 Word 模板配置或排查渲染样式 | `template-config/v1` 文件集合、YAML 合同和 `template_id@version` 绑定格式 |
| [document-ir-v2.md](/Users/sc/PycharmProjects/md2word/docs/dev/document-ir-v2.md) | 要迁移或排查 DocumentIR 布局字段 | v2 页面、bbox、role、caption/footnote 布局合同 |
| [backend.md](/Users/sc/PycharmProjects/md2word/docs/runbooks/backend.md) | 日常联调或本地运维 | 真实上传、重试、取消、清理本地文件 |
| [jobs.md](/Users/sc/MinerU/md2word_file/docs/api/jobs.md) | 联调前端或脚本调用方 | jobs 合同、下载入口、运维动作 |
| [mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md) | 联调 MinerU callback | callback 鉴权、checksum、allowlist 和状态推进 |
| [health.md](/Users/sc/MinerU/md2word_file/docs/api/health.md) | 看实例是否 ready | health/live、health/ready、health/metrics 的精确定义 |
| [templates.md](/Users/sc/MinerU/md2word_file/docs/api/templates.md) | 需要读取默认模板和绑定配置 | 默认模板、layout YAML、subscript YAML 的只读元数据 |
| [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md) | 联调术语规则版本管理 | Term Rule Set draft、publish、set-default 和 rollback 合同 |
| [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md) | 联调翻译配置版本管理 | Translation Profile draft、publish、set-default 和 rollback 合同 |
