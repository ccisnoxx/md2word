"""表格占位的真实转换失败：片段源页、文档范围错误与事件/API 定位合同。"""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.domains.document_jobs._failure_policy import worker_failure_evidence
from app.domains.document_jobs.failure_diagnostic import project_failure_diagnostic
from app.domains.document_jobs.models import DocumentJobEventRecord
from app.main import create_app
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.table_placeholder import PdfCropResult, PdfCropSource, TablePlaceholderError
from app.services.failure_context import FAILURE_CONTEXT_ATTRIBUTE, attach_failure_context
from tests import test_fastapi_jobs_backend as fixtures
from tests import test_document_ir_mineru_converter_layout as layout_fixtures
from tests.test_document_job_failure_diagnostic import _event, _zip


class TablePlaceholderFailureContextTests(TestCase):
    def setUp(self):
        self.crop = layout_fixtures._RecordingTableCropProvider("file_source", [(612, 792)] * 3)
        self.blocks = [{"type": "table", "html": "", "page_idx": 0, "bbox": [72, 80, 500, 250]}]
        self.layout = {"pdf_info": [{"page_idx": index, "page_size": [612, 792]} for index in range(3)]}

    def convert(self, *, blocks=None, layout=True, crop=..., source=None, loader=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mineru.zip"
            layout_fixtures.MinerUToDocumentIRLayoutTests._write_zip(
                self, path, blocks=self.blocks if blocks is None else blocks,
                layout=self.layout if layout else None,
            )
            return MinerUToDocumentIRService(pdf_crop_provider=self.crop if crop is ... else crop).convert_zip(
                path, job_id="job", source_file_id="file_source", document_language="en",
                placeholder_source_loader=loader if loader is not None else lambda: self.crop.source if source is None else source,
            )

    def diagnostic(self, error):
        payload = {"retry_count": 0, **worker_failure_evidence(error)}
        event = _event(payload)
        restored = DocumentJobEventRecord.model_validate_json(event.model_dump_json())
        self.assertEqual(restored.payload, payload)
        return project_failure_diagnostic(SimpleNamespace(status="failed", retry_count=0), [restored])

    def test_geometry_failure_on_first_source_page_survives_passing_validation(self):
        with self.assertRaises(TablePlaceholderError) as caught:
            self.convert(layout=False)
        error = caught.exception
        self.assertTrue(error.mineru_validation_report.can_convert)
        self.assertIsNone(error.mineru_validation_report.first_fatal)
        self.assertEqual(error.code, "table_placeholder_geometry_invalid")
        diagnostic = self.diagnostic(error)
        self.assertEqual((diagnostic.source, diagnostic.page_number, diagnostic.affected_page_numbers),
                         ("table_placeholder", 1, [1]))
        self.assertEqual((diagnostic.source_page_count, diagnostic.page_count_basis), (1, "content_blocks"))
        self.assertEqual(self.crop.requests, [])

    def test_cross_page_failure_uses_fragment_page_not_merged_owner(self):
        blocks = [
            {"type": "table", "html": "<table><tr><td>源表格</td></tr></table>", "page_idx": 0,
             "bbox": [72, 120, 500, 250]},
            {"type": "table_placeholder", "page_idx": 1, "bbox": [72, 80, 500, 250]},
            {"type": "table_placeholder", "page_idx": 2, "bbox": [72, 80, 500, 250]},
        ]
        error = TablePlaceholderError("table_placeholder_crop_failed")
        crop = Mock(crop=Mock(side_effect=error))
        with self.assertRaises(TablePlaceholderError) as caught:
            self.convert(blocks=blocks, crop=crop)
        self.assertIs(caught.exception, error)
        diagnostic = self.diagnostic(error)
        self.assertEqual((diagnostic.block_ids, diagnostic.page_number, diagnostic.affected_page_numbers),
                         (["block_0001"], 2, [2]))
        self.assertEqual((diagnostic.source_page_count, diagnostic.page_count_basis), (3, "mineru_layout"))
        self.assertEqual(crop.crop.call_count, 1)
        self.assertEqual(crop.crop.call_args.args[0].page_index, 1)
        self.assertEqual(error.mineru_validation_report.normalization["merged_table_placeholder_count"], 2)

    def test_unknown_fragment_page_is_document_scope(self):
        with self.assertRaises(TablePlaceholderError) as caught:
            self.convert(blocks=[{"type": "table", "html": "", "bbox": [72, 80, 500, 250]}], layout=False)
        diagnostic = self.diagnostic(caught.exception)
        self.assertEqual((diagnostic.scope, diagnostic.page_number, diagnostic.affected_page_numbers),
                         ("document", None, []))

    def test_source_unavailable_and_invalid_crop_image_keep_reason_and_page(self):
        cases = [
            (None, "table_placeholder_source_unavailable"),
            (Mock(crop=Mock(return_value=PdfCropResult(b"private-invalid-image", (612.0, 792.0)))),
             "table_placeholder_integrity_failed"),
        ]
        for provider, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(TablePlaceholderError) as caught:
                    self.convert(crop=provider)
                diagnostic = self.diagnostic(caught.exception)
                self.assertEqual((diagnostic.reason_code, diagnostic.page_number), (code, 1))

    def test_global_limits_and_source_identity_never_acquire_fragment_page(self):
        for limit in ("MAX_PLACEHOLDERS", "MAX_TOTAL_BYTES"):
            with self.subTest(limit=limit), patch(f"app.services.document_ir.table_placeholder.{limit}", 0):
                with self.assertRaises(TablePlaceholderError) as caught:
                    self.convert()
                diagnostic = self.diagnostic(caught.exception)
                self.assertEqual((diagnostic.reason_code, diagnostic.page_number, diagnostic.block_ids),
                                 ("table_placeholder_source_unavailable", None, []))
        for source in (
            PdfCropSource("wrong_file", self.crop.source.checksum_sha256, self.crop.source.content),
            PdfCropSource("file_source", "sha256:" + "0" * 64, self.crop.source.content),
        ):
            with self.subTest(source_id=source.file_id), self.assertRaises(TablePlaceholderError) as caught:
                self.convert(source=source)
            diagnostic = self.diagnostic(caught.exception)
            self.assertEqual((diagnostic.reason_code, diagnostic.scope, diagnostic.block_ids),
                             ("table_placeholder_integrity_failed", "document", []))

    def test_source_loader_integrity_failure_is_document_scope(self):
        # 正式 Worker 在返回 PdfCropSource 前就会检查对象身份、大小和 hash。
        error = TablePlaceholderError("table_placeholder_integrity_failed")
        with self.assertRaises(TablePlaceholderError) as caught:
            self.convert(loader=Mock(side_effect=error))
        self.assertIs(caught.exception, error)
        diagnostic = self.diagnostic(error)
        self.assertEqual((diagnostic.scope, diagnostic.page_number, diagnostic.block_ids),
                         ("document", None, []))

    def test_shared_helper_preserves_inner_context(self):
        error = TablePlaceholderError("table_placeholder_integrity_failed")
        attach_failure_context(error, operation_kind="table_placeholder", block_ids=[], source_page_index=None)
        original = getattr(error, FAILURE_CONTEXT_ATTRIBUTE)
        attach_failure_context(error, operation_kind="block", block_ids=["block_0001"], source_page_index=0)
        self.assertIs(getattr(error, FAILURE_CONTEXT_ATTRIBUTE), original)


class TablePlaceholderFailureApiTests(TestCase):
    def test_real_geometry_failure_reaches_event_detail_and_incident_api(self):
        blocks = [{"type": "text", "text": "首页", "page_idx": 0},
                  {"type": "table", "html": "", "page_idx": 1, "bbox": [72, 80, 500, 250]}]
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = _zip(blocks)
            crop = Mock()
            runtime.document_job_execution_service.document_ir_service.pdf_crop_provider = crop
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                created = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]})
                self.assertEqual(created.status_code, 201, created.text)
                job_id = created.json()["job_id"]
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                incidents = client.get(f"/api/v1/document-job-incidents/{job_id}/diagnostics", headers=headers).json()
                events = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers).json()["items"]
                listed = client.get("/api/v1/document-jobs", headers=headers).json()["items"]
        crop.crop.assert_not_called()
        self.assertEqual((detail["status"], detail["failed_stage"], detail["error_code"]),
                         ("failed", "ir_converting", "document_ir_failed"))
        diagnostic = detail["failure_diagnostic"]
        self.assertEqual((diagnostic["source"], diagnostic["reason_code"], diagnostic["page_number"]),
                         ("table_placeholder", "table_placeholder_geometry_invalid", 2))
        self.assertEqual(diagnostic["affected_page_numbers"], [2])
        self.assertEqual(incidents["failure_diagnostic"], diagnostic)
        self.assertEqual(incidents["item"]["failure_type"], "conversion_failed")
        self.assertTrue(all(item["failure_diagnostic"] is None for item in listed))
        failed = next(event for event in events if event["event_type"] == "stage_failed")
        self.assertEqual(failed["payload"]["retry_count"], 0)
        self.assertTrue(failed["payload"]["mineru_validation"]["can_convert"])
        self.assertIsNone(failed["payload"]["mineru_validation"]["first_fatal"])
        self.assertEqual(failed["payload"]["failure_context"]["source_page_index"], 1)
        self.assertEqual(json.loads(json.dumps(failed["payload"])), failed["payload"])
