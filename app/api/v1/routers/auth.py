from __future__ import annotations

# app/api/v1/routers/auth.py: 提供内部账号登录和当前用户查询接口。

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_runtime, get_trace_id, require_current_user
from app.core.audit_models import ActorContext
from app.core.auth_models import AuthenticatedUser
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.schemas.auth import AuthLoginRequest, AuthTokenResponse, CurrentUserResponse
from app.services.auth.service import AuthConfigurationError, InvalidCredentialsError


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthTokenResponse)
def login(
    request: AuthLoginRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> AuthTokenResponse:
    try:
        user = runtime.auth_service.authenticate(request.username, request.password)
        token = runtime.auth_service.issue_access_token(user)
    except AuthConfigurationError as exc:
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unconfigured", str(exc)) from exc
    except InvalidCredentialsError as exc:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", str(exc)) from exc

    runtime.audit_service.record(
        actor=ActorContext(actor_id=user.id, actor_role=user.role, source="jwt"),
        action="auth.login",
        target_type="user",
        target_id=user.id,
        trace_id=trace_id,
    )
    return AuthTokenResponse(
        access_token=token.access_token,
        expires_in=token.expires_in_seconds,
        role=user.role,
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        company_id=user.company_id,
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(user: AuthenticatedUser = Depends(require_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
        company_id=user.company_id,
        display_name=user.display_name,
    )
