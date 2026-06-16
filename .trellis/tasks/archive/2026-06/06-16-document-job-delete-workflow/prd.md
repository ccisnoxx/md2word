# Document Job Delete Workflow

## Goal

完善任务工作台的任务生命周期能力：在现有归档能力之外，新增 Admin-only 的任务删除预览与执行流程。删除应清理可安全删除的关联文件，同时保留任务 metadata、事件和 audit 证据，避免把“归档”误用为“删除”。

## Requirements

- 保持现有 `DELETE /api/v1/document-jobs/{job_id}` 的归档语义不变。
- 新增单任务删除预览接口，Admin-only、只读、无副作用。
- 新增单任务删除执行接口，Admin-only，必须提交 `reason`、`confirmation` 和 `preview_hash`。
- 删除仅允许 `succeeded`、`failed`、`canceled` 终态任务；`pending`、`queued`、`running` 返回 `409 conflict`。
- 删除采用 tombstone 语义：任务默认列表隐藏，但保留任务 metadata、事件和审计证据。
- 删除执行应清理可安全删除的关联文件；被其他任务引用的 source/result/intermediate/debug 文件必须保留并在预览中说明。
- 文件物理删除复用现有 retention/physical-delete 语义，不引入第二套危险删除实现。
- S3 文件不执行真实删除，沿用现有 unsupported/fake safety 语义。
- `available_actions` 增加 `delete`，前端按钮可用性以后端为准。
- 前端在任务详情和任务列表提供 Admin-only 删除入口；删除必须经过 preview、reason、confirmation。
- 前端文案明确区分：归档是可恢复隐藏；删除是 Admin-only 危险操作，会按预览清理可安全删除文件。
- 文档、OpenAPI、前端类型、mock/smoke 和后端测试同步更新。

## Acceptance Criteria

- [ ] Admin 可对终态任务调用 delete preview，响应包含删除文件、保留文件、保留原因、确认短语、`preview_hash` 和 safety 摘要。
- [ ] Admin 提交正确 `reason`、`confirmation`、`preview_hash` 后可删除终态任务。
- [ ] Operator 调用 delete preview/execute 返回 `403`。
- [ ] Active 任务 delete preview/execute 返回 `409`，提示需先取消任务。
- [ ] 已删除任务默认不出现在 `GET /api/v1/document-jobs` 列表中。
- [ ] 删除后任务详情仍可按权限读取，能看到 `deleted_at`、`deleted_by`、`delete_reason`。
- [ ] 删除执行写入 `document_job.delete` audit event 和 `job_deleted` 任务事件。
- [ ] 共享文件不会被误删，预览和执行结果均说明保留原因。
- [ ] 前端 admin 详情页和列表行操作可完成删除预览/执行；operator 不显示或不可执行删除。
- [ ] `docs/api/document-jobs.md`、OpenAPI snapshot、`frontend/src/api/types.ts` 与实现一致。

## Definition of Done

- 后端 targeted tests 覆盖权限、状态冲突、预览、执行、共享文件、幂等和 audit/event。
- 前端 unit/smoke 覆盖 action helper、删除确认完整性、admin/operator 权限和 409 错误展示。
- `scripts/ops/check_release.py`、OpenAPI 导出检查、前端 build/unit/smoke 在可用环境中通过，或明确说明无法运行原因。
- 不回滚或覆盖当前工作区中与本任务无关的既有未提交改动。

## Technical Approach

- 在 `document_jobs` 域内新增删除请求/响应 schema 和 service 方法。
- 删除预览基于任务可见文件集合构建 plan，并计算稳定 `preview_hash`。
- 删除执行重新计算预览并校验 hash，避免用户对过期预览执行删除。
- 文件删除只调用现有 `FileUploadService.delete_expired_files` / retention physical-delete 等价能力可安全复用的路径；如果该 primitive 要求 `expired` 状态，则新增受控任务删除 adapter，但仍使用同一底层 storage delete 和 metadata update 逻辑。
- `DocumentJobRecord` 增加 tombstone 字段，repository payload 后端保持兼容；列表默认排除 deleted，详情允许读取。
- 前端新增 delete preview/execute API wrapper，任务操作组件增加 `delete` action，详情页实现危险确认弹窗。

## Decision (ADR-lite)

**Context**: 现有 `DELETE /document-jobs/{job_id}` 已用于归档，直接改变语义会破坏当前前后端合同。

**Decision**: 保持归档接口不变，新增显式 `delete-preview` 和 `delete` 接口。删除为 Admin-only，采用 tombstone + 文件清理计划，必须 preview -> reason -> confirmation -> execute。

**Consequences**: API 表面略增，但避免兼容破坏，并保留完整审计。后续可在 P1 增加批量删除和删除记录筛选。

## Out of Scope

- 不处理 Word 输出质量、Golden Sample 人工质量或 renderer parity。
- 不实现 operator 删除、删除申请审批流或批量删除。
- 不执行真实 S3 删除。
- 不删除 audit/event 追溯记录。
- 不重构整个任务工作台或全站导航权限模型。

## Technical Notes

- 现有归档接口：`DELETE /api/v1/document-jobs/{job_id}`，语义为隐藏默认列表，不删除文件或事件。
- 现有任务动作：download、retry、clone、cancel、archive、unarchive。
- 现有文件保留/清理域已有 preview/execute/safety/audit 设计，应复用其安全边界。
- 主要影响文件预计包括：`app/domains/document_jobs/{models,schemas,service,router}.py`、持久化 repository、`frontend/src/api/{documentJobs,types}.ts`、`frontend/src/{components,pages,utils}`、`docs/api/document-jobs.md`、`tests/test_fastapi_jobs_backend.py`、`frontend/tests/smoke/core-flow.spec.ts`。
