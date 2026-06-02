---
doc_type: design
slug: term-assets-sql-versioning
component: term-assets
status: approved
summary: 术语规则和翻译术语进入 MySQL 后的唯一真源、版本发布、proposal、job 绑定和导入导出设计。
tags: [backend, term-rules, translation, terminology, mysql, resource-versioning]
last_reviewed: 2026-06-02
---

# 术语资产 SQL 版本化设计

本文是后续实现术语资产 SQL 化的输入文档。这里的术语资产包括：

- Term Rule Set：上下标、分段和渲染规则，seed 文件是 `resources/term_rules/term_rules.v2.yaml`。
- Translation Term Set：翻译术语表，seed 文件是 `resources/term_rules/translation_terms.csv`。

## 目标

- 生产 MySQL mode 下，SQL 是术语规则和翻译术语的唯一真源。
- YAML/CSV 只作为 seed、导入导出、备份和开发环境文件，不作为生产运行时真源。
- operator 可以从 job 结果提交术语建议，但不能直接影响全局默认规则。
- admin 可以审核建议，并一键发布默认版本。
- 新 job 绑定创建时的术语规则版本和翻译术语版本；旧 job 不被新默认版本悄悄影响。
- Term Rule Set 发布默认版本时继续生成 legacy runtime YAML，但该文件只是兼容产物。

## 非目标

- 第一版不做多租户隔离。
- 第一版不允许普通 operator 手选历史版本创建 job。
- 第一版不把翻译术语塞进 Translation Profile，也不把上下标规则和翻译术语合成同一个 proposal 表。
- 第一版不删除 YAML/CSV 的导入导出能力。

## 分阶段落地

阶段 1：

- MySQL mode 下运行时只读 SQL。
- 提供显式初始化动作，把 `term_rules.v2.yaml` 和 `translation_terms.csv` 导入 SQL。
- 保留 legacy runtime YAML 物化，用于兼容现有 conversion 链路。
- file/sqlite mode 继续保留现有文件路径。

阶段 2：

- 补 admin UI/API 的导入、导出、发布、回滚和审计。
- 生产环境禁止依赖直接修改本地 YAML/CSV 来改变术语资产。
- 支持从任意历史版本导出文件，默认导出当前默认版本。

## Term Rule Set

Term Rule Set 继续使用现有 proposal、draft、publish、default pointer 和 rollback 架构。

关键约束：

- `term_rules.v2.yaml` 是开发 seed 和导入导出格式，不是生产真源。
- 发布新默认版本时必须同步生成 `runtime_subscripts_dictionary.yaml`。
- runtime YAML 生成或校验失败时，发布必须失败或回滚，不能留下 SQL 已切默认但 legacy runtime 未更新的半成功状态。
- 已发布版本不可变；rollback 只切默认指针，不改历史内容。
- 当前 legacy runtime YAML 只代表当前默认 Term Rule Set 的兼容物化结果。

## Translation Term Set

翻译术语也采用版本化配置资产模型，不做单表当前态 CRUD。

建议最小 SQL 模型：

| 表 | 作用 |
|---|---|
| `translation_term_sets` | 保存 `language_pair`、默认版本指针和 draft 指针 |
| `translation_term_versions` | 保存 draft/published/archived 版本元数据 |
| `translation_terms` | 保存某个 set/version 下的术语明细 |
| `translation_term_proposals` | 保存 operator 提交的翻译术语建议 |
| `translation_term_proposal_changes` | 保存 proposal 内的一条或多条 add/update/delete 变更 |

`translation_terms` 至少需要保存：

| 字段 | 说明 |
|---|---|
| `set_id` | 翻译术语集 ID |
| `version` | 不可变版本号 |
| `source_term` | 原文术语 |
| `normalized_source_term` | 规范化唯一键 |
| `target_term` | 推荐译文 |
| `case_sensitive` | 单条术语是否大小写敏感 |
| `status` | `active` 或 `disabled` |
| `priority` | 同长度命中时的优先级 |
| `domain` / `category` | 元数据，不参与唯一键 |
| `note` | 维护说明 |
| `created_at` / `updated_at` | 行级时间 |

同一 `language_pair` 的同一版本内，`normalized_source_term` 唯一。第一版不把 `domain` 或 `category` 放入唯一键。

第一版每个 `language_pair` 只启用一个默认 Translation Term Set，`set_id` 固定从 `language_pair` 派生，例如 `translation-terms-en2zh`。默认指针按 `language_pair` 解析，普通用户不选择不同 set。后续如需多行业、多客户或多模板术语表，再通过 Translation Profile 或更高层配置选择不同 set。

别名和同义词用多条独立术语记录实现：

- 每个 `source_term` 仍有自己的 `normalized_source_term` 唯一键。
- 多个 `source_term` 可以指向同一个 `target_term`。
- 第一版不建立 alias 表、alias group 或 `canonical_term_id`。

