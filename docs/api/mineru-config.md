---
doc_type: lib-api-ref
entry: mineru-config
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/mineru/config.py
  - app/domains/mineru/router.py
  - app/domains/mineru/schemas.py
summary: 管理员读取 MinerU 账号与密钥安全状态并原子轮换运行时绑定。
tags: [config, mineru, secret, admin]
last_reviewed: 2026-07-10
---

# MinerU Config API

## 概述

`/api/v1/mineru-config` 为配置中心提供 MinerU 账号 UID 与 API 密钥的绑定轮换能力。接口只允许 admin Bearer JWT，不支持 legacy admin token、operator 或匿名访问。

安全边界：

- GET/PUT 响应不返回 UID、密钥原文、脱敏片段、长度或指纹。
- 更新必须同时提交非空 UID 与 API 密钥，不支持单项更新、清空、历史值或一键回滚。
- 保存只做本地校验与私有文件写入，不调用 MinerU 验证。
- 运行时文件以明文保存在共享 `DATA_DIR` 下，但使用原子替换并在支持的平台上限制为 `0600`。

## `GET /api/v1/mineru-config`

返回安全状态：

```json
{
  "api_token_configured": true,
  "uid_configured": true,
  "source": "runtime_config",
  "updated_at": "2026-07-10T00:00:00Z",
  "updated_by": "user_admin"
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `api_token_configured` | 当前是否存在可供新 MinerU 请求使用的密钥 |
| `uid_configured` | 当前是否存在与密钥绑定的 MinerU 账号 UID |
| `source` | `settings` 表示环境变量绑定，`runtime_config` 表示配置中心运行时文件绑定 |
| `updated_at` | 运行时文件更新时间；环境变量来源时为 `null` |
| `updated_by` | 最近通过配置中心更新的管理员 ID；环境变量来源时为 `null` |

运行时文件存在但损坏、缺少任一绑定字段、格式非法或不可读时返回 HTTP 503、`error_code=mineru_config_invalid`，不会混用或回退 `MINERU_API_TOKEN`、`MINERU_UID`。

## `PUT /api/v1/mineru-config`

请求：

```json
{"api_token": "new-token", "uid": "new-account-id"}
```

`api_token` 与 `uid` 都会去除首尾空白，结果必须分别为 1 到 4096、1 到 256 个字符。任一字段缺失、空白、超长或存在额外字段时返回 HTTP 422、`error_code=validation_error`，原绑定不变。

写入成功后：

- 新发起的 MinerU 上传、查询、下载和恢复请求立即使用新密钥与 UID；已创建的客户端不切换。
- callback checksum 每次先确认运行时绑定可读；payload 未携带 UID 时立即使用新运行时 UID，损坏文件即使遇到自带 UID 的 payload 也会明确失败。
- 记录 `mineru_config.update` 审计，目标为 `mineru_config/default`，details 只有 `api_token_configured=true` 与 `uid_configured=true`。
- 若配置文件已写入但审计仓储失败，返回 HTTP 503 并明确说明配置已保存；新绑定保持生效，管理员应刷新 GET 状态并修复审计仓储。

## 配置优先级

1. `var/config/mineru_config.json` 存在且合法时始终优先。
2. 文件不存在时共同使用 `MINERU_API_TOKEN` 与 `MINERU_UID`。
3. 文件存在但非法或缺少任一绑定字段时明确失败，不混用环境变量兜底。

当前生产基线中 API 与 Worker 共享 `md2word-var:/app/var`。代码回滚到不识别运行时文件的版本前，必须确认 `.env` 中仍有匹配的 `MINERU_API_TOKEN` 与 `MINERU_UID`。
