---
doc_type: feature-acceptance
feature: 2026-05-28-storage-backend-migration-plan
status: ready-for-review
accepted_at: 2026-05-28
design: .codestable/features/2026-05-28-storage-backend-migration-plan/storage-backend-migration-plan-design.md
roadmap: backend-worker-storage-evolution
roadmap_item: storage-backend-migration-plan
tags: [backend, jobs, storage, migration, acceptance]
---

# Storage Backend Migration Plan 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-28
> 关联方案 doc：`.codestable/features/2026-05-28-storage-backend-migration-plan/storage-backend-migration-plan-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：
- [x] `DatabaseJobRepository`：实现 job snapshot、events、files、stage messages 的最小协议，落点为 `app/repositories/database_job_repository.py`。
- [x] `ArtifactStorageProtocol`：定义 `build_registered_file()` 和 `resolve_download()`，下载结果通过 `DownloadArtifact` 表达 `local_path` / `stream` / `redirect`。
- [x] `ObjectArtifactStorageAdapter`：以本地对象目录模拟 object storage，保持 `JobFile.path` 不变并回填 `storage_backend=object`、`object_key=jobs/{job_id}/{logical_path}`。

**名词层“现状 -> 变化”逐项核对**：
- [x] `JobFile.path` 仍是 job 内逻辑路径，未变成本地绝对路径、object key 或 public URL。
- [x] `storage_backend/object_key/public_url` 保持兼容投影字段口径，下载主合同仍是 `download_url`。
- [x] `parsed_result_package` 已纳入 artifact 合同与统一下载入口，但产品默认交付物仍是 `result_docx`。

**流程图核对**：
- [x] metadata shadow copy、metadata backend switch、artifact shadow upload、artifact adapter switch、worker/queue 单独评估均有落点或明确结论。

## 2. 行为与决策核对

**需求摘要逐项验证**：
- [x] local file 迁移前校验已实现：`scripts/ops/check_local_file_storage_integrity.py` 只读报告 job、files、events、stage messages 和缺失 artifact。
- [x] database metadata adapter 已实现：`DatabaseJobRepository` 支持 file/database 双 adapter 下的 jobs 主链测试。
- [x] metadata shadow copy 已实现：`scripts/ops/shadow_copy_metadata_to_database.py` 可重复复制并校验 snapshot、events、files、stage messages。
- [x] artifact 下载合同已扩展：`download/{artifact_alias}` 可根据 `DownloadArtifact` 返回本地文件、流或重定向。
- [x] artifact shadow upload 已实现：`scripts/ops/shadow_upload_artifacts_to_object_storage.py` 回填 object metadata，并保留 local fallback。
- [x] worker / queue 已独立评估：本轮继续单体单实例，不引入 Redis、Celery、RQ、heartbeat、lease 或队列。

**明确不做逐项核对**：
- [x] 未选择具体 DB/S3/OSS 厂商；当前 database 为 sqlite 最小 adapter，object storage 为本地对象目录 adapter。
- [x] 未引入 Redis / Celery / RQ / 独立 worker。
- [x] 未删除或改写当前 file backend 数据。
- [x] 未把 events 改成 event sourcing；反向 grep 命中仅出现在范围说明和审计轨迹文档。
- [x] 未改变 HTTP API path、status 枚举或 events 审计语义。

**关键决策落地**：
- [x] 先 metadata 后 artifact：代码和脚本按 metadata adapter / shadow copy / switch，再 artifact download contract / shadow upload / switch 的顺序收口。
- [x] 第一轮 metadata 不默认双写：默认 runtime 仍为 file，database 需要显式配置切换。
- [x] readiness 是观测面：`health/ready` 报告 `configured_repository_backend`、`effective_repository_backend`、`stage_message_store`、`artifact_storage` 和 stage spool 计数，不自动修复 failed message。

**挂载点反向核对**：
- [x] metadata adapter 选择只落在 runtime 组装与测试构造路径。
- [x] repository ports 只落在 `app/repositories/protocols.py` 及 jobs service 依赖面。
- [x] artifact storage adapter 只落在 jobs 写侧、下载 router、lifecycle cleanup 和 migration 脚本。
- [x] readiness 字段只落在 `HealthService`、docs 和测试。
- [x] migration 脚本落在 `scripts/ops/`，没有混入 request 主链。

**拔除沙盘推演**：
- [x] 若要回退 database metadata adapter，可移除 `DatabaseJobRepository`、runtime database 选择分支、metadata shadow copy 脚本和对应测试；file backend 主链仍保留。
- [x] 若要回退 local object adapter，可移除 `ObjectArtifactStorageAdapter`、artifact shadow upload 脚本和 `local_object` 配置分支；local file adapter 和 `download_url` 合同仍保留。

## 3. 验收场景核对

- [x] **S1 local file 数据完整性只读校验**：由 `tests.test_local_file_storage_integrity_check` 覆盖，验证缺失 artifact 和不可迁移项报告。
- [x] **S2 metadata shadow copy 幂等**：由 `tests.test_metadata_shadow_copy` 覆盖，重复执行不重复 events/files/stage messages。
- [x] **S3 database backend switch**：由 `tests.test_database_job_repository` 覆盖，查询、retry、callback、replay 和 readiness 在 database backend 下可用。
- [x] **S4 artifact download contract**：由 `tests.test_job_artifact_contract` 和 `tests.test_fastapi_jobs_backend` 覆盖本地文件、stream、redirect 下载结果。
- [x] **S5 artifact shadow upload**：由 `tests.test_artifact_shadow_upload` 覆盖 `source_pdf`、`parsed_result_package`、`result_docx` 的 object_key 回填和 local fallback。
- [x] **S6 worker / queue 不引入**：由 `worker-queue-independent-evaluation.md` 明确结论，反向 grep 只命中范围说明和未来边界。

实际验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_job_workflow_policy tests.test_job_artifact_contract tests.test_database_job_repository tests.test_local_file_storage_integrity_check tests.test_metadata_shadow_copy tests.test_artifact_shadow_upload
```

