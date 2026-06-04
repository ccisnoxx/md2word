# md2word 产品成熟化路线图规划

## Goal

把已经跑通的 pdf-mineru 解析、翻译、Word 生成主流程，产品化为内部 Operator/Admin 可日常使用的工作台。

第一阶段聚焦“任务工作台成熟化”：让内部用户能完成上传、监控、查看详情、下载、失败重试、取消、归档、从任务上下文提交术语问题、管理员审核与基础系统状态查看的最小闭环。

本任务只做规划，不实现代码，不重新运行 pdf-mineru 解析、翻译、生成 Word 主流程。

## Requirements

- 核心用户角色
  - Operator：上传 PDF、创建任务、查看状态和日志、下载结果、对失败或质量问题提交术语/翻译术语提案。
  - Admin：具备 Operator 能力，并可在创建/重试任务时显式选择模板、术语规则集、翻译术语集、翻译配置，审核提案，查看系统状态。
  - QA/Ops：关注任务失败原因、事件日志、系统健康、归档语义和可追溯性；第一阶段不提供危险运维操作。
- 第一阶段必须补齐
  - 单任务完整闭环：列表、筛选、详情、事件日志、文件/结果区、下载、失败重试、取消、归档。
  - 轻量批量能力：批量归档终态任务、批量重试失败任务；可以先由前端逐个调用已有单任务 API。
  - 角色化任务配置：Admin 可显式选择资源版本；Operator 使用默认配置并查看只读摘要。
  - 任务上下文提案：从任务详情提交术语规则提案或翻译术语提案，并进入现有审核流。
  - 轻量系统状态页：Admin 只读查看 readiness、metrics、worker/backend/storage/resource 状态。
  - 信息架构：主导航应暴露任务工作台、配置中心、提案审核、系统状态等内部工作入口。
- 第一阶段不做
  - 外部客户自助门户。
  - 完整术语规则 CRUD 工作台。
  - 独立文件管理页、跨任务文件库、物理文件删除、存储空间管理。
  - 独立翻译结果页或段落对照质检工作台。
  - 在线修改系统环境配置、管理 worker、告警配置、全量操作审计页面。
  - 强制杀掉 MinerU 上游任务的承诺；取消语义先定义为停止后续处理/标记取消。

## Acceptance Criteria

- [x] 产出多角色讨论结论，明确 PM、前端、后端、UX、QA/Ops 的一致方向和主要取舍。
- [x] 产出推荐产品路线图，按最小闭环优先拆出第一阶段和后续阶段。
- [x] 产出页面清单，标明新增页面、已有页面补强点、角色权限和不做项。
- [x] 产出后端 API / 数据模型清单，标明已有能力、需要新增/补强能力、可轻量实现项。
- [x] 产出第一阶段最小可做范围，包含前端页面、后端接口、数据结构、验收标准。
- [x] 产出后续可拆分的 Trellis task 清单。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- 已确认的第一阶段边界：
  - 内部 Operator/Admin 工作台成熟化。
  - 不把完整术语规则 CRUD 工作台放入第一阶段。
  - 单任务闭环完整，批量能力轻量，不做真实删除。
  - Admin 显式选择配置，Operator 使用默认配置并查看摘要。
  - 只做轻量只读系统状态页。
  - 不做独立文件管理页，文件/结果区放在任务详情内。
