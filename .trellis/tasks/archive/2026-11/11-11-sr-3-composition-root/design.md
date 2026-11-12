# 设计

## 1. 目标结构

```text
app/main.py                      build_runtime / create_app / LazyDefaultApp / app / _validate_runtime_guardrails
app/composition/
  platform.py                    build_platform_services(settings, adapters) -> PlatformServices
                                 （audit、acceptance、auth、internal users、saved views、file upload/retention、resource_version_service）
  document_pipeline.py           build_document_pipeline(settings, adapters, platform) -> DocumentPipeline
                                 （document_ir、AI/MinerU 配置、translation provider/services、term_version_service、
                                   job_resource_snapshot、template_read、renderer、preview、execution、两个队列、recovery、
                                   job use cases、incident service）
  terminology.py                 build_terminology_services(settings, adapters, platform) -> TerminologyServices
                                 （term rules 全家、translation profile/term set/proposal、terminology release）
  health.py                      build_health_service(...) -> HealthService，以及告警投递 provider / secret resolver
  startup.py                     run_startup_bootstrap(...)：按基线顺序执行全部 bootstrap 副作用
app/api/middleware.py            install_trace_logging_middleware(app)
```

不保留 `app/composition/__init__.py` 的再导出，调用方直接从子模块导入。

## 2. bootstrap 顺序

基线中的顺序：

1. `acceptance_run_service.bootstrap_default_runs_if_empty()`（构造后立即执行）
2. `term_version_service.bootstrap_repository_from_csv_if_empty()`（在构造 `job_resource_snapshot_service` 之前）
3. `term_rule_set_version_service.bootstrap_seed_as_default_if_empty(...)` 或 `TermRuleBootstrapService(...).bootstrap()`
4. `translation_profile_service.bootstrap_default_profiles_if_missing()`
5. `template_read_service.get_default_template_id()`
6. `template_read_service.bootstrap_manifest_versions()`

另外 `resolved_settings.page_quality_policy()` 是一个配置校验调用，位于 renderer 构造之后，保持在 document_pipeline 中原位置。

设计决策：把 1–6 统一放到 `run_startup_bootstrap`，在所有服务构造完成后、`HealthService` 构造之前，按 1→6 的顺序执行。前提是 1、2 前移/后移不改变任何构造函数的行为。实施第 0 步会逐一阅读中间构造函数（`JobResourceSnapshotService`、`TemplateReadService`、`DocumentJobPreviewService`、执行服务等）是否在 `__init__` 中读取 acceptance runs 或 translation term repository。如果有读取，则该项 bootstrap 留在原位置，并在 `startup.py` 中注明原因。

## 3. 数据传递

各装配函数返回 frozen dataclass，字段名与 `AppRuntime` 字段一致。`build_runtime` 最后用显式关键字参数构造 `AppRuntime`，不使用 `**asdict()` 合并，以保留类型检查和可读性。

## 4. 被拒绝的方案

- 依赖注入容器 / provider 注册表：项目规则禁止为了架构外观引入框架，而且现有规模下显式函数完全够用。
- 每个领域在自己的包里放 `wiring.py`：会让领域代码反向依赖 `Settings` 和 persistence 工厂的细节；集中放在 `app/composition/` 更符合组合根的定位。
