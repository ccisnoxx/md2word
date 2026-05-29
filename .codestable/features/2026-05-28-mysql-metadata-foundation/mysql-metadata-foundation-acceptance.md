---
doc_type: feature-acceptance
feature: 2026-05-28-mysql-metadata-foundation
status: ready-for-review
accepted_at: 2026-05-28
design: .codestable/features/2026-05-28-mysql-metadata-foundation/mysql-metadata-foundation-design.md
roadmap: backend-productization-implementation
roadmap_item: mysql-metadata-foundation
tags: [backend, mysql, metadata, jobs, acceptance]
---

# MySQL Metadata Foundation 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-28
> 关联方案 doc：`.codestable/features/2026-05-28-mysql-metadata-foundation/mysql-metadata-foundation-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：
- [x] `MysqlJobRepository` 已实现 job snapshot、events、files、stage message store protocols，落点为 `app/repositories/mysql_job_repository.py`。
- [x] `JOBS_REPOSITORY_BACKEND=mysql` 已接入 `Settings` 和 `build_runtime()`，落点为 `app/core/config.py`、`app/main.py`。
- [x] MySQL 基础表覆盖 `jobs`、`job_events`、`job_files`、`stage_messages` 和 `resource_versions`，由 `MYSQL_SCHEMA_STATEMENTS` bootstrap。
- [x] readiness 可报告 `configured_repository_backend=mysql`、`effective_repository_backend=mysql`、`stage_message_store=mysql`，由 `tests.test_database_job_repository` 覆盖。

**名词层“现状 -> 变化”逐项核对**：
- [x] `file` 默认值保留，`database` 继续表示 sqlite，`mysql` 是显式新增 backend。
- [x] `metadata payload` 继续以 Pydantic JSON 保存；未把所有 job 字段拆成 MySQL 业务查询列。
- [x] `resource_versions` 只作为基础表存在；未实现 template / term-rule / translation 发布、默认指针或回滚业务流。
- [x] `local artifact storage` 边界保留；MySQL 只保存 artifact metadata，不保存 PDF、DOCX、MinerU zip 二进制。

**流程图核对**：
- [x] `Settings.jobs_repository_backend -> MysqlJobRepository -> jobs/events/files/stage_messages -> jobs services protocols -> health/ready` 图中节点均有代码落点。

## 2. 行为与决策核对

**需求摘要逐项验证**：
- [x] MySQL adapter 能创建、更新、查询 job，追加 events，登记 files，写入和 replay stage messages；证据为 `test_metadata_repository_contract_matches_file_backend`。
- [x] PDF / MinerU / DOCX fake 主链能在 `mysql` backend 替身下跑到 `completed`；证据为 `test_jobs_api_pdf_callback_flow_uses_mysql_repository`。
- [x] runtime 在 `mysql` 配置下把 repository、job_repository、stage_message_store 指向同一个 MySQL adapter；证据为 `test_build_runtime_switches_to_mysql_repository_and_readiness`。
- [x] readiness 在 MySQL 模式下不要求 `data/stage_messages` 目录作为 file spool；`stage_spool_dir_exists` 表示数据库内 store 可用。

**明确不做逐项核对**：
- [x] 未把 PDF / DOCX / MinerU zip 写入 MySQL；`JobFile.path` 仍是逻辑路径，artifact 二进制仍由 artifact storage adapter 管理。
- [x] 未新增真实历史数据迁移脚本；file -> MySQL migration 留给 operations feature。
- [x] 未引入 Redis、Celery、RQ、跨进程 lease 或多 worker 抢占锁。
- [x] 未实现 resource version 的发布 / 默认 / 回滚业务流。
- [x] 未引入 Alembic / SQLAlchemy；本轮只做轻量 schema bootstrap。
- [x] 未改变 HTTP API path、job status 枚举或 artifact 下载合同。

**关键决策落地**：
- [x] 新增 `mysql` backend，不复用 `database` 名称：`Settings.jobs_repository_backend` 已为 `Literal["file", "database", "mysql"]`。
- [x] MySQL adapter 复用 existing protocols：jobs services 仍从 runtime 注入 repository / stage message store，没有 MySQL 专属 service 分支。
- [x] JSON payload 作为权威快照：MySQL 表只有必要索引列 + `payload`，业务字段仍由 Pydantic models 解析。
- [x] `PyMySQL` 为可选运行依赖：`requirements.txt` 已加入 `PyMySQL>=1.1,<2`；未安装时配置 `mysql` 会启动失败，不回退 file。
- [x] `resource_versions` 只建基础表：无 service / router / API 暴露。

**挂载点反向核对**：
- [x] Metadata backend 配置：`app/core/config.py`。
- [x] Runtime repository 选择：`app/main.py::_build_job_metadata_repository()`。
- [x] Repository adapter：`app/repositories/mysql_job_repository.py`。
- [x] Readiness metadata store 观测：`app/services/health_service.py`。
- [x] 测试运行时：`tests/test_fastapi_jobs_backend.py::build_test_runtime()` 已支持通过 `repository_factory` 注入 mysql 替身。
- [x] grep 反向核对：`MysqlJobRepository`、`JOBS_REPOSITORY_BACKEND=mysql`、`resource_versions`、`PyMySQL` 命中均在 design、adapter、runtime、tests 和文档范围内。

**拔除沙盘推演**：
- [x] 若要拔除 MySQL backend，可移除 `mysql_job_repository.py`、`Settings.jobs_mysql_*`、`build_runtime()` 的 `mysql` 分支、requirements 中 `PyMySQL` 和相关测试；file/sqlite 主链仍保留。
- [x] 若要拔除 resource_versions 基础表，可从 `MYSQL_SCHEMA_STATEMENTS` 删除该表；当前没有业务代码依赖它，不影响 jobs 主链。

## 3. 验收场景核对

- [x] **S1**：`JOBS_REPOSITORY_BACKEND=mysql` 且连接可用；触发 `build_runtime()`；期望 runtime.repository 为 MySQL adapter，readiness 显示 `mysql`。
  - 证据来源：单测 fake MySQL connection。
  - 结果：通过。
- [x] **S2**：source PDF job；触发 create/update/list events/files/stage messages；期望 MySQL adapter 与 file/sqlite repository contract 行为一致。
  - 证据来源：`tests.test_database_job_repository.DatabaseJobRepositoryTests.test_metadata_repository_contract_matches_file_backend`。
  - 结果：通过。
- [x] **S3**：pending/running/failed stage messages；触发 `replay_pending()`；期望只 replay pending/running，不自动 replay failed。
  - 证据来源：repository contract 和 replay 测试。
  - 结果：通过。
- [x] **S4**：已登记 `JobFile(path="input/source.pdf")`；触发 MySQL 持久化和查询；期望 `path` 仍是逻辑路径。
  - 证据来源：repository contract 中 `source_pdf` 替换和查询断言。
  - 结果：通过。
- [x] **S5**：缺少 PyMySQL 依赖；触发配置 `mysql` backend；期望启动明确失败，不悄悄回退 file。
  - 证据来源：`MysqlJobRepository._build_pymysql_connection()` 在 `pymysql is None` 时抛出 `RuntimeError`。
  - 结果：通过代码审查；当前测试不启动真实 MySQL。
- [x] **反向核对**：HTTP API、status 枚举、events 语义、artifact 下载合同保持不变。
  - 证据来源：diff review + targeted tests。
  - 结果：通过。

实际验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/repositories/mysql_job_repository.py app/core/config.py app/main.py app/services/health_service.py tests/test_database_job_repository.py
python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-28-mysql-metadata-foundation/mysql-metadata-foundation-checklist.yaml --yaml-only
python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only
git diff --check
```

