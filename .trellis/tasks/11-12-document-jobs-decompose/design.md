# 设计：document_jobs 拆解与应用层接口

## 1. 原则

- **纯迁移优先**：方法体逐字搬移，只改 `self.x` 的接收者与方法名；不在同一提交里顺带改逻辑。
- **依赖单向**：组件之间只沿下文的方向调用，不持有宿主或门面引用；共用依赖在构造时显式注入（沿用现有协作者约定）。
- **公开接口即契约**：跨对象调用一律使用无下划线方法；下划线方法只在定义它的类内部使用。
- **不加兼容层**：模块路径变化时直接更新所有导入方，不保留转发模块或再导出。

## 2. translation_execution 拆分

`app/domains/document_jobs/translation_execution.py` 变为包 `translation_execution/`，导入路径 `app.domains.document_jobs.translation_execution` 保持可用（由包的 `__init__` 导出门面与队列协议，这是门面的真实位置，不是转发层）。

### 2.1 组件与方法归属（现方法 → 新位置）

| 组件（模块） | 职责 | 迁入方法 |
|---|---|---|
| `TranslationPlanner`（`planning.py`） | 由不可变 source + 资源快照计算本代根计划 | `_build_expected_translation_plans`→`build_expected_plans`、`_read_translation_artifact`→`read_artifact`、`_read_translation_source`→`read_source`、`_translation_profile_for_job`、`_translation_profile_batch_limits`、`_resolve_term_version_for_job`、`_page_range_for_item_ids` |
| `TranslationIntegrityBinder`（`integrity_binding.py`） | 完整性绑定与批次译文回放 | `_translation_integrity_binding`→`binding`、`_load_batch_replacements`→`load_batch_replacements` |
| `TranslationArtifactStore`（`artifacts.py`） | 批次结果与译后 DocumentIR 的制品登记、发布 provenance | `_register_translation_batch_result`→`register_batch_result`、`_register_translated_document_ir_and_continue`→`register_translated_document_ir` |
| `TranslationGenerationCoordinator`（`generation.py`） | 租约回收、可运行批次投递、取消、代次快照/摘要、幂等收口 | `_reset_expired_translation_batch_leases`、`_enqueue_runnable_translation_batches`、`_next_runnable_translation_batch`、`_cancel_translation_batch`、`_get_translation_execution_snapshot`、`summarize_translation_generation`→`summarize`、`_finalize_translation_generation`→`finalize`、`_reconcile_translation_batch_atomic_rejection`→`reconcile_atomic_rejection`、预算判定 `_provider_call_budget_remaining*` |
| `TranslationBatchInstaller`（`installation.py`） | `ir_converting→translating` 转换、根集合原子安装、首轮投递 | `_ensure_translation_batches_and_enqueue`→`install_and_enqueue` |
| `TranslationFailureHandler`（`failure.py`） | 失败分类、重试/终态、拆分、原子拒绝对账、存储失败收口 | `_handle_translation_batch_failure`、`_should_split_translation_batch`、`_split_translation_batch`、`_fail_translation_batch_storage`→`fail_storage` |
| `TranslationBatchRunner`（`provider_call.py`） | 单批次执行：领取/租约、阶段事件、Provider 调用、审计、成功提交 | `execute_translation_batch`→`run`、`_claim_translation_batch`→`claim`、`_mark_translating_started`、`_translate_document_ir`、`_record_translation_audit_events` |
| `_support.py`（模块函数） | 无状态辅助 | `_TranslationBatchStorageError`、`_is_metadata_storage_error`、`_translation_batch_error_code`、`_recorder_*` |

`_finalize_translation_generation` 与 `_enqueue_runnable_translation_batches` 互相调用（原 1162 行与 1611/1627 行），因此二者同属 `generation.py`，不强行拆开。原子拒绝对账依赖快照、结论与 finalize，也归 generation。

`_translate_document_ir` 在全仓无调用方（旧同步翻译路径残留），拆分时删除。

**依赖持有**：测试与夹具约 60 处在构造后替换 `translation_batches.document_ir_translation_service` / `translation_batch_task_queue` 等属性。为保证替换对全部组件生效，依赖由可变的 `deps.TranslationExecutionDeps` 唯一持有，组件只经 `self.deps.<name>` 读取，测试改为替换 `translation_batches.deps.<name>`；门面不提供逐字段转发属性。

### 2.2 依赖方向（无环）

```
planning ← integrity_binding ← artifacts ← generation ← installation
                                   ↑            ↑
                    provider_call → failure ────┘
```

### 2.3 门面 `TranslationBatchExecution`（稳定接口）

构造签名与现在完全相同（`execution.py` 和 composition 不需要改装配方式），内部组装上述组件。公开方法：

