"""第三批 C1+C2：可降级页级错误以整页图像替换，依赖闭包、阈值与前提不满足时整体失败。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.table_placeholder import PdfCropSource, TablePlaceholderError, checksum
from tests import test_fastapi_jobs_backend as fixtures

PDF = b"%PDF-1.4 degradation-source"
BAD_TABLE = "<table><tr><td>unclosed"


def _png(color="green"):
    buffer = io.BytesIO()
    Image.new("RGB", (30, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeRasterizer:
    DPI = 144

    def __init__(self, *, fail=False):
        self.pages = []
        self.fail = fail

    def rasterize(self, source, page_index):
        self.pages.append(page_index)
        if self.fail:
            raise TablePlaceholderError("table_placeholder_crop_failed")
        return _png()


def _three_pages(bad_page=1):
    blocks = [{"type": "title", "text": "Intro", "text_level": 1, "page_idx": 0},
              {"type": "text", "text": "Before table", "page_idx": 1},
              {"type": "text", "text": "After", "page_idx": 2}]
    blocks.insert(2, {"type": "table", "html": BAD_TABLE, "page_idx": bad_page})
    return blocks


class PageDegradationConverterTests(TestCase):
    def convert(self, blocks, *, rasterizer, members=None, layout=None, crop_provider=None, source_file_id="file_source"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content_list.json", json.dumps(blocks))
                if layout is not None:
                    archive.writestr("layout.json", json.dumps(layout))
                for name, data in (members or {}).items():
                    archive.writestr(name, data)
            service = MinerUToDocumentIRService(pdf_crop_provider=crop_provider, page_rasterizer=rasterizer)
            return service.convert_zip(path, job_id="job", source_file_id="file_source", document_language="en",
                                       placeholder_source_loader=lambda: PdfCropSource(source_file_id, checksum(PDF), PDF))

    def test_invalid_table_page_is_replaced_by_page_image(self):
        rasterizer = _FakeRasterizer()
        result = self.convert(_three_pages(), rasterizer=rasterizer)
        self.assertEqual(rasterizer.pages, [1])
        page_two = [block for block in result.document.blocks if block.page_index == 1]
        self.assertEqual([(block.id, block.type) for block in page_two],
                         [("degraded_page_0002_notice", "paragraph"), ("degraded_page_0002_image", "image")])
        self.assertIn("第 2 页因表格结构无法解析无法转换", page_two[0].text)
        self.assertEqual([block.text for block in result.document.blocks if block.page_index in {0, 2}], ["Intro", "After"])
        record = result.document.metadata.degraded_pages[0]
        self.assertEqual((record["page_index"], record["reason_codes"], record["removed_source_block_count"],
                          record["removed_source_type_counts"]), (1, ["invalid_table_html"], 2, {"table": 1, "text": 1}))
        report = result.validation_report
        self.assertEqual((report.can_convert, report.fatal_count), (True, 0))
        self.assertEqual([(issue.code, issue.stops_conversion) for issue in report.blockers], [("invalid_table_html", False)])
        raster = next(asset for asset in result.image_assets if asset.page_raster)
        self.assertEqual((raster.block_id, raster.page_raster["page_index"], raster.page_raster["dpi"]),
                         ("degraded_page_0002_image", 1, 144))

    def test_failed_image_fallback_degrades_page(self):
        layout = {"_version_name": "3.4.4", "pdf_info": [{"page_idx": index, "page_size": [612, 792]} for index in range(3)]}
        failing_crop = SimpleNamespace(crop=lambda request: (_ for _ in ()).throw(TablePlaceholderError("table_placeholder_crop_failed")))
        blocks = [{"type": "title", "text": "Intro", "text_level": 1, "page_idx": 0, "bbox": [90, 60, 500, 90]},
                  {"type": "image", "img_path": "images/missing.png", "page_idx": 1, "bbox": [94, 463, 478, 661]},
                  {"type": "text", "text": "After", "page_idx": 2, "bbox": [90, 60, 500, 90]}]
        result = self.convert(blocks, rasterizer=_FakeRasterizer(), layout=layout, crop_provider=failing_crop)
        self.assertEqual(result.document.metadata.degraded_pages[0]["reason_codes"], ["missing_image_asset"])
        self.assertEqual([issue.code for issue in result.validation_report.blockers], ["missing_image_asset"])

    def test_unmet_preconditions_fail_with_original_error(self):
        both_bad = _three_pages()
        both_bad[3] = {"type": "table", "html": BAD_TABLE, "page_idx": 2}
        cases = {
            "超过阈值": dict(blocks=both_bad, rasterizer=_FakeRasterizer()),
            "栅格失败": dict(blocks=_three_pages(), rasterizer=_FakeRasterizer(fail=True)),
            "无栅格器": dict(blocks=_three_pages(), rasterizer=None),
            "源 PDF 不一致": dict(blocks=_three_pages(), rasterizer=_FakeRasterizer(), source_file_id="file_other"),
        }
        for name, options in cases.items():
            with self.subTest(name), self.assertRaises(MinerUArtifactValidationError) as caught:
                self.convert(options.pop("blocks"), **options)
            report = caught.exception.report
            self.assertEqual(report.first_fatal.code, "invalid_table_html")
            self.assertTrue(all(issue.stops_conversion for issue in report.blockers if issue.code == "invalid_table_html"))


class DegradationClosureTests(TestCase):
    def _closure(self, groups, pages):
        trial = SimpleNamespace(metadata=SimpleNamespace(logical_table_groups=[]))
        document = SimpleNamespace(model_copy=lambda deep: trial)

        def attach(target, ledger):
            target.metadata.logical_table_groups = groups

        with patch("app.services.document_ir.mineru_converter.attach_logical_table_groups", attach):
            return MinerUToDocumentIRService._degradation_closure(document, None, set(pages))

    @staticmethod
    def _group(*fragments):
        return SimpleNamespace(fragments=[SimpleNamespace(source_span=SimpleNamespace(page_index=page), block_id=block_id)
                                          for page, block_id in fragments])

    def test_cross_page_group_pulls_in_every_page(self):
        groups = [self._group((1, "block_0003"), (2, "block_0005")), self._group((2, "block_0006"), (3, "block_0008"))]
        self.assertEqual(self._closure(groups, {1}), {1, 2, 3})
        self.assertEqual(self._closure(groups[1:], {1}), {1})

    def test_group_with_merged_receipt_or_unknown_page_abandons_degradation(self):
        self.assertIsNone(self._closure([self._group((1, "block_0003"), (2, None))], {1}))
        self.assertIsNone(self._closure([self._group((1, "block_0003"), (None, "block_0004"))], {1}))


class PageDegradationPipelineTests(TestCase):
    def test_degraded_job_succeeds_as_blocked_internal_draft(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("content_list.json", json.dumps(_three_pages()))
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = buffer.getvalue()
            runtime.document_job_execution_service.document_ir_service.page_rasterizer = _FakeRasterizer()
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]}).json()["job_id"]
                job = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                review = client.get(f"/api/v1/document-jobs/{job_id}/review", headers=headers).json()
                expected = {key: review["source"][key] for key in
                            ("generation", "result_file_id", "result_sha256", "file_review_source_revision", "receipt_sha256")}
                approve = client.patch(f"/api/v1/document-jobs/{job_id}/review", headers=headers,
                                       json={"status": "approved", "expected_source": expected})
            files = [file for file in runtime.document_file_repository.list_document_files() if file.job_id == job_id]
            read = runtime.document_job_execution_service.file_service.read_file_content
            raster_file = next(file for file in files if file.metadata.get("origin") == "pdf_page_raster")
            word = next(file for file in files if file.file_type == "generated_word")
            raster, docx = read(raster_file), read(word)
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        self.assertEqual((job["quality_status"], job["delivery_status"]), ("blocked", "internal_draft"))
        self.assertGreaterEqual(approve.status_code, 400, approve.text)
        with zipfile.ZipFile(io.BytesIO(docx)) as archive:
            media = [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn(raster, media)
        self.assertIn("已按原 PDF 页面图像保留", document_xml)
