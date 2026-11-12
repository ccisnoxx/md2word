from __future__ import annotations

# app/api/middleware.py: HTTP 层的 trace_id 传递与访问/异常日志中间件。

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request


def install_trace_logging_middleware(app: FastAPI) -> None:
    """沿用或生成 X-Trace-Id，写入 request.state 与响应头，并按固定格式记录访问与未处理异常日志。"""

    access_logger = logging.getLogger("access")
    system_logger = logging.getLogger("system")

    @app.middleware("http")
    async def trace_logging_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
        request.state.trace_id = trace_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            system_logger.exception(
                "[trace_id=%s method=%s path=%s status=exception duration_ms=%.1f]",
                trace_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Trace-Id"] = trace_id
        access_logger.info(
            "[trace_id=%s method=%s path=%s status_code=%s duration_ms=%.1f]",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
