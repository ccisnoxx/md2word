# Proposal Review Queue Enhancement Design

## Current State

### Frontend

- `frontend/src/pages/TermProposalsPage.vue`
  - 已同时承载 Term Rule Proposal 和 Translation Term Proposal 的创建、我的列表、Admin 审核队列。
  - 审核动作仍是单条：依赖 `selectedProposal` / `selectedTranslationProposal`。
  - 已支持来源任务链接展示。
  - 已支持从 job detail 带 query 进入新建表单。
  - 还没有：
    - 多选和批量工具条
    - `proposal_id` deep link 自动选中
    - 跳转 Term Rule / Translation Term 治理页的明确 CTA
    - 审核页内统一的冲突解决工作流
- `frontend/src/pages/TermRuleSetPage.vue`
  - 已有 draft CRUD、diff、preflight、publish、set-default、rollback。
  - 已展示“已 approve 待核对 proposals”，但当前只是列表，未把审核页和治理页做成双向聚焦联动。
- `frontend/src/pages/TranslationTermSetPage.vue`
  - 已有 diff、preflight、proposal compatibility、publish、set-default、rollback。
  - 已能跳到 `term-proposals?tab=translation-review&proposal_id=...`，但审核页当前不会消费 `proposal_id`。

### Backend

- Term Rule Proposal
  - `app/domains/term_rules/proposals_router.py`
  - `app/domains/term_rules/proposals_service.py`
  - 已支持 create/list/get/approve/approve-and-publish/reject。
  - 已支持结构化 `409 term_rule_proposal_conflict`。
  - 没有 bulk review contract。
- Translation Term Proposal
  - `app/domains/translation/proposals_router.py`
  - `app/domains/translation/proposals_service.py`
  - 已支持 create/list/get/approve/approve-and-publish/reject。
  - 已支持 `409 translation_term_proposal_conflict`，但审核接口冲突仍主要是字符串列表。
  - 没有 bulk review contract。
- Governance endpoints
  - `app/domains/term_rules/sets_router.py`
    - 已支持 draft diff、preflight、publish，且 preflight 能感知 approved-unpublished proposal 数量。
  - `app/domains/translation/sets_router.py`
    - 已支持 draft diff、preflight、proposal compatibility。

### Data / Persistence

- `TermRuleProposalRecord`
  - 单条 rule 意图：`create / update / disable`
  - 关键证据：`target_rule_snapshot`、`observed_term_rule_set_id/version`
- `TranslationTermProposalRecord`
  - 一条 proposal 内允许多条 `changes`
  - 关键证据：`observed_translation_term_set_id/version`
- 两类 proposal 已是独立持久化模型和独立 repository，不应为“统一队列 UI”而强行合表。

## Key Gaps

1. 批量审核缺口
   - 前端无多选和批量操作。
   - 后端无 bulk approve/reject contract，也没有 partial success result envelope。
   - `approve-and-publish` 直接做 bulk 会引入多次发布/默认指针变更风险。

2. 冲突解决缺口
   - Term Rule Proposal 审核页只展示结构化 conflict 文本，不提供跳治理页的“解决路径”。
   - Translation Term Proposal 治理页已有 compatibility 预览，但审核页没有消费同一视角。
   - Translation approve `409` 与治理页 compatibility finding shape 不统一，不利于复用冲突展示。

3. 深链与联动缺口
   - `TranslationTermSetPage` 已能传 `proposal_id`，但 `TermProposalsPage` 未根据 query 自动定位 proposal。
   - `TermProposalsPage` 当前 query 消费只覆盖 `new` / `translation-new` 等场景，未形成稳定的 review deep-link contract。
   - 审核页到治理页尚无标准 query contract，例如：
     - `set_id`
     - `proposal_id`
     - `source_job_id`
     - `observed_version`

4. 边界说明缺口
   - Term Rule Proposal 与 Translation Term Proposal 的复用目前只体现在同一个页面，边界文字与交互策略仍分散在旧任务文档和页面实现里。
   - 尚未形成“共享 UI 壳层 + 领域专属 contract”的显式设计。

## Recommended Task Split

建议使用 parent + 3 child tasks。

### Parent: `proposal-review-queue-enhancement`

职责：

- 拥有总目标、边界、task map、跨 child 验收标准。
- 负责定义 shared review shell、deep-link contract、bulk semantics 边界。
- 不直接作为实现目标，除非只做少量 planning/documentation 调整。

