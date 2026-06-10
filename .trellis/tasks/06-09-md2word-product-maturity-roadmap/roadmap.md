# md2word 产品成熟度路线图草稿

## Scope

本路线图基于 2026-06-09 读取到的仓库现状，只做规划讨论，不实现代码，不触发 PDF 解析、翻译或 Word 生成主流程。

## Current Product Shape

md2word 当前已经具备内部工作台雏形：

- 任务工作台：`/jobs` 支持上传、列表、状态筛选、QA 筛选、搜索、下载、重试、取消、归档、批量重试、批量归档。
- 任务详情：`/jobs/:jobId` 支持状态、阶段、失败信息、文件、事件流、请求快照、重试配置策略、术语建议入口。
- 翻译 QA：`/jobs/:jobId/translation-qa` 支持任务级复核状态、片段证据、术语 trace 和 AI call 摘要。
- 配置中心：模板、术语规则集、术语规则检查、翻译配置、翻译术语集已形成 admin 工作区。
- 运维与文件：系统状态、运维看板、审计日志、文件保留计划已有页面。

因此后续重点不是“从零补齐页面”，而是把已有能力收口成清晰的内部产品体验。

## Confirmed Decisions

- Product boundary: 近期 1-2 个阶段只做内部文档转换与配置治理工作台，暂不启动外部客户自助门户。
- Navigation UX: 采用全局 breadcrumb / 层级导航模式，不只是在少数页面临时增加返回按钮。
- Document job archive semantics: 增加 `unarchive` 作为误归档恢复能力，但不做真实删除；文件删除继续走文件保留 / 清理体系。
- Rerun semantics: 近期支持 `clone/rerun as new job`，但不混入 `retry`；原任务保留，新任务记录来源任务和新配置。
- Translation QA scope: 近期只做证据复核 + 术语 / 问题反馈，不做在线编辑译文或人工改稿后再生成 Word。
- Terminology UX: 逻辑上合并为“术语工作台”，实现上保留两个子视图 / tabs：`当前生效规则` 和 `草稿与发布`。
- File management UX: 近期拆分现有 `/system-status/file-retention`，至少形成 `文件库`、`容量与策略`、`清理执行` 三个子页面或明确 tabs。
- Job action availability: `DocumentJobResponse` 增加 `available_actions`，每个 action 带 `enabled` 和 `disabled_reason`；前端可保留轻量兜底，但展示以服务端为准。
- Translation QA queue API: 先复用 `GET /api/v1/document-jobs` 的 `translation_qa_status` 筛选新增 `/translation-qa` 前端视图；等统计、性能或字段不足被验证后再补专用 summary API。
- File deletion boundary: 近期不做按任务删除文件 / 删除任务相关所有文件；真实文件删除继续走文件库、retention policy、preview、confirmation 和 audit。
- Batch upload: 暂缓，不进入近期路线图；等单任务工作台、失败处理和 QA 队列稳定后再评估。
- System settings: 近期不做通用“系统设置页”；配置中心管理业务资源版本，系统状态保持只读，运行配置继续由部署环境管理。
- Translation result page: 不新增另一个“翻译结果页”；保留现有单任务 `translation-qa` 详情页，同时新增 `/translation-qa` 队列入口。
- Job config presets: 近期不做独立“任务配置预设页”；创建 / clone / rerun 继续基于默认资源版本或显式选择 published 版本。

## Multi-Role Conclusions

### Product Manager

- 推荐核心用户先锁定内部角色：文档交付 operator、配置 admin、翻译 QA reviewer、技术运营 admin。
- 近期核心场景应是“上传 PDF -> 追踪任务 -> 处理失败 -> 下载交付 -> QA / 术语反馈 -> 配置治理”。
- MVP 之后优先补齐任务交付体验和 QA / 配置闭环，暂不做外部客户自助门户。
- 不建议近期做复杂在线 Word 编辑、公开账号体系、计费、多租户客户控制台。

