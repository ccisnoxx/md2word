# Document job files and results

## Goal

在任务详情页补齐“文件/结果/日志”区，让 Operator/Admin 不离开任务上下文即可查看源 PDF、生成 Word、解析/IR 中间文件、AI 调用日志和可选 debug 归档的元数据、可下载状态和临时下载入口。

本子任务只做任务详情内的文件可追溯与下载授权，不触发 pdf-mineru 解析、翻译或 Word 生成主流程。

## Requirements

- 后端提供任务级文件汇总 API，按现有 document job 可见性权限返回该任务已登记的 `document_files`。
- 后端复用现有任务下载授权语义，保持默认结果 Word 下载兼容，同时支持按 `file_id` 获取同一任务内文件的临时下载链接。
- 文件下载必须校验：
  - 当前用户可见该任务；
  - 文件属于该任务或是该任务绑定的源文件；
  - 文件状态为 `uploaded`；
  - 文件未过期；
  - 文件类型属于任务产物范围：源 PDF、MinerU 原始结果、DocumentIR、图片资产、生成 Word、AI call log、AI debug archive。
- 前端任务详情页新增文件/结果区，展示文件角色、类型、文件名、大小、状态、过期时间和文件 ID。
- 前端只对可下载文件启用下载按钮；未生成、未上传、已过期或后端拒绝下载时展示明确不可用状态。
- 现有顶部“下载”动作继续下载生成 Word，不改变用户已有路径。
- 权限边界沿用现有 Operator/Admin 规则：Operator 只能访问自己的任务文件，Admin 可访问同租户/公司内可见任务。

## Acceptance Criteria

- [ ] `GET /api/v1/document-jobs/{job_id}/files` 返回当前用户可见任务的已登记文件列表，包含 source PDF、generated Word、MinerU raw、DocumentIR、AI log/debug 等已存在文件。
- [ ] `GET /api/v1/document-jobs/{job_id}/download-url` 不传 `file_id` 时保持现有 generated Word 下载行为；传 `file_id` 时可为同任务内已上传且未过期文件签发临时下载链接。
- [ ] 不允许下载其他任务文件、其他用户不可见任务文件、未上传文件、已过期文件或不属于任务产物范围的文件，并返回明确 403/404/409。
- [ ] 任务详情页展示文件/结果区；完成任务能看到源 PDF、生成 Word 和中间产物，翻译任务能看到 AI call log，可选 debug archive 存在时能看到保留/过期信息。
- [ ] 行级下载使用临时链接，不在前端保存长期 URL；顶部下载仍能下载结果 Word。
- [ ] 归档任务仍可查看文件列表和可用下载，不执行真实文件删除。
- [ ] 实现和验证不重跑外部 pdf-mineru 解析、真实翻译服务或生产 Word 主流程；测试使用现有 fake/eager runtime。

## Notes

- Explicit non-goals:
  - 不做独立文件管理页。
  - 不做物理删除、清理、保留策略编辑或存储空间管理。
  - 不做完整术语规则 CRUD 工作台。
  - 不做翻译结果段落对照质检页。
  - 不新增重跑解析/翻译/生成 Word 的入口。
