# md2word 产品成熟化总计划 / 集成计划

## 业务目标

第一轮交付“发布与安全边界收敛 + 前后端契约与配置治理一致性”：

- 让 operator/admin 的文件、任务、恢复动作和配置选择边界一致、可解释、可验证。
- 让前后端围绕 Files + Document Jobs + Ops Recovery Actions 收敛，避免旧 `/api/v1/jobs`、手写类型、配置版本 key 和 mock 继续漂移。
- Word 交付质量保持为已稳定能力；除非出现明确当前回归证据，否则不作为本轮 P0。

第二轮交付“任务/QA 工作台体验成熟化 + 运营规模化与长期维护稳态”：

- 让 operator/reviewer 能更顺畅地定位失败、复制诊断、复核 QA 证据、提交术语反馈。
- 让 release、runtime readiness、worker、OpenAPI/type/mock 漂移和运维动作副作用有稳定验收口径。

## API Contract

- 用户侧主链路只使用：
  - `POST /api/v1/files/upload-url`
  - `PUT /api/v1/files/{file_id}/content`
  - `POST /api/v1/document-jobs`
  - `GET /api/v1/document-jobs`
  - `GET /api/v1/document-jobs/{job_id}`
  - `GET /api/v1/document-jobs/{job_id}/events`
  - `GET /api/v1/document-jobs/{job_id}/files`
  - `GET /api/v1/document-jobs/{job_id}/download-url`
  - `POST /api/v1/document-jobs/{job_id}/retry|clone|cancel|unarchive`
  - `DELETE /api/v1/document-jobs/{job_id}`
- `/api/v1/jobs` 只保留 legacy 历史说明，不作为公开调用入口，不保留可复制的新联调命令。
- `DocumentJobResponse.available_actions` 是前端动作展示依据；命令执行仍以后端权限和状态校验为准。
- `template_version_id`、`term_rule_set_id/version`、`translation_term_set_id/version`、`translation_profile_id/version` 必须使用稳定 canonical value；前端不得使用展示 `label` 作为业务 key。
- `/api/v1/ops/recovery-actions/preview` 是只读预检；`/api/v1/ops/recovery-actions/execute` 是受控执行，必须明确权限、reason/confirmation、audit、queue/metadata mutation、安全 flags 和禁止项。

## 数据模型 / 状态流

- `document_jobs.status`: `pending | queued | running | succeeded | failed | canceled`。
- 活跃态：`pending/queued/running`；终态：`succeeded/failed/canceled`；归档态由 `archived_at` 正交表达。
- `files` 与 `document_jobs` 权限边界一致：operator 默认只能访问自己 `created_by` 的文件和任务；admin 可按权限全局可见。
- `FileUploadUrlRequest.job_id` 不属于 P0 Files -> Document Jobs 创建主链路；如保留字段，后端必须避免它制造不可用于创建 document job 的 source file。
- legacy `jobs` 与 `document_jobs` 不隐式合并；任何统一指标、Ops 列表或迁移视图都必须声明状态映射。
- 高风险运维动作统一为 preview -> reason -> confirmation -> audit，不因前端禁用态放松后端强校验。

## 权限 / 错误模型

- operator:
  - 创建自己的 upload authorization。
  - 上传/读取自己创建的文件 metadata。
  - 创建、查看、下载、retry/cancel/archive/clone 自己有权访问的 document job。
- admin:
  - 具备配置治理、系统状态、Ops、文件保留和跨用户文件/任务访问能力。
- 错误结构优先级：
  - 前端优先读取 `error.code/error.message/error.trace_id`。
  - 兼容 legacy `detail/error_code/trace_id`。
- 前端所有用户可见错误应展示 message/code/status/trace id，并支持复制诊断信息。
- `403` 用于权限不足，`409` 用于状态冲突，`503` 用于运行时能力未就绪。

## 后端范围

- Schema:
  - 明确 config summary option 的 canonical value 语义。
  - 明确 Ops execute 的安全响应字段。
  - 保持 `DocumentJobResponse` 兼容。