| 方法 | 用途 | 替代的私有调用 |
|---|---|---|
| `start_generation(job, *, trace_id, source_document_ir=None)` | 安装根批次并投递；未传 source 时自行读取 | `execution.py` 中 `_read_translation_source` + `_ensure_translation_batches_and_enqueue` 的三处组合 |
| `finalize_generation(job_id, *, generation, trace_id)` | 幂等收口 | `_finalize_translation_generation` |
| `summarize_generation(job, batches=None)` | 权威代次结论（API 与执行共用） | `summarize_translation_generation` |
| `execute_translation_batch(batch_id, *, trace_id)` | Worker 入口，名称不变 | — |
| `set_translation_batch_task_queue(queue)` | 运行时注入队列，不变 | — |

组件作为门面的只读属性公开（`planner`、`runner`、`generation` 等），供测试精确驱动 `claim`、`build_expected_plans`；测试不再 patch 下划线方法。

## 3. router / 应用层接口

### 3.1 翻译批次视图

`use_cases/queries.py::get_translation_batch_snapshot` 改为返回 `TranslationBatchListView(job, batches, summary)`。`DocumentJobQueries` 构造时注入一个窄协议 `TranslationGenerationSummarizer`（只有 `summarize_generation(job, batches)`），由 composition 传入 `execution_service.translation_batches`。router 删除对 `document_job_execution_service` 的引用。

### 3.2 下载授权

当前 router 内的 `_build_download_token / _verify_download_token / _download_token_secret` 与“预览文件 TTL + S3 预签名”分支迁入 `use_cases/downloads.py`：

- `authorize_download(job_id, *, user, file_id) -> DownloadGrant`：包含 `job / file / policy / expires_at` 以及二选一的 `presigned_url` 或 `token`；内部完成 `record_download_authorized`。
- `resolve_token_download(job_id, *, token) -> TokenDownload`：校验令牌，返回 `redirect_url`（S3）或 `local_path`（已校验存在）。

router 保留：`request.url_for` + `_externalize_url`（HTTP 关注点）、`audit_service.record`（spec 规定 router 写用户动作审计）、响应映射。错误码与文案逐字保留。发布物下载令牌（`_PublicationDownloadClaims`）同样迁入 `use_cases/publication.py`。

### 3.3 router 拆分

沿用本域已有的 `*_router.py` 约定：

| 新文件 | 内容 |
|---|---|
| `router.py` | `router` 对象；任务 CRUD/列表/批量/生命周期/事件/文件/翻译批次/QA/表格引用；按原顺序 `include_router` 子路由 |
| `downloads_router.py` | `download-url`、`download` |
| `quality_review_router.py` | 质量、预览元数据、评审、评审块、新一代请求（现 `_quality_review_router` + `_new_generation_router`） |
| `publication_router.py` | 发布、发布记录、发布物下载 |
| `http_responses.py` | `_build_*_response`、批量响应、`_actor_from_user` |

注册顺序必须与现状一致（FastAPI 按注册顺序匹配，`/{job_id}` 等动态段对顺序敏感），以 OpenAPI 逐字节比对验收。

### 3.4 schemas 拆分

`schemas.py` 变为包 `schemas/`，模型逐字迁移：

| 模块 | 内容 |
|---|---|
| `jobs.py` | 创建/详情/列表/归档/删除/取消/事件/文件/可用动作/失败诊断/重试/克隆/批量/下载 URL |
| `translation.py` | 翻译批次、callback 摘要、翻译 QA、表格引用 |
| `config.py` | 配置摘要 |
| `incidents.py` | incident 队列与批量 |
| `quality_review.py` | `QualityReviewModel` 及其全部子类、新一代请求 |
| `publication.py` | 发布请求/记录/下载 |

所有导入方（约 19 个文件）直接改到具体子模块；`schemas/__init__.py` 为空。

## 4. 预览与渲染

