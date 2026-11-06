# 事实研究与边界

## 线上已观察证据（2026-11-06，只读）

- `docjob_914c18d077b8`、`docjob_257b5b444a8f`（11 月 3 日）、`docjob_6deeb88b244b`（10 月 30 日）：ir_converting / document_ir_failed；安全消息是 `table_placeholder_geometry_invalid`；当前代 stage_failed 附 mineru_validation，can_convert=true、first_fatal=null、fatal_count=0，没有 failure_context；投影为 null。
- 前两条验证报告有第 53 页的非致命 empty_table_html；第三条有第 3–6 页的非致命同类告警。它们是已识别来源问题，不能证明随后的几何失败发生页，禁止用于补写历史失败定位。
- 另外 3 个 MinerU 内容块失败已经可在真实页面显示第 5/6 页或 11/12 页，表明现有 UI 和验证来源投影链路正常。
- 六条均为此次前端上线前的历史任务。本轮没有重试或修改生产记录。

## 代码定位

| 位置 | 证据 | 影响 |
|---|---|---|
| table_placeholder.py:25 | 异常仅保存 code 和固定消息 | 缺源页/块信息 |
| table_placeholder.py:136、153 | prepare_placeholders 遍历可信片段；source_span 含页索引 | 在真实发生点补上下文，不从 owner 猜页 |
| table_placeholder.py:145–195 | 全局数量、源身份、逐片段裁切/解码、累计预算 | 必须区分文档范围与片段范围 |
| mineru_converter.py:359–363 | 捕获占位异常并附 validation_report | 报告可能通过，错误仍真实发生 |
| _failure_policy.py:80–101 | 通用上下文注入原因码，再统一白名单过滤 | 可复用现有事件路径 |
| renderer/evidence.py:799–834 | 已允许四个占位原因码；缺占位 operation_kind | 只新增固定操作值，不放宽字段 |
| failure_diagnostic.py:13–36、68 | 当前代事件选择；非致命报告提前返回 null；操作来源写死渲染 | 补 fallback 和来源区分 |
| schemas.py:109–128 | 来源枚举仅验证/渲染，其余字段足够 | 扩展来源并同步 OpenAPI/前端 |
| word_renderer.py:84–91 | 通用附上下文 helper，保持内层位置 | 搬至中立模块避免 IR 依赖 renderer |
| integrity.py:52–68 | 既有页数唯一计算函数 | 复用，不再建页数算法 |
| frontend/src/utils/failureDiagnostic.ts:95–137 | 共享摘要和位置渲染；四类原因映射已存在 | 只适配新操作来源技术定位 |

## 相关测试与最小复用

- `tests/test_document_job_failure_diagnostic.py`：当前代、未知字段、页级/文档级投影及真实 eager API 链路。
- `tests/test_render_failure_context.py`：保持异常类型、操作上下文、白名单和事件→API。
- `tests/test_worker_failure_policy.py`、`tests/test_worker_failure_message.py`：固定错误分类、安全消息及证据过滤。
- `tests/test_image_normalization_pipeline.py`：表格占位参考图成功链路；`test_page_degradation.py`、`test_render_page_degradation.py` 为相关降级回归入口。
- `frontend/src/utils/failureDiagnostic.test.ts` 及上一任务的组件 SSR 测试：共享展示，不增加新的诊断页面。
- `scripts/ops/export_openapi.py`：在临时测试路径导出，不启动服务；响应枚举变更须同步当前快照。

## 结构决策

应用 clean-code-design：只移动确有两个服务复用的既有小 helper，继续让异常发生点拥有定位、_failure_policy 拥有安全证据、failure_diagnostic 拥有读侧投影、前端拥有中文文案。不新增通用错误框架、持久化层或第三方依赖。

本能力已有完整仓库模式，问题在内部链路丢字段与选择分支，不涉及陌生协议或库 API；无需外部生态研究。
