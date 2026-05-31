---
doc_type: implementation-checklist
slug: pdf-to-word-implementation-checklist
component: pdf-to-word-backend
status: draft
summary: 电子元器件 PDF 到模板化 Word 后端 MVP 的可执行开发任务清单，按 P0 开发依赖顺序排列。
tags: [implementation, checklist, backend, mvp, pdf, mineru, word, celery, oss]
last_reviewed: 2026-05-30
---

# PDF 到模板化 Word 后端实施计划清单

> 本文用于把 PRD 和技术实施计划拆成后续可转 Trellis task 或开发 issue 的任务清单。排序优先按 P0 可开发依赖顺序，不按静态模块分类。

## 1. 使用规则

- 每个任务应能独立验收，避免把多个不可分割的大模块塞进一个开发项。
- P0 任务优先打通中文 PDF 到模板化 Word 的可运行闭环。
- P1 任务只在 P0 主链路可稳定回归后进入正式开发。
- 遇到实现与本文冲突时，以最新 PRD、技术计划和实际代码约束为准，并回写本文。

## 2. 状态标记

| 状态 | 含义 |
|---|---|
| todo | 尚未开始 |
| doing | 正在开发 |
| blocked | 被依赖或外部条件阻塞 |
| done | 已完成并通过验收 |
| deferred | 明确后置 |

## 3. P0 开发任务清单

