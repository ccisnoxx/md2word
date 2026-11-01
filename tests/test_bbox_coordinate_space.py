"""MinerU 归一化 bbox 坐标空间：页面几何识别、PDF 点换算及裁切、横竖版消费方。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from docx import Document
from docx.enum.section import WD_ORIENTATION
from PIL import Image

from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.layout_signals import NORMALIZED_BBOX_SPACE, build_pages, pdf_point_bbox
from app.services.document_ir.models import (
    DocumentIR, DocumentIRBlock, DocumentIRBlockLayout, DocumentIRMetadata, DocumentIRPage,
)
from app.services.document_ir.table_placeholder import PdfCropResult, PdfCropSource, checksum
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.word_renderer import DocumentIRWordRenderer


def _package(directory, *, version="3.4.4", page_size=(612, 792)):
    layout = {"pdf_info": [{"page_idx": 0, "page_size": list(page_size)}]}
    if version is not None:
        layout["_version_name"] = version
    (Path(directory) / "layout.json").write_text(json.dumps(layout))
    return Path(directory)


class BuildPagesCoordinateSpaceTests(TestCase):
    def _pages(self, blocks, **package):
        with tempfile.TemporaryDirectory() as directory:
            return build_pages(blocks, _package(directory, **package), [])

    def test_normalized_pages_use_bbox_space_and_pdf_orientation(self):
        for page_size, orientation in (((612, 792), "portrait"), ((842, 595), "landscape")):
            with self.subTest(page_size=page_size):
                page = self._pages([{"page_idx": 0, "bbox": [94, 463, 906, 964]}], page_size=page_size)[0]
                self.assertEqual((page.width, page.height), (1000.0, 1000.0))
                self.assertEqual(page.metadata["bbox_coordinate_space"], NORMALIZED_BBOX_SPACE)
                self.assertEqual(page.metadata["pdf_page_size"], list(page_size))
                self.assertEqual(page.metadata["orientation"], orientation)

    def test_unconfirmed_coordinate_space_keeps_legacy_derivation(self):
        cases = {"旧版本": dict(version="2.5"), "无版本": dict(version=None), "非法版本": dict(version="dev")}
        for name, package in cases.items():
            with self.subTest(name):
                page = self._pages([{"page_idx": 0, "bbox": [94, 463, 906, 964]}], **package)[0]
                self.assertNotIn("bbox_coordinate_space", page.metadata)
                self.assertAlmostEqual(page.width, 906.0)
        page = self._pages([{"page_idx": 0, "bbox": [94, 463, 1200, 964]}])[0]
        self.assertNotIn("bbox_coordinate_space", page.metadata)


class PdfPointBboxTests(TestCase):
    def test_conversion_by_coordinate_space(self):
        normalized = DocumentIRPage(index=0, width=1000.0, height=1000.0, metadata={
            "pdf_page_size": [612, 792], "page_size_source": "layout.json", "bbox_coordinate_space": NORMALIZED_BBOX_SPACE})
        converted = pdf_point_bbox((511, 604, 906, 731), normalized)
        self.assertEqual([round(value, 1) for value in converted], [312.7, 478.4, 554.5, 579.0])
        legacy = DocumentIRPage(index=0, width=612.0, height=792.0,
                                metadata={"pdf_page_size": [612, 792], "page_size_source": "layout.json"})
        self.assertEqual(pdf_point_bbox((72, 80, 180, 100), legacy), (72.0, 80.0, 180.0, 100.0))
        derived = DocumentIRPage(index=0, width=911.0, height=1179.0,
                                 metadata={"pdf_page_size": [612, 792], "page_size_source": "layout.json"})
        self.assertIsNone(pdf_point_bbox((72, 80, 180, 100), derived))
        self.assertIsNone(pdf_point_bbox((72, 80, 180, 100), DocumentIRPage(index=0, width=1000.0, height=1000.0)))
        self.assertIsNone(pdf_point_bbox((180, 80, 72, 100), normalized))


class OrientationConsumerTests(TestCase):
    def test_normalized_landscape_page_renders_landscape_section(self):
        page = DocumentIRPage(index=0, width=1000.0, height=1000.0, metadata={
            "pdf_page_size": [842, 595], "page_size_source": "layout.json",
            "bbox_coordinate_space": NORMALIZED_BBOX_SPACE, "orientation": "landscape"})
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_land", source_file_id="file_land", document_language="en"),
            pages=[page],
            blocks=[DocumentIRBlock(id="b1", type="paragraph", order=0, text="Landscape body",
                                    layout=DocumentIRBlockLayout(page_index=0, bbox=(80, 100, 900, 160), role="body"))],
        )
        self.assertTrue(build_layout_plan(document).pages[0].landscape)
        content = DocumentIRWordRenderer().render_to_bytes(document, template_path=None, config_path=None,
                                                            image_loader=lambda _asset: None)
        self.assertEqual(Document(io.BytesIO(content)).sections[-1].orientation, WD_ORIENTATION.LANDSCAPE)


class _RecordingCropProvider:
    def __init__(self):
        self.requests = []

    def crop(self, request):
        self.requests.append(request)
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
        return PdfCropResult(buffer.getvalue(), request.frame)


class PlaceholderCropCoordinateTests(TestCase):
    def test_missing_table_html_crops_with_pdf_points(self):
        # 原始 x1=906 超出 612pt 页宽：修复前按 PDF 点校验被拒，换算后为 (312.7, 478.4, 554.5, 579.0)。
        provider = _RecordingCropProvider()
        pdf = b"%PDF-1.4 fake"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content_list.json", json.dumps([
                    {"type": "title", "text": "Device Information", "text_level": 1, "page_idx": 0, "bbox": [511, 560, 906, 590]},
                    {"type": "table", "table_body": "", "page_idx": 0, "bbox": [511, 604, 906, 731]},
                ]))
                archive.writestr("layout.json", json.dumps({"_version_name": "3.4.4",
                                                            "pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}))
            result = MinerUToDocumentIRService(pdf_crop_provider=provider).convert_zip(
                path, job_id="job", source_file_id="file_source", document_language="en",
                placeholder_source_loader=lambda: PdfCropSource("file_source", checksum(pdf), pdf))
        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(request.frame, (612, 792))
        self.assertEqual([round(value, 1) for value in request.bbox], [312.7, 478.4, 554.5, 579.0])
        binding = result.document.metadata.table_placeholders[0]
        self.assertEqual(binding.bbox, (511, 604, 906, 731))


class ReviewSpanProjectionTests(TestCase):
    def _span(self, page):
        from types import SimpleNamespace
        from app.domains.document_jobs.review_content import _spans
        block = DocumentIRBlock(id="b1", type="paragraph", order=0, text="Body",
                                layout=DocumentIRBlockLayout(page_index=0, bbox=(511, 604, 906, 731), role="body"))
        read = SimpleNamespace(pages_by_index={0: page}, fragments_by_block={})
        return _spans(read, block, None)[0]

    def test_normalized_page_projects_verified_pdf_points(self):
        span = self._span(DocumentIRPage(index=0, width=1000.0, height=1000.0, metadata={
            "pdf_page_size": [612, 792], "page_size_source": "layout.json", "bbox_coordinate_space": NORMALIZED_BBOX_SPACE}))
        self.assertTrue(span.coordinate_verified)
        self.assertEqual([round(value, 1) for value in span.bbox], [312.7, 478.4, 554.5, 579.0])
        self.assertEqual((span.page_width, span.page_height), (612, 792))

    def test_derived_legacy_page_stays_unverified_with_raw_bbox(self):
        span = self._span(DocumentIRPage(index=0, width=911.0, height=1179.0,
                                         metadata={"pdf_page_size": [612, 792], "page_size_source": "layout.json"}))
        self.assertFalse(span.coordinate_verified)
        self.assertEqual((span.bbox, span.page_width, span.reason_code), ((511.0, 604.0, 906.0, 731.0), None, "coordinate_space_unverified"))
