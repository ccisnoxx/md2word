---
doc_type: technical-plan
slug: pdf-to-word-technical-plan-draft
component: pdf-to-word-backend
status: draft
summary: 电子元器件 PDF 解析、AI 翻译、模板化排版并生成 Word 的后端技术实施计划草案。
tags: [technical-plan, backend, fastapi, celery, mysql, redis, oss, mineru]
last_reviewed: 2026-05-29
---

# 电子元器件 PDF 到模板化 Word 后端技术实施计划草案

> 本文为技术实施草案。它描述目标架构和实施计划，不代表当前代码已经全部实现。

## 1. 推荐技术栈

| 层级 | 推荐方案 | 替代方案 | 选择理由 | 风险 |
|---|---|---|---|---|
| API 框架 | Python + FastAPI | Flask / Django | 项目默认技术栈，适合前后端分离 API | 长任务不能在 API 进程内同步执行 |
| 异步任务 | Celery | RQ / Dramatiq / Arq | 成熟，支持队列、重试、超时和 Worker 扩展 | 配置复杂度高于轻量队列 |
| Broker | 公司已有 Redis | RabbitMQ | 已有 Redis，部署成本低 | Redis 可用性影响任务投递 |
| 数据库 | 公司已有 MySQL | PostgreSQL | 公司环境已具备，适合业务状态和元数据 | JSON 查询能力不如 PostgreSQL |
| 文件存储 | 公司 OSS | MinIO / 本地文件 | 存储 PDF、中间结果、图片、Word 等文件资产 | 需确认签名 URL 和生命周期策略 |
| PDF 解析 | MinerU | 其他 PDF parser / OCR | 项目已明确依赖 MinerU | 表格、双栏、图片解析质量需验证 |
| 中间结构 | DocumentIR | 直接使用 MinerU 原始结果 | 隔离解析、翻译和 Word 生成 | 需要设计和维护转换规则 |
| Word 生成 | python-docx / docxtpl + 自定义渲染规则 | LibreOffice 转换 / AI 生成 Word | 可控、可测试、可模板化 | 复杂表格和图片锚点需要调试 |
| AI 翻译 | 可替换 translation provider 接口 | 写死单一外部模型 | 支持外部模型开关和私有化适配 | 模型质量、成本、安全边界需确认 |
| 鉴权 | 内部账号 + JWT | 公司 SSO / 网关鉴权 | MVP 暂无统一鉴权，JWT 足够内部使用 | 后续接入 SSO 时需迁移 |

## 2. 后端架构说明

### 2.1 总体架构

```text
Client / Frontend / Script
  -> FastAPI API Service
    -> MySQL: users, files, document_jobs, job_events, templates, terms
    -> Redis: Celery broker
    -> OSS: upload/download authorization
  -> Celery Worker
    -> MinerU integration
    -> DocumentIR converter
    -> Translation provider
    -> Word renderer
    -> OSS uploader
```

### 2.2 API 层

- 负责登录、JWT 校验、角色校验、文件上传授权、任务创建、任务查询、事件查询、下载授权。
- 不执行 MinerU、AI 翻译、Word 生成等耗时任务。
- 创建任务时写入 MySQL，并投递 Celery。

### 2.3 任务编排层

- 统一使用 document_jobs 表表示一次 PDF 到 Word 的处理任务。
- 使用 job_events 记录阶段事件、错误、耗时和调试信息。
- Celery Worker 按 job_id 幂等执行。

### 2.4 MinerU 解析层

- 调用 MinerU 处理 PDF。
- 保存 MinerU 原始结果到 OSS。
- 将原始结果转换为内部 DocumentIR。
- 对表格、图片、双栏顺序等问题打 quality_flags。

### 2.5 翻译服务层

- P1 使用。
- 只翻译 DocumentIR 文本节点。
- 翻译任务绑定语言方向、模型配置和术语版本。
- 默认不保存完整发送文本，仅记录元数据、哈希、脱敏摘要和错误信息。

### 2.6 Word 生成层

- 根据模板版本和 DocumentIR 生成可编辑 docx。
- 模板规则控制页眉、Logo、字体、标题样式、页边距、目录、表格样式。
- AI 不直接生成最终 Word。

### 2.7 配置资产管理层

- 管理模板、模板版本、术语库、术语版本。
- MVP 先做后端最小能力，不做在线编辑器。
- 任务必须记录使用的模板版本和术语版本。

