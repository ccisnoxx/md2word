"""端到端验证：Word 不识别的图片经规范化后任务成功，DOCX 媒体与登记资产一致。"""
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from tests import test_fastapi_jobs_backend as fixtures


def _webp_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "blue").save(buffer, format="WEBP")
    return buffer.getvalue()


def _zip(blocks, webp):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", json.dumps(blocks))
        archive.writestr("images/figure.webp", webp)
    return buffer.getvalue()


class ImageNormalizationPipelineTests(TestCase):
    def _run_job(self, zip_bytes):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            runtime.document_job_execution_service.fake_mineru_client.result_zip_bytes = zip_bytes
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                created = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]})
                self.assertEqual(created.status_code, 201, created.text)
                job = client.get(f"/api/v1/document-jobs/{created.json()['job_id']}", headers=headers).json()
            files = [file for file in runtime.document_file_repository.list_document_files() if file.job_id == job["id"]]
            contents = {file.id: runtime.document_job_execution_service.file_service.read_file_content(file)
                        for file in files if file.status == "uploaded"}
        return job, files, contents

    @staticmethod
    def _docx_media(content):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return {name: archive.read(name) for name in archive.namelist() if name.startswith("word/media/")}

    def test_webp_body_image_is_rendered_as_png(self):
        webp = _webp_bytes()
        blocks = [{"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0},
                  {"type": "image", "img_path": "images/figure.webp", "page_idx": 0}]
        job, files, contents = self._run_job(_zip(blocks, webp))
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        image_file = next(file for file in files if file.file_type == "image_asset")
        self.assertEqual(image_file.mime_type, "image/png")
        self.assertTrue(image_file.original_filename.endswith("_figure.png"), image_file.original_filename)
        self.assertEqual((image_file.metadata["normalized_from_format"], image_file.metadata["normalized_from_sha256"]),
                         ("WEBP", hashlib.sha256(webp).hexdigest()))
        png = contents[image_file.id]
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        word = next(file for file in files if file.file_type == "generated_word")
        self.assertIn(png, self._docx_media(contents[word.id]).values())

    def test_webp_table_reference_placeholder_is_written_as_png(self):
        blocks = [{"type": "title", "text": "1 Features", "text_level": 1, "page_idx": 0},
                  {"type": "table", "html": "", "img_path": "images/figure.webp", "page_idx": 0,
                   "bbox": [72, 120, 520, 300]}]
        job, files, contents = self._run_job(_zip(blocks, _webp_bytes()))
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        reference = next(file for file in files
                         if file.file_type == "image_asset" and file.metadata.get("asset_role") == "table_reference")
        self.assertEqual((reference.mime_type, Path(reference.original_filename).suffix), ("image/png", ".png"))
        word = next(file for file in files if file.file_type == "generated_word")
        self.assertIn(contents[reference.id], self._docx_media(contents[word.id]).values())
