---
doc_type: feature-acceptance
feature: 2026-05-29-operations-readiness-and-test-baseline
status: passed
summary: 验收 operations readiness、JSON metrics、MySQL metadata migration baseline、release check、env/runbook 和测试 smoke 已按 design 落地，并完成 architecture / requirement / roadmap 回写
tags: [backend, operations, readiness, metrics, mysql, tests]
---

# Operations Readiness and Test Baseline 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-29-operations-readiness-and-test-baseline/operations-readiness-and-test-baseline-design.md`

## 1. 接口契约核对

- [x] `HealthMetricsResponse` 已在 `app/schemas/health.py` 定义，并通过 `app/schemas/api_v1.py` re-export。
- [x] `GET /api/v1/health/metrics` 已在 `app/api/v1/routers/health.py` 挂载，调用 `HealthService.build_metrics_response()`。
- [x] `/health/ready` 保持 `HealthReadyResponse` 兼容形状，只在 `dependency_checks` 中新增 artifact、disk、default resource version 和 MySQL schema bootstrap 字段。
- [x] `MysqlMetadataMigrationReport` 和 `shadow_copy_metadata_to_mysql()` 已在 `scripts/ops/shadow_copy_metadata_to_mysql.py` 定义，报告包含 source / target totals、target empty guard、mismatches 和 `ok`。
- [x] `ReleaseCheckReport` / `ReleaseCheckItem` 已在 `scripts/ops/check_release.py` 定义，聚合 OpenAPI snapshot 和 targeted unittest 分项。

## 2. 行为与决策核对

- [x] `health` router 继续承载 readiness / metrics；未新增 `ops` router。
- [x] `metrics` 是 JSON 运维计数，不是 Prometheus 格式，当前不引入外部监控依赖。
- [x] file -> MySQL migration 走离线脚本，不进入服务启动路径；默认拒绝写入非空目标。
- [x] release check 默认只跑本地 OpenAPI / unittest smoke，不依赖真实 MinerU、OpenAI 或公网。
- [x] `.env.example` 和 runbook 只提供占位与安全默认，没有真实 secret。
- [x] artifact 二进制仍由 artifact storage 管理，MySQL 只保存业务 metadata。

## 3. 验收场景核对

- [x] **S1 readiness 兼容扩展**
  - 证据：`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies` 覆盖旧字段保留和新增 `artifact_root_writable`、`artifact_disk_free_bytes`、默认资源版本、`mysql_schema_bootstrap_available`。

- [x] **S2 JSON metrics endpoint**
  - 证据：`test_health_metrics_reports_runtime_counters` 和 `test_health_metrics_reports_default_resource_versions_in_mysql_mode` 覆盖 metadata store、artifact storage、worker mode、job / stage / resource / audit counters。

- [x] **S3 MySQL migration baseline**
  - 证据：`tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_writes_mysql_and_validates_all_metadata` 覆盖空目标 copy + validate；`test_shadow_copy_to_mysql_refuses_non_empty_target_by_default` 覆盖非空目标拒绝。

- [x] **S4 release check 聚合**
  - 证据：`scripts/ops/check_release.py` 的默认 targets 覆盖 OpenAPI、health/metrics、metadata migration、job workflow、MySQL fake smoke 和 logging；最终运行结果 `ok: True`。

- [x] **S5 状态机与 smoke 覆盖**
  - 证据：release check 默认包含 `tests.test_database_job_repository.DatabaseJobRepositoryTests.test_jobs_api_pdf_callback_flow_uses_mysql_repository`、`test_build_runtime_switches_to_mysql_repository_and_readiness`、`tests.test_job_workflow_policy` 和 `tests.test_backend_logging`。

- [x] **S6 文档与环境基线**
  - 证据：`.env.example`、`docs/runbook.md`、`docs/api/health.md`、`docs/dev/runtime-observability-and-health.md`、`docs/dev/backend-local-minimal-env-and-commands.md`、`docs/api/manifest.yaml` 已同步 health metrics、MySQL migration、release check 和真实外部联调步骤。

- [x] **反向核对**
  - 未新增 Prometheus / external monitoring dependency。
  - 未引入 Alembic / SQLAlchemy ORM migration。
  - 未改变 artifact 二进制仍在 artifact storage 的边界。
  - 未新增审计查询 API、运维 UI、多实例 worker 锁或真实 artifact 删除。

## 4. 术语一致性

- `operations readiness`：design、architecture、docs 和代码中均指单实例生产化依赖状态，不代表自动修复。
- `metrics JSON`：设计和实现均为 `/api/v1/health/metrics` 的 JSON counters，不是 Prometheus。
- `MySQL migration baseline`：设计、脚本和 runbook 均限定为 file metadata -> 空 MySQL metadata shadow copy / validate，不是 Alembic 迁移体系。
- `release check`：设计、runbook 和脚本均指 `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`。
- `真实链路 smoke`：仍是 runbook 手工外部联调，不作为默认 release check 前置。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已补入 Operations readiness / Metrics JSON 核心术语、FastAPI 外部表面、物理结构、数据与状态和已知边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`
  - 已补入 health metrics API 合同、readiness 新字段、运维脚本、release check、runtime observability 和已知边界。
- [x] 方案第 4 节已补齐“与项目级架构文档的关系”，明确 acceptance 阶段需要回写的 architecture / requirement / roadmap 文档。

## 6. requirement 回写

- [x] `.codestable/requirements/fastapi-backend-productization.md` 已补入生产部署维护者故事。
- [x] “怎么解决”已补入 `/health/metrics`、readiness 扩展、MySQL metadata shadow copy / validate、release check 和 `.env.example` / runbook 基线。
- [x] “边界”已明确真实外部 MySQL smoke 仍按 runbook 手工执行，Alembic / ORM migration 和外部监控平台不在当前范围。
- [x] 变更日志已追加 Operations Readiness and Test Baseline。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `operations-readiness-and-test-baseline` 已从 `in-progress` 更新为 `done`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 第 5 节子 feature 状态已同步为 `done`。
- [x] roadmap 观察项已改为当前现状：operations baseline 已覆盖 `.env.example`、readiness/metrics、MySQL shadow copy / validate、release check 和运维文档；Prometheus、Alembic / ORM migration、多实例 worker 仍不在范围。
- [x] roadmap 变更日志已追加本 feature 完成验收回写记录。

## 8. attention.md 候选盘点

- [x] 已盘点：既有 `.codestable/attention.md` 已说明后端验证使用 `/Users/sc/miniconda3/envs/md2word/bin/python`，本 feature 不需要强制追加。
- [ ] 候选：后端 release / operations 变更收尾优先运行 `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`。该信息已写入 runbook，是否进入 attention 可由后续 `cs-note` 单独确认。

## 9. 遗留与验证记录

**遗留边界**：

- 真实外部 MySQL 服务 smoke 仍按 runbook 手工执行，默认 release check 使用 fake MySQL。
- 不接 Prometheus / Grafana / OpenTelemetry / ELK；如需外部监控，应另起 feature。
- 不引入 Alembic / SQLAlchemy migration；如需正式 schema migration 体系，应另走 roadmap / design。
- 不做多实例 worker lease、独立 queue、真实 artifact 删除或运维 UI。

**验证记录**：

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-29-operations-readiness-and-test-baseline/operations-readiness-and-test-baseline-checklist.yaml --yaml-only`
  - 结果：通过，1 passed / 0 failed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only`
  - 结果：通过，1 passed / 0 failed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`
  - 结果：`ok: True`；OpenAPI current，47 paths / 71 schemas；targeted unittest 9 targets，28 tests passed。