| ID | 状态 | 任务名称 | 依赖 | 涉及模块 | 交付物 | 验收标准 | 风险 |
|---|---|---|---|---|---|---|---|
| P0-001 | done | 确认当前代码基线与目标架构差距 | 无 | docs, app, tests | 现状差距记录或 issue 列表 | 明确哪些现有能力可复用，哪些需要新增或改造 | 仓库已有较多改动，需避免重复建设 |
| P0-002 | done | 确认公司开发环境连接参数清单 | 无 | config, deploy | `.env.example` 更新建议或配置清单 | MySQL、Redis、OSS、JWT 密钥、MinerU 配置项列清楚 | 缺少真实环境会阻塞联调 |
| P0-003 | done | 定义 MySQL 核心表结构草案 | P0-001 | models, repositories | users、document_files、document_jobs、job_events、templates 相关表设计 | 覆盖 P0 必需字段，并保留 tenant_id、company_id、created_by | 字段过多会拖慢实现，过少会影响追溯 |
| P0-004 | done | 建立最小内部账号与 JWT 鉴权 | P0-003 | auth, api, schemas | 登录接口、JWT 校验依赖、admin/operator 角色 | admin/operator 可登录；无 token、过期 token、错误角色被拒绝 | 后续接 SSO 时需兼容迁移 |
| P0-005 | done | 建立统一错误响应和错误码约定 | P0-004 | api, core | 错误模型、常见错误码、异常处理 | API 返回结构稳定，能表达无权限、文件超限、任务不存在等错误 | 错误码后补会影响前端联调 |
| P0-006 | done | 实现 OSS 文件元数据模型 | P0-003 | files, repositories, oss | `document_files` 读写、文件类型、过期时间、checksum 字段 | 可登记原始 PDF、中间结果、图片、Word 的 OSS 引用 | 只存 URL 会影响安全和后续迁移 |
| P0-007 | done | 实现 OSS 上传授权或后端代理上传入口 | P0-006 | api, files, oss | `/api/files/upload-url` 或等价接口 | operator/admin 可获得上传授权；非法类型和超大小被拒绝 | OSS 厂商 SDK 和签名规则待确认 |
| P0-008 | done | 实现 PDF 基础校验 | P0-007 | files, jobs | PDF 类型、50MB 限制、页数 200 限制 | 超限文档不创建任务并返回明确错误 | 页数读取失败需要明确错误 |
| P0-009 | done | 定义 document_jobs 状态机和阶段枚举 | P0-003 | jobs, models | 状态、阶段、错误字段、超时字段 | 支持 pending、queued、running、succeeded、failed、canceled 和 P0 阶段 | 状态机不清会导致重试和查询混乱 |
| P0-010 | done | 实现创建文档任务 API | P0-004, P0-008, P0-009 | api, jobs, repositories | `POST /api/v1/document-jobs` | 创建任务后写 MySQL，返回 job_id，初始状态可查询 | 不应在 API 内执行耗时处理 |
| P0-011 | done | 实现任务查询 API | P0-010 | api, jobs | 任务详情、任务列表 | operator 可查自己的任务，admin 可查更广范围 | 单租户简化但不能完全裸奔 |
| P0-012 | done | 实现 job_events 事件记录能力 | P0-009 | jobs, observability | 事件写入函数、事件查询接口 | 每个阶段可记录开始、完成、失败和耗时 | payload 不能默认写敏感全文 |
| P0-013 | done | 接入 Celery + Redis 基础 Worker | P0-010 | workers, jobs, config | Celery app、Worker 启动入口、测试任务 | API 创建任务后能投递 Worker，MySQL 状态随任务更新 | Redis 连接和部署配置可能不一致 |
| P0-014 | done | 实现任务幂等执行骨架 | P0-013 | workers, jobs | 按 job_id 执行的 orchestration skeleton | 重复投递不会生成不可追踪的重复结果 | 幂等设计缺失会放大重试风险 |
| P0-015 | done | 接入 MinerU 调用适配层 | P0-014 | integrations/mineru, parser | MinerU client 或命令封装 | Worker 可对 1 份样本 PDF 触发 MinerU 并保存原始结果 | MinerU 调用方式尚需最终确认 |
| P0-016 | done | 保存 MinerU 原始结果到 OSS | P0-015, P0-006 | parser, files, oss | raw result 文件登记和上传 | 原始解析结果可追溯到 job 和 source_file | 中间资产过大可能影响成本 |
| P0-017 | done | 设计 DocumentIR v1 schema | P0-015 | document_ir, schemas | IR schema 文档和数据结构 | 覆盖 heading、paragraph、table、image、list、formula、metadata、quality_flags | schema 过复杂会拖慢 P0 |
| P0-018 | done | 实现 MinerU 到 DocumentIR 转换 | P0-017 | document_ir, parser | 转换服务和单元测试 | 3-5 份样本能生成稳定 IR，并保留块顺序和资源引用 | 双栏顺序和表格结构可能不稳 |
| P0-019 | done | 保存 DocumentIR 和图片资产到 OSS | P0-018, P0-006 | document_ir, files, oss | IR 文件、图片文件、文件元数据 | IR 和图片可从 job 追溯和下载排查 | 图片路径和 OSS key 需稳定 |
| P0-020 | done | 定义模板配置包 v1 格式 | P0-017 | templates, renderer | 模板配置格式、1 套初始模板样例 | 能描述页眉、Logo、字体、标题样式、页边距、表格样式 | 不应试图支持任意 docx 自动适配 |
| P0-021 | done | 实现模板与模板版本只读注册能力 | P0-020 | templates, repositories, api | word_templates、template_versions 读写或种子数据 | API 可查询可用模板和版本，任务可绑定 template_version_id | admin 管理入口可先简化 |
| P0-022 | done | 实现 DocumentIR 到 Word 的最小渲染 | P0-020, P0-021 | renderer | heading、paragraph、basic table、image 的 docx 输出 | 1 份中文样本可生成可打开、可编辑 Word | 表格和图片排版是主要风险 |
| P0-023 | done | 实现模板样式应用 | P0-022 | renderer, templates | 页眉、Logo、字体、标题样式、页边距、表格样式 | 输出 Word 符合 1 套模板的核心规则 | python-docx/docxtpl 能力边界需验证 |
| P0-024 | done | 保存生成 Word 到 OSS 并登记结果 | P0-023, P0-006 | renderer, files, jobs | generated_files 或等价结果记录 | 任务成功后能定位生成 Word 文件 | OSS 上传失败需可重试 |
| P0-025 | done | 实现结果下载临时授权接口 | P0-024 | api, files, oss | `/api/v1/document-jobs/{job_id}/download-url` | 成功任务返回 10 分钟有效下载链接，失败/未完成返回明确错误 | 长期 URL 暴露风险 |
| P0-026 | done | 打通 P0 中文主链路端到端 | P0-010 至 P0-025 | api, workers, parser, renderer, oss | 上传、建任务、Worker 处理、下载 Word 的完整流程 | 1-3 份中文样本端到端跑通 | 任一阶段失败都可能阻断闭环 |
| P0-027 | done | 增加任务超时和失败分类 | P0-026 | workers, jobs | P0 20 分钟超时、failed_stage、error_code | 超时、MinerU 失败、渲染失败、OSS 失败都有可读原因 | Celery 超时与 MySQL 状态需一致 |
| P0-028 | done | 实现有限重试入口 | P0-027 | api, workers, jobs | `/api/document-jobs/{job_id}/retry` 或等价能力 | 可重试失败能按 job_id 幂等重跑，不可重试失败返回明确原因 | 重试可能覆盖或污染旧结果 |
| P0-029 | done | 增加请求日志、任务日志和审计日志 | P0-026 | observability, audit | request_id、job_id、actor、动作、耗时日志 | 登录、上传、建任务、下载授权、模板变更有审计记录 | 日志不能泄露敏感全文 |
| P0-030 | done | 实现文件保留期字段和清理策略雏形 | P0-006, P0-024 | files, jobs | expires_at、90 天保留策略、清理任务设计或实现 | 文件元数据有过期时间，后续可自动清理 | 是否使用 OSS 生命周期规则待确认 |
| P0-031 | done | 建立 Golden Sample 样本目录和清单 | P0-026 | tests, docs | 10-20 份样本清单、分类标签、验收记录模板 | 覆盖单栏、双栏、标题、参数表、关键图片 | 样本选择不代表真实输入会影响验收 |
| P0-032 | done | 实现 Golden Sample 回归脚本或测试入口 | P0-031 | tests, scripts | 批量提交任务、收集结果、输出通过率 | 能统计核心链路成功率和失败阶段 | 长任务测试环境成本较高 |
| P0-033 | blocked | 完成 P0 验收回归 | P0-032 | tests, docs | Golden Sample 验收报告 | 10-20 份样本核心链路成功率 >= 90%，成功样本 Word 可打开可编辑 | 轻量校对标准需人工统一 |
| P0-034 | done | 准备 Docker 部署配置 | P0-026 | deploy, config | API 和 Worker 使用同一镜像的 Docker 配置 | 云服务器可分别启动 API 服务和 Worker 服务 | 公司环境变量和网络策略需确认 |
| P0-035 | done | 编写内部联调说明 | P0-033, P0-034 | docs | 启动、配置、上传、建任务、查状态、下载、排错说明 | 内部人员按文档能完成一次 P0 流程 | 文档与实际 API 容易漂移 |

