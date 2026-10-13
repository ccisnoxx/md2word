# md2word Codex 逐任务提示词（合并版）

# md2word Codex 逐任务提示词

本目录为 `docs/implementation/codex-task-backlog.md` 中全部 45 个任务提供可直接复制给 Codex 的独立提示词。

## 使用方式

每个任务文件包含：

1. 分支准备命令；
2. 规划会话提示词；
3. 计划批准后的实施会话提示词；
4. 人工验收后的收尾提示词。

由于仓库 `AGENTS.md` 和 Trellis 工作流要求复杂任务先完成 `prd.md`、`design.md`、`implement.md`，默认一个任务使用两个 Codex 会话：先规划，再实现。轻量文档任务仍可按仓库规则在同一会话内完成，但不要绕过 manifest、依赖和验收门禁。

## 状态约定

`docs/implementation/codex-task-manifest.yaml` 是机器可读的执行状态清单：

```text
todo → planning → in_progress → review → done
                              ↘ blocked
review → skipped_existing（仅现有能力已完整满足且人工接受时）
```

- 实施会话只能把任务推进到 `review`；
- 人工验收后才能改为 `done` 或 `skipped_existing`；
- Trellis 子任务在人工验收前保持 `in_progress`，不得 archive；
- 每次只允许一个冲突范围的实现任务处于 `in_progress`。

## 父任务

父任务 slug：`datasheet-docx-delivery-quality`。

若尚未创建，请先参考 [`00-parent-task-bootstrap.md`](codex-prompts/00-parent-task-bootstrap.md)。

## 任务索引

| 任务 | 标题 | 阶段 | 依赖 | 建议分支 |
|---|---|---|---|---|
| [DOC-001](codex-prompts/DOC-001.md) | 合入文档包和索引 | R0 | 无 | `md2word/DOC-001` |
| [BAS-001](codex-prompts/BAS-001.md) | 当前能力与测试基线核验 | R0 | DOC-001 | `md2word/BAS-001` |
| [CON-101](codex-prompts/CON-101.md) | 产品模式和 UI 文案收口 | R1 | BAS-001 | `md2word/CON-101` |
| [CON-102](codex-prompts/CON-102.md) | 执行阶段扩展 | R1 | BAS-001 | `md2word/CON-102` |
| [CON-103](codex-prompts/CON-103.md) | 质量/复核/交付状态模型 | R1 | CON-102 | `md2word/CON-103` |
| [CON-104](codex-prompts/CON-104.md) | 下载和发布可用性合同 | R1 | CON-103 | `md2word/CON-104` |
| [IR-201](codex-prompts/IR-201.md) | MinerUArtifactValidator | R2 | BAS-001 | `md2word/IR-201` |
| [IR-202](codex-prompts/IR-202.md) | MarginArtifactNormalizer | R2 | IR-201 | `md2word/IR-202` |
| [IR-203](codex-prompts/IR-203.md) | CrossPageParagraphMerger | R2 | IR-201 | `md2word/IR-203` |
| [IR-204](codex-prompts/IR-204.md) | CaptionReconciler 增强 | R2 | IR-201 | `md2word/IR-204` |
| [IR-205](codex-prompts/IR-205.md) | LogicalTableGroup 与 source spans | R2 | IR-201 | `md2word/IR-205` |
| [IR-206](codex-prompts/IR-206.md) | Table Reference Asset | R2 | IR-205 | `md2word/IR-206` |
| [IR-207](codex-prompts/IR-207.md) | ZK7044 最小回归样本 | R2 | IR-201 | `md2word/IR-207` |
| [TAB-301](codex-prompts/TAB-301.md) | CanonicalTableGrid 模型 | R3 | IR-205 | `md2word/TAB-301` |
| [TAB-302](codex-prompts/TAB-302.md) | HTML Normalizer/Grid Builder | R3 | TAB-301 | `md2word/TAB-302` |
| [TAB-303](codex-prompts/TAB-303.md) | Table Validator/Quality Flags | R3 | TAB-302 | `md2word/TAB-303` |
| [TAB-304](codex-prompts/TAB-304.md) | 大表保留合并关系 | R3 | TAB-302 | `md2word/TAB-304` |
| [TAB-305](codex-prompts/TAB-305.md) | 跨页逻辑表 Word 渲染 | R3 | TAB-304、IR-205 | `md2word/TAB-305` |
| [TAB-306](codex-prompts/TAB-306.md) | 空 HTML 内部占位和 blocked | R3 | TAB-303、CON-103 | `md2word/TAB-306` |
| [TAB-307](codex-prompts/TAB-307.md) | 表格 evidence 聚合 | R3 | TAB-303、TAB-304 | `md2word/TAB-307` |
| [TAB-308](codex-prompts/TAB-308.md) | 表格专项回归门禁 | R3 | TAB-304、TAB-305、TAB-306、TAB-307、IR-207 | `md2word/TAB-308` |
| [TR-401](codex-prompts/TR-401.md) | Caption/Footnote 翻译覆盖 | R4 | IR-204 | `md2word/TR-401` |
| [TR-402](codex-prompts/TR-402.md) | ProtectedTokenCodec | R4 | BAS-001 | `md2word/TR-402` |
| [TR-403](codex-prompts/TR-403.md) | TranslationIntegrityValidator | R4 | TR-402 | `md2word/TR-403` |
| [TR-404](codex-prompts/TR-404.md) | TableContextBuilder | R4 | TAB-301 | `md2word/TR-404` |
| [TR-405](codex-prompts/TR-405.md) | 术语和目标语言后验检查 | R4 | TR-403 | `md2word/TR-405` |
| [TR-406](codex-prompts/TR-406.md) | 部分批次失败语义收口 | R4 | TR-403、CON-102 | `md2word/TR-406` |
| [TR-407](codex-prompts/TR-407.md) | 四语言方向样本和门禁 | R4 | TR-401、TR-402、TR-403、TR-404、TR-405、TR-406 | `md2word/TR-407` |
| [RND-501](codex-prompts/RND-501.md) | RenderPlan 与 block evidence | R5 | IR-205、TAB-301 | `md2word/RND-501` |
| [RND-502](codex-prompts/RND-502.md) | 公式 OMML 和降级规则 | R5 | BAS-001 | `md2word/RND-502` |
| [RND-503](codex-prompts/RND-503.md) | 图片并排和 Caption | R5 | IR-204 | `md2word/RND-503` |
| [RND-504](codex-prompts/RND-504.md) | WordPreviewProvider | R5 | CON-103 | `md2word/RND-504` |
| [RND-505](codex-prompts/RND-505.md) | PDF/IR/Word 页映射 | R5 | RND-501、RND-504 | `md2word/RND-505` |
| [RND-506](codex-prompts/RND-506.md) | 页级 DOCX 质量检查 | R5 | RND-504、RND-505 | `md2word/RND-506` |
| [QA-601](codex-prompts/QA-601.md) | 统一 Review 模型 | R6 | CON-103 | `md2word/QA-601` |
| [QA-602](codex-prompts/QA-602.md) | Quality/Review API | R6 | QA-601、TAB-307、RND-506 | `md2word/QA-602` |
| [QA-603](codex-prompts/QA-603.md) | 三栏审核页面 | R6 | QA-602、RND-505 | `md2word/QA-603` |
| [QA-604](codex-prompts/QA-604.md) | 下载状态提示 | R6 | CON-104、QA-602 | `md2word/QA-604` |
| [QA-605](codex-prompts/QA-605.md) | PublicationRecord 和发布门禁 | R6 | QA-601、RND-504 | `md2word/QA-605` |
| [QA-606](codex-prompts/QA-606.md) | 发布 UI 与审计 | R6 | QA-605 | `md2word/QA-606` |
| [QA-607](codex-prompts/QA-607.md) | 审核发布 E2E | R6 | QA-603、QA-604、QA-605、QA-606 | `md2word/QA-607` |
| [REL-701](codex-prompts/REL-701.md) | Release check 和 Acceptance gate | R7 | TAB-308、TR-407、QA-607 | `md2word/REL-701` |
| [REL-702](codex-prompts/REL-702.md) | 指标、告警和容量 | R7 | REL-701 | `md2word/REL-702` |
| [REL-703](codex-prompts/REL-703.md) | 迁移和灰度启用 | R7 | REL-701 | `md2word/REL-703` |
| [REL-704](codex-prompts/REL-704.md) | Runbook、OpenAPI、最终签字 | R7 | REL-703 | `md2word/REL-704` |


---

# Trellis 父任务与状态清单初始化

## 一次性准备

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
python3 ./.trellis/scripts/init_developer.py sc
python3 ./.trellis/scripts/task.py create \
  "Datasheet 文档交付质量完善" \
  --slug datasheet-docx-delivery-quality
```

将仓库中的：

```text
trellis-bootstrap/prd.md
trellis-bootstrap/design.md
trellis-bootstrap/implement.md
trellis-bootstrap/task-map.md
```

复制到新建父任务目录，并运行：

```bash
python3 ./.trellis/scripts/task.py validate <父任务目录名>
```

父任务负责范围、依赖和最终集成，不作为日常大规模实现任务。每个 Codex 提示词会在该父任务下创建一个独立子任务。

## 状态清单

确认文件存在：

```text
docs/implementation/codex-task-manifest.yaml
```

首次合入时，全部任务应为 `todo`。不要一次性把任务批量改为 `in_progress`。

## 基线规则

- 每项依赖必须先合并到基线分支并更新为 `done` 或经人工接受的 `skipped_existing`；
- 新任务从包含全部依赖的最新基线创建分支；
- 规划会话更新为 `planning`；
- 实施会话更新为 `in_progress`，完成后更新为 `review`；
- 人工验收后才更新为 `done` 并归档 Trellis 任务；
- 不自动 push。


---

# DOC-001 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 合入文档包和索引 |
| 阶段 | R0 · 文档与基线 |
| 依赖 | 无 |
| 建议分支 | `md2word/DOC-001` |
| Trellis 子任务 slug | `doc-001-documentation-package-index` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/DOC-001
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（无）的基线分支。若分支已存在，使用 `git switch md2word/DOC-001`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **DOC-001：合入文档包和索引** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/DOC-001`
发布阶段：`R0（文档与基线）`
依赖任务：无
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`doc-001-documentation-package-index`

## 本任务目标

把产品、架构、合同、设计和实施文档安全合入仓库，并建立可导航的权威文档入口。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 DOC-001 当前为 `todo`、`planning` 或明确可继续的状态；
   - 当前任务无依赖；
   - 若发现父任务或文档基线尚未建立，将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 DOC-001 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `DOCUMENTATION-MANIFEST.md`
   - `docs/README.md`
   - `README.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 DOC-001 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `README.md`
   - `DOCUMENTATION-MANIFEST.md`
   - `docs/**`
   - `trellis-bootstrap/**`

## 规划必须覆盖的交付物

- 核对文档包文件完整性和目录结构。
- 更新根 README 的产品、架构、实施计划和任务入口。
- 确认 PRD、冻结决策、实施计划和任务清单的权威关系。
- 检查全部新增 Markdown 相对链接。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得修改业务代码、测试行为、数据库或 API。
- 不得覆盖或删除既有事实文档。

## 明确范围外

- 任何业务实现。
- 重写现有 README 的运行说明。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **DOC-001：合入文档包和索引**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/DOC-001`
发布阶段：`R0（文档与基线）`
依赖任务：无
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`doc-001-documentation-package-index`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

把产品、架构、合同、设计和实施文档安全合入仓库，并建立可导航的权威文档入口。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 DOC-001 为 `planning`；
   - 当前任务无依赖；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `DOCUMENTATION-MANIFEST.md`
   - `docs/README.md`
   - `README.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 DOC-001，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 DOC-001 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `README.md`
   - `DOCUMENTATION-MANIFEST.md`
   - `docs/**`
   - `trellis-bootstrap/**`

必须交付：
- 核对文档包文件完整性和目录结构。
- 更新根 README 的产品、架构、实施计划和任务入口。
- 确认 PRD、冻结决策、实施计划和任务清单的权威关系。
- 检查全部新增 Markdown 相对链接。

验收条件：
- 所有相对链接有效。
- 既有 docs 子目录完整保留。
- `git diff --check` 通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得修改业务代码、测试行为、数据库或 API。
- 不得覆盖或删除既有事实文档。

## 明确范围外

- 任何业务实现。
- 重写现有 README 的运行说明。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- 运行或编写只读 Markdown 相对链接检查，报告全部失效链接。
- 确认未删除 `docs/api`、`docs/dev`、`docs/testing`、`docs/runbooks`、`docs/deploy` 既有内容。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 DOC-001 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **DOC-001：合入文档包和索引** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/DOC-001`
依赖任务：无

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 DOC-001 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# BAS-001 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 当前能力与测试基线核验 |
| 阶段 | R0 · 文档与基线 |
| 依赖 | DOC-001 |
| 建议分支 | `md2word/BAS-001` |
| Trellis 子任务 slug | `bas-001-current-capability-baseline` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/BAS-001
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（DOC-001）的基线分支。若分支已存在，使用 `git switch md2word/BAS-001`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **BAS-001：当前能力与测试基线核验** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/BAS-001`
发布阶段：`R0（文档与基线）`
依赖任务：DOC-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`bas-001-current-capability-baseline`

## 本任务目标

把 gap analysis 中的“不确定”项变成可复现事实，并为后续任务建立测试、脚本和实现基线。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 BAS-001 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 DOC-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 BAS-001 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/implementation/current-gap-analysis.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 BAS-001 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/**`
   - `frontend/**`
   - `tests/**`
   - `scripts/**`
   - `docs/api/**`
   - `docs/dev/**`
   - `.trellis/tasks/**`

## 规划必须覆盖的交付物

- 产出 `docs/implementation/baseline-verification-<date>.md`。
- 核验 Word Preview、Publication、caption/footnote 翻译、跨页段落、表格 reference asset 和 DB migration 机制。
- 记录现有 release、Golden、component、translation、frontend 测试命令和结果。
- 对 backlog 提出 `SKIPPED_EXISTING`、缩小范围或依赖调整建议。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 本任务不得修改业务行为。
- 调查结论必须引用真实代码、测试或文档路径。

## 明确范围外

- 顺手修复调查中发现的问题。
- 重构测试框架。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **BAS-001：当前能力与测试基线核验**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/BAS-001`
发布阶段：`R0（文档与基线）`
依赖任务：DOC-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`bas-001-current-capability-baseline`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

把 gap analysis 中的“不确定”项变成可复现事实，并为后续任务建立测试、脚本和实现基线。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 BAS-001 为 `planning`；
   - 确认依赖 DOC-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/implementation/current-gap-analysis.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 BAS-001，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 BAS-001 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/**`
   - `frontend/**`
   - `tests/**`
   - `scripts/**`
   - `docs/api/**`
   - `docs/dev/**`
   - `.trellis/tasks/**`

必须交付：
- 产出 `docs/implementation/baseline-verification-<date>.md`。
- 核验 Word Preview、Publication、caption/footnote 翻译、跨页段落、表格 reference asset 和 DB migration 机制。
- 记录现有 release、Golden、component、translation、frontend 测试命令和结果。
- 对 backlog 提出 `SKIPPED_EXISTING`、缩小范围或依赖调整建议。

验收条件：
- 所有“不确定”项有事实结论或明确阻断。
- 基线命令可复现或有精确环境阻断。
- 没有业务代码改动。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 本任务不得修改业务行为。
- 调查结论必须引用真实代码、测试或文档路径。

## 明确范围外

- 顺手修复调查中发现的问题。
- 重构测试框架。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python scripts/ops/check_release.py`（若环境依赖阻断，记录精确命令和阻断）。
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 BAS-001 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **BAS-001：当前能力与测试基线核验** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/BAS-001`
依赖任务：DOC-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 BAS-001 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# CON-101 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 产品模式和 UI 文案收口 |
| 阶段 | R1 · 合同和状态 |
| 依赖 | BAS-001 |
| 建议分支 | `md2word/CON-101` |
| Trellis 子任务 slug | `con-101-product-mode-ui-copy` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/CON-101
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（BAS-001）的基线分支。若分支已存在，使用 `git switch md2word/CON-101`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **CON-101：产品模式和 UI 文案收口** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-101`
发布阶段：`R1（合同和状态）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-101-product-mode-ui-copy`

## 本任务目标

产品层只展示“原文 PDF 转可编辑 Word”和四种翻译方向，并确保 direct 模式不暴露 AI 配置。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-101 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 CON-101 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 CON-101 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/translation/modes.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/utils/format.ts`
   - `frontend/src/components/PdfUploadPanel.vue`
   - `frontend/src/**/document*`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 保留历史 `zh2zh`/`zh_to_zh` 到 direct 的服务端兼容。
- 新 UI、文档和新 API 示例不再出现“中译中”。
- direct 模式隐藏翻译术语、翻译配置、Prompt、模型和 AI 调试项。
- 更新相关类型、文案、测试和 API 文档。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 历史兼容 alias 不能被删除。
- 不得新增中文转中文 Prompt。
- direct 创建和执行不得触发翻译服务。

## 明确范围外

- 改变任务主输出数量。
- 增加新语言方向。
- 重做上传页面视觉体系。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **CON-101：产品模式和 UI 文案收口**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-101`
发布阶段：`R1（合同和状态）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-101-product-mode-ui-copy`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

