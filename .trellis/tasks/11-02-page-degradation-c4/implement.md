# 实施计划

1. 基线：`test_page_degradation`、`test_render_page_degradation`、`test_document_job_delivery_state_api`、`test_openapi_export`、异常中心与翻译相关测试模块（实施时按 `rg` 定位）、前端 `npm run test`（相关文件）。
2. 后端降级摘要 → 基础质量模型与派生 → 异常中心 → 翻译跳过合成块与 metadata。
3. 后端测试补充（design 第 6 节）。
4. OpenAPI 快照重新导出。
5. 前端类型、工具函数与页面；前端单测与类型检查。
6. 规格：INPUT-002 降级合同补充展示与翻译行为；如有异常中心/质量相关规格同步。
7. 回归对比基线失败集合。

## 实施结果与验证（2026-11-02）

- 后端：`integrity` 输出 `degraded_pages` 摘要；`base_quality` 新增严格模型 `DegradedPageSummary` 与 `BaseQualityContribution.degraded_pages`；`incidents` 收录降级成功任务（`page_degraded`、P2、不可重试、建议动作与证据列出降级页）；`schemas` 枚举新增 `page_degraded`；`document_ir_translator.extract_translation_items` 跳过合成块；执行层译文 IR `translation.skipped_degraded_page_numbers`。
- 前端：`api/types.ts` 枚举、`utils/incidents.ts` 文案/颜色/优先级/指引、新增 `utils/degradedPages.ts`（含单测）、`JobDetailPage.vue` 降级页提示；`operationsCockpit.test.ts` 夹具补新键。
- OpenAPI：`docs/api/openapi.json` 重新导出，仅新增两处 `page_degraded` 枚举值（`quality_summary` 为自由对象，形状不变）。
- 设计偏差：`degraded_pages` 用 `exclude_if` 只在非空时序列化。首轮回归发现交付状态合同测试逐键固定基础质量形状，空列表会改变所有任务的持久与公开形状；改为非空才出现，未降级任务完全不变，也降低新旧版本并存时旧版本拒读的范围。
- 测试：新增 `tests/test_degraded_page_display.py` 2 项（详情摘要、异常中心收录/筛选/诊断、未降级任务不入队；翻译不送提示段落、提示保持中文、记录跳过页）；`test_render_page_degradation` 补渲染阶段摘要断言。
- 回归：28 个相关模块 604 项失败集合与基线（同一 HEAD 临时 worktree）完全一致。
- 前端：`npm ci` 后 `vue-tsc --noEmit` 通过；`vitest run --dir src` 235 项中 14 项失败，均在 `src/pages/jobRequestRaces.test.ts`（`loadReviewBlocks is not defined`），移除本次详情页改动后同样 14 项失败，属既有问题；未运行 `vite build` 与 Playwright。
