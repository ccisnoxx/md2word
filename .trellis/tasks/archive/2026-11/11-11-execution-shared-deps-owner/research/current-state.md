# 现状度量

基线 `main@6101ad44`（MinerU 段提取 PR #41 合并后）。用 AST 统计三个协作者类的 `__init__` 赋值与方法体中 `self.<共用属性>` 的读取，测试引用用正则检索 `app/`、`tests/`、`scripts/`。

## 1. 问题

三次提取（PR #39、#40、#41）都选择“共用依赖由宿主和协作者各持同一对象的引用”。生产装配构造后不再替换依赖，所以线上没有分叉。风险在测试：只替换一侧时，另一侧继续用旧对象，不报错。

已知实例：

- `tests/test_fastapi_jobs_backend.py:10643` 只替换宿主上的 `document_ir_service`。渲染协作者的页面降级会读取 `document_ir_service`，但这个用例在 `ir_converting` 阶段就失败，没走到渲染，所以没有暴露问题。
- `tests/document_job_list_query_v2_publication_fixtures.py:152-153` 为了避免分叉，必须手动同时写入 `rendering` 和 `translation_batches` 两个协作者。

## 2. 共用依赖与访问点

| 协作者 | 构造中保存的共用依赖 | 方法体读取次数 |
|---|---|---|
| `TranslationBatchExecution`（`translation_execution.py`） | `settings`、`job_repository`、`file_service`、`job_resource_snapshot_service` | `job_repository` 21、`settings` 6、`file_service` 5、`job_resource_snapshot_service` 2，合计 34 |
| `WordRenderExecution`（`render_execution.py`） | `settings`、`job_repository`、`file_repository`、`file_service`、`document_ir_service`、`job_resource_snapshot_service`、`logger` | `job_repository` 19、`file_service` 15、`file_repository` 12、`settings` 2、`document_ir_service` 2、`job_resource_snapshot_service` 1、`logger` 2，合计 53 |
| `MinerUExecution`（`mineru_execution.py`） | `settings`、`job_repository`、`file_service`、`logger` | `job_repository` 17、`settings` 8、`file_service` 2、`logger` 1，合计 28 |

三个协作者在构造之外都不写入这些属性。

宿主 `__init__` 当前持有：`settings`、`job_repository`、`file_repository`、`file_service`、`document_ir_service`、`logger`。`job_resource_snapshot_service` 宿主自己不用，渲染段提取时移除了，只由两个协作者持有。

## 3. `logger` 的特殊性

两个协作者的 `logger` 不是由宿主传入的，而是各自调用 `logging.getLogger("business")`，与宿主拿到的是 logging 模块里的同一个单例。测试中没有替换或 `patch.object` 任何执行服务的 `logger`。它不存在“传入引用后分叉”的问题，所以不纳入本任务。

排除 `logger` 后，需要改写的访问点为：翻译 34、渲染 51、MinerU 27，合计 112 处。

## 4. 测试与类外耦合

- 经协作者访问共用属性：只有夹具 `document_job_list_query_v2_publication_fixtures.py:152-153`（`job_resource_snapshot_service`）。
- 对执行服务共用属性的赋值：只有 `test_fastapi_jobs_backend.py:10643`（`document_ir_service`，宿主侧）。
- 检索命中但无关：`test_document_job_modes.py:308` 和夹具 `:154` 改的是 `runtime.document_job_service`；`test_document_job_review_hints.py:89` 改的是 `Mock` 对象。
- 对执行服务赋值已迁出的专属依赖（另一类静默失效）：当前 0 处。
- `app/`、`scripts/` 中没有经协作者访问共用属性的代码。
