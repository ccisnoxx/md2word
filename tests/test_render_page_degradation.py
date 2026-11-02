"""第三批 C3：带页定位的渲染失败降级为整页图像，另存新 IR 后重渲染一次；前提不满足按原错误失败。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.page_degradation import drop_degraded_table_groups, replace_degraded_pages
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests import test_fastapi_jobs_backend as fixtures
from tests.test_page_degradation import PDF, _FakeRasterizer, _png

ORIGINAL_RENDER_BLOCK = DocumentIRWordRenderer._render_block
TABLE = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"


def _pages(count):
    return [{"type": "text", "text": f"Page {index + 1} body", "page_idx": index} for index in range(count)]


def _zip(blocks):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list.json", json.dumps(blocks))
    return buffer.getvalue()


def _failing_on(*texts, error=ValueError):
    def failing(renderer, document, block, *args, **kwargs):
        if block.text in texts:
            raise error("内部细节不得进入事件")
        return ORIGINAL_RENDER_BLOCK(renderer, document, block, *args, **kwargs)
    return failing


class RenderPageDegradationPipelineTests(TestCase):
    def run_job(self, blocks, failing, *, rasterizer=True):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            service = runtime.document_job_execution_service
            service.fake_mineru_client.result_zip_bytes = _zip(blocks)
            service.document_ir_service.page_rasterizer = _FakeRasterizer() if rasterizer else None
            with TestClient(create_app(runtime)) as client, patch.object(DocumentIRWordRenderer, "_render_block", failing):
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]}).json()["job_id"]
                job = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                events = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers).json()["items"]
                approve = None
                if job["status"] == "succeeded":
                    review = client.get(f"/api/v1/document-jobs/{job_id}/review", headers=headers).json()
                    expected = {key: review["source"][key] for key in
                                ("generation", "result_file_id", "result_sha256", "file_review_source_revision", "receipt_sha256")}
                    approve = client.patch(f"/api/v1/document-jobs/{job_id}/review", headers=headers,
                                           json={"status": "approved", "expected_source": expected})
            files = {file.id: file for file in runtime.document_file_repository.list_document_files() if file.job_id == job_id}
            record = runtime.document_job_repository.get_document_job(job_id)
            read = service.file_service.read_file_content
            contents = {file_id: read(file) for file_id, file in files.items()}
        return job, events, approve, files, record, contents

    def test_failed_page_is_degraded_and_rerendered(self):
        job, events, approve, files, record, contents = self.run_job(_pages(3), _failing_on("Page 2 body"))
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        self.assertEqual((job["quality_status"], job["delivery_status"]), ("blocked", "internal_draft"))
        self.assertGreaterEqual(approve.status_code, 400, approve.text)
        switch = next(event for event in events if event["payload"].get("degraded_from_document_ir_file_id"))
        self.assertEqual(switch["payload"]["degraded_page_indexes"], [1])
        self.assertNotIn("内部细节", json.dumps(events, ensure_ascii=False))
        # 任务指针、结果绑定都指向降级后的新 IR；旧 IR 保留但不再权威。
        new_ir_id = switch["payload"]["document_ir_file_id"]
        self.assertEqual(record.document_ir_file_id, new_ir_id)
        word = files[record.result_file_id]
        self.assertEqual(word.metadata["document_ir_file_id"], new_ir_id)
        self.assertEqual(word.metadata["source_integrity"]["render_degraded_page_count"], 1)
        ir = DocumentIR.model_validate_json(contents[new_ir_id])
        self.assertEqual([(block.page_index, block.text) for block in ir.blocks if block.type == "paragraph"],
                         [(0, "Page 1 body"), (1, "第 2 页因 render_failed 无法转换，已按原 PDF 页面图像保留，本页不可编辑。"),
                          (2, "Page 3 body")])
        record_ = ir.metadata.degraded_pages[0]
        self.assertEqual((record_["trigger"], record_["operation_kind"], record_["render_reason_code"]),
                         ("render", "block", "ValueError"))
        raster = next(file for file in files.values() if file.metadata.get("origin") == "pdf_page_raster")
        self.assertIn(raster.id, record.image_asset_file_ids)
        with zipfile.ZipFile(io.BytesIO(contents[word.id])) as archive:
            media = [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]
        self.assertIn(contents[raster.id], media)

    def test_unmet_preconditions_fail_with_original_render_error(self):
        cases = {
            "无栅格器": dict(blocks=_pages(3), failing=_failing_on("Page 2 body"), rasterizer=False),
            "基础设施错误": dict(blocks=_pages(3), failing=_failing_on("Page 2 body", error=OSError)),
            "超过阈值": dict(blocks=_pages(1), failing=_failing_on("Page 1 body")),
            "重渲染仍失败": dict(blocks=_pages(4), failing=_failing_on("Page 2 body", "Page 3 body")),
        }
        for name, options in cases.items():
            with self.subTest(name):
                job, events, _approve, files, record, _contents = self.run_job(**options)
                self.assertEqual((job["status"], job["failed_stage"]), ("failed", "rendering"))
                self.assertIsNone(record.result_file_id)
                switched = [event for event in events if event["payload"].get("degraded_from_document_ir_file_id")]
                self.assertEqual(len(switched), 1 if name == "重渲染仍失败" else 0)
                if name == "重渲染仍失败":
                    # 第二次失败按本次错误定位，指针保持在已降级的新 IR。
                    self.assertEqual(job["failure_diagnostic"]["page_number"], 3)
                    self.assertEqual(record.document_ir_file_id, switched[0]["payload"]["document_ir_file_id"])


class DropDegradedTableGroupsTests(TestCase):
    def test_removed_table_group_leaves_valid_ir(self):
        blocks = [{"type": "text", "text": "Intro", "page_idx": 0},
                  {"type": "table", "html": TABLE, "page_idx": 1},
                  {"type": "text", "text": "After", "page_idx": 2}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            path.write_bytes(_zip(blocks))
            document = MinerUToDocumentIRService().convert_zip(
                path, job_id="job", source_file_id="file_source", document_language="en",
                placeholder_source_loader=lambda: PdfCropSource("file_source", checksum(PDF), PDF)).document
        self.assertEqual(len(document.metadata.logical_table_groups), 1)
        removed, _pending = replace_degraded_pages(document, {1: _png()}, {1: {"reason_codes": ["render_failed"]}},
                                                   source_pdf_sha256="sha256:x", dpi=144, trigger="render")
        drop_degraded_table_groups(document, removed)
        rebuilt = DocumentIR.model_validate(document.model_dump(mode="python"))
        self.assertEqual((rebuilt.metadata.logical_table_groups, rebuilt.metadata.logical_table_group_counts["group_count"]),
                         ([], 0))
        self.assertFalse(any(block.type == "table" for block in rebuilt.blocks))