### Frontend Lead

- 现有页面数量已经足够多，优先级应转向信息架构和页面拆分。
- `/jobs` 应成为日常操作主入口，补齐当前 UI 未覆盖但后端已有的能力：批量取消、创建时间筛选、运行中 / 失败快捷视图。
- `/jobs/:jobId` 应减少“所有信息堆在同一滚动页”的压力，逐步形成概览、文件、事件、诊断、上下文建议等 tabs 或分区。
- 翻译 QA 应从单任务详情页扩展出队列页，但先做 review queue，不做译文在线编辑。
- 文件保留页过重，建议拆成文件库、容量 / quota、危险清理三个操作层级。

### Backend Lead

- `document_jobs` 的主操作接口已经较完整：create/list/detail/events/files/retry/cancel/archive/download/config-summary/bulk actions。
- 近期后端应避免重复发明新任务模型，优先补小缺口：
  - 已确认下发 `available_actions` / `disabled_reason`，减少前端重复判断。
  - QA 队列需要更好的 summary / mode / QA 聚合字段时再补。
  - 已确认“重跑成功任务”或“按新配置重新生成”使用 `clone/rerun as new job`，不滥用 retry。
  - 已确认需要补 `unarchive` 恢复误归档任务；仍不做真实删除。
- 术语规则应坚持 versioned draft/publish 是生产修改入口，live `term-rules` 主要作为检查和模拟入口。

### UX

- 当前最大 UX 风险是“内部后台能力很多，但用户不知道从哪开始”。
- 推荐一级导航保持克制：任务、QA、配置、系统。配置与系统内部再分层。
- 已确认缺口：配置和系统二级页面缺少统一返回上级 / breadcrumb。典型例子是 `/settings/templates` 不能明确返回 `/settings`，只能依赖顶部导航或浏览器返回。
- 已确认采用统一的页面层级导航模式，而不是每个页面临时加一个按钮。
- 高风险操作应保留 preview、reason、confirmation phrase、audit 证据，不为省步骤而弱化安全边界。
- 对 operator 隐藏或禁用 admin-only 动作时，需要明确原因，而不是只让按钮消失。

### QA / Ops

- QA 视角最需要：失败任务队列、翻译 QA 队列、可追溯证据、结果下载、术语反馈链路。
- Ops 视角最需要：运行中卡住、失败队列、stage spool、审计、文件容量和过期清理。
- 不建议把 raw runtime logs 暴露给普通 operator；任务事件和 trace_id 足够作为第一层排障入口。

## Recommended Product Roadmap

Confirmed priority order:

1. `document-job-workbench-closure`
2. `translation-qa-review-loop`
3. `config-governance-ux-consolidation`
4. `file-library-retention-ux-split`
5. `product-navigation-and-role-model` as a cross-cutting follow-up if not absorbed by earlier phases.

### Phase 1: Document Job Workbench Closure

Goal: 让日常交付人员能稳定处理直接 PDF -> Word 任务。

Frontend:

- 增强 `/jobs`：批量取消、创建时间范围筛选、失败 / 运行中快捷视图、归档视图提示。
- 增强 `/jobs/:jobId`：详情分区更清晰，事件流可筛选 level / stage，文件下载入口更明确。
- 保留单文件上传；批量上传暂缓。

Backend:

- 优先复用已有 `document-jobs` 接口。
- 补 `available_actions` 字段，每个 action 返回 `enabled` 和 `disabled_reason`，覆盖 download、retry、cancel、archive、unarchive、clone/rerun 等动作。
- 补 `unarchive` 元数据操作，用于恢复误归档任务。
- 补 `clone/rerun` 创建新任务语义：原任务不变，新任务继承 source file，可选择新配置，并在 request snapshot / audit 中记录来源任务。
- 暂不补真实删除任务；文件删除继续走文件保留 / 清理体系。
- 不新增任务配置预设实体，避免形成第二套配置 source of truth。

