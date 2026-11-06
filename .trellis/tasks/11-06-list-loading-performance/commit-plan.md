# 提交计划（2026-11-07 已获批准）

建议在分支codex/list-loading-performance形成一个完整修复提交，建议标题：`fix: reduce task and incident list database overhead`。包含请求内就绪检查、完整key拆列及迁移、异常读取会话、直接回归、对应Spec和本任务脱敏文档。普通列表拆列与异常会话同属本任务且共享文件，合并成一次提交便于审阅一致候选。

当前明确产品/脚本/测试/Spec路径（提交前另补齐直接受影响的运维版本说明，未改变产品代码）：

- `docs/runbooks/backend.md`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/document-job-list-query-v2.md`
- `app/domains/document_jobs/incidents.py`
- `app/domains/document_jobs/list_query.py`
- `app/domains/document_jobs/service.py`
- `app/domains/files/repository.py`
- `app/infrastructure/persistence/document_job_list_query.py`
- `app/infrastructure/persistence/file/files.py`
- `app/infrastructure/persistence/mysql/backend.py`
- `app/infrastructure/persistence/mysql/document_jobs.py`
- `app/infrastructure/persistence/mysql/files.py`
- `app/infrastructure/persistence/mysql/schema.py`
- `app/infrastructure/persistence/sqlite/document_jobs.py`
- `app/infrastructure/persistence/sqlite/files.py`
- `app/infrastructure/persistence/sqlite/schema.py`
- `scripts/ops/migrate_document_job_list_query.py`
- `scripts/ops/migrate_document_job_reviews.py`
- `tests/test_database_job_repository.py`
- `tests/test_document_job_delivery_state_migration.py`
- `tests/test_document_job_list_query.py`
- `tests/test_document_job_list_query_migration.py`
- `tests/test_document_job_list_query_v2.py`
- `tests/test_document_job_list_query_v2_mysql.py`
- `tests/test_document_job_list_query_v2_writers.py`
- `scripts/ops/migrate_document_job_list_keys.py`
- `tests/test_document_file_read_session.py`
- `tests/test_document_file_read_session_mysql.py`
- `tests/test_document_job_list_key_columns.py`
- `tests/test_document_job_list_query_readiness.py`

任务文档仅限.trellis/tasks/11-06-list-loading-performance内本任务已识别的脱敏记录；不包含忽略的research/data、凭据、临时数据库/环境或其他worktree。提交前仍需核对当时diff，逐路径暂存，不能包含新的未知脏文件。

用户已明确批准按本计划核对并本地提交；本轮不推送或集成发布分支。相关源码与实测SHA一致，复用既有验证。生产发布另外授权：整体候选包含五列拆列迁移，必须遵循已记录停写/备份/回填/verify与旧JSON重建回退方案；异常读取会话本身无新增schema。线上API/浏览器验收随后执行。

提交前核对发现运维手册仍引用旧JSON版本2/1，已同步当前3/2及五列、干跑/回填游标和冻结旧工具回退规则；仅文档纠正，按项目规则不重跑应用测试。发布准备研究和审批计划作为本任务脱敏文档一并保留，未执行其中生产动作。
