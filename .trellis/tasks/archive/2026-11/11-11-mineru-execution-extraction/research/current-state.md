# 现状度量

基线 `main@bc4226a8`（渲染段提取 PR #40 合并后）。度量方法同前两次：用 AST 统计 `app/domains/document_jobs/execution.py`，测试引用用 `git ls-files` 范围内的正则检索。

## 1. 宿主规模

`execution.py` 1560 行，`DocumentJobExecutionService` 34 个方法。翻译段与渲染段已分别提取到 `translation_execution.py`、`render_execution.py`。剩余职责：状态推进与阶段分发、MinerU 解析与回调、IR 转换、任务级失败与超时收口、事件。

`execute_job` 中与 MinerU 相关的两个入口：

```python
job = self._process_replayable_callback_messages(job, trace_id=trace_id)
...
if latest.status == "running" and latest.stage == "parsing":
    latest = self._run_mineru_parse(latest, trace_id=trace_id)
```

## 2. 迁出集合（15 个方法，553 行）

| 方法 | 行 | 行数 | 说明 |
|---|---|---|---|
| `_run_mineru_parse` | 267 | 105 | 提交解析、轮询、选取结果 |
| `find_job_for_mineru_callback` | 373 | 15 | **公开**，回调路由调用 |
| `enqueue_mineru_callback_for_job` | 389 | 61 | **公开**，回调路由调用 |
| `_process_replayable_callback_messages` | 451 | 13 | `execute_job` 入口 |
| `_process_callback_message` | 465 | 118 | |
| `_build_callback_message_payload` | 584 | 16 | |
| `_build_callback_dedupe_key` | 601 | 12 | |
| `_sync_callback_ids` | 614 | 38 | |
| `_record_callback_ignored_event` | 653 | 21 | |
| `_download_and_register_mineru_result` | 675 | 90 | 解析与回调两条路径共用 |
| `_refresh_mineru_parse_attempt` | 1272 | 30 | |
| `_select_mineru_result` | 1303 | 15 | |
| `_mineru_language_for_job` | 1184 | 3 | |
| `_build_callback_seed` | 1465 | 5 | `@staticmethod` |
| `_build_mineru_client` | 1471 | 10 | 宿主 `__init__` 中作为默认客户端工厂 |

迁出后宿主约 1010 行。没有需要迁出的模块级定义。

不迁出、留在宿主的相邻方法：

- `_mark_parsing_started`：`queued → parsing` 的阶段推进，与 `_mark_queued_from_worker`、`_mark_ir_converting_started` 同类，归宿主所有。
- `_get_mineru_raw_result_file`：由 IR 转换读取 MinerU 原始结果，只被 `_convert_and_save_document_ir` 调用。

## 3. 双向耦合

协作者 → 宿主（5 个方法，16 处调用）：

| 方法 | 调用数 | 所在迁出方法 |
|---|---|---|
| `_record_event` | 10 | `_run_mineru_parse` 2、`enqueue_mineru_callback_for_job` 2、`_process_callback_message` 2、`_download_and_register_mineru_result` 2、`_sync_callback_ids` 1、`_record_callback_ignored_event` 1 |
| `_mark_failed` | 3 | `_run_mineru_parse`、`_process_callback_message`、`_refresh_mineru_parse_attempt` |
| `_fail_stage_attempt` | 1 | `_download_and_register_mineru_result` |
| `_mark_timed_out_if_needed` | 1 | `_refresh_mineru_parse_attempt` |
| `_get_uploaded_file` | 1 | `_run_mineru_parse` |

宿主 → 协作者：

- `execute_job` → `_process_replayable_callback_messages`、`_run_mineru_parse`。
- `__init__` → `self._build_mineru_client`（作为默认工厂）。阶段二改为在协作者 `__init__` 内取默认值，宿主不再引用。

类外调用方：`app/domains/jobs/mineru_callbacks_router.py:39` 调用 `find_job_for_mineru_callback`，`:44` 调用 `enqueue_mineru_callback_for_job`，都经 `runtime.document_job_execution_service`。`scripts/` 中没有引用。

翻译协作者与渲染协作者都不引用迁出集合中的方法。

## 4. 依赖归属

| 依赖 | MinerU 段 | 宿主其余方法 |
|---|---|---|
| `callback_message_store`、`mineru_client_factory`、`mineru_config_resolver` | 用 | 不用 |
| `settings`、`job_repository`、`file_service`、`logger` | 用 | 用 |

`app/domains/document_jobs/recovery.py` 中的 `self.callback_message_store` 属于 `DocumentJobRecoveryService`，是另一个类自己的属性，不受影响。

## 5. 模块级名字

仅 MinerU 段使用、应随迁出的导入：`DocumentJobCallbackMessage`、`MinerUClient`、`MinerUError`、`hashlib`、`secrets`、`spec_for_document_job_mode`。

两边共用：`Any`、`DocumentJobRecord`、`Path`、`json`、`tempfile`、`timedelta`、`utc_now`、`uuid4`。

测试中没有 `app.domains.document_jobs.execution.<名字>` 形式的模块路径补丁（渲染段提取后已清零）。

## 6. 测试耦合

### `fake_mineru_client` 不需要迁移

测试读取次数最多的 `fake_mineru_client`（约 90 处，分布在 15 个文件）不是执行服务的生产属性。它是测试装配时挂在宿主上的辅助引用：

```python
# tests/test_fastapi_jobs_backend.py:494-512
document_job_execution_service = DocumentJobExecutionService(..., mineru_client_factory=lambda: document_job_mineru_client)
document_job_execution_service.fake_mineru_client = document_job_mineru_client
```

真正生效的是构造参数 `mineru_client_factory`。宿主构造签名不变，并把该参数转交给协作者，所以 `fake_mineru_client` 继续挂在宿主上就能正常使用。

### 需要迁移的 8 处

| 位置 | 写法 | 类型 |
|---|---|---|
| `tests/test_fastapi_jobs_backend.py:1411`、`:1464`、`:1573` | `runtime.document_job_execution_service._build_mineru_client()` | 读取 |
| `tests/test_mineru_download_boundary.py:277` | `runtime.document_job_execution_service._build_mineru_client` | 读取 |
| `tests/test_mineru_download_boundary.py:322`、`:341` | `execution._build_mineru_client()` | 读取 |
| `tests/test_mineru_download_boundary.py:324`、`:343` | `execution.mineru_client_factory = lambda: client` | **赋值，静默失效风险** |

读取遇到不存在的属性会报 `AttributeError`，迁出后漏改会显式失败。只有两处赋值会静默失效：值写到宿主上，但没有任何代码读取。

测试中没有对迁出方法的 `patch.object` 或字符串形式的引用。

## 7. 覆盖 MinerU 路径的测试模块

回调相关引用最多的是 `test_fastapi_jobs_backend`（63）、`test_database_job_repository`（47）、`test_mineru_download_boundary`（4）、`test_job_workflow_policy`（4）、`test_openapi_export`（2）。经执行服务运行任务的模块都会经过 `_run_mineru_parse` 或回调重放，所以定向清单沿用渲染任务的 21 个模块，再加 `test_job_workflow_policy` 和 `test_openapi_export`（核对回调路由的 OpenAPI 未变）。

## 8. 文档

- `.trellis/spec/` 与 `docs/` 中没有 MinerU 段的方法级 owner 表述。
- `.trellis/spec/backend/directory-structure.md` 的 `document_jobs/` 文件列表要加入新模块。
- `.trellis/spec/backend/document-job-mode-contract.md:73`“推进和事件 owner 为 `execution.py`”在迁出后仍成立。
