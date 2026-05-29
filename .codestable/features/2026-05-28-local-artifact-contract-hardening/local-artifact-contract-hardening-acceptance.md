---
doc_type: feature-acceptance
feature: 2026-05-28-local-artifact-contract-hardening
status: ready-for-review
accepted_at: 2026-05-28
design: .codestable/features/2026-05-28-local-artifact-contract-hardening/local-artifact-contract-hardening-design.md
roadmap: backend-productization-implementation
roadmap_item: local-artifact-contract-hardening
tags: [backend, jobs, artifacts, local-storage, acceptance]
---

# Local Artifact Contract Hardening 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-28
> 关联方案 doc：`.codestable/features/2026-05-28-local-artifact-contract-hardening/local-artifact-contract-hardening-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `JobFile` 增加 `size_bytes: int | None = None` 和 `sha256: str | None = None`：已落在 `app/core/job_models.py`，旧 payload 缺字段时仍按默认值读取。
- [x] `JobFileResponse` 透出 `size_bytes` / `sha256`：已落在 `app/schemas/jobs.py`，`app/api/v1/routers/jobs_presenters.py` 从 `JobFile` 映射到 response。
- [x] `sha256` 使用 `sha256:<hex>`：`app/services/jobs/artifact_integrity.py` 的 `compute_artifact_fingerprint()` 统一生成带算法前缀的字符串。
- [x] retention dry-run candidate 增加 `storage_backend`、`path`、`object_key`、`size_bytes`、`sha256`：已落在 `app/services/jobs/artifact_retention.py`。

**名词层“现状 -> 变化”逐项核对**：

- [x] `JobFile`：从 logical path 合同扩展为 logical path + fingerprint 合同；旧记录兼容。
- [x] `ArtifactStorageProtocol` / `LocalArtifactStorageAdapter`：`build_registered_file()` 登记时调用 `attach_artifact_fingerprint()`，`resolve_download_path()` 默认调用 `validate_artifact_fingerprint()`。
- [x] `check_local_file_storage_integrity()`：保持只读，新增 `artifact_fingerprint_missing` warning、size mismatch 和 sha256 mismatch issue。
- [x] `ArtifactRetentionPlanner`：候选从 object-only 扩展为 local + object。

**流程图核对**：

- [x] `stage / command 生成本地文件 -> artifact_storage.build_registered_file()`：登记入口仍由 jobs services 使用 artifact storage adapter。
- [x] `计算 size_bytes + sha256 -> repository.upsert_file(JobFile)`：fingerprint 在 `JobFile` 入库前写入，repository 继续保存 JSON payload。
- [x] `GET /jobs/{job_id}/files 返回 fingerprint`：presenter 和 schema 已透出新字段。
- [x] `GET /jobs/{job_id}/download/{alias} -> 校验 size + sha256`：下载解析走 `artifact_storage.resolve_download()`，本地 path 在返回前校验。
- [x] `缺失或不匹配 -> 稳定 HTTP 错误`：`app/api/errors.py` 将缺失映射 404、路径错误映射 400、fingerprint mismatch 映射 409。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 新登记 artifact 持久化 `size_bytes` 和 `sha256`：`tests.test_job_artifact_contract` 与 `tests.test_fastapi_jobs_backend` 已覆盖。
- [x] 旧 `JobFile` 记录兼容：`test_legacy_job_file_without_fingerprint_remains_valid` 覆盖缺字段默认值。
- [x] 下载错误区分 alias / 未登记 / 缺失文件 / 路径越界 / fingerprint mismatch：下载错误映射测试覆盖 400 / 404 / 409，既有 alias 与未登记 artifact 测试继续通过。
- [x] 完整性检查只读并报告 mismatch：`tests.test_local_file_storage_integrity_check` 覆盖扫描前后文件树不变、size mismatch、sha256 mismatch 和 legacy warning。
- [x] retention 只做 dry-run：`tests.test_artifact_retention` 覆盖 local / object 候选和未到期过滤，代码未新增删除动作。

**明确不做逐项核对**：

- [x] 未引入新的 S3、OSS、MinIO 或外部对象存储能力；现有 object / S3 adapter 只跟随共享 `JobFile` 字段和 fallback 校验。
- [x] 未改变 `JobFile.path` 的 logical path 语义；下载前仍对 logical path 与 file type 预期路径做匹配。
- [x] 未把本地绝对路径放进 API response 或 fingerprint mismatch detail；测试断言 detail 不含 `runtime.settings.data_path`。
- [x] 未做旧数据强制迁移；缺少 fingerprint 只兼容读取或在完整性检查中报 warning。
- [x] 未执行真实删除；retention 输出 dry-run candidate。
- [x] 未改变 DOCX 渲染、MinerU callback、模板或术语规则业务语义。

**关键决策落地**：

- [x] fingerprint 是 `JobFile` 合同的一部分：字段在核心模型、schema、presenter、OpenAPI 和 docs 中同步。
- [x] hash 使用 `sha256:<hex>`：计算模块统一加前缀，测试断言前缀。
- [x] 下载错误保持 `{"detail": ...}` 外形：HTTP error mapping 保持 FastAPI 默认 detail 结构。
- [x] retention 先扩 dry-run：planner 只生成候选报告，没有 delete API。
- [x] object / S3 adapter 不扩能力：只补本地 fallback / 对象本地副本的 fingerprint 校验，redirect 模式不强行读取远端内容。

**挂载点反向核对**：

- [x] `JobFile` / `JobFileResponse`：挂载点仅限 `app/core/job_models.py`、`app/schemas/jobs.py`、`app/api/v1/routers/jobs_presenters.py`、OpenAPI 和 API 文档。
- [x] `ArtifactStorageProtocol.build_registered_file()`：挂载点集中在 `app/services/jobs/artifact_storage.py` 和现有 object adapter 复用路径。
- [x] `download_artifact` HTTP 映射：挂载点集中在 `app/api/errors.py` 与 jobs query 下载调用。
- [x] `check_local_file_storage_integrity.py`：只读脚本挂载点已覆盖。
- [x] `ArtifactRetentionPlanner`：dry-run 候选挂载点已覆盖。
- [x] 文档挂载点：`docs/api/jobs.md`、`docs/runbook.md`、`docs/api/openapi.json` 已更新。
- [x] 反向核查：`rg "size_bytes|sha256|ArtifactFingerprint|fingerprint|ArtifactRetention|check_local_file_storage_integrity|resolve_download_path|ArtifactFingerprintMismatch" app scripts tests docs .codestable/features/2026-05-28-local-artifact-contract-hardening` 命中均落在设计清单范围内；模板元数据已有 `sha256` 属既有能力，不属于本 feature 冲突。
- [x] 拔除沙盘推演：逆向删除 `artifact_integrity.py`、`JobFile` / `JobFileResponse` 字段、adapter 调用、错误映射、完整性检查扩展、retention candidate 字段和文档更新即可移除本 feature；无额外隐藏挂载点。

## 3. 验收场景核对

- [x] **S1 新登记 local artifact 带 fingerprint**
  - 证据来源：`tests.test_fastapi_jobs_backend` 上传 zip 主链测试、`tests.test_job_artifact_contract`
  - 结果：通过；`files` 中每个新登记 artifact 的 `size_bytes > 0` 且 `sha256` 以 `sha256:` 开头。
- [x] **S2 旧 JobFile 记录兼容**
  - 证据来源：`test_legacy_job_file_without_fingerprint_remains_valid`
  - 结果：通过；缺字段读取为 `None`。
- [x] **S3 缺失本地文件错误稳定**
  - 证据来源：`test_download_artifact_maps_storage_errors`
  - 结果：通过；`FileNotFoundError` 映射 404 且 detail 外形稳定。
- [x] **S4 路径非法仍是 bad request**
  - 证据来源：`test_download_artifact_maps_storage_errors` 与 local adapter path 校验
  - 结果：通过；`ValueError` 映射 400。
- [x] **S5 fingerprint mismatch 拒绝下载**
  - 证据来源：`test_download_artifact_rejects_fingerprint_mismatch_without_absolute_path`
  - 结果：通过；返回 409，detail 包含 `file_type` 和 logical path，不含服务端 data path。
- [x] **S6 完整性检查只读并报告 mismatch**
  - 证据来源：`test_reports_fingerprint_mismatches_and_legacy_warning`
  - 结果：通过；扫描前后文件树一致，报告 size / sha256 mismatch 和 legacy warning。
- [x] **S7 retention dry-run 覆盖 local artifact**
  - 证据来源：`tests.test_artifact_retention`
  - 结果：通过；candidate 包含 local / object artifact 及 size / sha256，不删除文件。
- [x] **S8 明确不做反向核对**
  - 证据来源：代码 grep、diff review、测试套件
  - 结果：通过；未新增外部对象存储、未新增真实删除、未改变 logical path 语义，API detail 未暴露绝对路径。

已运行验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_artifact_contract tests.test_fastapi_jobs_backend tests.test_local_file_storage_integrity_check tests.test_artifact_retention tests.test_artifact_shadow_upload tests.test_s3_artifact_storage
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
python3 .codestable/tools/validate-yaml.py --file <design/checklist/acceptance/items/roadmap/requirement/architecture>
```

