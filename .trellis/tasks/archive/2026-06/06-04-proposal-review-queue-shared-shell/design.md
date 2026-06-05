# Proposal Review Queue Shared Shell Design

## Goal

把 `frontend/src/pages/TermProposalsPage.vue` 补成稳定的共享审核壳层，让后续两个
domain child task 可以直接在此基础上接 bulk action 与治理联动，而不需要再返工
路由、聚焦和列表选中态。

本 child task 只做 shared shell，不改 backend contract，不改审核语义。

## Current State

- `TermProposalsPage.vue`
  - 只把 route query 用于 `tab=new`、`tab=translation-new` 和少量 tab 初始化。
  - `tab=review` 目前不会被 `initialActiveTab()` / `applyRouteProposalContext()` 正确消费。
  - 页面不会消费 `proposal_id`，治理页回链到审核页时无法自动定位目标 proposal。
  - `loadActiveTab()` 每次都会清空 `selectedProposal` / `selectedTranslationProposal`，刷新后选中态丢失。
  - 当前 route watcher 和 tab-change 各自驱动加载，缺少明确的“谁决定当前 focus”的边界。
- `TermProposalTable.vue`
  - 只有 `select` 事件，没有 prop-controlled 当前选中行视觉状态。
- `TranslationTermProposalTable.vue`
  - 同样只有 `select` 事件，没有当前选中行视觉状态。

## Scope

本 child task 只解决四件事：

1. 明确 review shell 的 route / deep-link contract
2. 让 queue 加载后可稳定恢复 focus，必要时从 `review` 回退到 `all`
3. 让两个 proposal table 支持统一的“当前选中行”契约
4. 保证现有任务上下文新建入口和来源任务回链不退化

## Non-goals

- 不新增 backend API
- 不引入 bulk approve / reject
- 不实现治理页 CTA
- 不把 `TermProposalsPage` 抽成新的 framework 或 generic queue page
- 不自动修正跨 domain 的错误 deep-link，例如 term `tab` 搭配 translation `proposal_id`

## Design Decisions

### 1. Keep `TermProposalsPage` as the shell

不新增页面，不引入抽象层。

原因：

- 现有页面已经同时承载两类 proposal 的 form、mine、all、review 入口。
- 当前痛点是状态同步和聚焦恢复，不是页面边界错误。
- 过早抽象会把 Term Rule / Translation 的差异藏进 generic 层，反而增加后续 child task 的实现成本。

### 2. Canonical query contract

本 child task 明确支持以下 query：

- `tab`
  - 允许值：
    - `mine`
    - `new`
    - `review`
    - `all`
    - `translation-mine`
    - `translation-new`
    - `translation-review`
    - `translation-all`
  - 未知值回退到默认：
    - admin 默认 `review`
    - operator 默认 `mine`
- `proposal_id`
  - 仅在 queue tab 生效：
    - `mine`
    - `review`
    - `all`
    - `translation-mine`
    - `translation-review`
    - `translation-all`
  - 在 form tab (`new` / `translation-new`) 中忽略
- 现有 proposal form context query 保持不变
  - `source_job_id`
  - `source_file_id`
  - `observed_term_rule_set_id`
  - `observed_term_rule_version`
  - `observed_translation_term_set_id`
  - `observed_translation_term_version`

约束：

- shared-shell 阶段只“消费” query，不负责把每一次 tab 点击都回写到 URL。
- route query 是外部入口契约，不是整页状态的唯一来源。

### 3. Tab classification helpers

在 `TermProposalsPage.vue` 内显式拆分 tab 类型，避免字符串判断散落：

- `isTermFormTab(tab)`
- `isTranslationFormTab(tab)`
- `isTermQueueTab(tab)`
- `isTranslationQueueTab(tab)`
- `isReviewTab(tab)`
- `fallbackTabFor(tab)`

目标：

- 把 `review` 支持补齐
- 让 fallback 规则、列表加载和 selection 恢复使用同一组判断
- 避免后续 child task 再复制一遍 tab/domain 逻辑

### 4. Focus resolution algorithm

页面内部采用“一次加载周期内解析 focus”的顺序，不额外引入全局状态机。

#### 4.1 输入

- `requestedTab = query.tab || defaultTab`
- `routeProposalId = query.proposal_id || ""`
- `rememberedSelectedId`
  - term domain: `selectedTermProposalId`
  - translation domain: `selectedTranslationProposalId`

#### 4.2 加载顺序

1. route watcher 触发时先执行 `applyRouteProposalContext()`
2. 若当前 tab 是 form tab：
   - 维持现有 form context 写入
   - 不消费 `proposal_id`
   - `new` 仍加载 reference data
3. 若当前 tab 是 queue tab：
   - 加载该 tab 对应的列表
   - 计算本轮的目标 focus id：
     - 优先 `routeProposalId`
     - 否则使用同 domain 的 `rememberedSelectedId`
   - 若没有 focus id：
     - 保持列表正常渲染
     - 清空当前 domain 的 detail panel
   - 若 focus id 在当前列表中：
     - 直接选中
   - 若 focus id 不在当前列表中，且满足以下全部条件：
     - 当前 tab 是 `review` 或 `translation-review`
     - 本轮 focus 来源是 route `proposal_id`
     - 当前用户是 admin
     - 尚未做过 fallback
     - 则回退到：
       - `review -> all`
       - `translation-review -> translation-all`
     - 再次加载列表并尝试选中
   - 若 fallback 后仍找不到：
     - 清空当前 detail panel
     - 展示轻量 inline 提示，不抛异常