- `preview.py` 保留 `DocumentJobPreviewService`（执行编排）；`_frozen_page_policy` 之后的证据读取函数（`read_current_preview_evidence`、`observe_current_preview`、`verified_current_preview_files`、`preview_download_ttl`、`current_page_mapping` 及其私有辅助）迁入 `preview_evidence.py`。
- `render_execution.py` 保留渲染编排与页级降级；占位图相关（`_ensure_placeholder_*`、`_read_current_placeholder_file`、`_get_placeholder_source_file`、`_load_placeholder_source`、`_read_placeholder_asset`、`_verify_placeholder_dependencies`）迁入 `render_placeholders.py::RenderPlaceholderSource`；结果文件查找与校验（`_get_document_ir_file`、`_get_existing_result_file`、`_validate_render_result_file`、`_validate_optional_block_anchors`、`_finish_*`）迁入 `render_result.py`。
- 实际落地：`render_placeholders.py::RenderPlaceholderSource`（含占位感知 `build_image_loader`）与 `render_result.py::WordResultFinalizer`（结果查找/认证与 `finish_*`），由 `WordRenderExecution` 构造为 `placeholders` / `results`；宿主调用 `rendering.render_and_save_word` 与 `rendering.placeholders.load_source`。`word_preview_service` 只被收尾使用，随 `results` 持有。`MinerUExecution` 公开 `run_parse`、`process_replayable_callback_messages`、`build_mineru_client`（默认客户端工厂，测试直接调用）。
- `preview_evidence.py` 承接存储异常归一化与全部证据读取；原 `DocumentJobPreviewService._descriptor` 改为证据模块函数 `artifact_descriptor`，消除证据→服务的反向依赖。被跨模块导入的 `_PreviewUnavailable`、`_read_artifact`、`_PreviewStorageError`、`_frozen_page_policy`、`_preview_storage_io` 改为公开名。

## 7. 实施中发现的既有缺陷

- `review_content.py::_load/list_blocks/get_block` 把 `DocumentJobQualityReview` 当作旧 `DocumentJobService` 使用，调用其上不存在的 `_ensure_job_not_deleted`、`_review_api_file`、`_file_belongs_to_job`、`_table_reference_snapshot`、`_list_table_references_snapshot`、`get_translation_batch_snapshot`（以及实例上的 `file_repository` / `file_upload_service` 需另核）。`GET /review/blocks`、`/review/blocks/{block_id}` 在 `_load` 第二行即会 `AttributeError`。自 `26706a5d`（use_cases 拆分）起存在；`test_document_job_review_hints` 以 `Mock(spec=[...])` 替代 service，未覆盖真实装配。
  - **已修复**：`DocumentJobQualityReview` 显式注入 `queries`、`table_references`；`review_content` 改经 `service.access.*`、`service.queries.get_translation_batch_snapshot`、`service.table_references.{table_reference_snapshot,list_table_references_snapshot}` 读取；复核用例与表格参考用例被跨模块调用的方法改为公开名（`review_api_job`、`review_cursor`、`finish_review_read`）。新增 `tests/test_document_job_review_blocks_api.py` 以真实 runtime 覆盖列表与详情（含表格分支）；翻译模式下的批次快照分支仅静态核对。
- `publication_provenance.py` 与 `use_cases/publication.py` 读取 `JobResourceSnapshotService` / renderer 的私有方法（`_load_snapshot_record`、`_materialize_*`、`_load_template_config`、`_resolve_asset_path`），属跨领域私有访问。
  - **已修复**：`JobResourceSnapshotService` 的 `load_snapshot_record`、`materialize_template`、`materialize_template_layout_config`、`materialize_term_rule_set` 改为公开方法（沿用已有公开 `materialize_translation_profile` 的形态，补充契约说明，行为不变）；`DocumentIRWordRenderer` 新增公开 `load_template_resources`（版式配置 + logo 路径），`render_to_result` 与发布来源核验共用，保证声明身份与实际渲染同一解析规则。
- **已修复**：`translation_execution/artifacts.py` 原调用翻译领域私有静态方法 `DocumentIRTranslationService._target_document_language`；改为直接使用已在手的公开模式规格 `spec.target_document_language`（对 en2zh/ru2zh/zh2en/zh2ru 四种模式逐一核对结果一致）。此后 `document_jobs`、`composition`、`workers` 中无跨对象私有调用。

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| 测试通过 `patch.object(collaborator, "_x")` 依赖方法位置 | 同步改测试到新组件公开方法；patch 目标随方法迁移，不保留旧名别名 |
| 构造后替换宿主属性的测试（spec 已说明需同时替换消费方） | 组件持有与门面相同的依赖对象；在 spec 中补充“需替换实际消费组件属性” |
| 路由顺序变化导致匹配差异 | OpenAPI 逐字节比对 + 原有 API 测试 |
| 并发/租约语义被搬移破坏 | 方法体逐字迁移；`test_translation_batch_failure_semantics`、`test_translation_batch_repository` 必跑 |

## 6. 待决策

1. **用例返回 HTTP 响应模型**：`use_cases/quality_review.py`、`translation_qa.py`、`read_model.py`、`review_content.py` 等直接构造 `schemas` 中的 Pydantic 响应。本任务只做包拆分，不改为独立 DTO——这些模型是严格的只读投影，再造一套 DTO 会成倍增加映射代码。若希望应用层完全不依赖 HTTP 模型，建议另开任务。
2. **执行顺序**：建议按 `translation_execution → router/use_cases → schemas → preview/render` 分四次提交，每次单独可验证、可回退。
