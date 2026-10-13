---
doc_type: workflow-spec
status: target
last_reviewed: 2026-10-03
---

# 工作流与状态机

## 1. 状态维度

系统不得使用单一状态同时表达执行、质量和交付。

| 维度 | 状态 |
|---|---|
| 执行 | `pending/queued/running/succeeded/failed/canceled` |
| 阶段 | `uploaded/.../completed/failed/canceled` |
| 质量 | `pending/passed/warning/blocked` |
| 复核 | `unreviewed/approved/needs_fix/blocked` |
| 交付 | `internal_draft/ready_to_publish/published` |

## 2. 直接转换状态机

```mermaid
stateDiagram-v2
  [*] --> uploaded
  uploaded --> parsing: Worker 接单
  parsing --> parsed: MinerU 结果有效
  parsing --> failed: MinerU 失败/超时
  parsed --> ir_converting
  ir_converting --> rendering: DocumentIR 完整
  ir_converting --> failed: 确定性内容丢失
  rendering --> quality_checking: DOCX 已生成
  rendering --> failed: DOCX 生成失败
  quality_checking --> uploading
  uploading --> completed
  completed --> [*]
```

直接任务必须跳过翻译相关阶段和资源。

## 3. 翻译任务状态机

```mermaid
stateDiagram-v2
  [*] --> uploaded
  uploaded --> parsing
  parsing --> parsed
  parsed --> ir_converting
  ir_converting --> translating
  translating --> translation_validating: 所有叶子批次完成
  translating --> failed: 批次最终失败
  translation_validating --> rendering: 完整性通过
  translation_validating --> failed: Token/ID/公式校验失败
  rendering --> quality_checking
  quality_checking --> uploading
  uploading --> completed
  completed --> [*]
```

## 4. 翻译批次状态机

```mermaid
stateDiagram-v2
  [*] --> pending
  pending --> queued
  queued --> running
  running --> succeeded
  running --> queued: retryable error 且预算未耗尽
  running --> split: truncation/size 错误
  split --> canceled: 父批次停止执行
  split --> [*]: 创建子批次
  running --> failed: 非重试错误或预算耗尽
```

主任务只有在所有有效叶子批次 `succeeded` 后才能进入 `translation_validating`。

## 5. 质量状态聚合

### `passed`

- 无 blocking flag；
- 无 warning flag，或只有被配置为非阻断的信息性标记。

### `warning`

- 有人工必须查看的问题；
- 文档仍具备交付可能；
- QA 批准后可发布。

### `blocked`

任一条件满足：

- 关键表格 HTML 缺失；
- 关键图片缺失；
- DocumentIR 完整性失败；
- 翻译技术 Token 变化；
- 翻译项目缺失；
- DOCX 无法打开；
- Word 内容被裁切或表格覆盖；
- 使用了非编辑表格占位；
- 规则配置的严重表格结构错误。

blocked 任务可以 `execution_status=succeeded`，因为系统已经成功生成内部诊断草稿。

## 6. 复核状态迁移

```mermaid
stateDiagram-v2
  [*] --> unreviewed
  unreviewed --> approved
  unreviewed --> needs_fix
  unreviewed --> blocked
  needs_fix --> unreviewed: 新 generation 生成
  blocked --> unreviewed: 新 generation 生成
  approved --> unreviewed: 结果文件变化
```

约束：

- `quality_status=blocked` 时后端必须拒绝 `approved`；
- ReviewRecord 绑定具体 result file/hash；
- 新结果不能继承旧批准。

## 7. 发布状态机

```mermaid
stateDiagram-v2
  [*] --> internal_draft
  internal_draft --> ready_to_publish: succeeded + non-blocked + approved
  ready_to_publish --> published: Admin 发布
  ready_to_publish --> internal_draft: 新结果/质量变化/撤销批准
  published --> [*]
```

发布后的文件不允许原地替换。需要新结果时创建克隆任务或新 publication generation。

## 8. 下载策略

后端返回操作可用性，不由前端推断：

```json
{
  "download": {
    "enabled": true,
    "classification": "internal_only",
    "warning_code": "quality_blocked_not_deliverable"
  },
  "publish": {
    "enabled": false,
    "disabled_reason": "quality_status_blocked"
  }
}
```

## 9. 重试策略

### MinerU/转换阶段重试

- 使用同一任务 `retry_count/generation`；
- 保留旧事件和 Artifact；
- 新生成结果使 Review 状态回到 `unreviewed`；
- 已发布任务不得原地重试覆盖。

### 翻译批次重试

- 只重试失败批次；
- 确定性错误（ID 缺失、Token 变化）默认不直接重复同一响应，应拆分或失败；
- Provider 临时错误可重试；
- 每个 root batch 有调用预算。

## 10. 取消

- pending/queued/running 可请求取消；
- 已发送给 MinerU 或 Provider 的请求可能无法物理取消，但结果回流时必须根据 generation/status 幂等忽略；
- 取消不删除 Artifact 和事件；
- 取消后的任务可克隆。

## 11. 失败分类

```text
input_error
mineru_submission_error
mineru_callback_error
artifact_download_error
mineru_artifact_invalid
source_ir_integrity_error
translation_provider_error
translation_integrity_error
render_error
quality_pipeline_error
artifact_upload_error
```

错误码必须机器可读，用户文案可以中文。

## 12. 事件要求

每个阶段至少记录：

- started；
- succeeded 或 failed；
- duration；
- generation；
- trace ID；
- 非敏感摘要。

翻译批次、QA、批准和发布有独立事件类型。
