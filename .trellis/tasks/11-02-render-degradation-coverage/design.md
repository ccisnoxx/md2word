# 设计

## 多页降级

`execution` 把“渲染 → 失败 → 降级 → 重渲染一次”改为有界循环，复用 `_degrade_render_failure_page`。

- 终止条件：已降级页再失败、超过 50% 阈值、其他前提不满足，或达到 `MAX_RENDER_DEGRADATION_ATTEMPTS = 5`。
- 上限理由：每轮要完整重渲染，失败页很多时逐页重试会耗尽 Worker 时限，得到更差的超时诊断。超过上限按当次错误失败。
- 每轮生成新 IR 并条件切换指针，链路由 `degraded_from_document_ir_file_id` 记录。
- `SoftTimeLimitExceeded` 加入不可降级错误：操作循环的 `except Exception` 同样会给它挂上下文，不排除的话超时后还会继续渲染。

## 计划阶段定位

`word_renderer` 在三个计划步骤上用同一个辅助函数挂上下文，新增 `operation_kind`：`layout_plan`、`table_plan`、`render_plan`，并加入 `FAILURE_OPERATION_KINDS` 白名单。

- `table_plan`：`TableRenderError.block_index` 已是当前 IR 索引，可定位块和页，因此可走降级；其他异常是文档级。
- `render_plan`：`ValueError` 类仍转为 `DocumentIntegrityError`，上下文挂在新异常上，只改善诊断，不降级（保持完整性失败关闭）。
- 执行层提前计算的 `build_layout_plan` 移到渲染成功之后，失败统一经渲染器定位；它是纯函数，只在质量证据处使用。

## 提示文案

`page_degradation` 增加原因码到中文的映射，范围是 `DEFERRABLE_ISSUE_CODES` 加 `render_failed`。文案直接按键取值，不设兜底默认值，并由测试保证覆盖。历史 IR 的已有文本不改。

## 权衡

未选择“一轮渲染收集全部失败页”：渲染器需要在失败后继续写同一份 Word 对象，状态不可靠，改动面也大。
