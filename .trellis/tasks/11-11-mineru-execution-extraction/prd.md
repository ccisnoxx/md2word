# MinerU 回调段提取

## 目标

翻译段（PR #39）和渲染段（PR #40）提取后，`app/domains/document_jobs/execution.py` 还有 1560 行。其中 MinerU 解析提交、回调排队与重放、结果下载登记共 15 个方法、553 行，有三个进入点：`execute_job` 中的两个入口，以及回调路由调用的两个公开方法。本任务沿用前两次的做法，把这部分提取为独立协作者。提取后宿主约 1010 行，只保留状态推进、IR 转换、任务级收口和事件。

本任务只建立宿主与 MinerU 段之间的边界，不改任何行为。度量见 [research/current-state.md](research/current-state.md)。

## 范围

- 新建 `app/domains/document_jobs/mineru_execution.py`，迁入 research §2 列出的 15 个方法。
- 宿主构造并持有协作者 `self.mineru`。`callback_message_store`、`mineru_client_factory`、`mineru_config_resolver` 不再由宿主持有。
- 宿主内 2 处入口改为经 `self.mineru` 访问。默认客户端工厂改为在协作者内取值。
- 回调路由的 2 处调用、测试中的 8 处访问改为经 `mineru` 访问。
- 更新 `directory-structure.md` 的文件列表。

## 非目标

- 不改方法名、签名、方法体逻辑、回调去重与重放语义、错误码、事件、阶段流转、持久化格式和回调路由的 HTTP 合同。
- `_mark_parsing_started`、`_get_mineru_raw_result_file` 以及任务级收口方法留在宿主。
- 宿主上不保留 `find_job_for_mineru_callback`、`enqueue_mineru_callback_for_job` 的转发方法。
- 不改测试装配中挂在宿主上的 `fake_mineru_client` 辅助引用（research §6）。
- 不缩减宿主构造签名，不修复与本次无关的既有测试失败。
- 不涉及回调身份校验（`app/domains/jobs/mineru_callbacks_router.py` 中的 `verify_*`）。

## 约束

- 与前两次一致：先用 Mixin 纯搬移，再改为协作者；每个阶段都用 AST 等价脚本核对。
- 协作者在调用时经 `self._host` 查找宿主方法，不捕获绑定方法。
- `mineru_execution.py` 不在运行时导入 `execution.py`。
- 提交时只纳入本任务的文件和行，不带上工作区中其他会话的改动。

## 验收标准

- [ ] AC-1 阶段一：15 个方法（含 `@staticmethod` 装饰器）与基线 AST 逐一等价，宿主其余方法逐一等价；不改任何测试。
- [ ] AC-2 阶段二：协作者方法去掉 `_host` 一跳后与基线等价；协作者只访问 5 个宿主方法；宿主只经 `_process_replayable_callback_messages`、`_run_mineru_parse` 两个入口访问协作者。
- [ ] AC-3 3 个 MinerU 依赖只由协作者持有，宿主没有同名属性，也没有转发方法；宿主构造签名不变；未传入工厂时，协作者的默认工厂行为与基线相同。
- [ ] AC-4 外部合同不变：回调路由的请求与响应、OpenAPI、回调去重键、消息状态流转、事件、错误码、阶段流转、MinerU 原始结果的文件登记格式。
- [ ] AC-5 定向测试的结果清单（用例、状态、最终异常行）在阶段一、阶段二都与基线逐行一致；测试只改访问路径。
- [ ] AC-6 全仓检索：经执行服务访问迁出方法和 3 个 MinerU 依赖的旧写法为 0。
- [ ] AC-7 `directory-structure.md` 的文件列表已更新。

## 评审决策（2026-11-11 用户确认）

1. **命名**：模块 `mineru_execution.py`、类 `MinerUExecution`、宿主属性 `mineru`。
2. **公开方法**：宿主上不保留转发方法，回调路由改为 `runtime.document_job_execution_service.mineru.<方法>`。
3. **阶段二**：做。阶段一完成后直接进入阶段二，`implement.md` 评审点 A 视为已确认。
