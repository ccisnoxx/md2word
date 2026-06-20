from __future__ import annotations

# app/services/auth/models.py: 定义内部账号、角色和 JWT 认证后的用户上下文。

from pydantic import BaseModel, Field

from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus

InternalUser = InternalUserRecord


class AuthenticatedUser(BaseModel):
    """JWT 校验后在 API 依赖中传递的用户上下文。"""

    id: str
    username: str
    role: InternalUserRole
    tenant_id: str
    company_id: str
    department_id: str = "default_department"
    display_name: str | None = None
    token_version: int = 1
    token_scopes: list[str] = Field(default_factory=list)
