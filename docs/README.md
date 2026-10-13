# md2word 产品与工程文档

本页导航产品目标与工程文档。职责和冲突处理见[文档清单与权威关系](../DOCUMENTATION-MANIFEST.md)，运行说明见[根 README](../README.md)。目标设计不等于当前已实现能力；当前 API 事实和既有运维资料保留在下方入口。

## 产品

- [完整 PRD](product/prd.md)
- [范围与冻结决策](product/scope-and-decisions.md)

## 架构

- [业务架构](architecture/business-architecture.md)
- [系统架构](architecture/system-architecture.md)
- [技术栈](architecture/technology-stack.md)
- [领域模型](architecture/domain-model.md)
- [工作流与状态机](architecture/workflows-and-state-machines.md)

## 数据合同

- [MinerU 产物合同](contracts/mineru-artifact-contract.md)
- [DocumentIR 合同](contracts/document-ir-contract.md)

## 详细设计

- [表格处理](design/table-processing-design.md)
- [翻译流水线](design/translation-design.md)
- [DOCX 与模板](design/docx-rendering-template-design.md)
- [质量、审核与发布](design/quality-review-release-design.md)

## 工程治理

- [测试与验收](engineering/testing-acceptance-strategy.md)
- [安全、可观测与运维](engineering/security-observability-operations.md)

## 实施

- [当前差距](implementation/current-gap-analysis.md)
- [总实施计划](implementation/implementation-plan.md)
- [Codex 任务清单](implementation/codex-task-backlog.md)
- [任务执行状态 Manifest](implementation/codex-task-manifest.yaml)
- [Codex/Trellis 执行指南](implementation/codex-execution-guide.md)
- [逐任务提示词索引](implementation/codex-prompts/README.md)
- [提示词合并版](implementation/codex-task-prompts-all-in-one.md)
- [父任务初始化指引](implementation/codex-prompts/00-parent-task-bootstrap.md)
- [迁移与上线](implementation/rollout-and-migration.md)

PRD 与冻结决策定义范围，总实施计划定义阶段，任务清单定义任务及依赖，Manifest 是执行状态与实际 Trellis 路径的唯一记录入口。实现完成只推进到 `review`，人工验收后才可标记 `done` 或 `skipped_existing`。

## 决策

- [架构决策记录](decisions/architecture-decisions.md)

## 既有实现与运行事实

- [API 清单](api/manifest.yaml)与[OpenAPI 快照](api/openapi.json)
- [后端开发文档索引](dev/backend-dev-docs-index.md)
- [P0 联调与测试入口](testing/pdf-to-word-p0-integration-guide.md)
- [后端运行手册](runbooks/backend.md)与[内部门户运行手册](runbooks/internal-portal.md)
- [线上优先验证流程](deploy/online-first-validation-workflow.md)

上述 `api/`、`dev/`、`testing/`、`runbooks/`、`deploy/` 资料继续保留；目标与当前行为的差异由[差距调查](implementation/current-gap-analysis.md)和对应任务核实。

## Trellis 父任务模板

- [父任务 PRD](../trellis-bootstrap/prd.md)
- [父任务设计](../trellis-bootstrap/design.md)
- [父任务实施模板](../trellis-bootstrap/implement.md)
- [子任务映射建议](../trellis-bootstrap/task-map.md)

模板用于建立父任务，不代表任务已经创建或验收。映射建议不替代正式任务清单中的 ID、slug 和依赖。
