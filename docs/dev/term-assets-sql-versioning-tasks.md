---
doc_type: implementation-plan
slug: term-assets-sql-versioning-tasks
component: term-assets
status: approved
summary: 术语规则和翻译术语 SQL 唯一真源、proposal、版本发布、job 绑定和导入导出的实施任务清单。
tags: [backend, frontend, mysql, term-rules, translation, terminology]
last_reviewed: 2026-06-02
---

# 术语资产 SQL 版本化任务清单

设计输入：[term-assets-sql-versioning.md](/Users/sc/PycharmProjects/md2word/docs/dev/term-assets-sql-versioning.md)

## 成功标准

- MySQL mode 下，Term Rule Set 和 Translation Term Set 的运行时读取只以 SQL 为真源。
- `term_rules.v2.yaml` 和 `translation_terms.csv` 只作为 seed、导入导出、备份和开发文件。
- operator 可以从 job 详情提交上下标规则和翻译术语 proposal，但不能改默认版本。
- admin 可以审核、发布、设默认、回滚和导入导出。
- 新 job 绑定创建时的 Term Rule Set 和 Translation Term Set 版本；旧 job 不被默认版本切换影响。
- Term Rule Set 发布默认版本时 legacy runtime YAML 同步成功；失败时发布不生效。

## 阶段 0：基线收口

- [x] 复查当前 Term Rule Set、translation terms、job snapshot、proposal 和 MySQL repository 现状。
- [x] 标出已经实现但需要调整的表、repository、service、router、frontend 页面和测试。
- [x] 确认生产 MySQL mode 禁止从 YAML/CSV 直接读取运行时术语资产。
- [x] 保留 file/sqlite mode 的 legacy 文件路径兼容。

阶段 0 收口记录（2026-06-02）：

