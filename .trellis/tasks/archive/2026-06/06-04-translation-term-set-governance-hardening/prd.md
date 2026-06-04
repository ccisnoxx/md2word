# Translation Term Set Governance Hardening

## Goal

在既有 Translation Term Set 轻量管理能力上补齐治理硬化，聚焦 Admin 日常可安全操作的 CSV 导入/导出、默认版本切换、rollback 语义确认、错误处理体验，以及归档 Trellis 文档与实际实现状态的一致性。

本任务属于产品成熟化路线图 Phase 2：Configuration Governance。范围已于 2026-06-04 确认并进入实现。

## Requirements

- 复用现有 `TranslationTermSetPage`、`translationTermSetsApi`、`TranslationTermSetVersionService`、`docs/api/translation-term-sets.md` 和 targeted unittest。
- 保持现有 Translation Term Set 管理合同：list/detail/draft/import/export/publish/set-default/rollback。
- CSV 导入体验必须明确：
  - `dedupe=reject` 是默认策略，重复项应阻断导入并展示可操作错误。
  - `dedupe=keep_first` 会保留第一条、丢弃后续重复行，并展示重复行报告。
  - CSV 校验失败、字段缺失、字段类型错误、language_pair 不匹配时不保存无效 draft。
- CSV 导出体验必须明确默认版本和指定版本的差异，导出结果包含 manifest 与 CSV 正文，前端允许复制和浏览器侧下载。
- 默认版本切换必须明确只影响后续新建 job 的默认绑定，不改变既有 job 的 resource snapshot。
- rollback 必须明确语义：只把默认指针切到指定 published version，不生成新版本，不删除或修改历史版本。
- 错误处理体验覆盖：
  - `503`：MySQL resource service 未启用。
  - `404`：set 或 version 不存在。
  - `400`：非法状态、CSV 校验失败、重复项默认拒绝、非法 target/dedupe。
  - `403`：Admin-only mutation 权限不足。
- 归档文档一致性必须修正：
  - `.trellis/tasks/archive/2026-06/06-04-translation-term-set-management/prd.md` checkbox 与实际实现对齐。
  - 同一归档任务的 `implement.md` 不再停留在“planning 未执行”口径，应记录实际完成范围、验证证据和残余缺口。
- 不触碰 pdf-mineru 解析、翻译 provider、生成 Word 主流程，不重跑主流程。
- 不做真实文件删除，不暴露 archive/delete Translation Term Set 操作。
- 不做逐条 Translation Term CRUD。
- 不做完整 diff / 冲突解决工作台；如需要，后续拆独立任务。
- 不破坏现有 job 创建/重试时绑定 Translation Term Set 版本的行为。

## Acceptance Criteria

- [x] 产出并确认治理硬化差距清单，区分文档一致性修正和代码补强。
- [x] 归档 Trellis 文档与实际实现状态一致，PRD checkbox 和 implement 记录不再误导后续规划。
- [x] 前端 CSV 导入区域能解释 `reject` / `keep_first`，并在成功导入后展示 totals 和重复项明细。
- [x] 前端对 `400` CSV 校验失败、重复项拒绝、`404`、`503` 有上下文明确的提示，不只显示通用错误。
- [x] 前端默认切换和 rollback 的确认文案明确“只影响默认指针/后续新 job，不改既有 job 快照”，并避免对当前默认版本执行无意义 rollback。
- [x] 后端合同不改变现有成功响应形状；如补充测试，仅覆盖现有合同的边界语义。
- [x] API 文档保持和实际行为一致，必要时补充前端可呈现的错误语义说明。
- [x] 最小验证通过或记录未运行原因：
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - `npm --prefix frontend run build`

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- 当前代码已比归档任务文档更完整，本任务不是从零实现 Translation Term Set 管理页，而是做治理体验硬化和文档一致性收口。