第一版不支持同一 `source_term` 多候选译文：

- 同一 `language_pair + version + normalized_source_term` 只能有一个 `target_term`。
- 不做 `target_terms[]`、候选权重或上下文选择。
- 需要多译时优先用更长上下文术语解决；后续如需行业、模板、客户或上下文差异，应通过不同 profile/set 或上下文规则表达。

## 翻译术语规范化和匹配

`normalized_source_term` 规则：

- trim 首尾空白。
- 连续空白折叠成一个空格。
- 默认大小写不敏感。

匹配规则：

- 默认大小写不敏感。
- 单条术语可设置 `case_sensitive=true` 覆盖。
- 同一位置多个候选命中时，最长 `source_term` 优先。
- 长度相同按 `priority`，默认 `0`。
- `priority` 也相同时使用稳定排序，保证结果可复现。
- `disabled` 术语保留在版本中，但不参与匹配。

## 翻译链路接入

第一版翻译术语继续作为 glossary context 提供给翻译器，不做强制文本替换。

约束：

- 不在原文段落里预先替换 `source_term`。
- 不在译文后处理阶段盲目替换 target text。
- 每个翻译请求只传命中术语，优先当前段落或当前 batch 命中。
- 如果当前 batch 没有命中，但文档级预扫描有高优先级术语，可以补少量文档级命中。
- 不把完整术语表塞进 prompt。
- trace 记录本次实际传给翻译器的 glossary 条目。

术语命中 trace 记录到 segment/batch 粒度，不记录完整原文大段。

建议字段：

- `job_id`
- `segment_id` 或 batch id
- `translation_term_set_id`
- `translation_term_version`
- `source_term`
- `target_term`
- `match_start` / `match_end` 或简短上下文窗口
- 是否实际注入到 glossary context
- provider 请求 trace id

trace 不记录完整 PDF 文本、完整 prompt、API key、token 或大段上下文。

## Proposal 流程

上下标规则和翻译术语各自独立建表，但保持状态机和体验一致。

共同状态：

| 状态 | 说明 |
|---|---|
| `pending` | operator 已提交，等待审核 |
| `approved` | admin 已审核通过并合入 draft |
| `rejected` | admin 拒绝 |
| `published` | proposal 对应变更已进入发布版本 |

共同字段：

- `source_job_id`
- `source_file_id`
- `observed_term_rule_version` 或 `observed_translation_term_version`
- `submitted_by`
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `published_term_rule_set_id/version` 或 `published_translation_term_set_id/version`
- `published_at`

Term Rule Proposal 第一版需要轻量证据字段：

- `page_number`
- `source_term`
- `context_before`
- `context_after`
- `observed_term_rule_set_id`
- `observed_term_rule_version`
- `reason`

第一版不存复杂坐标、多边形、整页 OCR 文本或可视化圈选区域；后续若需要 PDF 区域圈选，再增加 `bounding_boxes` 或 `source_regions`。

翻译术语 proposal 支持三类变更：

- `add`：新增 `source_term -> target_term`。
- `update`：修改已有术语的译文、说明、领域、大小写策略、状态或优先级。
- `delete`：从下一版默认术语集中移除该术语。

proposal 记录 job 当时绑定的版本作为证据来源，合并目标默认是当前 draft/default 的下一版。若当前默认版本和 job 使用版本不同，admin 审核时应显示 warning。

proposal 入口：

- job 详情页是第一版主要提交入口，自动填充 `source_job_id`、`source_file_id`、绑定版本和可用上下文。
- 独立术语建议页用于列表、筛选、审核 pending proposals 和 admin 操作。
- 独立创建入口第一版可以不给 operator；admin 审核页必须能回跳来源 job。

## Draft 和发布

翻译术语需要 draft，但第一版 UI 可以让 draft 对用户近乎透明。

流程：

1. operator 从 job 详情或转换结果页提交 proposal。
2. admin 审核 proposal。
3. 审核通过时，后端把变更合并到当前 draft。
4. admin 可以预览 draft diff 并运行校验。
5. admin 发布 draft，生成不可变 published version。
6. 可选设为默认版本。
7. 一键审核并发布等价于合并到 draft 后立即 publish 并设默认。

版本号由后端自动生成，格式使用时间戳加短序号，例如 `20260602-153012-001`。admin 不手填版本号，只填写 `release_note` 或 `publish_reason`。

Translation Term Set 第一版版本状态只保留：

- `draft`：可变草稿。
- `published`：不可变发布版本，可被设为默认。
- `archived`：历史归档版本，不允许再设为默认，除非 admin 先恢复。

第一版不引入版本级 `disabled` 或 `superseded`。是否生效由默认指针表达；单条术语是否参与匹配由行级 `status=active/disabled` 表达。

