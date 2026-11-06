# 最小修复设计

## 选择

四个局部 fixture 的 `public_deployment_mode` 从 `single_tenant_public` 改为显式 `internal`。继续采用现有 file/eager 隔离运行时；测试职责是回调处理，未断言公开部署能力。所有回调仍进入真实路由、URL 白名单校验和 checksum 校验，队列及状态断言不变。

四个方法已有创建 HTTP 201 断言，但放在 `job_id` 读取和后续动作之后。将原断言移至创建响应之后、首次 JSON 字段访问之前；失败可直接暴露 HTTP 状态差异，避免 KeyError 掩盖前置失败。不复制断言，不增加生产代码异常兜底。

## 范围约束与理由

- 不把 fixture 伪装成 MySQL/Celery，也不 mock readiness；这会改变测试环境职责并掩盖正确的生产保护。
- 不调整共享 helper，避免影响同文件其他用例。
- 不更换渲染器，不引入仅返回 fake-docx 的替身；当前 runtime 已使用正式 DocumentIRWordRenderer。
- 公开模式与 internal 的 callback 安全流程相同，见真实 router/guard 和 `docs/api/mineru-callbacks.md` 部署模式表。
- 生产 eager/non-MySQL 的专属 readiness 用例已存在；本任务只静态核对，不扩大执行列表。

## 风险与停止条件

规划时确认创建阶段根因；实施后四条完整定向路径均通过。若后续出现新的失败，先定位；不得削弱原断言或顺带修改业务代码。超出本计划局部配置与断言位置的变更需先报告具体证据并更新计划确认。

## 文档与兼容性

无公开 API、数据库、配置默认值和生产行为变更，因此不生成 OpenAPI、不增加 migration 或 CI。任务文档使用中文；实施时审阅四个方法内被触及的注释/开发者文本，仅在非显然的夹具责任需要解释时补充中文说明。