### 2.8 文件存储层

- 原始 PDF、MinerU 原始结果、DocumentIR、图片、生成 Word 均上传 OSS。
- MySQL 存 bucket、object_key、mime_type、size、checksum、etag、expires_at 等元数据。
- 下载时由 FastAPI 生成 10 分钟有效临时签名 URL。

### 2.9 日志与审计层

- 请求日志记录 API 请求、用户、耗时、状态码。
- 任务日志记录阶段、耗时、失败原因。
- 审计日志记录登录、上传、任务创建、模板变更、术语变更、下载授权等动作。

## 3. 目录 / 模块划分

```text
app/
  api/
    routes/
    deps.py
  core/
    config.py
    security.py
    errors.py
  models/
  schemas/
  repositories/
  services/
    auth/
    files/
    jobs/
    parser/
    document_ir/
    translation/
    renderer/
    templates/
    terms/
  workers/
    celery_app.py
    document_tasks.py
  integrations/
    mineru/
    ai/
    oss/
  observability/
    logging.py
    audit.py
    metrics.py
  tests/
```

【建议】如果当前仓库已有既定目录结构，应优先沿用现有结构，只把上述模块作为职责边界参考。

## 4. 数据模型建议

| 实体 | 关键字段 | 关系 | 说明 | 风险 |
|---|---|---|---|---|
| users | id, tenant_id, company_id, username, password_hash, role, status | belongs to tenant/company | MVP 内部账号 | 后续接 SSO 需迁移 |
| tenants | id, name, status | has many users/jobs | MVP 默认单租户 | 不要过早做复杂租户能力 |
| companies | id, tenant_id, name, status | has templates/jobs | 表示模板适用公司或内部归属 | 公司维度需与业务口径确认 |
| document_files | id, bucket, object_key, mime_type, size, checksum, etag, file_type, expires_at, created_by | linked by jobs/results | 文件元数据，OSS 存内容 | 只存 URL 会影响安全和迁移 |
| document_jobs | id, tenant_id, company_id, created_by, source_file_id, mode, status, stage, progress, template_version_id, term_version_id, error_code, error_message, failed_stage, timeout_at | central entity | 一次文档处理任务 | 字段过多时后续可拆子任务 |
| job_events | id, job_id, stage, level, message, payload, duration_ms, created_at | belongs to job | 阶段事件、错误、耗时 | payload 不应默认写敏感全文 |
| parse_results | id, job_id, raw_result_file_id, ir_file_id, quality_flags, created_at | belongs to job | MinerU 原始结果和 DocumentIR | IR schema 需要版本号 |
| translation_results | id, job_id, language_pair, model_provider, model_name, term_version_id, result_file_id, audit_summary, created_at | belongs to job | P1 翻译结果 | 敏感文本留存需控制 |
| generated_files | id, job_id, file_id, template_version_id, created_at | belongs to job/file | 最终 Word 输出 | 模板版本必须可追溯 |
| word_templates | id, tenant_id, company_id, name, status | has versions | 模板资产主表 | 不能承诺任意 docx 自适配 |
| template_versions | id, template_id, version, docx_sample_file_id, config_file_id, rule_version, status, published_at | belongs to template | 模板版本 | 配置兼容性需回归 |
| term_bases | id, tenant_id, company_id, name, language_pair, status | has versions | 术语库 | P1 最小能力即可 |
| term_versions | id, term_base_id, version, file_id, status, published_at | belongs to term_base | 术语版本 | 冲突和优先级后置 |
| ai_call_logs | id, job_id, segment_id, provider, model, language_pair, term_version_id, request_hash, redacted_summary, token_count, status, error_message, created_at | belongs to job | AI 调用审计 | 默认不存完整文本 |
| audit_logs | id, actor_id, action, object_type, object_id, metadata, created_at | references actor/object | 操作审计 | metadata 需脱敏 |

## 5. API 设计建议

