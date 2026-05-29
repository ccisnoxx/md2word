# Translation Profile and Segment Trace 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：.codestable/features/2026-05-29-translation-profile-and-segment-trace/translation-profile-and-segment-trace-design.md

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `TranslationProfileDraftUpdateRequest`：方案字段 `target_language/domain/prompt_version/model/max_pages_per_batch/max_chars_per_batch` 均已落在 `app/schemas/translation_profiles.py`，并带长度 / 范围校验。
- [x] `TranslationProfileVersionResponse`：方案字段 `translation_profile_id/version/status/snapshot_hash/is_default/target_language/domain/prompt_version/model/max_*` 均已落在 `app/schemas/translation_profiles.py`，实现额外返回 `published_at`。
- [x] Translation profile payload：`TranslationProfileVersionService._build_payload()` 只写入 profile id、版本、base_version、目标语言、领域、prompt 版本、模型和分批阈值；不写 secret。
- [x] Segment trace artifact：`translation_runtime.build_translation_trace_payload()` 输出 `schema_version/job_id/translation_profile/target_language/domain/prompt_version/model/batch_count/segments`，segment 含 `source_text/model_input_text/ai_translation_text/final_text`。

**名词层“现状 -> 变化”逐项核对**：

- [x] `ResourceVersionService`：Translation Profile 通过 `resource_type="translation_profile"` 写 draft / published / default pointer。
- [x] `ConversionRequest`：已增加 `job_id`、`translation_profile`、profile 派生配置字段和 `translation_trace_output`。
- [x] `JobFile` / artifact 合同：已支持 `translation_trace` file type 和 `translation-trace` download alias。

**流程图核对**：

- [x] `PUT draft -> publish -> set-default/rollback`：落点为 `app/api/v1/routers/translation_profiles.py` 与 `app/services/translation_profiles/versioning_service.py`。
- [x] `job stage convert en2zh -> default profile -> conversion request`：落点为 `app/services/jobs/stage.py` 与 `app/conversion/entrypoint.py`。
- [x] `write request.json + trace.json -> register artifacts`：落点为 `app/conversion/runtime_runner.py`、`app/conversion/runtime/translation_runtime.py`、`app/services/jobs/stage.py` 和 `app/services/jobs/artifacts.py`。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] Translation Profile API 已增加 list/detail/draft/update/publish/set-default/rollback，复用资源版本底座。
- [x] `en2zh` job 生成 `translation_trace` artifact，保存 source、模型输入、AI 初译、final text、模型和 prompt 版本。
- [x] MySQL resource service 可用时，`en2zh` 执行前优先读取默认 published Translation Profile；不可用或无默认时保持 settings 路径。
- [x] 原有 `translation_request` artifact 保持，并新增 `translation_trace`，没有替换旧产物。

**明确不做逐项核对**：

- [x] 未做人工校对 UI，未引入人工审核状态。
- [x] 未修改 jobs 创建 payload；`rg translation_profile_id|translation_profile_version app/api/v1/routers/jobs_ingest.py app/schemas/jobs.py app/core/job_models.py docs/api/jobs.md` 无命中。
- [x] 未把 `translation_profile_id/version` 写入 `JobRecord`；`JobRecord` 仍只保存 `translation_mode` 等现有字段。
- [x] Profile payload / trace 不保存 OpenAI API key、secret header 或完整 prompt 文本；实现仅传递 profile id、version、snapshot_hash 到 trace。
- [x] 未新增 `zh2en` / `zh2ru`，jobs ingest 仍只接受 `direct` / `en2zh`。
- [x] 未改 MinerU 解析、Word 渲染、术语规则或模板 Profile 合同。

**关键决策落地**：

- [x] 决策 1：复用 `ResourceVersionService`，无翻译专用状态机。
- [x] 决策 2：默认 Translation Profile 只影响 `en2zh` 执行时配置；job snapshot 仍留给后续 feature。
- [x] 决策 3：profile payload 不存 secret；测试断言 `records[version].payload` 不含 `api_key`。
- [x] 决策 4：Segment trace 是 job artifact；通过 `translation_trace` file type 和 `translation-trace` alias 暴露。

**编排层变化核对**：

- [x] `TranslationProfileVersionService`：负责默认 profile、draft 更新、版本号生成、publish、set-default 和 rollback。
- [x] `/api/v1/translation-profiles` router：写接口 admin-only，缺 MySQL resource service 时返回 503。
- [x] `JobStageService`：仅 `job.translation_mode == "en2zh"` 时解析默认 profile。
- [x] `translation_runtime`：新增 trace payload 构建 / 写文件函数，未改变 `apply_translation_responses()` 调用语义。

**挂载点反向核对**：

- [x] 挂载点清单均有实际代码落点：service、router、schemas、stage、translation runtime、jobs artifact 合同。
- [x] grep 命中均落在方案清单范围内；额外命中为 docs / tests / OpenAPI 导出，不构成未记录生产挂载点。
- [x] 拔除沙盘推演：移除 router 注册、runtime service 挂载、stage resolver、conversion request 字段、trace runtime 函数和 artifact spec 后，功能可整体卸载；残留为 docs / tests / API 文档需同步删除。

## 3. 验收场景核对

- [x] MySQL resource mode 下 `PUT /api/v1/translation-profiles/electronics-en2zh/draft` 保存成功，snapshot_hash 可见，不含 API key。
  - 证据：`tests.test_fastapi_jobs_backend.test_translation_profile_versioning_overrides_en2zh_request_and_records_trace`
  - 结果：通过。
