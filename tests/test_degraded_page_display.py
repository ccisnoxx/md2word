"""第三批 C4：降级页进入基础质量摘要与异常中心；翻译跳过合成块并记录跳过页。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.main import create_app
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from tests import test_fastapi_jobs_backend as fixtures
from tests.test_page_degradation import _FakeRasterizer, _three_pages
from tests.test_translation_integrity_execution import ControlledProvider


def _zip(blocks):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list.json", json.dumps(blocks))
    return buffer.getvalue()


class DegradedPageDisplayApiTests(TestCase):
    def test_detail_and_incident_queue_list_degraded_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            service = runtime.document_job_execution_service
            service.document_ir_service.page_rasterizer = _FakeRasterizer()
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                service.fake_mineru_client.result_zip_bytes = _zip(_three_pages())
                degraded_id = client.post("/api/v1/document-jobs", headers=headers,
                                          json={"source_file_id": source["id"]}).json()["job_id"]
                service.fake_mineru_client.result_zip_bytes = _zip(
                    [{"type": "text", "text": f"Page {index}", "page_idx": index} for index in range(3)])
                second = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                clean_id = client.post("/api/v1/document-jobs", headers=headers,
                                       json={"source_file_id": second["id"]}).json()["job_id"]
                detail = client.get(f"/api/v1/document-jobs/{degraded_id}", headers=headers).json()
                clean = client.get(f"/api/v1/document-jobs/{clean_id}", headers=headers).json()
                queue = client.get("/api/v1/document-job-incidents", headers=headers).json()
                filtered = client.get("/api/v1/document-job-incidents", headers=headers,
                                      params={"failure_type": "page_degraded"}).json()
                diagnostics = client.get(f"/api/v1/document-job-incidents/{degraded_id}/diagnostics", headers=headers).json()
        self.assertEqual((detail["status"], clean["status"]), ("succeeded", "succeeded"))
        self.assertEqual(detail["quality_summary"]["checks_v1"]["document_base"]["degraded_pages"],
                         [{"page_number": 2, "trigger": "validation", "reason_codes": ["invalid_table_html"]}])
        self.assertNotIn("degraded_pages", clean["quality_summary"]["checks_v1"]["document_base"])
        items = {item["job"]["id"]: item for item in queue["items"]}
        self.assertNotIn(clean_id, items)
        item = items[degraded_id]
        self.assertEqual((item["failure_type"], item["retryable"], item["priority"]), ("page_degraded", False, 2))
        self.assertIn("第 2 页", item["suggested_action"])
        self.assertIn("第 2 页验证阶段降级：invalid_table_html", item["evidence_summary"])
        self.assertEqual([entry["job"]["id"] for entry in filtered["items"]], [degraded_id])
        self.assertEqual(diagnostics["item"]["failure_type"], "page_degraded")


class DegradedSourceTranslationTests(TestCase):
    def test_synthetic_blocks_are_not_translated_and_skipped_pages_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = fixtures.build_test_runtime(root / "runtime", jobs_artifact_storage_backend="local_object")
            execution = runtime.document_job_execution_service
            provider = ControlledProvider()
            execution.document_ir_translation_service = DocumentIRTranslationService(provider)
            pdf = b"%PDF-1.4 degradation-source"
            source_pdf = runtime.file_upload_service.register_generated_content(
                tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
                file_type="source_pdf", filename="source.pdf", mime_type="application/pdf", content=pdf,
            )
            job = runtime.document_job_repository.create_document_job(DocumentJobRecord(
                id="job", tenant_id="tenant", company_id="company", created_by="operator",
                source_file_id=source_pdf.id, mode="en2zh_pdf_to_word", document_language="en",
                status="running", stage="ir_converting",
                template_version_id=execution.template_read_service.resolve_template_version(None).template_version_id,
            ))
            content = _zip(_three_pages())
            raw = runtime.file_upload_service.register_generated_content(
                tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
                file_type="mineru_raw_result", filename="mineru.zip", mime_type="application/zip", content=content,
            )
            zip_path = root / "source.zip"
            zip_path.write_bytes(content)
            execution.document_ir_service.page_rasterizer = _FakeRasterizer()
            document = execution.document_ir_service.convert_zip(
                zip_path, job_id="job", source_file_id=source_pdf.id, document_language="en",
                placeholder_source_loader=lambda: PdfCropSource(source_pdf.id, checksum(pdf), pdf),
            ).document
            job = execution._register_source_ir_and_enqueue_translation(
                job, raw_file=raw, document_ir=document, image_file_ids=[], image_archive_file=None, trace_id=None)
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job.id)[0]
            with patch.object(execution, "_render_and_save_word", side_effect=lambda job, **kwargs: job):
                completed = execution.execute_translation_batch(batch.id)
            target_file = runtime.document_file_repository.get_document_file(
                runtime.document_job_repository.get_document_job(job.id).document_ir_file_id)
            target = json.loads(runtime.file_upload_service.read_file_content(target_file))
        self.assertEqual(completed.status, "succeeded")
        sent = [item.text for request in provider.requests for item in request.items]
        self.assertEqual(len(sent), 2)
        self.assertFalse(any("无法转换" in text for text in sent))
        notice = next(block for block in target["blocks"] if block["id"] == "degraded_page_0002_notice")
        self.assertTrue(notice["text"].startswith("第 2 页因 invalid_table_html 无法转换"))
        self.assertEqual(target_file.metadata["translation"]["skipped_degraded_page_numbers"], [2])
