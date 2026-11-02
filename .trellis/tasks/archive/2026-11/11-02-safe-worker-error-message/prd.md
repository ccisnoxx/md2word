# Worker 失败消息不记录异常原文

## 目标

DocumentJob Worker 失败时写入任务 `error_message`、`stage_failed` 事件与错误日志的消息，不再包含任意异常的消息原文（可能含路径、配置、源文本或上游响应）；只保留由固定错误码或固定文本构造的消息。

## 背景（基线 `codex/failure-context-20261102`，含 P0-6）

- `execution._worker_failure_message` 仅对完整性错误、MinerU 外部调用、OSError 给固定消息，其余 `return str(error)`。
- 翻译流程另有 5 处 `error_message=str(exc)`（含一处 `except Exception`）；`DocumentIRTranslationError` 会包装任意 `str(exc)`。
- 消息由固定码构造、可安全保留的类型：`MinerUArtifactValidationError`、`TablePlaceholderError`、`TableRenderError`、`TableBuildError`、`TableEvidenceError`、`TableValidationError`、`TranslationIntegrityError`。

## 要求

1. `_worker_failure_message` 成为 Worker 失败消息的唯一构造点：上述安全类型保留原消息；`DocumentIRTranslationError` 输出 `翻译处理失败：{code}。`；完整性/MinerU/OSError 维持现状；其余异常输出 `Worker 执行失败（{异常类型名}），详见事件 trace_id。`。
2. 翻译流程 5 处 `error_message=str(exc)` 改为经该函数构造。
3. 不改变 `error_code`、`failed_stage`、失败分类与 `failure_context`；不改变翻译批次自身的诊断消息与 API 请求校验错误。

## 非目标

- 历史已持久化的 `error_message` 不迁移；`ApiError` 请求响应文案不在范围。

## 验收条件

- AC1：渲染/转换中的普通 `ValueError` 失败，任务 `error_message` 与事件不含异常原文，含异常类型名。
- AC2：安全类型（如 `invalid_image_asset` 验证失败、表格渲染错误）消息与现状一致。
- AC3：翻译 Provider 包装错误输出固定文案与机器码。
- AC4：相关测试与基线一致；依赖原文断言的测试逐条核对。

## 决策记录

2026-11-02 用户要求“收紧普通异常的 error_message，不再记录异常消息原文”；轻量任务，PRD 即实施依据。

## 实施结果（2026-11-02 北京时间）

- `_worker_failure_message` 按要求改造，新增 `SAFE_MESSAGE_ERRORS`；翻译流程 5 处 `error_message=str(exc)` 改为经该函数（另 2 处原本已使用）。
- 新增 `tests/test_worker_failure_message.py` 3 例；P0-6 端到端测试恢复为断言 `error_message` 不含异常原文且含类型名。
- 回归：执行阶段、翻译批次失败语义、DocumentIR 翻译、本地质量矩阵、失败诊断、渲染失败上下文、图片回退共 81 例，6 失败 5 错误与基线集合及失败原因行一致。