- Term Rule Set 已有 `TermRuleSetVersionService`、`TermRuleProposalService`、`/term-rule-sets`、`/term-rule-proposals`、`MysqlTermRuleAssetRepository` 和 `MysqlTermRuleProposalRepository`；legacy category/rule 写入口已通过 `ensure_legacy_term_rule_write_allowed()` 在版本化模式下阻断。
- MySQL schema 已有 `resource_versions`、`resource_default_versions`、`term_rule_proposals`、`term_rule_categories`、`term_rules`、`term_rule_segments`、`translation_term_versions`、`translation_terms`；其中 translation terms 仍是 `language_pair/version/seq/source_term/target_term` 的早期模型，阶段 1 需要补齐 `translation_term_sets`、`set_id`、`normalized_source_term`、行级状态、proposal changes 和 trace 表。
- `TermVersionService` 当前会把 `translation_terms.csv` seed 导入 MySQL repository，但 `load_version()` 在 SQL 无结果时仍回退 CSV；阶段 2 需要让 MySQL mode runtime 只读 SQL，并把 CSV 限定为 seed/import/export 来源。
- job snapshot 当前绑定 Template、Term Rule Set 和 Translation Profile；尚未绑定 `translation_term_set_id/translation_term_version`，`ConversionOptions` 和 job API 也还没有 translation term set/version 字段。
- stage 执行已通过 job snapshot 物化 Term Rule Set 到 job-local legacy YAML，file/sqlite mode 仍保留 legacy 文件路径；后续要补 translation term set 绑定，并避免 stage 重新读取当前默认指针。
- frontend 已有 term proposal、term rule set、translation profile 等管理入口相关文件，但 Translation Term Set/Proposal 管理面仍需阶段 8 补齐；测试侧已有 fake MySQL 对早期 translation term 表的替身支持，阶段 1 改 schema 时需同步扩展。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository tests.test_fastapi_jobs_backend
```

## 阶段 1：SQL Schema 和 Repository

- [x] 新增或补齐 `translation_term_sets`，保存 `language_pair`、`default_version`、`draft_version` 和时间字段。
- [x] 补齐 `translation_term_versions` 的 `set_id`、`status=draft/published/archived`、发布人、发布时间和 release note。
- [x] 补齐 `translation_terms` 的 `set_id`、`normalized_source_term`、`case_sensitive`、`status`、`priority`、`domain/category`、`note`。
- [x] 为 `set_id + version + normalized_source_term` 增加唯一约束。
- [x] 新增 `translation_term_proposals` 和 `translation_term_proposal_changes`。
- [x] 新增术语命中 trace 表，粒度为 segment/batch，不保存完整原文大段。
- [x] 扩展 repository protocol 和 MySQL adapter，避免 service 直接写 SQL。
- [x] fake MySQL 测试替身同步支持新增表和关键查询。

阶段 1 收口记录（2026-06-02）：

- `TranslationTermEntry` 已补齐 set/version 明细字段，并新增 Translation Term Set、Version、Proposal、Proposal Change 和 Match Trace 领域记录。
- MySQL schema 已补齐 `translation_term_sets`、扩展后的 `translation_term_versions` / `translation_terms`、`translation_term_proposals`、`translation_term_proposal_changes` 和 `translation_term_match_traces`。
- `MysqlTranslationTermRepository` 已通过 repository port 读写 set/version/terms/proposal/trace，service 不直接写 SQL。
- fake MySQL 已同步新增表和关键查询，并覆盖 version bootstrap、proposal changes 和 trace 写读。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

## 阶段 2：Seed 导入和 SQL 唯一真源

- [x] 实现 Term Rule Set seed 初始化：从 `term_rules.v2.yaml` 导入 SQL，生成初始 published/default 版本。
- [x] 实现 Translation Term Set seed 初始化：每个 `language_pair` 生成固定派生 `set_id`，例如 `translation-terms-en2zh`。
- [x] 导入默认严格拒绝重复；admin 高级导入支持 `dedupe=keep_first` 并生成报告。
- [x] MySQL mode 下 runtime 加载 Term Rule Set 和 Translation Term Set 时只读 SQL。
- [x] `translation_terms.csv` 保持导入导出种子文件定位，不作为生产运行时读取来源。
- [x] `runtime_subscripts_dictionary.yaml` 只作为 Term Rule Set 当前默认版本的兼容物化产物。

阶段 2 收口记录（2026-06-02）：

- MySQL mode 启动时通过 `TermRuleSetVersionService.bootstrap_seed_as_default_if_empty()` 仅在 SQL 没有默认版本时从 `term_rules.v2.yaml` 建立 `seed` published/default 版本；后续启动从 SQL 默认版本恢复 live store 和 legacy runtime YAML，不再读取本地 seed/store 决定运行时内容。
- Translation Term Set seed 导入保留 `translation_terms.csv` 作为一次性 seed/import 来源；MySQL repository 已有默认版本后不再读取 CSV，运行时加载缺失 SQL 版本时直接报缺失，不回退 CSV。
- 翻译术语 CSV 默认按 `language_pair + version + normalized_source_term` 严格拒绝重复；`dedupe=keep_first` 会保留第一条并返回重复项报告，供后续 admin 导入 API 复用。
- `runtime_subscripts_dictionary.yaml` 由当前默认 Term Rule Set SQL 版本物化，发布、设默认、回滚和启动恢复路径保持同一同步规则。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository tests.test_document_ir_translation
```

## 阶段 3：Translation Term Set 版本服务

- [x] 实现 draft 初始化：没有 draft 时从当前默认 published 版本复制。
- [x] 实现 publish：后端生成 `YYYYMMDD-HHMMSS-NNN` 不可变版本号。
- [x] 实现 set-default：只允许 published 版本成为默认版本。
- [x] 实现 rollback：第一版只把旧 published version 设为默认，不生成新版本。
- [x] 实现 archive：不能 archive 当前默认版本；archived 版本不能直接设默认。
- [x] 保持行级 `status=active/disabled`，不引入版本级 `disabled/superseded`。
- [x] 发布校验阻断重复、空 source、空 target、update/delete 不存在。
- [x] 重叠术语、无实际变化、证据版本落后只返回 warning，允许 admin 继续发布。