### Child 1: `proposal-review-queue-shared-shell`

职责：

- 复用 `TermProposalsPage` 建立统一队列壳层。
- 增加多选、批量工具条、bulk result summary、query deep-link、来源任务回链强化。
- 为 Term Rule / Translation 两类审核面板提供共享交互骨架，而不是共享业务逻辑。

独立验收：

- 不改后端 contract 也能先落部分前端交互和 deep-link。
- 页面能从 `proposal_id`、`tab`、`source_job_id` 聚焦到正确记录。

### Child 2: `term-rule-proposal-review-governance-linkage`

职责：

- 扩展 Term Rule Proposal 审核流：
  - bulk approve / reject contract
  - conflict → Term Rule Set 治理页的解决路径
  - 审核页与 `TermRuleSetPage` 的双向回链
- 继续遵守：
  - proposal 是建议
  - Term Rule Set draft CRUD / publish 才是权威治理入口

独立验收：

- 单条/批量审核不破坏现有 `409` 冲突语义。
- 冲突 proposal 可通过治理页处理后回到审核页复核。

### Child 3: `translation-term-proposal-review-governance-linkage`

职责：

- 扩展 Translation Term Proposal 审核流：
  - bulk approve / reject contract
  - 审核页复用 `proposal compatibility` 视角
  - 审核页与 `TranslationTermSetPage` 的双向回链
- 维持 Translation Term Set 页面“治理/发布”与 proposal 页面“审核/决定”分工。

独立验收：

- bulk review 不破坏多 change proposal 语义。
- 审核冲突与 compatibility preview 的字段模型能够复用。

## Boundary And Reuse Strategy

### Term Rule Proposal 边界

- 表达对象：单条术语规则变更建议。
- 领域动作：`create / update / disable`。
- 冲突核心：`target_rule_snapshot` vs 当前 draft rule。
- 权威编辑入口：`TermRuleSetPage` draft rule CRUD + preflight/publish。

### Translation Term Proposal 边界

- 表达对象：一组 translation term entry 变更建议。
- 领域动作：`add / update / delete` changes。
- 冲突核心：observed version vs 当前 draft entries。
- 权威编辑入口：`TranslationTermSetPage` CSV import / diff / preflight / publish / rollback。

### Shared Reuse

- 可以共享的层：
  - `TermProposalsPage` 的页面骨架
  - 列表选择 / 批量工具条 / deep-link / bulk result summary
  - 来源任务回链与治理页跳转模式
  - API 错误展示和冲突摘要 UI 模式
- 不应该强行共享的层：
  - proposal record / repository / service
  - conflict payload schema
  - approve merge logic
  - governance mutation contract

结论：

- 共享“队列工作台体验”，不共享“领域合并内核”。
- 如需统一后端形状，优先统一 bulk result envelope 和 query/deep-link contract，而不是抽象成通用 proposal service。

## Batch Review Recommendation

推荐范围：

- 包含：
  - bulk `approve`
  - bulk `reject`
- 暂不包含：
  - bulk `approve-and-publish`

原因：

- `approve-and-publish` 会触发版本发布和默认指针变更，天然比 `approve/reject` 更重。
- 对 Term Rule Set / Translation Term Set 而言，发布应继续通过治理页 preflight / publish 语义收口，避免队列页隐式承担完整发布工作台职责。
- 保留单条 `approve-and-publish` 作为快捷路径，满足现有能力兼容。

推荐 bulk contract 形状：

- 前端可先按 domain 分别调用 bulk endpoint。
- 返回结构化 per-item 结果，包含：
  - `proposal_id`
  - `ok`
  - `status_code`
  - `error_code`
  - `detail`
  - `proposal`（可选，返回最新状态）
- 允许 partial success。

## Conflict Resolution Recommendation

### Term Rule Proposal

- 审核页展示：
  - conflict type / message
  - 当前 rule
  - proposal snapshot
  - proposal observed version
- 提供 CTA：
  - 打开 `TermRuleSetPage` 对应 set
  - 可附带 `proposal_id` / `target_rule_id` / `source_term`
- 治理页职责：
  - 人工修改 draft
  - 查看 diff/preflight
  - 再回审核页重新判断，不自动 rebase proposal

