---
doc_type: roadmap-spike
slug: pdf-mineru-ingestion-spike
status: current
created: 2026-05-18
last_reviewed: 2026-05-18
tags: [mineru, pdf, callback, spike, backend]
reference_project: /Users/sc/PycharmProjects/create_pdf
---

# PDF -> MinerU -> callback Spike

## 1. 目标

评估是否应把“PDF 上传 -> 在线 MinerU 解析 -> callback 后处理 -> DOCX 生成”纳入当前 `md2word_file` 后端，以及如果要做，最小可落地方案应该是什么。

## 2. 结论

结论是：**可以做，但不应直接叠加到当前 `POST /api/v1/jobs` 的 MinerU zip 上传合同上**。如果要推进，应作为一组独立 feature 分阶段引入，而不是把现在已稳定的“上传 MinerU 输出 zip”链路直接改造成双模式混合入口。

原因：

1. 当前后端的最小闭环是“接收已完成的 MinerU 结果包”，而 PDF 直传会引入一个新的长生命周期状态机：上传、提交、等待回调、恢复结果、后处理。
2. `create_pdf` 里真正复杂的不是调用 MinerU API 本身，而是 callback 安全、结果 URL 白名单、丢回调后的恢复、公开部署访问边界和状态补偿。
3. 这些复杂度会直接改变 jobs 合同、health 字段、配置项、错误码和运维入口；如果和现有 zip 上传入口强行共用一个 `POST /jobs`，调用方会得到一个语义混杂的接口。

## 3. 参考项目里真正需要搬的东西

### 3.1 提交 MinerU 不是难点

`create_pdf` 的 `MinerUClient.upload_files_batch()` 已经证明，真正的提交动作只是：

- 构造 batch 请求
- 上传 PDF
- 记录 `batch_id / data_id / seed`

这部分在工程上不复杂，完全可以迁入本项目的 `app/clients/mineru_client.py`。

### 3.2 callback 安全和恢复才是主复杂度

从 `create_pdf` 的实现看，真正决定产品化成本的是：

- `PUBLIC_DEPLOYMENT_MODE=internal/single_tenant_public`
- `MINERU_CALLBACK_TOKEN` 和 query token 兼容
- callback checksum：`uid + seed + content`
- `MINERU_UID` 兜底
- 结果 zip URL 必须 `https + host allowlist`
- callback 丢失后需要 `recover-mineru-result`

这些都不属于“多写几个 API 就能顺手带上”的小改动，它们会形成新的安全和运维合同。

### 3.3 状态机会膨胀

如果引入 PDF 直传，当前 `uploaded/queued/converting/completed/failed/canceled` 状态粒度不够。至少要区分：

- `uploaded`
- `submitting`
- `parsing`
- `parsed`
- `converting`
- `completed`
- `failed`
- `canceled`

否则前端和运维无法区分“MinerU 还没回调”和“DOCX 渲染失败”。

## 4. 对当前项目的建议方案

### 4.1 不改现有 `POST /api/v1/jobs`

保留现有接口语义：

- `POST /api/v1/jobs`
  - 仍只接收 MinerU 输出 zip
  - 仍代表“后处理入口”

如果要支持 PDF 直传，新增独立入口更稳：

```text
POST /api/v1/jobs/pdf
POST /api/v1/mineru-callbacks/result
POST /api/v1/jobs/{job_id}/recover-mineru-result
```

这样现有调用方不会被破坏，新的 PDF 链路也能有自己的状态和安全约束。

### 4.2 保留当前 BackgroundTasks + file spool 模式

当前项目已经有：

- `JobStageMessage`
- `stage_messages/`
- 启动 replay

因此新的 MinerU 链路完全没必要一上来引入 Redis/Celery。最小可行路径是继续沿用现有模式，只新增 stage 类型：

- `submit_to_mineru`
- `process_callback`
- `recover_mineru_result`

### 4.3 产物合同继续收口

如果未来接入 PDF 直传，对外仍只通过 artifact 合同交付，不回退暴露本地绝对路径。新增的 artifacts 只需要扩展：

- `source_pdf`
- `mineru_result_zip`
- `raw_markdown`
- `assets_bundle`（可选）
- `result_docx`

当前已做好的 `JobArtifactService` 可以继续承载这组扩展。

## 5. 推荐拆解顺序

如果后续真的启动这条链路，建议按下面顺序做：

1. `pdf-upload-and-mineru-submission`
   - 新增 `POST /jobs/pdf`
   - 新增 `source_pdf` artifact
   - 接入 `submit_to_mineru` stage
   - 只做到“成功提交 MinerU 并记录 batch_id/data_id/seed”

2. `mineru-callback-ingress-and-guards`
   - 新增 callback router
   - 增加 internal/public 两种部署模式
   - 增加 callback token、checksum、UID 和结果 URL allowlist 校验

3. `mineru-callback-postprocess`
   - callback 命中 `done + full_zip_url` 后复用当前后处理链
   - 下载 zip、提取 markdown、生成 DOCX

4. `mineru-result-recovery`
   - 增加 `recover-mineru-result`
   - callback 丢失时按 `batch_id` 主动恢复

5. `pdf-ingestion-observability`
   - health 字段、事件、runbook、API 文档、错误码和排障说明补齐

## 6. 明确不建议的做法

- 不要把 PDF 上传和 MinerU zip 上传塞进同一个 `POST /api/v1/jobs`，靠 `content-type` 或表单字段猜模式。
- 不要先接 MinerU 提交，再把 callback 安全和恢复留到“后面再补”。
- 不要让结果 URL 白名单和 callback 鉴权依赖前端或反向代理兜底，服务端必须自己校验。
- 不要把当前 `health` 继续保持成“只看模板和目录”，一旦接 MinerU，必须把外部依赖 readiness 一起暴露。

## 7. 对当前 roadmap 的影响

本 spike 完成后，`fastapi-backend` 这一期 roadmap 可以视为完成。若要继续推进 PDF 直传 MinerU，建议另开新 roadmap 或新一轮 feature，而不是继续在当前 roadmap 上叠加。

更合适的新 roadmap 名称可以是：

- `mineru-online-ingestion`
- `pdf-ingestion-and-callback`

## 8. 结论摘要

- 当前阶段不建议立刻实现 PDF -> MinerU -> callback。
- 技术上可行，但它已经超出当前后端“上传 MinerU 结果 zip 并后处理”的边界。
- 最稳妥的下一步不是继续写代码，而是先单独起一个面向在线 MinerU 接入的 roadmap / feature 设计。
