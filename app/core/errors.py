from __future__ import annotations

# app/core/errors.py: 定义稳定错误码、应用层业务错误，以及错误码到 HTTP 状态的唯一映射。

from typing import Literal


ApiErrorCode = Literal[
    "invalid_request",
    "validation_error",
    "unauthorized",
    "invalid_credentials",
    "invalid_token",
    "token_expired",
    "forbidden",
    "role_forbidden",
    "not_found",
    "conflict",
    "user_conflict",
    "last_admin_conflict",
    "file_too_large",
    "service_unavailable",
    "auth_unconfigured",
    "job_state_conflict",
    "conversion_failed",
    "document_jobs_not_ready",
    "mineru_config_invalid",
    "resource_snapshot_error",
    "internal_error",
]

ApplicationErrorCode = Literal[
    "invalid_request",
    "validation_error",
    "unauthorized",
    "forbidden",
    "role_forbidden",
    "not_found",
    "conflict",
    "service_unavailable",
]

# 应用层只表达语义错误码；HTTP 状态只在这里决定，API 处理器与批量条目投影都经 http_status_for 读取。
APPLICATION_ERROR_HTTP_STATUS: dict[str, int] = {
    "invalid_request": 400,
    "validation_error": 422,
    "unauthorized": 401,
    "forbidden": 403,
    "role_forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "service_unavailable": 503,
}


class ApplicationError(Exception):
    """应用层业务错误：只携带稳定错误码、对外消息与可选原因码，不选择 HTTP 状态。"""

    def __init__(self, code: ApplicationErrorCode, message: str, *, reason_code: str | None = None) -> None:
        if not isinstance(self, ApiError) and code not in APPLICATION_ERROR_HTTP_STATUS:
            # 未映射的错误码会在响应时退化为 500，在抛出点直接暴露为编程错误。
            raise ValueError(f"未登记 HTTP 状态映射的应用层错误码: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason_code = reason_code

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r}, reason_code={self.reason_code!r})"


class ApiError(ApplicationError):
    """HTTP 层或尚未迁移领域使用的错误，显式携带 HTTP 状态；构造签名保持 (status_code, code, message)。"""

    def __init__(self, status_code: int, code: ApiErrorCode, message: str, *, reason_code: str | None = None) -> None:
        super().__init__(code, message, reason_code=reason_code)
        self.status_code = status_code

    def __repr__(self) -> str:
        return (f"ApiError(status_code={self.status_code!r}, code={self.code!r}, message={self.message!r}, "
                f"reason_code={self.reason_code!r})")


def http_status_for(error: ApplicationError) -> int:
    """返回错误对应的 HTTP 状态：ApiError 用其显式状态，其余按错误码映射。"""

    if isinstance(error, ApiError):
        return error.status_code
    return APPLICATION_ERROR_HTTP_STATUS[error.code]
