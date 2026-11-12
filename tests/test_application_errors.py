"""应用层错误合同：错误码到 HTTP 状态的唯一映射，以及与旧 ApiError 的兼容关系。"""

from typing import get_args
from unittest import TestCase

from app.core.errors import (
    APPLICATION_ERROR_HTTP_STATUS,
    ApiError,
    ApplicationError,
    ApplicationErrorCode,
    http_status_for,
)


class ApplicationErrorContractTests(TestCase):
    def test_every_application_code_has_one_http_status(self):
        self.assertEqual(set(get_args(ApplicationErrorCode)), set(APPLICATION_ERROR_HTTP_STATUS))
        expected = {"invalid_request": 400, "validation_error": 422, "unauthorized": 401, "forbidden": 403,
                    "role_forbidden": 403, "not_found": 404, "conflict": 409, "service_unavailable": 503}
        self.assertEqual(APPLICATION_ERROR_HTTP_STATUS, expected)

    def test_application_error_carries_no_http_status(self):
        error = ApplicationError("conflict", "任务状态已变化。", reason_code="job_changed")
        self.assertFalse(hasattr(error, "status_code"))
        self.assertEqual((http_status_for(error), error.code, str(error), error.reason_code),
                         (409, "conflict", "任务状态已变化。", "job_changed"))

    def test_api_error_keeps_explicit_status_and_is_application_error(self):
        error = ApiError(503, "document_jobs_not_ready", "未就绪。")
        self.assertIsInstance(error, ApplicationError)
        self.assertEqual((http_status_for(error), error.status_code, error.code), (503, 503, "document_jobs_not_ready"))

    def test_unmapped_application_code_fails_at_raise_site(self):
        with self.assertRaises(ValueError):
            ApplicationError("document_jobs_not_ready", "未就绪。")

    def test_specific_code_with_category_maps_status_by_category(self):
        error = ApplicationError("resource_snapshot_missing_template", "缺少模板。", category="conflict")
        self.assertEqual((http_status_for(error), error.code, error.category), (409, "resource_snapshot_missing_template", "conflict"))
        with self.assertRaises(ValueError):
            ApplicationError("resource_snapshot_invalid", "非法快照。")

    def test_api_handler_keeps_specific_code_and_category_status(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.errors import register_api_error_handlers
        from app.domains.jobs.resource_snapshots import JobResourceSnapshotError

        app = FastAPI()
        register_api_error_handlers(app)

        @app.get("/translated")
        def translated():
            source = JobResourceSnapshotError("Translation Term Set 不存在。", category="not_found",
                                              code="translation_term_set_not_found")
            raise ApplicationError(source.code, source.message, category=source.category)

        @app.get("/raw")
        def raw():
            raise JobResourceSnapshotError("资源版本服务不可用。", category="service_unavailable")

        with TestClient(app) as client:
            translated_response = client.get("/translated")
            raw_response = client.get("/raw")
        self.assertEqual((translated_response.status_code, translated_response.json()["error_code"]),
                         (404, "translation_term_set_not_found"))
        self.assertEqual((raw_response.status_code, raw_response.json()["error_code"]),
                         (503, "resource_snapshot_error"))
