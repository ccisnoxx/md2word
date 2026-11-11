# 设计

## 1. 目标结构

```text
app/domains/document_jobs/use_cases/
  __init__.py            DocumentJobUseCases（frozen dataclass，字段为各用例实例）与 build_document_job_use_cases(...)
  access.py              DocumentJobAccess：加载任务/有效任务、可见性、未删除校验、任务文件列表与可下载判断（共享读侧 owner）
  action_rules.py        纯函数：retry/cancel/archive/unarchive/clone/delete 禁用原因、可重试判断、publish 动作构建
  queries.py             DocumentJobQueries：get_job、list_jobs、list_visible_jobs、list_events、list_files、
                         list_translation_batches、get_translation_batch_snapshot、build_job_read_view、
                         build_available_actions、build_incident_classification_view、build_download_policy、
                         document_job_search_values、record_event
  submission.py          DocumentJobSubmission：create_job、clone_job、retry_job、retry_word_preview、入队/入队失败收口
  request_snapshot.py    请求快照、资源快照、clone 配置、模式/语言/模板/术语版本解析（submission 专用，纯解析 + 只读依赖）
  lifecycle_commands.py  DocumentJobLifecycleCommands：archive、unarchive、preview_delete、delete、cancel、删除计划
  publication.py         DocumentJobPublication：publish、list_publications、request_new_generation、
                         get_generation_request、发布文件下载与下载审计
  quality_review.py      DocumentJobQualityReview：quality/review/preview/pages/tables 读取、提交评审、table evidence
  table_references.py    DocumentJobTableReferences：list/read table reference 及快照校验
  translation_qa.py      DocumentJobTranslationQa：get/update translation QA 及工件读取
  downloads.py           DocumentJobDownloads：result/file 下载（含 authorized 版本）、record_download_authorized
```

模块划分是初稿。实施第 0 步会先生成方法调用图（`research/call-graph.md`），按"私有方法跟随唯一调用方，被多组调用的方法进入 `access.py` 或 `action_rules.py`"的规则最终定稿；如果和初稿不同，先更新本文件再动代码。

## 2. 依赖规则

- 用例类之间不能互相依赖。如果某个用例需要另一个用例的能力（例如读视图需要 publish 动作的可用性），这部分能力必须是 `action_rules.py` 中的纯函数，或者是 `DocumentJobAccess` 的公开方法。
- 每个用例只接收自己真正用到的构造参数（来自原 `__init__` 的 12 个依赖的子集）。
- 原来跨方法的 `self.xxx` 状态只有构造时注入的依赖，没有运行期可变状态，所以拆分不会产生状态同步问题（实施时再用 `rg "self\.\w+ = " service.py` 确认只出现在 `__init__` 里）。

## 3. 运行时与调用方

- `AppRuntime.document_job_service` → `AppRuntime.document_job_use_cases: DocumentJobUseCases`。
- router 改为 `runtime.document_job_use_cases.submission.create_job(...)` 这种形式；`DocumentJobIncidentService` 构造参数改为 `queries` 与 `access`（以它实际调用的方法为准；它还访问了 `file_repository.read_session()`，改为注入 `file_repository`）。
- `incidents_router.py` 中如果有类似的访问，一并调整。
- `app/main.py` 只把构造 `DocumentJobService` 的那一段替换为 `build_document_job_use_cases(...)`；组合根的拆分留给 sr-3。

## 4. 迁移策略（不保留门面）

按用例组逐步迁移，每一步：把方法组移入新类 → 把 router/incidents/测试中这些方法的调用点切到新用例 → 从 `DocumentJobService` 删除这些方法。迁移期间 `DocumentJobService` 与新用例并存，但同一个方法只存在于一处。

顺序（从依赖最少的开始）：`access` + `action_rules` → `table_references` → `translation_qa` → `downloads` → `quality_review` → `publication` → `lifecycle_commands` → `submission` + `request_snapshot` → `queries` → 删除 `service.py`。

## 5. 风险

- `test_fastapi_jobs_backend.py`（785KB）是主要的回归网，单次运行时间较长；每步只跑和该用例组相关的测试类，最后一步跑全量。
- 私有方法之间的隐式调用链很深（例如 `_build_job_read_observation` → `_build_publish_action` → `_verify_publication_result`）。调用图必须在搬移之前完成，避免出现循环依赖。

## 6. 实施定稿（2026-11-11，依据 `research/call-graph.tsv` 与 `tools/plan.py`）

与初稿不同的地方：

- **共享层**：没有采用纯函数模块 `action_rules.py`。动作禁用原因、发布/新代动作和读视图依赖 `settings`、文件仓储与快照服务，因此合并为有状态组件 `read_model.py`（`DocumentJobReadModel`），它是读视图与可用动作的唯一 owner。另外新增两个共享组件：`events.py`（`record_event` 被 7 个组件调用）和 `dispatcher.py`（投递与投递失败收口，submission 和 publication 共用）。`request_snapshot.py` 由用例模块改为共享组件。
- **公开名**：共享组件中被跨组件调用的私有方法去掉前导下划线。原来的 `_get_job`（仅做授权读取）改名为 `access.get_authorized_job`，以免与返回有效投影的公开方法 `access.get_job` 冲突。`common.py` 中需要跨模块共享的私有名（`UNREAD_RESULT`、`SYSTEM_LOGGER`、`ReviewCommit`、`TableReferenceSnapshot`）公开化；原来的 `_DocumentJobSearchable` 与 `list_query.DocumentJobSearchable` 定义完全相同，删除重复，直接复用后者。
- **死代码**：8 个方法在全仓库没有任何调用（`_matches_document_job_query`、`_matches_status_filter`、`_matches_translation_qa_status`、`_count_translation_qa_statuses`、`_matches_created_range`、`_document_job_sort_key`、`_snapshot_resource_id`、`_snapshot_resource_version`），不迁移。
- **迁移方式**：没有按 §4 逐组迁移、多次提交，而是用 `tools/generate.py` 一次性生成全部组件，再一次性切换调用方。原因是方法之间的私有调用链跨越多个组，逐组迁移会产生大量临时的跨类调用；一次切换反而更容易核验。逐字一致性由独立脚本 `tools/verify_moved.py` 核对：165 个方法反向还原后都与 HEAD 中的原方法一致。
- **构造后替换依赖**：生产代码坚持每个组件显式注入自己用到的依赖，`task_queue`、`job_resource_snapshot_service` 等由多个组件各自持有同一对象。测试在构造后替换依赖时，统一使用 `tests/document_job_use_case_support.py::replace_dependency`，同步到 bundle 中所有持有方。按模块路径 patch `utc_now`、`prepare_publication_evidence` 的写法，改为 `patch_use_case_clock` / `patch_publication_evidence`：对所有导入了该名字的用例模块使用同一个 mock，所以调用计数和 `side_effect` 序列与拆分前一致。
- **incidents**：`DocumentJobIncidentService` 改为显式注入 `file_repository`、`access`、`read_model`、`queries`、`submission`。

最终模块行数：request_snapshot 527、publication 480、submission 463、translation_qa 448、lifecycle_commands 403、read_model 370、quality_review 360，其余都在 230 行以下。全部在 600 行上限以内。
