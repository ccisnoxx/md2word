# 实施与验证计划

状态：阶段一、阶段二已实施并验证（2026-11-10），结果见文末“已执行验证”。

解释器统一用仓库根目录下的 `.venv/bin/python`。只跑下列定向模块，不执行 discover、聚合脚本、在线验证或真实 Provider/MinerU 调用。

## 0. 准备

1. 确认主工作区干净且没有其他分支在改 `execution.py` 的翻译段；从 `main` 建任务分支，`task.py set-branch` 记录。
2. 记录基线提交号，后续等价核对都以它为准。
3. 写一次性核对脚本 `verify_move.py`，放在本任务目录，不进入 `app/` 或 `tests/`。它用 `git show <基线>:app/domains/document_jobs/execution.py` 取基线源码，与工作区的两个文件比较：
   - `--stage 1`：迁出的 34 个方法和两个模块级定义的 `ast.dump` 与基线逐一相同；宿主其余方法与基线相同；`execution.py` 中不再定义迁出方法。
   - `--stage 2`：把 `self._host.<名字>` 归一为 `self.<名字>`、把宿主里的 `self.translation_batches.<名字>` 归一为 `self.<名字>` 后重复上述比较；另外断言协作者对 `self._host` 的访问只落在 7 个白名单方法上。
4. 基线测试运行，保存输出到本任务目录，作为通过/失败集合的对照：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_batch_failure_semantics \
  tests.test_translation_integrity_execution \
  tests.test_document_job_execution_stages \
  tests.test_degraded_page_display \
  tests.test_document_job_delivery_state_api