#### 4.3 Fallback boundary

只允许以下 fallback：

- `review -> all`
- `translation-review -> translation-all`

明确不做：

- `mine -> all`
- 跨 domain fallback
- 自动切回 form tab

原因：

- `mine` 涉及 ownership 语义，不应为了找 proposal 自动扩大视野。
- 跨 domain 自动纠错会掩盖错误 deep-link。
- 共享壳层阶段只解决治理回链场景，避免引入模糊规则。

### 5. Selection state model

保留当前“selected object + detail panel”的结构，但补一个稳定的 id 层：

- `selectedProposal`
- `selectedTranslationProposal`
- `selectedTermProposalId`
- `selectedTranslationProposalId`

规则：

- 用户点击表格行时，同时更新对象和对应的 selected id
- 列表刷新后，通过 selected id 重新在新列表里恢复对象
- 切换到另一 domain 时，不主动清空另一侧 remembered id
- 若目标 id 在新列表中不存在，则只清空当前 detail object，不影响另一 domain 的 remembered id

这样做的原因：

- 不需要把整个 detail panel 改成纯 computed lookup
- 后续 bulk child task 仍可复用 selected id 做单条操作和多选共存

### 6. Table visual contract

两个表格组件统一增加轻量 prop：

- `selectedId?: string | null`

行为约束：

- prop 只负责视觉高亮，不负责驱动 selection 逻辑
- 仍维持已有 `select` 事件
- 不在本 child task 中加入 checkbox、多选数组或 batch toolbar

实现建议：

- 使用 `el-table` 的 `row-class-name` 根据 `row.id === selectedId` 输出稳定 class
- 在 scoped style 中给选中行加浅背景和边界强调

### 7. Inline focus notice

当 route deep-link 指向的 proposal 不在当前 queue，且 fallback 后仍不可见时，页面应给一个
轻量 inline notice，而不是静默失败。

约束：

- 使用页内状态，例如 `focusNotice`
- 不使用持续弹 toast，避免刷新或 watcher 重跑时反复打扰
- notice 只说明“未定位到目标 proposal / 已回退到全部列表”等状态，不承载 conflict 语义

### 8. Non-regression boundary

必须保持以下行为不变：

- `JobDetailPage` 进入 `tab=new` 时，proposal form 仍带入来源任务上下文
- `JobDetailPage` 进入 `tab=translation-new` 时，translation proposal form 仍带入来源任务上下文
- proposal 详情中的来源任务 `router-link` 不变
- 现有 approve / reject / approve-and-publish 按钮和语义不变

## Frontend Files To Change

1. `frontend/src/pages/TermProposalsPage.vue`
   - 增加 queue tab / form tab 分类 helper
   - 修正 `review` query 支持
   - 增加 route `proposal_id` 读取与 focus resolution
   - 增加 per-domain selected id 和记忆恢复
   - 增加 `focusNotice` inline 提示
   - 让 refresh 与 route deep-link 使用同一套恢复逻辑
2. `frontend/src/components/TermProposalTable.vue`
   - 新增 `selectedId` prop
   - 根据 `selectedId` 高亮当前选中行
3. `frontend/src/components/TranslationTermProposalTable.vue`
   - 新增 `selectedId` prop
   - 根据 `selectedId` 高亮当前选中行

明确不改：

- `frontend/src/router/index.ts`
- `frontend/src/api/termProposals.ts`
- 任意 backend 文件

## API Reuse

No backend API change.

仅复用现有：

- `GET /api/v1/term-rule-proposals`
- `GET /api/v1/term-rule-proposals/{proposal_id}`
- `GET /api/v1/translation-term-proposals`
- `GET /api/v1/translation-term-proposals/{proposal_id}`

其中 `get(proposalId)` 只作为 fallback 可见性确认与单条详情恢复的补充手段；shared-shell
阶段不新增聚合接口。

## Risks

- route watcher、tab change、fallback load 叠加后可能造成重复加载；实现时要确保一次 route 解析最多触发一次 fallback。
- 如果 deep-link 指向的 proposal 在刷新瞬间状态变化，页面可能从 `review` 回退到 `all`；这是预期行为，应通过 inline notice 解释。
- 如果 route 中 tab/domain 与 proposal id 不匹配，本阶段只保证“不报错且不给出错误 selection”，不做自动纠正。

## Minimal Verification Checklist

- `cd frontend && npm run build`
- 手工 smoke
  - `/term-proposals?tab=review&proposal_id=<pending-term-rule-proposal-id>`
    - 打开 term review 队列并自动选中目标 proposal
  - `/term-proposals?tab=review&proposal_id=<approved-term-rule-proposal-id>`
    - 自动回退到 `all` 并选中目标 proposal
  - `/term-proposals?tab=translation-review&proposal_id=<pending-translation-proposal-id>`
    - 打开 translation review 队列并自动选中目标 proposal
  - `/term-proposals?tab=translation-review&proposal_id=<approved-translation-proposal-id>`
    - 自动回退到 `translation-all` 并选中目标 proposal
  - 在任一 queue 里手动点选一条 proposal 后点击“刷新”
    - 选中行和 detail panel 保持
  - 从任务详情页进入 `tab=new` / `tab=translation-new`
    - 来源任务上下文仍正确带入