结果：66 个相关 unittest 通过；OpenAPI 已刷新；release check 返回 `ok: true`；本 feature 的 design / checklist / acceptance、roadmap items / 主文档、requirement 和 architecture frontmatter 均通过 YAML 校验。

## 4. 术语一致性

- `artifact fingerprint`：代码中使用 `ArtifactFingerprint`、`ArtifactFingerprintMismatch`、`attach_artifact_fingerprint()`、`validate_artifact_fingerprint()`，与方案术语一致。
- `size_bytes` / `sha256`：核心模型、API schema、presenter、retention candidate、完整性检查、docs 和 OpenAPI 口径一致。
- `logical path`：继续由 `JobFile.path` 表示；API 和错误详情使用 logical path，不使用本地绝对路径。
- `retention dry-run`：代码和文档均保持 dry-run 语义，没有把 planner 描述为删除器。
- 防冲突：MinerU callback 的 checksum 仍是 callback 安全校验，不与 `JobFile.sha256` artifact fingerprint 混用。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已归并 `JobFile` fingerprint 术语、FastAPI artifact 数据状态、下载诊断状态码、旧记录兼容和 retention dry-run 边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已归并 `artifact_storage.py`、`artifact_integrity.py`、`object_artifact_storage.py`、`artifact_retention.py` 的职责，并在产物合同中写明 fingerprint、400 / 404 / 409、object fallback 和 dry-run 输出。
- [x] `.codestable/attention.md`：本 feature 未直接写入；候选见第 8 节，等待用户决定是否走 `cs-note`。

