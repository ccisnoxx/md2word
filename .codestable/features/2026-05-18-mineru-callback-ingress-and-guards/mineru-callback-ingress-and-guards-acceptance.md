---
doc_type: feature-acceptance
feature: 2026-05-18-mineru-callback-ingress-and-guards
status: current
summary: 对 mineru-callback-ingress-and-guards 的 callback 契约、安全边界、架构归并和 roadmap 回写的验收闭环
last_reviewed: 2026-05-18
tags: [acceptance, mineru, callback, guards]
---

# mineru-callback-ingress-and-guards 验收报告

> 阶段：阶段 3（验收闭环）  
> 验收日期：2026-05-18  
> 关联方案 doc：[mineru-callback-ingress-and-guards-design.md](/Users/sc/PycharmProjects/md2word/.codestable/features/2026-05-18-mineru-callback-ingress-and-guards/mineru-callback-ingress-and-guards-design.md)

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `NormalizedMinerUCallback`（[app/api/dependencies.py](/Users/sc/PycharmProjects/md2word/app/api/dependencies.py) `normalize_mineru_callback_payload`）：顶层字段、`content` JSON 和 `extract_result[0]` 可归一化出 `batch_id/data_id/state/full_zip_url/data`，与方案一致。
- [x] `enqueue_callback()`（[app/services/jobs/command.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/command.py)）：返回 `JobRecord, JobStageMessage`，并生成 `process_callback` stage，和方案定义一致。

**名词层“现状 → 变化”逐项核对**：

- [x] `JobRecord`：已新增 `mineru_result_zip_url`，并通过 [app/core/job_models.py](/Users/sc/PycharmProjects/md2word/app/core/job_models.py) / [app/schemas/api_v1.py](/Users/sc/PycharmProjects/md2word/app/schemas/api_v1.py) 对外暴露。
- [x] `JobStatus`：已新增 `parsed`，读模型统计也纳入 [app/services/jobs/query.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/query.py)。
- [x] `JobStageMessage.stage`：已新增 `process_callback`，代码落点在 [app/core/job_models.py](/Users/sc/PycharmProjects/md2word/app/core/job_models.py)。

**流程图核对**（第 2.2 节开头 mermaid 图）：

- [x] `POST /api/v1/mineru-callbacks/result` -> guard -> normalize -> `enqueue_callback()` -> `process_callback` -> repository 持久化，在 [app/api/v1/routers/mineru_callbacks.py](/Users/sc/PycharmProjects/md2word/app/api/v1/routers/mineru_callbacks.py)、[app/api/dependencies.py](/Users/sc/PycharmProjects/md2word/app/api/dependencies.py)、[app/services/jobs/command.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/command.py)、[app/services/jobs/stage.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/stage.py) 均有实际落点。

## 2. 行为与决策核对

对照方案第 1 节 + 第 2.2 节：

**需求摘要逐项验证**：

- [x] 新增 `POST /api/v1/mineru-callbacks/result`：接口已单独挂在 [app/api/v1/routers/mineru_callbacks.py](/Users/sc/PycharmProjects/md2word/app/api/v1/routers/mineru_callbacks.py)。
- [x] 支持 `internal / single_tenant_public` 两种部署模式：`verify_mineru_callback_identity()` 已实现分支。
- [x] `done + full_zip_url` 时任务进入 `parsed`：`_dispatch_process_callback()` 实际更新 `status=parsed`、`mineru_result_zip_url`。
- [x] `failed` 时任务进入 `failed`：`_dispatch_process_callback()` 实际写入 `status=failed`、`error_code=mineru_failed`。
- [x] `full_zip_url` 必须通过 `https + host allowlist`：router guard 和 stage 双重校验均存在。

**明确不做逐项核对**（用第 3 节“反向核对项”）：

- [x] 范围外事项“下载结果 zip / 生成 DOCX / recover-mineru-result / 直接接入 convert_package 主链”确实没做；`rg -n "recover-mineru-result|mineru_result_zip|download.*zip|convert_package.*callback"` 仅命中文档或既有转换入口，没有 callback 结果下载与 DOCX 回流实现。

**关键决策落地**：