结果：通过。该 conda 环境启动时仍出现已有 `_distutils_hack` warning，不影响测试结果。

## 4. 术语一致性

- `MySQL metadata store`：代码中对应 `MysqlJobRepository`、`MysqlJobRepositoryConfig` 和 `JOBS_REPOSITORY_BACKEND=mysql`。
- `sqlite database adapter`：代码中仍对应 `DatabaseJobRepository` 和 `JOBS_REPOSITORY_BACKEND=database`。
- `metadata payload`：MySQL adapter 通过 `model_dump(mode="json")` / `model_validate_json()` 保存和恢复。
- `resource version base table`：只在 `MYSQL_SCHEMA_STATEMENTS` 中出现为 `resource_versions`。
- `local artifact storage`：代码中 artifact adapter 独立存在，MySQL adapter 未处理二进制文件。
- 防冲突：`database` 没被改成泛指 MySQL；文档和配置均区分 sqlite `database` 与 MySQL `mysql`。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已补入 metadata store 术语、MySQL jobs metadata / stage messages / resource_versions 基础表、artifact 二进制独立存储、真实 MySQL smoke 和迁移体系未完成的边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已补入 `mysql_job_repository.py`、三种 metadata backend、MySQL readiness 口径和已知边界。
- [x] `docs/api/health.md`、`docs/dev/runtime-observability-and-health.md`、`docs/runbook.md`：已同步 `mysql` readiness 值，避免公开健康检查文档只写到 sqlite。
- [x] `.codestable/attention.md`：未直接修改；本阶段只在第 8 节列候选。

## 6. requirement 回写

- [x] `fastapi-backend-productization` 为 current requirement，本次实际更新用户故事、解决方案和边界：
  - 生产部署维护者可显式使用 MySQL metadata store。
  - `FastAPI + BackgroundTasks + metadata repository + conversion library` 替代只写 file repository 的旧描述。
  - 边界从“不包含 MySQL”更新为“包含 MySQL adapter，但不包含 PostgreSQL、真实 MySQL smoke、历史迁移 runbook 或 Alembic / SQLAlchemy 体系”。
- [x] 变更日志已追加本次 MySQL metadata store 能力。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `mysql-metadata-foundation` 已从 `in-progress` 改为 `done`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 第 5 节子 feature 清单已同步为 `done`，并填入 feature 目录。
- [x] roadmap 观察项已从“若实施 MySQL 需处理”更新为“轻量 adapter 已落地；SQLAlchemy / Alembic、真实 MySQL smoke、file -> MySQL 迁移 runbook 仍留给 operations feature”。

## 8. attention.md 候选盘点

- [ ] 候选 1：真实 MySQL 联调前需要先安装 `requirements.txt` 里的 `PyMySQL` 并配置 `JOBS_MYSQL_*`；当前自动化只用 fake MySQL connection 覆盖合同。建议如后续频繁做 MySQL feature，再通过 `cs-note` 归入“环境变量与凭证”或“测试”。

## 9. 遗留

- 后续优化点：真实 MySQL 服务 smoke、file -> MySQL 历史数据迁移 runbook、备份 / 回滚窗口、抽样校验策略，归 `operations-readiness-and-test-baseline` 或单独 migration feature。
- 已知限制：未引入 Alembic / SQLAlchemy，schema 仍由 adapter 轻量 bootstrap。
- 已知限制：`resource_versions` 只是基础表；默认指针、不可变发布版本、回滚和 service 查询协议由 `resource-versioning-foundation` 处理。
- 已知限制：仍保持单实例，不引入 Redis、Celery、RQ、多 worker 抢占锁或跨进程 lease。
- 用户终审：待用户确认。
