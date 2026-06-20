"""Pydantic schemas for internal user management APIs."""

from __future__ import annotations

# File: app/domains/users/schemas.py
# Purpose: Define safe request and response contracts for managed internal users.

from datetime import datetime

from pydantic import BaseModel

from app.domains.users.models import InternalUserRole, InternalUserStatus


class InternalUserResponse(BaseModel):
    id: str
    username: str
    normalized_username: str
    role: InternalUserRole
    tenant_id: str
    company_id: str
    department_id: str
    status: InternalUserStatus
    display_name: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None


class InternalUserListResponse(BaseModel):
    items: list[InternalUserResponse]
    total: int


class InternalUserCreateRequest(BaseModel):
    username: str
    display_name: str | None = None
    department_id: str = "default_department"
    role: InternalUserRole
    status: InternalUserStatus = "active"
    initial_password: str


class InternalUserUpdateRequest(BaseModel):
    display_name: str | None = None
    department_id: str | None = None
    role: InternalUserRole | None = None
    status: InternalUserStatus | None = None


class InternalUserResetPasswordRequest(BaseModel):
    new_password: str
