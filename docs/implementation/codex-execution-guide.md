---
doc_type: ai-development-guide
status: executable
last_reviewed: 2026-10-03
---

# Codex + Trellis 执行指南

## 1. 目的

本指南让 Codex 按现有 `AGENTS.md` 和 `.trellis/workflow.md` 工作，不把完整计划一次性大改到代码中。

## 2. 第一次使用

在仓库中先读取：

```text
AGENTS.md
.trellis/workflow.md
相关 .trellis/spec/**/index.md
本套 docs/product/prd.md
docs/implementation/current-gap-analysis.md
docs/implementation/implementation-plan.md
docs/implementation/codex-task-backlog.md
```

初始化开发者身份（若尚未初始化）：

```bash
python3 ./.trellis/scripts/init_developer.py <developer-name>
```

## 3. 创建父任务

建议父任务只管理范围、任务树和最终集成，不直接作为大规模实现任务。

```bash
python3 ./.trellis/scripts/task.py create \
  "Datasheet 文档交付质量完善" \
  --slug datasheet-docx-delivery-quality
```

将 `trellis-bootstrap/prd.md`、`design.md`、`implement.md` 复制到父任务目录并调整实际路径。

父任务职责：

- 链接产品 PRD；
- 固化阶段和子任务依赖；
- 维护跨阶段验收；
- 汇总最终发布证据。

## 4. 创建子任务

示例：

```bash
python3 ./.trellis/scripts/task.py create \
  "CanonicalTableGrid 模型" \
  --slug canonical-table-grid \
  --parent <parent-task-dir>
```

每个复杂子任务在开始代码前完成：

```text
prd.md
设计复杂时 design.md
implement.md
implement.jsonl/check.jsonl（sub-agent mode）
```

## 5. 任务粒度

合适：

- 一套状态字段和迁移；
- 一个表格 grid builder；
- 一个 ProtectedTokenCodec；
- 一个 preview adapter；
- 一个 review API 和对应测试。

过大：

- “实现全部 PRD”；
- “优化表格、翻译和前端”；
- “重构 document_jobs”；
- “完成三栏审核和发布”。

过小：

- 只改一个中文文案且无独立价值；
- 只增加一个无行为的 wrapper；
- 为同一功能创建大量不能独立验收的任务。

## 6. 规划提示词模板

交给 Codex：

```text
请按仓库 AGENTS.md 和 Trellis 工作流进入规划，不要开始实现。
当前目标任务：<TASK-ID 和标题>。
产品范围真源：docs/product/prd.md。
技术设计：<相关 docs 路径>。
实施总计划：docs/implementation/implementation-plan.md。
任务清单：docs/implementation/codex-task-backlog.md。

先完成：
1. 调查当前实现，说明已有能力和真实差距；
2. 写/更新当前 Trellis 任务 prd.md；
3. 复杂任务写 design.md；
4. 写 implement.md，包含顺序、验证命令、回滚点；
5. 标出所有 API、DB、状态和兼容影响；
6. 等待计划评审，不要修改业务代码。
```

## 7. 实现提示词模板

在计划批准、`task.py start` 后：

```text
Active task: <task path>
按 AGENTS.md、Trellis 和当前任务的 prd/design/implement 实现。
只完成当前任务，不实现 backlog 中后续项。
开始前读取相关 .trellis/spec；优先复用现有代码。
完成后执行 implement.md 指定的 targeted tests、回归和文档更新。
不得削弱：一任务一 DOCX、direct 无 AI、HTML 表格原生化、blocked 可下载不可发布、unreviewed 可下载不可发布。
```

## 8. 调查优先

每个任务先搜索：

- 相同模型/状态/API 是否已存在；
- 当前 tests 是否已有预期；
- docs/api/openapi.json 当前合同；
- 相关 runtime/adapter；
- 历史 Trellis task 和 journal；
- 是否有 feature flag/兼容路径。

发现任务已经完成时，不强行重写；将任务转为验证、测试补齐或 `SKIPPED_EXISTING`。

## 9. Context 配置

Sub-agent mode：

```bash
python3 ./.trellis/scripts/task.py add-context <task> implement <file> "reason"
python3 ./.trellis/scripts/task.py add-context <task> check <file> "reason"
python3 ./.trellis/scripts/task.py list-context <task>
```

建议上下文：

- 当前任务 PRD/design/implement；
- 相关目标设计文档；
- 相关 `.trellis/spec`；
- 当前实现文件；
- 对应 tests；
- 样本 manifest/报告。

不要把整个仓库无差别塞入 context。

## 10. 实现顺序

单任务内部推荐：

```text
模型/合同
→ 纯算法
→ 应用 wiring
→ persistence/migration
→ API
→ 前端
→ tests
→ docs/spec
```

并非每个任务都包含全部层。

## 11. 验证要求

最小：

- 相关单元测试；
- `git diff --check`；
- 相关类型/构建。

涉及文档转换：

- component regression；
- 相关 Golden Sample；
- DOCX quality evidence。

涉及翻译：

- fake provider unit/integration；
- 对应语言方向样本；
- token/ID negative tests。

涉及 API/DB：

- repository tests；
- migration tests；
- OpenAPI snapshot；
- `check_release.py`。

涉及前端：

- `npm run build`；
- `npm run test:unit`；
- targeted Playwright smoke。

## 12. 检查和完成

Trellis sub-agent mode：

```text
trellis-implement
→ trellis-check
→ trellis-update-spec
→ commit plan/confirmation
→ commit
→ /trellis:finish-work
```

Codex inline mode遵循 `.trellis/workflow.md` 的 inline 流程。

## 13. 提交规则

- 一个子任务尽量一个逻辑提交；
- 数据迁移和代码可以同任务多提交，但说明顺序；
- 不混入未知 dirty files；
- 不自动 push；
- 提交前展示 commit plan；
- 文档和测试随功能同提交或明确关联。

## 14. 禁止事项

Codex 不得：

- 自行增加双语、批量、在线编辑或知识库；
- 新增 zh2zh Prompt；
- 把复杂表格改成默认截图；
- 为减少工作量删除质量门禁；
- 把 blocked 状态当 failed 后不给下载；
- 让前端自行推断发布资格；
- 重建一套平行任务/Renderer/Translation 系统；
- 大范围依赖升级与功能任务混做；
- 无迁移直接修改生产数据库合同。

## 15. 每次任务最终回复格式

```text
完成内容
- ...

验证
- command: result

文档/注释
- 更新了哪些文档和开发者可见文本

兼容与迁移
- ...

剩余风险
- ...
```
