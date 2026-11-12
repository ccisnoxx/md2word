# 启动副作用顺序分析（sr-3 第 0 步）

基线：`26706a5d`。录制工具：`tools/record_bootstrap_order.py`，输出：`validation/bootstrap-order-baseline.json`。

## 1. 基线顺序（file 与 database 两种后端相同）

1. `AcceptanceRunService.bootstrap_default_runs_if_empty`
2. `AuthService._bootstrap_repository_from_config_if_empty`（构造函数内部的隐式副作用）
3. `TermVersionService.bootstrap_repository_from_csv_if_empty`
4. `Settings.page_quality_policy`（只做配置校验，可能抛异常，不写数据）
5. `FileTermRuleRepository.__init__`（创建 store 的父目录）
6. `TermRuleBootstrapService.bootstrap`（没有 `resource_version_service` 时走这里；MySQL 后端走 `TermRuleSetVersionService.bootstrap_seed_as_default_if_empty`）
7. `TemplateReadService.get_default_template_id`
8. `TemplateReadService.bootstrap_manifest_versions`

`TranslationProfileVersionService.bootstrap_default_profiles_if_missing` 只在有资源版本仓储（MySQL）时触发。

## 2. 构造函数是否依赖 bootstrap 写入的数据

用 AST 检查 `build_runtime` 中构造的全部类的 `__init__`：除 `AuthService`（导入内部用户）、`FileTermRuleRepository`（mkdir）、Poppler 适配器（`shutil.which`）、`HealthService`（`utc_now`）以外，其余构造函数只做属性赋值或构造无状态对象，不读取任何仓储。所以把显式 bootstrap 移到所有构造完成之后，不会改变任何构造函数的结果。

## 3. 集中执行后顺序的变化

目标顺序：先构造（2 → 4 → 5 按构造顺序发生），再由 `run_startup_bootstrap` 依次执行 1 → 3 → 6 → profile → 7 → 8。

变化只有两处：

- 第 1 步（验收种子）移到第 2 步（内部用户导入）之后。
- 第 3 步（翻译术语 CSV 导入）移到第 4、5 步之后。

这些副作用写入的位置互不相同：验收记录写 `acceptance_runs.json` 或对应表，内部用户写用户仓储，翻译术语写术语仓储，第 5 步只创建术语规则目录。它们都是"为空才写入"的幂等操作，没有一个读取另一个的产物，因此最终持久化状态与基线一致。

唯一可观察的差别：如果启动时有两处同时出错（例如内部用户配置错误，同时验收仓储不可写），最先抛出的异常会不同。两种顺序下启动都会失败，不影响正确性。

`create_app()` 中对 `bootstrap_manifest_versions()` 的再次调用（为直接注入的 runtime 补登记）保持不变。
