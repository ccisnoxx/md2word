from __future__ import annotations

# app/core/logging.py: 配置后端 access/business/system 日志格式和等级。

import json
import logging
from typing import Literal


LogFormat = Literal["text", "json"]

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "asctime",
    "message",
}


class JsonLogFormatter(logging.Formatter):
    """把标准 logging record 输出为单行 JSON，便于容器日志采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(app_env: str, log_format: LogFormat = "text") -> None:
    """按运行环境配置日志等级，并按 LOG_FORMAT 选择文本或 JSON 输出。"""

    level = logging.DEBUG if app_env in {"dev", "local", "test"} else logging.INFO
    if log_format == "json":
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    for logger_name in ("access", "business", "system"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(level)
        logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("python_multipart").setLevel(logging.INFO)
    logging.getLogger("python_multipart.multipart").setLevel(logging.INFO)
