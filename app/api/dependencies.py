from __future__ import annotations

# app/api/dependencies.py: 提供 FastAPI 运行时、trace 和访问控制依赖。

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.audit_models import ActorContext
from app.core.runtime import AppRuntime


def get_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def get_trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", ""))


def require_jobs_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_jobs_actor(runtime, x_jobs_token, x_admin_token, None)


def require_jobs_actor(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    mode = runtime.settings.jobs_access_mode
    if mode == "open":
        return ActorContext(actor_id=None, actor_role="anonymous", source="open")
    if mode == "token":
        if not runtime.settings.jobs_access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JOBS_ACCESS_TOKEN 未配置，jobs token 模式不可用。",
            )
        if x_jobs_token != runtime.settings.jobs_access_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="jobs token 校验失败。",
            )
        return ActorContext(
            actor_id=_normalize_optional_text(x_actor_id) or "jobs-client",
            actor_role="jobs",
            source="jobs_token",
        )
    return require_admin_actor(runtime, x_admin_token, x_actor_id)


def require_job_ops_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_job_ops_actor(runtime, x_jobs_token, x_admin_token, None)


def require_job_ops_actor(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    if runtime.settings.jobs_ops_access_mode == "jobs":
        return require_jobs_actor(runtime, x_jobs_token, x_admin_token, x_actor_id)
    return require_admin_actor(runtime, x_admin_token, x_actor_id)


def require_admin_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    require_admin_actor(runtime, x_admin_token, None)


def require_admin_actor(
    runtime: AppRuntime = Depends(get_runtime),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> ActorContext:
    if not runtime.settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN 未配置，管理接口不可用。",
        )
    if x_admin_token != runtime.settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin token 校验失败。",
        )
    return ActorContext(
        actor_id=_normalize_optional_text(x_actor_id) or "admin",
        actor_role="admin",
        source="admin_token",
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
