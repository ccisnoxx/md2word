# 部署审计

## 发布标识

- 执行时间：2026-08-24 16:57:14 CST
- 主机：`hostdzire`
- 分支：`codex/refine-word-generation-rules`
- 目标提交：`e91d8e6c65c7a5b8cd55ec7b1448c9484a527752`
- 前端提交：`aafee4bf92164835fcedab5999285f276170e17a`
- 后端 release：`/root/md2word-releases/e91d8e6`
- 前端 release：`/var/www/md2word-frontend/releases/e91d8e6-20260824T084059Z`
- deployment id：`hostdzire-20260824T084059Z-e91d8e6`

## 重置前状态

- 旧后端 release：`/root/md2word-releases/d8b8196`
- 旧前端 release：`/var/www/md2word-frontend/releases/0ec7d69-20260818T072719Z`
- `jobs=0`
- `default@1`、`default@2` 为 published，`default@3`、`default@4` 为 draft。
- 默认指针为 V2，版本序列 `next_version=5`。
- 运行时版本目录仅有 V3、V4，每个目录各含 DOCX 和 YAML。

## 实际重置范围

- 停止 API、Worker 后，在单一 MySQL 事务中删除：
  - `resource_versions` 四行；
  - `resource_default_versions` 一行；
  - `resource_version_sequences` 一行。
- 事务提交后仅删除 `/app/var/config/templates/default/v3`、`v4`。
- 保留 MySQL、Redis、共享 volume、其他资源版本、旧 release 和既有 audit events。
- 重置脚本返回：`deleted_versions=4`、`deleted_default_pointers=1`、`deleted_sequences=1`，删除目录为 V3、V4。

## 新 V1 状态

- 线上只存在 `default@1`，状态 `published`，`is_default=true`。
- `resource_version_sequences` 中不存在 `template/default` 行；下一 draft 由现有版本分配逻辑从 V2 开始。
- DOCX 路径：`resources/templates/default/datasheet_template.docx`
- DOCX SHA-256：`b21448dbc10e7c7d5028490ddc079d784eb12a0360b35be2345fa0218aa12cfb`
- YAML 路径：`resources/template_configs/datasheet_template.yaml`
- YAML SHA-256：`03281842a45506dd717558a9ab1121100b5e264cd5425671a4ff5f9641838b1c`
- 模板详情、版本列表和 layout-config API 返回 V1 为唯一默认版本；页脚配置为左 `v1.0`、中页码、右 `info@ichelps.com`。

## 验证证据

- 空生产环境 release check：235 项 targeted unittest 通过；OpenAPI、前端合同和 smoke mock 通过。
- 新运行时 readiness：`deployment_init_ready=true`、`p0_document_jobs_ready=true`，`readiness_blockers=[]`、`p0_document_jobs_blockers=[]`。
- Golden Sample preflight：四个样本、admin 运维认证、MySQL/Celery readiness 全部通过。
- 真实任务：`docjob_43018ca5e560`，状态 `succeeded`，任务和资源快照均为 `default@1`。
- 结果 DOCX SHA-256：`3911cf7d67bd68345c41da3e4c4f03138931e6703fc9fb56a5a844eb12f5417e`。
- OOXML：页脚包含左侧 `v1.0`、原生 `PAGE` field、margin-relative center/right positional tab、右侧 `info@ichelps.com`。
- WPS：实际显示左侧 `v1.0`、中部页码 `1`、右侧邮箱，正文与页脚无重叠。
- 前端 `current` 已原子切换，`nginx -t` 和 reload 通过；公网首页、静态资源、live/ready 正常。
- 最终 Compose：API、MySQL、Redis healthy，Worker 正常运行；近 20 分钟日志无 `ERROR`、`CRITICAL`、Traceback 或 exception。

## 未完成的非阻断视觉复核

- 应用内浏览器无登录态，Chrome 页面又被已打开的扩展浮层阻断，因此未绕过认证或扩展安全边界做线上登录后页面截图。
- 线上模板 API 已证明页面数据源只返回 V1 且为默认；前端生命周期组件的 unit、build 和 targeted smoke 已在目标提交通过。剩余风险仅为登录后视觉层复核，不影响已验证的版本状态、默认任务或文档输出。