| 方法 | 路径 | 用途 | 请求参数 | 响应数据 | 鉴权要求 | 错误码 / 异常 |
|---|---|---|---|---|---|---|
| POST | /api/auth/login | 登录 | username, password | access_token, role | 无 | INVALID_CREDENTIALS |
| GET | /api/auth/me | 当前用户 | 无 | user profile | JWT | UNAUTHORIZED |
| POST | /api/files/upload-url | 获取 OSS 上传授权 | filename, mime_type, size | upload_url, file_id, object_key | operator/admin | FILE_TOO_LARGE, INVALID_TYPE |
| POST | /api/document-jobs | 创建任务 | source_file_id, mode, template_version_id, language_pair | job_id, status | operator/admin | TEMPLATE_NOT_FOUND, PDF_LIMIT_EXCEEDED |
| GET | /api/document-jobs | 任务列表 | status, page, page_size | jobs[] | operator/admin | INVALID_QUERY |
| GET | /api/document-jobs/{job_id} | 查询任务状态 | path job_id | job detail | owner/admin | NOT_FOUND, FORBIDDEN |
| GET | /api/document-jobs/{job_id}/events | 查询任务事件 | path job_id | events[] | owner/admin | NOT_FOUND, FORBIDDEN |
| GET | /api/document-jobs/{job_id}/parse-result | 查询解析摘要 | path job_id | parse summary, quality_flags | owner/admin | NOT_READY |
| POST | /api/document-jobs/{job_id}/retry | 重试失败任务 | path job_id | new status | owner/admin | NOT_RETRYABLE |
| GET | /api/document-jobs/{job_id}/download-url | 获取 Word 下载链接 | path job_id | signed_url, expires_in | owner/admin | NOT_READY, FILE_EXPIRED |
| GET | /api/templates | 查询模板 | company_id, status | templates[] | operator/admin | 无 |
| GET | /api/templates/{template_id}/versions | 查询模板版本 | path template_id | versions[] | operator/admin | NOT_FOUND |
| POST | /api/templates | 创建模板 | name, company_id | template | admin | FORBIDDEN |
| POST | /api/templates/{template_id}/versions | 创建模板版本 | docx_sample_file_id, config_file_id | version | admin | INVALID_TEMPLATE_CONFIG |
| GET | /api/term-bases | 查询术语库 | language_pair | term_bases[] | operator/admin | 无 |
| POST | /api/term-bases/{id}/versions | 创建术语版本 | file_id, version | term_version | admin | INVALID_TERM_FILE |

## 6. 异步任务设计

### 6.1 任务类型

- P0 中文任务：PDF 校验完成后，执行解析、DocumentIR 转换、Word 渲染、OSS 上传。
- P1 英译中任务：在 P0 链路中增加翻译阶段。
- 后续任务：模板回归测试、批量清理、失败重跑、预览生成。

### 6.2 状态机

| 状态 | 说明 |
|---|---|
| pending | 任务已创建，未投递或等待投递 |
| queued | 已投递 Celery，等待 Worker |
| running | Worker 正在执行 |
| succeeded | 全链路完成 |
| failed | 任务失败，记录 failed_stage 和 error_message |
| canceled | 用户或系统取消 |

阶段建议：

```text
uploaded -> parsing -> parsed -> translating -> translated -> rendering -> uploading -> completed
```

P0 可跳过 translating / translated。

### 6.3 重试策略

- MinerU 解析失败：默认不自动无限重试，允许人工触发一次或有限次数重试。
- AI 调用失败：可按 provider 错误类型短暂重试，例如网络错误 2 次。
- OSS 上传失败：可自动重试。
- 模板渲染失败：通常是配置或数据问题，不建议自动重试。

### 6.4 幂等设计

- Celery 任务以 job_id 为唯一业务键。
- 每个阶段开始前检查 document_jobs 当前状态和阶段。
- 输出文件以 job_id、stage、version 构造 object_key，避免不可追踪的重复文件。
- 重试时记录新的 job_events，不覆盖历史事件。

### 6.5 进度查询

- API 只读 MySQL，不直接暴露 Celery backend。
- document_jobs.progress 可按阶段粗粒度更新。
- job_events 保存每个阶段的开始、完成、失败事件。

### 6.6 失败恢复

- failed 任务保留输入文件、中间结果和错误信息。
- 允许 operator/admin 对可重试失败进行 retry。
- 输入文件过期、模板版本停用、术语版本停用时，应拒绝重试并返回明确原因。

### 6.7 任务结果保存

- 原始 PDF、MinerU 原始结果、DocumentIR、图片、生成 Word 默认保留 90 天。
- MySQL 中记录 expires_at。
- 生成 Word 的临时下载链接有效期 10 分钟。

## 7. 权限与安全

### 7.1 用户身份体系