```

5. `tests/test_fastapi_jobs_backend.py` 超过一万行。基线阶段先定位其中引用迁出方法或专属属性的测试类，以及导入 `document_job_list_query_v2_publication_fixtures` 的模块，把这些类和模块加入定向清单并跑出基线。清单写入本文件“已执行验证”一节。

基线出现的失败属于既有问题：记录用例名，不修复，后续只要求集合不变。

## 1. 阶段一：纯搬移

1. 新建 `app/domains/document_jobs/translation_execution.py`，定义 `TranslationBatchExecutionMixin`，移入 34 个方法、`_TranslationBatchStorageError`、`_is_metadata_storage_error`。方法体逐字符不改。
2. 按实际使用整理两个文件的导入；`execution.py` 让 `DocumentJobExecutionService` 继承该 Mixin。
3. 新模块顶部写中文模块说明和类 docstring，说明职责和阶段一的临时形态。
4. 验证：
   - `verify_move.py --stage 1` 通过。
   - `.venv/bin/python -c "import app.main"` 无循环导入错误。
   - 重跑步骤 0 的定向清单，通过/失败集合与基线一致。
   - `git diff --stat` 只含两个应用文件，测试零改动；`git diff --check` 通过。

**评审点 A**：向用户报告阶段一结果，确认是否继续阶段二，以及是否在此处提交（提交需单独出计划并确认）。

## 2. 阶段二：改为协作者

1. `TranslationBatchExecutionMixin` 改为 `TranslationBatchExecution`，加 `__init__`，把 56 处宿主方法调用的接收者改为 `self._host`。类 docstring 列出 7 个白名单方法。
2. 宿主：`__init__` 中构造 `self.translation_batches`，去掉 Mixin 基类、5 个专属属性和 `set_translation_batch_task_queue`，6 处内部入口调用改走 `self.translation_batches`。
3. 类外调用方改访问路径：`app/workers/document_tasks.py:38`、`app/domains/document_jobs/router.py:396`、`EagerDocumentTranslationBatchTaskQueue.enqueue`、`app/main.py:218`。
4. 先处理夹具 `tests/document_job_list_query_v2_publication_fixtures.py:151`：读懂它替换 `job_resource_snapshot_service` 的意图，确定该改宿主、协作者还是两者。
5. 按 `design.md` §6 的对照表迁移其余测试访问路径。不改断言，不删用例。
6. 验证：
   - `verify_move.py --stage 2` 通过。
   - 全仓检索为零（AC-6）。检索对象是宿主上的 34 个迁出方法名和 5 个专属属性名，接收者覆盖 `execution`、`execution_service`、`document_job_execution_service` 以及基线阶段发现的其他别名。
   - `.venv/bin/python -c "import app.main"` 通过。
   - 重跑定向清单，通过/失败集合与基线一致。
   - `git diff --check` 通过。

## 3. 收尾

1. 更新 Spec：`.trellis/spec/backend/translation-batch-lifecycle.md` §1 的 owner 一行改为新模块；`.trellis/spec/backend/directory-structure.md:56` 的文件列表加入 `translation_execution.py`。其他合同文字不动。
2. `trellis-check` 审查最终 diff。本次改动触及并发与失败收口路径，另请一次独立只读复核，重点看 `self._host` 改写是否遗漏或越界、共用依赖是否出现两份不同对象。没有合适的复核者时如实报告。
3. 检查最终 diff 与工作区状态：无无关格式化、无重复逻辑、无遗留转发方法、无生成物。
4. 提交计划交用户确认后再提交；不自动推送。`task.py archive`、`add_session.py` 可能产生 Trellis 记账提交，执行前先说明。

## 回退点

- 阶段一后：丢弃任务分支上的改动即回到基线。
- 阶段二后：回退阶段二的改动即回到 Mixin 状态，阶段一的结果可单独保留。

## 停止条件

- `verify_move.py` 报告方法体不等价，而原因不是可解释的导入或接收者改写：停下排查，不靠调整脚本放行。
- 定向测试出现基线之外的新失败：先判断是访问路径漏改还是行为变化。同一问题两轮“修复后定向复测”仍未解决，就停止并报告证据、已尝试的做法和剩余选项。
- 阶段二发现宿主白名单不够用（需要第 8 个宿主方法或需要反向读取宿主属性）：停下回到设计评审，不就地扩大白名单。

## 已执行验证

2026-11-10，分支 `refactor/translation-batch-extraction`，基线 `main@d45e46e1`。评审点 A 由用户在启动任务时预先确认（“开始做阶段二”），阶段一未单独提交。

工具：`verify_move.py`（AST 等价与边界核对）；`validation/run_targeted.sh <标签>` 逐模块运行定向清单，`validation/summarize.py` 把日志归一为 `results.tsv`（用例标识、状态、最终异常行，随机 ID、临时路径、时间戳已归一），并核对解析条数与 `Ran N` 一致。

定向清单（13 个模块，共 368 行结果，含 subTest）：`test_translation_batch_failure_semantics`、`test_translation_integrity_execution`、`test_document_job_execution_stages`、`test_degraded_page_display`、`test_document_job_delivery_state_api`、`test_document_job_modes`、`test_database_job_repository`、`test_translation_table_context`、`test_document_job_list_query_v2_writers`、`test_document_job_incident_publish_light_check`、`test_document_job_list_publish_light_check`、`test_document_job_list_query_v2_service`、`test_fastapi_jobs_backend`。

| 关口 | 结果 |
|---|---|
| 基线 | 301 ok，14 FAIL，53 ERROR；失败集中在 `delivery_state_api`（20）、`execution_stages`（11）、`modes`（1）、`fastapi_jobs_backend`（35）。主要异常：`新文件对象路径缺少固定位置的独立 file_id`（27）、`发布状态只能由原子发布端口维护`（14）、`_build_image_loader() missing ... 'document_ir'`（5）、模板 seed 版本冲突（4）等，均与翻译批次搬移无关，按既有问题记录、不修复 |
| 阶段一 `verify_move.py --stage 1` | 核对通过：34 个方法与 2 个模块级定义 AST 等价，宿主其余方法逐一等价 |
| 阶段一导入 | 两模块无未解析全局名、无未使用导入；`import app.main` 成功 |
| 阶段一定向测试 | `results.tsv` 与基线逐行一致 |
| 阶段二 `verify_move.py --stage 2` | 核对通过：协作者方法去掉 `_host` 一跳后与基线等价；协作者只访问 7 个白名单宿主方法（56 处）；宿主只经 3 个内部入口访问协作者（6 处）；宿主不再持有 5 个专属属性 |
| 阶段二导入 | `import app.main` 成功；单独先导入 `translation_execution` 无循环导入 |
| 阶段二测试迁移 | 7 个测试文件 126 处，新增行去掉 `translation_batches` 一跳后均与删除行对应；夹具 `document_job_list_query_v2_publication_fixtures.py` 对共用的 `job_resource_snapshot_service` 两侧同步替换 |
| AC-6 检索 | 代码与文档（排除 `.trellis/tasks/`）中经执行服务访问迁出名字的旧写法 0 处；宿主类上无迁出名字 |
| 阶段二定向测试 | `results.tsv` 与基线逐行一致 |

未执行：全仓测试、真实 Celery Worker 与 MySQL 环境的端到端运行。Celery 任务名与参数未改，Worker 入口只改了访问路径，由 `test_fastapi_jobs_backend` 的 eager 队列路径覆盖。
