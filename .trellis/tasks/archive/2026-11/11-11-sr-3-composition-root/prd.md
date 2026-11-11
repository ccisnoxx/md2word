# 拆分 app/main.py 组合根

父任务：`11-11-structure-refactor`（对应用户需求第 1 项）。前置条件：sr-1、sr-2 已合入（两者都会改变执行服务和任务用例的装配方式）。

## 目标

`app/main.py` 只保留进程入口职责：`build_runtime()` 按顺序调用各领域的装配函数并组装 `AppRuntime`，`create_app()` 组装 FastAPI。各领域服务的构造细节、条件可用性判断，以及启动 bootstrap 副作用，分别移到职责明确的模块中。

## 现状

- `build_runtime()` 是一个约 300 行的函数，手工构造约 40 个服务。条件构造（`resource_version_service`、`term_rule_*`、`translation_*` 依赖可选 repository）和 6 处启动副作用交织在一起：`acceptance_run_service.bootstrap_default_runs_if_empty()`、`term_version_service.bootstrap_repository_from_csv_if_empty()`、term rule seed/bootstrap、`translation_profile_service.bootstrap_default_profiles_if_missing()`、`template_read_service.get_default_template_id()`、`bootstrap_manifest_versions()`。
- `create_app()` 中内联了 trace/access 日志中间件和启动恢复 lifespan。
- 外部入口：`app.main:app`（uvicorn）、`from app.main import build_runtime`（13 个测试文件 + `scripts/ops/run_file_retention_cleanup_readonly.py`）、`create_app(runtime)`。

## 需求

1. 新增 `app/composition/` 包，按领域分组提供装配函数：平台（审计/验收/认证/用户/保存视图/文件）、文档流水线（IR、翻译、渲染、预览、执行、队列、恢复、任务用例）、术语（term rules、翻译术语集、提案、发布、profile）、健康检查。
2. 启动 bootstrap 副作用集中在一个函数中，按原来的相对顺序执行。
3. trace/access 日志中间件移到 `app/api/middleware.py`，日志格式逐字保留。
4. `app/main.py` 保留 `build_runtime`、`create_app`、`LazyDefaultApp`、`app` 以及运行时防护（`_validate_runtime_guardrails`）。

## 约束

- `build_runtime(settings)`、`create_app(runtime)`、`app.main:app` 的签名和语义不变；`AppRuntime` 的字段不变（sr-2 的改名除外）。
- 不引入 DI 容器；装配函数是普通函数，返回 frozen dataclass 或具名元组，供 `build_runtime` 解包。
- 服务构造顺序的变化不能改变副作用顺序；如果某个构造函数在构造期间读取了被 bootstrap 写入的数据，则保留原来的顺序并在代码中注释说明。

## 验收标准

- [ ] `app/main.py` 不超过约 150 行，`app/composition/` 中每个模块不超过约 250 行。
- [ ] `build_runtime` 中没有直接 `new` 领域服务的代码（只调用装配函数，并组装 `AppRuntime`）。
- [ ] 启动副作用的执行顺序与基线一致（通过测试 patch 记录调用顺序来验证，见 implement）。
- [ ] 定向测试通过：`test_database_job_repository` 中的 `PersistenceAdapterTests`、`test_backend_logging`、`test_fastapi_jobs_backend`、`test_runtime_dependency_declarations`、`test_openapi_export`；`scripts/ops/run_file_retention_cleanup_readonly.py` 可以正常导入。
- [ ] `directory-structure.md` 的 "Runtime Composition" 一节已更新。