P0-001 至 P0-003 完成记录见 [pdf-to-word-p0-foundation-execution.md](./pdf-to-word-p0-foundation-execution.md)。

P0-004 至 P0-005 完成备注（2026-05-29）：已新增 `/api/v1/auth/login` 和 `/api/v1/auth/me`，支持配置化内部账号、PBKDF2 密码哈希、HS256 JWT、`admin` / `operator` 角色；现有 admin-only 依赖已可接受 admin JWT，operator JWT 会被拒绝。API 错误响应保留 `detail` 兼容字段，并统一增加 `error_code` 与 `error` 对象，覆盖未认证、凭证错误、角色不足、文件超限、资源缺失、冲突和服务未配置等基础错误码。

P0-006 至 P0-008 完成备注（2026-05-29）：已新增 `document_files` 元数据模型和 file/sqlite/MySQL repository 读写协议，字段覆盖 tenant/company、job_id、文件类型、storage_provider、bucket、object_key、checksum、etag、expires_at、created_by 和 metadata。新增 `/api/v1/files/upload-url`、`PUT /api/v1/files/{file_id}/content`、`GET /api/v1/files/{file_id}`，operator/admin 需携带 JWT 才能登记并通过本地代理上传 source PDF；本地 object store 使用稳定 `document-files/{tenant_id}/{file_id}/{filename}` key，S3 配置下可生成 put_object presigned URL。PDF 校验复用到 files 上传和既有 `/api/v1/jobs/pdf`，覆盖扩展名、content-type、大小上限和 200 页基础页数上限；非法类型、超大小、页数超限会返回统一错误结构。