阶段 3 收口记录（2026-06-02）：

- 新增 `TranslationTermSetVersionService`，负责 Translation Term Set 的 draft 初始化、draft 替换、publish、set-default、rollback 和 archive；runtime 在 MySQL translation term repository 存在时挂载该服务。
- draft 不存在时从当前默认 published 版本复制到 `draft`；publish 使用 `YYYYMMDD-HHMMSS-NNN` 后端版本号，写入不可变 published 版本，并清空 draft 指针。
- set-default / rollback 只允许指向 `published`；archive 只允许归档非当前默认的 published 版本，归档后不能直接设为默认。
- 版本状态保持 `draft/published/archived`，行级术语状态仍是 `active/disabled`；未引入版本级 `disabled/superseded`。
- 发布和变更校验已覆盖重复 normalized source、空 source/target、update/delete 不存在为 errors；重叠术语、无实际变化、证据版本落后为 warnings，不阻断发布。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

## 阶段 4：Proposal 闭环

- [x] 保持 Term Rule Proposal 和 Translation Term Proposal 独立建模。
- [x] Translation Term Proposal 支持 `add/update/delete`，数据结构保留批量 changes。
- [x] Term Rule Proposal 增加轻量证据字段：页码、上下文、观察版本和 reason。
- [x] Proposal 记录来源 job/file 和 observed version，合并目标默认当前 draft/default 的下一版。
- [x] approve 时合并到 draft；approve-and-publish 快捷路径合并后立即 publish 并设默认。
- [x] proposal 与当前 draft 冲突时阻断并返回冲突清单，不做 last-write-wins。
- [x] operator 只能创建 proposal；admin 才能审核、拒绝、发布。
- [x] 成功动作写 audit event。

阶段 4 收口记录（2026-06-02）：

- Term Rule Proposal 继续使用独立 `TermRuleProposalService` / `/term-rule-proposals`，Translation Term Proposal 新增独立 `TranslationTermProposalService` / `/translation-term-proposals`；两者共享体验但不合表。
- Translation Term Proposal API 支持批量 `add/update/delete` changes，approve 合并到当前 draft，approve-and-publish 合并后发布新 Translation Term Set 版本并设为默认。
- Term Rule Proposal 已保存 `page_number`、`context_before/context_after`、`observed_term_rule_set_id/version` 和既有 `reason`、source job/file。
- Translation Term Proposal 记录 source job/file、observed set/version；未显式传 observed version 时使用当前默认版本。
- Translation Term Proposal merge 前会比较 observed version 与当前 draft，同 key 被其他变更修改、add 已存在或 update/delete 缺失时返回 409 conflict conflicts 列表，不做 last-write-wins。
- operator 只能创建和查看自己的 proposal；admin 才能查看全部、approve、reject 和 approve-and-publish。
- proposal create / approve / reject / approve-and-publish，以及 Translation Term Set draft update / publish 成功后写 audit event。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

## 阶段 5：Job 版本绑定

- [x] job 创建时绑定 `term_rule_set_id`、`term_rule_version`、`translation_term_set_id`、`translation_term_version`。
- [x] operator 创建 job 时只能使用当前默认版本。
- [x] admin 创建或重跑 job 时可以选择历史 published 版本。
- [x] 重跑默认沿用原绑定版本；admin 可选择使用最新默认版本重跑。
- [x] job 详情、事件和 resource snapshot 展示实际绑定版本。
- [x] stage 执行只读取 job 绑定版本，不重新解析当前默认指针。

阶段 5 收口记录（2026-06-02）：

