---
doc_type: dev-guide
slug: backend-dev-docs-index
component: backend-docs
status: current
summary: 当前 md2word 后端开发文档索引，区分可直接依赖的现行文档与仅保留占位的 deferred 主题。
tags: [backend, docs, onboarding, index]
last_reviewed: 2026-06-30
---

# 后端开发文档索引

## 推荐阅读顺序

1. [backend-local-setup-and-architecture.md](./backend-local-setup-and-architecture.md)
2. [backend-architecture-baseline-and-issues.md](./backend-architecture-baseline-and-issues.md)
3. [backend-design-implementation-plan.md](./backend-design-implementation-plan.md)
4. [backend-local-minimal-env-and-commands.md](./backend-local-minimal-env-and-commands.md)
5. [runtime-observability-and-health.md](./runtime-observability-and-health.md)
6. [term-rule-set-versioning-guide.md](./term-rule-set-versioning-guide.md)
7. [translation-profile-and-segment-trace-guide.md](./translation-profile-and-segment-trace-guide.md)
8. [document-ir-v2.md](./document-ir-v2.md)
9. [local-conversion-sandbox.md](./local-conversion-sandbox.md)
10. [local-component-pdf-debugging-implementation-plan.md](./local-component-pdf-debugging-implementation-plan.md)
11. [component-pdf-regression-governance.md](./component-pdf-regression-governance.md)
12. [backend.md](../runbooks/backend.md)
13. API 细节查 [document-jobs.md](../api/document-jobs.md)、[files.md](../api/files.md)、[mineru-callbacks.md](../api/mineru-callbacks.md)、[health.md](../api/health.md)、[templates.md](../api/templates.md)、[term-rule-sets.md](../api/term-rule-sets.md) 和 [translation-profiles.md](../api/translation-profiles.md)。Legacy [jobs.md](../api/jobs.md) 只说明旧 `/api/v1/jobs` 已移除。

## 文档分工

| 文档 | 适合什么时候看 | 解决什么问题 |
|---|---|---|
| [backend-local-setup-and-architecture.md](./backend-local-setup-and-architecture.md) | 第一次接手仓库 | 当前 FastAPI 后端结构是什么、主链路怎么走 |
| [backend-architecture-baseline-and-issues.md](./backend-architecture-baseline-and-issues.md) | 要开始做架构设计、功能收口或结构优化 | 正式梳理当前后端的静态分层、动态 job 生命周期和优先级问题清单 |
| [backend-design-implementation-plan.md](./backend-design-implementation-plan.md) | 要按阶段推进后端整理和实现 | 把后端设计草案拆成可执行 checklist，标明优先级、涉及文件、预期结果和验证方式 |
| [backend-local-minimal-env-and-commands.md](./backend-local-minimal-env-and-commands.md) | 只想先跑起来 | 最小 `.env`、启动命令、健康检查怎么打 |
| [runtime-observability-and-health.md](./runtime-observability-and-health.md) | 遇到链路卡住或要排障 | 日志分层、health 字段、metrics、后台 stage 怎么观察 |
| [term-rule-set-versioning-guide.md](./term-rule-set-versioning-guide.md) | 要接入术语规则草稿、发布、设默认或回滚 | Term Rule Set versioned API 的使用步骤、核心概念和 legacy 写保护 |
| [translation-profile-and-segment-trace-guide.md](./translation-profile-and-segment-trace-guide.md) | 要接入翻译配置草稿、发布、设默认、回滚或读取翻译 trace | Translation Profile API 的使用步骤、核心概念和 `translation_trace` 产物读取方式 |
| [document-ir-v2.md](./document-ir-v2.md) | 要迁移或排查 DocumentIR 布局字段 | v2 页面、bbox、role、caption/footnote 布局合同 |
| [local-conversion-sandbox.md](./local-conversion-sandbox.md) | 要用本地 MinerU 结果包调试 Word 转换 | 正式项目作为唯一转换代码源、PyCharm 配置入口、sandbox 审计和样例资产盘点 |
| [local-component-pdf-debugging-implementation-plan.md](./local-component-pdf-debugging-implementation-plan.md) | 要按 direct/en2zh 建立本地电子元器件 PDF 调试闭环 | 本地 `mineru_result` staging、PyCharm preset、direct/en2zh 配置、验收矩阵和后续扩展路线 |
| [component-pdf-regression-governance.md](./component-pdf-regression-governance.md) | 要沉淀电子元器件品牌/分类样例并跑本地回归 | `component_pdf_samples` manifest、MinerU 样例添加、DOCX 回归和人工验收记录 |
| [backend.md](../runbooks/backend.md) | 日常联调或本地运维 | 真实上传、重试、取消、清理本地文件 |
| [document-jobs.md](../api/document-jobs.md) | 联调前端或脚本调用方 | 当前 P0 Files + Document Jobs 主任务合同、下载入口和任务动作 |
| [jobs.md](../api/jobs.md) | 排查历史引用 | legacy `/api/v1/jobs` 已从公开 v1 API 移除的说明 |
| [mineru-callbacks.md](../api/mineru-callbacks.md) | 联调 MinerU callback | callback 鉴权、checksum、allowlist 和状态推进 |
| [health.md](../api/health.md) | 看实例是否 ready | health/live、health/ready、health/metrics 的精确定义 |
| [templates.md](../api/templates.md) | 需要读取默认模板和绑定配置 | 默认模板、layout YAML、subscript YAML 的只读元数据 |
| [term-rule-sets.md](../api/term-rule-sets.md) | 联调术语规则版本管理 | Term Rule Set draft、publish、set-default 和 rollback 合同 |
| [translation-profiles.md](../api/translation-profiles.md) | 联调翻译配置版本管理 | Translation Profile draft、publish、set-default 和 rollback 合同 |

## Deferred 占位主题

下列文档目前只保留“主题占位 + 当前替代入口”，不要把它们当成现行实现规范：

- [backend-pdf-online-completion-change-summary.md](./backend-pdf-online-completion-change-summary.md)
- [document-ir-v1.md](./document-ir-v1.md)
- [template-config-package-v1.md](./template-config-package-v1.md)
- [term-assets-sql-versioning.md](./term-assets-sql-versioning.md)
- [term-assets-sql-versioning-tasks.md](./term-assets-sql-versioning-tasks.md)
- [translation-ai-audit-debug.md](./translation-ai-audit-debug.md)
- [translation-terms-v1.md](./translation-terms-v1.md)

这些主题如果后续要恢复为正式文档，必须先补齐真实代码/流程依据，再从 deferred 提升为 current。
