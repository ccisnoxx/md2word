# Translation QA Review Loop

## Goal

围绕现有单任务 Translation QA 证据页，补齐 QA 队列入口和“证据复核 -> 术语 / 问题反馈”的闭环，让审核人员可以快速找到待复核任务、进入证据页、记录 QA 结论，并把术语问题沉淀到后续规则治理流程。

本任务近期不做在线编辑译文、不做人工改译后重新生成 Word，也不新增重复的“翻译结果页”。

## Requirements

- 新增 `/translation-qa` 前端队列入口，作为 QA 专用视图。
- 队列近期复用现有 `GET /api/v1/document-jobs` 列表接口，通过 `translation_qa_status` 等已有筛选能力拿数据。
- 暂不新增 `/translation-qa/summary` 或专用聚合 API；只有页面落地后证明列表统计、聚合、筛选性能或字段不足，再补后端 summary API。
- 用户从 `/translation-qa` 队列进入现有单任务 `/jobs/:jobId/translation-qa` 证据页。
- 保留现有单任务 QA 详情页作为翻译证据页，不新增另一个“翻译结果页”。
- 单任务 QA 详情页聚焦证据复核：
  - 原文 / AI 翻译 / 最终译文片段对照。
  - 术语命中、术语规则、术语 trace。
  - AI 调用摘要、失败或低置信证据。
  - QA 状态、问题类型、审核备注。
- 支持从 QA 问题进入术语反馈 / proposal 流程，便于后续在术语工作台中治理。
- 不向普通审核用户暴露完整 prompt / response 原文；如需诊断，仅展示必要摘要或受权限控制的诊断入口。
- QA 队列与任务工作台共享任务状态和动作语义；任务取消、retry、clone/rerun、archive/unarchive 不在本页面重新定义。
- 近期不做批量上传、不做在线编辑译文、不做人工编辑后重跑 Word。

## Acceptance Criteria

- [ ] 审核人员可以从 `/translation-qa` 找到未复核、已通过、有问题等 QA 状态的 en2zh 文档任务。
- [ ] 队列中的任务可以跳转到 `/jobs/:jobId/translation-qa`，并能从详情页通过 breadcrumb 返回 QA 队列或任务层级。
- [ ] 单任务 QA 页可以查看片段证据、术语 trace、AI 调用摘要，并保存 QA 状态、问题类型和备注。
- [ ] QA 中发现的术语问题可以进入现有或规划中的 proposal / 术语工作台流程，不要求本任务完成规则发布。
- [ ] 队列首版不依赖新后端 summary API；仅在有明确字段或性能缺口时记录后续后端任务。
- [ ] 不实现在线编辑译文、不实现人工改译后重新生成 Word、不新增独立翻译结果页。
- [ ] 本任务进入实现前需要补 `design.md` 和 `implement.md`，明确页面结构、复用接口、状态字段、权限和验收方式。

## Notes

- Parent roadmap: `.trellis/tasks/06-09-md2word-product-maturity-roadmap/`.
- 当前阶段为 planning；不要在本任务中重新跑 PDF-MinerU 解析 / 翻译 / Word 生成主流程。
