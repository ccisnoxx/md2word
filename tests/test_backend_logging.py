from __future__ import annotations

# tests/test_backend_logging.py: 覆盖后端日志格式配置的最小合同。

import json
import logging
from unittest import TestCase

from app.core.config import Settings
from app.core.logging import JsonLogFormatter, configure_logging


class BackendLoggingTests(TestCase):
    def tearDown(self) -> None:
        configure_logging("test")

    def test_settings_accepts_json_log_format(self) -> None:
        settings = Settings(_env_file=None, log_format="json")

        self.assertEqual(settings.log_format, "json")

    def test_json_log_formatter_outputs_single_json_record(self) -> None:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="[trace_id=%s method=%s path=%s status_code=%s duration_ms=%.1f]",
            args=("trace-json", "GET", "/api/v1/health/ready", 200, 1.5),
            exc_info=None,
        )

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["logger"], "access")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(
            payload["message"],
            "[trace_id=trace-json method=GET path=/api/v1/health/ready status_code=200 duration_ms=1.5]",
        )

    def test_configure_logging_installs_json_formatter(self) -> None:
        configure_logging("prod", "json")

        access_logger = logging.getLogger("access")

        self.assertIsInstance(access_logger.handlers[0].formatter, JsonLogFormatter)
        self.assertEqual(access_logger.level, logging.INFO)
