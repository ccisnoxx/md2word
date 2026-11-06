# 实施与定向验证记录

日期：2026-11-06。本记录只证明本地合成输入、内存/eager Worker、测试持久化和 API/SSR 合同；未启动实际服务、访问生产、重试历史任务、提交或推送。

## 实际改动

- `app/services/failure_context.py` 接管原有附上下文 helper 与属性名；renderer 保留导入名称，Worker 切到共同 owner。仍只附加一次、保留原异常对象和类型。
- `table_placeholder.prepare_placeholders` 只捕获 `TablePlaceholderError`。片段异常用原始 `source_span.page_index` 和 render owner 块 ID；跨页 owner 不作为源页。占位数量、累计字节、源文件加载/身份/hash 以及最终整体验证异常预先附文档级上下文。页数复用 `build_page_counts`。
- 事件白名单仅增加 `table_placeholder` 操作值；四类原因码、安全字段规则及失败分类/重试/降级策略保持。
- 当前代、同一最新可选事件内，有效 MinerU fatal 仍优先；不存在有效报告则尝试操作上下文。新增公开来源 `table_placeholder`，不新增字段/端点。
- 前端同步来源类型及就近中文说明；共享 formatter 支持占位块/操作技术定位。概览已有 SSR 增加该来源；诊断页签 `JobDiagnosticsPanel.vue` 与异常抽屉 `IncidentTriagePage.vue` 已核对均调用 `jobFailureSummaryLines(..., true)`，由共享 formatter 测试覆盖，没有声称三处都做了组件 SSR。
- OpenAPI 当前导出同步该来源、说明，并补齐本次前源码已经存在而历史快照遗漏的 `source_page_count` / `page_count_basis`。这两个字段不是本轮新增 API 字段。
- 所有新增/实质修改的注释、docstring 和测试说明使用中文；不增加产品日志，不改变既有安全异常文案。

## 通过的验证

1. 失败链路与安全合同：

```bash
.venv/bin/python -m unittest tests.test_table_placeholder_failure_context tests.test_document_job_failure_diagnostic tests.test_render_failure_context tests.test_worker_failure_policy tests.test_worker_failure_message
```

首次完成一致实现后 **33/33 通过**。随后核对正式 `_load_placeholder_source`，确认它在返回 source 前会检查对象身份/大小/hash；补充源加载器错误的文档级捕获及回归后，只重跑受影响模块：

```bash
.venv/bin/python -m unittest tests.test_table_placeholder_failure_context
```

**8/8 通过**（原 7 项加 1 项）。其余 26 项输入未变化、结果复用，失败链路共覆盖 **34 个不同测试**。

真实合成 ZIP 无页面尺寸信息，在真实 `prepare_placeholders.validate_geometry` 失败；裁图 provider 明确未调用。经过真实 converter → eager Worker → 事件存储 → HTTP 详情/异常诊断，断言 `failed / ir_converting / document_ir_failed`、`source=table_placeholder`、实际第 2 页，以及同事件 `can_convert=true / first_fatal=null`。列表诊断仍为 null。

其他新增合同覆盖：页 0→第 1 页；跨页续表 owner 在首页而失败片段在第 2 页，下一片段未执行；未知页、数量/累计预算、源 ID/hash、源加载器失败为文档级；四类错误码；保留原异常身份与内层上下文；事件 JSON 往返；私密字段/非法 ID/页索引过滤；有效 MinerU 致命报告优先；旧代隔离和原事件选择规则。

2. 成功与直接相关降级回归：

```bash
.venv/bin/python -m unittest tests.test_image_normalization_pipeline.ImageNormalizationPipelineTests.test_webp_table_reference_placeholder_is_written_as_png tests.test_page_degradation.PageDegradationConverterTests tests.test_render_page_degradation tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_rejects_placeholder_without_image_or_pdf_source
```

**23/23 通过**。选择占位参考图成功、真实续表占位成功/缺来源失败、converter 页降级与渲染降级模块；未扩大到全仓。最后新增的 source_loader 捕获只改变异常元数据，不改变这些成功/降级路径，复用已通过结果。

3. 前端：

```bash
cd frontend
npx vitest run src/utils/failureDiagnostic.test.ts src/features/job-detail/JobOverviewPanel.test.ts
npx vue-tsc --noEmit
```

Vitest **27/27 通过**；vue-tsc **退出码 0**。Vitest 后仅为新增测试的 `failed_stage` 添加字面量类型断言，以及修正 API 类型中文注释，不改变测试运行行为，未重复 Vitest。不涉及打包行为，未运行 build 或浏览器 smoke。

4. API/差异：

```bash
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python scripts/ops/export_openapi.py --check --no-diff
git diff --check
```

导出及对比通过；**180 paths / 393 schemas**，检查 `ok=True / changed=False`。差异空白检查通过。

## 首次验证的问题与归因

- 新测试最初直接导入 `MinerUToDocumentIRLayoutTests` 作为 ZIP 夹具来源，unittest 意外收集了该既有类全部 30 项。那次共执行 63 项，其中既有类有 **5 errors + 1 failure**，均在未修改的 `find_content_list` 上因夹具含多个结果根触发 `mineru_content_list_ambiguous / multiple_result_roots`，尚未进入本轮占位代码。改为模块导入复用夹具，避免扩大收集；不修改这些历史用例或放宽包校验。
- 同次本任务 eager API 测试 1 项失败：测试 runtime 默认没有 crop provider，因此先得到 `table_placeholder_source_unavailable`。为目标几何用例注入不会被调用的 provider，并断言零调用；实际几何验证仍为真实实现。修正后定向通过。
- 初次 vue-tsc 发现新增测试对象 `failed_stage` 被推断成普通 string；增加 `as const` 后通过，产品类型无需放宽。
- 命令出现既有 Starlette/httpx 弃用警告。降级超时测试包含原有预期异常日志；测试通过，未借本轮维护无关异常日志行为。

## 复核与未验证边界

请独立复核：跨页 source span 与 owner 区分；源加载器/全局预算不被外层覆盖；现有白名单与新来源枚举；有效 fatal 优先和同代事件选择；helper 移动的兼容导入。

本轮不证明生产 API/Worker/前端已同步部署，不证明真实 Poppler 裁图或真实 Word 客户端验收；不回填旧任务。新上下文仅在本实现生效后新发生的对应失败中产生。没有数据库 schema、持久化状态机或原始转换算法修改。