结果：67 tests OK。该 conda 环境启动时仍出现已知 `_distutils_hack` warning，不影响测试结果。

## 4. 术语一致性

- `metadata store`：代码中对应 repository protocols、`FileJobRepository` 和 `DatabaseJobRepository`。
- `artifact storage`：代码中对应 `ArtifactStorageProtocol`、`LocalArtifactStorageAdapter` 和 `ObjectArtifactStorageAdapter`。
- `logical path`：`JobFile.path` 仍保持 `input/source.pdf`、`input/parsed-result.zip`、`output/result.docx` 这类 job 内路径。
- `object_key`：仅作为 object adapter 内部定位字段，未替代 `download_url`。
- `events`：仍定位为审计轨迹，不作为 job snapshot 重建来源。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已更新 FastAPI 当前能力，补入 `parsed -> completed`、`parsed_result_package`、database metadata adapter、local object artifact adapter 和 worker/queue 未引入边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已更新 callback 在线后处理流程、artifact 合同、readiness 字段和已知边界。
- [x] `.codestable/roadmap/backend-worker-storage-evolution/backend-worker-storage-evolution-roadmap.md`：已同步 storage migration 完成状态与 worker/queue 独立评估结论。
- [x] `.codestable/attention.md`：未发现需要每次启动都必须知道的新环境约束；保持不变。

## 6. requirement 回写

- [x] `fastapi-backend-productization` 为 current requirement，本次更新了当前能力边界：PDF 在线链路已可从 callback 自动到 completed；storage 仍默认 file/local，但已有 database/local_object 最小 adapter 与 shadow 能力。
- [x] `.codestable/requirements/VISION.md` 已同步 `last_reviewed` 和当前 requirement 链接路径。

## 7. roadmap 回写

- [x] `backend-worker-storage-evolution-items.yaml` 中 `storage-backend-migration-plan` 已标记为 `done`。
- [x] `backend-worker-storage-evolution-roadmap.md` 中对应子 feature 已标记为 `done`，备注说明 metadata/artifact 最小迁移边界已完成，worker/queue 未来另起 roadmap。
- [x] YAML/frontmatter 解析通过。

## 8. attention.md 候选盘点

- [x] 无候选。本 feature 未暴露新的“每个后续 feature 都会重复踩”的环境 / 命令 / 路径约束。

## 9. 遗留

- 后续优化点：真实生产数据迁移需要另起 runbook 或实施 feature，明确维护窗口、备份、抽样校验和回滚保留期。
- 已知限制：当前 database adapter 是 sqlite 最小实现，不代表已选择 MySQL / PostgreSQL；当前 object adapter 是本地对象目录，不代表已接入 S3 / OSS。
- 已知限制：当前仍不引入独立 worker / queue、多实例 heartbeat、lease、visibility timeout 或 dead letter。
- 已知限制：callback 丢失后的主动远端结果查询恢复仍未实现。
- 用户终审：待用户确认。
