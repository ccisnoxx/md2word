from __future__ import annotations

# app/services/auth/models.py: 定义内部账号、角色和 JWT 认证后的用户上下文。

from typing import Literal

from pydantic import BaseModel, Field


InternalUserRole = Literal["admin", "operator"]
InternalUserStatus = Literal["active", "disabled"]


class InternalUser(BaseModel):
    """MVP 内部账号记录；P0 先从配置加载，后续可迁移到 users 表。"""

    id: str
    username: str
    password_hash: str
    role: InternalUserRole
    tenant_id: str = "default"
    company_id: str = "default"
    status: InternalUserStatus = "active"
    display_name: str | None = None


class AuthenticatedUser(BaseModel):
    """JWT 校验后在 API 依赖中传递的用户上下文。"""

    id: str
    username: str
    role: InternalUserRole
    tenant_id: str
    company_id: str
    display_name: str | None = None
    token_scopes: list[str] = Field(default_factory=list)
