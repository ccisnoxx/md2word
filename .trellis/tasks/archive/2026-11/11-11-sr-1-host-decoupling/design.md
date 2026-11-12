# 设计

基线 `0c9a7923`。延续 `archive/2026-11/11-10-*-extraction` 三次协作者提取的结果：当时把协作者访问宿主的方法限定在一个白名单里，这次把这份白名单整体变成显式依赖。

## 1. 目标结构

```text
app/domains/document_jobs/
  execution_support.py   新增：DocumentJobLifecycle（执行期状态推进 + 事件记录）、
                         require_uploaded_file()、document_ir_layout_metadata()
  execution.py           DocumentJobExecutionService：阶段分发、IR 转换、装配三个协作者
  mineru_execution.py    MinerUExecution（无 _host）
  render_execution.py    WordRenderExecution（无 _host）
  translation_execution.py TranslationBatchExecution（无 _host）
```

## 2. `DocumentJobLifecycle`

从 `execution.py` 原样搬移，只把方法名去掉前导下划线：

| 原宿主私有方法 | 新公开方法 |
|---|---|
| `_record_event` | `record_event` |
| `_mark_failed` | `mark_failed` |
| `_mark_succeeded` | `mark_succeeded` |
| `_mark_timed_out_if_needed` / `_mark_timed_out` | `mark_timed_out_if_needed` / `mark_timed_out` |
| `_fail_stage_attempt` | `fail_stage_attempt` |

依赖：`settings`（超时秒数）、`job_repository`、`event_repository`、`logger`（保持 `"business"` logger）。`mark_succeeded` 中对 `PreviewPolicy` 的延迟导入保持不变。

`require_uploaded_file(file_repository, file_id)` 和 `document_ir_layout_metadata(document_ir)` 作为模块级函数，与原实现逐字一致。`_get_mineru_raw_result_file` 只有宿主使用，留在宿主中，改为调用 `require_uploaded_file`。

## 3. 协作者构造

```python
lifecycle = DocumentJobLifecycle(settings, job_repository, event_repository, logger)
self.lifecycle = lifecycle
self.mineru = MinerUExecution(settings=..., job_repository=..., file_service=..., lifecycle=lifecycle, <原专属依赖>)
self.rendering = WordRenderExecution(settings=..., job_repository=..., file_repository=..., file_service=...,
                                     document_ir_service=..., job_resource_snapshot_service=..., lifecycle=lifecycle, <原专属依赖>)
self.translation_batches = TranslationBatchExecution(settings=..., job_repository=..., file_service=...,
                                     job_resource_snapshot_service=..., lifecycle=lifecycle,
                                     resume_job=lambda job_id, *, trace_id: self.execute_job(job_id, trace_id=trace_id),
                                     <原专属依赖>)
```

- 依赖使用关键字参数，各协作者只接收第 1 节盘点出的实际依赖（以实施时的 `rg` 结果为准）。
- `resume_job` 用 lambda 包装，调用时才查找 `self.execute_job`，所以 `patch.object(execution, "execute_job")` 仍然生效。
- 渲染协作者使用 `document_ir_service.degradation_policy`，按原方式读取，不提前展开。
- 渲染协作者调用的 `_mark_succeeded` 改为 `lifecycle.mark_succeeded`。

## 4. 共享对象一致性

宿主和协作者持有的 `settings`、`job_repository`、`file_service` 等是同一个对象引用，与现状（经 `_host` 读取同一对象）等价。测试如果在构造后替换宿主属性（例如 `execution.job_repository = ...`），协作者就看不到新值。实施前用 `rg "execution(_service)?\.(job_repository|file_service|file_repository|settings)\s*="` 检查；若存在这种用法，就把相应测试改为构造时注入，并在提交说明中写明。

## 5. 被拒绝的方案

- 定义 `ExecutionHostProtocol`，把私有方法改成公开方法后继续注入宿主：耦合方向没有变化，只是换了名字。
- 事件总线/观察者：没有多订阅者需求，属于过度设计。

## 6. 分阶段

1. 新增 `execution_support.py`；宿主改为委托它，删除宿主上的私有方法；宿主内部调用点和测试中的 `execution._mark_failed/_fail_stage_attempt` 改为 `execution.lifecycle.*`。协作者暂时改为 `self._host.lifecycle.*`。
2. 逐个协作者改成显式依赖（mineru → render → translation），每个协作者一次提交，提交后跑该协作者的定向测试。
3. 删除协作者里残留的 `_host` 和 `TYPE_CHECKING` 导入，更新 spec。