Acceptance:

- operator 可以在任务工作台完成上传、追踪、失败处理、下载、归档。
- admin 可以批量处理失败或运行中任务，且所有高风险动作有确认和 audit。

### Phase 2: Translation QA Review Loop

Goal: 将 `en2zh_pdf_to_word` 从实验功能整理成可 review 的内部质量流程。

Frontend:

- 新增 `/translation-qa` 队列页或在 `/jobs` 提供 QA 专用视图。
- 不新增独立“翻译结果页”；从 QA 队列进入现有 `/jobs/:jobId/translation-qa` 单任务证据页。
- 支持按 `translation_qa_status`、失败/成功、更新时间筛选。
- 单任务 QA 页继续只做证据复核，不做在线改译文。
- 从 QA 问题一键跳转提交翻译术语建议。

Backend:

- 复用 `GET /document-jobs?translation_qa_status=...` 和 `GET/PATCH /translation-qa`。
- 如队列统计、性能或字段不足，再补 QA summary 聚合；不提前引入第二套任务查询合同。
- 不把全文 prompt/response 暴露给普通用户。

Acceptance:

- reviewer 能筛出未复核任务，查看证据，保存通过 / 需修正 / 阻塞结论。
- 术语问题能流入 proposal，不直接修改生产术语。
- QA 结论和术语建议能驱动后续配置治理及 clone/rerun，但不在 QA 页直接改译文。

### Phase 3: Configuration Governance Consolidation

Goal: 让配置变更有草稿、校验、发布、回滚和审计闭环。

Frontend:

- 保持 `/settings` 作为配置入口。
- 为配置二级页统一补 breadcrumb / 返回配置中心入口，例如 `/settings/templates`、`/settings/term-rule-sets`、`/settings/translation-profiles`。
- 术语规则逻辑上合并为“术语工作台”，但保留两个子视图：`当前生效规则` 用于 live 检查 / 模拟，`草稿与发布` 用于 draft rule CRUD、diff、preflight、proposal publish linkage。
- 翻译术语集近期继续 CSV draft import/export；逐行编辑作为后续增强。

Backend:

- 继续以 versioned resource service 为真源。
- 不开放 legacy live store 直写。
- 只有发布 / set-default / rollback 同步 runtime YAML。

Acceptance:

- admin 明确知道当前编辑的是 draft，不会误以为已生效。
- publish 前能看到 blocking finding、diff 和相关 proposal。

### Phase 4: File Library And Ops Split

Goal: 把现有文件保留与运维页面拆成更容易操作的管理区。

Frontend:

- 将当前 `/system-status/file-retention` 拆成三个子页面或明确 tabs：
  - `文件库`：只读搜索、定位文件、跳转任务。
  - `容量与策略`：storage usage、quota dry-run、quota ops summary、retention policies。
  - `清理执行`：mark-expired、delete-preview、delete-expired、cleanup run、history。
- 系统状态页保留只读 overview，不承载复杂操作。
- 不新增前端可写的通用系统设置页；provider、S3、quota、worker、MinerU 等运行配置继续走部署 / 运维流程。

Backend:

- 复用现有 Files API。
- 不新增“按任务一键删除所有文件”；删除继续按文件 metadata、retention policy、preview、confirmation 和 audit 处理。
- S3 真实删除继续受 gated integration 控制。

Acceptance:

- admin 能定位文件和容量问题。
- 危险清理操作必须 preview -> reason -> confirmation -> audit。

### Phase 5: Productization Later

Only after internal workflow is stable:

- 批量上传。
- 成功任务 rerun / clone with new config。
- 外部客户门户。
- 在线结果对比 / Word 校对。
- 在线编辑译文 / 人工修订后再生成 Word。
- 复杂组织和权限模型。

## Page Inventory

