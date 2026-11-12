---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  本文按文档治理任务 design revision 1 定义字段、生命周期、证据分类与维护边界；只核对规则一致性和导航，不声明代码或运行验收。实施记录：.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b1-implementation.md。
---

# 文档状态与核验规则

本文说明如何辨认文档的用途、证据和版本。文档职责及冲突处理仍由[文档清单与权威关系](../../DOCUMENTATION-MANIFEST.md)定义；产品任务的执行状态和实际 Trellis 路径仍由[任务 Manifest](../implementation/codex-task-manifest.yaml)记录。文档的维护状态不推进任务、不放宽验收或依赖门。

## 适用资料

维护范围包括根 README、文档权威清单、`docs/` 下的 Markdown/YAML、Docker README、`trellis-bootstrap/` 的 Markdown，以及 `tests/fixtures/` 中的说明和验收模板。逐份判断用途，不能按日期或目录自动归档。迁移路径和实际覆盖批次见[文档清单](../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/document-inventory.json)；本规则文档也遵循同一字段合同。

运行时 Prompt、模板与样本 Manifest、Compose 和 OpenAPI 生成快照是运行输入或生成产物，不注入治理字段。AGENTS、Skills、平台配置、Trellis Specs、任务历史和会话记录沿用各自生命周期，本规则只引用它们。

## 四个字段

Markdown 使用 YAML frontmatter；已有 frontmatter 时追加字段，不重写原键。纳入范围的 docs YAML Manifest 使用同名顶层字段，不插入 Markdown 分隔符，不改原业务结构。

```yaml
doc_status: active
last_verified_commit: null
owner: null
verification_scope: null
```

| 字段 | 含义与取值 |
|---|---|
| `doc_status` | 必填，取 `active`、`historical`、`superseded`、`draft`，只描述文档用途和维护阶段。 |
| `last_verified_commit` | 实际核验所依据代码的完整 40 位提交 SHA，或 `null`。最近编辑提交、当前 HEAD、历史 release 引用都不能自动填入。 |
| `owner` | 已确认的责任团队或维护者标识字符串，未知时为 `null`；不把任务 assignee 或签字角色批量当作文档 owner。 |
| `verification_scope` | 非空说明字符串或 `null`，写明核验章节、事实种类、依据和未核验边界。非空核验 SHA 必须有非空范围；没有进行核验时，两个核验字段均为 `null`。 |

原有 `doc_type`、`status`、`baseline_commit`、`last_reviewed`、`last_scanned`、slug、tags、component 等字段继续保留原值和语义。不能把 `baseline_commit` 改名作为新核验版本，也不能仅因补元数据就刷新全篇复核日期。

## 四种文档生命周期

| `doc_status` | 适用情形 | 阅读边界 |
|---|---|---|
| `active` | 仍维护和引用的说明、规范或目标设计 | 已冻结的目标设计也可以是 active；不代表功能已实现或上线。 |
| `historical` | 保留当时的问题、调查、运行或验收结论 | 正文保留时间、版本、环境和范围；后来可能已修复或变化。 |
| `superseded` | 已被明确文档替代 | 正文链接实际替代路径，同时保留旧入口供追溯。 |
| `draft` | 未冻结、待确认或尚不能作为维护依据的草案 | 不能当作已接受合同或实现事实。 |

例如，目标设计的 `status: target` 与 `doc_status: active` 可以并存；历史验收报告保留的 `status: current` 不会使旧 release 通过结论成为当前版本验收。

## 五类事实

正文或证据引用要使读者能够区分以下内容；不新增第二套全局功能状态字段。

| 事实种类 | 需要说明的依据 | 不能外推的结论 |
|---|---|---|
| 当前代码实现 | 真实责任模块、调用入口、核验提交或工作区内容身份 | 符号存在不证明开关启用、链路运行、完整 AC 或人工接受。 |
| 文档声明通过 | 报告、原 release/run、环境、样本及实际验收范围 | 未核看原始证据时明确为报告声明，不能改写成新一次通过。 |
| 计划能力 | 目标设计、任务 AC 和依赖 | 不作为当前 API、行为或上线事实。 |
| 历史问题 | 原调查日期、基线和结论 | 未复核前不能当作当前仍存在的缺口并重复实现。 |
| 当前仍存在的问题 | 对应本次基线的差异、失败或反例 | 文案漂移可用源文件对比证明；运行时缺陷需有相应运行证据。 |

局部核验只覆盖明确列出的章节和性质，其余旧章节继续沿用原历史范围。`active`、日期或一行 SHA 都不能替代验收证据。

## 版本与工作区证据

核验事实先写入对应任务研究记录，再将范围和引用补到文档。若所依赖的源码或配置与提交不同，`last_verified_commit` 保持 `null`，在 `verification_scope` 指向使用仓库相对路径和 SHA-256 记录实际读取字节的证据。HEAD 不能代表脏工作区，也不能仅因一份源码已提交就推断整链依赖和配置一致。

只检查导航、字段或历史报告文字时，说明这类局部检查，保留核验 SHA 为 `null`；不能把报告中的 release SHA 当成亲自核验代码的提交。没有已确认责任人时保留 owner 为 `null`，后续确认后再更新。

本轮 B1 的逐份范围、源码身份和检查结果见[实施记录](../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b1-implementation.md)。后续维护使用各自任务的实际证据，避免继续引用不覆盖新改动的旧记录。

## 维护与验收

1. 确认资料用途和唯一权威入口；阅读原文、相关源码/配置或原报告，保护已有字段与历史结论。
2. 只更新实际核对的事实和章节。发现目标、代码、Manifest 或历史记录不一致时，按 AC、提交包含关系和人工接受证据对账，证据不足项明确保留。
3. 按本次核验填写字段；替代文档给出链接，历史报告保留原版本、环境、样本、run 和签字范围。
4. 对文档变更检查 YAML/frontmatter、重复键、字段类型、相对链接和实际差异；Manifest 的既有任务对象、规则和依赖保持，除非另有精确授权。
5. 纯文档治理不触发应用测试、构建、CI、完整发布门禁或生产操作。产品改动的必要验证由对应任务和项目 Specs 决定；未执行的验收应明确保留边界。

只读对账不自动将任务改为 `done` 或 `skipped_existing`；实现交付与人工接受继续遵循现有 Manifest 规则。本规则不新增状态系统、常驻校验工具或发布流程。
