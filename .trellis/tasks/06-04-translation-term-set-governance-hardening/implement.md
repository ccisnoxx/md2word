# Translation Term Set Governance Hardening Implementation Record

本任务范围已于 2026-06-04 确认并完成实现。未提交 git，未归档 task。

## Classification

治理硬化，包含：

- 文档一致性修正。
- 前端行为不改变核心合同的体验补强。
- 可选的后端边界测试补充。

不属于从零功能开发，也不改变主流程行为。

## Ordered Steps

1. Documentation consistency
   - 更新 `.trellis/tasks/archive/2026-06/06-04-translation-term-set-management/prd.md` checkbox。
   - 更新同目录 `implement.md`，记录实际完成范围、已观察到的测试覆盖和残余缺口。
   - 验证点：归档文档不再声称任务仍停在 planning，且不把未做的 diff/CRUD 写成已完成。

2. Frontend CSV import hardening
   - 修改 `frontend/src/pages/TranslationTermSetPage.vue`。
   - 为 `reject` / `keep_first` 增加简短说明。
   - 将 `lastImportReport.duplicates` 展示为表格或页面内结果区。
   - 导入失败时显示“draft 未保存”的上下文提示。
   - 验证点：不新增逐条 CRUD，不新增文件上传/删除。

3. Frontend default / rollback copy hardening
   - 修改 `TranslationTermSetPage.vue` 的 `setDefault()` 和 `rollback()` 确认文案。
   - rollback 对当前默认版本禁用或改为不可操作提示。
   - 验证点：文案明确只影响默认指针和后续新 job，不改变已有 job snapshot。

4. Error handling experience
   - 复用 `normalizeApiError` 和 `ApiErrorAlert`，优先在页面内派生本页 action hint。
   - 覆盖 `503`、`404`、`400` CSV 校验失败、重复项拒绝、非法状态。
   - 验证点：不引入新的全局错误 envelope。

5. API docs
   - 更新 `docs/api/translation-term-sets.md`：
     - CSV 校验失败不会保存无效 draft。
     - `keep_first` duplicates 报告用于前端展示。
     - set-default/rollback 不改变已有 job resource snapshot。
   - 如 OpenAPI 未变，不重新导出 openapi。

6. Optional backend tests
   - 若实现中发现后端边界缺测，补 `tests/test_fastapi_jobs_backend.py`：
     - invalid CSV header/status/bool/int -> `400`。
     - missing rollback version -> `404`。
   - 验证命令：
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`

7. Frontend verification
   - 运行：
     `npm --prefix frontend run build`
   - 不启动 pdf-mineru、翻译 provider 或 Word 生成流程。

## Review Gates

- Gate 1：用户确认规划范围后，才能 `task.py start`。
- Gate 2：完成文档一致性修正后，确认是否继续前端体验补强。
- Gate 3：前端 build 和 targeted backend unittest 通过或明确记录阻塞后，才进入 finish/archive。

## Rollback Points

- 文档修正可单独提交；如前端补强范围膨胀，停止在文档一致性修正。
- 前端体验改动限定在 `TranslationTermSetPage.vue`；如触发大量布局风险，回退到只改确认文案和错误提示。
- 后端代码默认不改；如果测试补充暴露合同缺陷，再拆小修复。

## Execution Notes

- 已修正 `.trellis/tasks/archive/2026-06/06-04-translation-term-set-management/prd.md`，将已落地的轻量 Translation Term Set 管理能力标记为完成，并补充 completion notes。
- 已修正 `.trellis/tasks/archive/2026-06/06-04-translation-term-set-management/implement.md`，从 planning 清单改为实现记录，列出完成范围、测试证据和残余缺口。
- 已补强 `frontend/src/pages/TranslationTermSetPage.vue`：
  - 文件头改为明确的 File/Purpose 格式。
  - CSV import dialog 增加 `reject` / `keep_first` 策略说明。
  - 最近一次导入结果展示 totals、dedupe 和 duplicates 明细。
  - 页面级错误提示覆盖 `503`、`404`、CSV/重复项类 `400` 和其他 `400`。
  - set-default 与 rollback 确认文案补充 job snapshot 边界。
  - 当前默认版本禁用 rollback。
- 已更新 `docs/api/translation-term-sets.md`：
  - `last_reviewed` 更新为 2026-06-04。
  - 补充 CSV 校验失败不保存 draft。
  - 补充 set-default/rollback 只切默认指针且不改已有 job snapshot。

## Verification Run

- `npm --prefix frontend run build`
  - 结果：通过。
  - 备注：Vite 输出 chunk size warning，属于既有打包体积提示，不阻塞本任务。
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - 结果：通过，`Ran 140 tests in 19.856s`。
  - 备注：测试输出包含预期失败路径日志和 Starlette deprecation warning，不影响测试结果。
- 浏览器轻量验证：
  - URL：`http://127.0.0.1:3000/settings/translation-term-sets`
  - 后端以临时 file backend 启动，预期 Translation Term Set service 不可用。
  - 结果：页面标题、HTTP 503、不可用提示和新增上下文提示均渲染成功。

## Residual Risk

- 未增加前端组件自动化测试；本轮用 typecheck/build 和浏览器轻量验证覆盖。
- 未调整后端 audit 语义；`rollback()` 仍复用 `set_default_version()`，可能同时产生 set_default 和 rollback audit event。当前测试和产品语义接受该行为。
