"""普通直转坏表结构的定向验收，核对 HTTP 下载与 Word 实物。"""

import hashlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from fastapi.testclient import TestClient

from app.domains.files.service import FileUploadService
from app.infrastructure.pdf_crop import PopplerPdfPageRasterizer
from app.main import create_app
from app.services.document_ir.table_reference_assets import TABLE_REFERENCE_ROLE
from tests import test_fastapi_jobs_backend as fixtures
from tests.document_job_list_query_v2_publication_fixtures import RecordingPreviewProvider
from tests.test_page_degradation import _png as make_png
from tests.test_pdf_crop import _source as make_pdf_source

BAD_HTML = "<table><tr><td>Alpha</td><td>Beta"
ILLEGAL_MERGE = '<table><tr><td rowspan="3">Alpha</td><td>Beta</td></tr><tr><td>Tail</td></tr></table>'
COMPLETE_HTML = "<table><tr><td>Alpha</td><td>Beta</td></tr></table>"
TABLE_SOURCE_POINTER = "/1"


class ReviewableTableStructureFallbackTests(unittest.TestCase):
    @contextmanager
    def _direct_job(self, html, *, reference=None, rasterizer=None, preview=False):
        blocks = [
            {"type": "text", "text": "Body before table.", "page_idx": 0,
             "bbox": [50, 70, 760, 120], "column_hint": "wide"},
            {"type": "table", "html": html, "page_idx": 0, "column_hint": "wide"},
        ]
        if html:
            blocks[1]["bbox"] = [50, 170, 760, 360]
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            if reference is not None:
                blocks[1]["img_path"] = "images/table-reference.png"
                archive.writestr(blocks[1]["img_path"], reference)
            archive.writestr("content_list.json", json.dumps(blocks))
            if preview:
                archive.writestr("middle.json", json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [842, 596]}]}))

        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = package.getvalue()
            execution.document_ir_service.page_rasterizer = rasterizer
            if preview:
                # 提供独立预览贡献，单独观察表格结构对整体质量的影响。
                execution.settings.word_preview_backend = "sandboxed"
                execution.rendering.results.word_preview_service.provider = RecordingPreviewProvider()
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(
                    self, client, headers, pdf_content=make_pdf_source(media="0 0 842 596").content,
                )
                created = client.post("/api/v1/document-jobs", headers=headers, json={
                    "source_file_id": source["id"], "translation_mode": "direct", "document_language": "en",
                })
                self.assertEqual(created.status_code, 201, created.text)
                job_url = f"/api/v1/document-jobs/{created.json()['job_id']}"
                detail = client.get(job_url, headers=headers)
                self.assertEqual(detail.status_code, 200, detail.text)
                yield runtime, client, headers, job_url, detail.json()

    def _download_warning(self, runtime, client, headers, job_url, job, *, reason, preserved_as):
        record = runtime.document_file_repository.get_document_file(job["result_file_id"]) if job["result_file_id"] else None
        checks = job["quality_summary"].get("checks_v1", {})
        self.assertEqual((job["status"], job["stage"], job["quality_status"]), ("succeeded", "completed", "warning"), {
            "error": job["error_message"],
            "layout_flags": record.metadata["layout_quality_flags"] if record else [],
            "contributions": {name: (item.get("quality_status"), item.get("reason_code")) for name, item in checks.items()},
        })
        quality = client.get(f"{job_url}/quality", headers=headers)
        self.assertEqual(quality.status_code, 200, quality.text)
        payload = quality.json()
        self.assertEqual(payload["states"]["quality_status"], "warning")
        base, = [item for item in payload["producers"]["items"] if item["producer"] == "document_base"]
        review, = base["table_structure_reviews"]
        self.assertEqual(
            (review["page_number"], review["source_pointer"], review["reason"], review["preserved_as"]),
            (1, TABLE_SOURCE_POINTER, reason, preserved_as),
        )
        self.assertEqual(review["severity"], "warning")
        self.assertIs(review["manual_review_required"], True)

        ticket = client.get(f"{job_url}/download-url", headers=headers)
        self.assertEqual(ticket.status_code, 200, ticket.text)
        self.assertEqual(ticket.json()["classification"], "internal_only")
        download = client.get(ticket.json()["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, runtime.file_upload_service.read_file_content(record))
        self.assertEqual(record.checksum_sha256, "sha256:" + hashlib.sha256(download.content).hexdigest())
        self.assertEqual(payload["source"]["result_sha256"], record.checksum_sha256)
        return download.content

    def _assert_image_preserved(self, content, expected_image):
        word = Document(io.BytesIO(content))
        self.assertFalse(word.tables)
        self.assertEqual(len(word.inline_shapes), 1)
        self.assertTrue(any("不可编辑" in paragraph.text for paragraph in word.paragraphs))
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            media = [package.read(name) for name in package.namelist() if name.startswith("word/media/")]
        self.assertIn(expected_image, media)
        return word

    def _assert_no_downloadable_result(self, runtime, client, headers, job_url, job):
        self.assertEqual(job["status"], "failed", job)
        self.assertIsNone(job["result_file_id"])
        signed = client.get(f"{job_url}/download-url", headers=headers)
        self.assertEqual(signed.status_code, 409, signed.text)
        files = runtime.document_file_repository.list_document_files()
        self.assertFalse(any(file.job_id == job["id"] and file.file_type == "generated_word" for file in files))

    def test_bad_html_preserves_the_native_cells_and_downloads(self):
        with self._direct_job(BAD_HTML, preview=True) as context:
            content = self._download_warning(*context, reason="invalid_table_html", preserved_as="native")
        word = Document(io.BytesIO(content))
        table, = word.tables
        row, = table.rows
        self.assertEqual([cell.text for cell in row.cells], ["Alpha", "Beta"])
        self.assertFalse(word.inline_shapes)

    def test_illegal_merge_preserves_the_verified_reference_and_downloads(self):
        reference = make_png("blue")
        with self._direct_job(ILLEGAL_MERGE, reference=reference, preview=True) as context:
            content = self._download_warning(*context, reason="invalid_table_merge", preserved_as="reference_image")
        word = self._assert_image_preserved(content, reference)
        self.assertTrue(any(paragraph.text == "Body before table." for paragraph in word.paragraphs))

    @unittest.skipUnless(shutil.which("pdftoppm"), "整页回退验证需要 Poppler pdftoppm")
    def test_empty_table_without_crop_preserves_the_single_pdf_page_and_downloads(self):
        with self._direct_job("", rasterizer=PopplerPdfPageRasterizer(), preview=True) as context:
            runtime, _, _, _, job = context
            content = self._download_warning(*context, reason="empty_table_html", preserved_as="pdf_page")
            raster, = [file for file in runtime.document_file_repository.list_document_files()
                       if file.job_id == job["id"] and file.metadata.get("origin") == "pdf_page_raster"]
            self.assertEqual(raster.metadata["page_raster"]["page_index"], 0)
            page_bytes = runtime.file_upload_service.read_file_content(raster)
        self._assert_image_preserved(content, page_bytes)

    def test_empty_table_without_reliable_fallback_fails_with_page_location(self):
        with self._direct_job("") as context:
            job = context[-1]
            self._assert_no_downloadable_result(*context)
            self.assertEqual(job["error_code"], "document_ir_failed")
            diagnostic = job["failure_diagnostic"]
            self.assertEqual((diagnostic["reason_code"], diagnostic["page_number"]),
                             ("table_structure_recovery_unavailable", 1))

    def test_reference_bytes_with_a_different_digest_still_fail(self):
        read_content = FileUploadService.read_file_content

        def read_changed_reference(service, record):
            content = read_content(service, record)
            return make_png("red") if record.metadata.get("asset_role") == TABLE_REFERENCE_ROLE else content

        with patch.object(FileUploadService, "read_file_content", read_changed_reference):
            with self._direct_job(ILLEGAL_MERGE, reference=make_png("blue"), rasterizer=PopplerPdfPageRasterizer()) as context:
                self._assert_no_downloadable_result(*context)
                self.assertIn("table_placeholder_integrity_failed", context[-1]["error_message"])

    def test_word_without_the_planned_native_table_still_fails(self):
        save = DocxDocument.save
        removed_cells = []

        def save_without_table(document, stream):
            for table in document.tables:
                caption = table._tbl.tblPr.find(qn("w:tblCaption"))
                if caption is None or not caption.get(qn("w:val"), "").startswith("md2word-table-"):
                    continue
                removed_cells.extend(cell.text for row in table.rows for cell in row.cells)
                parent = table._tbl.getparent()
                index = parent.index(table._tbl)
                parent.remove(table._tbl)
                try:
                    return save(document, stream)
                finally:
                    parent.insert(index, table._tbl)
            return save(document, stream)

        with patch.object(DocxDocument, "save", save_without_table):
            with self._direct_job(COMPLETE_HTML, rasterizer=PopplerPdfPageRasterizer()) as context:
                self._assert_no_downloadable_result(*context)
                job = context[-1]
                self.assertEqual(job["error_code"], "render_failed")
                self.assertIn("ir_render_evidence:", job["error_message"])
        self.assertEqual(removed_cells, ["Alpha", "Beta"])