P0-009 至 P0-012 完成备注（2026-05-29）：已新增 `document_jobs` 状态机模型，覆盖 `pending`、`queued`、`running`、`succeeded`、`failed`、`canceled` 及 P0 阶段 `uploaded`、`parsing`、`parsed`、`ir_converting`、`rendering`、`uploading`、`completed`、`failed`、`canceled`，并保留 template、term、result、mineru、error、retry、timeout、request_snapshot 等追溯字段。file/sqlite/MySQL metadata repository 已支持 `document_jobs` 和 `document_job_events` 读写；新增版本化接口 `/api/v1/document-jobs`、`/api/v1/document-jobs/{job_id}`、`/api/v1/document-jobs/{job_id}/events`，创建任务只绑定已上传 source PDF、写入初始 `pending/uploaded` 记录和 `job_created` 事件，不投递 Worker。查询按 JWT 用户做最小权限隔离：operator 只能看自己的任务，admin 可看同 tenant/company 任务；事件 payload 只写 source_file_id、mode、template_version_id 等非全文摘要。

P0-013 至 P0-014 完成备注（2026-05-29）：已新增 `app/workers/celery_app.py`、`app/workers/document_tasks.py` 和 `scripts/dev/run_document_worker.py`，配置项覆盖 `DOCUMENT_JOBS_WORKER_BACKEND`、Redis broker URL、result backend 和队列名，`requirements.txt` 已加入 `celery[redis]`。`DocumentJobService` 在启用 Worker backend 时会把新任务从 `pending/uploaded` 推进到 `queued/uploaded` 并按 `job_id` 投递；`DocumentJobExecutionService` 提供 P0 幂等骨架，Worker 可从 `pending` 或 `queued` 恢复执行，推进到 `running/parsing` 后标记解析骨架完成为 `running/parsed`，重复投递不会追加重复阶段事件或生成不可追踪结果。真实 MinerU 调用、原始结果保存和后续阶段仍留给 P0-015 起接入。

P0-015 至 P0-019 完成备注（2026-05-29）：`DocumentJobExecutionService` 已从幂等骨架升级为 MinerU raw -> DocumentIR -> image/IR 保存链路：Worker 读取已上传 source PDF，调用 MinerU batch 提交和查询接口，结果就绪后下载 raw zip 并登记为 `mineru_raw_result` 文件；结果未就绪时保持 `running/parsing`，等待后续重投递或重试。新增 `DocumentIR v1` Pydantic 数据结构和 `docs/dev/document-ir-v1.md`，覆盖 heading、paragraph、table、image、list、formula、metadata、assets、quality_flags；新增 `MinerUToDocumentIRService` 从 MinerU `content_list_v2.json` / `content_list.json` 生成稳定块序和图片资产引用。`FileUploadService` 新增 Worker 生成内容登记和二进制读取能力，IR JSON 登记为 `document_ir`，图片登记为 `image_asset`，并回填 `document_jobs` 的 `mineru_raw_result_file_id`、`document_ir_file_id` 和 `image_asset_file_ids`，后续 Word 渲染从 `running/rendering` 继续。

