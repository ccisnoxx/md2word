"""验证 MinerU 验证失败的定位投影：纯函数边界与真实 Worker 失败链路的 API 输出。"""
import io
import json
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image

from app.domains.document_jobs.failure_diagnostic import project_failure_diagnostic
from app.domains.document_jobs.models import DocumentJobEventRecord
from app.domains.resources.models import utc_now
from app.main import create_app
from tests import test_fastapi_jobs_backend as fixtures


def _event(payload, *, event_type="stage_failed", stage="ir_converting", age=0):
    return DocumentJobEventRecord(
        id=f"event_{age}", tenant_id="t", company_id="c", job_id="job", created_by="u",
        stage=stage, level="error", event_type=event_type, message="失败", payload=payload,
        created_at=utc_now() - timedelta(seconds=age),
    )


def _report(first, blockers=(), **extra):
    return {"can_convert": False, "first_fatal": first, "blockers": list(blockers),
            "fatal_count": len(blockers), "warning_count": 1, "details_truncated": False, **extra}


IMAGE_ISSUE = {"code": "invalid_image_asset", "page_index": 12, "source_type": "image",
               "json_pointer": "/content_list/148", "stops_conversion": True,
               "facts": {"reason": "unreadable_or_unsupported_image"}}


class ProjectFailureDiagnosticTests(TestCase):
    job = SimpleNamespace(status="failed", retry_count=1)

    def test_page_failure_projects_one_based_pages_and_reason(self):
        second = {**IMAGE_ISSUE, "page_index": 3, "json_pointer": "/content_list/40"}
        payload = {"retry_count": 1, "mineru_validation": _report(IMAGE_ISSUE, [IMAGE_ISSUE, second, IMAGE_ISSUE])}
        result = project_failure_diagnostic(self.job, [_event(payload)])
        self.assertEqual(result.model_dump(), {
            "source": "mineru_validation", "stage": "ir_converting", "scope": "page", "page_number": 13,
            "source_type": "image", "json_pointer": "/content_list/148", "reason_code": "invalid_image_asset",
            "reason": "unreadable_or_unsupported_image", "affected_page_numbers": [4, 13],
            "fatal_count": 3, "warning_count": 1, "details_truncated": False, "block_ids": [], "operation_kind": None,
        })

    def test_document_failure_has_no_page(self):
        first = {"code": "mineru_package_limit_exceeded", "page_index": None, "json_pointer": "",
                 "facts": {"reason": "total_bytes"}}
        payload = {"retry_count": 1, "mineru_validation": _report(first, [first], details_truncated=True)}
        result = project_failure_diagnostic(self.job, [_event(payload)])
        self.assertEqual((result.scope, result.page_number, result.json_pointer, result.affected_page_numbers),
                         ("document", None, None, []))
        self.assertEqual(result.reason, "total_bytes")
        self.assertTrue(result.details_truncated)

    def test_latest_current_generation_event_wins(self):
        old = _event({"retry_count": 0, "mineru_validation": _report({**IMAGE_ISSUE, "page_index": 0})})
        current = _event({"retry_count": 1, "mineru_validation": _report(IMAGE_ISSUE)}, age=5)
        newer_other = _event({"retry_count": 1, "error_code": "oss_failed"})
        result = project_failure_diagnostic(self.job, [old, current, newer_other])
        self.assertEqual(result.page_number, 13)

    def test_no_diagnostic_without_trustworthy_current_failure(self):
        report = _report(IMAGE_ISSUE)
        cases = {
            "旧代": (self.job, [_event({"retry_count": 0, "mineru_validation": report})]),
            "缺代数": (self.job, [_event({"mineru_validation": report})]),
            "代数类型错误": (self.job, [_event({"retry_count": True, "mineru_validation": report})]),
            "非失败事件": (self.job, [_event({"retry_count": 1, "mineru_validation": report}, event_type="stage_started")]),
            "报告可转换": (self.job, [_event({"retry_count": 1, "mineru_validation": {**report, "can_convert": True}})]),
            "无首个失败": (self.job, [_event({"retry_count": 1, "mineru_validation": {**report, "first_fatal": None}})]),
            "首个失败无代码": (self.job, [_event({"retry_count": 1, "mineru_validation": _report({"page_index": 2})})]),
            "任务未失败": (SimpleNamespace(status="succeeded", retry_count=1),
                       [_event({"retry_count": 1, "mineru_validation": report})]),
        }
        for name, (job, events) in cases.items():
            with self.subTest(name):
                self.assertIsNone(project_failure_diagnostic(job, events))

    def test_malformed_fields_are_narrowed_not_trusted(self):
        first = {"code": "invalid_image_asset", "page_index": -1, "source_type": 7, "json_pointer": ["x"],
                 "facts": {"reason": {"nested": True}}}
        blockers = [{"page_index": "2", "stops_conversion": True}, {"page_index": 4, "stops_conversion": "yes"}, "bad"]
        report = {**_report(first, blockers), "fatal_count": "3", "warning_count": -2, "details_truncated": "true"}
        result = project_failure_diagnostic(self.job, [_event({"retry_count": 1, "mineru_validation": report})])
        self.assertEqual(result.model_dump(exclude={"stage", "source"}), {
            "scope": "document", "page_number": None, "source_type": None, "json_pointer": None,
            "reason_code": "invalid_image_asset", "reason": None, "affected_page_numbers": [],
            "fatal_count": 0, "warning_count": 0, "details_truncated": False, "block_ids": [], "operation_kind": None,
        })


