---
doc_type: feature-acceptance
feature: 2026-05-18-pdf-upload-and-mineru-submission
status: current
summary: 对 pdf-upload-and-mineru-submission 的接口契约、行为、架构归并和 roadmap 回写的验收闭环
last_reviewed: 2026-05-18
tags: [acceptance, mineru, pdf, jobs]
---

# pdf-upload-and-mineru-submission 验收报告

> 阶段：阶段 3（验收闭环）  
> 验收日期：2026-05-18  
> 关联方案 doc：[pdf-upload-and-mineru-submission-design.md](/Users/sc/MinerU/md2word_file/.codestable/features/2026-05-18-pdf-upload-and-mineru-submission/pdf-upload-and-mineru-submission-design.md)

## 1. 接口契约核对

- [x] `POST /api/v1/jobs/pdf` 已落地，接收 `pdf/template_id/translation_mode/document_language/use_mineru_header_footer`。代码：`app/api/v1/routers/jobs.py`
- [x] `JobRecord` 已新增 `source_kind/mineru_batch_id/mineru_data_id/mineru_callback_seed/mineru_status`。代码：`app/core/job_models.py`
- [x] `JobFile.file_type` 已新增 `source_pdf`。代码：`app/core/job_models.py`
- [x] `JobStageMessage.stage` 已新增 `submit_to_mineru`。代码：`app/core/job_models.py`
- [x] `MinerUClient.upload_files_batch()` 已作为独立客户端引入。代码：`app/clients/mineru_client.py`
- [x] `GET /api/v1/jobs/{job_id}` 现已返回 `source_kind` 和 MinerU 标识字段。代码：`app/schemas/api_v1.py`、`app/api/v1/routers/jobs.py`

## 2. 行为与决策核对

- [x] 原始 PDF 上传与 MinerU zip 上传合同分离：`POST /api/v1/jobs/pdf` 与现有 `POST /api/v1/jobs` 并存。
- [x] `MINERU_API_TOKEN` 缺失时直接拒绝创建 PDF 任务，返回 `503`，没有产生静默停滞任务。
- [x] `submit_to_mineru` 只承担 PDF 提交与状态推进，不承担 callback 或 DOCX 后处理。
- [x] PDF 提交成功后任务停在 `parsing`，没有越界进入 callback 后处理逻辑。
- [x] `retry` 已按 `source_kind` 分流：`source_pdf` 任务失败后会重新走 `submit_to_mineru`。

## 3. 验收场景核对

- [x] **S1**：上传合法 PDF，返回 `201`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_pdf_submits_to_mineru_and_enters_parsing`

- [x] **S2**：后台成功提交 MinerU 后任务进入 `parsing`，并持久化 `mineru_batch_id/mineru_data_id/mineru_status`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_pdf_submits_to_mineru_and_enters_parsing`

- [x] **S3**：缺 `MINERU_API_TOKEN` 时直接返回 `503`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_pdf_rejects_when_mineru_token_missing`

- [x] **S4**：非法 PDF 返回 `400`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_pdf_rejects_invalid_pdf`

- [x] **S5**：MinerU 提交失败时任务进入 `failed`，`error_code=mineru_submit_failed`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_pdf_marks_job_failed_when_mineru_submit_fails`

- [x] **S6**：现有 `POST /api/v1/jobs` 的 zip 上传入口不受影响
  - 证据来源：`/Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover -s tests`

## 4. 术语一致性

- `source_pdf`：代码 / 测试 / 文档命中一致 ✓
- `source_kind`：代码 / 设计文档命中一致 ✓
- `submit_to_mineru`：stage 命名一致 ✓
- `mineru_batch_id / mineru_data_id / mineru_status`：代码 / 设计文档 / API 契约一致 ✓

## 5. 架构归并

- [x] [backend-fastapi-service.md](/Users/sc/MinerU/md2word_file/.codestable/architecture/backend-fastapi-service.md) 已更新，纳入 `source_pdf`、`submit_to_mineru`、`parsing` 和 PDF 在线前半程。
- [x] [ARCHITECTURE.md](/Users/sc/MinerU/md2word_file/.codestable/architecture/ARCHITECTURE.md) 已保持与现状一致；当前总入口仍明确“PDF -> 在线 MinerU -> callback”未完整接入。
- [x] `conversion-flow.md` 无需更新，理由是本 feature 不改变底层 DOCX 后处理链。

## 6. requirement 回写

- [x] [fastapi-backend-productization.md](/Users/sc/MinerU/md2word_file/.codestable/requirements/fastapi-backend-productization.md) 已更新边界：当前后端不再只是接收 MinerU 输出 zip，也已支持“上传原始 PDF -> 成功提交 MinerU -> 进入 parsing”的前半程能力。

## 7. roadmap 回写

- [x] `.codestable/roadmap/mineru-online-ingestion/mineru-online-ingestion-items.yaml` 中 `pdf-upload-and-mineru-submission` 已改为 `done`
- [x] `.codestable/roadmap/mineru-online-ingestion/mineru-online-ingestion-roadmap.md` 的子 feature 清单状态已同步为 `done`

## 8. attention.md 候选盘点

- [ ] 候选 1：真实 MinerU 联调需要在 `.env` 里补 `MINERU_API_TOKEN`，否则只能跑 fake client 路径；是否要加到 `.codestable/attention.md`？

## 9. 遗留

- 当前还没有真实 `MINERU_API_TOKEN`，因此本 feature 的外部提交路径只完成对象级验证，未完成真实在线联调。
- 当前 feature 只做到“上传 PDF -> 提交 MinerU -> 进入 parsing”，callback、安全验签、结果恢复和 DOCX 回流仍在后续 feature 范围内。
