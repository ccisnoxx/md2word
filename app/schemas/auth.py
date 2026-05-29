from __future__ import annotations

# app/schemas/auth.py: 定义内部登录和当前用户 API 的 v1 请求/响应模型。

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

