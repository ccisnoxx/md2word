# 设计

基线 `main@d45e46e1`。迁出集合、耦合度量和测试耦合见 [research/current-state.md](research/current-state.md)。

## 1. 目标结构

```text
app/domains/document_jobs/
  execution.py               DocumentJobExecutionService：任务状态推进、MinerU、IR、渲染、失败收口、事件
  translation_execution.py   TranslationBatchExecution：根计划、领取与租约、Provider 调用、失败与拆分、汇合回填
  workflow.py                不变：树校验与纯 generation reducer
  repository.py              不变：批次原子端口
```

`DocumentJobExecutionService` 在自己的 `__init__` 里构造 `TranslationBatchExecution` 并保存为 `self.translation_batches`。构造签名不变，`app/main.py:195` 和 `tests/test_fastapi_jobs_backend.py:494` 两处构造不用改。

## 2. 两个方向的边界

协作者到宿主，只允许 7 个方法，且每次调用时经 `self._host.<名字>` 查找：

| 方法 | 用途 |
|---|---|
| `_record_event` | 写任务事件 |
| `_mark_failed` | 任务失败收口 |
| `_fail_stage_attempt` | 按阶段快照归类失败 |
| `_mark_timed_out_if_needed` | 超时收口 |
| `execute_job` | 翻译校验通过后续跑渲染 |
| `_get_uploaded_file` | 读取已上传文件记录 |
| `_document_ir_layout_metadata` | IR 诊断元数据 |

前五个是任务级状态与事件的收口，owner 本来就是宿主。后两个是借用的读取辅助，本任务不动它们的归属。

宿主到协作者：

- 内部入口 3 个：`_ensure_translation_batches_and_enqueue`、`_finalize_translation_generation`、`_read_translation_source`。
- 公开方法 3 个：`execute_translation_batch`、`summarize_translation_generation`、`set_translation_batch_task_queue`。

`translation_execution.py` 不在运行时导入 `execution.py`。宿主类型和队列 Protocol 只在 `TYPE_CHECKING` 下导入，避免循环导入。

## 3. 依赖归属

| 依赖 | 阶段二后的持有者 |
|---|---|
| `translation_batch_repository`、`document_ir_translation_service`、`translation_audit_service`、`term_version_service`、`translation_batch_task_queue` | 仅协作者 |
| `settings`、`job_repository`、`file_service`、`job_resource_snapshot_service` | 宿主和协作者各持同一对象的引用 |
| 其余（事件仓储、回调存储、文件仓储、MinerU、渲染、预览等） | 仅宿主 |

共用的 4 个依赖在生产装配中构造后不再替换，两边引用同一对象。测试里有 1 处构造后替换共用依赖（`tests/document_job_list_query_v2_publication_fixtures.py:151`），阶段二需要读懂该夹具的意图后决定改哪一侧，不能机械替换。

## 4. 分两阶段

单次改动如果同时搬移 1888 行又改写 56 个调用点，diff 会显示为整段删除加整段新增，评审者看不出方法体里改了什么。这段代码承载租约、代次和失败收口的并发语义，所以把“搬移”和“改接线”分开，让每一步都能用机械手段核对。

### 阶段一：纯搬移

- 新建 `translation_execution.py`，定义 `TranslationBatchExecutionMixin`，把 34 个方法和两个模块级定义原样移入。
- `DocumentJobExecutionService` 继承该 Mixin。实例仍是同一个对象，`self.<名字>` 的解析结果不变。
- 导入按实际使用拆到两个文件；`execution.py` 里只被迁出集合使用的导入删除。
- 不改任何调用方，不改任何测试。

阶段一结束时行为与基线完全相同，测试中对 `execution` 实例的方法调用、属性赋值和 `patch.object` 全部照常生效。这是一个可以停下的状态，但它只是物理拆分。

### 阶段二：改为协作者

