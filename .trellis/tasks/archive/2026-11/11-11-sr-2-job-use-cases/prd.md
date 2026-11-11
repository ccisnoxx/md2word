# 将 document_jobs 任务编排拆为明确的 Use Case/Workflow

父任务：`11-11-structure-refactor`（对应用户需求第 2 项）。前置条件：`11-11-sr-1-host-decoupling` 已合入。

## 目标

把 3829 行的 `DocumentJobService`（约 190 个方法、50+ 公开方法）拆成若干按业务用例划分的应用服务。每个用例只持有自己需要的依赖，router 和 incidents 直接依赖具体用例，不再经过一个"上帝服务"。

## 现状

- 公开方法可以按用例分为 8 组：提交（create/clone/retry/retry_word_preview）、生命周期命令（archive/unarchive/preview_delete/delete/cancel）、发布与新代次、质量/评审读取与提交、表格引用、翻译 QA、下载、列表/读视图/可用动作。
- 生产调用方只有 `router.py`（46 处）和 `incidents.py`（14 处）；测试中约 30 处通过 `runtime.document_job_service` 访问，其余走 HTTP。
- 跨组共享的内部能力：任务加载与可见性校验、任务文件归属判断、动作禁用原因（读视图展示和命令执行都要用）。

## 需求

1. 新增 `app/domains/document_jobs/use_cases/` 包，每个用例组一个模块，各自是一个类，构造时显式接收依赖。
2. 共享的读侧原语（加载任务、可见性、文件归属）只保留一个 owner；动作禁用原因等纯规则抽成无状态函数，读视图和命令共用同一份实现。
3. `AppRuntime` 用 `document_job_use_cases`（各用例的不可变集合）替换 `document_job_service`；router、incidents 和测试改为调用具体用例。
4. 迁移完成后删除 `DocumentJobService`，不保留转发门面。
5. 仍然被外部引用的模块级类型（`DocumentJobListResult`、`DocumentJobDeletePlan`、`TableReferenceContent`、`DocumentJobDownloadPolicy`、`NewGenerationRequestUnavailable` 等）迁移到其所属用例模块，或迁移到中性模块，并更新所有导入方。

## 约束

- 外部行为完全不变：HTTP 契约、OpenAPI、错误码、审计记录、事件、CAS 条件。
- 方法体只搬移，不重写逻辑；需要跨用例共享的私有方法，提升为共享 owner 的公开方法或纯函数，不在多个用例里复制。
- 不引入 DI 容器、命令总线或 mediator。
- `translation_execution.py` 的内部拆分不在本任务范围内（见父任务非目标）。

## 验收标准

- [ ] `app/domains/document_jobs/service.py` 已删除；`rg "DocumentJobService\b|document_job_service" app tests scripts` 结果为 0（`DocumentJobExecutionService` 等不受影响）。
- [ ] 每个用例模块不超过约 600 行；没有用例模块依赖另一个用例类（只能依赖共享 owner 和纯规则模块）。
- [ ] `tests.test_openapi_export` 通过，输出一致。
- [ ] 定向测试通过：`test_fastapi_jobs_backend`、`test_document_job_modes`、`test_document_job_delivery_state_api`、`test_document_job_download_availability`、`test_document_job_download_availability_api`、`test_document_job_list_query_v2_service`、`test_document_job_incident_publish_light_check`、`test_document_job_list_publish_light_check`、`test_translation_batch_failure_semantics`、`test_document_job_result_persistence`、`test_document_job_review_hints`。
- [ ] `directory-structure.md` 已更新 document_jobs 的用例布局。