- [x] 已有 draft publish `make_default=true` 后生成 `YYYY.MM.DD-N` published version，默认指针指向该版本。
  - 证据：同一集成测试断言 publish response `is_default` 和 detail `default_version`。
  - 结果：通过。
- [x] 两个 published profile 的 set-default / rollback 只切默认指针，不改历史 payload。
  - 证据：`TranslationProfileVersionService.set_default_version()` / `rollback()` 只调用 resource version default pointer 操作；底座测试覆盖默认指针语义。
  - 结果：通过。
- [x] file backend profile 写接口返回 503，现有 en2zh settings 路径仍可执行。
  - 证据：router 统一 `_require_translation_profile_service()` 返回 503；`test_upload_en2zh_preserves_conversion_request_options_and_translation_artifact` 覆盖 settings 路径。
  - 结果：通过。
- [x] 默认 published profile + `translation_mode=en2zh` job 使用 profile 中的 model / prompt / batch 参数。
  - 证据：集成测试断言 `request.translation_model/translation_prompt_version/translation_max_pages/translation_max_chars` 被 profile 覆盖。
  - 结果：通过。
- [x] `translation_mode=en2zh` job 完成后 files 列表包含 `translation_request`、`translation_trace`、`result_docx`，trace 记录 source、AI 初译和 final text。
  - 证据：后端集成测试断言 files 顺序；runtime characterization 测试断言 trace segment 字段。
  - 结果：通过。
- [x] direct job 不生成 translation trace，也不解析默认 Translation Profile。
  - 证据：stage 仅 `en2zh` 调用 resolver；entrypoint 仅 `en2zh` 设置 `translation_trace_output`。
  - 结果：通过。
- [x] 不修改 jobs 创建 payload，不写 `translation_profile_id/version` 到 `JobRecord`。
  - 证据：`jobs_ingest.py` 的 `ConversionOptions` 仍只含模板、翻译模式、文档语言、页眉页脚；`rg` 反查无 job payload 命中。
  - 结果：通过。

## 4. 术语一致性

- `Translation Profile` / `translation_profile`：代码命中集中在 service、schema、router、runtime wiring、docs 和 tests，命名与方案一致。
- `electronics-en2zh`：作为 MVP 默认 profile id，命中 service、docs 和 tests，命名一致。
- `Segment Trace` / `translation_trace` / `translation-trace`：file type 使用下划线，download alias 使用短横线，符合现有 artifact alias 风格。
- 防冲突：`translation_profile_id/version` 未进入 jobs 创建 payload 或 `JobRecord`；`api_key/default_headers/secret` 未进入 Translation Profile payload / trace runtime。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已补入 Translation Profile / Segment Trace 核心术语、FastAPI 路由、物理结构、resource version 接入、artifact 清单和边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已补入 translation-profiles router/service、Translation Profile 版本管理流程、API 合同、artifact 合同、翻译能力和已知边界。
- [x] `.codestable/architecture/conversion-flow.md`：已补入 profile 派生 TranslationConfig 与 `translation_trace` 写入流程。
- [x] `.codestable/attention.md`：本 feature 未暴露需要补入 attention.md 的新环境 / 命令 / 工作流类内容。

## 6. requirement 回写

- [x] `requirement=fastapi-backend-productization` 指向 current req，且本次新增用户可见管理 API 与 artifact 行为，已更新 `.codestable/requirements/fastapi-backend-productization.md`。
- [x] 已补入翻译配置维护者用户故事、`translation-profiles` 解决方案、`translation_trace` artifact 能力、当前边界和变更日志。
- [x] 保留原始产品化愿景；只追加本次已落地能力，不覆盖历史叙述。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `translation-profile-and-segment-trace` 已从 `in-progress` 改为 `done`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 中第 6 条状态已同步为 `done`。
- [x] roadmap 观察项已同步为 Translation Profile API 与 `translation_trace` artifact 已落地，job 资源快照仍留给 `job-resource-snapshot-binding`。

## 8. attention.md 候选盘点

- [x] 无候选：本 feature 未暴露新的解释器、服务启动、环境变量、路径或命令陷阱。既有测试解释器要求已在 `.codestable/attention.md` 中记录。

## 9. 遗留

- 后续优化点：
  - `job-resource-snapshot-binding`：任务创建时绑定 template / term-rule / translation profile 的不可变 published version。
  - 后续人工校对工作台可消费 `translation_trace`，但本轮不引入 UI 或审核状态。
- 已知限制：
  - Translation Profile MVP 只支持 `electronics-en2zh`。
  - file/sqlite backend 不启用 `/translation-profiles` 管理接口；`en2zh` 仍可走 settings / `.env`。
  - trace 不保存完整 prompt 文本或 secret，无法单独作为完整 LLM 调用复现包。
- 实现阶段顺手发现：
  - 方案记录的现存差异仍存在：`translation_request_output` 帮助文案和实际行为不完全一致，当前写 request 后仍继续调用 LLM；本轮未修复。

## 验证记录

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning tests.test_translation_runtime_characterization tests.test_fastapi_jobs_backend`：76 tests passed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_input_adapter_characterization tests.test_job_artifact_contract`：26 tests passed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`：2 tests passed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`：OpenAPI check ok，changed False，path_count 46，schema_count 67。
- [x] YAML validation：feature checklist 与 roadmap items 均可解析。