归并判据：未读过 design 的读者只看 architecture，也能知道系统现在有 artifact fingerprint、下载前校验、只读完整性检查和 retention dry-run 形态。

## 6. requirement 回写

- [x] 方案 frontmatter 指向 `fastapi-backend-productization`，该 req 已是 `current`。
- [x] 本次改动改变了用户可见的 artifact 合同和下载诊断，因此已更新 `.codestable/requirements/fastapi-backend-productization.md`：
  - 用户故事补入维护者 / 集成方需要大小、hash 和下载诊断。
  - 解决方案补入 artifact fingerprint 与下载校验。
  - 边界补入不强制 backfill、不真实删除、不新增外部对象存储。
  - 变更日志补入 2026-05-28 local artifact contract hardening。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml`：`local-artifact-contract-hardening` 已从 `in-progress` 改为 `done`，feature 指向 `2026-05-28-local-artifact-contract-hardening`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md`：第 5 节子 feature 清单已同步为 done，主文档补入完成后的最小闭环和后续边界。
- [x] YAML 校验：见最终验证命令。

## 8. attention.md 候选盘点

- [x] 有候选，暂不擅自写入。
  - 候选 1：使用 `/Users/sc/miniconda3/envs/md2word/bin/python` 跑测试时，当前 conda 环境会打印 `_distutils_hack` / `distutils-precedence.pth` warning；本次命令退出码为 0，warning 不代表测试失败。若后续验收经常误判，可以通过 `cs-note` 追加到 `.codestable/attention.md` 的“测试”或“命令与脚本陷阱”分节。

## 9. 遗留

- 后续优化点：
  - 旧 `JobFile` 记录仍可能缺少 `size_bytes` / `sha256`；当前只兼容读取和 warning，不做强制 backfill。
  - 真实 artifact 删除、删除审计和恢复策略未纳入本 feature，应由后续 permission / operations feature 决定。
  - S3 redirect 模式不在重定向前读取远端对象内容；当前只保证登记 fingerprint 和本地 fallback 校验。
- 已知限制：
  - fingerprint mismatch 只能说明登记值与当前文件内容不一致，无法单独判断是篡改、并发写入还是登记时机问题；真实环境高频出现时应另起 issue。
- 顺手发现：
  - 无需新增 issue；本次发现的 conda warning 只作为 attention 候选登记。
