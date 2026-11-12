# document_jobs 高复杂度模块拆解与应用层接口

## Goal

在不改变任何外部行为（HTTP 合同、持久化格式、批次生命周期语义、事件与审计）的前提下，继续拆解 `app/domains/document_jobs` 中的高复杂度模块，并建立稳定的应用层接口，使 router、用例、执行协作者与基础设施适配器之间只经公开方法交互，不再相互读取私有成员。

## 现状证据（基线 `30081252`，2026-11-12）

| 文件 | 行数 | 大小 | 主要问题 |
|---|---|---|---|
| `translation_execution.py` | 2056 | 101 KB | 单类 `TranslationBatchExecution` 同时承担计划、安装、调度/租约、Provider 调用、失败/拆分、完整性绑定、制品登记、代次收口 |
| `router.py` | 1418 | 64 KB | 含下载令牌签名/校验、预签名与预览 TTL 计算；直接访问 `runtime.document_job_execution_service.translation_batches` |
| `schemas.py` | 1557 | 57 KB | 约 125 个模型混在一个文件，横跨任务、翻译 QA、配置、incident、质量评审、发布 |
| `preview.py` | 709 | 47 KB | 预览执行服务与“当前预览证据读取”工具函数混在一起 |
| `render_execution.py` | 698 | 44 KB | 渲染编排、占位图依赖、已有结果查找/校验混在一起 |

跨对象私有访问（生产代码）：

- `execution.py` → `translation_batches._read_translation_source / _ensure_translation_batches_and_enqueue / _finalize_translation_generation`、`mineru._run_mineru_parse / _process_replayable_callback_messages`、`rendering._render_and_save_word / _load_placeholder_source`。
- `router.py` → `runtime.document_job_execution_service.translation_batches.summarize_translation_generation`（HTTP 层直达执行层）。
- 测试约 25 处直接调用或 patch 上述私有方法。

## Requirements

1. `translation_execution.py` 按职责拆为包：计划生成、批次安装、调度与代次收口、Provider 调用、失败与拆分、完整性绑定、制品持久化；`TranslationBatchExecution` 保留为唯一对外门面。
2. router 不再访问执行服务；翻译批次视图、下载授权/令牌由用例提供。router 只负责 HTTP 解析、URL 外部化、审计记录与响应映射（与 `directory-structure.md` 一致）。
3. `router.py` 按资源拆分子路由与响应构造；挂载路径、路由顺序、`operation_id`、响应模型不变。
4. `schemas.py` 按资源拆为包，模型定义逐字迁移，不改字段、校验、别名或 `model_config`。
5. `preview.py`、`render_execution.py` 拆出证据读取 / 占位图 / 结果校验组件，宿主经公开方法调用。
6. 生产代码不存在跨对象私有成员访问（`obj._x` 其中 `obj` 不是 `self`/`cls`）；测试改为使用公开方法或组件级公开方法。
7. 同步更新 `.trellis/spec/backend/directory-structure.md` 与 `translation-batch-lifecycle.md` 中的 owner 描述。

## Non-Goals

- 不改业务规则、状态机、仓储端口、数据库结构、OpenAPI 合同、前端。
- 不拆 `review_content.py`、`execution.py`、`mineru_execution.py` 内部结构（仅把被外部调用的私有方法改为公开名）。
- 不把用例返回的 Pydantic 响应模型改造成独立 DTO（见 design.md「待决策」）。
- 不引入 DI 容器、插件、策略框架等额外抽象。

## Acceptance Criteria

- [ ] 拆分前后 `app.openapi()` 输出逐字节相同。
- [ ] 受影响测试套件结果与基线一致（基线失败项单独记录，不因本任务扩大修复）。
- [ ] `rg` 检查：`app/` 下无 `\b(?!self|cls)\w+\._[a-z]\w*\(` 形式的跨对象私有调用落在 document_jobs 执行协作者上；router 不引用 `document_job_execution_service`。
- [ ] 拆分后本任务触及的模块单文件不超过约 600 行。
- [ ] 相关 spec 已更新；新增/改动的注释与 docstring 为中文。
