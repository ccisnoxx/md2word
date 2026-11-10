# B04 后续：翻译批次执行子系统提取

状态：规划草案，待评审。未获实施授权；评审通过并执行 `task.py start` 前不改动应用代码。

## 背景

`app/domains/document_jobs/execution.py` 共 4128 行，`DocumentJobExecutionService` 一个类同时承担任务状态推进、MinerU 调用与回调、IR 转换、翻译批次执行、渲染和失败收口。架构文档已把它列为待收口项（`docs/architecture/system-architecture.md:265`）。

翻译批次执行是其中边界最清晰的一块：有独立的 Worker 入口、独立的仓储端口和独立的 Spec（`.trellis/spec/backend/translation-batch-lifecycle.md`），占 34 个方法、1888 行，对类内其余部分只依赖 7 个方法。度量见 [research/current-state.md](research/current-state.md)。

本任务承接整改总计划 B04（`.trellis/tasks/11-06-source-audit-remediation-plan/design.md:72-78`）的试点，沿用其取舍：按内聚职责提取，不引入通用阶段框架。

## 目标

把翻译批次执行逻辑从 `DocumentJobExecutionService` 提取为同目录下的独立协作者，使翻译批次的执行 owner 唯一、它对任务级状态收口的依赖显式且有限。运行行为不变。

## 范围

- `app/domains/document_jobs/execution.py`、新增的 `app/domains/document_jobs/translation_execution.py`。
- 三处类外调用方的访问路径：`app/workers/document_tasks.py`、`app/domains/document_jobs/router.py`、`app/main.py`。
- 受影响测试的访问路径迁移。
- 两份 Spec 的 owner 表述：`translation-batch-lifecycle.md`、`directory-structure.md`。

## 非目标

- 不新增 `JobStageHandler`、`StageContext`、`StageResult` 或其他通用阶段框架。
- 不改方法名，不调整方法体内的逻辑、错误码、消息、事件或 CAS 条件。
- 不删除疑似无调用方的 `_translate_document_ir`，不清理其他死代码。
- 不迁移四个任务队列类和两个队列 Protocol。
- 不继续细分新模块内部（领取与租约、失败与拆分、汇合回填）。
- 不提取渲染、MinerU、IR 转换，不改 `service.py`、`main.py` 的装配结构。
- 不改数据库、持久化格式、HTTP 响应、Celery 任务名与参数。
- 不修复与本次改动无关的既有测试失败。

## 约束

- 分两个阶段交付，每个阶段结束都是可独立保留、可独立回退的状态。阶段二是否执行，在阶段一验收后由用户确认。
- 在任务分支上实施；提交前出提交计划并经确认，不自动推送。
- 新增或实质改动的注释、docstring 使用中文；原样搬移的方法体不改写。

## 验收标准

- [ ] AC-1（阶段一，搬移等价）：迁出的 34 个方法与两个模块级定义，其 AST 与基线逐一相同；留在宿主的方法 AST 与基线相同。差异只出现在类定义头、导入和所在模块。
- [ ] AC-2（阶段二，接线受限）：协作者访问宿主仅限 `research/current-state.md` §2 列出的 7 个方法；宿主访问协作者仅限 3 个内部入口和公开方法。把 `self._host.<名字>` 归一回 `self.<名字>` 后，迁出方法的 AST 仍与基线相同。
- [ ] AC-3（阶段二，owner 唯一）：5 个翻译专属依赖只由协作者持有；宿主上不存在同名属性，也不存在迁出方法的转发包装。
- [ ] AC-4（外部合同不变）：`DocumentJobExecutionService` 构造签名、Celery 任务名与参数、`GET /api/v1/document-jobs/{job_id}/translation-batches` 响应、事件类型与顺序、错误码与消息、任务阶段流转、持久化格式均不变。
- [ ] AC-5（测试）：受影响测试模块的通过/失败集合与同一环境下的基线运行一致，没有新增失败。测试改动只限访问路径和 `patch.object` 目标对象，不改断言、不删用例。
- [ ] AC-6（无静默失效）：阶段二后，全仓检索不到对宿主上已迁出属性或方法的读、写或打补丁。
- [ ] AC-7（Spec）：两份 Spec 中“`execution.py` 负责翻译批次执行”的表述改为新模块，其余合同文字不变。

## 待评审决策

1. 是否执行阶段二。建议执行；只做阶段一的话得到的是物理拆分，职责仍在同一个对象上。
2. `_translate_document_ir` 是否另开小任务确认并删除。本任务只原样搬移。
