# 本地验收记录

- AC1：`test_set_default_template_rejects_missing_or_changed_registered_files` 覆盖 DOCX、YAML 各自缺失和各自可解析但哈希已变化。四个子用例均核对 HTTP 400、逻辑原因码、原始指针（含更新时间）和审计。新测试在旧代码上可复现四种失败。
- AC2、AC5：`test_set_default_template_version_does_not_select_global_template` 用无 YAML 的自定义模板切换并回切，核对成功响应、实际指针、审计和后续任务快照。版本接口保留原全局 ID，独立 PATCH 接口可切换该 ID。
- AC3：`tests.test_template_default_switch_mysql` 在真实 MySQL Community Server 8.4.9、`REPEATABLE-READ` 上，用独立连接在两个请求观察同一指针后放行。已有指针与无指针的首次竞争均得到一个 200、一个 409、一条胜出审计，且独立读取获得胜出版本。
- AC4：真实 MySQL 验证预检后目标状态和哈希变化会拒绝切换。两个提交顺序覆盖切换与禁用的互斥。数据库触发器注入读回不符和审计写入错误，验证事务回滚。提交响应丢失用例让真实数据库完成提交后注入连接错误，验证 HTTP 503 和实际指针、审计状态。
- 生命周期与运行模式的三个既有 API 用例及 `tests.test_resource_versioning` 的 11 个用例通过。上述本地 API 与真实数据库证据合计 24 个测试方法，另外执行改动 Python 文件的语法检查及限定路径的 diff 检查。

真实 MySQL 使用独立 Colima profile 和仅绑定 loopback 的临时容器。镜像为 `mysql:8.4.9`，镜像索引摘要 `sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`，执行架构 arm64。测试仅访问自身创建的随机 schema。证据覆盖本地 API 与 MySQL 事务行为。