P0-020 至 P0-025 完成备注（2026-05-29）：已新增 `template-config/v1` 模板配置包模型和 `docs/dev/template-config-package-v1.md`，默认 `datasheet_template.yaml` 标注 schema 并补充 `table_style`；模板版本查询响应会返回 `template_version_id`，document_jobs 创建时会把模板绑定解析为 `template_id@version`。新增 `DocumentIRWordRenderer`，可按模板 DOCX 和配置包渲染 heading、paragraph、list、formula、基础 HTML table、image，并应用页边距、页眉/页脚、字体、标题、正文、表格和图注样式。`DocumentJobExecutionService` 已从 `running/rendering` 继续执行到 Word 渲染、`generated_word` 文件登记、`succeeded/completed` 状态回填，并保持重复投递不重复生成已登记结果。新增 `/api/v1/document-jobs/{job_id}/download-url` 和本地签名下载入口，成功任务返回 10 分钟有效 GET 链接，未完成任务返回统一 `conflict` 错误；OpenAPI 快照已同步。

P0-026 至 P0-030 完成备注（2026-05-29）：P0 中文主链路已通过 API 上传授权、后端代理上传、`POST /api/v1/document-jobs`、Worker 解析/IR/Word 渲染、`GET /api/v1/document-jobs/{job_id}/download-url` 和临时下载完成端到端回归。`DocumentJobExecutionService` 增加 P0 20 分钟超时检查、Celery soft/hard time limit 配置和可落库的超时失败状态，失败分类覆盖 `document_job_timeout`、`mineru_failed`、`document_ir_failed`、`render_failed`、`oss_failed`，并写入 `failed_stage`、`error_code`、`error_message` 和 error 级任务事件。新增 `POST /api/v1/document-jobs/{job_id}/retry`，按 `P0_DOCUMENT_JOB_MAX_RETRIES` 有限重试，保持原 `job_id` 幂等恢复，重试时保留可复用中间产物并在解析失败且无 raw result 时清理旧 MinerU batch 绑定。请求 access log 已保留 `trace_id`、方法、路径、状态和耗时，任务日志保留 `trace_id/job_id/stage/status`；登录、上传授权、上传内容、建任务、下载授权、document_job retry 和模板变更会写 `audit_events`，不记录 token、文件正文或解析全文。`document_files.expires_at` 继续按 `OSS_FILE_RETENTION_DAYS=90` 写入，新增 `DocumentFileRetentionPlanner` 可生成过期文件 dry-run 并把候选标记为 `expired`，物理删除仍留给后续 OSS 生命周期或人工任务；OpenAPI 快照已同步。

P0-031 至 P0-035 完成/阻塞备注（2026-05-29）：已新增 Golden Sample 目录 `tests/fixtures/golden_samples/`，包含 12 份样本槽位清单、分类标签、人工验收记录模板和 `pdfs/` 目录；当前仓库未包含真实 PDF，样本项均标记 `source_status=pending_pdf`。新增 `scripts/ops/run_golden_sample_regression.py`，可按现有 `/api/v1/auth/login`、`/api/v1/files/upload-url`、`PUT /api/v1/files/{file_id}/content`、`POST /api/v1/document-jobs`、任务查询和下载授权接口批量提交样本、轮询结果、下载 Word、检查 docx 包可打开性，并输出 `report.json` / `report.md` 到 `tests/tmp/golden_sample_runs/`；新增 `tests/test_golden_sample_manifest.py` 覆盖清单结构和标签覆盖。P0 验收回归报告已建在 `docs/testing/pdf-to-word-golden-sample-acceptance-report.md`，但因没有 10-20 份真实 PDF 样本，不能执行成功率 >= 90% 的正式验收，P0-033 据实标记为 blocked。Docker 部署已收敛到 `docker/prod/Dockerfile`、`docker/prod/docker-compose.yml`、`docker/dev/Dockerfile`、`docker/dev/docker-compose.yml`、`.dockerignore`、`.env.example` 和 `docs/deploy/p0-docker-deployment.md`，API 与 document_jobs Worker 使用同一镜像，Compose 提供 MySQL、Redis 和共享 `/app/var` volume。内部联调说明已新增 `docs/testing/pdf-to-word-p0-integration-guide.md`，覆盖启动/配置、登录、上传授权、上传 PDF、建任务、查状态、查事件、下载 Word、Golden Sample 批量回归和常见排错。

