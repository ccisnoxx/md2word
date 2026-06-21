---
doc_type: lib-api-ref
entry: auth
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/auth.py
  - app/api/v1/routers/auth_schemas.py
  - app/services/auth/service.py
  - app/services/auth/permissions.py
summary: Auth API 提供内部账号登录、当前用户查询和当前用户自助修改密码。
tags: [auth, users, api]
last_reviewed: 2026-06-21
---

## 概述

Auth API 使用托管内部用户仓库作为运行时账号真源。`AUTH_INTERNAL_USERS_FILE`
和 `AUTH_INTERNAL_USERS_JSON` 只在仓库为空时做一次 bootstrap 导入；仓库已有用户后不会继续合并配置用户。

当前角色只支持 `admin` 和 `operator`。权限由 `app/services/auth/permissions.py`
按角色派生，不支持自定义权限矩阵、SSO、MFA、自注册或邮件重置。

## API 参考

### `POST /api/v1/auth/login`

- 用途：使用内部账号密码登录并获取 Bearer JWT。
- 请求体：

```json
{
  "username": "admin",
  "password": "change-me-password"
}
```

- 响应包含访问 token、过期秒数、角色、权限、用户 id、租户/公司/部门字段。
- 失败：
  - 仓库为空或 JWT secret 未配置：`503 auth_unconfigured`
  - 用户名、密码错误或账号停用：`401 invalid_credentials`

### `GET /api/v1/auth/me`

- 用途：返回当前 Bearer JWT 对应用户和权限 claims。
- 鉴权：Bearer JWT。
- 响应不包含 `password_hash`、密码、JWT 或 token version。
- token 校验会重新读取托管用户仓库；账号被停用或 token version 已变化时，旧 token 会失效。

### `POST /api/v1/auth/change-password`

- 用途：当前登录用户自助修改密码。
- 鉴权：Bearer JWT。
- 请求体：

```json
{
  "current_password": "old-password",
  "new_password": "new-password"
}
```

- 成功后密码 hash 更新，用户 `token_version` 增加，旧 token 失效。
- 成功动作写入 `auth.change_password` audit event。
- 失败：
  - 当前密码错误：`400 invalid_request`
  - 新密码为空或不满足最小长度：`400 invalid_request`
  - token 无效或过期：`401 invalid_token` / `401 token_expired`

## 安全边界

- API 响应不得返回密码、密码 hash、JWT、secret、配置文件原文或 token version。
- 日常账号运营通过 `/api/v1/users`，不要通过编辑配置文件覆盖托管仓库。
- 更换 `AUTH_JWT_SECRET_KEY` 仍会使所有现有 token 失效。
