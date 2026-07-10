# Runtime Configuration

本文记录 MinerU 账号 UID 与 API 密钥绑定的运行时轮换合同。其权威实现位于 `app/domains/mineru/config.py`，API、Worker、callback 验签、健康检查和业务门禁不得各自重新实现配置优先级。

## Scenario: MinerU 账号与密钥运行时轮换

### 1. Scope / Trigger

- 触发条件：修改 MinerU UID/密钥读取、管理员配置接口、MinerU 客户端创建、callback checksum、健康就绪状态、PDF 上传/恢复门禁或部署共享 volume。
- 核心不变量：API 密钥与 UID 是一组原子绑定；运行时文件存在后是唯一权威来源，文件损坏、缺字段、格式非法或不可读时明确失败，绝不混用或静默使用旧环境变量。

### 2. Signatures

- 配置服务：`MinerUConfigService.get_effective_config() -> EffectiveMinerUConfig`。
- 更新服务：`MinerUConfigService.update_credentials(*, api_token: str, uid: str, updated_by: str) -> EffectiveMinerUConfig`。
- 管理员读取：`GET /api/v1/mineru-config`。
- 管理员覆盖：`PUT /api/v1/mineru-config`，请求为 `{"api_token": "<new-secret>", "uid": "<new-account-id>"}`。
- 运行时文件：`Settings.data_path / "config/mineru_config.json"`。

### 3. Contracts

- `api_token` 与 `uid` 去除首尾空白后长度必须分别为 `1..4096`、`1..256`；PUT 必须同时提交，不提供单项更新、清空、历史、回滚或外部有效性测试。
- 文件必须是严格 JSON 对象，只含必填字段 `api_token`、`uid`、`updated_at`、`updated_by`；未知字段或缺少任一绑定字段都视为损坏。
- 文件不存在时才共同读取 `MINERU_API_TOKEN` 与 `MINERU_UID`；合法文件中的完整绑定始终共同覆盖环境变量。
- 写入使用同目录临时文件和原子替换，目标文件在支持 POSIX 权限的平台上为 `0600`，不保留备份或旧绑定。
- GET/PUT 响应只含 `api_token_configured`、`uid_configured`、`source`、`updated_at`、`updated_by`，不得返回 UID、密钥、脱敏片段、长度、指纹或请求体。
- 更新审计固定为 `action=mineru_config.update`、`target_type=mineru_config`、`target_id=default`，详情只含 `{"api_token_configured": true, "uid_configured": true}`；actor、时间和 `trace_id` 由审计记录承载。
- `JobStageService` 与 `DocumentJobExecutionService` 在每次创建新 `MinerUClient` 时调用同一个 resolver，并同时传入 `api_token` 与 `uid`；已经创建的客户端保持原绑定。
- callback checksum 每次先通过同一个 resolver 确认运行时绑定可读；payload 未携带 UID 时读取配置 UID，payload 自带 UID 时沿用官方 callback 合同，但损坏文件仍优先明确失败。

### 4. Validation & Error Matrix

- 运行时文件不存在 -> 分别使用去除空白后的 `MINERU_API_TOKEN` 与 `MINERU_UID`，并按实际值返回两项配置状态。
- 文件 JSON 损坏、缺少绑定字段、字段非法、不可读或目标是损坏符号链接 -> 抛出 `MinerUConfigError`；HTTP 返回 `503/mineru_config_invalid`，健康状态记录同名异常且不得混用或回退环境变量。
- PUT 任一字段缺失、空白、超长或含未知字段 -> `422/validation_error`；该接口的校验响应不得包含 Pydantic 原始 `input`。
- 原子写入失败 -> `503/service_unavailable`，不得声称更新成功。
- 文件写入成功但审计失败 -> 保留新文件并返回明确 `503/service_unavailable`；管理员刷新后可确认新的更新时间和更新人。
- 保存流程 -> 只做本地校验、持久化和审计，不调用 MinerU 或其他外部接口。

### 5. Good/Base/Bad Cases

- Good：管理员覆盖完整绑定后，后续 API、Stage Worker 和 Celery Worker 新建的客户端无需重启即读取新 UID 与密钥，callback fallback、健康和业务门禁使用同一结论。
- Base：从未通过配置中心保存时，现有部署继续共同读取 `MINERU_API_TOKEN` 与 `MINERU_UID`，响应只显示 `source=settings` 和两项配置状态。
- Bad：只更新密钥或 UID；捕获运行时文件解析异常后混用环境变量；在响应、日志或审计中写入 UID/密钥片段；保存时发送 MinerU 测试请求；为轮换保留旧绑定副本。

### 6. Tests Required

- `tests.test_mineru_config`：断言两项环境变量 fallback、完整文件优先、任一空白拒绝、缺 UID 不混用、严格解析、损坏符号链接不回退、原子覆盖、无备份和 `0600`。
- `tests.test_fastapi_jobs_backend`：断言 admin 权限、响应/422/审计不泄露 UID 或密钥、健康与门禁一致、callback fallback、两条客户端工厂即时读取完整绑定、旧客户端不变、损坏文件和审计失败语义。
- `tests.test_openapi_export`：断言 `/api/v1/mineru-config` 及安全响应字段，并保持 `docs/api/openapi.json` 最新。
- 前端单测：断言 API method/path、两个字段必须绑定提交、独立页面不提供回显/清空/测试、保存成功清空两个输入、导航和诊断路由指向 `/settings/mineru`。
- 发布前运行 `.venv/bin/python scripts/ops/check_release.py` 和 `npm --prefix frontend run build`。

### 7. Wrong vs Correct

#### Wrong

```python
try:
    token, uid = read_runtime_file()
except Exception:
    token = settings.mineru_api_token
    uid = settings.mineru_uid
```

#### Correct

```python
config = runtime.mineru_config_service.get_effective_config()
client = MinerUClient(api_token=config.api_token, user_token=config.uid or "", ...)
```

只有 `FileNotFoundError` 表示配置中心尚未接管；其他读取或解析失败必须继续作为明确错误传播，禁止从运行时文件和环境变量拼接绑定。
