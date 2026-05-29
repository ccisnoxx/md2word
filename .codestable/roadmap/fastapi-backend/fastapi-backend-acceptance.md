---
doc_type: roadmap-acceptance
slug: fastapi-backend-acceptance
status: current
summary: 对 fastapi-backend 这一期后端产品化工作的验收闭环，覆盖接口契约、行为、场景、术语、架构归并、requirement 回写和 roadmap 回写
last_reviewed: 2026-05-18
tags: [acceptance, backend, fastapi, jobs, docx]
---

# fastapi-backend 验收报告

> 阶段：验收闭环  
> 验收日期：2026-05-18  
> 关联方案 doc：[fastapi-backend-roadmap.md](/Users/sc/MinerU/md2word_file/.codestable/roadmap/fastapi-backend/fastapi-backend-roadmap.md)

## 1. 接口契约核对

对照 roadmap 第 7 节实际核查：

- [x] `POST /api/v1/jobs`：`package`、`translation_mode`、`document_language`、`use_mineru_header_footer` 已落地；`en2zh` 会先做翻译可用性预检。代码：`app/api/v1/routers/jobs.py`
- [x] `GET /api/v1/jobs`、`GET /api/v1/jobs/{job_id}`、`GET /files`、`GET /events`、`GET /result`、`GET /download/{artifact_alias}` 已落地。代码：`app/api/v1/routers/jobs.py`
- [x] `GET /api/v1/health/live` 与 `GET /api/v1/health/ready` 已落地，兼容入口 `/api/v1/health` 已保留。代码：`app/api/v1/routers/health.py`
- [x] `GET /api/v1/templates`、`GET /api/v1/templates/{template_id}`、`GET /download` 已落地。代码：`app/api/v1/routers/templates.py`
- [x] 内部 conversion 合同已从 jobs stage 中抽离，`ConversionRequest/ConversionResult/ConversionFailure` 有稳定定义。代码：`app/conversion/contracts.py`
- [x] 产物合同已由 `JobArtifactService` 承载，router 不再散落 alias/media-type/path 规则。代码：`app/services/jobs/artifacts.py`

流程图核对：

- [x] roadmap 里的后端主流程节点在代码均有实际落点：`create_job_from_saved_upload()` → `enqueue_conversion()` → `dispatch_message()` → `build_job_conversion_request()` → `ConversionService.convert()` → `download/result`

## 2. 行为与决策核对

需求摘要逐项验证：

- [x] 可上传合法 MinerU 输出 zip 并生成 DOCX：真实样例 `job_d93a9b69f751` 成功完成。
- [x] `direct` 与 `en2zh` 共用同一条 jobs 主链：`job_d93a9b69f751`（direct）与 `job_567c1e2d7839`（en2zh）均完成。
- [x] 支持任务状态、事件、产物和下载：`jobs` / `events` / `files` / `result` 都可查。
- [x] 支持 `retry`、`cancel`、`cleanup-local-files` 本地运维动作：对象级测试已覆盖。
- [x] 支持默认模板和绑定 YAML 只读查询：真实 `/api/v1/templates` 已返回元数据。

明确不做逐项核对：

- [x] 未实现 `PDF -> 在线 MinerU -> callback`。
- [x] 未引入 MySQL / SQLite / Redis / Celery。
- [x] 未实现模板 CRUD 和术语规则 CRUD。
- [x] 未改变现有 DOCX 版式策略，只做服务化壳层和合同收紧。

关键决策落地：

- [x] API 层保持薄：router 不直接调用 `run_conversion()`，实际由 `ConversionEntrypoint` 和 `JobStageService` 承载。
- [x] file backend 先行：`FileJobRepository` 是当前唯一仓储实现，`health` 明确暴露 `configured/effective_repository_backend=file`。
- [x] 产物只通过逻辑路径和下载合同暴露：`JobFile.path` 为 job 内逻辑路径，本地绝对路径只在服务端推导。
- [x] `en2zh` 预检前移：缺 `OPENAI_API_KEY` 或 prompt 时，`POST /jobs` 直接返回 `503`。

挂载点反向核对：

- [x] jobs 挂载点集中在 `app/api/v1/routers/jobs.py`、`app/services/jobs/*`、`app/repositories/file_job_repository.py`
- [x] templates 挂载点集中在 `app/api/v1/routers/templates.py` 与 `app/services/templates/read_service.py`
- [x] `rg` 结果显示 `source_package` / `translation_request` / `result_docx` / `translation_started` / `translation_completed` / `/api/v1/templates` 等关键术语都只落在预期文件中，没有清单外的散落实现
- [x] 拔除沙盘推演：删掉 `app/services/jobs/artifacts.py` 或 `app/conversion/contracts.py`，`jobs` 和 `templates` 合同会直接失效，挂载点清单成立

## 3. 验收场景核对

