from __future__ import annotations

# app/api/dependencies.py: 提供 FastAPI 运行时、trace 和访问控制依赖。

from fastapi import Depends, Header, Request, status

from app.domains.audit.models import ActorContext
from app.services.auth.models import AuthenticatedUser
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.services.auth.service import AuthConfigurationError, TokenValidationError


def get_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def get_trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", ""))


def require_jobs_access(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_jobs_actor(runtime, authorization, x_jobs_token, x_admin_token, None)


def require_jobs_actor(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    jwt_user = _optional_jwt_user(runtime, authorization)
    if jwt_user is not None:
        return _actor_from_user(jwt_user)

    mode = runtime.settings.jobs_access_mode
    if mode == "open":
        return ActorContext(actor_id=None, actor_role="anonymous", source="open")
    if mode == "token":
        if not runtime.settings.jobs_access_token:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "service_unavailable",
                "JOBS_ACCESS_TOKEN 未配置，jobs token 模式不可用。",
            )
        if x_jobs_token != runtime.settings.jobs_access_token:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "jobs token 校验失败。",
            )
        return ActorContext(
            actor_id=_normalize_optional_text(x_actor_id) or "jobs-client",
            actor_role="jobs",
            source="jobs_token",
        )
    return require_admin_actor(runtime, None, x_admin_token, x_actor_id)


def require_job_ops_access(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_job_ops_actor(runtime, authorization, x_jobs_token, x_admin_token, None)


def require_job_ops_actor(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    if runtime.settings.jobs_ops_access_mode == "jobs":
        return require_jobs_actor(runtime, authorization, x_jobs_token, x_admin_token, x_actor_id)
    return require_admin_actor(runtime, authorization, x_admin_token, x_actor_id)


def require_admin_access(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_admin_actor(runtime, authorization, x_admin_token, None)


def require_authenticated_or_admin_access(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """允许内部用户 JWT 或 legacy admin token 读取治理资源，禁止匿名访问。"""

    if _optional_jwt_user(runtime, authorization) is not None:
        return
    require_admin_actor(runtime, None, x_admin_token, None)


def require_admin_actor(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    jwt_user = _optional_jwt_user(runtime, authorization)
    if jwt_user is not None:
        if jwt_user.role != "admin":
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "role_forbidden",
                "当前角色无权限执行该操作。",
            )
        return _actor_from_user(jwt_user)

    if not runtime.settings.admin_token:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_unavailable",
            "ADMIN_TOKEN 未配置，管理接口不可用。",
        )
    if x_admin_token != runtime.settings.admin_token:
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "admin token 校验失败。",
        )
    return ActorContext(
        actor_id=_normalize_optional_text(x_actor_id) or "admin",
        actor_role="admin",
        source="admin_token",
    )


def require_current_user(
    runtime: AppRuntime = Depends(get_runtime),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """要求 Bearer JWT，并返回当前内部用户。"""

    return _required_jwt_user(runtime, authorization)


def require_admin_user(
    user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    """要求当前 JWT 用户是 admin。"""

    if user.role != "admin":
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "role_forbidden",
            "当前角色无权限执行该操作。",
        )
    return user


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _optional_jwt_user(runtime: AppRuntime, authorization: str | None) -> AuthenticatedUser | None:
    token = _extract_bearer_token(authorization, required=False)
    if token is None:
        return None
    return _validate_token(runtime, token)


def _required_jwt_user(runtime: AppRuntime, authorization: str | None) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization, required=True)
    return _validate_token(runtime, token)


def _extract_bearer_token(authorization: str | None, *, required: bool) -> str | None:
    normalized = _normalize_optional_text(authorization)
    if normalized is None:
        if required:
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", "缺少 Bearer token。")
        return None
    scheme, _, token = normalized.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_token", "Authorization 必须使用 Bearer token。")
    return token.strip()


def _validate_token(runtime: AppRuntime, token: str) -> AuthenticatedUser:
    try:
        return runtime.auth_service.authenticate_bearer_token(token)
    except AuthConfigurationError as exc:
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unconfigured", str(exc)) from exc
    except TokenValidationError as exc:
        error_code = "token_expired" if exc.code == "token_expired" else "invalid_token"
        raise ApiError(status.HTTP_401_UNAUTHORIZED, error_code, exc.message) from exc


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(
        actor_id=user.id,
        actor_role=user.role,
        source="jwt",
    )
