from __future__ import annotations

# app/api/errors.py: 统一维护 API 边界的领域异常到 HTTP 响应映射。

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.conversion.contracts import ConversionFailure
from app.core.errors import ApiError, ApiErrorCode
from app.core.job_workflow import JobWorkflowViolation
from app.services.jobs.artifact_integrity import ArtifactFingerprintMismatch
from app.services.jobs.resource_snapshots import JobResourceSnapshotError


_STATUS_ERROR_CODES: dict[int, ApiErrorCode] = {
    status.HTTP_400_BAD_REQUEST: "invalid_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "file_too_large",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


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

    return api_error_response(_request, status.HTTP_409_CONFLICT, "job_state_conflict", exc.message)


async def _conversion_failure_handler(_request: Request, exc: ConversionFailure) -> JSONResponse:
    """把同步转换入口失败统一暴露为服务不可用。"""

    return api_error_response(_request, status.HTTP_503_SERVICE_UNAVAILABLE, "conversion_failed", exc.message)


async def _job_resource_snapshot_error_handler(_request: Request, exc: JobResourceSnapshotError) -> JSONResponse:
    """把资源快照绑定失败映射为创建 job 时的明确 HTTP 响应。"""

    return api_error_response(_request, exc.status_code, "resource_snapshot_error", exc.message)


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """把应用层 ApiError 输出为统一错误结构。"""

    return api_error_response(request, exc.status_code, exc.code, exc.message)


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """为现有 HTTPException 统一补充 error_code，同时保留原 detail 兼容字段。"""

    code, message = _code_and_message_from_detail(exc.status_code, exc.detail)
    return api_error_response(
        request,
        exc.status_code,
        code,
        message,
        detail=exc.detail,
        headers=exc.headers,
    )


async def _request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """把 FastAPI 请求校验错误纳入统一错误结构。"""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build_error_content(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "请求参数校验失败。",
            detail=exc.errors(),
        ),
    )


def api_error_response(
    request: Request,
    status_code: int,
    code: ApiErrorCode,
    message: str,
    *,
    detail: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """生成统一 API 错误响应；detail 字段保持向后兼容。"""

    return JSONResponse(
        status_code=status_code,
        content=_build_error_content(request, status_code, code, message, detail=detail),
        headers=headers,
    )


def _build_error_content(
    request: Request,
    status_code: int,
    code: ApiErrorCode,
    message: str,
    *,
    detail: object | None = None,
) -> dict[str, object]:
    trace_id = str(getattr(request.state, "trace_id", ""))
    return {
        "detail": message if detail is None else detail,
        "error_code": code,
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
            "trace_id": trace_id,
        },
    }


def _code_and_message_from_detail(status_code: int, detail: object) -> tuple[ApiErrorCode, str]:
    if isinstance(detail, dict):
        raw_code = detail.get("code")
        code = raw_code if isinstance(raw_code, str) else _STATUS_ERROR_CODES.get(status_code, "internal_error")
        raw_message = detail.get("message") or detail.get("detail")
        return code, str(raw_message) if raw_message is not None else str(detail)
    return _STATUS_ERROR_CODES.get(status_code, "internal_error"), str(detail)


def register_api_error_handlers(app: FastAPI) -> None:
    """注册当前 API 认可的领域异常映射。"""

    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _request_validation_exception_handler)
    app.add_exception_handler(JobWorkflowViolation, _job_workflow_violation_handler)
    app.add_exception_handler(ConversionFailure, _conversion_failure_handler)
    app.add_exception_handler(JobResourceSnapshotError, _job_resource_snapshot_error_handler)
