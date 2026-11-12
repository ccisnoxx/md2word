# 设计（父任务）

父任务只负责跨子任务的边界与集成，具体设计见各子任务 `design.md`。

## 1. 现状证据（基线 `0c9a7923`）

| 区域 | 证据 |
|---|---|
| 组合根 | `app/main.py` 485 行；`build_runtime()` 单函数手工装配约 40 个服务，并内联 6 处启动 bootstrap 副作用 |
| 任务编排 | `app/domains/document_jobs/service.py` 3829 行，`DocumentJobService` 50+ 公开方法、约 190 个方法；生产调用方仅 `router.py`（46 处）与 `incidents.py`（14 处） |
| `_host` 耦合 | `mineru/render/translation_execution.py` 共 208 处 `self._host.*`；私有方法调用 `_record_event` 36、`_mark_failed` 33、`_get_uploaded_file` 6、`_fail_stage_attempt` 6、`_mark_timed_out_if_needed` 6、`_document_ir_layout_metadata` 3、`_mark_succeeded` 1 |
| Renderer/Evidence | `renderer/evidence.py` 1208 行，31 个导入方；`DocumentIRWordRenderer` 由 3 个 Mixin 拼装（text 683、table 767、word 589 行），`render_to_result` 单方法 138 行 |
| Vue 页面 | `OpsDashboardPage` 3004、`FileRetentionPage` 2329、`JobsPage` 2106、`IncidentTriagePage` 2059 行；已有 `features/job-detail/` 拆分先例 |

## 2. 文件归属（避免并行冲突）

| 子任务 | 独占写入范围 |
|---|---|
| sr-1 | `app/domains/document_jobs/{execution,mineru_execution,render_execution,translation_execution}.py`、新增 `execution_support.py`、相关测试调用点 |
| sr-2 | `app/domains/document_jobs/service.py`、新增 `use_cases/`、`router.py`、`incidents*.py`、`app/core/runtime.py` 中 `document_job_service` 字段、相关测试 |
| sr-3 | `app/main.py`、新增 `app/composition/`、`app/api/middleware.py`、`scripts/ops/run_file_retention_cleanup_readonly.py`（仅导入） |
| sr-4 | `app/services/renderer/**`、evidence 的全部导入方（仅改 import 行） |
| sr-5 | `frontend/src/pages/{OpsDashboard,FileRetention,Jobs,IncidentTriage}Page.vue`、新增 `frontend/src/features/<page>/` |

冲突点：sr-4 需要修改 `execution.py`、`render_execution.py`、`router.py` 等文件中的 evidence import 行，和 sr-1/sr-2 重叠。处理方式：后合入的一方 rebase 时只解决 import 行冲突，不夹带其他改动。

## 3. 统一的"行为不变"判定

- 后端：子任务列出的定向 `unittest` 模块全部通过；OpenAPI 导出一致。
- 渲染：同一批 MinerU fixture 在重构前后生成的 DOCX，解压后逐个 XML part 字节一致（见 sr-4）。
- 前端：`npm run test:unit`、`npm run build`、相关 Playwright smoke 通过；DOM 中的 `aria-label` 和 smoke 依赖的选择器不变。

## 4. 回滚

每个子任务按"一个职责一次提交"推进，任何一步都可以单独 `git revert`。子任务之间只通过已合入的代码产生依赖，不共享未提交的状态。
