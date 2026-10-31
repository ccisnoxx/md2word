"""Quality/Review 与发布操作使用的局部安全 JSON 和禁止缓存边界。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api.errors import api_error_response
from app.core.errors import ApiError
from app.domains.document_jobs.schemas import QualityReviewErrorResponse


SAFE_INTERNAL_ERROR_MESSAGE = "服务内部错误，请凭 trace_id 联系管理员。"
_SYSTEM_LOGGER = logging.getLogger("system")
_NO_STORE_HEADER = {
    "description": "本操作的成功和错误响应均禁止缓存。",
    "schema": {"type": "string", "enum": ["no-store"]},
}
_TRACE_HEADER = {
    "description": "与错误正文 request_id/trace_id 一致的当次请求标识。",
    "schema": {"type": "string"},
}
QUALITY_REVIEW_RESPONSES: dict[int, dict[str, Any]] = {
    code: {
        "model": QualityReviewErrorResponse,
        "description": description,
        "headers": {"Cache-Control": _NO_STORE_HEADER, "X-Trace-Id": _TRACE_HEADER},
    }
    for code, description in {
        400: "游标无效。",
        401: "需要有效用户 JWT。",
        403: "任务归属或角色不允许访问。",
        404: "任务或已声明质量实物不存在。",
        409: "来源、证据或复核状态冲突；请刷新后核对。",
        422: "请求参数校验失败。",
        503: "已知存储或预览服务不可用。",
        500: "服务内部错误；复核可能已提交，请用 GET /review 与 /review/history 对账，勿自动重试批准。",
    }.items()
}
QUALITY_REVIEW_RESPONSES[200] = {
    "description": "已授权的当前观察或本次复核提交结果。",
    "headers": {"Cache-Control": _NO_STORE_HEADER, "X-Trace-Id": _TRACE_HEADER},
}
QUALITY_REVIEW_RESPONSES[500]["content"] = {
    "application/json": {
        "example": {
            "detail": SAFE_INTERNAL_ERROR_MESSAGE,
            "error_code": "internal_error",
            "request_id": "trace-example",
            "trace_id": "trace-example",
            "error": {
                "code": "internal_error",
                "message": SAFE_INTERNAL_ERROR_MESSAGE,
                "status_code": 500,
                "request_id": "trace-example",
                "trace_id": "trace-example",
            },
        }
    }
}


class QualityReviewApiRoute(APIRoute):
    """包住完整生成 handler，覆盖依赖、请求校验及响应序列化。"""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def quality_review_handler(request: Request) -> Response:
            try:
                try:
                    response = await original(request)
                except ApiError as error:
                    if self.path.endswith(("/publish", "/new-generation")) and error.code == "role_forbidden" and error.reason_code is None:
                        error.reason_code = "admin_required"
                    response = await request.app.exception_handlers[ApiError](request, error)
                except RequestValidationError as error:
                    if self.path.endswith(("/publish", "/new-generation")):
                        # Pydantic 的 ctx 可含 ValueError 或原始输入；这些命令入口只返回安全定位。
                        response = api_error_response(request, 422, "validation_error", "请求参数校验失败。",
                            detail=[{"loc": list(item["loc"]), "type": item["type"], "msg": "请求参数校验失败。"}
                                    for item in error.errors()])
                    else:
                        response = await request.app.exception_handlers[RequestValidationError](request, error)
                except StarletteHTTPException as error:
                    # 项目注册的是 FastAPI 子类；Starlette 基类也沿同一错误合同。
                    response = await request.app.exception_handlers[HTTPException](request, error)
                response.headers["Cache-Control"] = "no-store"
                return response
            except Exception as error:
                # 只记录可检索定位字段；异常正文、链和 traceback 可能带内容或对象路径。
                _SYSTEM_LOGGER.error(
                    "quality_review_api_unhandled_error trace_id=%s method=%s route=%s exception_type=%s",
                    getattr(request.state, "trace_id", ""),
                    request.method,
                    self.path,
                    type(error).__name__,
                )
                response = api_error_response(request, 500, "internal_error", SAFE_INTERNAL_ERROR_MESSAGE)
                response.headers["Cache-Control"] = "no-store"
                return response

        return quality_review_handler
