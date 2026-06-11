# md2word 后端开发计划：产品成熟化

## 业务目标

后端第一轮目标是提供稳定、可验证、权限一致的服务端合同：

- Files API 与 Document Jobs API 的 operator/admin 权限边界一致。
- 创建任务前继续由服务端确认 P0 execution readiness，避免生成注定卡住的 job。
- 配置版本绑定使用稳定业务 key，不依赖展示 label。
- Ops recovery execute 从文档和接口上明确为“受控执行”，不是只读查询。
- 不修改 Word 渲染/导出质量链路；除非出现明确当前回归证据，否则不把 Word 交付质量列为 P0。

第二轮目标是增强可运营性：

- 明确 Celery worker 单/多实例约束。
- 为 OpenAPI/type/mock 漂移提供更强 release evidence。
- 在真实规模增长前评估查询索引化和原子 claim。

## API Contract

- Files:
  - `POST /api/v1/files/upload-url` 创建 source file upload authorization。
  - `PUT /api/v1/files/{file_id}/content` 只允许 owner 或 admin 上传内容。
  - `GET /api/v1/files/{file_id}` 只允许 owner 或 admin 读取 metadata。
  - `job_id` 不属于 P0 document job 创建主链路；若传入会导致 source file 不可创建 document job，则后端应拒绝或忽略。
- Document Jobs:
  - `POST /api/v1/document-jobs` 只接受 uploaded source PDF。
  - operator 只能创建自己上传的 source file 对应任务。
  - `available_actions` 必须完整返回。
  - `config-summary` 明确 option 的 `resource_id/version/label` 语义。
- Ops:
  - `GET /api/v1/ops/recovery-actions` registry。
  - `POST /api/v1/ops/recovery-actions/preview` 只读。
  - `POST /api/v1/ops/recovery-actions/execute` 受控执行，必须返回和记录 safety/audit 证据。

## 数据模型 / 状态流

- `DocumentJobRecord.status` 保持 `pending/queued/running/succeeded/failed/canceled`。
- `DocumentFileRecord.job_id` 为空的 uploaded source PDF 才能被 document job 创建绑定。
- `DocumentFileRecord.created_by` 是 operator 文件访问边界。
- `DocumentJobRecord.created_by` 是 operator 任务访问边界。
- `archive/unarchive` 不删除 metadata 或 artifact。
- Ops recovery execute 可能产生 audit、document job event、queue mutation；这些副作用必须在响应 safety 和 audit details 中可见。

## 权限 / 错误模型

- Files:
  - owner 或 admin 可读取文件 metadata。
  - owner 或 admin 可上传 pending upload 内容。
  - 非 owner operator 返回 `403 forbidden`，不泄露文件是否属于他人以外的敏感细节。
- Document Jobs:
  - 现有 `created_by` 约束保持。
  - 操作冲突返回 `409 conflict`。
- Ops:
  - Admin only。
  - 缺 reason/confirmation 返回 `400 invalid_request`。
  - 未通过 gate 返回 `409 conflict` 或已定义业务错误码。
- 错误体统一使用 `ApiError` / registered handler，保留 `detail` 兼容。

## Schema / Migration

- 第一轮不做 DB migration。
- 如果修改 `FileUploadUrlRequest.job_id` 语义：
  - 优先保持字段兼容但拒绝 P0 source PDF 非空 `job_id`。
  - 或文档标记 deprecated，不从前端传入。
- 如果补 Ops execute response 字段，更新：
  - Pydantic schema。
  - OpenAPI。
  - `docs/api/ops.md`。
  - 前端 type/wrapper/mock。

## Service / API

- `FileUploadService` 增加统一 owner/admin guard。
- `files/router.py` 的 GET/PUT content 路径复用该 guard。
- `DocumentJobService._validate_source_file_for_create` 继续拒绝已绑定 `job_id` 的 source file。
- `DocumentJobService` 的 config option projection 输出稳定字段，不要求前端解析 label。
- Ops recovery execute 文档与实现对齐：
  - preview only 不变。
  - execute 的 queue/audit/event side effects 明确。

## 异步任务

- 第一轮不改 `DocumentJobExecutionService` 的 MinerU/DocumentIR/renderer 主流程。
- `document_jobs_worker_backend=celery` 的 worker 能力证明进入验收：
  - readiness blocker 无异常。
  - 至少一次 eager/mock 或受控真实任务执行证据。
- 多 worker 原子 claim 不在第一轮实现；如果生产只支持单 worker，在 runbook 和 deploy docs 中明确。

## 文件处理 / 存储

- 继续使用 Files API 登记和上传 source PDF。
- 继续通过 document job download-url 下载结果。
- 不新增 task-scoped 删除。
- 文件物理删除继续只走 retention/cleanup preview -> reason -> confirmation -> audit。
- S3 真实删除保持 blocked，除非另有明确批准。

## 单元测试 / 集成测试

- 增加或更新后端测试：
  - operator A 不能 `GET /api/v1/files/{file_id}` 读取 operator B 文件。
  - operator A 不能 `PUT /api/v1/files/{file_id}/content` 上传 operator B pending upload。
  - admin 可以读取必要 metadata。
  - `upload-url` 带 `job_id` 的 P0 source PDF 行为明确。
  - document job create 继续拒绝已绑定 `job_id` 的 source file。
  - Ops execute 的权限、reason/confirmation、audit、safety flags。
- 保留 OpenAPI 移除 legacy jobs 的断言。

## 后端接口完成标准

- 所有新/变更接口都有 schema、OpenAPI、API docs、测试。
- Files/Document Jobs 权限边界一致。
- `POST /api/v1/document-jobs` readiness gate 行为不回退。
- Ops preview 与 execute 的 side effects 可从响应和 audit 核对。
- 不新增 silent fallback，不吞 trace id，不修改 Word 交付链路。

## 风险、回滚点、验证命令

- 权限收口可能暴露旧脚本依赖跨用户 file_id；回滚点是通过 admin token 执行运维脚本，不恢复 operator 跨用户访问。
- `job_id` 字段收口可能影响非 P0 历史链路；回滚点是仅对 `file_type=source_pdf` 的 document job 创建链路拒绝。
- Ops execute 口径收口可能要求前端文案同步；后端保持兼容响应字段。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```
