from __future__ import annotations

# app/core/errors.py: 定义 API 可复用的错误码和应用层异常。

from dataclasses import dataclass
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
    "resource_snapshot_error",
    "internal_error",
]


@dataclass(slots=True)
class ApiError(Exception):
    """应用层主动抛出的 API 错误，携带稳定错误码和 HTTP 状态。"""

    status_code: int
    code: ApiErrorCode
    message: str

    def __str__(self) -> str:
        return self.message