- Migration:
  - 第一轮不做 DB migration。
  - 第二轮如进入查询索引化或多 worker 原子 claim，再单独设计迁移。
- Service/API:
  - Files API operator 权限与 Document Jobs 对齐。
  - document job create 保持 readiness gate。
  - Ops recovery execute 口径从“只读 Ops namespace”修正为“受控执行”。
- 异步任务:
  - 第一轮不改 Word 生成链路。
  - 明确 Celery 单 worker / 多 worker 支持约束；多 worker 原子 claim 进入第二轮或后续专项。
- 文件处理 / 存储:
  - 二进制 artifact 继续不入 metadata DB。
  - 不做 task-scoped 文件删除。
  - 真实 S3 delete、scheduler execute、provider cancellation 继续 blocked，除非另有明确批准和验收。

## 前端范围

- 页面/组件:
  - 统一创建、clone、模板验证中的配置版本值编码。
  - QA unavailable 时只读，不允许 PATCH。
  - release gate route mapping 不依赖脆弱字符串优先级。
  - 文件物理删除确认禁用态与 cleanup run 保持一致。
  - `ApiErrorAlert` 提供复制诊断。
- 状态管理:
  - 第一轮不引入大型全局 store。
  - 抽局部 helper/composable：config option key、危险确认、document job action/download、query sync。
- API client / 类型:
  - 维护 OpenAPI endpoint -> frontend wrapper/type/mock 覆盖表。
  - 暂不强制全量类型生成，但 release check 应能发现核心契约漂移。
- Loading / error / empty:
  - 任务详情页逐步拆成面板级 loading/error。
  - QA unavailable、artifact missing、debug archive disabled/expired 有明确只读/空态。

## Mock 或 Contract First

- 合同权威顺序：后端 Pydantic schema -> OpenAPI -> `docs/api/*.md` -> `frontend/src/api/types.ts` -> smoke mock。
- Mock 必须覆盖：
  - succeeded/active/failed job
  - readiness blocker
  - bulk partial failure
  - 403/409/503 structured error
  - QA unavailable / artifact missing
  - 危险确认失败和成功
  - Ops preview vs execute/fake/real safety flags

## 测试与验收

- 后端：
  - Files 跨 operator 权限。
  - upload `job_id` 行为。
  - document job readiness gate。
  - available_actions。
  - Ops execute gate/audit/safety flags。
- 前端：
  - config option payload。
  - error normalize/copy。
  - release gate routing。
  - QA unavailable guard。
  - 危险确认 disabled/enabled。
- Smoke:
  - operator 主流程。
  - admin system/ops/file-retention。
  - QA 队列与保存。
  - 403/409/503 错误展示。

## 端到端验收

- Operator core:
  - 登录。
  - 上传 PDF。
  - 创建任务。
  - 列表看到 active。
  - 详情查看 events/files。
  - 成功后生成 download-url。
- Blocker:
  - P0 required 且 worker disabled 时，创建页显示 blocker。
  - 直接调用 create 返回 `document_jobs_not_ready`，且不创建 job。
- QA:
  - 未复核队列进入证据页。
  - 可用 QA 能保存状态。
  - 不可用 QA 只读，不能提交 PATCH。
- Ops:
  - preview 不产生副作用。
  - execute/fake/real 边界、audit 和 safety flags 可核对。
- Permissions:
  - operator 不能读取/上传他人 file_id 内容。
  - admin 可按权限查看和处理。

## 风险、回滚点、验证命令

- 权限收口可能影响旧脚本；回滚点是临时提供 admin-only 兼容路径，不恢复 operator 越权。
- 配置版本格式调整可能影响旧 mock；回滚点是后端短期兼容旧格式并记录 warning。
- 自动刷新和详情拆分可能引入 UI 回归；回滚点是关闭自动刷新或保留旧 tab 入口。
- 多 worker 原子化暂不做；必须在文档和 readiness 中明确部署约束。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```
