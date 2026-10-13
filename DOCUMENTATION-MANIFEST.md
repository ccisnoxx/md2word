# 文档清单与权威性

| 路径 | 用途 | 权威性 |
|---|---|---|
| [docs/product/prd.md](docs/product/prd.md) | 产品需求和验收边界 | 产品范围真源 |
| [docs/product/scope-and-decisions.md](docs/product/scope-and-decisions.md) | 冻结决策、非目标和变更规则 | 产品决策真源 |
| [docs/architecture/business-architecture.md](docs/architecture/business-architecture.md) | 业务能力、角色、对象、流程 | 业务架构真源 |
| [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) | 模块、运行拓扑和依赖方向 | 目标系统架构真源 |
| [docs/architecture/technology-stack.md](docs/architecture/technology-stack.md) | 实际依赖和技术约束 | 技术栈说明 |
| [docs/architecture/domain-model.md](docs/architecture/domain-model.md) | 领域对象、状态和数据所有权 | 目标领域模型真源 |
| [docs/architecture/workflows-and-state-machines.md](docs/architecture/workflows-and-state-machines.md) | 工作流和状态迁移 | 状态机真源 |
| [docs/contracts/mineru-artifact-contract.md](docs/contracts/mineru-artifact-contract.md) | MinerU 结果包输入合同 | 外部解析输入合同 |
| [docs/contracts/document-ir-contract.md](docs/contracts/document-ir-contract.md) | DocumentIR 当前与目标合同 | 内部文档合同 |
| [docs/design/table-processing-design.md](docs/design/table-processing-design.md) | 表格规范化、QA 和 Word 渲染 | 表格设计真源 |
| [docs/design/translation-design.md](docs/design/translation-design.md) | 翻译单元、Prompt、Token 和校验 | 翻译设计真源 |
| [docs/design/docx-rendering-template-design.md](docs/design/docx-rendering-template-design.md) | Word 原生渲染和模板 | DOCX 设计真源 |
| [docs/design/quality-review-release-design.md](docs/design/quality-review-release-design.md) | 自动 QA、人工复核、批准和发布 | 质量交付设计真源 |
| [docs/engineering/testing-acceptance-strategy.md](docs/engineering/testing-acceptance-strategy.md) | 测试层级、样本和门禁 | 验收策略真源 |
| [docs/engineering/security-observability-operations.md](docs/engineering/security-observability-operations.md) | 安全、隐私、指标和运维 | 非功能要求真源 |
| [docs/implementation/current-gap-analysis.md](docs/implementation/current-gap-analysis.md) | 现状能力与目标差距 | 规划输入 |
| [docs/implementation/implementation-plan.md](docs/implementation/implementation-plan.md) | 阶段、依赖、出口和回滚 | 总实施计划真源 |
| [docs/implementation/codex-task-backlog.md](docs/implementation/codex-task-backlog.md) | 可执行任务清单 | 任务拆分真源 |
| [docs/implementation/codex-execution-guide.md](docs/implementation/codex-execution-guide.md) | Codex/Trellis 执行规则 | AI 开发入口 |
| [docs/implementation/rollout-and-migration.md](docs/implementation/rollout-and-migration.md) | API、数据和发布兼容方案 | 上线迁移真源 |
| [docs/decisions/architecture-decisions.md](docs/decisions/architecture-decisions.md) | 关键架构决策记录 | 决策索引 |

## 导航与执行资料

| 路径 | 用途 | 权威性 |
|---|---|---|
| [README.md](README.md) | 项目入口与既有运行说明 | 根导航 |
| [docs/README.md](docs/README.md) | 文档分层导航 | 文档入口 |
| [docs/implementation/codex-task-manifest.yaml](docs/implementation/codex-task-manifest.yaml) | 任务执行状态、依赖引用与实际 Trellis 路径 | 执行状态真源 |
| [docs/implementation/codex-prompts/README.md](docs/implementation/codex-prompts/README.md) | 45 个任务的独立提示词索引 | 执行辅助，不替代任务定义 |
| [docs/implementation/codex-task-prompts-all-in-one.md](docs/implementation/codex-task-prompts-all-in-one.md) | 提示词合并阅读版 | 便捷入口，不另建状态 |
| [docs/implementation/codex-prompts/00-parent-task-bootstrap.md](docs/implementation/codex-prompts/00-parent-task-bootstrap.md) | 父任务初始化说明 | 建立记录的指引 |
| [trellis-bootstrap/prd.md](trellis-bootstrap/prd.md) | 父任务需求模板 | 模板，不代表已创建或验收 |
| [trellis-bootstrap/design.md](trellis-bootstrap/design.md) | 父任务设计模板 | 模板 |
| [trellis-bootstrap/implement.md](trellis-bootstrap/implement.md) | 父任务实施模板 | 模板 |
| [trellis-bootstrap/task-map.md](trellis-bootstrap/task-map.md) | 子任务映射建议 | 建议，不覆盖 backlog |

文档包包含七类目标文档、执行清单与提示词、父任务模板。既有 `docs/api/`、`docs/dev/`、`docs/testing/`、`docs/runbooks/`、`docs/deploy/` 继续作为当前合同与历史事实资料保留，不因导入目标文档而覆盖或删除。

## 权威性冲突处理

1. 产品范围冲突时，以 [产品 PRD](docs/product/prd.md) 和[冻结决策](docs/product/scope-and-decisions.md) 为准。
2. 代码当前行为与目标设计冲突时，[当前差距调查](docs/implementation/current-gap-analysis.md) 应记录差距；不得默认为代码现状就是目标行为。
3. API 实际字段仍以 [OpenAPI 快照](docs/api/openapi.json) 和运行时 OpenAPI 为准；实施任务修改 API 时必须同步快照和本套合同文档。
4. 现有 Trellis Specs 对代码约束具有执行优先级；本套文档定义产品与架构目标，不取代 `.trellis/spec/`。
5. 已发布任务、模板、术语和文档产物不得因新文档自动迁移；迁移必须遵循 [迁移与上线方案](docs/implementation/rollout-and-migration.md)。
6. [已接受 ADR](docs/decisions/architecture-decisions.md) 记录架构决策；若与 PRD 或冻结决策存在无法消解的冲突，停止对应任务并明确记录，不自行放宽边界。
7. [总实施计划](docs/implementation/implementation-plan.md) 定义阶段与出口，[backlog](docs/implementation/codex-task-backlog.md) 定义任务与依赖，[manifest](docs/implementation/codex-task-manifest.yaml) 记录执行状态与实际任务路径。提示词、bootstrap 和历史 task-map 不覆盖这三者。
8. DOC-001 文档合入不证明目标功能已经实现或测试通过；文档标注的基线保留其原始含义，实际能力由对应任务核验。实现后标记 `review`，只有人工验收才可标记 `done` 或 `skipped_existing`；此前 Trellis 子任务保持 `in_progress`，不 archive。
