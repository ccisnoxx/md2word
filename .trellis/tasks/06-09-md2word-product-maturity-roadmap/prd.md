# md2word 产品成熟度路线图规划

## Goal

在不改业务代码、不重新跑 PDF 解析 / 翻译 / Word 生成主流程的前提下，基于当前项目现状，产出 md2word 从“P0 主链路基本跑通”走向“内部产品化工作台”的路线图、页面清单、后端 API / 数据模型缺口清单和可拆 Trellis task 边界。

## Requirements

- 以现有代码和文档为事实基础，避免把已经实现的能力重复规划为“新增能力”。
- 从产品经理、前端负责人、后端负责人、UX、QA / 运维视角共同评估后续完善方向。
- 优先围绕最小闭环拆阶段：任务交付闭环、翻译 QA 闭环、配置治理闭环、文件与运维闭环。
- 明确哪些能力进入近期路线图，哪些能力暂不做。
- 输出页面清单，标记已有、需要增强、建议新增或建议拆分的页面。
- 补充全局导航 / 返回上级体验要求，避免用户进入二级配置或系统页面后只能依赖顶部一级导航离开。
- 输出后端 API / 数据模型清单，区分已有接口、前端未充分使用的接口、真正缺口。
- 输出后续可拆的 Trellis tasks，但本父 task 只做规划，不进入实现。
- 遵守当前限制：不写业务代码，不改 API 合同，不启动转换主流程，不触发外部 provider 调用。

## Current Facts

- `document_jobs` 已支持上传后创建任务、分页列表、状态 / QA 筛选、详情、事件、文件、下载、单 / 批量重试、单 / 批量取消、单 / 批量归档、翻译 QA 状态。
- 前端已有 `/jobs`、`/jobs/:jobId`、`/jobs/:jobId/translation-qa`，覆盖任务工作台、详情和翻译 QA 证据页。
- 前端已有配置中心：模板配置、术语规则集、术语规则检查、翻译配置、翻译术语集、术语 proposal 审核。
- 术语规则存在两层语义：`term-rules` 是 live / legacy 检查与模拟入口，`term-rule-sets` 是 versioned draft / publish / default / rollback 入口。
- 文件与运维已有能力：文件库搜索、文件保留计划、quota dry-run、清理预览 / 执行、清理历史、系统状态、审计日志、运维看板。
- 当前产品成熟度主要缺口不是“完全没有页面或接口”，而是信息架构、任务闭环优先级、页面复杂度拆分、操作路径一致性和少量后端补洞。
- 已确认的 UX 缺口：例如 `/settings/templates` 只有刷新和进入详情，没有返回配置中心 `/settings` 的明确入口；详情页局部有“返回列表”，但项目缺少统一 breadcrumb / 返回上级模式。

## Confirmed Decisions

- 近期产品边界：内部文档转换与配置治理工作台；暂不启动外部客户自助门户。
- 返回上级体验：采用全局 breadcrumb / 层级导航模式，覆盖配置、系统和详情深链。
- 任务归档语义：增加 `unarchive` 恢复误归档任务；不做真实删除，文件删除继续走文件保留 / 清理体系。
- 任务重跑语义：近期支持 `clone/rerun as new job`，不混入 `retry`；原任务保留，新任务记录来源任务和新配置快照。
- 翻译 QA 边界：近期只做证据复核 + 术语 / 问题反馈，不做在线编辑译文或人工改稿后再生成 Word。
- 术语规则 UX：逻辑上合并为“术语工作台”，实现上保留 `当前生效规则` 和 `草稿与发布` 两个子视图 / tabs。
- 文件管理 UX：近期拆分现有文件保留页，至少形成 `文件库`、`容量与策略`、`清理执行` 三个子页面或明确 tabs。
- 任务操作可用性：后端在 `DocumentJobResponse` 增加 `available_actions`，每个 action 带 `enabled` 和 `disabled_reason`；前端可保留轻量兜底判断，但展示以服务端为准。
- 翻译 QA 队列接口：先复用 `GET /api/v1/document-jobs` 的 `translation_qa_status` 筛选新增 `/translation-qa` 前端视图；统计、性能或字段不足被验证后再补专用 summary API。
- 文件删除边界：近期不做按任务删除文件 / 删除任务相关所有文件；真实文件删除继续走文件库、保留策略、preview、confirmation 和 audit。
- 批量上传：暂缓，不进入近期路线图。
- 系统设置边界：近期不做通用“系统设置页”；配置中心管理业务资源版本，系统状态页保持只读，运行配置继续由部署环境管理。
- 翻译结果页边界：不新增另一个“翻译结果页”；保留现有单任务 `translation-qa` 详情页，同时新增 `/translation-qa` 队列入口。
- 任务配置预设：近期不做独立“任务配置预设页”；创建 / clone / rerun 继续基于默认资源版本或显式选择 published 版本。

## Non-Goals

- 不做外部客户门户。
- 不做在线 Word 编辑器或完整文档协同校对。
- 不做在线编辑译文 / 人工修订后再生成 Word。
- 不做按任务删除文件 / 删除任务相关所有文件。
- 不做批量上传。
- 不做前端可写的通用系统设置页。
- 不做与现有 `translation-qa` 详情页重复的独立“翻译结果页”。
- 不做独立“任务配置预设页”或新的任务配置实体。
- 不做复杂 RBAC、动态菜单、权限组后台。
- 不重写现有任务模型或重新设计整套 API envelope。
- 不新增生产依赖或替换前后端技术栈。
- 不在本 task 中实现代码、跑转换主流程、调用外部解析或翻译 provider。

## Acceptance Criteria

- [ ] 形成多角色讨论结论，覆盖产品、前端、后端、UX、QA / 运维视角。
- [ ] 形成推荐产品路线图，按最小闭环优先拆阶段。
- [ ] 形成页面清单，标注已有 / 增强 / 新增 / 暂不做。
- [ ] 形成导航和返回上级策略，覆盖配置中心、系统状态、详情页和深链上下文。
- [ ] 形成后端 API / 数据模型清单，标注已有 / 需补齐 / 暂缓。
- [ ] 形成后续 Trellis task 拆分建议。
- [ ] 每个关键路线决策都有明确推荐答案和待用户拍板问题。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