rollback 第一版只把 `default_version` 切到某个旧 `published` version，不生成新版本。后续高级动作 `republish-from-version` 可以基于旧版本复制成新 draft，再发布为新版本。audit 必须区分 `translation_term_set.rollback` 和 `translation_term_set.publish`。

proposal 与当前 draft 产生冲突时，第一版阻断并返回冲突原因，由 admin 手动解决。冲突包括：

- `add` 的 `normalized_source_term` 已在 draft 中存在。
- `update` 或 `delete` 的目标术语在 draft 中已被其他 proposal 改动或删除。
- Term Rule Proposal 的同一 `source_term` 已存在不同 segments。
- proposal 基于的 observed version 落后于当前默认或 draft，且同一 key 已变化。

后端不做 last-write-wins。admin 可以进入 draft 手动编辑、拒绝 proposal，或重新提交修正版 proposal。

## 发布校验

发布前必须做自动校验。

阻断发布的错误：

- 同一版本内 `normalized_source_term` 重复。
- `source_term` 为空。
- `target_term` 为空。
- `delete` 不存在的术语。
- `update` 不存在的术语。
- Term Rule Set 发布默认版本时 legacy runtime YAML 生成或校验失败。

允许 admin 带 warning 发布的问题：

- 新增术语和已有术语重叠，例如 `ADC` 与 `high-speed ADC`。
- 变更前后没有实际变化。
- job 证据版本和当前默认版本不同。

## Job 版本绑定

job 创建时必须绑定当时使用的术语资产版本：

- `term_rule_set_id`
- `term_rule_version`
- `translation_term_set_id`
- `translation_term_version`

转换执行时只使用 job 绑定的版本。admin 发布新默认版本后，只影响新 job。旧 job 如需使用新版本，需要显式重新创建或重新运行并选择新配置。

权限边界：

- operator 创建 job 时只使用当前默认版本，第一版不允许选择历史版本。
- admin 创建或重跑 job 时可以选择特定 Term Rule Set 版本和 Translation Term Set 版本。
- job 详情页对所有角色展示实际绑定版本。
- 重跑 job 默认沿用原绑定版本；admin 可选择使用最新默认版本重跑。

## 导入导出

导入：

- 默认严格校验，遇到重复 `normalized_source_term` 或重复规则时拒绝导入。
- admin 高级导入可选择 `dedupe=keep_first`，按规范化键去重并保留第一条。
- `keep_first` 必须生成导入报告，列出被丢弃的重复项。
- 一次性 seed 迁移可以使用 `keep_first`；生产导入不应静默去重。

导出：

- 默认导出当前默认版本。
- admin 可选择任意历史 `set_id/version` 导出。
- Term Rule Set 支持导出 `term_rules.v2.yaml` 和 legacy runtime YAML。
- Translation Term Set 第一版支持导出 CSV。
- 导出产物应带 `set_id`、`version`、`exported_at`、`exported_by` 等元信息；CSV 可通过旁路 manifest 表达，避免破坏现有读取器。

## 审计

以下成功动作应写 audit event：

- proposal create
- proposal approve
- proposal reject
- proposal approve-and-publish
- draft update
- publish
- set-default
- rollback
- import
- export

审计记录 actor、目标资源、版本、来源 job/file、动作结果和时间，不记录完整 PDF 内容、API key、token 或大段原文。

## 实现检查点

- MySQL mode 下，SQL 是术语规则和翻译术语运行时唯一真源。
- `term_rules.v2.yaml` 和 `translation_terms.csv` 可导入 SQL，但不在生产运行时被直接读取。
- 每个 `language_pair` 第一版只有一个固定派生的 Translation Term Set，例如 `translation-terms-en2zh`。
- 翻译术语支持别名作为多条独立记录，但不支持一词多译。
- 翻译术语只作为 glossary context，且每次只注入命中术语。
- 术语命中 trace 记录到 segment/batch 粒度，不落完整原文大段。
- operator 能提交上下标规则和翻译术语 proposal。
- proposal 主要从 job 详情页提交，并带轻量证据字段。
- proposal 与当前 draft 冲突时阻断，由 admin 手动解决。
- operator 不能发布、不能改默认版本、不能选择历史版本创建 job。
- admin 能一键审核并发布默认版本。
- 新 job 绑定创建时的 Term Rule Set 和 Translation Term Set 版本。
- 旧 job 不因默认版本切换而改变转换结果。
- Translation Term Set 第一版 rollback 只切默认指针；版本状态只使用 `draft/published/archived`。
- Term Rule Set 发布默认版本时 legacy runtime YAML 同步成功；失败时发布不生效。
- 导入默认拒绝重复；admin 可显式 `dedupe=keep_first` 并得到报告。
- 导出默认当前默认版本，也可选择历史版本。
