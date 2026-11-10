# 设计

基线 `main@80032c25`。迁出集合、耦合与测试引用见 [research/current-state.md](research/current-state.md)。整体做法沿用翻译批次提取（`.trellis/tasks/archive/2026-11/11-10-translation-batch-extraction/design.md`），这里只写本次的差异与新风险。

## 1. 目标结构

```text
app/domains/document_jobs/
  execution.py               DocumentJobExecutionService：任务状态推进、MinerU、回调、IR、失败收口、事件
  translation_execution.py   TranslationBatchExecution（已有）
  render_execution.py        WordRenderExecution：渲染、页面降级、质量检查、上传收尾、表格占位符读取
```

宿主 `__init__` 构造 `WordRenderExecution` 并保存为 `self.rendering`，与 `self.translation_batches` 并列。构造签名不变，`app/main.py` 和 `tests/test_fastapi_jobs_backend.py` 的直接构造不用改。

## 2. 两个方向的边界

协作者到宿主，只允许以下 6 个方法，且在调用时经 `self._host.<名字>` 查找：

| 方法 | 用途 |
|---|---|
| `_record_event` | 写任务事件 |
| `_mark_failed` | 任务失败收口 |
| `_mark_succeeded` | 任务成功终态 |
| `_mark_timed_out_if_needed` | 超时收口 |
| `_get_uploaded_file` | 读取已上传文件记录 |
| `_document_ir_layout_metadata` | IR 诊断元数据 |

`_mark_succeeded` 目前只有渲染段调用，但它写的是任务终态，和 `_mark_failed` 一样归宿主所有，所以不迁出。

宿主到协作者有 2 个入口：

- `execute_job` → `self.rendering._render_and_save_word`
- `_convert_and_save_document_ir` 中的 `placeholder_source_loader=lambda: self.rendering._load_placeholder_source(job)`

`render_execution.py` 只在 `TYPE_CHECKING` 下导入宿主类型。

## 3. 依赖归属（阶段二后）

| 依赖 | 持有者 |
|---|---|
| `word_renderer`、`template_read_service`、`word_preview_service` | 仅渲染协作者 |
| `job_resource_snapshot_service` | 渲染协作者与翻译协作者；宿主不再持有 |
| `settings`、`job_repository`、`file_repository`、`file_service`、`document_ir_service`、`logger` | 宿主与渲染协作者，引用同一对象 |
| 其余（事件仓储、回调存储、MinerU 等） | 仅宿主 |

`word_preview_service` 的默认构造仍写在宿主 `__init__` 里（它需要 `event_repository`，渲染协作者不持有该依赖）。宿主算出实例后只传给协作者，自己不保存。

共用依赖从翻译段的 4 个增加到 6 个。这一取舍的风险在于：今后只替换其中一侧会让两边悄然分叉。目前测试只在夹具里替换 `job_resource_snapshot_service`，阶段二后宿主已没有这个属性，夹具改为同步两个协作者。

## 4. 分两阶段

### 阶段一：纯搬移

- 新建 `render_execution.py`，定义 `WordRenderExecutionMixin`，17 个方法原样移入。
- 宿主改为 `class DocumentJobExecutionService(WordRenderExecutionMixin)`，导入按实际使用拆分，只被渲染段使用的导入从宿主删除。
- 测试只改 4 处模块路径补丁（research §6），从 `app.domains.document_jobs.execution.<名字>` 改为 `app.domains.document_jobs.render_execution.<名字>`。

这是与翻译段的主要差异：翻译段阶段一不改任何测试，本次阶段一必须改补丁目标。原因是迁出方法的全局名在新模块的命名空间里解析，按旧模块路径打补丁已经拦截不到。宿主不再导入这两个名字，所以遗漏的补丁会报 `AttributeError`，不会悄悄失效；验收脚本另外核对宿主模块中确实不存在 `ensure_renderer_integrity`、`build_renderer_evidence`。

### 阶段二：改为协作者

- Mixin 改为 `WordRenderExecution`，增加 `__init__(host, *, settings, job_repository, file_repository, file_service, document_ir_service, job_resource_snapshot_service, template_read_service, word_renderer, word_preview_service)`；`logger` 在构造中取 `logging.getLogger("business")`，与宿主为同一个对象。
- 方法体内对 6 个宿主方法的 20 处调用，接收者从 `self` 改为 `self._host`。
- 宿主去掉 Mixin 基类和 4 个渲染依赖属性，2 处入口改为 `self.rendering.<名字>`。
- 测试迁移访问路径（§6）。

## 5. 关键取舍

**占位符读取组随渲染迁出。** 它的 7 个方法中有 6 个只被渲染使用，IR 只经 lambda 用了 `_load_placeholder_source` 一个入口。如果留在宿主，渲染协作者需要额外回调 4 个宿主方法，白名单会从 6 个扩大到 10 个。备选是把它单独做成第三个小协作者，但它只有 96 行、只有一个外部入口，不值得多一层。这一项列为待评审决策。

**`_mark_succeeded` 留在宿主。** 理由见 §2。

**不拆 `_render_and_save_word`。** 229 行的方法里有 prepared result 恢复、降级循环和证据生成，内部拆分涉及控制流，不能用 AST 等价核对，留给后续任务。

**其余取舍与翻译段相同**：使用宿主引用而不是注入回调，不为宿主定义 Protocol，不改名，不保留转发方法，构造签名不变。

## 6. 测试迁移（阶段二）

| 原写法 | 新写法 |
|---|---|
| `execution._render_and_save_word(...)` 等迁出方法 | `execution.rendering.<同名>(...)` |
| `patch.object(execution, "_render_and_save_word", …)` | `patch.object(execution.rendering, "_render_and_save_word", …)` |
| `execution.word_renderer`、`template_read_service`、`word_preview_service` 的读取与 `patch.object(execution.word_renderer, …)` | `execution.rendering.<同名>` |
| `runtime.document_job_execution_service.word_renderer = …` | `runtime.document_job_execution_service.rendering.word_renderer = …` |
| 夹具对 `job_resource_snapshot_service` 的宿主赋值与翻译同步 | 同一对象赋给 `execution.rendering` 与 `execution.translation_batches` |
| `patch.object(execution, "execute_job" / "_mark_failed" / "_record_event")` | 不变 |

规模：迁出方法 20 处，渲染依赖 36 处，夹具 2 行，共约 58 处，再加阶段一的 4 处模块路径补丁。实施前以检索结果为准。涉及的文件有 `test_document_job_result_persistence.py`、`test_document_job_execution_stages.py`、`test_rnd503_dependency_integration.py`、`test_fastapi_jobs_backend.py`、`test_degraded_page_display.py`、`test_translation_integrity_execution.py`、`test_translation_batch_failure_semantics.py` 和夹具 `document_job_list_query_v2_publication_fixtures.py`。

静默失效只可能来自赋值，已知 3 处（research §6）。读取和 `patch.object` 遇到不存在的属性会报 `AttributeError`。AC-6 的全仓检索覆盖这两类写法。

## 7. 兼容与回退

- 没有数据迁移，Celery 任务名和参数不变，新旧 Worker 混跑不会产生格式分歧。
- 回退以阶段为单位。
- 实施前如果 `main` 上的渲染段有新改动（例如降级策略后续项），先合入，再重取基线和度量。
