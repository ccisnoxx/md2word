# 生产冷启动单一初始化实施计划

## 实施顺序

1. 在 `app/main.py` 接入统一初始化开关，并移除 `app/composition/startup.py` 内的模板单独开关。由 `app/infrastructure/persistence/factory.py` 向 SQLite、MySQL 透传 schema 初始化选择，由 `app/composition/platform.py` 向 `AuthService` 透传初次导入选择。保留默认路径及原有顺序。
2. 修改 `app/workers/document_tasks.py` 的三个 Runtime 构建入口。以现有 `tests/test_worker_template_bootstrap.py` 为起点扩展针对初始化所有权的检查，覆盖普通任务、翻译批次与 Worker 恢复边界，验证任务参数、恢复条件及结果仍按原有合同处理。
3. 修改 `docker/prod/docker-compose.yml` 与 `docker/dev/docker-compose.yml` 的 API 依赖。更新标准部署与本地 Worker 启动说明，并在 hostdzire 部署文档记录分层编排的先后顺序限制。更新后端装配和 schema 相关 Trellis spec 中受影响的启动合同。
4. 复用 `tests/integration/template_catalog_compose.py` 的隔离项目、生产镜像、真实 MySQL/Redis 与 MinerU 夹具。把其中的分批 `up` 替换为一次标准 Compose `up`，在 `up` 后立即取证 API 健康探针首次成功时间、Worker 启动时间和两容器重启计数。利用现有 API/Worker 分别重启用例核对保留的数据与业务结果。使用独立空隔离项目和确定性初始化失败输入验证 API 健康探针失败时的启动约束，例如向空库提供无法解析的测试账号配置。

## 定向检查

覆盖实际构造链。Worker 装配若访问 MySQL schema、账号空库探测或任何 seed 入口，应让定向用例失败。SQLite 使用临时数据库确认 Worker 构造跳过 schema，默认构造创建 schema。文件模式继续验证模板 seed 与默认选择均未在 Worker 装配期读取。对于已有 `app.main.build_persistence_adapters` 具名替身，按实际受影响的调用签名更新并验证。

```bash
.venv/bin/python -m unittest \
  tests.test_worker_template_bootstrap \
  tests.test_document_worker_entrypoint \
  tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_runtime_bootstraps_term_assets_and_translation_terms \
  tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_switches_to_database_repository_and_readiness \
  tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_switches_to_mysql_repository_and_readiness \
  tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_keeps_file_repository_as_local_default \
  tests.test_resource_versioning.MysqlResourceVersionRepositoryTests.test_mysql_runtime_exposes_resource_version_service \
  tests.test_template_seed_history.TemplateSeedHistoryTests.test_build_runtime_accepts_published_managed_seed \
  tests.test_acceptance_center_api.AcceptanceCenterApiTests.test_runtime_bootstraps_current_acceptance_summaries_when_empty \
  tests.test_internal_user_management.InternalUserManagementTests.test_config_bootstrap_imports_only_when_managed_repository_is_empty
git diff --check
```

## 隔离验收

使用已核对的隔离 Docker context、生产依赖锁对应的 Linux amd64 wheelhouse 与独立 Compose 项目。先核对 `compose config` 的最终合并结果，确认夹具没有覆盖 API 的健康依赖，再执行专项。报告至少记录冷启动时序、重启计数、默认资源读回、账号登录、真实队列任务和 DOCX 结果，以及保留数据后的重启结果。既有数据验证至少比较默认指针、版本标识或摘要、账号标识和已完成产物校验值。失败场景记录 API 未健康与 Worker 容器未开始执行的状态。收尾范围限本次测试专属容器、卷和镜像。

```bash
.venv/bin/python tests/integration/template_catalog_compose.py \
  --docker-context "$MD2WORD_TEST_DOCKER_CONTEXT" \
  --wheelhouse "$MD2WORD_TEST_WHEELHOUSE" \
  --report "$MD2WORD_TEST_BOOTSTRAP_REPORT"
```

若隔离 Docker 或 wheelhouse 不可用，记录缺失条件与已完成的定向证据，AC2/AC3 的真实 Compose 部分保留待验。线上环境、真实外部 MinerU 和发布流程的验收属于独立交付。

## 风险复核

- 确认 Worker 角色的三个入口都无法到达启动期初始化，尤其是 `AuthService` 构造副作用和 MySQL schema 维护。核对 API 默认路径的账号初次导入、已有账号和 default 指针。
- 确认 Compose 用健康状态约束启动，校验夹具与部署脚本没有把依赖条件替换回启动状态。对带 `--no-deps` 的 hostdzire 路径只评审文档边界。
- 执行最终差异检查及独立 Trellis 复核。回退时按设计中的成对回退步骤处理 API/Worker 与 Compose。

## 实施证据

定向检查与三项真实 Compose 验收的结果见 [验收记录](./research/verification.md)。
