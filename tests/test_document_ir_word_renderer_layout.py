from __future__ import annotations

# tests/test_document_ir_word_renderer_layout.py: 覆盖 DocumentIRWordRenderer 的 v2 layout plan 路径。

import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.word_renderer import DocumentIRWordRenderer


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class DocumentIRWordRendererLayoutTests(unittest.TestCase):
    def test_build_layout_plan_separates_decorations_and_two_column_regions(self) -> None:
        document = self._make_v2_two_column_document()

        plan = build_layout_plan(document)

        self.assertEqual(plan.mode, "layout_v2")
        self.assertEqual(len(plan.pages), 1)
        self.assertEqual([block.text for block in plan.pages[0].header_blocks], ["Header"])
        self.assertEqual([block.text for block in plan.pages[0].footer_blocks], ["Footer"])
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col"])

    def test_build_layout_plan_prefers_column_hint_for_stable_non_overlapping_regions(self) -> None:
        document = self._make_v2_stable_hint_document()

        plan = build_layout_plan(document)

        self.assertEqual(plan.mode, "layout_v2")
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[0].blocks], ["Left A", "Right A", "Left B", "Right B"])

    def test_render_to_bytes_uses_two_column_table_for_v2_region(self) -> None:
        renderer = DocumentIRWordRenderer()

        content = renderer.render_to_bytes(
            self._make_v2_two_column_document(),
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))

        self.assertGreaterEqual(len(rendered.tables), 1)
        self.assertIn("Left column", rendered.tables[0].cell(0, 0).text)
        self.assertIn("Right column", rendered.tables[0].cell(0, 1).text)
        self.assertTrue(any(paragraph.text == "Wide block" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_prefers_column_hint_when_splitting_two_column_cells(self) -> None:
        renderer = DocumentIRWordRenderer()

        content = renderer.render_to_bytes(
            self._make_v2_hint_override_document(),
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))

        self.assertGreaterEqual(len(rendered.tables), 1)
        self.assertIn("Left by hint", rendered.tables[0].cell(0, 0).text)
        self.assertIn("Right by hint", rendered.tables[0].cell(0, 1).text)

    def test_render_to_bytes_preserves_template_decorations_when_config_disabled(self) -> None:
        renderer = DocumentIRWordRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            template_path = temp_path / "template.docx"
            config_path = temp_path / "template.yaml"
            template = Document()
            template.sections[0].header.paragraphs[0].text = "Template Header"
            template.sections[0].footer.paragraphs[0].text = "Template Footer"
            template.save(template_path)
            config_path.write_text(
                (
                    "schema_version: template-config/v1\n"
                    "header:\n"
                    "  enabled: false\n"
                    "footer:\n"
                    "  enabled: false\n"
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                self._make_v2_two_column_document(),
                template_path=template_path,
                config_path=config_path,
                image_loader=lambda _asset: None,
            )
            rendered = Document(io.BytesIO(content))

        self.assertEqual(rendered.sections[0].header.paragraphs[0].text, "Template Header")
        self.assertEqual(rendered.sections[0].footer.paragraphs[0].text, "Template Footer")

    def test_render_to_bytes_keeps_v1_sequential_fallback(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_v1", source_file_id="file_v1", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_0001", type="paragraph", order=0, text="First"),
                DocumentIRBlock(id="block_0002", type="paragraph", order=1, text="Second"),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))

        self.assertEqual(len(rendered.tables), 0)
        self.assertEqual([paragraph.text for paragraph in rendered.paragraphs if paragraph.text], ["First", "Second"])

    def test_render_to_bytes_preserves_html_table_spans_and_annotations(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_table", source_file_id="file_table", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=0,
                    html=(
                        "<table><tr><th colspan=\"2\">Header</th><th>Value</th></tr>"
                        "<tr><td rowspan=\"2\">A</td><td>B1</td><td>C1</td></tr>"
                        "<tr><td>B2</td><td>C2</td></tr></table>"
                    ),
                    captions=["Table 1: merged cells"],
                    footnotes=["Note: kept editable"],
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 80, 400, 180), role="body"),
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual(len(rendered.tables), 1)
        self.assertIn("Header", rendered.tables[0].cell(0, 0).text)
        self.assertIn("A", rendered.tables[0].cell(1, 0).text)
        self.assertIn('w:gridSpan', xml)
        self.assertIn('w:vMerge', xml)
        self.assertTrue(any(paragraph.text == "Table 1: merged cells" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Note: kept editable" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_uses_bbox_width_for_images_and_annotations(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_image", source_file_id="file_image", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            assets=[DocumentIRAsset(id="asset_image", kind="image", source_path="images/chart.png")],
            blocks=[
                DocumentIRBlock(
                    id="block_image",
                    type="image",
                    order=0,
                    text="Ignored fallback",
                    asset_ref="asset_image",
                    captions=["Figure 1: bbox-sized chart"],
                    footnotes=["Source: MinerU"],
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 80, 100, 180), role="body"),
                )
            ],
        )

        content = renderer.render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: MINIMAL_PNG_BYTES,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)
        extent_match = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml)

        self.assertIsNotNone(extent_match)
        self.assertLess(int(extent_match.group(1)), 3_000_000)
        self.assertTrue(any(paragraph.text == "Figure 1: bbox-sized chart" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Source: MinerU" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_preserves_inline_rich_text_markup(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_rich", source_file_id="file_rich", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_rich",
                    type="paragraph",
                    order=0,
                    text="V<sub>OS</sub> = 5<sup>2</sup><br/>next",
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        xml = self._document_xml(content)

        self.assertIn('w:val="subscript"', xml)
        self.assertIn('w:val="superscript"', xml)
        self.assertIn("<w:br", xml)

    def _document_xml(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            return docx_zip.read("word/document.xml").decode("utf-8")

    def _make_v2_two_column_document(self) -> DocumentIR:
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_v2", source_file_id="file_v2", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_header",
                    type="paragraph",
                    order=0,
                    text="Header",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 0, 400, 30), role="page_header"),
                ),
                DocumentIRBlock(
                    id="block_left",
                    type="paragraph",
                    order=1,
                    text="Left column",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 60, 150, 100), role="body"),
                ),
                DocumentIRBlock(
                    id="block_right",
                    type="paragraph",
                    order=2,
                    text="Right column",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 60, 380, 100), role="body"),
                ),
                DocumentIRBlock(
                    id="block_wide",
                    type="paragraph",
                    order=3,
                    text="Wide block",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 130, 400, 170), role="body"),
                ),
                DocumentIRBlock(
                    id="block_footer",
                    type="paragraph",
                    order=4,
                    text="Footer",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 560, 400, 590), role="page_footer"),
                ),
            ],
        )

    def _make_v2_stable_hint_document(self) -> DocumentIR:
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_hint", source_file_id="file_hint", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_left_a",
                    type="paragraph",
                    order=0,
                    text="Left A",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 60, 150, 80), role="body", column_hint="left"),
                ),
                DocumentIRBlock(
                    id="block_right_a",
                    type="paragraph",
                    order=1,
                    text="Right A",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 90, 380, 110), role="body", column_hint="right"),
                ),
                DocumentIRBlock(
                    id="block_left_b",
                    type="paragraph",
                    order=2,
                    text="Left B",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 200, 150, 220), role="body", column_hint="left"),
                ),
                DocumentIRBlock(
                    id="block_right_b",
                    type="paragraph",
                    order=3,
                    text="Right B",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 240, 380, 260), role="body", column_hint="right"),
                ),
                DocumentIRBlock(
                    id="block_wide",
                    type="paragraph",
                    order=4,
                    text="Wide after hints",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 300, 400, 330), role="body", column_hint="wide"),
                ),
            ],
        )

    def _make_v2_hint_override_document(self) -> DocumentIR:
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_override", source_file_id="file_override", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_left_hint",
                    type="paragraph",
                    order=0,
                    text="Left by hint",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 60, 380, 100), role="body", column_hint="left"),
                ),
                DocumentIRBlock(
                    id="block_right_hint",
                    type="paragraph",
                    order=1,
                    text="Right by hint",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 70, 150, 110), role="body", column_hint="right"),
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
