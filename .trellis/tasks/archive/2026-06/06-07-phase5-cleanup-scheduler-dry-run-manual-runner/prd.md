# Phase 5 cleanup scheduler dry-run manual runner

## Goal

新增 Admin-only 手动触发的 cleanup scheduler dry-run runner：请求期间获取 cleanup distributed lock，生成 readonly cleanup report，写入 durable history，然后释放锁。

本任务不引入后台 scheduler loop、不执行物理删除、不执行 S3 delete、不调用 provider 或外部告警服务。

## Requirements

- 新增 `POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`。
- 只允许 Admin 调用。
- 调用流程必须：
  - acquire cleanup lock；
  - build readonly cleanup report；
  - persist scheduler dry-run history；
  - release cleanup lock。
- 如果 lock 已被 active owner 持有，返回 409，不生成 report，不执行 cleanup。
- 响应必须包含：
  - dry-run `run_id`；
  - readonly report；
  - lock owner / fencing token / acquired / released 摘要；
  - safety metadata。
- Durable history 必须包含 `action_mode=scheduler_dry_run`、safe readonly report、lock fencing token 和 safety flags。
- 不生成 executable signed cleanup plan；manual scheduler dry-run 不是删除授权。
- 不调用 physical-delete preview/execute。
- 不修改 `document_files` metadata。
- 不写成功 cleanup execute audit。

## Acceptance Criteria

- [ ] Admin manual scheduler dry-run 返回 200，包含 readonly report、lock 和 safety。
- [ ] Operator 调用返回 403。
- [ ] Active lock 存在时返回 409，且不会写新的 dry-run history。
- [ ] Dry-run history 可通过现有 history list/detail 读取，且不包含 object_key、本地路径、bucket、文件内容或 secret。
- [ ] Dry-run 后 lock 被释放。
- [ ] Targeted backend tests、OpenAPI export/test、frontend build、Trellis validate、`git diff --check` 通过。

## Non-goals

- 不做 autonomous destructive scheduler。
- 不做 recurring loop/cron/background worker。
- 不做 physical delete preview/execute。
- 不做真实 S3 delete。
- 不做 provider cancellation。
- 不做 real Slack/email/webhook。
- 不运行 pdf-mineru 解析、翻译 provider 或 Word 生成主流程。
