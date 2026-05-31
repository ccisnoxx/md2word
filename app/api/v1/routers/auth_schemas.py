from __future__ import annotations

# app/api/v1/routers/auth_schemas.py: 定义 auth 路由私有的 v1 请求和响应模型。

from pydantic import BaseModel


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user_id: str
    username: str
    tenant_id: str
    company_id: str


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    role: str
    tenant_id: str
    company_id: str
    display_name: str | None = None