## 4. P1 实验任务清单

| ID | 状态 | 任务名称 | 依赖 | 涉及模块 | 交付物 | 验收标准 | 风险 |
|---|---|---|---|---|---|---|---|
| P1-001 | done | 定义 translation provider 接口 | P0-017, P0-026 | translation, integrations/ai | provider 抽象、配置开关 | 可切换外部模型开关，并预留私有化适配 | 写死 provider 会影响后续替换 |
| P1-002 | done | 定义最小术语表版本格式 | P1-001 | terms, translation | CSV/JSON/XLSX 之一的术语格式 | 支持 language_pair、source_term、target_term、version | 术语冲突暂不处理 |
| P1-003 | done | 实现术语版本只读加载和任务绑定 | P1-002 | terms, jobs | term_versions 记录和加载服务 | 翻译任务记录 term_version_id | 没有版本追溯会影响质量排查 |
| P1-004 | done | 实现 DocumentIR 文本节点翻译 | P1-001, P1-003 | translation, document_ir | 只翻译文本节点的服务 | 翻译后 IR 结构不变，非文本资产不被 AI 改写 | AI 可能返回不可控格式 |
| P1-005 | done | 实现 AI 调用审计记录 | P1-004 | translation, observability | ai_call_logs 或等价记录 | 默认保存元数据、哈希、脱敏摘要、错误信息，不保存完整文本 | 摘要脱敏策略需明确 |
| P1-006 | done | 实现任务级调试全文留存开关 | P1-005 | translation, files, config | prompt and response 调试归档，1 天过期 | 仅开关开启时保存完整 prompt and response | 敏感信息存储风险 |
| P1-007 | done | 打通英文 PDF 英译中实验链路 | P1-004 至 P1-006 | workers, translation, renderer | 英文 PDF -> 中文 DocumentIR -> Word | 1-3 份英文样本可完成实验流程 | 翻译质量和术语一致性不稳定 |
| P1-008 | done | 建立 P1 翻译质量验收样本 | P1-007 | tests, docs | 英文样本、术语表、人工验收记录 | 记录术语命中、结构不变性和人工质量反馈 | 质量标准主观性强 |