- [x] D1 callback 入口单独建 router：已新增 [app/api/v1/routers/mineru_callbacks.py](/Users/sc/PycharmProjects/md2word/app/api/v1/routers/mineru_callbacks.py)，未混入 `jobs.py`。
- [x] D2 `internal/public` 直接在服务端分支：已落在 `verify_mineru_callback_identity()`。
- [x] D3 `checksum` 仅在 payload 携带时启用：已落在 `verify_mineru_callback_checksum_for_job()`。
- [x] D4 callback 终态只收口到 `parsed/failed`：已落在 `_dispatch_process_callback()`，未继续派生后处理。
- [x] D5 任务匹配优先级 `data_id -> batch_id`：`find_job_for_callback()` 已按该顺序实现，并有回归测试锁住。

**编排层“现状 → 变化”逐项核对**：

- [x] 新增 callback router：见 [app/api/v1/routers/mineru_callbacks.py](/Users/sc/PycharmProjects/md2word/app/api/v1/routers/mineru_callbacks.py)。
- [x] 新增 `process_callback` stage：见 [app/services/jobs/stage.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/stage.py) `enqueue_process_callback()` 和 `_dispatch_process_callback()`。
- [x] `JobStageService` 负责 `full_zip_url` 校验、`mineru_status` 更新和 `parsed/failed` 收口：与方案一致。
- [x] router 只负责 guard + normalize + enqueue，不直接改 job：已通过实现和测试核对。

**流程级约束核对**（错误语义 / 幂等 / 并发 / 扩展点 / 可观测点）：

- [x] 公开模式缺 callback token 配置返回 `503`；token/checksum 错误返回 `403`；payload 缺 `batch_id/data_id` 或 URL 非法返回 `400`；缺 seed 且要求 checksum 返回 `409`。对象级测试已覆盖主要错误语义。
- [x] 幂等覆盖：`process_callback` 每次按最新 payload 覆盖 `mineru_status/full_zip_url`，未引入累加型副作用。
- [x] 并发 / 顺序：`verify_mineru_callback_job_state()` 与 stage 内防御式护栏均把作用范围限制在 `parsing/parsed/failed`。
- [x] 扩展点：当前只把 `parsed` 作为后续 postprocess 的稳定挂点，未另起平行主链。
- [x] 可观测点：已实际落盘 `mineru_callback_received / mineru_callback_processed / mineru_callback_failed`。

**挂载点反向核对（可卸载性）**：

- [x] `POST /api/v1/mineru-callbacks/result`：代码落点为 [app/api/v1/routers/mineru_callbacks.py](/Users/sc/PycharmProjects/md2word/app/api/v1/routers/mineru_callbacks.py)，与清单一致。
- [x] `process_callback`：代码落点为 [app/core/job_models.py](/Users/sc/PycharmProjects/md2word/app/core/job_models.py)、[app/services/jobs/stage.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/stage.py)，与清单一致。
- [x] `parsed`：代码落点为 [app/core/job_models.py](/Users/sc/PycharmProjects/md2word/app/core/job_models.py)、[app/schemas/api_v1.py](/Users/sc/PycharmProjects/md2word/app/schemas/api_v1.py)、[app/services/jobs/query.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/query.py)，与清单一致。
- [x] `PUBLIC_DEPLOYMENT_MODE / MINERU_CALLBACK_TOKEN / MINERU_CALLBACK_TOKEN_QUERY_NAME / MINERU_UID / MINERU_RESULT_HOST_ALLOWLIST`：代码落点为 [app/core/config.py](/Users/sc/PycharmProjects/md2word/app/core/config.py)。
- [x] `mineru_result_zip_url`：代码落点为 [app/core/job_models.py](/Users/sc/PycharmProjects/md2word/app/core/job_models.py)、[app/schemas/api_v1.py](/Users/sc/PycharmProjects/md2word/app/schemas/api_v1.py)、[app/services/jobs/stage.py](/Users/sc/PycharmProjects/md2word/app/services/jobs/stage.py)。
- [x] 反向 grep：`mineru_callbacks|process_callback|mineru_result_zip_url|parsed` 的代码引用都能映射回 design 第 2.3 节清单，没有发现清单外新增挂载点。
- [x] 拔除沙盘推演：若移除 router、`process_callback` stage、`parsed` 状态和相关配置项，残留主要在 API/架构/运行文档；当前无隐式业务逻辑残留。

## 3. 验收场景核对

对照方案第 3 节关键场景清单，逐条可观察证据验证：

