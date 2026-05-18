from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

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
    mode = runtime.settings.jobs_access_mode
    if mode == "open":
        return
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
        return
    require_admin_access(runtime, x_admin_token)


def require_job_ops_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    # 当前按用户要求复用普通 jobs 访问口径；后续若要收紧，只需在这里切回 admin/token 策略。
    require_jobs_access(runtime, x_jobs_token, x_admin_token)


def require_admin_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
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