P1-001 至 P1-004 完成备注（2026-05-30）：已新增 `app/services/translation/` provider 边界，默认 `TRANSLATION_PROVIDER_BACKEND=disabled`，可切到 `openai_compatible` 并复用 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`，私有化模型可实现同一 `TranslationProvider` 端口。最小术语表选择 CSV 格式，样例为 `resources/term_rules/translation_terms.csv`，文档见 `docs/dev/translation-terms-v1.md`，必填 `language_pair`、`source_term`、`target_term`、`version`，运行时 canonical 绑定为 `language_pair@version`。新增只读 `TermVersionService`，`en2zh_pdf_to_word` 创建任务未显式传术语版本时会绑定默认 `DEFAULT_TRANSLATION_TERM_VERSION_ID=en2zh@v1`，并写入 `document_jobs.term_version_id`、`request_snapshot` 和创建事件 payload。新增 `DocumentIRTranslationService`，仅抽取 heading/paragraph/image caption 的 `text`、list 的 `list_items`、table HTML 文本节点交给 provider，返回后写回 DocumentIR 副本；公式、资产、块顺序、块类型和资产引用不交给 AI。

P1-005 至 P1-008 完成备注（2026-05-30）：`DocumentJobExecutionService` 已在 `en2zh_pdf_to_word` 的 `ir_converting` 阶段接入 DocumentIR 文本翻译，生成的 `document_ir` 为中文 IR，随后复用现有 Word renderer 输出中文 Word；重复投递仍以 `document_ir_file_id` 幂等跳过。新增 `TranslationAuditService`，每次 provider 调用都会登记 `ai_call_log` 文件，默认只保存 provider 元数据、语言方向、术语版本、item/字符计数、sha256 哈希、脱敏 item 摘要和失败错误信息，不保存完整 prompt、response、术语文本或密钥。新增任务级 `debug_full_text` 请求开关，并受 `TRANSLATION_DEBUG_ARCHIVE_ENABLED` 配置保护；仅二者同时开启且任务为 `en2zh_pdf_to_word` 时登记 `ai_debug_archive` 全文调试文件，过期时间按 `TRANSLATION_DEBUG_ARCHIVE_RETENTION_DAYS=1` 写入。翻译失败会保留 `ai_call_log` 并把任务落为 `failed/translation_failed`。P1 翻译验收样本已建立在 `tests/fixtures/p1_translation_samples/`，包含 1 份合成英文 smoke PDF、3 个样本槽位清单、术语文件引用和人工验收记录模板；真实业务英文 PDF 仍需后续替换/补齐后做人工质量评估。

## 5. P2 后置任务池

| ID | 状态 | 任务名称 | 前置条件 | 说明 |
|---|---|---|---|---|
| P2-001 | deferred | 在线人工审核 / 校对工作台 | P0/P1 链路稳定，前端启动 | 段落级编辑、差异对比、保存草稿、版本管理后置 |
| P2-002 | deferred | 在线模板编辑器 | 模板配置包 v1 稳定 | 需要权限、版本、发布、回滚和兼容性检查 |
| P2-003 | deferred | 在线术语库管理 | P1 术语版本验证有效 | 需要导入、编辑、冲突合并、优先级、发布回滚 |
| P2-004 | deferred | 外部客户自助门户 | 内部流程验证可交付 | 需要完整多租户、客户权限、配额和审计 |
| P2-005 | deferred | 扫描件 OCR 支持 | 文本型 PDF 链路稳定 | OCR 会显著增加解析和质量风险 |
| P2-006 | deferred | BOM / 检测报告支持 | 数据手册样本稳定 | 文档类型不同，需要单独 IR 和验收样本 |

## 6. 第一批建议拆分为开发 issue

如果后续要把本文转成 Trellis task 或开发 issue，建议第一批只拆 P0-001 到 P0-014：

| 建议 issue | 覆盖任务 | 目标 |
|---|---|---|
| Issue 1 | P0-001 至 P0-003 | 明确现状差距、环境配置和 MySQL 核心模型 |
| Issue 2 | P0-004 至 P0-005 | 建立内部账号、JWT 和统一错误响应 |
| Issue 3 | P0-006 至 P0-008 | 打通 OSS 文件登记、上传授权和 PDF 校验 |
| Issue 4 | P0-009 至 P0-012 | 建立 document_jobs、状态机、查询和事件 |
| Issue 5 | P0-013 至 P0-014 | 接入 Celery Worker 和幂等任务骨架 |

完成这 5 个 issue 后，再进入 MinerU、DocumentIR 和 Word 渲染主链路，风险会更可控。

## 7. 当前待确认事项

| 问题 | 阻塞任务 | 建议处理 |
|---|---|---|
| MinerU 的实际调用方式 | P0-015 | 先做 3-5 份样本 PoC，确认本地命令、容器或远程服务 |
| OSS 厂商 SDK 和签名规范 | P0-007, P0-025 | 与公司云资源负责人确认 bucket、object_key、签名 URL 规则 |
| MySQL 版本和迁移工具 | P0-003 | 确认是否已有 Alembic 或其他迁移流程 |
| 初始公司模板样例 | P0-020 | 收集 1 套 docx 样例和目标输出样例 |
| Golden Sample 具体 PDF | P0-033 | 业务和技术共同选 10-20 份样本，并按 `tests/fixtures/golden_samples/manifest.yaml` 放入 `tests/fixtures/golden_samples/pdfs/` |
| 外部 AI provider | P1-001 | P0 之后再选型和验证 |
