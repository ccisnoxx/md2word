from __future__ import annotations

# tests/test_document_ir_word_renderer_layout.py: 覆盖 DocumentIRWordRenderer 的 v2 layout plan 路径。

import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENTATION
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
from app.services.renderer.evidence import build_renderer_evidence
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
            Path(__file__).resolve().parents[1] / "resources" / "template_configs" / "datasheet_template.yaml"
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
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[0].blocks], ["Left A", "Right A", "Left B", "Right B"])

    def test_build_layout_plan_keeps_explicit_wide_blocks_out_of_stable_two_column_regions(self) -> None:
        document = self._make_v2_wide_between_columns_document()

        plan = build_layout_plan(document)

        self.assertEqual(plan.mode, "layout_v2")
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["two_col", "one_col", "two_col"])
        self.assertEqual([block.text for block in plan.pages[0].regions[0].blocks], ["Left A", "Right A"])
        self.assertEqual([block.text for block in plan.pages[0].regions[1].blocks], ["Wide callout"])
        self.assertEqual([block.text for block in plan.pages[0].regions[2].blocks], ["Left B", "Right B"])

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
        self.assertEqual(evidence["layout_quality_flags"], ["layout_sample:block_0001"])
        self.assertTrue(evidence["docx_quality"]["editable_content_available"])
        self.assertFalse(evidence["docx_quality"]["image_only_suspected"])
        self.assertEqual(evidence["quality_flags"], [])

    def test_render_to_bytes_uses_two_column_table_for_v2_region(self) -> None:
        renderer = DocumentIRWordRenderer()

        content = renderer.render_to_bytes(
            self._make_v2_two_column_document(),
            template_path=None,
            config_path=None,
            image_loader=lambda _asset: None,
        )
        rendered = Document(io.BytesIO(content))
        xml = self._document_xml(content)

        self.assertGreaterEqual(len(rendered.tables), 1)
        self.assertIn("Left column", rendered.tables[0].cell(0, 0).text)
        self.assertIn("Right column", rendered.tables[0].cell(0, 1).text)
        self.assertTrue(any(paragraph.text == "Wide block" for paragraph in rendered.paragraphs))
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            self.assertIn(f'<w:{edge} w:val="none"', xml)

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

    def test_extracted_decorations_keep_normal_style_and_legacy_font_fallbacks(self) -> None:
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

        decoration_parts = (
            (rendered.sections[0].header.paragraphs[0], ("Header East", "Header East", "Header East")),
            (rendered.sections[0].footer.paragraphs[0], ("Normal East", "Normal West", "Normal Complex")),
        )
        for paragraph, (east_asia, western, complex_script) in decoration_parts:
            run = next(item for item in paragraph.runs if item.text)
            self.assertEqual(run.font.size.pt, 12)
            self.assertTrue(run.bold)
            self.assertEqual(str(run.font.color.rgb), "123456")
            self.assertEqual(paragraph.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
            self.assertEqual(paragraph.paragraph_format.space_before.pt, 2)
            self.assertEqual(paragraph.paragraph_format.space_after.pt, 3)
            run_fonts = run._element.rPr.rFonts
            self.assertEqual(run_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia"), east_asia)
            self.assertEqual(run_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii"), western)
            self.assertEqual(run_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hAnsi"), western)
            self.assertEqual(run_fonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}cs"), complex_script)

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
        self.assertLess(xml.index("Table 1: merged cells"), xml.index("<w:tbl>"))
        self.assertLess(xml.index("<w:tbl>"), xml.index("Note: kept editable"))
        self.assertIn("<w:keepNext/>", xml[: xml.index("<w:tbl>")])
        self.assertTrue(any(paragraph.text == "Table 1: merged cells" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Note: kept editable" for paragraph in rendered.paragraphs))

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

        self.assertIn("R</w:t>", xml)
        self.assertIn("θJA", xml)
        self.assertIn("Table 1: R", xml)
        self.assertIn("nV/√Hz", xml)
        self.assertIn("Note: E=mc", xml)
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

        self.assertIn("T", xml)
        self.assertIn("A</w:t>", xml)
        self.assertIn("+25°C", xml)
        self.assertIn("5 μs", xml)
        self.assertIn('w:val="subscript"', xml)
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

        self.assertIn("√Hz", xml)
        self.assertIn("5 μs", xml)
        self.assertIn("PACKAGE", xml)
        self.assertIn("-40°C", xml)
        self.assertIn("θJC(top)", xml)
        self.assertIn("ψ", xml)
        self.assertIn("±5", xml)
        self.assertIn("CM", xml)
        self.assertIn("R", xml)
        self.assertIn("L", xml)
        self.assertIn("nV/√Hz", xml)
        self.assertIn("μV/°C", xml)
        self.assertIn('w:val="subscript"', xml)
        self.assertIn('w:val="superscript"', xml)
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
        extent_match = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml)

        self.assertIsNotNone(extent_match)
        self.assertLess(int(extent_match.group(1)), 3_000_000)
        self.assertLess(xml.index("<w:keepNext/>"), xml.index("<w:drawing>"))
        self.assertLess(xml.index("<w:drawing>"), xml.index("Figure 1: V"))
        self.assertLess(xml.index("Figure 1: V"), xml.index("Source: 5 μs MinerU"))
        self.assertGreaterEqual(xml.count("<w:keepNext/>"), 2)
        self.assertIn('w:val="subscript"', xml)
        self.assertNotIn(r"\mu", xml)
        self.assertTrue(any(paragraph.text == "Figure 1: VOS bbox-sized chart" for paragraph in rendered.paragraphs))
        self.assertTrue(any(paragraph.text == "Source: 5 μs MinerU" for paragraph in rendered.paragraphs))

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
        self.assertIn('w:val="subscript"', xml)
        self.assertIn('w:val="superscript"', xml)
        self.assertIn("nV/√Hz", xml)
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

    def test_render_to_bytes_promotes_heading_like_paragraphs_to_word_headings(self) -> None:
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

    def test_render_to_bytes_uses_tab_leaders_for_toc_like_entries(self) -> None:
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

        self.assertEqual(rendered.paragraphs[1].text, "Features\t1")
        self.assertEqual(rendered.paragraphs[2].text, "特性\t1")
        self.assertEqual(rendered.paragraphs[3].text, "目录\t3")
        self.assertEqual(rendered.paragraphs[4].text, "Appendix A Device Pinout\t120")
        self.assertEqual(rendered.paragraphs[5].text, "Updated numbering")
        self.assertGreaterEqual(xml.count("<w:tab/>"), 4)
        self.assertGreaterEqual(xml.count('w:leader="dot"'), 4)
        self.assertEqual(xml.count("<w:numPr>"), 1)

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
                        "  font_size: 10",
                        "  color: '#778899'",
                        "  alignment: left",
                    ]
                ),
                encoding="utf-8",
            )

            content = renderer.render_to_bytes(document, template_path=None, config_path=config_path, image_loader=lambda _asset: None)

        xml = self._document_xml(content)
        self.assertIn('w:val="112233"', xml)
        self.assertIn('w:val="445566"', xml)
        self.assertIn('w:val="778899"', xml)
        self.assertGreaterEqual(xml.count('w:leader="dot"'), 2)

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

        self.assertGreaterEqual(len(rendered.sections), 1)
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
