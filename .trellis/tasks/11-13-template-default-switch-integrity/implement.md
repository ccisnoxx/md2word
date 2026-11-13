# 实施与验证

## 实施顺序

1. 先在模板服务和 API 测试中准备临时 DOCX、YAML、旧默认版本和两份已发布候选。通过真实字节验证缺失与可解析内容被修改的四种失败，断言版本指针及成功审计未变化。
2. 在资源仓储端口与 MySQL adapter 中加入专用条件切换操作。沿用现有事务上下文与绑定参数，处理目标状态和快照复查、旧指针匹配、首次插入、事务内读回和审计。按同一加锁顺序补上模板禁用的条件写入。只更新执行这些路径所需的测试替身。
3. 更新 `TemplateReadService.set_default_template_version()` 与该 API 的错误映射。复用现有模板包校验和统一原因码。提交前完成响应准备，成功后基于事务内确认结果返回。保留既有发布和全局默认模板接口入口。
4. 更新 `docs/api/templates.md` 及 `.trellis/spec/backend/template-layout-configuration.md` 的相关段落，说明两个默认入口、HTTP 409、成功审计及提交结果未知时的读回方式。

## 定向验证

- 使用 `.venv/bin/python -m unittest` 运行新增的模板切换、MySQL adapter、回滚和禁用竞争用例。校验故障注入中的旧指针、成功审计和实际返回码。覆盖合法无 YAML、非全局默认模板的切换、旧版本回切及新任务绑定。
- 运行 `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_profile_versioning_publishes_defaults_and_disables_versions`、`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml` 和 `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_versioning_endpoints_require_mysql_resource_service`，保护已发布版本生命周期和运行模式合同。
- 使用专用 loopback MySQL 8.4 随机 schema，加载涉及表的仓库 DDL，并用独立连接及屏障使两个请求先观察同一默认状态。分别验证已有指针和首次插入的竞争。用新连接核对最终指针、版本状态及审计，验证事务内审计失败导致指针回滚。当前 Docker 默认上下文未连到 daemon。实施时核实可用的隔离环境，并如实记录真实 MySQL 证据是否取得。
- 按 Trellis 检查流程对实际 diff 做独立只读复核，重点检查锁顺序、失败后有无第二次写入、响应是否来自确认结果，以及用户工作区既有改动。按项目规则选择定向检查。

## 停止与回退条件

- 任一失败请求更新指针或写入成功审计、两个请求都覆盖相同旧指针、默认版本被并发禁用，均阻止验收。
- 本任务交付本地实现和验证证据。应用代码可按正常发布流程回退。修复无需改表结构或回填现有资源记录。