def _unreadable_image_bytes():
    """截断的 PNG：Pillow 安全解码失败；WebP 等可解码格式现会被规范化，不能再用来制造失败。"""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()[:40]


def _zip(blocks=None, images=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if blocks is not None:
            archive.writestr("content_list_v2.json", json.dumps(blocks))
        for path in images:
            archive.writestr(path, _unreadable_image_bytes())
    return buffer.getvalue()


class FailureDiagnosticApiTests(TestCase):
    def _run_failed_job(self, zip_bytes, *, extra=None):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = zip_bytes
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                created = client.post("/api/v1/document-jobs", headers=headers,
                                      json={"source_file_id": source["id"], **(extra or {})})
                self.assertEqual(created.status_code, 201, created.text)
                job_id = created.json()["job_id"]
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                listed = client.get("/api/v1/document-jobs", headers=headers).json()["items"]
                diagnostics = client.get(f"/api/v1/document-job-incidents/{job_id}/diagnostics", headers=headers).json()
        return detail, listed, diagnostics

    def test_unreadable_images_report_pages_and_classify_as_conversion(self):
        blocks = [
            {"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "Body", "page_idx": 1},
            {"type": "image", "img_path": "images/a.webp", "page_idx": 2},
            {"type": "text", "text": "Body", "page_idx": 3},
            {"type": "image", "img_path": "images/b.webp", "page_idx": 4},
        ]
        detail, listed, diagnostics = self._run_failed_job(
            _zip(blocks, ["images/a.webp", "images/b.webp"]), extra={"translation_mode": "en2zh"})
        self.assertEqual((detail["status"], detail["failed_stage"], detail["error_code"]),
                         ("failed", "ir_converting", "document_ir_failed"))
        expected = {
            "source": "mineru_validation", "stage": "ir_converting", "scope": "page", "page_number": 3,
            "source_type": "image", "json_pointer": "/2", "reason_code": "invalid_image_asset",
            "reason": "unreadable_or_unsupported_image", "affected_page_numbers": [3, 5],
            "fatal_count": 2, "warning_count": 5, "details_truncated": False, "block_ids": [], "operation_kind": None,
        }
        self.assertEqual(detail["failure_diagnostic"], expected)
        self.assertEqual(diagnostics["failure_diagnostic"], expected)
        self.assertIsNone(diagnostics["item"]["job"]["failure_diagnostic"])
        self.assertTrue(all(item["failure_diagnostic"] is None for item in listed))
        self.assertEqual(diagnostics["item"]["failure_type"], "conversion_failed")

    def test_document_level_failure_does_not_invent_a_page(self):
        detail, _listed, diagnostics = self._run_failed_job(_zip(None, ["images/a.webp"]))
        diagnostic = detail["failure_diagnostic"]
        self.assertEqual((diagnostic["scope"], diagnostic["page_number"], diagnostic["affected_page_numbers"]),
                         ("document", None, []))
        self.assertEqual(diagnostic["reason_code"], "mineru_content_list_missing")
        self.assertEqual(diagnostics["failure_diagnostic"], diagnostic)
        self.assertEqual(diagnostics["item"]["failure_type"], "conversion_failed")


class IncidentClassificationTests(TestCase):
    def test_error_code_wins_over_keyword_heuristics(self):
        from app.domains.document_jobs.incidents import DocumentJobIncidentService
        service = DocumentJobIncidentService(None)
        base = {"status": "failed", "mode": "en2zh_pdf_to_word", "review_status": "unreviewed",
                "translation_qa_status": "unreviewed", "translation_qa_issue_type": None, "translation_qa_note": None,
                "result_file_id": None, "document_ir_file_id": None}
        cases = [
            ({"failed_stage": "ir_converting", "error_code": "document_ir_failed",
              "error_message": "MinerU 产物验证失败：missing_image_asset。"}, "conversion_failed"),
            ({"failed_stage": "ir_converting", "error_code": "translation_failed",
              "error_message": "历史翻译失败"}, "translation_failed"),
            ({"failed_stage": "ir_converting", "error_code": "oss_failed",
              "error_message": "存储失败"}, "conversion_failed"),
        ]
        for fields, expected in cases:
            with self.subTest(fields["error_code"]):
                job = SimpleNamespace(**base, **fields)
                self.assertEqual(service._classify_failure(job, stalled=False), expected)