- `ConversionOptions` 和 `JobResourceSnapshot` 已补齐 Translation Term Set 绑定字段；MySQL resource snapshot 会在 en2zh job 创建时绑定当前默认或 admin 指定的 published Translation Term Set 版本。
- operator 创建 job 时禁止传 `term_rule_set_id/version` 和 `translation_term_set_id/version`；admin 可在创建 job 时显式选择历史 published 术语资产版本。
- `/jobs/{job_id}/retry` 默认保留原 job 的术语资产绑定；admin 可通过 `use_latest_term_assets=true` 切到最新默认术语资产，或显式传术语资产版本选择历史 published 版本。
- job accepted/detail response 和 `job_created` event 的 resource snapshot 展示实际绑定的 Term Rule Set 与 Translation Term Set 版本。
- stage 物化资源时按 job snapshot 校验并加载绑定的 Term Rule Set 与 Translation Term Set 版本；默认指针切换不会影响已创建 job 的执行。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

## 阶段 6：翻译链路和 Trace

- [x] Translation Term Set 只作为 glossary context 注入翻译器，不做原文预替换或译文后处理强替换。
- [x] 每次翻译请求只传命中术语，优先 segment/batch 命中，必要时补少量文档级命中。
- [x] 命中规则使用最长优先、`priority` 和稳定排序。
- [x] 支持默认大小写不敏感，单条 `case_sensitive=true` 覆盖。
- [x] 记录实际注入的 glossary 条目到 segment/batch trace。
- [x] trace 不保存完整 PDF 文本、完整 prompt、API key、token 或大段上下文。

阶段 6 收口记录（2026-06-02）：

