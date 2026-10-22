# TR-406 执行接线合同

本文件记录 `execution.py` 已接入的执行侧边界，存储原子端口以同目录的
`storage-contract.md` 为准。执行器不在本地复制批次树、预算或停止规则。

## 已接入的纯判定与停止闸门

- `summarize_translation_generation()` 从当前不可变 source DocumentIR、绑定的
  Translation Profile/term snapshot 和本代配置重新计算 `TranslationRootPlan`，再调用
  `workflow.reduce_translation_generation()`；不能用现有批次记录反推预期根计划。
- finalizer 先消费 reducer 结论。终态失败、残缺树、非法叶子状态或待消费预算耗尽时，
  立即把任务收口为 `failed/translating/translation_failed`，不等待 running 兄弟。
- `execute_translation_batch()` 在 claim 前和 Provider 返回后重新检查同代结论。已有
  terminal/tree-invalid 结论时拒绝新 Provider 结果晋升；已发生的真实调用只保留已有
  安全审计和内部诊断身份。
- enqueue/claim 入口在同代结论为 terminal/completed/canceled/validating 时停止新工作，
  并调用同代幂等 finalizer。普通 CAS 竞争或旧 generation 不被解释为新失败。

## 结果与 API 投影

- `GET /api/v1/document-jobs/{id}/translation-batches` 保留旧批次字段，追加 nullable
  `execution` 和逐行 `is_effective_leaf`、`failure_disposition`。direct 任务不读取翻译
  批次并返回 `execution=null`。
- split 父节点只显示 `superseded`，不进入 leaf 计数；终态失败后的排队/运行兄弟显示
  `stopped`。`translation_batch_result` 仍是内部中间证据，不产生下载授权或主件资格。

## 已接入的存储合同

execution 已按 `storage-contract.md` 使用窄原子端口：根计划一次性安装与同代快照、带
expected generation/attempt/lease 的 claim、排队/成功/失败条件提交、过期租约释放，以及
携带同一 `expected_plans` 的 split 事务。端口返回 `None` 时按普通竞争、旧代或停止结论
处理，并读取同代快照交给 reducer/finalizer；真实文件、JSON、SQL、锁错误继续上抛到阶段
错误映射，不使用兼容 fallback。
