# Phase 5 signed cleanup plan foundation

## Goal

为 manual cleanup run 增加 signed cleanup plan 基础合同：preview 生成可持久追溯、不可篡改校验的计划摘要；execute 必须绑定同一 run/plan/hash/file_ids，作为后续 scheduler dry-run、distributed lock 和 S3 safety contract 的前置安全能力。

本任务不引入 scheduler loop，不扩大物理删除能力，不调用真实 S3/provider/alert 服务。

## Requirements

- Cleanup run preview 必须生成并返回 cleanup plan：
  - `plan_id`
  - `run_id`
  - `preview_hash`
  - `requested_file_ids`
  - `max_files`
  - `expires_at`
  - `signature`
  - `signature_algorithm`
  - safety flags
- Cleanup run durable history 必须保存同一 cleanup plan 摘要。
- Cleanup run execute 请求可携带 `plan_id` 和 `plan_signature`。
- 当 execute 携带 plan 字段时，后端必须校验：
  - history 中存在同一 `run_id`
  - plan 未过期
  - `plan_id` 与 history plan 一致
  - `plan_signature` 与 history plan 一致
  - `file_ids`、`max_files`、`preview_hash` 与 history plan 一致
- 校验失败必须返回 conflict 或 invalid request，不执行 physical delete，不写成功 audit，并记录 failed history。
- 兼容旧客户端：未携带 plan 字段的 execute 仍按现有 `run_id + preview_hash` 合同执行，但响应和 history 应包含 plan。
- Plan signature 使用本地 deterministic HMAC，secret 来源优先使用已存在配置，不新增真实 secret 管理依赖。
- 不在 plan/history 响应中写入或返回 object key、本地路径、bucket、文件内容、checksum、etag、raw metadata、credentials 或 provider payload。

## Acceptance Criteria

- [ ] Preview 响应包含 `cleanup_plan`，history detail/list 也包含同一 plan。
- [ ] Execute 携带正确 `plan_id` 和 `plan_signature` 时成功沿用同一 `run_id`，并把 history 更新为 executed。
- [ ] Execute 携带错误 plan signature / plan id / file_ids / preview hash 时返回 409，不执行物理删除。
- [ ] Unknown run_id 仍记录 failed history，不执行物理删除。
- [ ] 旧 execute 请求不传 plan 字段仍兼容。
- [ ] OpenAPI、API docs、frontend TS contract 更新。
- [ ] Targeted backend tests、OpenAPI export/test、frontend build、Trellis validate、`git diff --check` 通过。

## Non-goals

- 不做真实 S3 delete。
- 不做 scheduler loop 或无人值守 destructive cleanup。
- 不做 distributed lock。
- 不做 provider cancellation。
- 不做 real Slack/email/webhook alert delivery。
- 不运行 pdf-mineru 解析、翻译 provider、Word 生成主流程。
