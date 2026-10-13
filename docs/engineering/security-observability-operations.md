---
doc_type: non-functional-design
status: target
last_reviewed: 2026-10-03
---

# 安全、可观测与运维

## 1. 安全边界

系统是公司内部单租户应用，但处理可能包含未公开技术资料，不能按普通公开文件处理。

## 2. 数据流

### 直接转换

```text
Browser → API/Storage → MinerU → Worker → DOCX
```

不得进入 LLM Provider。

### 翻译

```text
Browser → API/Storage → MinerU → DocumentIR
→ 受控文本单元 → LLM Provider → 目标 DocumentIR → DOCX
```

不向 LLM 发送：

- 整个 PDF；
- 图片；
- 表格 HTML 标签结构；
- 对象存储路径；
- 用户信息；
- secret。

## 3. 身份与权限

- 内部账号 + JWT；
- 角色仅 `operator/admin`；
- 所有管理、发布、清理和全文 debug 操作为 Admin-only；
- 任务读权限按 owner/admin；
- 下载授权由后端生成，不能只靠前端隐藏。

## 4. 外部 Provider 安全

### MinerU

- Callback 签名/HMAC；
- job/generation 绑定；
- 幂等 dedupe key；
- 结果 URL 允许域名；
- HTTPS；
- 禁止 localhost/IP literal/私网解析；
- 下载大小、重定向和超时限制；
- ZIP 展开限制。

### LLM

- Provider config 不返回 secret；
- API Key 只从环境或 secret resolver；
- 日志不记录 Authorization；
- 调用摘要与全文 debug 分离；
- 超时和重试预算；
- Prompt injection 风险通过“模型只接触文本且只能返回 ID/text”降低。

## 5. Artifact 安全

- object key 不暴露给普通 API；
- 下载 URL 短时有效；
- 文件路径标准化；
- 文件清理需 preview、确认、reason 和 audit；
- 发布件和源文件保留策略独立；
- debug archive 最短保留期；
- 已发布文件禁止物理覆盖。

## 6. 日志

### 必须字段

```text
timestamp
level
service
trace_id
job_id
generation
stage
event_type
duration_ms
error_code
```

### 禁止字段

- 密码；
- JWT；
- API Key；
- 完整 PDF 文本；
- 完整 Prompt/Response（常规日志）；
- 本地绝对路径；
- presigned URL query。

## 7. 指标

### 任务

- jobs created/completed/failed/canceled；
- stage duration；
- stale running jobs；
- retry count；
- queue lag。

### MinerU

- submission latency；
- callback latency；
- invalid callback；
- package download/validation failure；
- missing asset/table HTML。

### 翻译

- calls、latency、tokens、cost（若可用）；
- batch retries/splits；
- ID/Token validation failures；
- term hit rate；
- language direction pass rate。

### 渲染/质量

- DOCX render duration；
- table/image/formula count；
- blocked/warning rate；
- table issue distribution；
- preview failure；
- review pass rate；
- publish count。

## 8. 告警

P0：

- API/Worker/DB/Redis 不可用；
- 任务队列停止消费；
- MinerU callback 连续失败；
- 产物存储不可写；
- DOCX 无法生成或打开；
- 发布 API 绕过质量/复核门禁。

P1：

- blocked 比例异常升高；
- 翻译校验失败率升高；
- preview 连续失败；
- stale jobs；
- 存储接近配额。

## 9. 健康检查

### Liveness

进程可响应，不检查所有下游。

### Readiness

至少检查：

- MySQL；
- Redis/Celery 配置；
- Artifact Storage；
- document_jobs worker backend；
- 必须配置资源；
- 生产访问 guardrail。

翻译 Provider 或 MinerU 暂时不可用可返回 degraded capability，但创建相应模式任务时必须拒绝或明确不可用。

## 10. 备份与恢复

备份：

- MySQL；
- Artifact Storage；
- 模板和术语版本目录；
- bootstrap admin 输入；
- 生产 `.env`/secret 的外部安全备份。

恢复验证：

- 历史任务可查询；
- 发布件可下载；
- 默认模板/术语指针正确；
- pending callback/batch 可重放；
- 不重复发布或覆盖文件。

## 11. 容量

限制并监控：

- 单 PDF 大小和页数；
- MinerU ZIP 下载/展开大小；
- 图片数和总大小；
- 单表 HTML 大小和行数；
- 翻译批次字符数；
- 单任务 Artifact 总量；
- debug archive 保留。

限制触发必须产生可理解错误，不允许 Worker OOM 后无事件终止。

## 12. 隐私与调试

全文 debug：

- 默认 false；
- Admin-only；
- UI 有敏感数据提示；
- 独立 file type；
- 自动过期；
- 查看/下载审计。

常规 QA 应使用必要片段和哈希，不依赖全文归档。

## 13. 发布运维

1. 使用 commit/release 标识镜像；
2. 先执行 schema migration；
3. 部署 API/Worker；
4. 检查 readiness；
5. 运行 release check；
6. 运行 Golden/Translation gates；
7. Admin signoff；
8. 记录 deployment ID 和 run directory；
9. 保留回滚镜像和 schema 回滚说明。
