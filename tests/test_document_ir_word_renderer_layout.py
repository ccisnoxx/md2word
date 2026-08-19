from __future__ import annotations

# tests/test_document_ir_word_renderer_layout.py: 覆盖 DocumentIRWordRenderer 的 v2 layout plan 路径。

import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from docx import Document
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Emu

from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.renderer.evidence import build_renderer_evidence, ensure_renderer_integrity
from app.services.renderer.docx_quality import analyze_docx_quality_bytes
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.renderer.word_renderer import DocumentIRRenderOptions, DocumentIRWordRenderer


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class DocumentIRWordRendererLayoutTests(unittest.TestCase):
    def test_seed_config_declares_western_and_complex_fonts_for_all_text_groups(self) -> None:
        config = TemplateConfigPackage.load(
            Path(__file__).resolve().parents[1] / "resources" / "template_configs" / "datasheet_template_v2.yaml"
        )

        for group_name in (
            "part_number",
            "category",
            "heading1",
            "heading2",
            "heading3",
            "toc_title",
            "toc_level1",
            "toc_level2",
            "toc_level3",
            "normal",
            "table_content",
            "table_note",
            "caption",
            "long_table_caption",
        ):
            style = getattr(config, group_name)
            self.assertEqual(style.western_font_name, "Arial", group_name)
            self.assertEqual(style.complex_script_font_name, "Times New Roman", group_name)
        self.assertEqual(config.header.title_western_font_name, "Arial")
        self.assertEqual(config.header.title_complex_script_font_name, "Times New Roman")
        self.assertEqual(config.footer.western_font_name, "Arial")
        self.assertEqual(config.footer.complex_script_font_name, "Times New Roman")

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
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["one_col", "two_col", "one_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[0].blocks], ["Left A"])
        self.assertEqual([block.text for block in plan.pages[0].regions[1].blocks], ["Right A", "Left B"])
        self.assertEqual([block.text for block in plan.pages[0].regions[2].blocks], ["Right B", "Wide after hints"])

    def test_build_layout_plan_keeps_explicit_wide_blocks_out_of_stable_two_column_regions(self) -> None:
        document = self._make_v2_wide_between_columns_document()

        plan = build_layout_plan(document)

        self.assertEqual(plan.mode, "layout_v2")
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col", "two_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[0].blocks], ["Left A", "Right A"])
        self.assertEqual([block.text for block in plan.pages[0].regions[1].blocks], ["Wide callout"])
        self.assertEqual([block.text for block in plan.pages[0].regions[2].blocks], ["Left B", "Right B"])

    def test_build_layout_plan_keeps_single_column_gap_between_real_two_column_bands(self) -> None:
        def block(block_id: str, text: str, bbox: tuple[float, float, float, float], hint: str) -> DocumentIRBlock:
            return DocumentIRBlock(
                id=block_id,
                type="paragraph",
                order=len(text),
                text=text,
                layout=DocumentIRBlockLayout(page_index=0, bbox=bbox, role="body", column_hint=hint),
            )

        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_local_bands", source_file_id="file_local_bands", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                block("upper_left", "Upper left", (0, 60, 170, 120), "left"),
                block("upper_right", "Upper right", (220, 65, 390, 125), "right"),
                block("middle_left", "Middle only", (0, 170, 170, 230), "left"),
                block("lower_left", "Lower left", (0, 310, 170, 400), "left"),
                block("lower_right", "Lower right", (220, 315, 390, 400), "right"),
            ],
        )

        plan = build_layout_plan(document)

        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col", "two_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[1].blocks], ["Middle only"])

    def test_renderer_evidence_summarizes_layout_and_docx_quality(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_evidence", source_file_id="file_evidence", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_0001",
                    type="paragraph",
                    order=0,
                    page_index=0,
                    text="Formal renderer evidence should remain editable in Word output.",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72, 80, 320, 140), role="body"),
                )
            ],
            quality_flags=["layout_sample:block_0001"],
        )
        layout_plan = build_layout_plan(document)
        word_content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )

        evidence = build_renderer_evidence(document, word_content, layout_plan)

        self.assertEqual(evidence["schema_version"], "document-ir/v2")
        self.assertEqual(evidence["renderer_mode"], "layout_v2")
        self.assertEqual(evidence["layout_page_count"], 1)
        self.assertEqual(evidence["layout_block_count"], 1)
        self.assertEqual(evidence["expected_layout_block_count"], 1)
        self.assertEqual(evidence["layout_block_count_delta"], 0)
        self.assertEqual(evidence["layout_quality_flags"], ["layout_sample:block_0001"])
        self.assertTrue(evidence["docx_quality"]["editable_content_available"])
        self.assertFalse(evidence["docx_quality"]["image_only_suspected"])
        self.assertEqual(evidence["quality_flags"], [])
        self.assertEqual(evidence["blocking_quality_flags"], [])

    def test_renderer_evidence_blocks_missing_layout_drawing_and_table(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_blocking", source_file_id="file_blocking", document_language="zh"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            assets=[DocumentIRAsset(id="asset_chart", kind="image", source_path="chart.png")],
            blocks=[
                DocumentIRBlock(id="missing_page", type="paragraph", order=0, text="不应静默丢失的正文"),
                DocumentIRBlock(
                    id="missing_drawing",
                    type="image",
                    order=1,
                    asset_ref="asset_chart",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 80, 180, 180), role="body"),
                ),
                DocumentIRBlock(
                    id="missing_table",
                    type="table",
                    order=2,
                    html="not-a-table",
                    text="表格回退文本",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 200, 390, 300), role="body"),
                ),
            ],
        )
        word_content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )

        evidence = build_renderer_evidence(document, word_content)

        self.assertEqual(evidence["expected_layout_block_count"], 3)
        self.assertEqual(evidence["layout_block_count"], 2)
        self.assertEqual(evidence["expected_inline_shape_count"], 1)
        self.assertEqual(evidence["inline_shape_count"], 0)
        self.assertEqual(evidence["expected_table_count"], 1)
        self.assertEqual(evidence["table_count"], 0)
        self.assertIn("ir_layout_integrity:missing_blocks", evidence["blocking_quality_flags"])
        self.assertIn("ir_docx_integrity:inline_shape_count_mismatch", evidence["blocking_quality_flags"])
        self.assertIn("ir_docx_integrity:table_count_mismatch", evidence["blocking_quality_flags"])
        with self.assertRaises(DocumentIntegrityError) as raised:
            ensure_renderer_integrity(evidence)
        self.assertIn("expected_inline_shape_count=1", str(raised.exception))
        self.assertIn("inline_shape_count=0", str(raised.exception))

    def test_render_to_bytes_uses_native_columns_for_v2_region(self) -> None:
        renderer = DocumentIRWordRenderer()

        content = renderer.render_to_bytes(
            self._make_v2_two_column_document(),
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual(len(rendered.tables), 0)
        self.assertTrue(any(paragraph.text == "Left column" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Right column" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Wide block" for paragraph in rendered.paragraphs))
        self.assertIn('<w:cols w:space="720" w:num="2"', xml)
        self.assertIn('<w:br w:type="column"', xml)
        self.assertGreaterEqual(xml.count('<w:type w:val="continuous"'), 2)
        self.assertEqual(rendered.sections[0].page_width, rendered.sections[1].page_width)
        self.assertEqual(rendered.sections[0].left_margin, rendered.sections[1].left_margin)
        self.assertTrue(rendered.sections[1].header.is_linked_to_previous)

    def test_render_to_bytes_prefers_column_hint_when_ordering_native_columns(self) -> None:
        renderer = DocumentIRWordRenderer()

        content = renderer.render_to_bytes(
            self._make_v2_hint_override_document(),
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))

        self.assertEqual(len(rendered.tables), 0)
        visible_paragraphs = [paragraph.text for paragraph in rendered.paragraphs if paragraph.text]
        self.assertEqual(visible_paragraphs, ["Left by hint", "Right by hint"])
        self.assertIn('<w:br w:type="column"', self._document_xml(content))
        self.assertEqual(rendered.sections[-1].start_type, WD_SECTION_START.CONTINUOUS)
        self.assertNotIn('<w:br w:type="page"', self._document_xml(content))

    def test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_image_rows", source_file_id="file_image_rows", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            assets=[DocumentIRAsset(id="asset_chart", kind="image", source_path="images/chart.png")],
            blocks=[
                DocumentIRBlock(
                    id=f"block_{index}",
                    type="image",
                    order=index,
                    asset_ref="asset_chart",
                    captions=[f"Figure {index}: {tail}"],
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=bbox,
                        role="body",
                        column_hint="left" if index % 2 else "right",
                    ),
                )
                for index, tail, bbox in (
                    (1, "Left first", (10, 80, 170, 180)),
                    (2, "Right first", (220, 82, 380, 180)),
                    (3, "Left second", (10, 220, 170, 320)),
                    (4, "Right second", (220, 218, 380, 320)),
                )
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: MINIMAL_PNG_BYTES,
        )
        xml = self._document_xml(content)

        self.assertLess(xml.index("Left first"), xml.index("Right first"))
        self.assertLess(xml.index("Right first"), xml.index("Left second"))
        self.assertLess(xml.index("Left second"), xml.index("Right second"))
        self.assertNotIn('<w:br w:type="column"', xml)
        self.assertEqual(len(Document(io.BytesIO(content)).sections), 1)
        self.assertEqual(xml.count('<w:tabs>'), 4)
        self.assertEqual(xml.count('w:val="center"'), 8)
        self.assertGreaterEqual(xml.count("<w:keepNext/>"), 3)
        self.assertEqual(xml.count(" SEQ Figure \\* ARABIC "), 4)

    def test_render_to_bytes_keeps_multi_annotation_images_in_native_columns(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_image_notes", source_file_id="file_image_notes", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            assets=[DocumentIRAsset(id="asset_chart", kind="image", source_path="images/chart.png")],
            blocks=[
                DocumentIRBlock(
                    id=f"block_{index}",
                    type="image",
                    order=index,
                    asset_ref="asset_chart",
                    captions=[f"Figure {index}: chart"],
                    footnotes=["Source note"] if index == 1 else [],
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=bbox,
                        role="body",
                        column_hint="left" if index == 1 else "right",
                    ),
                )
                for index, bbox in ((1, (10, 80, 170, 180)), (2, (220, 82, 380, 180)))
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: MINIMAL_PNG_BYTES,
        )
        xml = self._document_xml(content)

        self.assertIn('<w:cols w:space="720" w:num="2"', xml)
        self.assertIn('<w:br w:type="column"', xml)
        self.assertIn("Source note", xml)
        self.assertNotIn("<w:tabs>", xml)

    def test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages(self) -> None:
        document = self._make_v2_hint_override_document()
        document.pages.append(DocumentIRPage(index=1, width=400.0, height=600.0))
        document.blocks.append(
            DocumentIRBlock(
                id="block_next_page",
                type="heading",
                order=2,
                level=2,
                text="Next source page",
                layout=DocumentIRBlockLayout(page_index=1, bbox=(0, 60, 400, 100), role="body", column_hint="wide"),
            )
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual(rendered.sections[-1].start_type, WD_SECTION_START.CONTINUOUS)
        self.assertNotIn('<w:br w:type="page"', xml)
        self.assertIn("<w:pageBreakBefore/>", xml)
        self.assertTrue(any(paragraph.text == "Next source page" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_anchors_semantic_page_breaks_to_real_content(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_semantic_pages", source_file_id="file_semantic_pages", document_language="zh"),
            pages=[DocumentIRPage(index=index, width=400.0, height=600.0) for index in range(5)],
            blocks=[
                DocumentIRBlock(
                    id="intro",
                    type="paragraph",
                    order=0,
                    text="Intro",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 60, 400, 100), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="working_principle",
                    type="heading",
                    order=1,
                    level=2,
                    text="工作原理",
                    layout=DocumentIRBlockLayout(page_index=1, bbox=(0, 60, 400, 100), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="captioned_table",
                    type="table",
                    order=2,
                    captions=["绝对最大额定值"],
                    html="<table><tr><th>参数</th></tr><tr><td>值</td></tr></table>",
                    layout=DocumentIRBlockLayout(page_index=2, bbox=(0, 80, 400, 180), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="table_context",
                    type="paragraph",
                    order=3,
                    text="默认测试条件：VS = ±18V、VCM = 0V、TA = 25°C。",
                    metadata={"annotation_role": "table_context", "source_block_id": "context_table"},
                    layout=DocumentIRBlockLayout(page_index=3, bbox=(0, 60, 400, 80), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="context_table",
                    type="table",
                    order=4,
                    html="<table><tr><th>参数</th></tr><tr><td>值</td></tr></table>",
                    layout=DocumentIRBlockLayout(page_index=3, bbox=(0, 90, 400, 190), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="flowing_page",
                    type="paragraph",
                    order=5,
                    text="Natural continuation",
                    layout=DocumentIRBlockLayout(page_index=4, bbox=(0, 60, 400, 100), role="body", column_hint="wide"),
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)
        paragraphs = {paragraph.text: paragraph for paragraph in rendered.paragraphs if paragraph.text}

        self.assertTrue(paragraphs["工作原理"].paragraph_format.page_break_before)
        self.assertTrue(paragraphs["工作原理"].paragraph_format.keep_with_next)
        self.assertTrue(paragraphs["绝对最大额定值"].paragraph_format.page_break_before)
        self.assertTrue(paragraphs["默认测试条件：VS = ±18V、VCM = 0V、TA = 25°C。"].paragraph_format.page_break_before)
        self.assertIsNone(paragraphs["Natural continuation"].paragraph_format.page_break_before)
        self.assertEqual(xml.count("<w:pageBreakBefore/>"), 3)
        self.assertNotIn('<w:br w:type="page"', xml)

    def test_render_to_bytes_keeps_continuous_restore_when_wide_content_follows_columns(self) -> None:
        document = self._make_v2_two_column_document()
        document.pages.append(DocumentIRPage(index=1, width=400.0, height=600.0))
        document.blocks.append(
            DocumentIRBlock(
                id="block_next_page",
                type="heading",
                order=5,
                level=2,
                text="Next source page",
                layout=DocumentIRBlockLayout(page_index=1, bbox=(0, 60, 400, 100), role="body", column_hint="wide"),
            )
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual(rendered.sections[-1].start_type, WD_SECTION_START.CONTINUOUS)
        self.assertTrue(any(section.start_type == WD_SECTION_START.CONTINUOUS for section in rendered.sections))
        self.assertNotIn('<w:br w:type="page"', xml)
        self.assertTrue(any(paragraph.text == "Wide block" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_starts_new_section_when_page_orientation_changes(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_orientation", source_file_id="file_orientation", document_language="en"),
            pages=[
                DocumentIRPage(index=0, width=612.0, height=792.0),
                DocumentIRPage(index=1, width=792.0, height=612.0),
            ],
            blocks=[
                DocumentIRBlock(
                    id="block_portrait",
                    type="paragraph",
                    order=0,
                    text="Portrait",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72, 80, 300, 120), role="body"),
                ),
                DocumentIRBlock(
                    id="block_landscape",
                    type="paragraph",
                    order=1,
                    text="Landscape",
                    layout=DocumentIRBlockLayout(page_index=1, bbox=(72, 80, 300, 120), role="body"),
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))

        self.assertEqual(rendered.sections[-1].start_type, WD_SECTION_START.NEW_PAGE)
        self.assertEqual(rendered.sections[-1].orientation, WD_ORIENTATION.LANDSCAPE)
        self.assertNotIn('<w:br w:type="page"', self._document_xml(content))

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
        xml = self._document_xml(content)
        self.assertEqual(xml.count("<w:headerReference"), 1)
        self.assertEqual(xml.count("<w:footerReference"), 1)
        self.assertTrue(all(section.header.is_linked_to_previous for section in rendered.sections[1:]))
        self.assertTrue(all(section.footer.is_linked_to_previous for section in rendered.sections[1:]))

    def test_render_to_bytes_writes_configured_body_header_and_footer_font_slots(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_fonts", source_file_id="file_fonts", document_language="zh"),
            blocks=[
                DocumentIRBlock(
                    id="block_fonts",
                    type="paragraph",
                    order=0,
                    text="中文 Latin العربية",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "normal:",
                        "  font_name: SimSun",
                        "  western_font_name: Arial",
                        "  complex_script_font_name: Times New Roman",
                        "header:",
                        "  enabled: true",
                        "  title_text: 中文 Header العربية",
                        "  title_font_name: Microsoft YaHei",
                        "  title_western_font_name: Calibri",
                        "  title_complex_script_font_name: Arial",
                        "footer:",
                        "  enabled: true",
                        "  show_page_number: true",
                        "  font_name: FangSong",
                        "  western_font_name: Arial",
                        "  complex_script_font_name: Times New Roman",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                document,
                template_path=(
                    Path(__file__).resolve().parents[1]
                    / "resources"
                    / "templates"
                    / "default"
                    / "datasheet_template.docx"
                ),
                config_path=config_path,
                image_loader=lambda _asset: None,
            )

        footer_xml = self._related_xml(content, "word/footer")
        self.assertIn("<w:fldChar", footer_xml)
        expected_parts = (
            (self._document_xml(content), ("SimSun", "Arial", "Times New Roman")),
            (self._related_xml(content, "word/header"), ("Microsoft YaHei", "Calibri", "Arial")),
            (footer_xml, ("FangSong", "Arial", "Times New Roman")),
        )
        for xml, (east_asia, western, complex_script) in expected_parts:
            run_fonts = re.search(r"<w:rFonts\b[^>]*/>", xml)
            self.assertIsNotNone(run_fonts)
            font_attributes = run_fonts.group(0)
            self.assertIn(f'w:eastAsia="{east_asia}"', font_attributes)
            self.assertIn(f'w:ascii="{western}"', font_attributes)
            self.assertIn(f'w:hAnsi="{western}"', font_attributes)
            self.assertIn(f'w:cs="{complex_script}"', font_attributes)

    def test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer(self) -> None:
        renderer = DocumentIRWordRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "footer:",
                        "  enabled: true",
                        "  left_text: V1.1",
                        "  right_text: www.example.com",
                        "  show_page_number: true",
                        "  font_name: FangSong",
                        "  western_font_name: Arial",
                        "  complex_script_font_name: Times New Roman",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                self._make_v2_two_column_document(),
                template_path=None,
                config_path=config_path,
                image_loader=lambda _asset: None,
            )

        rendered = Document(io.BytesIO(content))
        footer_xml = self._related_xml(content, "word/footer")
        self.assertIn("V1.1", footer_xml)
        self.assertIn("www.example.com", footer_xml)
        self.assertIn(" PAGE ", footer_xml)
        self.assertNotIn("Footer", footer_xml)
        self.assertNotIn("<w:tbl", footer_xml)
        self.assertIn('w:ptab w:alignment="center" w:relativeTo="margin" w:leader="none"', footer_xml)
        self.assertIn('w:ptab w:alignment="right" w:relativeTo="margin" w:leader="none"', footer_xml)
        self.assertTrue(all(section.footer.is_linked_to_previous for section in rendered.sections[1:]))

    def test_extracted_decorations_keep_normal_style_and_legacy_font_inheritance(self) -> None:
        renderer = DocumentIRWordRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "normal:",
                        "  font_name: Normal East",
                        "  western_font_name: Normal West",
                        "  complex_script_font_name: Normal Complex",
                        "  font_size: 12",
                        "  bold: true",
                        "  color: '#123456'",
                        "  alignment: right",
                        "  space_before: 2",
                        "  space_after: 3",
                        "header:",
                        "  enabled: true",
                        "  title_font_name: Header East",
                        "footer:",
                        "  enabled: true",
                        "  show_page_number: false",
                        "  alignment: center",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                self._make_v2_two_column_document(),
                template_path=None,
                config_path=config_path,
                image_loader=lambda _asset: None,
            )
            rendered = Document(io.BytesIO(content))

        header_paragraph = rendered.sections[0].header.paragraphs[0]
        footer_paragraph = rendered.sections[0].footer.paragraphs[0]
        for paragraph in (header_paragraph, footer_paragraph):
            run = next(item for item in paragraph.runs if item.text)
            self.assertEqual(run.font.size.pt, 12)
            self.assertTrue(run.bold)
            self.assertEqual(str(run.font.color.rgb), "123456")
            self.assertEqual(paragraph.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
            self.assertEqual(paragraph.paragraph_format.space_before.pt, 2)
            self.assertEqual(paragraph.paragraph_format.space_after.pt, 3)

        header_fonts = next(item for item in header_paragraph.runs if item.text)._element.rPr.rFonts
        self.assertEqual(header_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia"), "Header East")
        self.assertEqual(header_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii"), "Header East")
        self.assertEqual(header_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hAnsi"), "Header East")
        self.assertEqual(header_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}cs"), "Header East")
        footer_run = next(item for item in footer_paragraph.runs if item.text)
        self.assertIsNone(footer_run._element.rPr.rFonts)

    def test_decoration_font_resolution_preserves_explicit_empty_and_fallback_order(self) -> None:
        resolve = DocumentIRWordRenderer._resolve_decoration_font

        self.assertEqual(resolve("", "Legacy", "Normal"), "")
        self.assertEqual(resolve(None, "Legacy", "Normal"), "Legacy")
        self.assertEqual(resolve(None, None, "Normal"), "Normal")

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
        self.assertIn("<w:tblHeader", xml)
        self.assertGreaterEqual(xml.count("<w:cantSplit"), 3)
        self.assertIn('<w:jc w:val="center"', xml)
        self.assertIn('<w:jc w:val="left"', xml)
        self.assertIn('<w:spacing w:before="0" w:after="0"', xml)
        self.assertLess(xml.index(" SEQ Table "), xml.index("<w:tbl>"))
        self.assertLess(xml.index("<w:tbl>"), xml.index("Note: kept editable"))
        self.assertIn("<w:keepNext/>", xml[: xml.index("<w:tbl>")])
        self.assertTrue(any(paragraph.text == "Table 1: merged cells" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Note: kept editable" for paragraph in rendered.paragraphs))

    def test_render_to_bytes_writes_fraction_omml_in_formula_and_table_cells(self) -> None:
        formula = (
            r"\mathrm{激励频率} = \frac {(\mathrm{FCW} \times \mathrm{f} _ {\mathrm{CLKIN}})}"
            r"{2 ^ {1 5}}"
        )
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_fraction", source_file_id="file_fraction", document_language="zh"),
            blocks=[
                DocumentIRBlock(id="block_formula", type="formula", order=0, latex=formula),
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=1,
                    html=f"<table><tr><td>{formula}</td></tr></table>",
                ),
                DocumentIRBlock(id="block_inline_times", type="paragraph", order=2, text=r"A \times B"),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        xml = self._document_xml(content)
        visible_text = self._document_text(content)
        root = ElementTree.fromstring(xml)
        math_namespace = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}

        def script_text(element: ElementTree.Element, name: str) -> str:
            script_part = element.find(f"m:{name}", math_namespace)
            self.assertIsNotNone(script_part)
            return "".join(script_part.itertext())

        superscripts = [
            (script_text(element, "e"), script_text(element, "sup"))
            for element in root.findall(".//m:sSup", math_namespace)
        ]
        subscripts = [
            (script_text(element, "e"), script_text(element, "sub"))
            for element in root.findall(".//m:sSub", math_namespace)
        ]

        self.assertGreaterEqual(xml.count("<m:oMath>"), 2)
        self.assertGreaterEqual(xml.count("<m:f>"), 2)
        self.assertGreaterEqual(xml.count("<m:sSup>"), 2)
        self.assertGreaterEqual(xml.count("<m:sSub>"), 2)
        self.assertGreaterEqual(superscripts.count(("2", "15")), 2)
        self.assertGreaterEqual(subscripts.count(("f", "CLKIN")), 2)
        self.assertIn("FCW ×fCLKIN", visible_text)
        self.assertIn("215", visible_text)
        self.assertIn("A × B", visible_text)
        self.assertNotIn(r"\frac", xml)
        self.assertNotIn(r"\times", xml)

    def test_malformed_fraction_remains_visible_and_is_reported_as_latex_residue(self) -> None:
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_bad_fraction", source_file_id="file_bad_fraction", document_language="en"),
            blocks=[DocumentIRBlock(id="block_formula", type="formula", order=0, latex=r"\frac{1}{2")],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        quality = analyze_docx_quality_bytes(content)

        self.assertIn(r"\frac", self._document_xml(content))
        self.assertEqual(quality["latex_residue_count"], 1)

    def test_render_to_bytes_writes_extended_omml_in_all_shared_text_paths(self) -> None:
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_extended_omml", source_file_id="file_extended_omml", document_language="zh"),
            blocks=[
                DocumentIRBlock(
                    id="block_formula",
                    type="formula",
                    order=0,
                    latex=r"\overline{\mathbf{SOE}} + \boxed{\mathrm{X}} + \bigotimes + \mathbf{t}_{\text{TRACK}}",
                ),
                DocumentIRBlock(
                    id="block_heading",
                    type="heading",
                    order=1,
                    level=2,
                    text=r"状态 $\overline{\mathbf{SAMPLE}}$",
                ),
                DocumentIRBlock(
                    id="block_text",
                    type="paragraph",
                    order=2,
                    text=r"电源 AV $_{DD}$ 与 $\bigotimes$",
                ),
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=3,
                    html=r"<table><tr><td>V<sub>OS</sub>，A<sub>V</sub> $_{DD}$，DV $_{DD}$ 与 $\boxed{\mathrm{X}}$</td></tr></table>",
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        xml = self._document_xml(content)
        root = ElementTree.fromstring(xml)
        namespace = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}

        def script_text(element: ElementTree.Element, name: str) -> str:
            part = element.find(f"m:{name}", namespace)
            self.assertIsNotNone(part)
            return "".join(part.itertext())

        subscripts = [
            (script_text(element, "e"), script_text(element, "sub"))
            for element in root.findall(".//m:sSub", namespace)
        ]
        self.assertGreaterEqual(len(root.findall(".//m:bar", namespace)), 2)
        self.assertTrue(all(item.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val") == "top" for item in root.findall(".//m:barPr/m:pos", namespace)))
        self.assertGreaterEqual(len(root.findall(".//m:rPr/m:sty", namespace)), 3)
        self.assertGreaterEqual(len(root.findall(".//m:borderBox", namespace)), 2)
        self.assertGreaterEqual(self._document_text(content).count("⨂"), 2)
        self.assertTrue({("t", "TRACK"), ("AV", "DD"), ("DV", "DD")} <= set(subscripts))
        self.assertGreaterEqual(subscripts.count(("AV", "DD")), 2)
        self.assertIn('w:vertAlign w:val="subscript"', xml)
        self.assertNotIn("&lt;/td&gt;", xml)
        for residue in (r"\overline", r"\mathbf", r"\bigotimes", r"\boxed", "_{DD}", "_{TRACK}"):
            self.assertNotIn(residue, xml)
        self.assertEqual(analyze_docx_quality_bytes(content)["latex_residue_count"], 0)

    def test_render_to_bytes_preprocesses_cm4112_formulas_without_tex_residue(self) -> None:
        fraction = r"\frac {\left(V _ {I N} - V _ {S}\right)}{R _ {S} + 5 0 0 \Omega} \leq 5 \mathrm{mA}"
        total_delay = (
            r"\mathrm{总} t _ {s} = \sqrt {\left(t _ {s , C M 7 5 0 1}\right) ^ {2} + "
            r"\left(t _ {s , C M 4 1 1 X}\right) ^ {2}}"
        )
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_cm4112_math", source_file_id="file_cm4112_math", document_language="zh"),
            blocks=[
                DocumentIRBlock(id="fraction", type="formula", order=0, latex=fraction),
                DocumentIRBlock(id="delay", type="formula", order=1, latex=total_delay),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        xml = self._document_xml(content)
        visible_text = self._document_text(content)

        self.assertIn("<m:f>", xml)
        self.assertIn("<m:rad>", xml)
        self.assertIn('<m:degHide m:val="1"/>', xml)
        self.assertGreaterEqual(xml.count("<m:sSub>"), 6)
        self.assertGreaterEqual(xml.count("<m:sSup>"), 2)
        for expected in ("≤", "Ω", "总", "CM7501", "CM411X"):
            self.assertIn(expected, visible_text)
        for residue in (r"\frac", r"\left", r"\right", r"\leq", "I N", "5 0 0", "C M 7 5 0 1"):
            self.assertNotIn(residue, xml)
        self.assertEqual(analyze_docx_quality_bytes(content)["latex_residue_count"], 0)

    def test_render_to_bytes_supports_datasheet_tex_matrix_in_all_math_entries(self) -> None:
        expression = (
            r"\dfrac{\mathbf{V}_{I N}^{2}}{\sqrt[3]{\mathit{x}}} + "
            r"\left(\boldsymbol{\Phi} \approx \varphi\right) + \text{总} + "
            r"\pm + \mu + \circ + \times + \theta + \Omega + \Delta + \leq + \sim + \ldots + \rightarrow \tag{1}"
        )
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_tex_matrix", source_file_id="file_tex_matrix", document_language="zh"),
            blocks=[
                DocumentIRBlock(id="formula", type="formula", order=0, latex=expression),
                DocumentIRBlock(id="inline", type="paragraph", order=1, text=f"正文 ${expression}$"),
                DocumentIRBlock(id="table", type="table", order=2, html=f"<table><tr><td>${expression}$</td></tr></table>"),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        xml = self._document_xml(content)
        visible_text = self._document_text(content)

        self.assertGreaterEqual(xml.count("<m:f>"), 3)
        self.assertGreaterEqual(xml.count("<m:rad>"), 3)
        self.assertGreaterEqual(xml.count("<m:deg>"), 3)
        self.assertNotIn("<m:degHide", xml)
        self.assertGreaterEqual(xml.count("<m:sSub>"), 3)
        self.assertGreaterEqual(xml.count("<m:sSup>"), 3)
        for expected in ("VIN", "Φ", "≈", "ϕ", "总", "±", "μ", "°", "×", "θ", "Ω", "Δ", "≤", "∼", "…", "→"):
            self.assertIn(expected, visible_text)
        for residue in (r"\dfrac", r"\sqrt", r"\left", r"\right", r"\boldsymbol", r"\tag"):
            self.assertNotIn(residue, xml)
        self.assertEqual(analyze_docx_quality_bytes(content)["latex_residue_count"], 0)

    def test_render_to_bytes_styles_later_th_cells_as_table_headers(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_later_th", source_file_id="file_later_th", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_later_th",
                    type="table",
                    order=0,
                    html=(
                        "<table><tr><td colspan=\"2\">Electrical Characteristics</td></tr>"
                        "<tr><th>PARAMETER</th><th>TEST CONDITIONS</th></tr>"
                        "<tr><td>VOS</td><td>TA = +25°C</td></tr></table>"
                    ),
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        xml = self._document_xml(content)

        self.assertIn("PARAMETER", xml)
        self.assertIn("TEST CONDITIONS", xml)
        self.assertGreaterEqual(xml.count("<w:shd"), 3)

    def test_render_to_bytes_normalizes_formula_text_in_table_cells_and_notes(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_table_formula", source_file_id="file_table_formula", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_table_formula",
                    type="table",
                    order=0,
                    html=(
                        r"<table><tr><th>Parameter</th><th>Value</th></tr>"
                        r"<tr><td>$R_{\theta JA}$</td><td>nV/ \sqrt{Hz}</td></tr></table>"
                    ),
                    captions=[r"Table 1: $R_{\theta JA}$ formulas"],
                    footnotes=[r"Note: E=mc^2"],
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        xml = self._document_xml(content)
        visible_text = self._document_text(content)

        self.assertIn("R", visible_text)
        self.assertIn("θJA", visible_text)
        self.assertIn("Table 1: RθJA formulas", visible_text)
        self.assertIn("nV/√Hz", visible_text)
        self.assertIn("Note: E=mc2", visible_text)
        self.assertIn(" SEQ Table ", xml)
        self.assertIn("<m:oMath>", xml)
        self.assertIn("<m:sSub>", xml)
        self.assertIn('w:val="subscript"', xml)
        self.assertIn('w:val="superscript"', xml)
        self.assertNotIn(r"\theta", xml)
        self.assertNotIn(r"\sqrt", xml)

    def test_render_to_bytes_applies_subscript_config_to_formal_renderer_outputs(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_terms", source_file_id="file_terms", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_text", type="paragraph", order=0, text="VOS and IOS are specified."),
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=1,
                    html="<table><tr><th>Parameter</th></tr><tr><td>VOS</td></tr></table>",
                    captions=["Table 1: VOS limits"],
                ),
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            subscript_config_path = Path(temp_dir) / "subscripts.yaml"
            subscript_config_path.write_text(
                "\n".join(
                    [
                        "subscript_rules:",
                        "  electrical:",
                        "    VOS: V<sub>OS</sub>",
                        "    IOS: I<sub>OS</sub>",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                document,
                template_path=None,
                config_path=None,
                image_loader=lambda _asset: None,
                options=DocumentIRRenderOptions(subscript_config_path=subscript_config_path, document_language="en"),
            )

        xml = self._document_xml(content)
        self.assertGreaterEqual(xml.count('w:val="subscript"'), 4)
        self.assertIn("V</w:t>", xml)
        self.assertIn("OS", xml)
        self.assertNotIn("&lt;sub&gt;", xml)

    def test_datasheet_five_column_table_widths_prioritize_description_column(self) -> None:
        renderer = DocumentIRWordRenderer()

        widths = renderer._table_column_widths(5, 10_000)

        self.assertEqual(sum(widths), 10_000)
        self.assertGreater(widths[1], widths[0] * 3)
        self.assertGreater(widths[1], widths[4] * 3)

    def test_render_to_bytes_normalizes_datasheet_temperature_and_microsecond_symbols(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_formula_edge", source_file_id="file_formula_edge", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_formula_edge",
                    type="formula",
                    order=0,
                    latex=r"$T_A = +25^\circ C$, $5 \mu s$",
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        xml = self._document_xml(content)
        visible_text = self._document_text(content)

        self.assertIn("TA = +25°C, 5 μs", visible_text)
        self.assertIn("<m:oMath>", xml)
        self.assertIn("<m:sSub>", xml)
        self.assertNotIn("^°", xml)
        self.assertNotIn(r"\circ", xml)
        self.assertNotIn(r"\mu", xml)

    def test_render_to_bytes_normalizes_manual_quality_record_formula_residue(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_manual_formula_residue", source_file_id="file_manual_formula_residue", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_manual_formula_residue",
                    type="paragraph",
                    order=0,
                    text=(
                        r"$\\sqrt{Hz}$ $5 \\mu s$ $PACKAGE^{(1)}$ $-40^{\\circ}C$ "
                        r"$R_{\\theta JC(top)}$ $\\psi_{JT}$ $V_S = \\pm 5$ "
                        r"$V_{CM}$ $I_B$ $R_L=5 kΩ$ nV/\\sqrt{Hz} "
                        r"$\\mathrm { \\mu V / ^ { \\circ } C }$"
                    ),
                )
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        xml = self._document_xml(content)
        visible_text = " ".join(self._document_text(content).split())

        for expected in ("Hz", "5 μs", "PACKAGE", "-40°C", "θJC(top)", "ψJT", "±5", "CM", "nV/√Hz", "μV / ° C"):
            self.assertIn(expected, visible_text)
        self.assertIn("<m:sSub>", xml)
        self.assertIn("<m:sSup>", xml)
        self.assertIn("<m:rad>", xml)
        self.assertNotIn(r"\mathrm", xml)
        self.assertNotIn(r"\sqrt", xml)
        self.assertNotIn(r"\theta", xml)
        self.assertNotIn(r"\psi", xml)
        self.assertNotIn(r"\circ", xml)
        self.assertNotIn(r"\pm", xml)
        self.assertNotIn(r"\mu", xml)

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
                    captions=[r"Figure 1: $V_{OS}$ bbox-sized chart"],
                    footnotes=[r"Source: $5 \mu s$ MinerU"],
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
        settings_xml = self._settings_xml(content)
        extent_match = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml)

        self.assertIsNotNone(extent_match)
        self.assertLess(int(extent_match.group(1)), 1_500_000)
        self.assertLess(xml.index("<w:keepNext/>"), xml.index("<w:drawing>"))
        self.assertLess(xml.index("<w:drawing>"), xml.index(" SEQ Figure "))
        self.assertGreaterEqual(xml.count("<w:keepNext/>"), 2)
        self.assertIn('w:val="subscript"', xml)
        self.assertNotIn(r"\mu", xml)
        self.assertTrue(any(paragraph.text == "Figure 1: VOS bbox-sized chart" for paragraph in rendered.paragraphs))
        self.assertIn("Source: 5 μs MinerU", self._document_text(content))
        self.assertIn('<w:doNotAutoCompressPictures w:val="true"', settings_xml)
        self.assertEqual(self._first_media_bytes(content), MINIMAL_PNG_BYTES)

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

    def test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_semantic", source_file_id="file_semantic", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_heading",
                    type="heading",
                    order=0,
                    level=2,
                    text="6.5 Thermal Information",
                ),
                DocumentIRBlock(
                    id="block_list",
                    type="list",
                    order=1,
                    list_items=["• Low noise", "- Stable supply"],
                ),
                DocumentIRBlock(
                    id="block_formula",
                    type="formula",
                    order=2,
                    latex=r"$R_{\theta JA}$, E=mc^2, nV/ \sqrt{Hz}",
                ),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)
        numbering_xml = self._numbering_xml(content)

        self.assertEqual(rendered.paragraphs[0].style.name, "Heading 2")
        self.assertEqual([paragraph.text for paragraph in rendered.paragraphs[1:3]], ["Low noise", "Stable supply"])
        self.assertIn('w:val="Heading2"', xml)
        self.assertIn("<w:numPr>", xml)
        self.assertIn('w:val="bullet"', numbering_xml)
        self.assertIn("<m:sSub>", xml)
        self.assertIn("<m:sSup>", xml)
        self.assertIn("<m:rad>", xml)
        self.assertIn("nV/", xml)
        self.assertNotIn("• Low noise", xml)
        self.assertNotIn(r"\sqrt", xml)

    def test_render_to_bytes_promotes_bullet_like_paragraphs_to_word_lists(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_auto_list", source_file_id="file_auto_list", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_bullet", type="paragraph", order=0, text="• Paragraph bullet"),
                DocumentIRBlock(id="block_dash", type="paragraph", order=1, text="- Nested paragraph bullet"),
                DocumentIRBlock(id="block_temperature", type="paragraph", order=2, text="-40°C operation"),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)
        numbering_xml = self._numbering_xml(content)

        self.assertEqual(
            [paragraph.text for paragraph in rendered.paragraphs if paragraph.text],
            ["Paragraph bullet", "Nested paragraph bullet", "-40°C operation"],
        )
        self.assertEqual(xml.count("<w:numPr>"), 2)
        self.assertIn('w:val="bullet"', numbering_xml)
        self.assertNotIn("• Paragraph bullet", xml)
        self.assertNotIn("- Nested paragraph bullet", xml)
        self.assertIn("-40°C operation", xml)

    def test_render_to_bytes_keeps_v1_heading_like_paragraph_compatibility(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_auto_heading", source_file_id="file_auto_heading", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_numbered_heading", type="paragraph", order=0, text="6.5 Thermal Information"),
                DocumentIRBlock(id="block_title_case_heading", type="paragraph", order=1, text="Absolute Maximum Ratings"),
                DocumentIRBlock(
                    id="block_body",
                    type="paragraph",
                    order=2,
                    text="This section describes the device behavior",
                ),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual([paragraph.text for paragraph in rendered.paragraphs], [
            "6.5 Thermal Information",
            "Absolute Maximum Ratings",
            "This section describes the device behavior",
        ])
        self.assertEqual(rendered.paragraphs[0].style.name, "Heading 2")
        self.assertEqual(rendered.paragraphs[1].style.name, "Heading 2")
        self.assertEqual(rendered.paragraphs[2].style.name, "Normal")
        self.assertGreaterEqual(xml.count('w:val="Heading2"'), 2)

    def test_render_to_bytes_uses_explicit_v2_semantics_without_heading_guessing(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_v2_semantics", source_file_id="file_v2_semantics", document_language="zh"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="caption",
                    type="paragraph",
                    order=0,
                    text="图 1 输出电压",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 30, 180, 55), role="body"),
                ),
                DocumentIRBlock(
                    id="reference",
                    type="paragraph",
                    order=1,
                    text="图 13 显示了输出响应",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 65, 180, 90), role="body"),
                ),
                DocumentIRBlock(
                    id="explicit_heading",
                    type="heading",
                    order=2,
                    level=1,
                    text="工作原理",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 100, 390, 130), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="bullet",
                    type="paragraph",
                    order=3,
                    text="• 应用说明",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 140, 180, 165), role="body"),
                ),
                DocumentIRBlock(
                    id="toc",
                    type="paragraph",
                    order=4,
                    text="工作原理 .... 10",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(10, 175, 180, 200), role="body"),
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        paragraphs = {paragraph.text: paragraph for paragraph in rendered.paragraphs if paragraph.text}

        self.assertEqual(paragraphs["图 1 输出电压"].style.name, "Normal")
        self.assertEqual(paragraphs["图 13 显示了输出响应"].style.name, "Normal")
        self.assertEqual(paragraphs["工作原理"].style.name, "Heading 1")
        self.assertIn("应用说明", paragraphs)
        self.assertIn("更新目录", paragraphs)
        self.assertEqual(self._document_xml(content).count(" TOC \\o"), 1)

    def test_layout_merges_single_side_tail_before_paired_images_into_one_column_flow(self) -> None:
        def body(
            block_id: str,
            block_type: str,
            text: str | None,
            bbox: tuple[float, float, float, float],
            hint: str,
            *,
            asset_ref: str | None = None,
        ) -> DocumentIRBlock:
            return DocumentIRBlock(
                id=block_id,
                type=block_type,
                order=len(block_id),
                text=text,
                asset_ref=asset_ref,
                layout=DocumentIRBlockLayout(page_index=0, bbox=bbox, role="body", column_hint=hint),
            )

        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_tail", source_file_id="file_tail", document_language="zh"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            assets=[
                DocumentIRAsset(id="asset_left", kind="image", source_path="left.png"),
                DocumentIRAsset(id="asset_right", kind="image", source_path="right.png"),
            ],
            blocks=[
                body("left", "paragraph", "左栏正文", (10, 50, 180, 100), "left"),
                body("right", "paragraph", "右栏正文", (220, 50, 390, 100), "right"),
                body("tail", "paragraph", "左栏尾部", (10, 120, 180, 155), "left"),
                body("image_left", "image", None, (10, 220, 180, 330), "left", asset_ref="asset_left"),
                body("image_right", "image", None, (220, 220, 390, 330), "right", asset_ref="asset_right"),
            ],
        )

        plan = build_layout_plan(document)
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "two_col"])
        self.assertEqual([block.id for block in plan.pages[0].regions[0].blocks], ["left", "right", "tail"])

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: MINIMAL_PNG_BYTES,
        )
        xml = self._document_xml(content)
        self.assertEqual(xml.count('w:num="2"'), 1)
        self.assertEqual(analyze_docx_quality_bytes(content)["inline_shape_count"], 2)

    def test_layout_keeps_text_after_image_only_region_outside_image_flow(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_image_tail", source_file_id="file_image_tail", document_language="zh"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="image_left",
                    type="image",
                    order=0,
                    asset_ref="asset_left",
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=(10, 50, 180, 180),
                        role="body",
                        column_hint="left",
                    ),
                ),
                DocumentIRBlock(
                    id="image_right",
                    type="image",
                    order=1,
                    asset_ref="asset_right",
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=(220, 50, 390, 180),
                        role="body",
                        column_hint="right",
                    ),
                ),
                DocumentIRBlock(
                    id="text_tail",
                    type="paragraph",
                    order=2,
                    text="下一段正文",
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=(10, 220, 180, 260),
                        role="body",
                        column_hint="left",
                    ),
                ),
            ],
        )

        plan = build_layout_plan(document)

        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col"])
        self.assertEqual([block.id for block in plan.pages[0].regions[1].blocks], ["text_tail"])

    def test_render_to_bytes_uses_one_native_toc_field_for_toc_like_entries(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_toc", source_file_id="file_toc", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_toc_title", type="paragraph", order=0, text="目录"),
                DocumentIRBlock(id="block_toc_entry", type="paragraph", order=1, text="Features........................ 1"),
                DocumentIRBlock(
                    id="block_toc_list",
                    type="list",
                    order=2,
                    list_items=["特性 .... 1", "目录 .... 3", "Appendix A Device Pinout 120", "• Updated numbering"],
                ),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertEqual([paragraph.text for paragraph in rendered.paragraphs], ["目录", "更新目录", "Updated numbering"])
        self.assertEqual(xml.count(" TOC \\o"), 1)
        self.assertNotIn("Features", xml)
        self.assertNotIn("Appendix A Device Pinout", xml)
        self.assertNotIn("<w:tab/>", xml)
        self.assertEqual(xml.count("<w:numPr>"), 1)
        self.assertIn('<w:updateFields w:val="true"', self._settings_xml(content))

    def test_render_to_bytes_links_unique_caption_references_with_native_fields(self) -> None:
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_refs", source_file_id="file_refs", document_language="zh"),
            assets=[DocumentIRAsset(id="asset_figure", kind="image", source_path="figure.png")],
            blocks=[
                DocumentIRBlock(id="block_ref", type="paragraph", order=0, text="参见图 3、表 2；图 99 保持原文，表 7 也保持原文。"),
                DocumentIRBlock(
                    id="block_figure",
                    type="image",
                    order=1,
                    asset_ref="asset_figure",
                    captions=["图 3. 典型波形"],
                    footnotes=["测试条件说明"],
                ),
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=2,
                    html="<table><tr><td>见图 3</td></tr></table>",
                    captions=["表 2 参数"],
                ),
                DocumentIRBlock(
                    id="block_duplicate_a",
                    type="table",
                    order=3,
                    html="<table><tr><td>A</td></tr></table>",
                    captions=["Table 7: duplicate A"],
                ),
                DocumentIRBlock(
                    id="block_duplicate_b",
                    type="table",
                    order=4,
                    html="<table><tr><td>B</td></tr></table>",
                    captions=["Table 7: duplicate B"],
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: MINIMAL_PNG_BYTES,
        )
        xml = self._document_xml(content)

        self.assertIn(" SEQ 图 \\* ARABIC ", xml)
        self.assertIn(" SEQ 表 \\* ARABIC ", xml)
        self.assertEqual(xml.count(" SEQ Table \\* ARABIC "), 2)
        self.assertIn('w:name="_md2word_figure_3"', xml)
        self.assertIn('w:name="_md2word_table_2"', xml)
        self.assertGreaterEqual(xml.count(" REF _md2word_figure_3 \\h "), 2)
        self.assertIn(" REF _md2word_table_2 \\h ", xml)
        self.assertNotIn("REF _md2word_figure_99", xml)
        self.assertNotIn("REF _md2word_table_7", xml)
        self.assertNotIn('w:name="_md2word_table_7"', xml)
        self.assertIn("测试条件说明", xml)
        self.assertIn('<w:updateFields w:val="true"', self._settings_xml(content))

    def test_render_to_bytes_keeps_compound_caption_numbers_as_plain_text(self) -> None:
        document = DocumentIR(
            metadata=DocumentIRMetadata(
                job_id="docjob_compound_captions",
                source_file_id="file_compound_captions",
                document_language="zh",
            ),
            blocks=[
                DocumentIRBlock(id="block_refs", type="paragraph", order=0, text="参见表1-1、表 1.1、表1–1、Figure 1A，以及表 1。"),
                DocumentIRBlock(
                    id="block_valid",
                    type="table",
                    order=1,
                    html="<table><tr><td>valid</td></tr></table>",
                    captions=["表 1 有效题注"],
                ),
                DocumentIRBlock(
                    id="block_hyphen",
                    type="table",
                    order=2,
                    html="<table><tr><td>hyphen</td></tr></table>",
                    captions=["表1-1 复合编号"],
                ),
                DocumentIRBlock(
                    id="block_decimal",
                    type="table",
                    order=3,
                    html="<table><tr><td>decimal</td></tr></table>",
                    captions=["表 1.1 复合编号"],
                ),
                DocumentIRBlock(
                    id="block_en_dash",
                    type="table",
                    order=4,
                    html="<table><tr><td>en dash</td></tr></table>",
                    captions=["表1–1 复合编号"],
                ),
                DocumentIRBlock(
                    id="block_suffix",
                    type="table",
                    order=5,
                    html="<table><tr><td>suffix</td></tr></table>",
                    captions=["Figure 1A compound number"],
                ),
            ],
        )

        content = DocumentIRWordRenderer().render_to_bytes(
            document,
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        xml = self._document_xml(content)
        visible_text = self._document_text(content)

        self.assertEqual(xml.count(" SEQ 表 \\* ARABIC "), 1)
        self.assertNotIn(" SEQ Figure ", xml)
        self.assertEqual(xml.count(" REF _md2word_table_1 \\h "), 1)
        self.assertIn("表1-1", visible_text)
        self.assertIn("表 1.1", visible_text)
        self.assertIn("表1–1", visible_text)
        self.assertIn("Figure 1A", visible_text)

    def test_render_to_bytes_uses_configured_toc_styles(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_toc_style", source_file_id="file_toc_style", document_language="en"),
            blocks=[
                DocumentIRBlock(id="block_toc_title", type="paragraph", order=0, text="Table of Contents"),
                DocumentIRBlock(id="block_toc_level1", type="paragraph", order=1, text="1 Features........................ 1"),
                DocumentIRBlock(id="block_toc_level2", type="paragraph", order=2, text="1.1 Device Details................ 2"),
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "toc_title:",
                        "  font_size: 15",
                        "  color: '#112233'",
                        "  alignment: center",
                        "toc_level1:",
                        "  font_size: 11",
                        "  color: '#445566'",
                        "  alignment: left",
                        "toc_level2:",
                        "  font_name: SimSun",
                        "  western_font_name: Arial",
                        "  complex_script_font_name: Noto Sans Arabic",
                        "  font_size: 10",
                        "  bold: true",
                        "  italic: true",
                        "  color: '#778899'",
                        "  alignment: right",
                        "  line_spacing: 1.2",
                        "  space_before: 2",
                        "  space_after: 3",
                        "  first_line_indent_pt: 4",
                        "  left_indent_pt: 5",
                        "  right_indent_pt: 6",
                        "toc_level3:",
                        "  font_size: 9",
                        "  color: '#AABBCC'",
                        "  alignment: justify",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(document, template_path=None, config_path=config_path, image_loader=lambda _asset: None)

        xml = self._document_xml(content)
        styles_root = ElementTree.fromstring(self._styles_xml(content))
        word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        toc2 = styles_root.find(f".//{word_ns}style[@{word_ns}styleId='TOC2']")
        toc3 = styles_root.find(f".//{word_ns}style[@{word_ns}styleId='TOC3']")

        self.assertIsNotNone(toc2)
        self.assertIsNotNone(toc3)
        assert toc2 is not None
        assert toc3 is not None
        toc2_fonts = toc2.find(f"./{word_ns}rPr/{word_ns}rFonts")
        self.assertIsNotNone(toc2_fonts)
        assert toc2_fonts is not None
        self.assertIn('w:val="112233"', xml)
        self.assertIn('w:val="445566"', xml)
        self.assertEqual(toc2_fonts.get(f"{word_ns}eastAsia"), "SimSun")
        self.assertEqual(toc2_fonts.get(f"{word_ns}ascii"), "Arial")
        self.assertEqual(toc2_fonts.get(f"{word_ns}hAnsi"), "Arial")
        self.assertEqual(toc2_fonts.get(f"{word_ns}cs"), "Noto Sans Arabic")
        self.assertEqual(toc2.find(f"./{word_ns}rPr/{word_ns}color").get(f"{word_ns}val"), "778899")
        self.assertIsNotNone(toc2.find(f"./{word_ns}rPr/{word_ns}b"))
        self.assertIsNotNone(toc2.find(f"./{word_ns}rPr/{word_ns}i"))
        self.assertEqual(toc2.find(f"./{word_ns}pPr/{word_ns}jc").get(f"{word_ns}val"), "right")
        self.assertEqual(toc2.find(f"./{word_ns}pPr/{word_ns}ind").get(f"{word_ns}left"), "100")
        self.assertEqual(toc3.find(f"./{word_ns}rPr/{word_ns}color").get(f"{word_ns}val"), "AABBCC")
        self.assertEqual(toc3.find(f"./{word_ns}pPr/{word_ns}jc").get(f"{word_ns}val"), "both")
        self.assertEqual(xml.count(" TOC \\o"), 1)

    def test_render_to_bytes_uses_configured_long_table_caption_and_border_color(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_table_style", source_file_id="file_table_style", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=0,
                    html="<table><tr><th>Parameter</th></tr><tr><td>Gain</td></tr></table>",
                    captions=["A.1 Continued electrical characteristics"],
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "table_style:",
                        "  style_name: Table Grid",
                        "  header_fill: AABBCC",
                        "  border_color: '123456'",
                        "caption:",
                        "  color: '#111111'",
                        "long_table_caption:",
                        "  color: '#ABCDEF'",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(document, template_path=None, config_path=config_path, image_loader=lambda _asset: None)

        xml = self._document_xml(content)
        self.assertIn('w:val="ABCDEF"', xml)
        self.assertIn('w:fill="AABBCC"', xml)
        self.assertIn('w:color="123456"', xml)

    def test_render_to_bytes_uses_configured_page_size_and_header_bold_flag(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_page_config", source_file_id="file_page_config", document_language="en"),
            pages=[DocumentIRPage(index=0, width=400.0, height=600.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=0,
                    html="<table><tr><th>Parameter</th></tr><tr><td>Gain</td></tr></table>",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72, 80, 300, 160), role="body"),
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "page_setup:",
                        "  page_width_cm: 10",
                        "  page_height_cm: 20",
                        "table_style:",
                        "  header_bold: false",
                        "  header_fill: ''",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(document, template_path=None, config_path=config_path, image_loader=lambda _asset: None)
            rendered = Document(io.BytesIO(content))

        xml = self._document_xml(content)
        self.assertAlmostEqual(rendered.sections[0].page_width.cm, Cm(10).cm, places=1)
        self.assertAlmostEqual(rendered.sections[0].page_height.cm, Cm(20).cm, places=1)
        self.assertNotIn("<w:b/>", xml)
        self.assertNotIn("<w:b ", xml)
        self.assertNotIn("<w:shd", xml)

    def test_render_to_bytes_uses_configured_heading_word_style_when_available(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_heading_style", source_file_id="file_heading_style", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_heading",
                    type="heading",
                    order=0,
                    level=2,
                    text="Configured title style",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                (
                    "schema_version: template-config/v1\n"
                    "heading2:\n"
                    "  word_style_name: Title\n"
                    "  font_size: 14\n"
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(
                document,
                template_path=None,
                config_path=config_path,
                image_loader=lambda _asset: None,
            )
            rendered = Document(io.BytesIO(content))

        self.assertEqual(rendered.paragraphs[0].style.name, "Title")

    def test_render_to_bytes_preserves_portrait_section_for_wide_table_page(self) -> None:
        renderer = DocumentIRWordRenderer()
        wide_row = "".join(f"<th>H{index}</th>" for index in range(8))
        wide_values = "".join(f"<td>V{index}</td>" for index in range(8))
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_wide", source_file_id="file_wide", document_language="en"),
            pages=[
                DocumentIRPage(index=0, width=612.0, height=792.0),
                DocumentIRPage(index=1, width=612.0, height=792.0),
            ],
            blocks=[
                DocumentIRBlock(
                    id="block_intro",
                    type="paragraph",
                    order=0,
                    text="Portrait intro",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72, 80, 260, 120), role="body", column_hint="left"),
                ),
                DocumentIRBlock(
                    id="block_wide_table",
                    type="table",
                    order=1,
                    html=f"<table><tr>{wide_row}</tr><tr>{wide_values}</tr></table>",
                    layout=DocumentIRBlockLayout(page_index=1, bbox=(40, 80, 572, 260), role="body", column_hint="wide"),
                ),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)
        grid_widths = [int(value) for value in re.findall(r'<w:gridCol w:w="(\d+)"', xml)]
        available_width = Emu(
            rendered.sections[-1].page_width
            - rendered.sections[-1].left_margin
            - rendered.sections[-1].right_margin
        )
        available_width_twips = available_width.twips

        self.assertEqual(len(rendered.sections), 1)
        self.assertEqual(rendered.sections[0].orientation, WD_ORIENTATION.PORTRAIT)
        self.assertEqual(rendered.sections[-1].orientation, WD_ORIENTATION.PORTRAIT)
        self.assertLess(rendered.sections[-1].page_width, rendered.sections[-1].page_height)
        self.assertNotIn('w:orient="landscape"', xml)
        self.assertEqual(len(rendered.tables[-1].columns), 8)
        self.assertEqual(len(grid_widths), 8)
        self.assertLessEqual(sum(grid_widths), available_width_twips + 8)

    def test_render_to_bytes_keeps_source_landscape_page_landscape(self) -> None:
        renderer = DocumentIRWordRenderer()
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_landscape", source_file_id="file_landscape", document_language="en"),
            pages=[DocumentIRPage(index=0, width=792.0, height=612.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_body",
                    type="paragraph",
                    order=0,
                    text="Landscape source content",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72, 80, 400, 120), role="body"),
                ),
            ],
        )

        content = renderer.render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _asset: None)
        rendered = Document(io.BytesIO(content))

        self.assertEqual(rendered.sections[-1].orientation, WD_ORIENTATION.LANDSCAPE)
        self.assertGreater(rendered.sections[-1].page_width, rendered.sections[-1].page_height)

    def test_render_to_bytes_renders_context_like_table_caption_as_body_text(self) -> None:
        renderer = DocumentIRWordRenderer()
        condition = (
            "at TA = +25°C, VS = ±5 V to ±15 V, VCM = VOUT = VS / 2, "
            "and RL = 10 kΩ connected to VS / 2 (unless otherwise noted)"
        )
        document = DocumentIR(
            metadata=DocumentIRMetadata(job_id="docjob_table_context", source_file_id="file_table_context", document_language="en"),
            blocks=[
                DocumentIRBlock(
                    id="block_table",
                    type="table",
                    order=0,
                    html="<table><tr><th>PARAMETER</th><th>VALUE</th></tr><tr><td>VOS</td><td>5</td></tr></table>",
                    captions=[condition],
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "template.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version: template-config/v1",
                        "normal:",
                        "  alignment: left",
                        "  first_line_indent_pt: 21",
                        "caption:",
                        "  alignment: center",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(document, template_path=None, config_path=config_path, image_loader=lambda _asset: None)
            rendered = Document(io.BytesIO(content))

        xml = self._document_xml(content)
        before_table_xml = xml[: xml.index("<w:tbl>")]
        self.assertEqual(rendered.paragraphs[0].text, condition)
        self.assertEqual(rendered.paragraphs[0].alignment, WD_ALIGN_PARAGRAPH.LEFT)
        self.assertIn('<w:jc w:val="left"', before_table_xml)
        self.assertNotIn('<w:jc w:val="center"', before_table_xml)

    def _document_xml(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            return docx_zip.read("word/document.xml").decode("utf-8")

    def _numbering_xml(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            return docx_zip.read("word/numbering.xml").decode("utf-8")

    def _settings_xml(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            return docx_zip.read("word/settings.xml").decode("utf-8")

    def _styles_xml(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            return docx_zip.read("word/styles.xml").decode("utf-8")

    def _first_media_bytes(self, content: bytes) -> bytes:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            media_name = next(name for name in docx_zip.namelist() if name.startswith("word/media/"))
            return docx_zip.read(media_name)

    def _document_text(self, content: bytes) -> str:
        root = ElementTree.fromstring(self._document_xml(content))
        return "".join(element.text or "" for element in root.iter() if element.tag.endswith("}t"))

    def _related_xml(self, content: bytes, prefix: str) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            part_name = next(name for name in docx_zip.namelist() if name.startswith(prefix) and name.endswith(".xml"))
            return docx_zip.read(part_name).decode("utf-8")

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

    def _make_v2_wide_between_columns_document(self) -> DocumentIR:
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_wide_between", source_file_id="file_wide_between", document_language="en"),
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
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 70, 380, 90), role="body", column_hint="right"),
                ),
                DocumentIRBlock(
                    id="block_wide_callout",
                    type="paragraph",
                    order=2,
                    text="Wide callout",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 180, 400, 220), role="body", column_hint="wide"),
                ),
                DocumentIRBlock(
                    id="block_left_b",
                    type="paragraph",
                    order=3,
                    text="Left B",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(0, 300, 150, 320), role="body", column_hint="left"),
                ),
                DocumentIRBlock(
                    id="block_right_b",
                    type="paragraph",
                    order=4,
                    text="Right B",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(220, 310, 380, 330), role="body", column_hint="right"),
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