- `TranslationBatchExecutionMixin` 改为独立类 `TranslationBatchExecution`，增加 `__init__(host, *, settings, job_repository, file_service, job_resource_snapshot_service, translation_batch_repository, document_ir_translation_service, translation_audit_service, term_version_service, translation_batch_task_queue)`。
- 方法体内对 7 个宿主方法的 56 处调用，接收者由 `self` 改为 `self._host`。其他内容不动。
- 宿主去掉 Mixin 基类和 5 个翻译专属属性，3 个内部入口的 6 处调用改为 `self.translation_batches.<名字>`，删除 `set_translation_batch_task_queue`。
- 类外调用方改访问路径：`app/workers/document_tasks.py:38`、`app/domains/document_jobs/router.py:396`、`execution.py` 内 `EagerDocumentTranslationBatchTaskQueue.enqueue`、`app/main.py:218`。
- 测试迁移访问路径（见 §6）。

## 5. 关键取舍

**协作者而不是通用阶段处理器。** `execute_job` 的阶段分发只有约 50 行，条件分支不是负担所在。翻译是按批次扇出的子系统，有自己的 Worker 入口、租约和代次校验，套不进 `execute(context) -> StageResult` 的线性接口。B04 设计也已排除通用框架。

**宿主引用而不是注入回调。** 协作者保存宿主引用并在调用时查找方法。如果在构造时把 `host.execute_job` 等绑定方法捕获下来，测试里的 `patch.object(execution, "execute_job")`（`test_document_job_execution_stages.py:329`、`:489`）将不再拦截翻译收口后的续跑，行为会悄悄改变。

**不为宿主定义 Protocol。** 宿主只有一个实现，现有测试都用真实 runtime，没有第二个实现方。7 个方法的白名单写在协作者类的 docstring 里，并由验收脚本核对。

**不改名。** 跨类调用带下划线的方法不理想，但宿主这 7 个方法在类内还有 59 处调用，测试也按名字打补丁。改名与改接线混在一起会让 diff 失去可核对性，留给后续任务。

**不保留转发方法。** 宿主上不留 `execute_translation_batch` 之类只做转发的方法，调用方直接走 `translation_batches`。代价是测试里 45 处 `execute_translation_batch` 调用需要改路径。

**构造签名不变。** 宿主继续接收翻译相关的构造参数并转交给协作者。这样构造参数个数没有减少，换来的是装配代码和直接构造的测试不用动。把协作者提到 `main.py` 装配、缩减宿主签名，可以在后续任务里单独做。

## 6. 测试迁移（阶段二）

只改访问路径和 `patch.object` 的目标对象：

| 原写法 | 新写法 |
|---|---|
| `execution.execute_translation_batch(...)` 等迁出方法 | `execution.translation_batches.<同名>(...)` |
| `patch.object(execution, "_finalize_translation_generation", …)` 等 | `patch.object(execution.translation_batches, "<同名>", …)` |
| `execution.document_ir_translation_service` 等 5 个专属属性的读写 | `execution.translation_batches.<同名>` |
| `runtime.document_job_execution_service.document_ir_translation_service = …` | `runtime.document_job_execution_service.translation_batches.document_ir_translation_service = …` |
| `patch.object(execution, "execute_job")` | 不变 |

涉及 `test_translation_batch_failure_semantics.py`、`test_translation_integrity_execution.py`、`test_document_job_execution_stages.py`、`test_degraded_page_display.py`、`test_fastapi_jobs_backend.py`、`test_document_job_delivery_state_api.py` 和夹具 `document_job_list_query_v2_publication_fixtures.py`，按检索计数至少 126 处（明细见 `research/current-state.md` §4）。

主要风险是静默失效：阶段二后如果还有测试写 `execution.document_ir_translation_service = x`，Python 不会报错，只是在宿主上多出一个没人读的属性，用例可能照样通过但已不在测它原本要测的东西。对策是 AC-6 的全仓检索必须为零，并在迁移前后比较各测试模块的通过/失败集合。

## 7. 兼容与回退

- 没有数据迁移。Celery 任务名、参数和持久化记录格式不变，新旧 Worker 混跑不产生格式分歧。
- 回退以阶段为单位：回退阶段二回到 Mixin 状态，回退阶段一回到基线。两个阶段都不涉及数据。
- 如果实施时其他分支改动了 `execution.py` 的翻译段，先合入对方改动、重取基线，再做搬移，不手工解决整段搬移造成的冲突。

## 8. 不在本设计内

新模块内部仍是一个 34 个方法、约 1900 行的类。本任务只建立宿主与翻译批次之间的边界；内部是否再分，取决于后续真实的修改压力。渲染段、MinerU 回调段的提取同理，各自另立任务。
