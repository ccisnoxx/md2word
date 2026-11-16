# 实施与验证

## 实施顺序

1. 用户审阅本方案后激活任务，按 backend Spec 开工。先改持久化初始化和认证导入，再由 `app/main.py` 显式控制 `app/composition/startup.py` 的全量 bootstrap。核对注入的 Runtime、测试工厂及两个运维 CLI 的调用契约。依赖初始化的测试和夹具显式准备相应状态。避免在构造时调用借由读取触发写入的默认项解析。
2. 在 `app/workers/document_tasks.py` 接入两种任务共享的进程级获取点，保留主进程的 MinerU 恢复入口。验证 `TemplateReadService` 在无 MySQL 目录的兼容路径上跨任务读取更新后的 manifest；仅改该路径所需的缓存行为。
3. 一起修改 dev/prod Compose、对应 Dockerfile 的默认 API 命令及本地 API 调试入口。Compose API 继续使用现有探针和监听参数。同步部署说明中仓库 Compose 和分层 `--no-deps` 的顺序，并更新启动职责相关 Spec，使 schema 初始化、Worker 装配和恢复的合同与代码一致。

## 最小定向验证

| 覆盖 | 检查 |
| --- | --- |
| AC1 | 复用验收 seed、fake MySQL 术语初始化、内部用户导入、模板历史测试。覆盖新库及已有数据的初始化。API 工厂测试用阻塞/异常注入证明初始化完成才返回可服务的 App，失败不提供健康响应。 |
| AC2 | 扩展现有 Worker 模板测试，在临时目录运行真实装配。使用 file/SQLite 和 fake MySQL 跟踪目录、schema、六类 seed（含账号）与默认模板入口，断言空路径不被创建、已有存储不被装配修改。验证恢复拿到同样的只装配实例。 |
| AC3 | 整理 dev/prod Compose 后以非真实占位配置分别运行 `docker compose config --quiet`，核对 API 工厂参数、探针和 Worker 依赖。此检查验证编排配置。清洁卷的实际 API 健康到 Worker ready 可在单独授权的 Compose 运行中取证。 |
| AC4 | 文档和翻译任务各执行一次，断言同 PID 只构造一次；覆盖 fork/PID 变更、首次构造失败后可再次尝试、同 Runtime 读到更新后的配置和 legacy manifest。重用已有任务快照与历史模板断言。 |
| AC5 | 在模拟 callback 与 polling 两种设置下调用现有 Worker 信号接收者，观察跳过或单次 `polling_only=True` 恢复。保留 Celery 启动入口的队列、Poppler 前置检查和任务重试语义。 |

实施时从以下现有目标收敛到修改涉及的最小用例集，按需加上特定回归用例。

```bash
.venv/bin/python -m unittest tests.test_worker_template_bootstrap tests.test_document_worker_entrypoint
.venv/bin/python -m unittest tests.test_acceptance_center_api.AcceptanceCenterApiTests.test_runtime_bootstraps_current_acceptance_summaries_when_empty tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_runtime_bootstraps_term_assets_and_translation_terms tests.test_internal_user_management.InternalUserManagementTests.test_config_bootstrap_imports_only_when_managed_repository_is_empty
.venv/bin/python -m unittest tests.test_template_seed_history tests.test_mineru_config
git diff --check
```

复核持久化首次初始化、API 健康前的启动顺序和 Worker fork 后的 Runtime 归属。fake MySQL 能提供 SQL 调用层证据，真实 DDL、broker + prefork 的端到端启动顺序和 hostdzire 生效配置要以实际运行记录确认。[定向验证记录](verification.md)
