# 子代理上下文与工作边界

当前任务：`.trellis/tasks/11-10-documentation-evidence-governance`。

实施前必须读本任务 prd.md、design.md、implement.md 和当前批次清单。2026-11-10 用户已明确批准本稿按四批顺序实施；主会话通过 task.py start 激活后，代理才可按分配范围修改维护文档。不得更改产品 Manifest 执行状态或自行扩大范围。

上下文中的质量 Spec 只用于保持依赖说明和仓库卫生的既有合同，不因此执行其中与本任务无关的产品测试或发布流程。项目 AGENTS 的文档验证边界优先于通用清单。

大清单 `research/document-inventory.json` 不全量注入；按 proposed_batch 读取当前批次路径及元数据即可。目录／日期不是生命周期判断依据，所有 proposed_doc_status 和 proposed_owner 在规划中均保持 null。

如果未来派发写入代理，每次 prompt 以 `Active task: .trellis/tasks/11-10-documentation-evidence-governance` 开头，明确当前批次和路径所有权；说明不是独占工作区，不得回退其他修改，要求中文摘要。主会话拥有任务记录与跨批协调，不让多个代理同时编辑导航和 Manifest。检查代理复核候选差异，不以任务完成消息替代证据。
