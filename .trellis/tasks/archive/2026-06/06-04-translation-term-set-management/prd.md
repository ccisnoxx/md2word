# Translation Term Set Management

## Goal

补齐 Admin 侧 Translation Term Set 轻量管理入口，让管理员能围绕现有 `en2zh` 翻译术语集完成版本查看、CSV 导入/导出、draft 发布、默认版本切换和 rollback。

本任务只进入规划/设计阶段时不实现代码；开始实现前必须先确认本 PRD、design 和 implement 边界。

## Requirements

- 管理对象限定为路线图中的 Translation Term Set，不扩展到完整术语规则 CRUD 工作台。
- 后端复用现有 `TranslationTermSetVersionService` 的 draft、publish、set-default、rollback、import/export 能力；只补必要 API 包装和响应模型。
- 前端新增 Admin-only 配置中心页面，和现有 `TermRuleSetPage` / `TranslationProfilesPage` 保持同类交互风格。
- CSV 是本阶段唯一批量编辑入口：支持导入到 draft、查看导入校验/去重报告、导出默认或指定版本 CSV。
- 版本管理只做查看、发布 draft、设默认、rollback；不做真实文件删除，不做 Translation Term 条目逐行 CRUD，不做复杂 diff / 冲突解决工作台。
- 非 MySQL resource service 部署必须清晰显示不可用，后端保持 `503` 能力门控。
- 不触碰 pdf-mineru 解析、翻译 provider 调用、Word 生成主流程，不重跑主流程。
- API 行为保持向后兼容：现有 import/export 路径和响应不破坏。

## Acceptance Criteria

- [ ] Admin 可以从配置中心进入“翻译术语集”页面；Operator 不看到该入口且不能访问 admin-only route。
- [ ] 页面可以列出 Translation Term Set，查看选中 set 的默认版本、draft 摘要、校验 warnings/errors 和 published versions。
- [ ] Admin 可以把 CSV 导入 draft；重复项按 `reject` / `keep_first` 策略返回明确结果，错误不保存无效 draft。
- [ ] Admin 可以导出当前默认或指定版本 CSV，导出结果包含 manifest 和 CSV 正文。
- [ ] Admin 可以发布 draft、设默认版本、rollback 到已发布版本；rollback 只切默认指针，不生成新版本。
- [ ] 后端在 MySQL resource service 不可用时返回 `503`，缺失 set/version 返回 `404`，非法状态或 CSV 返回 `400`。
- [ ] 不新增真实删除、文件清理、术语逐行 CRUD、完整 diff/冲突解决、pdf-mineru/翻译/Word 主流程调用。
- [ ] 最小验证通过：后端 targeted unittest 覆盖新增管理 API，前端 typecheck/build 通过或明确记录未运行原因。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- 父路线图里该子任务属于 later task：`翻译术语集列表、详情、导入导出、版本、默认、回滚`。
