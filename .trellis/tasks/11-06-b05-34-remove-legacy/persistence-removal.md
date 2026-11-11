# 持久层、健康检查与旧运维工具清理

## 范围

已移除 file/SQLite/MySQL 的旧 JobSnapshotRepository、JobFileRepository、StageMessageStore，以及 factory 对应端口、导出与 file stage_messages 目录初始化。SQLite/MySQL 仅删除 jobs、job_files、stage_messages 的 CREATE 与旧阶段消息索引；保留 job_events 全部 DDL、三后端事件仓储和正式 document_jobs 事件实现，不新增/执行 DROP，不连接外部服务。

HealthService 及 health_schemas 仅移除旧 jobs 统计、旧 stage spool 依赖/指标/告警和对应构造参数；保留 worker_mode、jobs_dir、artifact_storage、DocumentJob/正式 callback/资源/部署/认证等判断。factory 保持 jobs 共享目录创建。修改范围内注释与 docstring 已同步中文，不新增运行日志。未改动的 HealthDeploymentInfo 类保留原英文 docstring，避免引入无关 OpenAPI description 差异。

## 文件删除与理由

| 文件 | 原行数 | 理由 |
|---|---:|---|
| `app/infrastructure/persistence/file/stage_messages.py` | 62 | 旧阶段消息仓储已无消费者。 |
| `app/infrastructure/persistence/sqlite/stage_messages.py` | 112 | 旧阶段消息仓储已无消费者。 |
| `app/infrastructure/persistence/mysql/stage_messages.py` | 123 | 旧阶段消息仓储已无消费者。 |
| `scripts/ops/shadow_copy_metadata_to_database.py` | 352 | 仅服务旧 JobRecord/JobFile/stage 数据迁移或完整性扫描，无正式 DocumentJob 消费者。 |
| `scripts/ops/shadow_copy_metadata_to_mysql.py` | 213 | 仅服务旧 JobRecord/JobFile/stage 数据迁移或完整性扫描，无正式 DocumentJob 消费者。 |
| `scripts/ops/check_local_file_storage_integrity.py` | 407 | 仅服务旧 JobRecord/JobFile/stage 数据迁移或完整性扫描，无正式 DocumentJob 消费者。 |
| `scripts/ops/shadow_upload_artifacts_to_object_storage.py` | 213 | 仅服务旧 JobRecord/JobFile/stage 数据迁移或完整性扫描，无正式 DocumentJob 消费者。 |
| `tests/test_metadata_shadow_copy.py` | 210 | 旧工具专属测试 5 项，无正式任务覆盖。 |
| `tests/test_local_file_storage_integrity_check.py` | 160 | 旧工具专属测试 3 项，无正式任务覆盖。 |
| `tests/test_artifact_shadow_upload.py` | 91 | 旧工具专属测试 2 项，无正式任务覆盖。 |

## 混合测试处理

`tests/test_database_job_repository.py` 仅删除 `test_replay_pending_flow_uses_database_repository`（旧 stage 重放专属）和对应 snapshot/file/stage SQL fake、夹具、合同片段；保留正式 DocumentJob/DocumentFile/Callback/TranslationBatch/User/Resource/SavedView 等方法与断言。原跨实例测试继续保护 JobEvent 持久化，增加 SQLite 有 job_events 且无三张旧表断言；三后端 readiness 测试改检验正式 DocumentJob 仓储。MySQL schema 期望表集合只减去三张旧表。

## 验证

指定解释器 `${PROJECT_ROOT}/.venv/bin/python` 与 `PYTHONDONTWRITEBYTECODE=1` 执行以下 6 个方法，最终全部通过：

- `test_metadata_repository_contract_matches_file_backend`（file/SQLite/fake MySQL 正式元数据及保留事件合同）
- `test_mysql_schema_bootstrap_includes_resource_versions`
- `test_database_repository_persists_records_across_instances`
- `test_build_runtime_switches_to_database_repository_and_readiness`
- `test_build_runtime_switches_to_mysql_repository_and_readiness`
- `test_build_runtime_keeps_file_repository_as_local_default`

首次事件测试发现清理旧夹具后遗留 `persisted_job_id` 断言 NameError，删除该旧断言并单独重跑该方法通过；其他五项成功结果复用。另以 AST 对比 HEAD 确认三后端 JobEventRepository 类未变，以 DDL 字符串对比确认 job_events 表与索引未变，正式 SQLite/MySQL document_jobs.py 文件逐字未变。`git diff --check` 通过。

主会话负责整体 build_runtime/Celery/compileall、OpenAPI 和健康/正式阶段定向验收。未执行完整回归、真实 MySQL、部署或生产变更。未发现需保留的未知正式依赖。
