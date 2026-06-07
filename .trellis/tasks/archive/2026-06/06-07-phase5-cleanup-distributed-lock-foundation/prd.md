# Phase 5 cleanup distributed lock foundation

## Goal

为后续 cleanup scheduler dry-run / manual runner 建立 distributed lock foundation：同一时间只允许一个 cleanup automation owner 持有租约，并通过 fencing token 防止旧 owner 释放或覆盖新 owner。

本任务只实现锁模型、服务、持久化和测试，不启动 scheduler，不执行物理删除，不调用 S3/provider/alert 服务。

## Requirements

- 新增 cleanup lock domain model 和 service。
- 支持固定 lock name：`file_retention_cleanup`。
- 支持 acquire：
  - 没有锁、锁已释放、锁已过期时可以获取。
  - 未过期 active lock 存在时返回 conflict。
  - 成功获取时生成单调递增 `fencing_token` 和新的 `owner_id` 租约。
- 支持 refresh：
  - 仅当前 owner + fencing token 可刷新。
  - 已过期、已释放或 token 不匹配时返回 conflict。
- 支持 release：
  - 仅当前 owner + fencing token 可释放。
  - release 后不再视为 active。
- 支持 read/status：
  - 返回 effective active/expired/released 状态。
  - read 不执行 cleanup、不修改 document_files、不写 audit。
- file/sqlite/MySQL metadata backend 必须能持久化锁记录。
- 不返回 secret、文件路径、object_key、bucket、provider payload 或 cleanup plan signature 之外的敏感信息。

## Acceptance Criteria

- [ ] file/sqlite/MySQL adapter contract 覆盖 acquire/refresh/release/expired takeover/fencing token。
- [ ] Active unexpired lock 阻止第二个 owner acquire。
- [ ] Expired lock 允许新 owner acquire，并生成更大的 fencing token。
- [ ] 旧 owner/token 不能 refresh 或 release 新锁。
- [ ] 不新增 scheduler loop，不执行 cleanup run，不执行真实 S3 delete。
- [ ] Trellis validate、targeted tests、`git diff --check` 通过。

## Non-goals

- 不实现 scheduler dry-run runner。
- 不实现 autonomous destructive cleanup。
- 不执行或模拟 physical delete。
- 不做 distributed DB advisory lock；本切片只建立 metadata lock contract。
- 不新增前端按钮。
- 不运行 pdf-mineru 解析、翻译 provider 或 Word 生成主流程。
