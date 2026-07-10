# MinerU 密钥运行时配置设计

## 1. 最小可行设计

新增一个独立的 MinerU 运行时配置领域，由 `MinerUConfigService` 作为密钥状态的唯一权威来源。该服务每次读取时都检查共享运行时文件；文件不存在才读取 `Settings.mineru_api_token`，文件存在则必须成功解析，禁止回退环境变量。

不建立通用配置框架，也不把 MinerU 合并进翻译 Provider 配置。MinerU 被 legacy jobs、document_jobs、健康检查和运维状态共同使用，独立领域边界比挂在任一任务域下更清晰。

## 2. 模块与依赖边界

### 后端所有权

- `app/domains/mineru/config.py`：持久化记录、有效配置模型、配置读取/更新和领域错误。
- `app/domains/mineru/schemas.py`：管理员 GET/PUT API 合同。
- `app/domains/mineru/router.py`：权限、审计和安全响应映射。
- `app/core/config.py`：只负责从 `DATA_DIR` 派生固定文件 `var/config/mineru_config.json`，不新增可变配置来源。
- `app/main.py`：构造一个 `MinerUConfigService`，注入 `AppRuntime`、两条任务链路和 `HealthService`。
- `app/api/errors.py` / `app/core/errors.py`：把配置损坏映射为稳定的 HTTP 503 与 `mineru_config_invalid`，不向响应暴露文件路径或异常原文。

### 依赖方向

```text
Settings / shared DATA_DIR
        |
        v
MinerUConfigService  <--- GET/PUT MinerU config API
        |
        +---> HealthService / Config Workbench diagnostics
        +---> legacy JobStageService client factory
        +---> DocumentJobExecutionService client factory
        +---> PDF upload / result recovery guards
        +---> Ops integration control safe summary
```

`MinerUClient` 仍只负责外部 HTTP 协议。任务服务在每次创建客户端时调用配置 resolver，避免客户端持有可变全局状态，也不需要进程内事件总线或缓存失效机制。

## 3. 文件合同

运行时文件位于 `Settings.data_path / "config/mineru_config.json"`，只包含当前值：

```json
{
  "api_token": "<secret>",
  "updated_at": "2026-07-10T00:00:00+00:00",
  "updated_by": "admin-id"
}
```

合同约束：

- `api_token`、`updated_at`、`updated_by` 都是必填字段；未知字段或字段类型错误视为配置损坏。
- `api_token` 在模型边界去除首尾空白后必须非空，并设置合理长度上限，计划沿用现有 API Key 的 `4096` 字符上限。
- 写入使用同目录唯一临时文件，写完后设为 `0600` 再原子替换目标文件，替换后再次尽力确认权限。
- 文件不存在代表尚未由配置中心接管，允许使用环境变量；任何其他读取或解析失败都抛出 `MinerUConfigError`。
- 更新不读取旧记录，因而即使旧文件损坏，管理员仍可用合法非空密钥覆盖并修复；不会写历史文件或备份副本。

## 4. API 合同

### `GET /api/v1/mineru-config`

仅 admin JWT 可访问，响应：

```json
{
  "api_token_configured": true,
  "source": "settings",
  "updated_at": null,
  "updated_by": null
}
```

`source` 只允许 `settings` 或 `runtime_config`。响应没有 token、mask、长度或指纹字段。

### `PUT /api/v1/mineru-config`

仅 admin JWT 可访问，请求只包含：

```json
{"api_token": "new-secret"}
```

- 缺失、空白或超长值由 Pydantic 边界返回统一 `validation_error`。
- 不提供 `clear_api_token`，也不接受其他 MinerU 配置字段。
- 写文件成功后记录 `action=mineru_config.update`、`target_type=mineru_config`、`target_id=default`、`details={"api_token_configured": true}`；审计事件自身提供 actor、`created_at` 和 `trace_id`。
- 审计失败时捕获并转换为明确的 503：说明新密钥已保存但审计失败，保留文件且不回滚；系统日志只记录 `trace_id` 和动作，不记录请求体或密钥。

## 5. 运行时一致性

### 客户端创建

`JobStageService` 与 `DocumentJobExecutionService` 接收同一个 typed config resolver。各自 `_build_mineru_client()` 在创建客户端时读取一次有效配置；配置为空时保留当前明确的“未配置”失败，配置损坏时传播领域错误。已创建客户端不重新绑定 token，符合“已发出的请求不切换”的要求。

### 健康与门禁

`HealthService.build_dependency_checks()` 每次只解析一次 MinerU 有效配置，并把同一结果传给普通 readiness 和 P0 document_jobs readiness：

- 未配置：`mineru_api_token_missing`。
- 文件损坏：`mineru_config_invalid`，`pdf_submission_available=false`，不再附加误导性的 missing 结论，也不回退环境变量。
- 合法运行时配置：`mineru_api_token_configured=true`，并可安全暴露 `mineru_config_source`、`mineru_config_updated_at` 和 `mineru_config_error=null`。

PDF 上传入口、结果恢复和 Ops integration control 不再直接读取 `runtime.settings.mineru_api_token`，统一使用服务结论。Config Workbench 仅把 `mineru_api_token_missing` 与 `mineru_config_invalid` 路由到新页面；callback URL/UID 等页面不可编辑的问题继续指向系统状态。

## 6. 前端设计

新增 `MinerUConfigPage.vue`，复用 `WorkbenchPageHeader`、`WorkbenchPanelCard` 和 `ApiErrorAlert`：

- 左侧/主卡片只提供一个密码输入框和“更新密钥”按钮，不提供显示当前值、`show-password`、清空或测试按钮。
- 右侧状态卡片展示 configured/missing、配置来源、更新时间和更新人。
- 成功后清空输入并使用 PUT 响应刷新状态。
- 审计失败错误由 API 明确提示“密钥已保存”，页面保留错误并允许刷新确认状态。
- 路由、侧边导航、面包屑、配置中心入口卡片以及 release gate 路由表统一增加 `/settings/mineru`，权限保持 `roles=[admin]` 与 `settings:write`。

## 7. 兼容性、发布与回滚

- 未创建运行时文件的部署继续使用 `MINERU_API_TOKEN`，现有部署升级后行为不变。
- 首次通过页面更新后，共享 volume 中的运行时文件成为权威来源；后续只修改 `.env` 不会生效，这是已确认的运维合同。
- API 与 Worker 已共享 `md2word-var`，不修改 Compose volume；Celery 每个任务构建 runtime，长期 Stage Worker 则依靠 resolver 每次读文件。
- 代码回滚时旧版本不会读取该文件，会重新使用 `MINERU_API_TOKEN`；运维回滚前必须确认环境变量仍含可用密钥。运行时文件保留在 volume 中，重新升级后仍会继续优先。
- 不执行本地真实 MinerU 验证。正式 API/Worker/共享 volume/真实任务证据按线上优先流程在 hostdzire 收集。

## 8. 取舍与剩余风险

- 采用 `0600` 明文文件而非加密或 Secret Manager，拥有容器/宿主机文件读取权限的主体仍能读取密钥。
- 文件与审计仓储无法组成同一事务；按已确认策略，审计失败时优先保持新密钥可用并返回错误。
- 当前方案依赖单机共享 volume，不支持未来多主机实例同步；扩展部署拓扑时必须替换持久化边界。
- 不调用 MinerU 验证，因此错误密钥只能在后续真实任务中暴露。