- MVP 使用内部账号 + JWT。
- 角色简化为 admin 和 operator。
- admin 管理模板配置和术语配置。
- operator 创建任务、查询任务、下载结果。

### 7.2 公司 / 租户隔离

- MVP 单租户简化。
- 数据模型保留 tenant_id、company_id、created_by。
- API 查询默认按当前用户归属过滤，admin 可查看更广范围。

### 7.3 文件访问权限

- 不直接长期暴露 OSS URL。
- FastAPI 校验权限后生成临时签名 URL。
- 下载链接有效期 10 分钟。

### 7.4 模板和术语权限

- admin 可创建、发布、停用模板版本和术语版本。
- operator 只能读取可用模板和术语版本。

### 7.5 版本回滚权限

- MVP 可预留回滚 API 或由后台脚本处理。
- 回滚动作必须写 audit_logs。

### 7.6 外部 AI 调用安全

- 外部 AI 调用由配置开关控制。
- 默认不在业务日志中保存完整发送文本。
- 记录任务 ID、段落 ID、语言方向、模型提供方、模型名、术语版本、请求时间、响应时间、token/字符数、内容哈希、脱敏摘要和错误信息。
- 调试开关开启时，按任务级别短期保存完整 prompt/response，保留 1 天。
- translation provider 接口预留私有化模型适配。

### 7.7 数据脱敏

- 日志 payload 不默认写 PDF 原文和完整翻译文本。
- AI 调用摘要需要脱敏。
- 错误信息避免包含密钥、签名 URL、完整文件路径。

## 8. 日志与可观测性

| 类别 | 内容 |
|---|---|
| 请求日志 | request_id, user_id, method, path, status_code, duration_ms |
| 任务日志 | job_id, stage, status, duration_ms, error_code |
| 解析日志 | MinerU 调用耗时、输出文件、quality_flags |
| 翻译日志 | provider, model, token/字符数、耗时、错误类型 |
| Word 生成日志 | template_version_id, block_count, table_count, image_count, duration_ms |
| OSS 日志 | bucket, object_key, size, operation, duration_ms |
| 审计日志 | actor_id, action, object_type, object_id, metadata |

关键指标：

- 任务成功率。
- P0 各阶段耗时。
- MinerU 解析失败率。
- Word 生成失败率。
- P1 翻译失败率。
- 队列积压量。
- 平均文件大小和页数。
- Golden Sample 回归通过率。

告警策略：

- 任务失败率超过阈值。
- Worker 队列积压超过阈值。
- OSS 上传/下载授权失败率异常。
- Redis 或 MySQL 连接异常。
- 单阶段耗时超过预期。

## 9. 测试与验证

| 类型 | 验证内容 |
|---|---|
| 单元测试 | PDF 限制校验、DocumentIR schema、模板选择、OSS key 生成、权限判断 |
| API 测试 | 登录、上传授权、创建任务、查询状态、事件查询、下载授权 |
| 任务链路测试 | P0 中文 PDF 到 Word 全链路 |
| Golden Sample 回归 | 10-20 份样本，核心链路成功率不低于 90% |
| 模板兼容性测试 | 1-2 套模板配置包生成结果 |
| 翻译质量测试 | P1 英译中样本、术语版本引用、结构不变性 |
| 安全测试 | JWT 过期、越权访问、下载链接过期、敏感日志检查 |
| 性能测试 | 50MB / 200 页边界、P0 20 分钟、P1 60 分钟超时 |
| 故障测试 | MinerU 失败、AI 失败、OSS 失败、Worker 重启、Redis 短暂不可用 |

## 10. 分阶段实施计划

| 阶段 | 目标 | 主要任务 | 交付物 | 验证方式 | 风险 |
|---|---|---|---|---|---|
| 阶段 0 | PoC 验证 | 选 3-5 份样本，验证 MinerU、DocumentIR、Word 生成 | PoC 脚本和样例输出 | 人工查看 Word | MinerU 输出不稳定 |
| 阶段 1 | P0 基础后端 | FastAPI、JWT、MySQL 模型、OSS 文件元数据、Celery Worker | 可创建和查询 document_jobs | API 测试 | 状态模型设计不清 |
| 阶段 2 | P0 中文主链路 | MinerU 解析、DocumentIR 转换、模板渲染、OSS 上传 | 中文 PDF 到 Word 全链路 | 10-20 份 Golden Sample | 表格和图片还原不足 |
| 阶段 3 | 模板资产雏形 | 1-2 套模板配置包、模板版本、任务引用 | 模板版本管理能力 | 模板回归测试 | 配置规则过度复杂 |
| 阶段 4 | P1 翻译实验 | translation provider、术语版本、AI 调用审计 | 英译中实验链路 | 英文样本人工验收 | 翻译质量和成本不稳定 |
| 阶段 5 | 稳定化 | 重试、失败分类、日志指标、文件清理 | 运维可用版本 | 故障注入和回归测试 | 清理策略与合规冲突 |

