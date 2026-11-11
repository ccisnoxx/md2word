# 设计

基线 `main@bc4226a8`。迁出集合、耦合与测试引用见 [research/current-state.md](research/current-state.md)。整体做法沿用前两次提取（`.trellis/tasks/archive/2026-11/11-10-translation-batch-extraction/`、`11-10-render-execution-extraction/`），这里只写本次的差异。

## 1. 目标结构

```text
app/domains/document_jobs/
  execution.py               DocumentJobExecutionService：状态推进与阶段分发、IR 转换、任务级失败与超时收口、事件
  mineru_execution.py        MinerUExecution：解析提交与轮询、回调排队与重放、结果下载登记、客户端构造
  translation_execution.py   TranslationBatchExecution（已有）
  render_execution.py        WordRenderExecution（已有）
```

宿主 `__init__` 构造 `MinerUExecution` 并保存为 `self.mineru`。构造签名不变，`app/main.py` 和测试装配的直接构造都不用改。

## 2. 两个方向的边界

协作者到宿主只允许 5 个方法，且在调用时经 `self._host.<名字>` 查找：`_record_event`、`_mark_failed`、`_fail_stage_attempt`、`_mark_timed_out_if_needed`、`_get_uploaded_file`。这 5 个方法都已在前两次的白名单中出现过。

宿主到协作者：

- 内部入口 2 个，都在 `execute_job` 中：`_process_replayable_callback_messages`、`_run_mineru_parse`。
- 公开方法 2 个，由回调路由调用：`find_job_for_mineru_callback`、`enqueue_mineru_callback_for_job`。

`mineru_execution.py` 只在 `TYPE_CHECKING` 下导入宿主类型。

## 3. 依赖归属（阶段二后）

| 依赖 | 持有者 |
|---|---|
| `callback_message_store`、`mineru_client_factory`、`mineru_config_resolver` | 仅 MinerU 协作者 |
| `settings`、`job_repository`、`file_service`、`logger` | 宿主与 MinerU 协作者，引用同一对象 |

默认工厂：基线宿主 `__init__` 中是 `self.mineru_client_factory = mineru_client_factory or self._build_mineru_client`。阶段二把这一行原样移入协作者 `__init__`，`self` 改为指向协作者，此时 `_build_mineru_client` 是协作者自己的方法。它只读取 `self.settings` 与 `self.mineru_config_resolver`，这两个都是协作者持有的同一对象，所以行为不变。

## 4. 分两阶段

### 阶段一：纯搬移

- 新建 `mineru_execution.py`，定义 `MinerUExecutionMixin`，把 15 个方法（含 `_build_callback_seed` 的 `@staticmethod`）原样移入。
- 宿主改为 `class DocumentJobExecutionService(MinerUExecutionMixin)`，导入按实际使用拆分。
- 不改任何测试。测试中没有模块路径补丁，也没有对迁出方法的 `patch.object`，所以这一阶段与翻译段一样不需要改测试。

### 阶段二：改为协作者

- Mixin 改为 `MinerUExecution`，增加 `__init__(host, *, settings, job_repository, file_service, callback_message_store, mineru_config_resolver, mineru_client_factory)`。`logger` 取 `logging.getLogger("business")`。
- 方法体内对 5 个宿主方法的 16 处调用，接收者改为 `self._host`。
- 宿主去掉 Mixin 基类和 3 个 MinerU 依赖属性，`__init__` 不再计算默认工厂，2 处入口改为 `self.mineru.<名字>`。
- 回调路由的 2 处调用改为 `runtime.document_job_execution_service.mineru.<名字>`。
- 测试迁移 8 处（§6）。

## 5. 关键取舍

**不保留公开方法的转发。** 宿主上的两个公开方法只有回调路由一个调用方，改路由只需要动 2 行。保留转发会让宿主继续出现在 MinerU 回调的调用链上，和前两次的做法不一致。列为待评审决策 2。

**`_mark_parsing_started` 留在宿主。** 它写的是 `queued → parsing` 的阶段推进，和 `_mark_queued_from_worker`、`_mark_ir_converting_started` 同类。阶段推进归宿主所有。

**`_get_mineru_raw_result_file` 留在宿主。** 它的唯一调用方是 IR 转换，读取的是已经登记的文件。

**`fake_mineru_client` 不迁移。** 它是测试装配时挂在宿主上的辅助引用，真正生效的是构造参数 `mineru_client_factory`。宿主把这个参数转交给协作者后，读取 `fake_mineru_client` 的约 90 处测试不受影响。如果改成挂在协作者上，会无谓地扩大测试改动面。

**其余取舍同前**：使用宿主引用而不是注入回调，不为宿主定义 Protocol，不改名，宿主构造签名不变。

## 6. 测试迁移（阶段二）

| 原写法 | 新写法 |
|---|---|
| `runtime.document_job_execution_service._build_mineru_client` | `runtime.document_job_execution_service.mineru._build_mineru_client` |
| `execution._build_mineru_client()` | `execution.mineru._build_mineru_client()` |
| `execution.mineru_client_factory = lambda: client` | `execution.mineru.mineru_client_factory = lambda: client` |
| `….fake_mineru_client` | 不变 |

共 8 处，位置见 research §6。其中 `test_mineru_download_boundary.py:324`、`:343` 两处是赋值，属于静默失效风险，优先处理；AC-6 的检索要覆盖赋值写法。

## 7. 兼容与回退

- 没有数据迁移。回调路由的 HTTP 合同、Celery 任务名与参数都不变，回调消息的去重键和状态流转也不变，新旧 Worker 混跑时，对同一条回调消息的处理语义一致。
- 回退以阶段为单位。
- 实施前如果 `main` 上 MinerU 段有新改动，先合入，再重取基线和度量。
