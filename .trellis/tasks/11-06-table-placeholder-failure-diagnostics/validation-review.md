# 独立复核记录

日期：2026-11-06。角色：Trellis check。结论：未发现本任务产品实现的阻塞缺陷；修正一处 Spec 测试证据归属。本轮没有修改产品代码或测试，不改变实施验证的输入。

## Findings (fixed)

- 文件：`.trellis/spec/backend/error-handling.md:170`。
- 问题：必要测试条目把“正常占位路径”归到新增 `test_table_placeholder_failure_context.py`，而该模块的 8 项测试保护失败上下文/API；成功占位证据来自实施记录列出的既有用例。
- 修复：删除该模块条目中的成功路径声明，并明确正常占位由 `test_image_normalization_pipeline.py` 的表格参考图用例、`test_document_ir_mineru_converter_layout.py` 的续表占位用例提供；直接降级回归归到原有两个降级模块。仅修正文档证据索引。

## Findings (not fixed)

没有本次候选变更引入且尚未修复的确认缺陷，没有需要改变设计或扩大范围的建议。

实施首轮误收集历史布局类时出现的 5 errors + 1 failure，保留为既有 `multiple_result_roots` 夹具问题；本次复核未重跑、未修复，也不把它们列成本轮产品通过项。归因与原命令见 `validation-implementation.md`。

## 核对证据

| 复核项 | 代码与测试证据 | 结论 |
|---|---|---|
| 真实失败页与 owner 区分 | `table_placeholder.py:163–228` 读取 `fragment.source_span`；跨页测试用首页 owner `block_0001`、第 2 页失败片段并断言只调用一次裁图 | 源索引仅在投影 +1，不借 owner 首页或未执行片段猜页 |
| 全局与源加载错误 | `table_placeholder.py:149–158,180–188,210–215,232–236` 在数量/累计预算、源加载/身份及最终绑定验证处预附文档上下文；`failure_context.py:8` 仅首次附加 | 外层片段捕获不会覆盖文档级定位；无可靠页时为 null |
| 原异常及策略 | 捕获仅限 `TablePlaceholderError`，原样 `raise`；converter 仍给原异常附原报告；`_failure_policy.py` 只换共同属性常量导入；`execution.py:3397` 后的既有降级条件仍排除 `TablePlaceholderError` | 不改变分类、安全消息、重试、取消、转换结果或降级条件 |
| 报告优先级与代数 | `failure_diagnostic.py:20–38` 保持既有当前代最新候选事件选择；报告不足以形成 fatal 诊断时仅回退同一事件；对应新增投影用例覆盖有效 fatal、无效报告及旧代 | 有效 MinerU fatal 优先，不跨事件或跨代借位置 |
| 隐私及受控值 | `evidence.py:799–834` 仅增加一个操作枚举值；四类原因码、ID、索引与页数依据过滤未放宽；Worker 测试覆盖私密字段、危险 ID、非法索引及原因码 | 事件不新增正文、HTML、bbox、URL、路径或任意异常正文 |
| 页数与依赖 | 片段准备复用 `integrity.build_page_counts`；新增共同 helper 仅依赖 `typing.Any`，renderer 导入保留原公开名称；既有渲染测试仍从 renderer 导入属性常量 | 不另建页数公式或引入反向 renderer 依赖；仅给失败诊断提供总页数及依据 |
| 真实事件/API | 新模块使用合成 ZIP 和真实 converter/eager Worker/测试持久化/HTTP API；仅注入不会调用的 crop provider，断言真实几何验证先失败 | 详情与异常诊断相同，列表仍 null，JSON 往返及失败状态有实际断言 |
| UI 与 API 合同 | schema、前端类型、OpenAPI 三处来源均增加 `table_placeholder`；formatter 及概览 SSR 有新用例；`JobDiagnosticsPanel.vue:293` 与 `IncidentTriagePage.vue:711` 调同一共享摘要并开启技术详情 | 新来源的原因、页码、块/操作接线一致；不声称三个页面都运行了组件 SSR |
| OpenAPI 快照差异 | 当前 diff 仅诊断模型；`git show HEAD:app/domains/document_jobs/schemas.py` 已含 `source_page_count/page_count_basis` | 两个页数字段是补齐旧快照，不是本轮新 API 字段 |
| Spec 与语言 | 两份 Spec 只同步本诊断的来源、优先级、页码和证据；新增及实质改动的注释/docstring 为中文 | 本轮复核只更正上述测试索引；未新增产品日志或异常文案 |

## Verification

- Lint：仓库没有配置独立 Python/前端 lint 命令或配置文件，本项不适用，不记作 lint 已通过。本轮实际执行 `git diff --check`，修正文档后退出码 0。
- TypeCheck：通过，复用实施者 `npx vue-tsc --noEmit` 的退出码 0；前端源码、配置和依赖未因复核变化。未配置独立后端类型检查。
- Tests：通过，复用实施记录的 34 个不同诊断/安全测试（首轮 33 项后，源加载器改动仅重跑新增模块 8 项）、成功与直接降级回归 23/23、前端 27/27。复核读取测试实现与真实调用路径，没有重复运行应用测试。
- OpenAPI：通过，复用当前导出/check 的 `180 paths / 393 schemas`、`ok=True / changed=False`；复核后模型、导出脚本及快照输入未变化。
- 新执行检查：候选 diff/工作树、实现与测试逐路径核对、HEAD 模型字段比对、共享 UI 调用点检查、lint 配置入口检查、`git diff --check`。未运行全仓测试、build、浏览器 smoke 或发布聚合门禁。

## 边界

本地证据不等于生产部署或真实 Poppler/Word 客户端验收。没有启动实际服务、访问生产、重试或回填历史任务，也没有提交、推送、部署、归档或变更任务状态。新增上下文只会在包含本实现的执行器发生新失败时产生；历史缺证据记录仍允许 null。