### Translation Term Proposal

- 审核页展示：
  - proposal changes
  - observed version
  - compatibility/conflict 摘要
- 提供 CTA：
  - 打开 `TranslationTermSetPage` 对应 set
  - 聚焦 proposal compatibility 行
- 推荐后端方向：
  - 尽量让 approve `409` 与 compatibility finding 形状趋同
  - 但不要为此重写已工作的 proposal merge 领域逻辑

## Frontend Scope

- `frontend/src/pages/TermProposalsPage.vue`
  - shared queue shell
  - deep-link query parsing
  - batch action UX
  - domain-specific review panel enhancements
- `frontend/src/components/TermProposalTable.vue`
  - 多选列 / 高亮选中 / 状态辅助列
- `frontend/src/components/TranslationTermProposalTable.vue`
  - 多选列 / 高亮选中 / compatibility summary 入口
- `frontend/src/pages/TermRuleSetPage.vue`
  - 反向跳回 review queue
  - 可选的 proposal context focus
- `frontend/src/pages/TranslationTermSetPage.vue`
  - 反向跳回 review queue
  - 消费 `proposal_id` 以聚焦 compatibility 行或至少高亮
- `frontend/src/api/termProposals.ts`
  - 新增 bulk API wrapper
- `frontend/src/api/types.ts`
  - bulk result types
  - 如需要，补齐 translation conflict / compatibility 复用类型

## Backend API Scope

### Existing APIs To Reuse

- `GET /api/v1/term-rule-proposals`
- `POST /api/v1/term-rule-proposals/{proposal_id}/approve`
- `POST /api/v1/term-rule-proposals/{proposal_id}/approve-and-publish`
- `POST /api/v1/term-rule-proposals/{proposal_id}/reject`
- `GET /api/v1/translation-term-proposals`
- `POST /api/v1/translation-term-proposals/{proposal_id}/approve`
- `POST /api/v1/translation-term-proposals/{proposal_id}/approve-and-publish`
- `POST /api/v1/translation-term-proposals/{proposal_id}/reject`
- `GET /api/v1/term-rule-sets/{set_id}/diff`
- `GET /api/v1/term-rule-sets/{set_id}/preflight`
- `GET /api/v1/translation-term-sets/{set_id}/diff`
- `GET /api/v1/translation-term-sets/{set_id}/preflight`
- `GET /api/v1/translation-term-sets/{set_id}/proposal-compatibility`

### Likely Additions

- `POST /api/v1/term-rule-proposals/bulk-approve`
- `POST /api/v1/term-rule-proposals/bulk-reject`
- `POST /api/v1/translation-term-proposals/bulk-approve`
- `POST /api/v1/translation-term-proposals/bulk-reject`

可选补强：

- Term Rule 读侧兼容性预览 endpoint
  - 仅当审核页必须在 approve 前看到类似 Translation compatibility 视角时再加
  - 优先先复用已有 snapshot/current rule/conflict 结构，不急着新增 generic preview
- Translation approve `409` 结构化增强
  - 仅在前端无法复用 compatibility finding 的情况下推进

## Data Model Scope

不建议新增 proposal 表或统一 proposal 基类表。

可接受的小增量：

- bulk request / response schema
- 可选的 query context 参数
- 如 translation approve `409` 要结构化增强，可只扩 schema，不改持久化字段

## Testing Scope

### Backend

- `tests/test_fastapi_jobs_backend.py`
  - Term Rule bulk approve/reject success / partial success / conflict / auth
  - Translation bulk approve/reject success / partial success / conflict / auth
  - deep-link 需要的 list/filter/query contract 如果涉及后端，也要补 coverage
- `tests/test_openapi_export.py`
  - bulk endpoints / response model / updated 409 schema
- `tests/test_database_job_repository.py`
  - 仅在持久化 contract 改动时补充

### Frontend

- 最小必须：
  - `cd frontend && npm run build`
- 如改动较多，建议增加：
  - query deep-link smoke
  - bulk action smoke
  - governance page round-trip smoke

## Explicitly Out Of Scope This Round

- 完整术语规则 CRUD 扩展。
- Translation Term Set 逐条 CRUD。
- bulk `approve-and-publish`。
- 自动冲突解决、自动 rebase、force approve。
- 真实文件删除。
- pdf-mineru / 翻译 / Word 主流程重跑。

