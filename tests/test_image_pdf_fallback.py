"""P0-4：正文图片不可用时从源 PDF 回退裁切；安全与限额错误不回退，裁切失败保持原错误。"""
import dataclasses
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.mineru_package import DEFAULT_POLICY
from app.services.document_ir.table_placeholder import PdfCropResult, PdfCropSource, TablePlaceholderError, checksum
from tests import test_fastapi_jobs_backend as fixtures

PDF = b"%PDF-1.4 fallback-source"
LAYOUT = {"_version_name": "3.4.4", "pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}


def _png(color="red", size=(6, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _eps():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="EPS")
    return buffer.getvalue()


class _RecordingCropProvider:
    def __init__(self, *, fail=False):
        self.requests = []
        self.fail = fail

    def crop(self, request):
        self.requests.append(request)
        if self.fail:
            raise TablePlaceholderError("table_placeholder_crop_failed")
        return PdfCropResult(_png("blue", (20, 10)), request.frame)


def _image(path, bbox=(94, 463, 478, 661), page=0):
    return {"type": "image", "img_path": path, "page_idx": page, "bbox": list(bbox)}


class ImagePdfFallbackConverterTests(TestCase):
    def convert(self, blocks, members=None, *, provider=None, layout=LAYOUT, loader=True, policy=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content_list.json", json.dumps(blocks))
                if layout is not None:
                    archive.writestr("layout.json", json.dumps(layout))
                for name, data in (members or {}).items():
                    archive.writestr(name, data)
            service = MinerUToDocumentIRService(pdf_crop_provider=provider, **({"policy": policy} if policy else {}))
            return service.convert_zip(path, job_id="job", source_file_id="file_source", document_language="en",
                                       placeholder_source_loader=(lambda: PdfCropSource("file_source", checksum(PDF), PDF))
                                       if loader else None)

    def test_recoverable_images_are_cropped_from_source_pdf(self):
        cases = {"缺失文件": {}, "无法解码": {"images/a.png": _png()[:30]}, "非白名单格式": {"images/a.png": _eps()}}
        for name, members in cases.items():
            with self.subTest(name):
                provider = _RecordingCropProvider()
                result = self.convert([_image("images/a.png")], members, provider=provider)
                self.assertEqual(len(provider.requests), 1)
                request = provider.requests[0]
                self.assertEqual(request.frame, (612, 792))
                self.assertEqual([round(value, 1) for value in request.bbox], [57.5, 366.7, 292.5, 523.5])
                asset = result.image_assets[0]
                self.assertEqual((asset.mime_type, asset.source_path, asset.content), ("image/png", "derived/pdf-region-crop.png",
                                                                                      _png("blue", (20, 10))))
                self.assertEqual((asset.pdf_fallback["page_index"], asset.pdf_fallback["bbox"], asset.pdf_fallback["frame"]),
                                 (0, [94, 463, 478, 661], [612, 792]))
                report = result.validation_report
                self.assertEqual((report.blocker_count, report.fatal_count, report.can_convert), (0, 0, True))
                self.assertEqual(report.issue_counts["warning"]["image_asset_pdf_fallback"], 1)
                self.assertEqual(result.document.blocks[0].metadata["mineru_asset_origin"], "pdf_region_crop")

    def test_security_and_limit_errors_never_reach_the_cropper(self):
        provider = _RecordingCropProvider()
        with self.assertRaises(MinerUArtifactValidationError) as traversal:
            self.convert([_image("../escape.png")], provider=provider)
        self.assertEqual(traversal.exception.report.first_fatal.code, "mineru_path_invalid")
        policy = dataclasses.replace(DEFAULT_POLICY, max_file_bytes=50)
        with self.assertRaises(MinerUArtifactValidationError) as oversize:
            self.convert([_image("images/a.png")], {"images/a.png": _png(size=(64, 64))}, provider=provider, policy=policy)
        self.assertEqual(oversize.exception.report.first_fatal.code, "mineru_package_limit_exceeded")
        self.assertEqual(provider.requests, [])

    def test_word_compatible_image_does_not_fall_back(self):
        provider = _RecordingCropProvider()
        result = self.convert([_image("images/a.png")], {"images/a.png": _png()}, provider=provider)
        self.assertEqual((provider.requests, result.image_assets[0].content, result.image_assets[0].pdf_fallback),
                         ([], _png(), None))

    def test_unavailable_fallback_keeps_original_failure(self):
        cases = {
            "无裁切器": dict(provider=None),
            "无源 PDF": dict(provider=_RecordingCropProvider(), loader=False),
            "坐标空间未知": dict(provider=_RecordingCropProvider(), layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}),
            "裁切失败": dict(provider=_RecordingCropProvider(fail=True)),
        }
        for name, options in cases.items():
            with self.subTest(name), self.assertRaises(MinerUArtifactValidationError) as caught:
                self.convert([_image("images/a.png")], **options)
            report = caught.exception.report
            self.assertEqual((report.first_fatal.code, report.first_fatal.json_pointer, report.first_fatal.page_index),
                             ("missing_image_asset", "/0", 0))
            self.assertNotIn("image_asset_pdf_fallback", report.issue_counts["warning"])

    def test_partial_failure_reports_every_unrecovered_image(self):
        class _FailSecond(_RecordingCropProvider):
            def crop(self, request):
                self.requests.append(request)
                if len(self.requests) == 2:
                    raise TablePlaceholderError("table_placeholder_crop_failed")
                return PdfCropResult(_png("blue"), request.frame)

        with self.assertRaises(MinerUArtifactValidationError) as caught:
            self.convert([_image("images/a.png"), _image("images/b.png", (500, 100, 900, 300))], provider=_FailSecond())
        report = caught.exception.report
        self.assertEqual([(issue.json_pointer, issue.stops_conversion) for issue in report.blockers], [("/1", True)])
        self.assertEqual(report.issue_counts["warning"]["image_asset_pdf_fallback"], 1)
        self.assertEqual(report.first_fatal.json_pointer, "/1")

    def test_other_fatal_error_restores_deferred_images_as_fatal(self):
        provider = _RecordingCropProvider()
        with self.assertRaises(MinerUArtifactValidationError) as caught:
            # 无法解析的表格 HTML 在 complete_validation 才成为中止错误（路径安全错误更早中止，不经过这里）。
            self.convert([_image("images/a.png"), {"type": "table", "html": "<table><tr><td>unclosed", "page_idx": 0}],
                         provider=provider)
        report = caught.exception.report
        self.assertEqual(provider.requests, [])
        self.assertEqual(sorted((issue.code, issue.stops_conversion) for issue in report.blockers),
                         [("invalid_table_html", True), ("missing_image_asset", True)])


class ImagePdfFallbackPipelineTests(TestCase):
    def test_missing_image_job_succeeds_with_source_pdf_crop(self):
        provider = _RecordingCropProvider()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("content_list.json", json.dumps([
                {"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0, "bbox": [90, 60, 500, 90]},
                _image("images/missing.png")]))
            archive.writestr("layout.json", json.dumps(LAYOUT))
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = buffer.getvalue()
            runtime.document_job_execution_service.document_ir_service.pdf_crop_provider = provider
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                created = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]})
                job = client.get(f"/api/v1/document-jobs/{created.json()['job_id']}", headers=headers).json()
            files = [file for file in runtime.document_file_repository.list_document_files() if file.job_id == job["id"]]
            read = runtime.document_job_execution_service.file_service.read_file_content
            image_file = next(file for file in files if file.file_type == "image_asset")
            word = next(file for file in files if file.file_type == "generated_word")
            png, docx = read(image_file), read(word)
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual((image_file.mime_type, image_file.metadata["origin"]), ("image/png", "pdf_region_crop"))
        self.assertEqual(image_file.metadata["pdf_fallback"]["source_pdf_sha256"], provider.requests[0].source.checksum_sha256)
        with zipfile.ZipFile(io.BytesIO(docx)) as archive:
            media = [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]
        self.assertIn(png, media)