产品层只展示“原文 PDF 转可编辑 Word”和四种翻译方向，并确保 direct 模式不暴露 AI 配置。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-101 为 `planning`；
   - 确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 CON-101，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 CON-101 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/translation/modes.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/utils/format.ts`
   - `frontend/src/components/PdfUploadPanel.vue`
   - `frontend/src/**/document*`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 保留历史 `zh2zh`/`zh_to_zh` 到 direct 的服务端兼容。
- 新 UI、文档和新 API 示例不再出现“中译中”。
- direct 模式隐藏翻译术语、翻译配置、Prompt、模型和 AI 调试项。
- 更新相关类型、文案、测试和 API 文档。

验收条件：
- 五种用户可见模式准确。
- direct 配置显隐正确。
- 旧 alias 仍可解析为 direct。
- 后端模式测试、前端 unit 和 build 通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 历史兼容 alias 不能被删除。
- 不得新增中文转中文 Prompt。
- direct 创建和执行不得触发翻译服务。

## 明确范围外

- 改变任务主输出数量。
- 增加新语言方向。
- 重做上传页面视觉体系。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 CON-101 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **CON-101：产品模式和 UI 文案收口** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-101`
依赖任务：BAS-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 CON-101 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# CON-102 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 执行阶段扩展 |
| 阶段 | R1 · 合同和状态 |
| 依赖 | BAS-001 |
| 建议分支 | `md2word/CON-102` |
| Trellis 子任务 slug | `con-102-document-job-stages` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/CON-102
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（BAS-001）的基线分支。若分支已存在，使用 `git switch md2word/CON-102`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **CON-102：执行阶段扩展** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-102`
发布阶段：`R1（合同和状态）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-102-document-job-stages`

## 本任务目标

为任务增加 `translating`、`translation_validating`、`quality_checking` 阶段，并保持旧任务和旧前端兼容。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-102 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 CON-102 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 CON-102 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/workflow.py`
   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/**`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 扩展后端 stage enum、合法状态映射和事件。
- direct 跳过翻译阶段。
- 翻译批次、完整性校验、渲染和质量检查事件映射到正确 stage。
- 前端增加新阶段文案并保留 unknown fallback。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 旧记录必须可读取。
- 不得把翻译 batch status 与 DocumentJob stage 混为同一状态。
- 失败阶段必须可定位。

## 明确范围外

- 同时实现质量状态字段。
- 同时实现 Review 或 Publication。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **CON-102：执行阶段扩展**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-102`
发布阶段：`R1（合同和状态）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-102-document-job-stages`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

为任务增加 `translating`、`translation_validating`、`quality_checking` 阶段，并保持旧任务和旧前端兼容。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-102 为 `planning`；
   - 确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 CON-102，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 CON-102 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/workflow.py`
   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/**`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 扩展后端 stage enum、合法状态映射和事件。
- direct 跳过翻译阶段。
- 翻译批次、完整性校验、渲染和质量检查事件映射到正确 stage。
- 前端增加新阶段文案并保留 unknown fallback。

验收条件：
- direct/translation 全路径阶段顺序有测试。
- 旧 stage 响应不崩溃。
- OpenAPI 和前端类型同步。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 旧记录必须可读取。
- 不得把翻译 batch status 与 DocumentJob stage 混为同一状态。
- 失败阶段必须可定位。

## 明确范围外

- 同时实现质量状态字段。
- 同时实现 Review 或 Publication。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 CON-102 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **CON-102：执行阶段扩展** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-102`
依赖任务：BAS-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 CON-102 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# CON-103 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 质量/复核/交付状态模型 |
| 阶段 | R1 · 合同和状态 |
| 依赖 | CON-102 |
| 建议分支 | `md2word/CON-103` |
| Trellis 子任务 slug | `con-103-quality-review-delivery-state` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/CON-103
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（CON-102）的基线分支。若分支已存在，使用 `git switch md2word/CON-103`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **CON-103：质量/复核/交付状态模型** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-103`
发布阶段：`R1（合同和状态）`
依赖任务：CON-102
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-103-quality-review-delivery-state`

## 本任务目标

在 DocumentJob 上建立独立 `quality_status`、`review_status`、`delivery_status` 和 `quality_summary`，并完成持久化、迁移和兼容投影。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-103 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 CON-102 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 CON-103 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 CON-103 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/schemas.py`
   - `app/infrastructure/persistence/**`
   - `app/infrastructure/mysql/**`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 新增 additive 数据库迁移与默认值。
- repository、service、schema、API 全链路读写。
- 旧任务 backfill 为 pending/unreviewed/internal_draft。
- 保留旧 translation QA 字段作为兼容投影，不自动批准 direct。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 执行、质量、复核、交付四维状态必须分离。
- blocked 不能 ready/published。
- 历史任务不得假定 passed。
- 迁移不得删除旧字段或历史数据。

## 明确范围外

- 实现 ReviewRecord 详情表。
- 实现发布接口。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要破坏性修改旧 translation QA 数据时停止。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **CON-103：质量/复核/交付状态模型**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-103`
发布阶段：`R1（合同和状态）`
依赖任务：CON-102
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-103-quality-review-delivery-state`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

在 DocumentJob 上建立独立 `quality_status`、`review_status`、`delivery_status` 和 `quality_summary`，并完成持久化、迁移和兼容投影。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-103 为 `planning`；
   - 确认依赖 CON-102 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 CON-103，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 CON-103 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/schemas.py`
   - `app/infrastructure/persistence/**`
   - `app/infrastructure/mysql/**`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 新增 additive 数据库迁移与默认值。
- repository、service、schema、API 全链路读写。
- 旧任务 backfill 为 pending/unreviewed/internal_draft。
- 保留旧 translation QA 字段作为兼容投影，不自动批准 direct。

验收条件：
- 迁移可前滚并有回滚/停用说明。
- 旧任务查询通过。
- 模型不变量和 repository 测试通过。
- OpenAPI 更新。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 执行、质量、复核、交付四维状态必须分离。
- blocked 不能 ready/published。
- 历史任务不得假定 passed。
- 迁移不得删除旧字段或历史数据。

## 明确范围外

- 实现 ReviewRecord 详情表。
- 实现发布接口。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要破坏性修改旧 translation QA 数据时停止。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- 若影响 API、状态或资源合同：`.venv/bin/python scripts/ops/check_release.py`。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 CON-103 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **CON-103：质量/复核/交付状态模型** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-103`
依赖任务：CON-102

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 CON-103 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# CON-104 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 下载和发布可用性合同 |
| 阶段 | R1 · 合同和状态 |
| 依赖 | CON-103 |
| 建议分支 | `md2word/CON-104` |
| Trellis 子任务 slug | `con-104-download-publish-availability` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/CON-104
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（CON-103）的基线分支。若分支已存在，使用 `git switch md2word/CON-104`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **CON-104：下载和发布可用性合同** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-104`
发布阶段：`R1（合同和状态）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-104-download-publish-availability`

## 本任务目标

由后端权威返回下载分类、警告和发布禁用原因，前端只消费该合同。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-104 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 CON-104 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 CON-104 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/**`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 定义 blocked/unreviewed/approved 的 download 与 publish available actions。
- 返回 `internal_only`、warning code/message 和 publish disabled reasons。
- 更新下载入口和发布按钮消费方式。
- 兼容现有 available actions。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- blocked 和 unreviewed 均允许内部下载。
- blocked 与 unreviewed 均不可发布。
- approved 且非 blocked 仅 Admin 可发布。
- 前端不得复制后端判定公式。

## 明确范围外

- 实现 PublicationRecord。
- 给 DOCX 强制加水印。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **CON-104：下载和发布可用性合同**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-104`
发布阶段：`R1（合同和状态）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`con-104-download-publish-availability`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

由后端权威返回下载分类、警告和发布禁用原因，前端只消费该合同。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 CON-104 为 `planning`；
   - 确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/design/quality-review-release-design.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 CON-104，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 CON-104 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/schemas.py`
   - `frontend/src/**`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 定义 blocked/unreviewed/approved 的 download 与 publish available actions。
- 返回 `internal_only`、warning code/message 和 publish disabled reasons。
- 更新下载入口和发布按钮消费方式。
- 兼容现有 available actions。

验收条件：
- 三类核心场景 API/前端测试通过。
- 错误状态有稳定机器码。
- 旧客户端仍能处理 additive 字段。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- blocked 和 unreviewed 均允许内部下载。
- blocked 与 unreviewed 均不可发布。
- approved 且非 blocked 仅 Admin 可发布。
- 前端不得复制后端判定公式。

## 明确范围外

- 实现 PublicationRecord。
- 给 DOCX 强制加水印。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 CON-104 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **CON-104：下载和发布可用性合同** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/CON-104`
依赖任务：CON-103

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 CON-104 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-201 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | MinerUArtifactValidator |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | BAS-001 |
| 建议分支 | `md2word/IR-201` |
| Trellis 子任务 slug | `ir-201-mineru-artifact-validator` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-201
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（BAS-001）的基线分支。若分支已存在，使用 `git switch md2word/IR-201`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-201：MinerUArtifactValidator** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-201`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-201-mineru-artifact-validator`

## 本任务目标

在 MinerU→DocumentIR 前对结果包、JSON、页面、bbox、HTML 和资产引用执行结构化验证。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-201 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-201 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-201 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/mineru_package.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/artifact_validator.py`
   - `app/domains/document_jobs/execution.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 验证 nested/flat content list、页数组、块字段、bbox、图片路径和表格 HTML。
- 输出结构化 warnings/blockers，而非自由文本。
- 拒绝路径穿越和把 `images/` 目录当作有效图片文件。
- 将 evidence 接入任务事件和质量聚合边界。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不做 PDF OCR 预检。
- 不修改 MinerU 技术内容。
- 包路径必须限制在解压根目录。

## 明确范围外

- 修复表格内容。
- 引入第二解析器。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-201：MinerUArtifactValidator**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-201`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-201-mineru-artifact-validator`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

在 MinerU→DocumentIR 前对结果包、JSON、页面、bbox、HTML 和资产引用执行结构化验证。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-201 为 `planning`；
   - 确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-201，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-201 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/mineru_package.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/artifact_validator.py`
   - `app/domains/document_jobs/execution.py`
   - `tests/**`

必须交付：
- 验证 nested/flat content list、页数组、块字段、bbox、图片路径和表格 HTML。
- 输出结构化 warnings/blockers，而非自由文本。
- 拒绝路径穿越和把 `images/` 目录当作有效图片文件。
- 将 evidence 接入任务事件和质量聚合边界。

验收条件：
- 恶意路径、非法 bbox、缺图、空 HTML 和正常包均有单测。
- 正常历史包不被误阻断。
- validator 结果可序列化。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不做 PDF OCR 预检。
- 不修改 MinerU 技术内容。
- 包路径必须限制在解压根目录。

## 明确范围外

- 修复表格内容。
- 引入第二解析器。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-201 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-201：MinerUArtifactValidator** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-201`
依赖任务：BAS-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-201 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-202 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | MarginArtifactNormalizer |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-201 |
| 建议分支 | `md2word/IR-202` |
| Trellis 子任务 slug | `ir-202-margin-artifact-normalizer` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-202
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-201）的基线分支。若分支已存在，使用 `git switch md2word/IR-202`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-202：MarginArtifactNormalizer** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-202`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-202-margin-artifact-normalizer`

## 本任务目标

使用跨页重复、顶部/底部位置和文本稳定性重新判定运行页眉页脚。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-202 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-202 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-202 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/layout_signals.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/margin_artifact_normalizer.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 识别高频固定位置的型号、公司名、版本号和页码。
- 高置信度时重分类 role；低置信度只加 flag。
- 保留原始 source type 和 bbox metadata。
- 增加 ZK7044 型号标题、版本号 paragraph、一次性正文标题回归。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得按 raw type 无条件删除。
- 不得改变主阅读顺序。
- 一次性正文标题不得因位于页顶而被删除。

## 明确范围外

- 推断完整标题层级。
- 修改公司模板页眉页脚。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-202：MarginArtifactNormalizer**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-202`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-202-margin-artifact-normalizer`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

使用跨页重复、顶部/底部位置和文本稳定性重新判定运行页眉页脚。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-202 为 `planning`；
   - 确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-202，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-202 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/layout_signals.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/margin_artifact_normalizer.py`
   - `tests/**`

必须交付：
- 识别高频固定位置的型号、公司名、版本号和页码。
- 高置信度时重分类 role；低置信度只加 flag。
- 保留原始 source type 和 bbox metadata。
- 增加 ZK7044 型号标题、版本号 paragraph、一次性正文标题回归。

验收条件：
- ZK7044 典型误分类样本通过。
- 旧页眉页脚行为不回归。
- 所有自动重分类都有 evidence。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得按 raw type 无条件删除。
- 不得改变主阅读顺序。
- 一次性正文标题不得因位于页顶而被删除。

## 明确范围外

- 推断完整标题层级。
- 修改公司模板页眉页脚。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-202 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-202：MarginArtifactNormalizer** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-202`
依赖任务：IR-201

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-202 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-203 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | CrossPageParagraphMerger |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-201 |
| 建议分支 | `md2word/IR-203` |
| Trellis 子任务 slug | `ir-203-cross-page-paragraph-merger` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-203
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-201）的基线分支。若分支已存在，使用 `git switch md2word/IR-203`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-203：CrossPageParagraphMerger** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-203`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-203-cross-page-paragraph-merger`

## 本任务目标

保守合并明显跨页断开的逻辑段落，并保留全部 source spans。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-203 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-203 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-203 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/models.py`
   - `app/services/document_ir/cross_page_paragraph_merger.py`
   - `app/services/document_ir/mineru_converter.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 依据结束标点、下一块类型、缩进、页边界和列表编号判断。
- 合并后保存多页 bbox/source span。
- 为不确定情况增加 flag 而非强制合并。
- 覆盖 ZK7044 第 29–30、40–41 页。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得跨标题、表格、图片或新列表项合并。
- 不得改写文本。
- 源块 ID 和顺序可追溯。

## 明确范围外

- 做通用语言纠错。
- 跨多个非连续页面合并。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-203：CrossPageParagraphMerger**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-203`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-203-cross-page-paragraph-merger`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

保守合并明显跨页断开的逻辑段落，并保留全部 source spans。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-203 为 `planning`；
   - 确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-203，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-203 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/models.py`
   - `app/services/document_ir/cross_page_paragraph_merger.py`
   - `app/services/document_ir/mineru_converter.py`
   - `tests/**`

必须交付：
- 依据结束标点、下一块类型、缩进、页边界和列表编号判断。
- 合并后保存多页 bbox/source span。
- 为不确定情况增加 flag 而非强制合并。
- 覆盖 ZK7044 第 29–30、40–41 页。

验收条件：
- 正例和负例单测齐全。
- 合并后翻译/渲染仍能定位两个源页面。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得跨标题、表格、图片或新列表项合并。
- 不得改写文本。
- 源块 ID 和顺序可追溯。

## 明确范围外

- 做通用语言纠错。
- 跨多个非连续页面合并。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-203 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-203：CrossPageParagraphMerger** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-203`
依赖任务：IR-201

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-203 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-204 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | CaptionReconciler 增强 |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-201 |
| 建议分支 | `md2word/IR-204` |
| Trellis 子任务 slug | `ir-204-caption-reconciler` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-204
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-201）的基线分支。若分支已存在，使用 `git switch md2word/IR-204`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-204：CaptionReconciler 增强** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-204`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-204-caption-reconciler`

## 本任务目标

统一 image/chart/table caption 的拆分、编号和相邻对象绑定，并为不确定关系生成 QA 标记。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-204 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-204 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-204 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/table_annotations.py`
   - `app/services/document_ir/caption_reconciler.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 扩展严格编号序列修复。
- 支持一个 caption 中多个图/表编号的拆分。
- 为无 caption 相邻对象补绑定 evidence。
- 覆盖图 5/6、图 24/25 和表 caption 组合。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只在严格可判定时自动修复。
- 不得依据语言模型猜测 caption。
- 原始 caption 必须保留在 metadata/evidence。

## 明确范围外

- 图片内部文字识别。
- 在线人工编辑 caption。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-204：CaptionReconciler 增强**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-204`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-204-caption-reconciler`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

统一 image/chart/table caption 的拆分、编号和相邻对象绑定，并为不确定关系生成 QA 标记。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-204 为 `planning`；
   - 确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-204，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-204 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/mineru_converter.py`
   - `app/services/document_ir/table_annotations.py`
   - `app/services/document_ir/caption_reconciler.py`
   - `tests/**`

必须交付：
- 扩展严格编号序列修复。
- 支持一个 caption 中多个图/表编号的拆分。
- 为无 caption 相邻对象补绑定 evidence。
- 覆盖图 5/6、图 24/25 和表 caption 组合。

验收条件：
- 正例绑定正确。
- 不确定样本产生 `caption_binding_uncertain`。
- 图片、表格和翻译链路不回归。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只在严格可判定时自动修复。
- 不得依据语言模型猜测 caption。
- 原始 caption 必须保留在 metadata/evidence。

## 明确范围外

- 图片内部文字识别。
- 在线人工编辑 caption。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-204 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-204：CaptionReconciler 增强** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-204`
依赖任务：IR-201

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-204 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-205 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | LogicalTableGroup 与 source spans |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-201 |
| 建议分支 | `md2word/IR-205` |
| Trellis 子任务 slug | `ir-205-logical-table-group` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-205
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-201）的基线分支。若分支已存在，使用 `git switch md2word/IR-205`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-205：LogicalTableGroup 与 source spans** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-205`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-205-logical-table-group`

## 本任务目标

把页级 table fragments 表达为可追溯的逻辑表格组。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-205 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-205 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-205 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/models.py`
   - `app/services/document_ir/layout_signals.py`
   - `app/services/document_ir/logical_table_group.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 `logical_group_id`、fragment page/bbox、continuation relation、header signature 和 repeated-header hint。
- 保留每个原始 fragment 和 raw HTML。
- 将逻辑组 metadata 写入 DocumentIR 或独立 artifact。
- 覆盖表 3、表 9、表 10、表 24。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得凭空补齐缺失 fragment。
- 不得在本任务中实现 Word 合并渲染。
- 主阅读顺序和 source spans 必须稳定。

## 明确范围外

- 实现 CanonicalTableGrid。
- 实现表格截图回退。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-205：LogicalTableGroup 与 source spans**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-205`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-205-logical-table-group`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

把页级 table fragments 表达为可追溯的逻辑表格组。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-205 为 `planning`；
   - 确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-205，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-205 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/models.py`
   - `app/services/document_ir/layout_signals.py`
   - `app/services/document_ir/logical_table_group.py`
   - `tests/**`

必须交付：
- 定义 `logical_group_id`、fragment page/bbox、continuation relation、header signature 和 repeated-header hint。
- 保留每个原始 fragment 和 raw HTML。
- 将逻辑组 metadata 写入 DocumentIR 或独立 artifact。
- 覆盖表 3、表 9、表 10、表 24。

验收条件：
- 连续表格正确归组。
- 相邻但不同表格不误合并。
- 空 fragment 仍保留并可被后续 blocked 策略消费。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得凭空补齐缺失 fragment。
- 不得在本任务中实现 Word 合并渲染。
- 主阅读顺序和 source spans 必须稳定。

## 明确范围外

- 实现 CanonicalTableGrid。
- 实现表格截图回退。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-205 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-205：LogicalTableGroup 与 source spans** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-205`
依赖任务：IR-201

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-205 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-206 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Table Reference Asset |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-205 |
| 建议分支 | `md2word/IR-206` |
| Trellis 子任务 slug | `ir-206-table-reference-asset` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-206
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-205）的基线分支。若分支已存在，使用 `git switch md2word/IR-206`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-206：Table Reference Asset** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-206`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-206-table-reference-asset`

## 本任务目标

把 MinerU 表格截图登记为一等 QA Artifact，并通过受控接口供审核使用。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-206 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-206 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-206 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/document_ir/models.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/domains/files/**`
   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/router.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 为表格 reference image 保存 source path、mime、checksum、file ID 和 block/group 关联。
- 缺失 reference 生成 warning。
- 审核 API 使用权限校验后的下载/展示入口。
- 不改变正常 Word 表格渲染。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- Reference Image 不得成为 HTML 正常时的默认 Word 内容。
- 不得返回内部对象路径或公共匿名 URL。
- 资产路径必须经过 validator。

## 明确范围外

- 实现三栏前端。
- 从图片自动重建表格。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-206：Table Reference Asset**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-206`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-206-table-reference-asset`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

把 MinerU 表格截图登记为一等 QA Artifact，并通过受控接口供审核使用。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-206 为 `planning`；
   - 确认依赖 IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-206，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-206 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/document_ir/models.py`
   - `app/services/document_ir/mineru_converter.py`
   - `app/domains/files/**`
   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/router.py`
   - `tests/**`

必须交付：
- 为表格 reference image 保存 source path、mime、checksum、file ID 和 block/group 关联。
- 缺失 reference 生成 warning。
- 审核 API 使用权限校验后的下载/展示入口。
- 不改变正常 Word 表格渲染。

验收条件：
- 表格 reference 可从任务详情/审核 API 定位。
- 缺失和正常场景测试通过。
- 文件保留和删除策略一致。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- Reference Image 不得成为 HTML 正常时的默认 Word 内容。
- 不得返回内部对象路径或公共匿名 URL。
- 资产路径必须经过 validator。

## 明确范围外

- 实现三栏前端。
- 从图片自动重建表格。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- 若影响 API、状态或资源合同：`.venv/bin/python scripts/ops/check_release.py`。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-206 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-206：Table Reference Asset** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-206`
依赖任务：IR-205

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-206 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# IR-207 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | ZK7044 最小回归样本 |
| 阶段 | R2 · MinerU 与 DocumentIR |
| 依赖 | IR-201 |
| 建议分支 | `md2word/IR-207` |
| Trellis 子任务 slug | `ir-207-zk7044-minimal-fixtures` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/IR-207
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-201）的基线分支。若分支已存在，使用 `git switch md2word/IR-207`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **IR-207：ZK7044 最小回归样本** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-207`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-207-zk7044-minimal-fixtures`

## 本任务目标

从 ZK7044 MinerU 结果中沉淀多个最小、可离线复现风险的 fixture。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-207 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 IR-207 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 IR-207 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `tests/fixtures/component_pdf_samples/**`
   - `scripts/dev/manage_component_pdf_samples.py`
   - `scripts/dev/run_component_pdf_regression.py`
   - `docs/dev/component-pdf-regression-governance.md`

## 规划必须覆盖的交付物

- 按 overview、complex-table、corrupted-table、missing-table、caption-pair、cross-page-paragraph、register-map 分页组最小化。
- manifest 写明来源、风险、验收焦点和授权/最小化说明。
- 避免提交完整厂商/客户文档和生成 DOCX。
- runner 可按 sample ID 离线执行。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只保留复现所需块和图片。
- 不得伪造预期结果来迎合现有实现。
- 专有内容授权不明确时必须去标识/最小化或停止。

## 明确范围外

- 修改转换算法。
- 提交完整 69 页资料。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 样本授权或最小化方式无法确认时停止。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **IR-207：ZK7044 最小回归样本**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-207`
发布阶段：`R2（MinerU 与 DocumentIR）`
依赖任务：IR-201
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`ir-207-zk7044-minimal-fixtures`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

从 ZK7044 MinerU 结果中沉淀多个最小、可离线复现风险的 fixture。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 IR-207 为 `planning`；
   - 确认依赖 IR-201 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/mineru-artifact-contract.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 IR-207，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 IR-207 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `tests/fixtures/component_pdf_samples/**`
   - `scripts/dev/manage_component_pdf_samples.py`
   - `scripts/dev/run_component_pdf_regression.py`
   - `docs/dev/component-pdf-regression-governance.md`

必须交付：
- 按 overview、complex-table、corrupted-table、missing-table、caption-pair、cross-page-paragraph、register-map 分页组最小化。
- manifest 写明来源、风险、验收焦点和授权/最小化说明。
- 避免提交完整厂商/客户文档和生成 DOCX。
- runner 可按 sample ID 离线执行。

验收条件：
- manifest 校验通过。
- 每个 fixture 能稳定暴露目标风险。
- 仓库体积可控。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只保留复现所需块和图片。
- 不得伪造预期结果来迎合现有实现。
- 专有内容授权不明确时必须去标识/最小化或停止。

## 明确范围外

- 修改转换算法。
- 提交完整 69 页资料。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 样本授权或最小化方式无法确认时停止。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 DocumentIR/MinerU 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`，或先运行本任务新增的单一样本再运行全量。
- `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 IR-207 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **IR-207：ZK7044 最小回归样本** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/IR-207`
依赖任务：IR-201

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 IR-207 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-301 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | CanonicalTableGrid 模型 |
| 阶段 | R3 · 表格核心 |
| 依赖 | IR-205 |
| 建议分支 | `md2word/TAB-301` |
| Trellis 子任务 slug | `tab-301-canonical-table-grid` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-301
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-205）的基线分支。若分支已存在，使用 `git switch md2word/TAB-301`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-301：CanonicalTableGrid 模型** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-301`
发布阶段：`R3（表格核心）`
依赖任务：IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-301-canonical-table-grid`

## 本任务目标

定义可序列化、可翻译、可验证和可渲染的稳定二维表格模型。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-301 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-301 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-301 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/tables/**`
   - `app/services/document_ir/models.py`
   - `app/conversion/runtime/table_html_parser.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 TableGrid、TableCell、CellRun、source fragment、span、header、quality 字段。
- 设计稳定 table/cell/run ID。
- 保存 raw HTML hash 和模型版本。
- 实现 JSON roundtrip 与兼容读取。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- raw HTML 永久保留。
- 模型不得包含 Word 专有对象。
- 本任务不改变现有 renderer 行为。

## 明确范围外

- 实现 HTML parser。
- 实现 Word 渲染。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-301：CanonicalTableGrid 模型**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-301`
发布阶段：`R3（表格核心）`
依赖任务：IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-301-canonical-table-grid`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

定义可序列化、可翻译、可验证和可渲染的稳定二维表格模型。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-301 为 `planning`；
   - 确认依赖 IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-301，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-301 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/tables/**`
   - `app/services/document_ir/models.py`
   - `app/conversion/runtime/table_html_parser.py`
   - `tests/**`

必须交付：
- 定义 TableGrid、TableCell、CellRun、source fragment、span、header、quality 字段。
- 设计稳定 table/cell/run ID。
- 保存 raw HTML hash 和模型版本。
- 实现 JSON roundtrip 与兼容读取。

验收条件：
- 模型校验和序列化单测通过。
- ID 在同一输入下确定性稳定。
- 非法 span/重复 ID 被拒绝。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- raw HTML 永久保留。
- 模型不得包含 Word 专有对象。
- 本任务不改变现有 renderer 行为。

## 明确范围外

- 实现 HTML parser。
- 实现 Word 渲染。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-301 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-301：CanonicalTableGrid 模型** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-301`
依赖任务：IR-205

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-301 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-302 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | HTML Normalizer/Grid Builder |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-301 |
| 建议分支 | `md2word/TAB-302` |
| Trellis 子任务 slug | `tab-302-html-normalizer-grid-builder` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-302
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-301）的基线分支。若分支已存在，使用 `git switch md2word/TAB-302`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-302：HTML Normalizer/Grid Builder** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-302`
发布阶段：`R3（表格核心）`
依赖任务：TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-302-html-normalizer-grid-builder`

## 本任务目标

从 MinerU HTML 确定性构建 CanonicalTableGrid，并显式表示 span 冲突和单元格 runs。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-302 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-302 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-302 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/conversion/runtime/table_html_parser.py`
   - `app/services/tables/html_normalizer.py`
   - `app/services/tables/grid_builder.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 保留 raw HTML，生成 normalized HTML。
- 处理 `rowspan`、`colspan`、`br`、`sup`、`sub`、公式和嵌套标记。
- 构建占位网格并检测越界/冲突。
- 不自动修改数字、单位和技术内容。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 冲突不得静默覆盖。
- 不允许把整表作为纯文本处理。
- 不在此任务中修复 MinerU 技术错误。

## 明确范围外

- 实现质量严重度。
- 实现翻译 context。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-302：HTML Normalizer/Grid Builder**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-302`
发布阶段：`R3（表格核心）`
依赖任务：TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-302-html-normalizer-grid-builder`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

从 MinerU HTML 确定性构建 CanonicalTableGrid，并显式表示 span 冲突和单元格 runs。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-302 为 `planning`；
   - 确认依赖 TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-302，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-302 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/conversion/runtime/table_html_parser.py`
   - `app/services/tables/html_normalizer.py`
   - `app/services/tables/grid_builder.py`
   - `tests/**`

必须交付：
- 保留 raw HTML，生成 normalized HTML。
- 处理 `rowspan`、`colspan`、`br`、`sup`、`sub`、公式和嵌套标记。
- 构建占位网格并检测越界/冲突。
- 不自动修改数字、单位和技术内容。

验收条件：
- 正常、畸形、合并、公式和空单元格测试通过。
- 同一 HTML 输出稳定。
- 原表内容可逐 run 回溯。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 冲突不得静默覆盖。
- 不允许把整表作为纯文本处理。
- 不在此任务中修复 MinerU 技术错误。

## 明确范围外

- 实现质量严重度。
- 实现翻译 context。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-302 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-302：HTML Normalizer/Grid Builder** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-302`
依赖任务：TAB-301

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-302 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-303 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Table Validator/Quality Flags |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-302 |
| 建议分支 | `md2word/TAB-303` |
| Trellis 子任务 slug | `tab-303-table-validator-quality-flags` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-303
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-302）的基线分支。若分支已存在，使用 `git switch md2word/TAB-303`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-303：Table Validator/Quality Flags** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-303`
发布阶段：`R3（表格核心）`
依赖任务：TAB-302
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-303-table-validator-quality-flags`

## 本任务目标

检测表格结构和内容异常，生成可聚合的 blocker/warning 标记，但不修改表格内容。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-303 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-302 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-303 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-303 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/tables/validator.py`
   - `app/services/tables/quality.py`
   - `app/services/document_ir/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 检测空 HTML、grid 不闭合、列数不一致、span 冲突、数字粘连、单位粘连、异常长数字和跨页不一致。
- 定义稳定机器码和 evidence。
- 支持按配置映射为 warning/blocker。
- 接入任务质量聚合接口边界。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- validator 只标记，不自动拆分单元格或改数值。
- 同一问题机器码稳定。
- 误报需要最小样本覆盖。

## 明确范围外

- 实现 Review UI。
- 调用 LLM 修表。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-303：Table Validator/Quality Flags**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-303`
发布阶段：`R3（表格核心）`
依赖任务：TAB-302
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-303-table-validator-quality-flags`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

检测表格结构和内容异常，生成可聚合的 blocker/warning 标记，但不修改表格内容。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-303 为 `planning`；
   - 确认依赖 TAB-302 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-303，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-303 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/tables/validator.py`
   - `app/services/tables/quality.py`
   - `app/services/document_ir/**`
   - `tests/**`

必须交付：
- 检测空 HTML、grid 不闭合、列数不一致、span 冲突、数字粘连、单位粘连、异常长数字和跨页不一致。
- 定义稳定机器码和 evidence。
- 支持按配置映射为 warning/blocker。
- 接入任务质量聚合接口边界。

验收条件：
- ZK7044 表 6 产生预期粘连 flags。
- 正常 OPA228/ZK7044 表不被误阻断。
- 严重度配置有测试。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- validator 只标记，不自动拆分单元格或改数值。
- 同一问题机器码稳定。
- 误报需要最小样本覆盖。

## 明确范围外

- 实现 Review UI。
- 调用 LLM 修表。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-303 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-303：Table Validator/Quality Flags** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-303`
依赖任务：TAB-302

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-303 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-304 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 大表保留合并关系 |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-302 |
| 建议分支 | `md2word/TAB-304` |
| Trellis 子任务 slug | `tab-304-large-table-merge-preservation` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-304
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-302）的基线分支。若分支已存在，使用 `git switch md2word/TAB-304`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-304：大表保留合并关系** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-304`
发布阶段：`R3（表格核心）`
依赖任务：TAB-302
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-304-large-table-merge-preservation`

## 本任务目标

替换当前超阈值展开 span 的默认策略，使大表仍使用 Word `gridSpan`/`vMerge` 保留合并语义。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-304 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-302 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-304 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-304 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/table_renderer.py`
   - `app/services/tables/**`
   - `app/conversion/runtime/table_html_parser.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 使用 CanonicalTableGrid 渲染大表。
- 保留跨行跨列合并。
- 通过流式/分段/复用降低内存，而不是展开结构。
- 失败时产生明确错误/blocked evidence，不改成截图。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- HTML 存在时必须保持原生 Word Table。
- 不得因行数或 HTML 长度阈值丢失 merge。
- 不得静默截断行列。

## 明确范围外

- 跨页 logical fragments 合并。
- 空 HTML 占位。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-304：大表保留合并关系**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-304`
发布阶段：`R3（表格核心）`
依赖任务：TAB-302
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-304-large-table-merge-preservation`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

替换当前超阈值展开 span 的默认策略，使大表仍使用 Word `gridSpan`/`vMerge` 保留合并语义。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-304 为 `planning`；
   - 确认依赖 TAB-302 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-304，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-304 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/table_renderer.py`
   - `app/services/tables/**`
   - `app/conversion/runtime/table_html_parser.py`
   - `tests/**`

必须交付：
- 使用 CanonicalTableGrid 渲染大表。
- 保留跨行跨列合并。
- 通过流式/分段/复用降低内存，而不是展开结构。
- 失败时产生明确错误/blocked evidence，不改成截图。

验收条件：
- 超大寄存器表 DOCX 可打开且合并关系存在。
- 常规表格不回归。
- 性能/内存证据被记录。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- HTML 存在时必须保持原生 Word Table。
- 不得因行数或 HTML 长度阈值丢失 merge。
- 不得静默截断行列。

## 明确范围外

- 跨页 logical fragments 合并。
- 空 HTML 占位。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-304 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-304：大表保留合并关系** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-304`
依赖任务：TAB-302

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-304 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-305 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 跨页逻辑表 Word 渲染 |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-304、IR-205 |
| 建议分支 | `md2word/TAB-305` |
| Trellis 子任务 slug | `tab-305-cross-page-logical-table-rendering` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-305
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-304、IR-205）的基线分支。若分支已存在，使用 `git switch md2word/TAB-305`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-305：跨页逻辑表 Word 渲染** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-305`
发布阶段：`R3（表格核心）`
依赖任务：TAB-304、IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-305-cross-page-logical-table-rendering`

## 本任务目标

将多个 LogicalTableGroup fragment 渲染成一个 Word Table，并保留 source evidence。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-305 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-304、IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-305 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-305 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/table_renderer.py`
   - `app/services/renderer/layout_plan.py`
   - `app/services/tables/**`
   - `tests/**`

## 规划必须覆盖的交付物

- caption 只输出一次。
- 删除/识别重复表头并设置 Word repeat header。
- 允许 Word 自然分页。
- 记录每个 fragment 到输出表格的 evidence。
- 覆盖表 10、表 24。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得猜测或补齐缺失 fragment。
- 不同逻辑表不得合并。
- 空 fragment 必须交由 blocked 策略。

## 明确范围外

- 实现表格在线编辑。
- 重新解析 PDF 表格。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-305：跨页逻辑表 Word 渲染**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-305`
发布阶段：`R3（表格核心）`
依赖任务：TAB-304、IR-205
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-305-cross-page-logical-table-rendering`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

将多个 LogicalTableGroup fragment 渲染成一个 Word Table，并保留 source evidence。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-305 为 `planning`；
   - 确认依赖 TAB-304、IR-205 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-305，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-305 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/table_renderer.py`
   - `app/services/renderer/layout_plan.py`
   - `app/services/tables/**`
   - `tests/**`

必须交付：
- caption 只输出一次。
- 删除/识别重复表头并设置 Word repeat header。
- 允许 Word 自然分页。
- 记录每个 fragment 到输出表格的 evidence。
- 覆盖表 10、表 24。

验收条件：
- 多页表只产生一个 Word Table。
- 表头重复和 source spans 正确。
- 缺失 fragment 不被静默忽略。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得猜测或补齐缺失 fragment。
- 不同逻辑表不得合并。
- 空 fragment 必须交由 blocked 策略。

## 明确范围外

- 实现表格在线编辑。
- 重新解析 PDF 表格。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-305 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-305：跨页逻辑表 Word 渲染** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-305`
依赖任务：TAB-304、IR-205

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-305 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-306 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 空 HTML 内部占位和 blocked |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-303、CON-103 |
| 建议分支 | `md2word/TAB-306` |
| Trellis 子任务 slug | `tab-306-empty-html-placeholder-blocked` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-306
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-303、CON-103）的基线分支。若分支已存在，使用 `git switch md2word/TAB-306`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-306：空 HTML 内部占位和 blocked** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-306`
发布阶段：`R3（表格核心）`
依赖任务：TAB-303、CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-306-empty-html-placeholder-blocked`

## 本任务目标

实现空 HTML 表格的受控非编辑占位、质量阻塞、可内部下载和不可发布策略。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-306 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-303、CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-306 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-306 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/table_renderer.py`
   - `app/services/document_ir/**`
   - `app/domains/document_jobs/**`
   - `app/domains/files/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 有 reference image 时插入明确标记的表格占位。
- 无 reference 时使用 source PDF + page/bbox 裁图（通过受控 provider/adapter）。
- 设置质量 `blocked` 和稳定问题码。
- available actions 保持 download true、publish false。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 占位必须标明非编辑和来源。
- 不得把占位误认为正常 native table。
- 不得允许批准或发布。

## 明确范围外

- 自动重建缺失表格。
- 把所有异常表格都转图片。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-306：空 HTML 内部占位和 blocked**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-306`
发布阶段：`R3（表格核心）`
依赖任务：TAB-303、CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-306-empty-html-placeholder-blocked`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现空 HTML 表格的受控非编辑占位、质量阻塞、可内部下载和不可发布策略。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-306 为 `planning`；
   - 确认依赖 TAB-303、CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-306，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-306 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/table_renderer.py`
   - `app/services/document_ir/**`
   - `app/domains/document_jobs/**`
   - `app/domains/files/**`
   - `tests/**`

必须交付：
- 有 reference image 时插入明确标记的表格占位。
- 无 reference 时使用 source PDF + page/bbox 裁图（通过受控 provider/adapter）。
- 设置质量 `blocked` 和稳定问题码。
- available actions 保持 download true、publish false。

验收条件：
- 有/无 reference 两类场景通过。
- DOCX 可下载。
- blocked 门禁和 API negative test 通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 占位必须标明非编辑和来源。
- 不得把占位误认为正常 native table。
- 不得允许批准或发布。

## 明确范围外

- 自动重建缺失表格。
- 把所有异常表格都转图片。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-306 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-306：空 HTML 内部占位和 blocked** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-306`
依赖任务：TAB-303、CON-103

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-306 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-307 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 表格 evidence 聚合 |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-303、TAB-304 |
| 建议分支 | `md2word/TAB-307` |
| Trellis 子任务 slug | `tab-307-table-evidence-aggregation` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-307
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-303、TAB-304）的基线分支。若分支已存在，使用 `git switch md2word/TAB-307`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-307：表格 evidence 聚合** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-307`
发布阶段：`R3（表格核心）`
依赖任务：TAB-303、TAB-304
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-307-table-evidence-aggregation`

## 本任务目标

生成 table-level evidence，统一结构、reference、Word shape、source spans 和 quality flags。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-307 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-303、TAB-304 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-307 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-307 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/evidence.py`
   - `app/services/renderer/docx_quality.py`
   - `app/services/tables/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 table evidence schema。
- 聚合 source grid、reference asset、Word table shape、merge、fragment 和 flags。
- 写入质量报告 artifact/summary。
- 为后续 Review API 提供稳定查询合同。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- evidence 不得包含未授权全文或内部存储路径。
- 不得改变文档内容。
- 机器码和 block/table ID 必须稳定。

## 明确范围外

- 实现 QA 页面。
- 引入新的 BI/分析平台。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-307：表格 evidence 聚合**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-307`
发布阶段：`R3（表格核心）`
依赖任务：TAB-303、TAB-304
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-307-table-evidence-aggregation`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

生成 table-level evidence，统一结构、reference、Word shape、source spans 和 quality flags。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-307 为 `planning`；
   - 确认依赖 TAB-303、TAB-304 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-307，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-307 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/evidence.py`
   - `app/services/renderer/docx_quality.py`
   - `app/services/tables/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

必须交付：
- 定义 table evidence schema。
- 聚合 source grid、reference asset、Word table shape、merge、fragment 和 flags。
- 写入质量报告 artifact/summary。
- 为后续 Review API 提供稳定查询合同。

验收条件：
- 单表和任务级聚合测试通过。
- 表 6、空 HTML、大表 evidence 完整。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- evidence 不得包含未授权全文或内部存储路径。
- 不得改变文档内容。
- 机器码和 block/table ID 必须稳定。

## 明确范围外

- 实现 QA 页面。
- 引入新的 BI/分析平台。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-307 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-307：表格 evidence 聚合** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-307`
依赖任务：TAB-303、TAB-304

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-307 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TAB-308 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 表格专项回归门禁 |
| 阶段 | R3 · 表格核心 |
| 依赖 | TAB-304、TAB-305、TAB-306、TAB-307、IR-207 |
| 建议分支 | `md2word/TAB-308` |
| Trellis 子任务 slug | `tab-308-table-regression-gate` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TAB-308
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-304、TAB-305、TAB-306、TAB-307、IR-207）的基线分支。若分支已存在，使用 `git switch md2word/TAB-308`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TAB-308：表格专项回归门禁** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-308`
发布阶段：`R3（表格核心）`
依赖任务：TAB-304、TAB-305、TAB-306、TAB-307、IR-207
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-308-table-regression-gate`

## 本任务目标

把 OPA228 和 ZK7044 表格风险纳入可重复脚本及 release gate。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-308 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-304、TAB-305、TAB-306、TAB-307、IR-207 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TAB-308 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TAB-308 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `tests/fixtures/**`
   - `scripts/dev/run_component_pdf_regression.py`
   - `scripts/ops/check_release.py`
   - `scripts/ops/run_golden_sample_regression.py`
   - `docs/engineering/testing-acceptance-strategy.md`

## 规划必须覆盖的交付物

- 增加 HTML→Word Table、merge 保留、空 HTML blocked、blocked 不可发布等自动门禁。
- 输出可审计报告和 sample ID。
- 区分 P0/P1/P2。
- 确保脚本离线可运行。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得提交完整专有 PDF 或生成 DOCX。
- 门禁不得依赖真实外部 AI。
- 失败不得被 warning 静默吞掉。

## 明确范围外

- 修复表格算法本身。
- 扩大到泛 PDF。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TAB-308：表格专项回归门禁**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-308`
发布阶段：`R3（表格核心）`
依赖任务：TAB-304、TAB-305、TAB-306、TAB-307、IR-207
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tab-308-table-regression-gate`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

把 OPA228 和 ZK7044 表格风险纳入可重复脚本及 release gate。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TAB-308 为 `planning`；
   - 确认依赖 TAB-304、TAB-305、TAB-306、TAB-307、IR-207 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/table-processing-design.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TAB-308，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TAB-308 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `tests/fixtures/**`
   - `scripts/dev/run_component_pdf_regression.py`
   - `scripts/ops/check_release.py`
   - `scripts/ops/run_golden_sample_regression.py`
   - `docs/engineering/testing-acceptance-strategy.md`

必须交付：
- 增加 HTML→Word Table、merge 保留、空 HTML blocked、blocked 不可发布等自动门禁。
- 输出可审计报告和 sample ID。
- 区分 P0/P1/P2。
- 确保脚本离线可运行。

验收条件：
- 所有表格门禁正负样本通过。
- release check 能阻止回归。
- 报告可定位到任务/样本/flag。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得提交完整专有 PDF 或生成 DOCX。
- 门禁不得依赖真实外部 AI。
- 失败不得被 warning 静默吞掉。

## 明确范围外

- 修复表格算法本身。
- 扩大到泛 PDF。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的表格模型/解析/渲染定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`（渲染行为变化时）。
- 检查生成 DOCX 的 OOXML/quality evidence；不得只检查文件可打开。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TAB-308 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TAB-308：表格专项回归门禁** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TAB-308`
依赖任务：TAB-304、TAB-305、TAB-306、TAB-307、IR-207

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TAB-308 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-401 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Caption/Footnote 翻译覆盖 |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | IR-204 |
| 建议分支 | `md2word/TR-401` |
| Trellis 子任务 slug | `tr-401-caption-footnote-translation` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-401
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-204）的基线分支。若分支已存在，使用 `git switch md2word/TR-401`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-401：Caption/Footnote 翻译覆盖** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-401`
发布阶段：`R4（翻译完整性）`
依赖任务：IR-204
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-401-caption-footnote-translation`

## 本任务目标

显式抽取并回填 image、chart、table 的 captions 和 footnotes。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-401 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-204 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-401 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-401 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/translation/document_ir_translator.py`
   - `app/domains/translation/models.py`
   - `app/services/document_ir/models.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 为 annotation 生成稳定 translation item ID。
- 翻译后按原索引回填。
- 保持 blocks/assets/layout/HTML 结构不变。
- direct 模式不执行 annotation 翻译。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得把 caption/footnote 合并进无关正文。
- 不得翻译图片像素内文字。
- 缺失/额外 ID 必须失败关闭。

## 明确范围外

- Protected Token。
- 重做 CaptionReconciler。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-401：Caption/Footnote 翻译覆盖**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-401`
发布阶段：`R4（翻译完整性）`
依赖任务：IR-204
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-401-caption-footnote-translation`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

显式抽取并回填 image、chart、table 的 captions 和 footnotes。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-401 为 `planning`；
   - 确认依赖 IR-204 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-401，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-401 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/translation/document_ir_translator.py`
   - `app/domains/translation/models.py`
   - `app/services/document_ir/models.py`
   - `tests/**`

必须交付：
- 为 annotation 生成稳定 translation item ID。
- 翻译后按原索引回填。
- 保持 blocks/assets/layout/HTML 结构不变。
- direct 模式不执行 annotation 翻译。

验收条件：
- image/chart/table annotation 正负测试通过。
- 翻译后数量、顺序和 ID 稳定。
- direct Provider 调用仍为 0。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得把 caption/footnote 合并进无关正文。
- 不得翻译图片像素内文字。
- 缺失/额外 ID 必须失败关闭。

## 明确范围外

- Protected Token。
- 重做 CaptionReconciler。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-401 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-401：Caption/Footnote 翻译覆盖** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-401`
依赖任务：IR-204

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-401 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-402 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | ProtectedTokenCodec |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | BAS-001 |
| 建议分支 | `md2word/TR-402` |
| Trellis 子任务 slug | `tr-402-protected-token-codec` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-402
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（BAS-001）的基线分支。若分支已存在，使用 `git switch md2word/TR-402`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-402：ProtectedTokenCodec** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-402`
发布阶段：`R4（翻译完整性）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-402-protected-token-codec`

## 本任务目标

实现数字、单位、地址、位字段、信号、型号和公式的 collision-safe 编码/解码。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-402 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-402 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-402 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/translation/protected_tokens.py`
   - `app/domains/translation/models.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义可扩展 token 分类和检测顺序。
- 生成批次内唯一占位符。
- 支持 roundtrip、缺失、重复、篡改检测。
- 避免过度保护普通自然语言。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 编码/解码必须纯函数且确定性。
- 原始技术文本必须字节/字符级恢复。
- 占位符不得与源文现有文本冲突。

## 明确范围外

- 调用模型。
- 术语后验检查。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-402：ProtectedTokenCodec**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-402`
发布阶段：`R4（翻译完整性）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-402-protected-token-codec`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现数字、单位、地址、位字段、信号、型号和公式的 collision-safe 编码/解码。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-402 为 `planning`；
   - 确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-402，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-402 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/translation/protected_tokens.py`
   - `app/domains/translation/models.py`
   - `tests/**`

必须交付：
- 定义可扩展 token 分类和检测顺序。
- 生成批次内唯一占位符。
- 支持 roundtrip、缺失、重复、篡改检测。
- 避免过度保护普通自然语言。

验收条件：
- 覆盖 `25°C`、`0x0028`、`[4:0]`、`VCC1_VCO`、公式、URL 和模型名。
- roundtrip 100%。
- collision 和恶意占位符测试通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 编码/解码必须纯函数且确定性。
- 原始技术文本必须字节/字符级恢复。
- 占位符不得与源文现有文本冲突。

## 明确范围外

- 调用模型。
- 术语后验检查。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-402 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-402：ProtectedTokenCodec** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-402`
依赖任务：BAS-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-402 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-403 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | TranslationIntegrityValidator |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | TR-402 |
| 建议分支 | `md2word/TR-403` |
| Trellis 子任务 slug | `tr-403-translation-integrity-validator` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-403
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TR-402）的基线分支。若分支已存在，使用 `git switch md2word/TR-403`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-403：TranslationIntegrityValidator** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-403`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-402
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-403-translation-integrity-validator`

## 本任务目标

在任何译文回填前验证 ID、占位符、数字、单位、地址、位字段、公式和型号完整性。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-403 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TR-402 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-403 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-403 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/translation/document_ir_translator.py`
   - `app/domains/translation/integrity.py`
   - `app/domains/translation/provider.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 把 codec metadata 与 provider result 对账。
- 输出稳定机器错误码和 batch evidence。
- 验证失败时不调用 apply_replacements。
- 记录审计摘要但不泄露全文。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 必须 fail-closed。
- 不得自动修复模型篡改。
- 一个失败 item 不能污染同批其他 replacement。

## 明确范围外

- 批次最终失败主任务语义。
- 目标语言检测。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-403：TranslationIntegrityValidator**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-403`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-402
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-403-translation-integrity-validator`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

在任何译文回填前验证 ID、占位符、数字、单位、地址、位字段、公式和型号完整性。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-403 为 `planning`；
   - 确认依赖 TR-402 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-403，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-403 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/translation/document_ir_translator.py`
   - `app/domains/translation/integrity.py`
   - `app/domains/translation/provider.py`
   - `tests/**`

必须交付：
- 把 codec metadata 与 provider result 对账。
- 输出稳定机器错误码和 batch evidence。
- 验证失败时不调用 apply_replacements。
- 记录审计摘要但不泄露全文。

验收条件：
- 所有故意改 Token/数字/单位/公式的 fake response 被拒绝。
- 正常响应通过。
- 失败批次可重试但不回填。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 必须 fail-closed。
- 不得自动修复模型篡改。
- 一个失败 item 不能污染同批其他 replacement。

## 明确范围外

- 批次最终失败主任务语义。
- 目标语言检测。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-403 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-403：TranslationIntegrityValidator** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-403`
依赖任务：TR-402

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-403 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-404 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | TableContextBuilder |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | TAB-301 |
| 建议分支 | `md2word/TR-404` |
| Trellis 子任务 slug | `tr-404-table-context-builder` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-404
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-301）的基线分支。若分支已存在，使用 `git switch md2word/TR-404`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-404：TableContextBuilder** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-404`
发布阶段：`R4（翻译完整性）`
依赖任务：TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-404-table-context-builder`

## 本任务目标

为表格短文本提供 section、table、row、column 和 group context，同时保持输出合同只含 ID/text。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-404 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-404 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-404 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/tables/**`
   - `app/domains/translation/models.py`
   - `app/domains/translation/document_ir_translator.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 基于 CanonicalTableGrid 提取行/列标题和最近分组。
- context 有严格字符预算。
- 短文本优先注入。
- provider 输出和回填不包含 context。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- context 只读，不可改变结构。
- 不得把整张大表重复注入每个 item。
- 不得包含内部路径或无关全文。

## 明确范围外

- 改变翻译 Prompt 输出 schema。
- 实现术语 QA。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-404：TableContextBuilder**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-404`
发布阶段：`R4（翻译完整性）`
依赖任务：TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-404-table-context-builder`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

为表格短文本提供 section、table、row、column 和 group context，同时保持输出合同只含 ID/text。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-404 为 `planning`；
   - 确认依赖 TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-404，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-404 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/tables/**`
   - `app/domains/translation/models.py`
   - `app/domains/translation/document_ir_translator.py`
   - `tests/**`

必须交付：
- 基于 CanonicalTableGrid 提取行/列标题和最近分组。
- context 有严格字符预算。
- 短文本优先注入。
- provider 输出和回填不包含 context。

验收条件：
- `Typical/Reserved/Output` 等短单元格获得正确上下文。
- 字符预算和缺失标题降级测试通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- context 只读，不可改变结构。
- 不得把整张大表重复注入每个 item。
- 不得包含内部路径或无关全文。

## 明确范围外

- 改变翻译 Prompt 输出 schema。
- 实现术语 QA。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-404 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-404：TableContextBuilder** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-404`
依赖任务：TAB-301

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-404 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-405 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 术语和目标语言后验检查 |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | TR-403 |
| 建议分支 | `md2word/TR-405` |
| Trellis 子任务 slug | `tr-405-term-language-post-validation` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-405
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TR-403）的基线分支。若分支已存在，使用 `git switch md2word/TR-405`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-405：术语和目标语言后验检查** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-405`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-403
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-405-term-language-post-validation`

## 本任务目标

对 mandatory term、forbidden term、目标语言和源语言残留进行后验 QA。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-405 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TR-403 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-405 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-405 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/translation/**`
   - `app/domains/document_jobs/**`
   - `resources/term_rules/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 检查注入术语是否按规则输出。
- 检测 forbidden translation。
- 检测大段源语言残留和错误目标语言。
- 生成 item/batch/job 级 QA flags。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得因专有名词、信号名和受保护 Token 误报源语言残留。
- 后验检查不得修改译文。
- 规则版本必须来自任务快照。

## 明确范围外

- 新增翻译语言。
- 调用第二模型自动改译文。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-405：术语和目标语言后验检查**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-405`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-403
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-405-term-language-post-validation`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

对 mandatory term、forbidden term、目标语言和源语言残留进行后验 QA。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-405 为 `planning`；
   - 确认依赖 TR-403 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-405，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-405 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/translation/**`
   - `app/domains/document_jobs/**`
   - `resources/term_rules/**`
   - `tests/**`

必须交付：
- 检查注入术语是否按规则输出。
- 检测 forbidden translation。
- 检测大段源语言残留和错误目标语言。
- 生成 item/batch/job 级 QA flags。

验收条件：
- mandatory/forbidden/混合语言正负测试通过。
- 四语言方向规则可配置。
- QA evidence 可审计。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得因专有名词、信号名和受保护 Token 误报源语言残留。
- 后验检查不得修改译文。
- 规则版本必须来自任务快照。

## 明确范围外

- 新增翻译语言。
- 调用第二模型自动改译文。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-405 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-405：术语和目标语言后验检查** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-405`
依赖任务：TR-403

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-405 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-406 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 部分批次失败语义收口 |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | TR-403、CON-102 |
| 建议分支 | `md2word/TR-406` |
| Trellis 子任务 slug | `tr-406-partial-batch-failure-semantics` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-406
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TR-403、CON-102）的基线分支。若分支已存在，使用 `git switch md2word/TR-406`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-406：部分批次失败语义收口** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-406`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-403、CON-102
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-406-partial-batch-failure-semantics`

## 本任务目标

保证任一叶子翻译批次最终失败时，不产生静默混合语言可交付件。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-406 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TR-403、CON-102 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-406 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-406 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/translation/**`
   - `frontend/src/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义批次 split/retry/terminal failure 与主任务状态关系。
- partial artifact 仅用于 debug。
- generation/retry_count 一致。
- 事件和 UI 显示明确失败/阻塞原因。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得自动回退 direct。
- 不得用源文填充失败 item 后标记成功。
- 旧 generation 结果不得覆盖新 generation。

## 明确范围外

- 重写队列系统。
- 增加真实外部 Provider 测试。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-406：部分批次失败语义收口**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-406`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-403、CON-102
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-406-partial-batch-failure-semantics`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

保证任一叶子翻译批次最终失败时，不产生静默混合语言可交付件。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-406 为 `planning`；
   - 确认依赖 TR-403、CON-102 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-406，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-406 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/execution.py`
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/translation/**`
   - `frontend/src/**`
   - `tests/**`

必须交付：
- 定义批次 split/retry/terminal failure 与主任务状态关系。
- partial artifact 仅用于 debug。
- generation/retry_count 一致。
- 事件和 UI 显示明确失败/阻塞原因。

验收条件：
- 截断、429、超时、缺 ID、Token 篡改和叶子失败路径测试通过。
- 混合语言结果无法下载为正式产物。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得自动回退 direct。
- 不得用源文填充失败 item 后标记成功。
- 旧 generation 结果不得覆盖新 generation。

## 明确范围外

- 重写队列系统。
- 增加真实外部 Provider 测试。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <preflight 中确认的本任务定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-406 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-406：部分批次失败语义收口** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-406`
依赖任务：TR-403、CON-102

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-406 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# TR-407 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 四语言方向样本和门禁 |
| 阶段 | R4 · 翻译完整性 |
| 依赖 | TR-401、TR-402、TR-403、TR-404、TR-405、TR-406 |
| 建议分支 | `md2word/TR-407` |
| Trellis 子任务 slug | `tr-407-four-language-regression-gates` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/TR-407
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TR-401、TR-402、TR-403、TR-404、TR-405、TR-406）的基线分支。若分支已存在，使用 `git switch md2word/TR-407`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **TR-407：四语言方向样本和门禁** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-407`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-401、TR-402、TR-403、TR-404、TR-405、TR-406
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-407-four-language-regression-gates`

## 本任务目标

分别建立 en2zh、ru2zh、zh2en、zh2ru 样本、脚本、自动证据和人工验收记录。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-407 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TR-401、TR-402、TR-403、TR-404、TR-405、TR-406 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 TR-407 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 TR-407 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `tests/fixtures/translation_samples/**`
   - `scripts/ops/run_p1_translation_regression.py`
   - `scripts/dev/run_local_mineru_quality_matrix.py`
   - `docs/engineering/testing-acceptance-strategy.md`

## 规划必须覆盖的交付物

- 每个方向覆盖正文、列表、表格、caption、footnote、单位、公式、地址和位字段。
- CI 使用 fake provider 或固定录制响应。
- 提供人工技术语言质量记录模板。
- 门禁按语言方向独立发布。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 一种方向通过不得代表其他方向通过。
- 不得在 CI 使用真实外部模型。
- 不得提交敏感全文。

## 明确范围外

- 新增语言方向。
- 优化模型 Prompt 内容之外的产品范围。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **TR-407：四语言方向样本和门禁**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-407`
发布阶段：`R4（翻译完整性）`
依赖任务：TR-401、TR-402、TR-403、TR-404、TR-405、TR-406
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`tr-407-four-language-regression-gates`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

分别建立 en2zh、ru2zh、zh2en、zh2ru 样本、脚本、自动证据和人工验收记录。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 TR-407 为 `planning`；
   - 确认依赖 TR-401、TR-402、TR-403、TR-404、TR-405、TR-406 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/translation-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/implementation/rollout-and-migration.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 TR-407，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 TR-407 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `tests/fixtures/translation_samples/**`
   - `scripts/ops/run_p1_translation_regression.py`
   - `scripts/dev/run_local_mineru_quality_matrix.py`
   - `docs/engineering/testing-acceptance-strategy.md`

必须交付：
- 每个方向覆盖正文、列表、表格、caption、footnote、单位、公式、地址和位字段。
- CI 使用 fake provider 或固定录制响应。
- 提供人工技术语言质量记录模板。
- 门禁按语言方向独立发布。

验收条件：
- 四个 manifest 可独立运行。
- 技术 Token/结构门禁通过。
- 人工验收状态可追溯。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 一种方向通过不得代表其他方向通过。
- 不得在 CI 使用真实外部模型。
- 不得提交敏感全文。

## 明确范围外

- 新增语言方向。
- 优化模型 Prompt 内容之外的产品范围。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 translation/fake-provider 定向测试模块>`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`
- 按任务涉及方向运行 `run_local_mineru_quality_matrix.py --mode <mode> --sample-set translation-core`（样本存在时）。
- 必须包含缺失 ID、额外 ID、Token 被修改、批次失败等负向测试；不得调用真实外部模型作为普通 CI。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 TR-407 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **TR-407：四语言方向样本和门禁** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/TR-407`
依赖任务：TR-401、TR-402、TR-403、TR-404、TR-405、TR-406

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 TR-407 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-501 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | RenderPlan 与 block evidence |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | IR-205、TAB-301 |
| 建议分支 | `md2word/RND-501` |
| Trellis 子任务 slug | `rnd-501-render-plan-block-evidence` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-501
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-205、TAB-301）的基线分支。若分支已存在，使用 `git switch md2word/RND-501`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-501：RenderPlan 与 block evidence** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-501`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：IR-205、TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-501-render-plan-block-evidence`

## 本任务目标

显式记录 section/block 渲染决策和 block→Word evidence，为预览、QA 和定位提供稳定合同。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-501 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-205、TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-501 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-501 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/layout_plan.py`
   - `app/services/renderer/evidence.py`
   - `app/services/renderer/word_renderer.py`
   - `app/services/document_ir/models.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 RenderPlan/RenderDecision。
- 记录样式、section、方向、表格/图片策略、bookmark/anchor。
- 输出独立 evidence artifact 或 renderer metadata。
- 保证 block ID 可追踪。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- DocumentIR 不应被 Word 专有对象污染。
- 渲染计划不得改变内容语义。
- evidence 不得暴露内部路径。

## 明确范围外

- 实现 Word preview。
- 实现三栏 UI。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-501：RenderPlan 与 block evidence**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-501`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：IR-205、TAB-301
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-501-render-plan-block-evidence`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

显式记录 section/block 渲染决策和 block→Word evidence，为预览、QA 和定位提供稳定合同。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-501 为 `planning`；
   - 确认依赖 IR-205、TAB-301 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-501，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-501 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/layout_plan.py`
   - `app/services/renderer/evidence.py`
   - `app/services/renderer/word_renderer.py`
   - `app/services/document_ir/models.py`
   - `tests/**`

必须交付：
- 定义 RenderPlan/RenderDecision。
- 记录样式、section、方向、表格/图片策略、bookmark/anchor。
- 输出独立 evidence artifact 或 renderer metadata。
- 保证 block ID 可追踪。

验收条件：
- 同一 IR+模板输出稳定决策。
- 主要 block 均有 evidence。
- 旧 renderer 输出不回归。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- DocumentIR 不应被 Word 专有对象污染。
- 渲染计划不得改变内容语义。
- evidence 不得暴露内部路径。

## 明确范围外

- 实现 Word preview。
- 实现三栏 UI。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-501 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-501：RenderPlan 与 block evidence** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-501`
依赖任务：IR-205、TAB-301

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-501 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-502 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 公式 OMML 和降级规则 |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | BAS-001 |
| 建议分支 | `md2word/RND-502` |
| Trellis 子任务 slug | `rnd-502-formula-omml-fallback` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-502
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（BAS-001）的基线分支。若分支已存在，使用 `git switch md2word/RND-502`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-502：公式 OMML 和降级规则** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-502`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-502-formula-omml-fallback`

## 本任务目标

统一 inline、block 和 table formula 的 OMML 渲染及明确降级规则。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-502 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-502 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-502 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/text_renderer.py`
   - `app/services/renderer/table_renderer.py`
   - `app/services/renderer/semantic_text.py`
   - `app/conversion/docx_rules/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 统一 LaTeX/semantic formula 解析入口。
- 可转换公式输出 OMML。
- 无法转换时使用受控文本或图片降级并生成 flag。
- 消除静默 LaTeX 残留。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 公式内容不得被翻译或改值。
- 降级必须可见、可审计。
- 不得因失败删除公式。

## 明确范围外

- 实现全功能数学排版引擎。
- 改变翻译 Token 规则。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-502：公式 OMML 和降级规则**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-502`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：BAS-001
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-502-formula-omml-fallback`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

统一 inline、block 和 table formula 的 OMML 渲染及明确降级规则。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-502 为 `planning`；
   - 确认依赖 BAS-001 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-502，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-502 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/text_renderer.py`
   - `app/services/renderer/table_renderer.py`
   - `app/services/renderer/semantic_text.py`
   - `app/conversion/docx_rules/**`
   - `tests/**`

必须交付：
- 统一 LaTeX/semantic formula 解析入口。
- 可转换公式输出 OMML。
- 无法转换时使用受控文本或图片降级并生成 flag。
- 消除静默 LaTeX 残留。

验收条件：
- inline/block/table 公式正负测试通过。
- DOCX quality 不出现未解释 LaTeX residue。
- Microsoft Word 人工检查项明确。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 公式内容不得被翻译或改值。
- 降级必须可见、可审计。
- 不得因失败删除公式。

## 明确范围外

- 实现全功能数学排版引擎。
- 改变翻译 Token 规则。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-502 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-502：公式 OMML 和降级规则** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-502`
依赖任务：BAS-001

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-502 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-503 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 图片并排和 Caption |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | IR-204 |
| 建议分支 | `md2word/RND-503` |
| Trellis 子任务 slug | `rnd-503-image-group-caption-rendering` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-503
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（IR-204）的基线分支。若分支已存在，使用 `git switch md2word/RND-503`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-503：图片并排和 Caption** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-503`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：IR-204
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-503-image-group-caption-rendering`

## 本任务目标

基于 bbox 严格识别同一行图片组，用无边框布局表格渲染并保持 caption 绑定。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-503 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 IR-204 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-503 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-503 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/image_renderer.py`
   - `app/services/renderer/layout_plan.py`
   - `app/services/renderer/word_renderer.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义图片组判定阈值和 evidence。
- 并排图使用无边框 Word 布局表格。
- 保持宽高比和行内对象。
- caption/footnote 在正确图片下方。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不确定时按单图顺序渲染并标记，不强制并排。
- 不得使用浮动文本框模拟整页。
- 图片内部文字不翻译。

## 明确范围外

- 重绘图表。
- 图像 OCR。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-503：图片并排和 Caption**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-503`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：IR-204
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-503-image-group-caption-rendering`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

基于 bbox 严格识别同一行图片组，用无边框布局表格渲染并保持 caption 绑定。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-503 为 `planning`；
   - 确认依赖 IR-204 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-503，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-503 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/image_renderer.py`
   - `app/services/renderer/layout_plan.py`
   - `app/services/renderer/word_renderer.py`
   - `tests/**`

必须交付：
- 定义图片组判定阈值和 evidence。
- 并排图使用无边框 Word 布局表格。
- 保持宽高比和行内对象。
- caption/footnote 在正确图片下方。

验收条件：
- ZK7044 图 5/6、图 24/25 和普通单图通过。
- 不同 Word/预览下不明显漂移。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不确定时按单图顺序渲染并标记，不强制并排。
- 不得使用浮动文本框模拟整页。
- 图片内部文字不翻译。

## 明确范围外

- 重绘图表。
- 图像 OCR。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-503 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-503：图片并排和 Caption** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-503`
依赖任务：IR-204

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-503 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-504 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | WordPreviewProvider |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | CON-103 |
| 建议分支 | `md2word/RND-504` |
| Trellis 子任务 slug | `rnd-504-word-preview-provider` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-504
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（CON-103）的基线分支。若分支已存在，使用 `git switch md2word/RND-504`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-504：WordPreviewProvider** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-504`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-504-word-preview-provider`

## 本任务目标

实现可替换的 DOCX→PDF/页面图 Provider，并把预览结果登记为 Artifact。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-504 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-504 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-504 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/preview/**`
   - `app/domains/files/**`
   - `app/domains/document_jobs/execution.py`
   - `app/core/config.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 PreviewProvider port、fake adapter 和生产 adapter 配置边界。
- 支持超时、沙箱、重试、资源限制和错误码。
- 登记 preview PDF/pages artifact。
- 预览失败不删除 DOCX，但质量 blocked/禁止发布。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- Provider 不得进入 DocumentIR 语义。
- 不得执行不受控 shell/宏。
- 不得把预览服务暴露为匿名文件服务器。

## 明确范围外

- 实现页面映射。
- 在本任务中选择或采购外部 SaaS。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 生产预览引擎需要未批准的新系统依赖且无法用 port/fake 完成时停止。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-504：WordPreviewProvider**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-504`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-504-word-preview-provider`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现可替换的 DOCX→PDF/页面图 Provider，并把预览结果登记为 Artifact。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-504 为 `planning`；
   - 确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-504，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-504 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/preview/**`
   - `app/domains/files/**`
   - `app/domains/document_jobs/execution.py`
   - `app/core/config.py`
   - `tests/**`

必须交付：
- 定义 PreviewProvider port、fake adapter 和生产 adapter 配置边界。
- 支持超时、沙箱、重试、资源限制和错误码。
- 登记 preview PDF/pages artifact。
- 预览失败不删除 DOCX，但质量 blocked/禁止发布。

验收条件：
- fake provider 组件测试通过。
- 超时/损坏 DOCX/空输出失败关闭。
- 文件保留和权限正确。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- Provider 不得进入 DocumentIR 语义。
- 不得执行不受控 shell/宏。
- 不得把预览服务暴露为匿名文件服务器。

## 明确范围外

- 实现页面映射。
- 在本任务中选择或采购外部 SaaS。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 生产预览引擎需要未批准的新系统依赖且无法用 port/fake 完成时停止。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-504 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-504：WordPreviewProvider** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-504`
依赖任务：CON-103

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-504 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-505 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | PDF/IR/Word 页映射 |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | RND-501、RND-504 |
| 建议分支 | `md2word/RND-505` |
| Trellis 子任务 slug | `rnd-505-pdf-ir-word-page-mapping` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-505
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（RND-501、RND-504）的基线分支。若分支已存在，使用 `git switch md2word/RND-505`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-505：PDF/IR/Word 页映射** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-505`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：RND-501、RND-504
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-505-pdf-ir-word-page-mapping`

## 本任务目标

建立源 PDF span、DocumentIR block、Word anchor 和 preview page 的可降级映射。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-505 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 RND-501、RND-504 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-505 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-505 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/evidence.py`
   - `app/services/preview/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 为输出 block 生成 bookmark/anchor。
- 从 preview 提取或推断 Word page mapping。
- 映射 artifact 记录 source spans。
- 映射失败降级到最近页并标记 confidence。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得承诺像素级一一分页。
- 稳定 ID 必须贯穿。
- 映射失败不得改变内容或发布条件之外的状态。

## 明确范围外

- 实现前端三栏交互。
- 修改源 PDF。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-505：PDF/IR/Word 页映射**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-505`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：RND-501、RND-504
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-505-pdf-ir-word-page-mapping`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

建立源 PDF span、DocumentIR block、Word anchor 和 preview page 的可降级映射。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-505 为 `planning`；
   - 确认依赖 RND-501、RND-504 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-505，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-505 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/evidence.py`
   - `app/services/preview/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

必须交付：
- 为输出 block 生成 bookmark/anchor。
- 从 preview 提取或推断 Word page mapping。
- 映射 artifact 记录 source spans。
- 映射失败降级到最近页并标记 confidence。

验收条件：
- 段落、跨页段落、表格 fragment 和图片可定位。
- 最近页降级和低置信度测试通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得承诺像素级一一分页。
- 稳定 ID 必须贯穿。
- 映射失败不得改变内容或发布条件之外的状态。

## 明确范围外

- 实现前端三栏交互。
- 修改源 PDF。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-505 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-505：PDF/IR/Word 页映射** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-505`
依赖任务：RND-501、RND-504

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-505 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# RND-506 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 页级 DOCX 质量检查 |
| 阶段 | R5 · DOCX、模板和预览 |
| 依赖 | RND-504、RND-505 |
| 建议分支 | `md2word/RND-506` |
| Trellis 子任务 slug | `rnd-506-page-level-docx-quality` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/RND-506
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（RND-504、RND-505）的基线分支。若分支已存在，使用 `git switch md2word/RND-506`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **RND-506：页级 DOCX 质量检查** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-506`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：RND-504、RND-505
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-506-page-level-docx-quality`

## 本任务目标

基于 Word preview 检测裁切、溢出、异常空白页、重叠和页面密度异常。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-506 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 RND-504、RND-505 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 RND-506 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 RND-506 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/services/renderer/docx_quality.py`
   - `app/services/preview/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义 page-level metrics 和 flags。
- 关联 block/page mapping。
- 聚合为 quality run。
- 区分 blocker、warning 和人工检查项。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 视觉规则只标记，不修改文档。
- 不得用像素相似度作为唯一通过标准。
- 阈值必须可配置且有样本证据。

## 明确范围外

- 实现浏览器预览 UI。
- 使用 OCR 重新解析 Word。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **RND-506：页级 DOCX 质量检查**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-506`
发布阶段：`R5（DOCX、模板和预览）`
依赖任务：RND-504、RND-505
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rnd-506-page-level-docx-quality`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

基于 Word preview 检测裁切、溢出、异常空白页、重叠和页面密度异常。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 RND-506 为 `planning`；
   - 确认依赖 RND-504、RND-505 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/contracts/document-ir-contract.md`
   - `docs/design/docx-rendering-template-design.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 RND-506，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 RND-506 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/services/renderer/docx_quality.py`
   - `app/services/preview/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

必须交付：
- 定义 page-level metrics 和 flags。
- 关联 block/page mapping。
- 聚合为 quality run。
- 区分 blocker、warning 和人工检查项。

验收条件：
- 合成裁切/空白/溢出负例可检测。
- 正常 Golden 不误阻断。
- 质量报告包含页码和 evidence。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 视觉规则只标记，不修改文档。
- 不得用像素相似度作为唯一通过标准。
- 阈值必须可配置且有样本证据。

## 明确范围外

- 实现浏览器预览 UI。
- 使用 OCR 重新解析 Word。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 renderer/evidence/preview 定向测试模块>`
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- 检查 DOCX OOXML、预览 Artifact 和质量 evidence；如需 Microsoft Word 人工验收，明确记录为待人工项。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 RND-506 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **RND-506：页级 DOCX 质量检查** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/RND-506`
依赖任务：RND-504、RND-505

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 RND-506 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-601 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 统一 Review 模型 |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | CON-103 |
| 建议分支 | `md2word/QA-601` |
| Trellis 子任务 slug | `qa-601-unified-document-review` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-601
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（CON-103）的基线分支。若分支已存在，使用 `git switch md2word/QA-601`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-601：统一 Review 模型** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-601`
发布阶段：`R6（审核、批准和发布）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-601-unified-document-review`

## 本任务目标

将现有 translation QA 兼容演进为 direct/translation 共用、append-only 的 Document Review 模型。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-601 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-601 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-601 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/service.py`
   - `app/infrastructure/persistence/**`
   - `frontend/src/**`
   - `tests/**`

## 规划必须覆盖的交付物

- 新增 ReviewRecord 表/模型和迁移。
- 旧 translation QA 映射到统一 review。
- review 绑定 result file/hash。
- 结果变化使旧批准失效。
- blocked 不能 approved。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 旧字段过渡期保留。
- 不得从历史 Golden signoff 自动创建发布。
- ReviewRecord 不可原地覆盖历史记录。

## 明确范围外

- 实现三栏 UI。
- 实现 PublicationRecord。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-601：统一 Review 模型**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-601`
发布阶段：`R6（审核、批准和发布）`
依赖任务：CON-103
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-601-unified-document-review`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

将现有 translation QA 兼容演进为 direct/translation 共用、append-only 的 Document Review 模型。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-601 为 `planning`；
   - 确认依赖 CON-103 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-601，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-601 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/service.py`
   - `app/infrastructure/persistence/**`
   - `frontend/src/**`
   - `tests/**`

必须交付：
- 新增 ReviewRecord 表/模型和迁移。
- 旧 translation QA 映射到统一 review。
- review 绑定 result file/hash。
- 结果变化使旧批准失效。
- blocked 不能 approved。

验收条件：
- direct/translation review API 兼容。
- 迁移/backfill 测试通过。
- hash 变化和 blocked negative test 通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 旧字段过渡期保留。
- 不得从历史 Golden signoff 自动创建发布。
- ReviewRecord 不可原地覆盖历史记录。

## 明确范围外

- 实现三栏 UI。
- 实现 PublicationRecord。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-601 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-601：统一 Review 模型** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-601`
依赖任务：CON-103

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-601 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-602 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Quality/Review API |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | QA-601、TAB-307、RND-506 |
| 建议分支 | `md2word/QA-602` |
| Trellis 子任务 slug | `qa-602-quality-review-api` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-602
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（QA-601、TAB-307、RND-506）的基线分支。若分支已存在，使用 `git switch md2word/QA-602`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-602：Quality/Review API** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-602`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-601、TAB-307、RND-506
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-602-quality-review-api`

## 本任务目标

提供任务质量、表格 evidence、预览、review 查询和 review 更新的权限化 API。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-602 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 QA-601、TAB-307、RND-506 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-602 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-602 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/schemas.py`
   - `app/api/v1/router.py`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 定义 quality summary/detail、preview metadata、review history/update endpoints。
- owner/admin 权限。
- 稳定分页/错误码。
- 旧 translation QA 路由兼容或明确 deprecated。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- API 不提供内容编辑。
- 不得返回内部对象路径或敏感全文。
- 后端权威校验 blocked/approved 规则。

## 明确范围外

- 实现前端页面。
- 实现发布。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-602：Quality/Review API**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-602`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-601、TAB-307、RND-506
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-602-quality-review-api`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

提供任务质量、表格 evidence、预览、review 查询和 review 更新的权限化 API。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-602 为 `planning`；
   - 确认依赖 QA-601、TAB-307、RND-506 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-602，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-602 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/schemas.py`
   - `app/api/v1/router.py`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 定义 quality summary/detail、preview metadata、review history/update endpoints。
- owner/admin 权限。
- 稳定分页/错误码。
- 旧 translation QA 路由兼容或明确 deprecated。

验收条件：
- OpenAPI 快照更新。
- 权限、404、冲突和 hash 失效测试通过。
- 前端可只依赖新合同。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- API 不提供内容编辑。
- 不得返回内部对象路径或敏感全文。
- 后端权威校验 blocked/approved 规则。

## 明确范围外

- 实现前端页面。
- 实现发布。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-602 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-602：Quality/Review API** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-602`
依赖任务：QA-601、TAB-307、RND-506

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-602 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-603 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 三栏审核页面 |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | QA-602、RND-505 |
| 建议分支 | `md2word/QA-603` |
| Trellis 子任务 slug | `qa-603-three-panel-review-ui` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-603
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（QA-602、RND-505）的基线分支。若分支已存在，使用 `git switch md2word/QA-603`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-603：三栏审核页面** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-603`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-602、RND-505
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-603-three-panel-review-ui`

## 本任务目标

实现 PDF、内容证据和 Word preview 的只读同步审核页面。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-603 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 QA-602、RND-505 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-603 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/architecture/system-architecture.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-603 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `frontend/src/**/review/**`
   - `frontend/src/pages/**`
   - `frontend/src/api/**`
   - `frontend/tests/**`

## 规划必须覆盖的交付物

- 三栏布局、页码导航、问题筛选和状态保存。
- 点击 block 同步 PDF bbox、内容证据和 Word page。
- 展示表格 reference、raw HTML 摘要、术语和 Token evidence。
- 支持 direct 与 translation。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 页面只读，不实现在线 Word/译文/表格编辑。
- 不维护第二套状态机。
- URL/query state 可恢复。
- 必须支持键盘和基础可访问性。

## 明确范围外

- Publication UI。
- 复杂富文本编辑器。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-603：三栏审核页面**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-603`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-602、RND-505
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-603-three-panel-review-ui`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现 PDF、内容证据和 Word preview 的只读同步审核页面。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-603 为 `planning`；
   - 确认依赖 QA-602、RND-505 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/architecture/system-architecture.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-603，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-603 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `frontend/src/**/review/**`
   - `frontend/src/pages/**`
   - `frontend/src/api/**`
   - `frontend/tests/**`

必须交付：
- 三栏布局、页码导航、问题筛选和状态保存。
- 点击 block 同步 PDF bbox、内容证据和 Word page。
- 展示表格 reference、raw HTML 摘要、术语和 Token evidence。
- 支持 direct 与 translation。

验收条件：
- 核心组件 unit、build 和 Playwright smoke 通过。
- 映射失败有降级提示。
- operator/admin 权限正确。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 页面只读，不实现在线 Word/译文/表格编辑。
- 不维护第二套状态机。
- URL/query state 可恢复。
- 必须支持键盘和基础可访问性。

## 明确范围外

- Publication UI。
- 复杂富文本编辑器。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-603 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-603：三栏审核页面** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-603`
依赖任务：QA-602、RND-505

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-603 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-604 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 下载状态提示 |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | CON-104、QA-602 |
| 建议分支 | `md2word/QA-604` |
| Trellis 子任务 slug | `qa-604-download-status-warning` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-604
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（CON-104、QA-602）的基线分支。若分支已存在，使用 `git switch md2word/QA-604`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-604：下载状态提示** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-604`
发布阶段：`R6（审核、批准和发布）`
依赖任务：CON-104、QA-602
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-604-download-status-warning`

## 本任务目标

为 blocked 和 unreviewed DOCX 提供醒目但不妨碍内部下载的确认与状态标识。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-604 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 CON-104、QA-602 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-604 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-604 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `frontend/src/**`
   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/schemas.py`
   - `tests/**`

## 规划必须覆盖的交付物

- 下载按钮展示状态标签和 warning。
- blocked 显示“质量阻塞，不可交付”。
- unreviewed 翻译显示“未复核”。
- 确认后仍可下载；publish 入口禁用。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得给 DOCX 强制加水印。
- 不得把 blocked 当作执行失败隐藏下载。
- 不得由前端重算资格。

## 明确范围外

- 实现发布功能。
- 修改 DOCX 内容。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-604：下载状态提示**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-604`
发布阶段：`R6（审核、批准和发布）`
依赖任务：CON-104、QA-602
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-604-download-status-warning`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

为 blocked 和 unreviewed DOCX 提供醒目但不妨碍内部下载的确认与状态标识。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-604 为 `planning`；
   - 确认依赖 CON-104、QA-602 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-604，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-604 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `frontend/src/**`
   - `app/domains/document_jobs/router.py`
   - `app/domains/document_jobs/schemas.py`
   - `tests/**`

必须交付：
- 下载按钮展示状态标签和 warning。
- blocked 显示“质量阻塞，不可交付”。
- unreviewed 翻译显示“未复核”。
- 确认后仍可下载；publish 入口禁用。

验收条件：
- 两类确认流程 unit/E2E 通过。
- 下载审计仍记录。
- 普通 approved 文档无多余阻断。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得给 DOCX 强制加水印。
- 不得把 blocked 当作执行失败隐藏下载。
- 不得由前端重算资格。

## 明确范围外

- 实现发布功能。
- 修改 DOCX 内容。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-604 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-604：下载状态提示** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-604`
依赖任务：CON-104、QA-602

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-604 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-605 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | PublicationRecord 和发布门禁 |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | QA-601、RND-504 |
| 建议分支 | `md2word/QA-605` |
| Trellis 子任务 slug | `qa-605-publication-record-gate` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-605
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（QA-601、RND-504）的基线分支。若分支已存在，使用 `git switch md2word/QA-605`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-605：PublicationRecord 和发布门禁** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-605`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-601、RND-504
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-605-publication-record-gate`

## 本任务目标

实现不可变、Admin-only 的文档 PublicationRecord，并绑定具体结果文件、哈希和配置快照。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-605 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 QA-601、RND-504 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-605 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-605 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/router.py`
   - `app/infrastructure/persistence/**`
   - `tests/**`
   - `docs/api/**`

## 规划必须覆盖的交付物

- 新增 publication 表/模型/迁移。
- 发布前校验 execution succeeded、quality non-blocked、review approved、preview available、hash 一致。
- 发布记录保存源/结果/模板/规则/Prompt/术语/model 快照。
- 已发布文件不可覆盖。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只有 Admin 可发布。
- 同一 result_file/checksum 不得重复或被覆盖发布。
- 新 generation 必须重新 review/publish。
- 迁移 additive。

## 明确范围外

- 实现发布前端。
- 自动上传人工修改 Word。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要覆盖历史发布文件或删除历史结果时停止。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-605：PublicationRecord 和发布门禁**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-605`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-601、RND-504
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-605-publication-record-gate`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现不可变、Admin-only 的文档 PublicationRecord，并绑定具体结果文件、哈希和配置快照。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-605 为 `planning`；
   - 确认依赖 QA-601、RND-504 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-605，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-605 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/document_jobs/models.py`
   - `app/domains/document_jobs/repository.py`
   - `app/domains/document_jobs/service.py`
   - `app/domains/document_jobs/router.py`
   - `app/infrastructure/persistence/**`
   - `tests/**`
   - `docs/api/**`

必须交付：
- 新增 publication 表/模型/迁移。
- 发布前校验 execution succeeded、quality non-blocked、review approved、preview available、hash 一致。
- 发布记录保存源/结果/模板/规则/Prompt/术语/model 快照。
- 已发布文件不可覆盖。

验收条件：
- publish 正负、唯一约束、并发和权限测试通过。
- 历史任务不自动发布。
- OpenAPI/审计合同更新。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 只有 Admin 可发布。
- 同一 result_file/checksum 不得重复或被覆盖发布。
- 新 generation 必须重新 review/publish。
- 迁移 additive。

## 明确范围外

- 实现发布前端。
- 自动上传人工修改 Word。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要覆盖历史发布文件或删除历史结果时停止。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-605 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-605：PublicationRecord 和发布门禁** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-605`
依赖任务：QA-601、RND-504

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-605 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-606 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 发布 UI 与审计 |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | QA-605 |
| 建议分支 | `md2word/QA-606` |
| Trellis 子任务 slug | `qa-606-publication-ui-audit` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-606
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（QA-605）的基线分支。若分支已存在，使用 `git switch md2word/QA-606`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-606：发布 UI 与审计** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-606`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-605
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-606-publication-ui-audit`

## 本任务目标

实现发布原因、前置检查、Publication 列表、最终下载入口和完整审计 UI。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-606 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 QA-605 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-606 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-606 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `frontend/src/**`
   - `app/domains/audit/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

## 规划必须覆盖的交付物

- Admin 发布弹窗展示前置检查与禁用原因。
- 发布原因必填。
- 展示不可变 PublicationRecord 列表。
- 最终交付件下载与内部草稿下载明确区分。
- 写入审计事件。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- UI 不得绕过后端门禁。
- Operator 不显示可执行发布动作。
- 审计不得包含敏感全文。

## 明确范围外

- 重新生成发布文件。
- 外部客户门户。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-606：发布 UI 与审计**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-606`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-605
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-606-publication-ui-audit`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

实现发布原因、前置检查、Publication 列表、最终下载入口和完整审计 UI。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-606 为 `planning`；
   - 确认依赖 QA-605 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-606，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-606 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `frontend/src/**`
   - `app/domains/audit/**`
   - `app/domains/document_jobs/**`
   - `tests/**`

必须交付：
- Admin 发布弹窗展示前置检查与禁用原因。
- 发布原因必填。
- 展示不可变 PublicationRecord 列表。
- 最终交付件下载与内部草稿下载明确区分。
- 写入审计事件。

验收条件：
- unit/build/Playwright 权限与发布流程通过。
- 审计事件字段和错误映射测试通过。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- UI 不得绕过后端门禁。
- Operator 不显示可执行发布动作。
- 审计不得包含敏感全文。

## 明确范围外

- 重新生成发布文件。
- 外部客户门户。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-606 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-606：发布 UI 与审计** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-606`
依赖任务：QA-605

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-606 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# QA-607 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 审核发布 E2E |
| 阶段 | R6 · 审核、批准和发布 |
| 依赖 | QA-603、QA-604、QA-605、QA-606 |
| 建议分支 | `md2word/QA-607` |
| Trellis 子任务 slug | `qa-607-review-publication-e2e` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/QA-607
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（QA-603、QA-604、QA-605、QA-606）的基线分支。若分支已存在，使用 `git switch md2word/QA-607`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **QA-607：审核发布 E2E** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-607`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-603、QA-604、QA-605、QA-606
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-607-review-publication-e2e`

## 本任务目标

建立覆盖未复核、质量阻塞、批准发布、结果失效和发布不可变的端到端门禁。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-607 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 QA-603、QA-604、QA-605、QA-606 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 QA-607 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 QA-607 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `frontend/tests/e2e/**`
   - `tests/**`
   - `scripts/ops/check_release.py`
   - `docs/engineering/testing-acceptance-strategy.md`

## 规划必须覆盖的交付物

- 场景 1：unreviewed translation 可下载不可发布。
- 场景 2：blocked table 可下载不可批准。
- 场景 3：approved warning 文档可发布。
- 场景 4：新结果使旧批准失效。
- 场景 5：published 文件不可覆盖。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 测试使用 fake provider/preview 和隔离数据库。
- 不得依赖真实外部 AI。
- E2E 不得通过直接改数据库绕过业务 API。

## 明确范围外

- 增加新的业务场景。
- 手工修 Word 回传。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **QA-607：审核发布 E2E**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-607`
发布阶段：`R6（审核、批准和发布）`
依赖任务：QA-603、QA-604、QA-605、QA-606
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`qa-607-review-publication-e2e`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

建立覆盖未复核、质量阻塞、批准发布、结果失效和发布不可变的端到端门禁。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 QA-607 为 `planning`；
   - 确认依赖 QA-603、QA-604、QA-605、QA-606 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/architecture/domain-model.md`
   - `docs/architecture/workflows-and-state-machines.md`
   - `docs/design/quality-review-release-design.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/engineering/testing-acceptance-strategy.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 QA-607，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 QA-607 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `frontend/tests/e2e/**`
   - `tests/**`
   - `scripts/ops/check_release.py`
   - `docs/engineering/testing-acceptance-strategy.md`

必须交付：
- 场景 1：unreviewed translation 可下载不可发布。
- 场景 2：blocked table 可下载不可批准。
- 场景 3：approved warning 文档可发布。
- 场景 4：新结果使旧批准失效。
- 场景 5：published 文件不可覆盖。

验收条件：
- 五个场景均有 API 和浏览器证据。
- 失败可定位。
- release check 集成。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 测试使用 fake provider/preview 和隔离数据库。
- 不得依赖真实外部 AI。
- E2E 不得通过直接改数据库绕过业务 API。

## 明确范围外

- 增加新的业务场景。
- 手工修 Word 回传。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python -m unittest <本任务的 repository/service/router/permission 定向测试模块>`
- `.venv/bin/python scripts/ops/check_release.py`
- `npm --prefix frontend run test:unit`（涉及前端时）。
- `npm --prefix frontend run build`（涉及前端时）。
- `npm --prefix frontend run test:smoke`（涉及审核/发布 E2E 时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 QA-607 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **QA-607：审核发布 E2E** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/QA-607`
依赖任务：QA-603、QA-604、QA-605、QA-606

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 QA-607 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# REL-701 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Release check 和 Acceptance gate |
| 阶段 | R7 · 发布收口 |
| 依赖 | TAB-308、TR-407、QA-607 |
| 建议分支 | `md2word/REL-701` |
| Trellis 子任务 slug | `rel-701-release-acceptance-gate` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/REL-701
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（TAB-308、TR-407、QA-607）的基线分支。若分支已存在，使用 `git switch md2word/REL-701`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **REL-701：Release check 和 Acceptance gate** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-701`
发布阶段：`R7（发布收口）`
依赖任务：TAB-308、TR-407、QA-607
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-701-release-acceptance-gate`

## 本任务目标

扩展发布检查，统一验证 schema、preview、quality/review/publish、表格和翻译门禁。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-701 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 TAB-308、TR-407、QA-607 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 REL-701 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 REL-701 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `scripts/ops/check_release.py`
   - `scripts/ops/run_golden_sample_regression.py`
   - `scripts/ops/run_p1_translation_regression.py`
   - `app/domains/acceptance/**`
   - `tests/**`
   - `docs/testing/**`

## 规划必须覆盖的交付物

- 检查 schema current 和 API/Worker 兼容。
- 检查 preview provider readiness。
- 检查 blocked/unreviewed/published 负向合同。
- 接入表格和四方向 translation gates。
- 输出可审计 run directory。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得把失败门禁降级为普通 warning。
- 不得依赖真实外部 AI 作为 CI 必需条件。
- 历史 release 命令尽量兼容。

## 明确范围外

- 生产部署。
- 新增产品功能。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **REL-701：Release check 和 Acceptance gate**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-701`
发布阶段：`R7（发布收口）`
依赖任务：TAB-308、TR-407、QA-607
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-701-release-acceptance-gate`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

扩展发布检查，统一验证 schema、preview、quality/review/publish、表格和翻译门禁。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-701 为 `planning`；
   - 确认依赖 TAB-308、TR-407、QA-607 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 REL-701，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 REL-701 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `scripts/ops/check_release.py`
   - `scripts/ops/run_golden_sample_regression.py`
   - `scripts/ops/run_p1_translation_regression.py`
   - `app/domains/acceptance/**`
   - `tests/**`
   - `docs/testing/**`

必须交付：
- 检查 schema current 和 API/Worker 兼容。
- 检查 preview provider readiness。
- 检查 blocked/unreviewed/published 负向合同。
- 接入表格和四方向 translation gates。
- 输出可审计 run directory。

验收条件：
- 本地和测试环境 release check 可复现。
- 关键负向用例会阻断。
- Acceptance Center 记录完整。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得把失败门禁降级为普通 warning。
- 不得依赖真实外部 AI 作为 CI 必需条件。
- 历史 release 命令尽量兼容。

## 明确范围外

- 生产部署。
- 新增产品功能。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python scripts/ops/check_release.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`，以及本阶段新增的四方向门禁。
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `npm --prefix frontend run test:smoke`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 REL-701 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **REL-701：Release check 和 Acceptance gate** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-701`
依赖任务：TAB-308、TR-407、QA-607

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 REL-701 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# REL-702 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 指标、告警和容量 |
| 阶段 | R7 · 发布收口 |
| 依赖 | REL-701 |
| 建议分支 | `md2word/REL-702` |
| Trellis 子任务 slug | `rel-702-metrics-alerts-capacity` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/REL-702
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（REL-701）的基线分支。若分支已存在，使用 `git switch md2word/REL-702`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **REL-702：指标、告警和容量** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-702`
发布阶段：`R7（发布收口）`
依赖任务：REL-701
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-702-metrics-alerts-capacity`

## 本任务目标

增加表格、翻译、预览、审核和发布的低基数指标、告警与容量保护。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-702 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 REL-701 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 REL-702 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 REL-702 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/domains/ops/**`
   - `app/services/health_service.py`
   - `app/core/logging.py`
   - `app/core/config.py`
   - `docs/engineering/security-observability-operations.md`
   - `tests/**`

## 规划必须覆盖的交付物

- 定义任务阶段时长、blocked 比率、Token 校验失败、preview 失败、review backlog、publish 失败等指标。
- 设置合理告警。
- 增加 PDF/ZIP/图片/表格/翻译 batch/Artifact 容量限制。
- 敏感字段不进入 metrics/logs。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 指标标签必须低基数。
- 不得记录原文/译文全文。
- 容量触发必须产生可理解错误和事件。

## 明确范围外

- 更换监控平台。
- 引入高基数 per-block 指标。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **REL-702：指标、告警和容量**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-702`
发布阶段：`R7（发布收口）`
依赖任务：REL-701
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-702-metrics-alerts-capacity`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

增加表格、翻译、预览、审核和发布的低基数指标、告警与容量保护。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-702 为 `planning`；
   - 确认依赖 REL-701 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 REL-702，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 REL-702 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/domains/ops/**`
   - `app/services/health_service.py`
   - `app/core/logging.py`
   - `app/core/config.py`
   - `docs/engineering/security-observability-operations.md`
   - `tests/**`

必须交付：
- 定义任务阶段时长、blocked 比率、Token 校验失败、preview 失败、review backlog、publish 失败等指标。
- 设置合理告警。
- 增加 PDF/ZIP/图片/表格/翻译 batch/Artifact 容量限制。
- 敏感字段不进入 metrics/logs。

验收条件：
- 指标/告警单测或 fake sink 测试通过。
- 容量负例不会导致 Worker 静默 OOM。
- runbook 更新。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 指标标签必须低基数。
- 不得记录原文/译文全文。
- 容量触发必须产生可理解错误和事件。

## 明确范围外

- 更换监控平台。
- 引入高基数 per-block 指标。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python scripts/ops/check_release.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`，以及本阶段新增的四方向门禁。
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `npm --prefix frontend run test:smoke`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 REL-702 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **REL-702：指标、告警和容量** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-702`
依赖任务：REL-701

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 REL-702 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# REL-703 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | 迁移和灰度启用 |
| 阶段 | R7 · 发布收口 |
| 依赖 | REL-701 |
| 建议分支 | `md2word/REL-703` |
| Trellis 子任务 slug | `rel-703-migration-gradual-rollout` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/REL-703
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（REL-701）的基线分支。若分支已存在，使用 `git switch md2word/REL-703`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **REL-703：迁移和灰度启用** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-703`
发布阶段：`R7（发布收口）`
依赖任务：REL-701
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-703-migration-gradual-rollout`

## 本任务目标

按 additive migration、兼容 API/Worker、feature flags、历史 backfill 和回滚演练完成灰度启用。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-703 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 REL-701 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 REL-703 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 REL-703 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `app/infrastructure/persistence/**`
   - `app/core/config.py`
   - `docker/**`
   - `deploy/**`
   - `scripts/**`
   - `docs/implementation/rollout-and-migration.md`
   - `tests/**`

## 规划必须覆盖的交付物

- 整理并执行 migration 顺序。
- API 先兼容新旧字段，再部署 Worker。
- 实现/核验 feature flags 及移除条件。
- 历史任务 backfill。
- 完成 rollback rehearsal 和兼容窗口说明。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得删除新表/列作为主要回滚方式。
- 历史任务不自动重跑。
- 任务中途不切算法 snapshot。
- 已发布文件不重生成。

## 明确范围外

- 生产数据破坏性清理。
- 同时升级基础设施大版本。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要未批准的生产数据改写或停机窗口时停止。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **REL-703：迁移和灰度启用**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-703`
发布阶段：`R7（发布收口）`
依赖任务：REL-701
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-703-migration-gradual-rollout`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

按 additive migration、兼容 API/Worker、feature flags、历史 backfill 和回滚演练完成灰度启用。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-703 为 `planning`；
   - 确认依赖 REL-701 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 REL-703，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 REL-703 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `app/infrastructure/persistence/**`
   - `app/core/config.py`
   - `docker/**`
   - `deploy/**`
   - `scripts/**`
   - `docs/implementation/rollout-and-migration.md`
   - `tests/**`

必须交付：
- 整理并执行 migration 顺序。
- API 先兼容新旧字段，再部署 Worker。
- 实现/核验 feature flags 及移除条件。
- 历史任务 backfill。
- 完成 rollback rehearsal 和兼容窗口说明。

验收条件：
- 前滚、滚动部署和回滚演练有证据。
- 旧前端/旧 Worker 兼容窗口通过。
- shadow→blocked→review→publish 分阶段开关可控。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 不得删除新表/列作为主要回滚方式。
- 历史任务不自动重跑。
- 任务中途不切算法 snapshot。
- 已发布文件不重生成。

## 明确范围外

- 生产数据破坏性清理。
- 同时升级基础设施大版本。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。
- 需要未批准的生产数据改写或停机窗口时停止。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python scripts/ops/check_release.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`，以及本阶段新增的四方向门禁。
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `npm --prefix frontend run test:smoke`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 REL-703 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **REL-703：迁移和灰度启用** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-703`
依赖任务：REL-701

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 REL-703 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```


---

# REL-704 Codex 提示词

| 字段 | 内容 |
|---|---|
| 标题 | Runbook、OpenAPI、最终签字 |
| 阶段 | R7 · 发布收口 |
| 依赖 | REL-703 |
| 建议分支 | `md2word/REL-704` |
| Trellis 子任务 slug | `rel-704-runbook-openapi-signoff` |
| 实现会话结束状态 | manifest=`review`；Trellis=`in_progress` |
| 人工验收后状态 | manifest=`done` 或 `skipped_existing`；Trellis 归档 |

## 使用前

```bash
cd /Users/sc/PycharmProjects/md2word
git status --short
git switch main
git pull --ff-only
git switch -c md2word/REL-704
codex
```

> 如果基线分支不是 `main`，替换为实际已完成并已合并全部依赖（REL-703）的基线分支。若分支已存在，使用 `git switch md2word/REL-704`。若工作区存在不认识的改动，先停止，不要 stash、删除或混入当前任务。

## 会话 1：规划提示词

> 新开 Codex 会话，复制下面全部内容。规划完成后先人工检查 `prd.md`、`design.md`、`implement.md`。

```text
请为 md2word 任务 **REL-704：Runbook、OpenAPI、最终签字** 完成 Trellis 规划。本会话只做调查和规划，不修改业务代码，不执行 `task.py start`，不提交，不 push。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-704`
发布阶段：`R7（发布收口）`
依赖任务：REL-703
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-704-runbook-openapi-signoff`

## 本任务目标

使 API 文档、runbook、Acceptance Center、线上真实任务证据和 Admin signoff 与最终实现一致。

## 开始前必须执行

1. 执行 `pwd` 和 `git status --short`，确认工作目录和未识别 dirty files；不得 stash、删除或覆盖不属于本任务的改动。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、相关 `.trellis/spec/**/index.md` 和现有 Trellis 任务记录。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-704 当前为 `todo`、`planning` 或明确可继续的状态；
   - 逐项确认依赖 REL-703 均为 `done` 或经人工接受的 `skipped_existing`；
   - 依赖未完成时将当前任务标记为 `blocked` 并停止。
4. 在 `docs/implementation/codex-task-backlog.md` 中读取 REL-704 的完整任务定义。
5. 读取以下文档，不得仅凭任务标题规划：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
6. 调查当前真实代码、测试、API、数据库、配置、脚本和历史 Trellis 记录，确认已有能力与目标差距。
7. 如果当前能力已经完整满足验收条件，不得重复建设；把任务规划为“验证并收口”，在结论中建议 `skipped_existing`。
8. 定位父任务；若子任务不存在，使用 `task.py create` 和 `--parent` 创建；若已存在，复用，不得创建重复任务。
9. 将 manifest 中 REL-704 更新为 `planning`，记录实际 Trellis task path；不要更新其他任务状态。
10. 编写或更新当前子任务的 `prd.md`、`design.md`、`implement.md`；复杂任务必须三份齐全。
11. 为 implement/check 配置最小必要 context；不得把整个仓库无差别加入。
12. 运行 `task.py validate <task>`；最终停在规划评审门，不执行实现。

## 重点调查代码区域

   - `docs/api/**`
   - `docs/runbooks/**`
   - `docs/testing/**`
   - `docs/deploy/**`
   - `README.md`
   - `app/openapi.json`
   - `scripts/ops/**`
   - `.trellis/**`

## 规划必须覆盖的交付物

- 更新 OpenAPI 和所有受影响 API 文档。
- 更新内部门户/后端/部署/回滚 runbook。
- 记录线上 direct 与已启用翻译方向真实任务证据。
- 记录 Admin Microsoft Word 人工签字。
- 关闭或标注剩余兼容项。

## 规划中必须固化的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 文档只能描述已实现和已验证事实。
- 不得把未运行的线上验证写成通过。
- 不得在本任务新增功能。

## 明确范围外

- 实现任何业务代码。
- 替代人工 Word 签字。

## 规划文档最低内容

`prd.md`：目标、用户/业务结果、范围、非目标、验收条件、权限和失败语义。

`design.md`：当前实现、目标边界、数据流、模型/API/DB/前端影响、兼容、迁移、回滚、安全和可观测性。

`implement.md`：有序任务清单、计划修改文件、定向测试、回归门禁、文档/Spec 更新、回滚点和完成定义。

## 规划阶段停止条件

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 完成后输出

1. 依赖状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与目标文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限影响；
8. 幂等、并发、generation、不可变和错误映射影响；
9. 安全、隐私、外部调用和敏感数据边界；
10. 测试与回归计划；
11. 风险、停止条件和回滚点；
12. Trellis 子任务准确路径及 `task.py validate` 结果。

不要修改业务代码，不要执行 `task.py start`，等待我审核规划。
```

## 会话 2：实施提示词

> 规划文档已审核后，再新开 Codex 会话，复制下面全部内容。

```text
请实现 md2word 任务 **REL-704：Runbook、OpenAPI、最终签字**。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-704`
发布阶段：`R7（发布收口）`
依赖任务：REL-703
父任务 slug：`datasheet-docx-delivery-quality`
子任务 slug：`rel-704-runbook-openapi-signoff`
任务完成后的 manifest 状态：`review`；人工验收后才改为 `done` 或 `skipped_existing`
Trellis 状态：保持 `in_progress`，人工验收前不要 archive

我已经审核并接受当前 Trellis 子任务的 `prd.md`、`design.md` 和 `implement.md`，授权你开始实现当前任务。

## 本任务目标

使 API 文档、runbook、Acceptance Center、线上真实任务证据和 Admin signoff 与最终实现一致。

## 开始前必须执行

1. 执行 `pwd`、`git status --short` 和 `git branch --show-current`；确认位于建议分支或经说明的等效分支。
2. 读取根 `AGENTS.md`、`.trellis/workflow.md`、当前子任务 `prd.md`、`design.md`、`implement.md` 和相关 `.trellis/spec`。
3. 打开 `docs/implementation/codex-task-manifest.yaml`：
   - 确认 REL-704 为 `planning`；
   - 确认依赖 REL-703 均为 `done` 或经人工接受的 `skipped_existing`；
   - 确认没有另一个冲突的 `in_progress` 实现任务。
4. 读取以下产品和设计文档：
   - `docs/product/prd.md`
   - `docs/product/scope-and-decisions.md`
   - `docs/implementation/implementation-plan.md`
   - `docs/implementation/codex-task-backlog.md`
   - `docs/implementation/codex-execution-guide.md`
   - `docs/implementation/codex-task-manifest.yaml`
   - `docs/decisions/architecture-decisions.md`
   - `docs/engineering/testing-acceptance-strategy.md`
   - `docs/engineering/security-observability-operations.md`
   - `docs/implementation/rollout-and-migration.md`
   - `docs/architecture/system-architecture.md`
5. 在 `docs/implementation/codex-task-backlog.md` 中再次核对 REL-704，不得实现相邻或后续任务。
6. 读取当前相关代码、测试、API 文档、数据库迁移和历史任务，确认计划仍与真实实现一致。
7. 运行 `implement.md` 规定的当前基线测试；无法运行时记录精确命令、环境阻断和替代证据。
8. 使用 `task.py start` 激活准确的子任务，并将 manifest 中 REL-704 改为 `in_progress`。
9. 若发现能力已完整存在，停止新增实现，改为验证/测试/文档收口；不要制造第二套实现。

## 本任务范围

主要代码区域：
   - `docs/api/**`
   - `docs/runbooks/**`
   - `docs/testing/**`
   - `docs/deploy/**`
   - `README.md`
   - `app/openapi.json`
   - `scripts/ops/**`
   - `.trellis/**`

必须交付：
- 更新 OpenAPI 和所有受影响 API 文档。
- 更新内部门户/后端/部署/回滚 runbook。
- 记录线上 direct 与已启用翻译方向真实任务证据。
- 记录 Admin Microsoft Word 人工签字。
- 关闭或标注剩余兼容项。

验收条件：
- 文档链接、OpenAPI、release gate、真实任务和签字证据齐全。
- 剩余风险和后续版本明确。

## 不可违反的不变量

- 一次只实现当前任务，不得提前实现任务清单中的其他任务。
- 保持模块化单体；不得为本任务引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；需要其他语言时创建或克隆新任务。
- `direct_pdf_to_word` 不得调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不得增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不得以截图作为默认简化方案。
- 质量 `blocked` 和翻译 `unreviewed` 均可内部下载，但不得批准或发布。
- 前端不得自行推断发布资格，必须消费后端权威状态或 available actions。
- 不得新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不得为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 文档只能描述已实现和已验证事实。
- 不得把未运行的线上验证写成通过。
- 不得在本任务新增功能。

## 明确范围外

- 实现任何业务代码。
- 替代人工 Word 签字。

## 编码前输出

先输出以下 preflight，然后在没有停止条件时继续执行，不需要等待我再次确认：

1. 依赖和 manifest 状态检查；
2. 当前行为；
3. 目标行为；
4. 当前实现与已批准任务文档的差异；
5. 范围内和明确范围外；
6. 计划修改文件；
7. OpenAPI、数据库、迁移、状态机和权限变化；
8. 事务、幂等、并发、generation、不可变和错误映射影响；
9. 前端路由、query key、URL 状态和 generated types 影响（如适用）；
10. 安全、隐私、外部调用、文件和敏感数据边界；
11. 测试与回归计划；
12. 风险、停止条件和回滚点。

只有遇到以下情况才停止并将任务标记为 `blocked`：

- 依赖任务未达到 `done` 或经人工确认的 `skipped_existing`。
- 产品 PRD、冻结决策或已接受 ADR 存在无法消解的冲突。
- 必须进行未批准的破坏性数据库迁移、覆盖已发布文件或删除历史审计数据。
- 完成当前任务必须改变已冻结的任务模式、表格原生化、下载或发布规则。
- 必要的专有样本授权、外部系统选择或人工安全授权缺失，且无法用 fake/adapter 完成范围内实现。

## 最低验证要求

至少运行并逐项报告以下验证；按实际变更增加更精确的定向测试。不得把未运行的命令写成通过：

- `git diff --check`
- `.venv/bin/python scripts/ops/check_release.py`
- `.venv/bin/python scripts/ops/run_golden_sample_regression.py`
- `.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight`，以及本阶段新增的四方向门禁。
- `.venv/bin/python scripts/dev/run_component_pdf_regression.py`
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `npm --prefix frontend run test:smoke`（适用时）。

另外必须：

- 对照 `prd.md` 的每条验收标准给出测试或人工证据；
- 更新受影响的 API 文档、项目文档和 `.trellis/spec`；
- 不得留下未解释的新 quality flag；
- 若使用 feature flag，写明默认值、snapshot 行为和移除条件；
- 若涉及数据库，写明前滚、backfill、兼容窗口和回滚策略；
- 若涉及前端，前端不得维护第二套业务状态机。

## 完成状态

实现和本地验证完成后：

1. 将 `docs/implementation/codex-task-manifest.yaml` 中 REL-704 从 `in_progress` 更新为 `review`；
2. 记录实际分支、Trellis task path、验证结果和残余风险；
3. 不得自行改为 `done`；
4. 不得 archive Trellis task；
5. 不自动 push；
6. 按 `AGENTS.md` 最终停在 commit plan，等待人工验收与提交授权。

## 完成后输出

1. 实现摘要；
2. 修改文件列表；
3. OpenAPI、数据库、迁移和兼容合同变化；
4. 关键业务不变量如何保证；
5. 事务、锁、幂等、并发、generation 和错误映射；
6. 安全与敏感数据边界；
7. 前端行为与页面状态（如适用）；
8. 实际运行的测试命令和逐项结果；
9. 未运行测试及具体原因；
10. Trellis 任务和 manifest 状态变化；
11. 已知限制与残余风险；
12. 后续任务，只列出，不实现；
13. commit plan，不提交、不 push。
```

## 人工验收后的收尾提示词

```text
我已经人工审查并接受 **REL-704：Runbook、OpenAPI、最终签字** 的实现、测试证据和残余风险。

仓库根目录：`/Users/sc/PycharmProjects/md2word`
建议分支：`md2word/REL-704`
依赖任务：REL-703

请只执行当前任务的收尾操作：

1. 读取 `AGENTS.md`、`.trellis/workflow.md`、当前子任务和 `docs/implementation/codex-task-manifest.yaml`；
2. 确认 REL-704 当前为 `review`，且工作区只包含当前任务及已识别的文档/任务元数据变更；
3. 对照 `prd.md` 再核验全部验收条件和已报告测试，不新增功能；
4. 若本任务实际为“现有能力已满足，仅完成验证收口”，把 manifest 状态改为 `skipped_existing`；否则改为 `done`；
5. 按仓库 Trellis 约定记录人工验收完成，并在适当顺序执行 spec update、提交和 task archive；如果 archive 会生成 bookkeeping commit，先说明实际行为；
6. 用户本条消息视为对当前任务 commit plan 的确认：只提交当前任务相关文件，不包含未知 dirty files，不 push；
7. 不修改其他任务状态，不开始后续任务；
8. 运行 `git diff --check`，并运行当前任务 `implement.md` 中要求的最终轻量验证；
9. 报告最终 manifest 状态、Trellis 状态/归档位置、commit hash、提交文件、验证结果和最终 `git status --short`。

不得实现任何后续任务，不得 push。
```
