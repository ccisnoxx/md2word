"""验证参数正文的源换行、空行和公式能完整到达正式 DOCX。"""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.conversion.docx_rules.formula import scan_math_spans
from app.conversion.docx_rules.mineru_content import clean_markdown_document, clean_text
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.render_evidence import build_renderer_evidence
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


class ParameterParagraphLineBreakTests(unittest.TestCase):
    def convert(self, blocks):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "parameters.zip"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("content_list_v2.json", json.dumps([blocks], ensure_ascii=False))
                package.writestr("layout.json", json.dumps({
                    "pdf_info": [{"page_idx": 0, "page_size": [600, 800]}],
                }))
            return MinerUToDocumentIRService().convert_zip(
                path, job_id="parameter_lines", source_file_id="source", document_language="zh",
            )

    def test_parameter_groups_keep_seventeen_breaks_and_four_formulas_in_docx(self):
        # 只保留故障块的双组参数结构，型号、数值和正文均为脱敏夹具。
        formulas = [r"V _ {D D}", r"I _ {Q}", r"V _ {S S}", r"I _ {B}"]
        runs = [
            {"type": "text", "content": "参数组 A\n供电电压："},
            {"type": "equation_inline", "content": formulas[0]},
            {"type": "text", "content": "= 6 V\n静态电流："},
            {"type": "equation_inline", "content": formulas[1]},
            {"type": "text", "content": "= 12 nA\n测试温度：-35 °C\n正向电流：3 mA\n反向漏电：7 nA\n"
                "输出电压：2.5 V\n条件：x - y\n\n参数组 B\n供电电压："},
            {"type": "equation_inline", "content": formulas[2]},
            {"type": "text", "content": "= 9 V\n静态电流："},
            {"type": "equation_inline", "content": formulas[3]},
            {"type": "text", "content": "= 18 nA\n测试温度：-20 °C\n正向电流：5 mA\n反向漏电：9 nA\n"
                "输出电压：3.0 V\n条件：a - b\n测试结束"},
        ]
        source = (
            "参数组 A\n供电电压： $V _ {D D}$ = 6 V\n静态电流： $I _ {Q}$ = 12 nA\n"
            "测试温度：-35 °C\n正向电流：3 mA\n反向漏电：7 nA\n输出电压：2.5 V\n条件：x - y\n\n"
            "参数组 B\n供电电压： $V _ {S S}$ = 9 V\n静态电流： $I _ {B}$ = 18 nA\n"
            "测试温度：-20 °C\n正向电流：5 mA\n反向漏电：9 nA\n输出电压：3.0 V\n条件：a - b\n测试结束"
        )
        visible_lines = [
            "参数组 A", "供电电压： VDD = 6 V", "静态电流： IQ = 12 nA", "测试温度：-35°C",
            "正向电流：3 mA", "反向漏电：7 nA", "输出电压：2.5 V", "条件：x - y", "",
            "参数组 B", "供电电压： VSS = 9 V", "静态电流： IB = 18 nA", "测试温度：-20°C",
            "正向电流：5 mA", "反向漏电：9 nA", "输出电压：3.0 V", "条件：a - b", "测试结束",
        ]
        for payload in ({"content": {"paragraph_content": runs}}, {"text": source}):
            with self.subTest(source="runs" if "content" in payload else "string"):
                converted = self.convert([{"type": "paragraph", "bbox": [60, 80, 270, 680], **payload}])
                block, = converted.document.blocks
                self.assertEqual((block.type, block.text, block.list_items, block.level),
                    ("paragraph", source, None, None))
                self.assertEqual(block.text.count("\n"), 17)
                self.assertEqual([span.source for span in scan_math_spans(block.text)],
                    [f"${formula}$" for formula in formulas])
                self.assertEqual(converted.validation_report.fatal_count, 0)
                self.assertEqual(converted.document.metadata.source_block_count, 1)

                with tempfile.TemporaryDirectory() as directory:
                    config_path = Path(directory) / "justify.yaml"
                    config_path.write_text("schema_version: template-config/v1\nnormal:\n  alignment: justify\n", encoding="utf-8")
                    rendered = DocumentIRWordRenderer().render_to_result(converted.document,
                        template_path=None, config_path=config_path, image_loader=lambda _asset: None)
                evidence = build_renderer_evidence(converted.document, rendered.content, render_result=rendered)
                ensure_renderer_integrity(evidence)
                self.assertEqual(evidence["blocking_quality_flags"], [])
                self.assertEqual(evidence["formula_summary"]["formula_count"], 4)
                self.assertEqual(evidence["formula_summary"]["fallback_count"], 0)
                with zipfile.ZipFile(io.BytesIO(rendered.content)) as package:
                    root = ET.fromstring(package.read("word/document.xml"))
                    settings = ET.fromstring(package.read("word/settings.xml"))
                paragraph, = [node for node in root.findall("./w:body/w:p", NS)
                    if any(leaf.text == "参数组 A" for leaf in node.findall(".//w:t", NS))]
                self.assertEqual(len(paragraph.findall(".//w:br", NS)), 17)
                self.assertEqual(len(paragraph.findall(".//m:oMath", NS)), 4)
                self.assertEqual(len(paragraph.findall(".//m:sSub", NS)), 4)
                visible = "".join("\n" if leaf.tag == f"{{{NS['w']}}}br" else leaf.text or ""
                    for leaf in paragraph.iter()
                    if leaf.tag in {f"{{{NS['w']}}}t", f"{{{NS['m']}}}t", f"{{{NS['w']}}}br"})
                self.assertEqual(visible.split("\n"), visible_lines)
                self.assertEqual(paragraph.find("./w:pPr/w:jc", NS).get(qn("w:val")), "both")
                self.assertEqual(settings.find("./w:compat/w:doNotExpandShiftReturn", NS).get(qn("w:val")), "true")
                self.assertIsNone(paragraph.find("./w:pPr/w:numPr", NS))
                self.assertEqual(root.findall(".//w:tbl", NS), [])

    def test_ordinary_lines_and_single_line_minus_remain_paragraphs(self):
        texts = ["ordinary\nbody\n\nnext", "-40 °C", "x - y"]
        result = self.convert([{"type": "paragraph", "text": text} for text in texts])
        self.assertEqual([block.type for block in result.document.blocks], ["paragraph"] * 3)
        self.assertEqual([block.text for block in result.document.blocks], texts)
        self.assertTrue(all(block.list_items is None and block.level is None for block in result.document.blocks))

    def test_string_and_runs_preserve_multiple_blank_lines_without_changing_heading_cleanup(self):
        source = "first\r\n\r\n\r\nsecond\rthird"
        result = self.convert([
            {"type": "paragraph", "text": source},
            {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": source}]}},
            {"type": "title", "content": {"title_content": [{"type": "text", "content": source}]}},
            {"type": "page_footer", "content": {"page_footer_content": [{"type": "text", "content": source}]}},
        ])
        self.assertEqual([block.text for block in result.document.blocks],
            ["first\n\n\nsecond\nthird", "first\n\n\nsecond\nthird", "first second third", "first second third"])
        self.assertEqual([block.type for block in result.document.blocks], ["paragraph", "paragraph", "heading", "paragraph"])

    def test_authoritative_sources_keep_lines_without_consuming_empty_nested_runs(self):
        source = "first\n\nsecond"
        result = self.convert([
            {"type": "paragraph", "text": source, "content": {"paragraph_content": []}},
            {"type": "paragraph", "content": [{"type": "text", "content": source}]},
        ])
        self.assertEqual([block.text for block in result.document.blocks], [source, source])
        self.assertEqual(result.validation_report.fatal_count, 0)

    def test_line_preserving_cleanup_keeps_math_whitespace_and_existing_defaults(self):
        formula = "\\frac { a  +\n b }{ c }"
        source = f"first\t  line\r\n\r\n\r\n${formula}$\rnext <details>隐藏</details>end"
        preserved = clean_text(source, preserve_line_breaks=True)
        self.assertEqual(preserved, f"first line\n\n\n${formula}$\nnext end")
        self.assertEqual([span.source for span in scan_math_spans(preserved)], [f"${formula}$"])
        self.assertEqual(clean_text(source), f"first line ${formula}$ next end")
        self.assertEqual(clean_markdown_document("first\n\n\nlast"), "first\n\nlast")

    def test_string_and_runs_keep_original_whitespace_inside_math_sources(self):
        formula = "\\frac { a  +\r\n b }{ c }"
        source = f"first\n ${formula}$ \nlast"
        result = self.convert([
            {"type": "paragraph", "text": source},
            {"type": "paragraph", "content": {"paragraph_content": [
                {"type": "text", "content": "first\n"},
                {"type": "equation_inline", "content": formula},
                {"type": "text", "content": "\nlast"},
            ]}},
        ])
        self.assertEqual([block.text for block in result.document.blocks], [source, source])
        for block in result.document.blocks:
            self.assertEqual([span.source for span in scan_math_spans(block.text)], [f"${formula}$"])

    def test_soft_break_compatibility_is_enabled_only_for_multiline_body(self):
        cases = [
            ({"type": "paragraph", "text": "first\nsecond"}, True),
            ({"type": "paragraph", "text": "single line"}, False),
            ({"type": "title", "text": "first\nsecond"}, False),
            ({"type": "page_footer", "text": "first\nsecond"}, False),
        ]
        for block, expected in cases:
            with self.subTest(source_type=block["type"], expected=expected):
                converted = self.convert([block])
                rendered = DocumentIRWordRenderer().render_to_result(converted.document,
                    template_path=None, config_path=None, image_loader=lambda _asset: None)
                with zipfile.ZipFile(io.BytesIO(rendered.content)) as package:
                    settings = ET.fromstring(package.read("word/settings.xml"))
                self.assertEqual(settings.find("./w:compat/w:doNotExpandShiftReturn", NS) is not None, expected)

    def test_soft_break_compatibility_preserves_template_settings_and_source_bytes(self):
        converted = self.convert([{"type": "paragraph", "text": "first\nsecond"}])
        for existing in (None, "false", "true", "missing_compat"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                template = Document()
                settings = template.settings.element
                compat = settings.find(qn("w:compat"))
                original_compat_settings = [ET.tostring(child) for child in compat.findall(qn("w:compatSetting"))]
                if existing == "missing_compat":
                    settings.remove(compat)
                    original_compat_settings = []
                else:
                    leading = OxmlElement("w:noLeading")
                    compat.insert(0, leading)
                    if existing is not None:
                        element = OxmlElement("w:doNotExpandShiftReturn")
                        element.set(qn("w:val"), existing)
                        compat.insert(1, element)
                path = Path(directory) / "template.docx"
                template.save(path)
                original_bytes = path.read_bytes()
                rendered = DocumentIRWordRenderer().render_to_result(converted.document,
                    template_path=path, config_path=None, image_loader=lambda _asset: None)
                self.assertEqual(path.read_bytes(), original_bytes)
                with zipfile.ZipFile(io.BytesIO(rendered.content)) as package:
                    output_settings = ET.fromstring(package.read("word/settings.xml"))
                output_compat = output_settings.find("w:compat", NS)
                element, = output_compat.findall("w:doNotExpandShiftReturn", NS)
                self.assertEqual(element.get(qn("w:val")), "true")
                self.assertEqual([ET.tostring(child) for child in output_compat.findall("w:compatSetting", NS)],
                    original_compat_settings)
                if existing != "missing_compat":
                    self.assertIsNotNone(output_compat.find("w:noLeading", NS))
                    self.assertIsNotNone(output_compat.find("w:useFELayout", NS))
                    tags = [child.tag for child in output_compat]
                    self.assertLess(tags.index(qn("w:noLeading")), tags.index(qn("w:doNotExpandShiftReturn")))
                    self.assertLess(tags.index(qn("w:doNotExpandShiftReturn")), tags.index(qn("w:useFELayout")))
                else:
                    tags = [child.tag for child in output_settings]
                    self.assertLess(tags.index(qn("w:compat")), tags.index(qn("w:rsids")))


if __name__ == "__main__":
    unittest.main()
