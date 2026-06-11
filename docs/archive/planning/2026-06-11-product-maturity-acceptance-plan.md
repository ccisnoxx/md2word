# md2word 联调验收计划：产品成熟化

## 验收目标

第一轮验收证明：

- Files 与 Document Jobs 权限边界一致。
- 任务创建配置、readiness、错误体和动作可用性合同稳定。
- Ops recovery preview/execute 的副作用边界可审计。
- 前端能正确展示 blocker、禁用原因、危险确认和诊断信息。

第二轮验收证明：

- 任务详情和 QA 工作台可以稳定处理局部失败、空态、不可用证据和移动端/键盘可访问性。
- Release/worker/OpenAPI/type/mock 的长期维护检查有可执行入口。

## API Contract

- 公开主链路 API:
  - Files upload authorization/content。
  - Document Jobs create/list/detail/events/files/download-url/actions。
  - Ops recovery registry/preview/execute。
- Legacy `/api/v1/jobs`:
  - 不在 OpenAPI。
  - 不出现在新联调命令中。
- 错误合同:
  - nested `error.*` 优先。
  - legacy 字段兼容。
- Config contract:
  - option `resource_id/version/label` 语义一致。
  - 前端 payload 不使用 label 作为业务 key。

## 数据模型 / 状态流

- 活跃任务自动刷新只针对 `pending/queued/running`。
- 失败任务展示 `failed_stage/error_code/error_message`。
- QA 状态只适用于 `en2zh_pdf_to_word`。
- Files source PDF 必须在未绑定 job 时创建 document job。
- Archive 不删除文件；文件删除只走 retention/cleanup。

## 权限 / 错误模型验收

- operator A:
  - 可上传自己的 PDF。
  - 可创建自己的 document job。
  - 不能读取/上传 operator B 的 file id。
- admin:
  - 可进入配置、系统、Ops、文件保留。
  - 可按权限查看跨用户文件/任务。
- structured error:
  - 403 显示权限不足。
  - 409 显示状态冲突。
  - 503 显示 readiness blocker。
  - trace id 可复制。

## 后端接口完成标准

- `POST /api/v1/files/upload-url`
  - 正常创建 authorization。
  - P0 主链路不依赖 `job_id`。
- `PUT /api/v1/files/{file_id}/content`
  - owner/admin 可上传。
  - 其他 operator 返回 403。
- `GET /api/v1/files/{file_id}`
  - owner/admin 可读取。
  - 其他 operator 返回 403。
- `POST /api/v1/document-jobs`
  - ready 时创建成功。
  - unready required 时返回 `document_jobs_not_ready` 且不创建 job。
  - 已绑定 source file 返回 409。
- `GET /api/v1/document-jobs`
  - filters、summary、QA summary、archive 行为不回退。
- Ops recovery:
  - preview 不写 audit、不投递 worker。
  - execute/fake/real action 明确 safety flags。
  - 非 admin 被拒绝。

## 前端接入验收顺序

1. config option helper 单测通过。
2. QA unavailable guard 单测/页面 smoke 通过。
3. release gate routing 单测通过。
4. dangerous confirmation disabled/enabled 单测或 smoke 通过。
5. diagnostic copy 单测通过。
6. operator core smoke 通过。
7. admin system/ops/file-retention smoke 通过。

## Mock 或 Contract First

- 前端 smoke mock 必须覆盖：
  - succeeded job
  - active job
  - failed job
  - readiness blocker
  - 403 forbidden
  - 409 conflict
  - 503 structured error
  - QA unavailable
  - file retention preview/execute
  - ops recovery preview/execute safety
- Mock 字段不得从页面临时拼，应与 OpenAPI/type 同步。

## 单元测试 / 集成测试 / E2E 或 Smoke

- 后端 unit/integration:
  - Files 权限。
  - upload `job_id` 行为。
  - Document Jobs readiness。
  - available_actions。
  - Ops execute gate/audit。
  - OpenAPI legacy jobs removal。
- 前端 unit:
  - errors。
  - auth permission fallback。
  - format/action helpers。
  - config option key。
  - release gate route mapping。
  - QA unavailable guard。
- Smoke:
  - operator document job workbench。
  - config blocked create flow。
  - translation QA queue/detail。
  - admin status/ops/file-retention。

## 端到端验收

- Operator core:
  1. 登录。
  2. 打开 `/jobs`。
  3. 进入 `/jobs/new`。
  4. 上传 PDF。
  5. 创建任务。
  6. 查看 active 状态。
  7. 进入详情查看 events/files。
  8. 成功后生成 download-url。
- Blocker:
  1. P0 required 且 worker disabled。
  2. 创建页显示 readiness blocker。
  3. API create 返回 503。
- Failed:
  1. 列表显示 failed stage/code/message。
  2. 详情诊断可复制 trace。
  3. retry 可用性以后端 available_actions 为准。
- QA:
  1. 队列筛选未复核。
  2. 可用 QA 保存状态。
  3. 不可用 QA 只读。
- Ops:
  1. recovery preview 无副作用。
  2. execute 需要 admin、reason、confirmation。
  3. safety flags 与 audit 一致。

## 风险、回滚点、验证命令

- 权限收口风险：
  - 旧脚本可能使用 operator token 跨 file id。
  - 回滚：改用 admin token 运维脚本，不恢复 operator 越权。
- Config contract 风险：
  - 旧 mock/页面可能使用 label。
  - 回滚：helper 短期兼容 label 查找，但提交 payload 保持 canonical。
- Ops execute 风险：
  - 文案若仍写只读会误导。
  - 回滚：隐藏 execute 控件，只保留 preview。
- Worker 风险：
  - `/live` 通过不代表 worker 可用。
  - 回滚：发布门禁必须依赖 `/ready` 和 runtime evidence。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```