## 11. 风险与验证方式

| 风险 | 类型 | 影响程度 | 触发条件 | 应对方案 | 验证方式 |
|---|---|---:|---|---|---|
| MinerU 对双栏顺序解析不稳定 | 技术 | 高 | 双栏规格书正文顺序错乱 | DocumentIR 中记录块顺序和质量标记，样本回归 | Golden Sample 分类型统计 |
| 表格重建质量不足 | 技术 | 高 | 参数表跨页、合并单元格复杂 | 先支持主要参数表，复杂表格标记人工校对 | 人工样例对比 |
| 图片丢失或锚点错误 | 技术 | 中 | 引脚图、封装图提取异常 | 图片作为独立资产引用，渲染时固定规则插入 | Word 输出抽检 |
| AI 翻译破坏结构 | 技术 | 高 | 让 AI 处理整段 Markdown 或 Word | 只翻译 DocumentIR 文本节点，结构由系统保持 | 结构不变性测试 |
| 外部 AI 数据泄露 | 安全 | 高 | 日志保存全文或签名 URL 暴露 | 默认只存哈希和脱敏摘要，调试全文保留 1 天 | 日志审计 |
| OSS URL 长期暴露 | 安全 | 中 | MySQL 存长期可访问 URL | 存 object_key，下载时生成临时签名 URL | 权限和过期测试 |
| Worker 重复执行 | 一致性 | 中 | Celery 重试或 Worker 重启 | job_id 幂等、阶段检查、输出文件可追踪 | 故障注入 |
| 任务超时导致状态不一致 | 稳定性 | 中 | P0 超 20 分钟或 P1 超 60 分钟 | Celery 超时 + MySQL failed 状态兜底 | 超时测试 |
| 模板规则过度灵活 | 交付 | 中 | 希望支持任意 docx | MVP 限定 1-2 套预配置模板包 | 模板回归 |
| Golden Sample 不代表真实输入 | 产品 | 高 | 样本选择过窄 | 业务和技术共同维护样本分类 | 样本覆盖评审 |

## 12. 反直觉技术原则

【建议】不要让 AI 直接生成 Word，而是让 AI 只翻译 DocumentIR 的文本节点，Word 由模板引擎确定性生成。

- 为什么反直觉：看起来让 AI 直接生成 Word 或 Markdown 更快。
- 适用前提：系统需要稳定排版、模板一致、术语可追溯、可回归测试。
- 潜在收益：结构可控、样式可控、失败点可定位、结果可复现。
- 主要代价：必须维护 DocumentIR schema 和模板渲染规则。
- 最小验证方式：选 3 份中文 PDF 和 1 份英文 PDF，验证 MinerU -> DocumentIR -> Word 与 DocumentIR -> 翻译文本 -> Word 两条链路。

## 13. Open questions

| 问题 | 影响程度 | 影响范围 | 建议确认方式 |
|---|---|---|---|
| MinerU 的实际调用方式 | 高 | Worker 部署、资源、超时 | 确认本地命令、容器或远程服务 |
| OSS SDK、bucket、签名 URL 规范 | 中 | 文件服务和安全 | 与公司云资源负责人确认 |
| MySQL 版本和 JSON 字段支持 | 中 | DocumentIR 摘要、event payload | 查看公司数据库版本 |
| Redis 部署方式和连接限制 | 中 | Celery broker 稳定性 | 与运维确认连接数和持久化策略 |
| 外部 AI provider 和模型 | 中 | P1 成本、质量、安全 | 做模型对比样本测试 |
| 初始模板配置包格式 | 高 | Word 生成实现 | 用 1 套模板先做 PoC |
| 初始术语表格式 | 中 | P1 翻译一致性 | 先用 CSV/JSON/XLSX 中一种 |
| 清理任务是否由本服务执行 | 中 | 文件生命周期 | 确认 OSS 生命周期规则是否可用 |
