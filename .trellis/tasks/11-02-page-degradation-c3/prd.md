# C3：渲染阶段整页降级

父任务：`11-02-partial-success-page-degradation`（D1–D6、D2' 见父任务 PRD；C1+C2 已完成并归档于 `archive/2026-11/11-02-page-degradation-c1c2`）。

## 目标

Word 渲染时某个操作失败，且 P0-6 的失败定位给出了源页码时，不再让整份文档失败：把该页（及其表格依赖页）按 C1 的同一方式替换为提示 + 原 PDF 整页图像，重新渲染一次；仍失败才整体失败。任务成功时质量 `blocked`、交付 `internal_draft`。

## 背景

- P0-6：`word_renderer` 抛出的异常带 `failure_context`（`operation_kind`、`block_ids`、`source_page_index` 等），已经白名单落入事件与失败诊断。
- C1+C2：converter 在 IR 层把降级页源块替换为合成提示段落与整页图像块，记录 `metadata.degraded_pages`；来源对账扣除降级源块；渲染器与渲染证据不感知降级。
- 渲染阶段读取已持久化的 IR 文件（`job.document_ir_file_id`），渲染证据、结果凭据（`prepared_result.document_ir_file_id`）、发布溯源与恢复流程都绑定这个文件。因此降级后的 IR 必须作为新 IR 文件持久化并切换任务指针，不能只在内存里改。
- 质量：C1 的降级原因是验证报告里的非中止 blocker；渲染阶段降级没有验证问题，需要另一条进入 `base_quality` blocker 计数的路径。

## 范围

1. 触发：`render_to_result` 抛出的异常带 `failure_context` 且 `source_page_index` 非空；排除基础设施与完整性类错误（文件读写、OSError、ApiError、`TablePlaceholderError`、`DocumentIntegrityError`、MinerU 错误）。质量检查阶段（渲染证据）的失败不降级。
2. 依赖闭包：沿用 C2 规则，基于 IR 中已挂接的逻辑表格组；组跨降级页则全组页降级；组含合并回执（`block_id is None`）则放弃。
3. 前提与阈值：非翻译任务；源 PDF 与整页栅格器可用；降级页总数（含 C1 已降级页）× 2 ≤ 页数；失败页尚未被降级（已是合成块的页再失败则整体失败）。任一不满足 → 按原渲染错误整体失败（与现状一致）。
4. IR 替换：复用 C1 的页替换逻辑（抽为 converter 与执行层共用的函数），额外移除被删表格的逻辑表格组、表格参考图资产与占位绑定，并重算组计数；`degraded_pages` 记录增加 `trigger`（`validation` / `render`）与渲染失败的 `operation_kind`、`reason_code`。
5. 持久化：登记整页图像资产与新 IR 文件，以条件更新把 `document_ir_file_id` 从旧 IR 切换到新 IR，并追加图像文件 ID；记录一条降级事件（复用现有事件类型，不新增）。
6. 重新渲染：只重试一次；第二次失败按第二次的错误整体失败。
7. 质量：渲染阶段降级页计入 `base_quality` blocker，`quality_status=blocked`、交付 `internal_draft`。

## 非目标

- 翻译模式任务的渲染降级（归 C4）；质量检查阶段失败的降级；多轮迭代降级；`validate()` 阶段块结构错误。

## 验收条件

- AC1：某页渲染失败（带页码）的非翻译任务成功；该页为提示 + 整页图像，其他页可编辑；`quality_status=blocked`、`delivery_status=internal_draft`，批准被拒。
- AC2：任务的 `document_ir_file_id` 指向降级后的新 IR；结果凭据、渲染证据、来源对账、逻辑表格组校验都基于新 IR 通过；Worker 在切换后中断，重投可直接按新 IR 渲染。
- AC3：失败页属于跨页表格组时组内各页一起降级；含合并回执时整体失败。
- AC4：无页码、基础设施错误、超过阈值、无源 PDF/栅格器、翻译任务、降级后重渲染仍失败时整体失败，失败诊断与现状一致。
- AC5：不触发降级的任务行为与基线一致。

## 待确认决策

- **D1 触发错误范围**：带 `source_page_index` 的渲染期异常，排除基础设施与完整性类（推荐）；或只限表格类错误（`TableRenderError`）。
- **D2 重试次数**：只降级并重渲染一次（推荐，与父 PRD 一致）；或循环降级直到成功或触及阈值（每轮一次完整渲染，成本随失败页数增长）。
- **D3 降级 IR 的持久化**：登记新 IR 文件并条件切换任务指针（推荐，保持“结果绑定的 IR 就是渲染所用 IR”）；备选为只在内存降级，需要放宽结果凭据与恢复流程对 IR 的绑定（不推荐）。
- **D4 质量信号**：`degraded_pages` 记录加 `trigger`，来源对账输出 `render_degraded_page_count`，`base_quality` 计入 blocker（推荐）；备选为向 MinerU 验证报告追加问题（会改动带哈希的产物验证合同，不推荐）。
- **D5 翻译任务**：本任务不做，保持整体失败，归 C4（推荐）。

### 决策记录

2026-11-02 用户确认 D1–D5 均按推荐：带页码的渲染期异常触发（排除基础设施与完整性类）；只降级并重渲染一次；降级 IR 另存新文件并条件切换任务指针；`degraded_pages.trigger` + 来源对账 `render_degraded_page_count` 计入 `base_quality` blocker；翻译任务不做，归 C4。