- [x] **S1**：`internal` 模式下 callback 不需要 token
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_callback_internal_mode_accepts_and_marks_job_parsed`
  - 结果：通过

- [x] **S2**：`single_tenant_public` 模式下缺 token 或 token 错误时拒绝
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_callback_public_mode_requires_token`、`tests/test_fastapi_jobs_backend.py::test_callback_public_mode_missing_token_config_returns_503`
  - 结果：通过

- [x] **S3**：payload 可从 `content` JSON 字符串归一化出 `batch_id/data_id/state/full_zip_url`
  - 证据来源：`tests/test_fastapi_jobs_backend.py` 中全部 callback 路径都仅提交 `batch_id + content`，实际可收口到对应 job
  - 结果：通过

- [x] **S4**：checksum 正确时允许通过；错误时返回 `403`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_callback_checksum_uses_seed_and_uid_fallback`、`tests/test_fastapi_jobs_backend.py::test_callback_rejects_invalid_checksum_without_leaving_stage_message`
  - 结果：通过

- [x] **S5**：callback 命中 `done + full_zip_url` 时任务进入 `parsed` 并持久化 `mineru_result_zip_url`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_callback_internal_mode_accepts_and_marks_job_parsed`
  - 结果：通过

- [x] **S6**：callback 命中 `failed` 时任务进入 `failed`，`error_code=mineru_failed`
  - 证据来源：`tests/test_fastapi_jobs_backend.py::test_callback_failed_state_marks_job_failed`
  - 结果：通过

- [x] **S7**：不改动现有 `/api/v1/jobs` 与 `/api/v1/jobs/pdf` 入口语义
  - 证据来源：`/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - 结果：通过

## 4. 术语一致性

对照方案第 0 节 + 第 2.1 节命名 grep 代码：

- `process_callback`：代码 / 测试 / 文档命中一致 ✓
- `parsed`：状态枚举、schema、测试和文档命中一致 ✓
- `mineru_result_zip_url`：模型、schema、stage、接口文档命中一致 ✓
- `public deployment guard` 对应配置键命名 `PUBLIC_DEPLOYMENT_MODE`、`MINERU_CALLBACK_TOKEN`、`MINERU_RESULT_HOST_ALLOWLIST` 一致 ✓
- 防冲突：未发现额外同义状态或平行 callback stage 命名 ✓

## 5. 架构归并

- [x] [backend-fastapi-service.md](/Users/sc/PycharmProjects/md2word/.codestable/architecture/backend-fastapi-service.md)：已归并 `mineru_callbacks` router、`process_callback` 编排、callback 事件和安全边界。
- [x] [ARCHITECTURE.md](/Users/sc/PycharmProjects/md2word/.codestable/architecture/ARCHITECTURE.md)：已归并 `parsed/process_callback` 术语、`/api/v1/mineru-callbacks` 路由和“callback ingress 已接入但后处理未回流”的现状边界。
- [x] `conversion-flow.md` 无需更新，理由是本 feature 不改底层 DOCX 转换主链，只补 FastAPI 在线解析收口。

## 6. requirement 回写

- [x] [fastapi-backend-productization.md](/Users/sc/PycharmProjects/md2word/.codestable/requirements/fastapi-backend-productization.md) 已更新：能力边界从“PDF 提交前半程”升级到“已接 callback ingress 与安全收口，可进入 `parsed/failed`”，同时明确仍未自动生成 DOCX。

## 7. roadmap 回写

- [x] `.codestable/roadmap/mineru-online-ingestion/mineru-online-ingestion-items.yaml` 中 `mineru-callback-ingress-and-guards` 已改为 `done`
- [x] `.codestable/roadmap/mineru-online-ingestion/mineru-online-ingestion-roadmap.md` 的子 feature 清单状态已同步为 `done`

## 8. attention.md 候选盘点

- [x] 本 feature 未暴露需要补入 `attention.md` 的新内容；callback 相关运行口径已沉淀在现有 API / runbook / architecture 文档中。

## 9. 遗留

- 后续优化点：`mineru-callback-postprocess` 仍需把 `parsed` 回流到下载结果 zip 与 DOCX 后处理主链。
- 后续优化点：`mineru-result-recovery` 仍需补 callback 丢失时的主动恢复入口。
- 已知限制：当前只做对象级测试，尚未完成真实 public 模式 callback 联调。
- 实现阶段顺手发现：conda 环境启动 `unittest` 时会打印 `_distutils_hack` 缺失告警，但不影响当前对象级测试通过。