- [x] 场景 S1：上传合法 MinerU 输出 zip，`direct` 模式生成 DOCX
  - 证据来源：真实联调任务 `job_d93a9b69f751`
  - 结果：通过；下载文件 [job_d93a9b69f751.docx](/private/tmp/job_d93a9b69f751.docx)，`file` 识别为 `Microsoft Word 2007+`

- [x] 场景 S2：`en2zh` 模式走翻译并生成中文 DOCX
  - 证据来源：真实联调任务 `job_567c1e2d7839`
  - 结果：通过；事件流包含 `translation_started`、`translation_completed`，下载文件 [job_567c1e2d7839_zh.docx](/private/tmp/job_567c1e2d7839_zh.docx)

- [x] 场景 S3：翻译不可用时拒绝创建 `en2zh` 任务
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_upload_en2zh_rejects_when_translation_unavailable`
  - 结果：通过；返回 `503`

- [x] 场景 S4：`retry` 可重入失败任务
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_retry_requeues_failed_job_without_admin_token`
  - 结果：通过

- [x] 场景 S5：`cancel` 只允许取消 `uploaded/queued` 任务
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_cancel_queued_job_without_admin_token`
  - 结果：通过

- [x] 场景 S6：`cleanup-local-files` 只删除未登记运行态目录
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_cleanup_local_files_preserves_registered_artifacts_and_removes_work_dir`
  - 结果：通过

- [x] 场景 S7：只读模板接口返回默认模板和绑定配置元数据
  - 证据来源：真实 `GET /api/v1/templates`、`GET /api/v1/templates/default`
  - 结果：通过

- [x] 场景 S8：默认模板文件可下载
  - 证据来源：真实下载 [default_template.docx](/private/tmp/default_template.docx)
  - 结果：通过

- [x] 场景 S9：全量自动化回归保持通过
  - 证据来源：`/Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover -s tests`
  - 结果：通过，当前共 `100` 个测试

## 4. 术语一致性

- `source_package`：代码、测试、文档命中一致 ✓
- `translation_request`：代码、测试、文档命中一致 ✓
- `result_docx`：代码、测试、文档命中一致 ✓
- `convert_package`：后台 stage 命名一致 ✓
- `translation_started / translation_completed / translation_failed`：事件名一致 ✓
- `default_template_id` 与 `/api/v1/templates/default`：模板只读合同一致 ✓

防冲突：

- `rg` 核查未发现“同一语义多个名字”或“同一名字多个语义”的冲突命名 ✓

## 5. 架构归并

- [x] 新增架构 doc：[backend-fastapi-service.md](/Users/sc/MinerU/md2word_file/.codestable/architecture/backend-fastapi-service.md)
  - 归并内容：FastAPI 后端表面、jobs、templates、health、stage、artifact 合同、翻译能力和运行边界
- [x] 更新总入口：[ARCHITECTURE.md](/Users/sc/MinerU/md2word_file/.codestable/architecture/ARCHITECTURE.md)
  - 归并内容：仓库已从单一 CLI 工具演进为“CLI 转换核心 + FastAPI 后端壳层”的双表面结构
- [x] `conversion-flow.md` 保持有效，无需额外改写
  - 理由：它仍然准确描述底层转换核心的输入、修补、翻译和渲染流程
- [x] `app-conversion-internal.md` 保持有效，无需额外改写
  - 理由：FastAPI 壳层没有改变底层 runtime 模块边界

## 6. requirement 回写

- [x] 当前仓库此前没有 requirement 文档，本次新增能力属于用户可感知的新能力，因此执行 backfill。
- [x] 新增 requirement：[fastapi-backend-productization.md](/Users/sc/MinerU/md2word_file/.codestable/requirements/fastapi-backend-productization.md)
- [x] 新增索引：[VISION.md](/Users/sc/MinerU/md2word_file/.codestable/requirements/VISION.md)
- [x] requirement 状态已直接落为 `current`

## 7. roadmap 回写

- [x] `.codestable/roadmap/fastapi-backend/fastapi-backend-items.yaml` 已全部更新为 `done`
- [x] `fastapi-backend-roadmap.md` 主文档第 14/15/16/17 节已同步为完成态
- [x] `pdf-mineru-ingestion-spike` 调研结论已写入 `.codestable/roadmap/fastapi-backend/drafts/pdf-mineru-ingestion-spike.md`
- [x] roadmap 相关 YAML 均已通过 `validate-yaml.py`

## 8. attention.md 候选盘点

- [ ] 候选 1：FastAPI 运行时依赖当前通过仓库内 `.python_packages/` vendoring 方式补齐，`run_api.py` 是最稳定启动入口；这条规则是否要写进 `.codestable/attention.md`，避免后续 feature 再踩一次？

## 9. 遗留

- `translation_request_output` 在底层 CLI 文案和实际行为之间仍有差异，已记录为后续观察项。
- 当前后端仍只支持 file backend；如需数据库或对象存储，需要另起后续 feature。
- `PDF -> 在线 MinerU -> callback` 不在本期范围，已完成 spike，建议另开新 roadmap / feature。
