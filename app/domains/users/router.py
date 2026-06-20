"""Admin HTTP API for managed internal users."""

from __future__ import annotations

# File: app/domains/users/router.py
# Purpose: Expose admin-only internal user lifecycle endpoints.

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus
from app.domains.users.schemas import (
    InternalUserCreateRequest,
    InternalUserListResponse,
    InternalUserResetPasswordRequest,
    InternalUserResponse,
    InternalUserUpdateRequest,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=InternalUserListResponse)
def list_internal_users(
    role: InternalUserRole | None = None,
    status_value: Annotated[InternalUserStatus | None, Query(alias="status")] = None,
    keyword: str | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> InternalUserListResponse:
    """Return a safe admin-only list of managed internal users."""

    records = runtime.internal_user_management_service.list_users(
        role=role,
        status=status_value,
        keyword=keyword,
    )
    return InternalUserListResponse(items=[_build_user_response(record) for record in records], total=len(records))


@router.post("", response_model=InternalUserResponse, status_code=status.HTTP_201_CREATED)
def create_internal_user(
    request: InternalUserCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> InternalUserResponse:
    """Create a managed internal user without returning the provided password."""

    record = runtime.internal_user_management_service.create_user(
        username=request.username,
        display_name=request.display_name,
        role=request.role,
        status=request.status,
        initial_password=request.initial_password,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="users.create",
        target_type="user",
        target_id=record.id,
        trace_id=trace_id,
        details={
            "username": record.username,
            "role": record.role,
            "status": record.status,
            "display_name": record.display_name,
        },
    )
    return _build_user_response(record)


@router.patch("/{user_id}", response_model=InternalUserResponse)
def update_internal_user(
    user_id: str,
    request: InternalUserUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> InternalUserResponse:
    """Update safe fields for one managed user."""

    result = runtime.internal_user_management_service.update_user(
        user_id,
        display_name=request.display_name,
        display_name_provided="display_name" in request.model_fields_set,
        role=request.role,
        status_value=request.status,
        actor_id=user.id,
    )
    action = "users.update"
    if result.status_changed_to == "disabled":
        action = "users.disable"
    elif result.status_changed_to == "active":
        action = "users.enable"
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action=action,
        target_type="user",
        target_id=result.user.id,
        trace_id=trace_id,
        details={
            "changed_fields": result.changed_fields,
            "role": result.user.role,
            "status": result.user.status,
            "display_name": result.user.display_name,
        },
    )
    return _build_user_response(result.user)


@router.post("/{user_id}/reset-password", response_model=InternalUserResponse)
def reset_internal_user_password(
    user_id: str,
    request: InternalUserResetPasswordRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> InternalUserResponse:
    """Reset a managed user's password without exposing old or new password values."""

    record = runtime.internal_user_management_service.reset_password(
        user_id,
        new_password=request.new_password,
        actor_id=user.id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="users.reset_password",
        target_type="user",
        target_id=record.id,
        trace_id=trace_id,
        details={"password_reset": True},
    )
    return _build_user_response(record)


def _build_user_response(record: InternalUserRecord) -> InternalUserResponse:
    """Map a repository user record to the safe API response shape."""

    return InternalUserResponse(
        id=record.id,
        username=record.username,
        normalized_username=record.normalized_username,
        role=record.role,
        tenant_id=record.tenant_id,
        company_id=record.company_id,
        status=record.status,
        display_name=record.display_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        created_by=record.created_by,
        updated_by=record.updated_by,
    )


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
