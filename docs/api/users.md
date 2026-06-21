---
doc_type: lib-api-ref
entry: users
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/users/router.py
  - app/domains/users/schemas.py
  - app/domains/users/service.py
  - app/domains/users/repository.py
  - app/services/auth/service.py
summary: Users API 提供 Admin-only 托管内部用户生命周期管理。
tags: [users, auth, api, admin]
last_reviewed: 2026-06-21
---

## 概述

Users API 管理内部 `admin` / `operator` 账号。托管用户仓库是运行时真源，
配置文件只在仓库为空时导入一次作为迁移/bootstrap 输入。

所有 `/api/v1/users` 接口都要求 Bearer JWT 且当前用户为 `admin`。响应模型不包含密码、密码 hash、JWT 或 secret。

## API 参考

### `GET /api/v1/users`

- 用途：列出内部用户。
- 鉴权：Admin Bearer JWT。
- Query：
  - `role`: `admin` 或 `operator`
  - `status`: `active` 或 `disabled`
  - `keyword`: 匹配用户名、normalized username、显示名或用户 id
- 响应：

```json
{
  "items": [
    {
      "id": "user_abc123",
      "username": "operator",
      "normalized_username": "operator",
      "role": "operator",
      "tenant_id": "default",
      "company_id": "default",
      "department_id": "default_department",
      "status": "active",
      "display_name": "交付人员",
      "created_at": "2026-06-21T00:00:00Z",
      "updated_at": "2026-06-21T00:00:00Z",
      "created_by": "user_admin",
      "updated_by": "user_admin"
    }
  ],
  "total": 1
}
```

### `POST /api/v1/users`

- 用途：创建内部用户。
- 鉴权：Admin Bearer JWT。
- 请求体：

```json
{
  "username": "operator",
  "display_name": "交付人员",
  "department_id": "default_department",
  "role": "operator",
  "status": "active",
  "initial_password": "change-me-password"
}
```

- 成功动作写入 `users.create` audit event。
- 用户名按大小写不敏感规则唯一。

### `PATCH /api/v1/users/{user_id}`

- 用途：更新显示名、部门、角色或状态。
- 鉴权：Admin Bearer JWT。
- 角色、部门或状态变化会增加 `token_version`，使该用户旧 token 失效。
- 禁止禁用或降级最后一个 active admin。
- 成功动作按变化写入 `users.update`、`users.disable` 或 `users.enable` audit event。

### `POST /api/v1/users/{user_id}/reset-password`

- 用途：管理员重置指定用户密码。
- 鉴权：Admin Bearer JWT。
- 请求体：

```json
{
  "new_password": "temporary-password"
}
```

- 成功后旧 token 失效，并写入 `users.reset_password` audit event。
- API 不返回新密码、旧密码或密码 hash。

## 错误矩阵

- 非 admin 调用：`403 role_forbidden`
- 用户不存在：`404 not_found`
- 用户名为空、密码为空或密码过短：`400 invalid_request`
- 用户名重复：`409 user_conflict`
- 禁用或降级最后一个 active admin：`409 last_admin_conflict`

## 运营注意事项

- 生产/准生产应使用 MySQL metadata store 并做好备份；file backend 只适合本地或单进程低并发环境。
- 仓库已有用户后，修改 `AUTH_INTERNAL_USERS_FILE` 不会自动更新运行时用户。
- 上线前至少确认两个 active admin 可登录，避免账号锁死。
