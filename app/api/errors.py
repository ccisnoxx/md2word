from __future__ import annotations

# app/api/errors.py: 统一维护 API 边界的领域异常到 HTTP 响应映射。

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.conversion.contracts import ConversionFailure
from app.core.job_workflow import JobWorkflowViolation
from app.services.jobs.artifact_integrity import ArtifactFingerprintMismatch
from app.services.jobs.resource_snapshots import JobResourceSnapshotError


def not_found_http_exception(exc: FileNotFoundError) -> HTTPException:
    """把资源缺失异常映射为稳定的 404 响应。"""

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def bad_request_http_exception(exc: ValueError) -> HTTPException:
    """把边界输入异常映射为稳定的 400 响应。"""

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def artifact_download_http_exception(exc: FileNotFoundError | ValueError) -> HTTPException:
    """把 artifact storage 的本地异常映射为稳定的下载接口 HTTP 错误。"""

    if isinstance(exc, ArtifactFingerprintMismatch):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return not_found_http_exception(exc)
    return bad_request_http_exception(exc)


async def _job_workflow_violation_handler(_request: Request, exc: JobWorkflowViolation) -> JSONResponse:
    """把 workflow policy 拒绝统一暴露为 409 conflict。"""

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message},
    )


async def _conversion_failure_handler(_request: Request, exc: ConversionFailure) -> JSONResponse:
    """把同步转换入口失败统一暴露为服务不可用。"""

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": exc.message},
    )


async def _job_resource_snapshot_error_handler(_request: Request, exc: JobResourceSnapshotError) -> JSONResponse:
    """把资源快照绑定失败映射为创建 job 时的明确 HTTP 响应。"""

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


def register_api_error_handlers(app: FastAPI) -> None:
    """注册当前 API 认可的领域异常映射。"""

    app.add_exception_handler(JobWorkflowViolation, _job_workflow_violation_handler)
    app.add_exception_handler(ConversionFailure, _conversion_failure_handler)
    app.add_exception_handler(JobResourceSnapshotError, _job_resource_snapshot_error_handler)