| Page | Status | Recommendation |
|---|---|---|
| `/login` | existing | 保持。 |
| `/jobs` | existing | Phase 1 增强。 |
| `/jobs/:jobId` | existing | Phase 1 重整分区 / tabs。 |
| `/jobs/:jobId/translation-qa` | existing | Phase 2 保留为单任务翻译 QA / 证据详情页；不另建重复“翻译结果页”。 |
| `/translation-qa` | missing | Phase 2 新增 QA 队列入口，进入现有单任务证据页。 |
| `/term-proposals` | existing | Phase 2/3 串联 QA 和配置治理。 |
| `/settings` | existing | 保持配置入口。 |
| `/settings/templates` | existing | 增加返回配置中心 / breadcrumb。 |
| `/settings/templates/:templateId` | existing | 保留返回列表，并纳入 breadcrumb；后续增强验证任务体验。 |
| `/settings/term-rule-sets` | existing | 纳入“术语工作台”的 `草稿与发布` 子视图，作为术语生产修改主入口。 |
| `/settings/term-rules` | existing | 纳入“术语工作台”的 `当前生效规则` 子视图，只做 live 检查和模拟。 |
| `/settings/translation-profiles` | existing | 保持基础字段版本管理，增加返回配置中心 / breadcrumb。 |
| `/settings/translation-term-sets` | existing | 后续考虑逐行编辑，增加返回配置中心 / breadcrumb。 |
| `/system-status` | existing | 保持只读 overview。 |
| `/system-status/ops-dashboard` | existing | 保持 admin 运维入口。 |
| `/system-status/audit-events` | existing | 保持。 |
| `/system-status/file-retention` | existing but overloaded | Phase 4 拆分为 `文件库` / `容量与策略` / `清理执行` 子页面或 tabs。 |

## API And Data Model Inventory

| Domain | Existing | Potential Gap |
|---|---|---|
| Document Jobs | create/list/detail/events/files/translation-qa/retry/cancel/archive/download/bulk/config-summary | available_actions, unarchive and clone/rerun confirmed; QA queue summary deferred until evidence |
| Files | upload/content/get/library/search/retention/quota/delete/cleanup/history | product-level file library route split; task-scoped delete explicitly deferred |
| Term Rule Sets | draft rule CRUD/diff/preflight/import/export/publish/default/rollback | UX consolidation, not backend rewrite |
| Term Rules Live | list/get/categories/simulate/import/export legacy | keep read-only/check path in versioned mode |
| Translation Term Sets | list/draft/diff/preflight/import/export/publish/default/rollback/proposal compatibility | future row-level edit if CSV workflow becomes bottleneck |
| Translation Profiles | list/detail/draft/publish/default/rollback | prompt body editing intentionally deferred |
| Audit | list/export/detail | enough for current governance |
| Ops / Health | readiness/metrics/ops alerts/integration controls | keep real destructive actions gated |

## Decisions Needed

1. Product boundary: internal workbench only, or start external portal path? Confirmed: internal workbench only for the next 1-2 phases.
2. Job archive semantics: keep archive as one-way hide, or add unarchive / delete? Confirmed: add unarchive, no real delete.
3. Rerun semantics: only retry failed jobs, or support rerun successful jobs with new config? Confirmed: support clone/rerun as a new job, separate from retry.
4. Translation QA scope: evidence review only, or move toward online editing? Confirmed: evidence review plus terminology/problem feedback only; no online translation editing for now.
5. Term rule UX: keep live check and draft edit as separate pages, or merge under one terminology hub? Confirmed: merge logically into terminology workbench, retain live-check and draft-publish subviews/tabs.
6. File management: split existing file retention page now, or keep one admin-heavy page until ops stabilizes? Confirmed: split into file library, capacity/policy, cleanup execution.
7. Navigation UX: use global breadcrumb / parent return pattern, or only add local back buttons to selected pages? Confirmed: global breadcrumb / parent return pattern.