- DocumentIR 翻译链路只把 Translation Term Set 的命中条目作为 provider glossary context 传入，不做 source term 预替换，也不在译文返回后强行替换 target text。
- 单次 provider 请求会在当前 batch 文本节点中预扫描术语，过滤 disabled、语言方向不匹配和未命中条目；重叠命中按最长优先，其次 `priority`，最后按版本内稳定顺序选择。
- 默认匹配大小写不敏感，单条术语可用 `case_sensitive=true` 切换为精确大小写匹配。
- provider request 携带实际注入 glossary 的 segment/batch trace；审计 call log 只记录术语、位置和短上下文摘要，不写完整 PDF 文本、完整 prompt、API key、token 或大段上下文。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_document_ir_translation
```

## 阶段 7：导入导出 API

- [x] Term Rule Set 支持导入 `term_rules.v2.yaml` 到 draft 或 seed 初始化路径。
- [x] Term Rule Set 支持导出任意历史版本为 `term_rules.v2.yaml`。
- [x] Term Rule Set 支持导出任意历史版本为 legacy runtime YAML。
- [x] Translation Term Set 支持导入 CSV 到 draft 或 seed 初始化路径。
- [x] Translation Term Set 支持导出任意历史版本为 CSV。
- [x] 默认导出当前默认版本；admin 可选择任意历史 `set_id/version`。
- [x] 导出产物附带 `set_id/version/exported_at/exported_by` 元信息，CSV 通过旁路 manifest 表达。

阶段 7 收口记录（2026-06-02）：

- `/term-rule-sets/{set_id}/import` 支持 admin 导入 `term_rules.v2.yaml` 到 draft，或在缺少默认版本时走 seed 初始化；默认 `dedupe=reject` 会把重复 `source_term` 作为导入错误，显式 `dedupe=keep_first` 保留第一条并返回重复报告。
- `/term-rule-sets/{set_id}/export` 默认导出当前默认版本；admin 可传 `version` 导出历史版本，并通过 `format=term_rules_v2|legacy_runtime` 选择标准 YAML 或 legacy runtime YAML。
- `/translation-term-sets/{set_id}/import` 支持 admin 导入 CSV 到 draft，或在缺少默认版本时走 seed 初始化；CSV 兼容基础 seed 四列，并支持 `case_sensitive/status/priority/domain/category/note` 扩展列。
- `/translation-term-sets/{set_id}/export` 默认导出当前默认版本；admin 可传 `version` 导出历史版本 CSV。响应将 CSV 正文和 manifest 分离，manifest 包含 `set_id/language_pair/version/exported_at/exported_by/format`。
- Term Rule Set 和 Translation Term Set 的 import/export 成功动作都会写 audit event；旧 `/term-rules/import`、`/term-rules/export` legacy file/sqlite 兼容接口保持不变。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

## 阶段 8：前端管理面

- [x] job 详情页提供上下标规则 proposal 和翻译术语 proposal 提交入口。
- [x] job 详情页提交 proposal 时自动携带 job/file、绑定版本和可用上下文。
- [x] 独立术语建议页支持列表、筛选、详情、审核、拒绝和 admin 一键审核发布。
- [x] admin 能查看冲突列表和 warning。
- [x] admin 能在创建或重跑 job 时选择历史 published 版本。
- [x] operator UI 不展示发布、设默认、回滚和历史版本选择控件。
- [x] 所有角色都能在 job 详情页看到实际绑定版本。

阶段 8 收口记录（2026-06-02）：

- 任务详情页新增 Term Rule Proposal 和 Translation Term Proposal 提交入口，提交时携带 `source_job_id`、`source_file_id`、绑定版本字段和页面上下文。
- 术语建议页新增翻译术语 proposal 的我的/待审核/全部队列，admin 可 approve、reject 或 approve-and-publish，并展示后端返回的 conflicts/warnings/errors。
- admin 创建 document job 和详情页重试时可选择 Term Rule Set 历史 published version，并可填写 Translation Term Set/version；operator 不渲染这些选择控件。
- job 详情页展示 Term Rule Set、Translation Term Set 和 legacy `term_version_id` 绑定信息。

验证：

```bash
npm run build
```

## 阶段 9：文档、OpenAPI 和验收

- [x] 更新 API 文档：Translation Term Set、Translation Term Proposal、import/export、job version selection。
- [x] 更新开发文档索引，加入设计文档和本任务清单。
- [x] 刷新 `docs/api/openapi.json`。
- [x] 增加端到端测试：operator 提交 proposal，admin approve-and-publish，新 job 使用新默认版本，旧 job 保持旧版本。
- [x] 增加回滚测试：rollback 只切默认指针，不影响已创建 job。
- [x] 增加导入重复测试：默认拒绝，`dedupe=keep_first` 保留第一条并输出报告。
- [x] 增加 legacy runtime YAML 半成功防护测试。

阶段 9 收口记录（2026-06-02）：

- 新增 `docs/api/translation-term-sets.md` 和 `docs/api/translation-term-proposals.md`，并在 `docs/api/jobs.md` 补充 Translation Term Set 版本选择、retry 术语资产重绑和 job resource snapshot 边界。
- `docs/api/manifest.yaml` 已登记 Translation Term Set / Proposal API 文档，`docs/dev/backend-dev-docs-index.md` 已加入设计文档和任务清单入口。
- `docs/api/openapi.json` 已通过 `scripts/ops/export_openapi.py` 刷新。
- 新增端到端测试覆盖 operator 从旧 job 提交 Translation Term Proposal、admin approve-and-publish 后新 job 绑定新默认版本、旧 job 仍保持旧版本。
- 新增 rollback job 绑定测试，确认 Translation Term Set rollback 只切默认指针，不改已创建 job 的 `resource_snapshot`。
- 导入重复测试覆盖默认拒绝和 `dedupe=keep_first` 保留第一条并输出重复报告。
- Term Rule Set 默认切换改为先同步 legacy runtime YAML 再切 SQL 默认指针；同步失败时返回错误、不写 audit、不切默认，避免半成功。
- AI call log 中的 glossary trace 上下文改为长度和 hash 摘要，避免默认审计文件写入完整原文句子；全文仅在 debug archive 开关开启时保存。

验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository tests.test_fastapi_jobs_backend tests.test_document_ir_translation
(cd frontend && npm run build)
```
