"""RND-502 的数学语义、受控降级和最终字节绑定回归。"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import time
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from xml.etree import ElementTree as ET

from docx import Document

from app.conversion.docx_rules.formula import (
    FORMULA_FALLBACK_NOTICE,
    formula_block_span,
    render_formula,
    scan_math_spans,
)
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata
from app.services.renderer.docx_quality import analyze_docx_quality_bytes, validate_formula_report
from app.services.renderer.evidence import build_renderer_evidence, ensure_renderer_integrity
from app.services.renderer.word_renderer import DocumentIRWordRenderer

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter() if node.tag in {f"{{{NS['w']}}}t", f"{{{NS['m']}}}t"})


def document(*blocks: DocumentIRBlock) -> DocumentIR:
    return DocumentIR(metadata=DocumentIRMetadata(job_id="formula_job", source_file_id="formula_source", document_language="zh"), blocks=list(blocks))


def render(ir: DocumentIR):
    return DocumentIRWordRenderer().render_to_result(ir, template_path=None, config_path=None, image_loader=lambda _: None)


def xml_of(content: bytes) -> ET.Element:
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        return ET.fromstring(package.read("word/document.xml"))


def changed_docx(content: bytes, change) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as original, zipfile.ZipFile(output, "w") as target:
        for entry in original.infolist():
            value = original.read(entry.filename)
            if entry.filename == "word/document.xml":
                root = ET.fromstring(value)
                change(root)
                value = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(entry, value)
    return output.getvalue()


class FormulaParserTests(unittest.TestCase):
    def math(self, source: str):
        result = render_formula(formula_block_span(source))
        self.assertEqual(result.mode, "omml")
        return result.elements[0]

    def test_supported_structures_keep_values_and_styles(self):
        root = self.math(r"\frac{a_1}{\sqrt[3]{x}}+\overline{AB}+\boxed{z}+\mathit{q}+\mathbf{r}+\Phi")
        self.assertEqual(text_of(root), "a13x+AB+z+q+r+Φ")
        for tag in ("f", "sSub", "rad", "bar", "borderBox"):
            self.assertEqual(len(root.findall(f".//m:{tag}", NS)), 1)
        self.assertEqual(text_of(root.find(".//m:deg", NS)), "3")
        self.assertEqual(root.find(".//m:barPr/m:pos", NS).get(f"{{{NS['m']}}}val"), "top")
        styled = {text_of(node): node.find("m:rPr/m:sty", NS).get(f"{{{NS['m']}}}val") for node in root.findall(".//m:r", NS)}
        self.assertEqual(styled["q"], "i")
        self.assertEqual(styled["r"], "b")
        self.assertEqual(styled["Φ"], "p")

    def test_bare_exponent_consumes_one_token(self):
        root = self.math("x^2+3")
        script = root.find("m:sSup", NS)
        self.assertEqual(text_of(script.find("m:e", NS)), "x")
        self.assertEqual(text_of(script.find("m:sup", NS)), "2")
        self.assertEqual(text_of(root[-1]), "+3")

    def test_explicit_group_is_the_complete_script_base(self):
        for expression, base in (("a+b", "a+b"), (r"\frac{a}{b}+c", "ab+c")):
            for marker, tag, argument in (("^", "sSup", "2"), ("_", "sSub", "min")):
                with self.subTest(expression=expression, marker=marker):
                    root = self.math("{" + expression + "}" + marker + "{" + argument + "}")
                    self.assertEqual(len(root), 1)
                    script = root.find("m:" + tag, NS)
                    self.assertIsNotNone(script)
                    self.assertEqual(text_of(script.find("m:e", NS)), base)
                    self.assertEqual(text_of(script[-1]), argument)

    def test_text_wrappers_preserve_internal_spaces(self):
        for command in ("text", "mathrm", "mathsf"):
            with self.subTest(command=command):
                self.assertEqual(text_of(self.math("\\" + command + "{A B  C}")), "A B  C")

    def test_scripted_command_keeps_full_text_atom_and_explicit_style(self):
        root = self.math(r"\text{A B}^2")
        self.assertEqual(len(root), 1)
        self.assertEqual(text_of(root.find("m:sSup/m:e", NS)), "A B")
        for command, style in (("mathit", "i"), ("mathbf", "b")):
            with self.subTest(command=command):
                root = self.math("\\" + command + "{x}^2")
                self.assertEqual(root.find("m:sSup/m:e//m:sty", NS).get(f"{{{NS['m']}}}val"), style)

    def test_nested_script_text_wrappers_preserve_internal_spaces(self):
        for marker in ("_", "^"):
            for command in ("text", "mathrm", "mathsf"):
                with self.subTest(marker=marker, command=command):
                    root = self.math("x" + marker + "{\\" + command + "{A B  C}}")
                    self.assertEqual(text_of(root), "xA B  C")

    def test_vee_is_logical_symbol_and_tag_keeps_number(self):
        root = self.math(r"a\vee b+\frac{1}{2}\tag{7}")
        self.assertIn("∨", text_of(root))
        self.assertNotIn("V", text_of(root))
        self.assertTrue(text_of(root).endswith(" (7)"))
        self.assertEqual(len(root.findall(".//m:f", NS)), 1)

    def test_expected_failures_preserve_exact_source_and_reason(self):
        cases = {
            r"\unknown{a<2 & b}": "unsupported_command",
            r"\frac{1}{2": "invalid_syntax",
            r"\begin{matrix}a&b\end{matrix}": "unsupported_structure",
            r"\begin{cases}x\end{cases}": "unsupported_structure",
            r"\frac{\text{a}\unknown{x}}{2}": "unsupported_command",
            r"x\tag{\frac{1}{2}}": "unsupported_structure",
            r"x\tag{7": "invalid_syntax",
            r"x\tag{7}+y": "unsupported_structure",
            r"\text{<b>A B</b>}": "unsafe_normalization",
        }
        for source, reason in cases.items():
            with self.subTest(source=source):
                result = render_formula(formula_block_span(source))
                self.assertEqual(result.mode, "text_fallback")
                self.assertEqual(result.reason, reason)
                self.assertEqual("".join(text_of(node) for node in result.elements), FORMULA_FALLBACK_NOTICE + source)

    def test_empty_input_fails_and_internal_errors_propagate(self):
        for source in ("", " ", "$$", "<eq></eq>"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                render_formula(formula_block_span(source))
        with patch("app.conversion.docx_rules.formula._OmmlParser.parse", side_effect=RuntimeError("内部错误")):
            with self.assertRaises(RuntimeError):
                render_formula(formula_block_span("x"))

    def test_unclosed_explicit_math_is_registered_and_falls_back(self):
        for source in (r"\(x^2", r"\[x^2", "<eq>x^2", "$x^2"):
            with self.subTest(source=source):
                spans = scan_math_spans(source)
                self.assertEqual(len(spans), 1)
                result = render_formula(spans[0])
                self.assertEqual(result.reason, "invalid_syntax")
                self.assertEqual("".join(text_of(node) for node in result.elements), FORMULA_FALLBACK_NOTICE + source)
                block = render_formula(formula_block_span(source))
                self.assertEqual(block.reason, "invalid_syntax")
                self.assertEqual("".join(text_of(node) for node in block.elements), FORMULA_FALLBACK_NOTICE + source)

    def test_bare_scripts_keep_the_complete_expression_and_command_scope(self):
        for source, text in (("V_{OUT}", "VOUT"), (r"R_{\theta JA}", "RθJA"), (r"x_{\text{A B}}", "xA B")):
            with self.subTest(source=source):
                spans = scan_math_spans(source)
                self.assertEqual(len(spans), 1)
                self.assertEqual(spans[0].source, source)
                rendered = render_formula(spans[0])
                self.assertIn(rendered.mode, {"omml", "semantic_runs"})
                self.assertEqual("".join(text_of(node) for node in rendered.elements), text)
        source = r"\frac{V_{OUT}}{2}"
        self.assertEqual([span.source for span in scan_math_spans(source)], [source])

    def test_malformed_or_nested_semantic_scripts_preserve_literal_source(self):
        for source, reason in (("V<sub><b>High", "invalid_syntax"),
                               ("V<sub>High</sup>", "invalid_syntax"),
                               ("x<sub>i<sup>2</sup></sub>", "unsupported_structure"),
                               ("V<sub>$OUT$</sub>", "unsupported_structure"),
                               (r"V<sub>\(OUT\)</sub>", "unsupported_structure"),
                               ("V<sub><eq>OUT</eq></sub>", "unsupported_structure"),
                               (r"V<sub>\frac{a}{b}</sub>", "unsupported_structure"),
                               ("V<sub>x^2</sub>", "unsupported_structure")):
            with self.subTest(source=source):
                spans = scan_math_spans(source)
                self.assertEqual(len(spans), 1)
                self.assertEqual(spans[0].source, source)
                result = render_formula(spans[0])
                self.assertEqual(result.reason, reason)
                self.assertEqual("".join(text_of(node) for node in result.elements), FORMULA_FALLBACK_NOTICE + source)

    def test_long_plain_and_mixed_text_scanning_avoids_quadratic_backtracking(self):
        started = time.perf_counter()
        for source in ("a" * 60000, "a" * 60000 + " V<sub>OUT</sub> x^2"):
            spans = scan_math_spans(source)
        self.assertEqual([span.source for span in spans], ["V<sub>OUT</sub>", "x^2"])
        self.assertLess(time.perf_counter() - started, 3.0)

    def test_scanner_preserves_offsets_and_ordinary_boundaries(self):
        source = r"前 $x^2$ 中 \(a+b\) 后 $$\frac{1}{2}$$ 与 <eq>\text{A B}</eq>"
        spans = scan_math_spans(source)
        self.assertEqual(len(spans), 4)
        self.assertEqual([source[span.start:span.end] for span in spans], [span.source for span in spans])
        for ordinary in (r"C:\work\file_name", r"\\server\share\file", r"C:\theta\file", r"\\theta\file", "$5 and $10", r"\$5", "ordinary_name", "a < b & c > d"):
            with self.subTest(ordinary=ordinary):
                self.assertEqual(scan_math_spans(ordinary), ())
        self.assertEqual([span.source for span in scan_math_spans("输出V<sub>OUT</sub>")], ["V<sub>OUT</sub>"])


class FormulaRenderEvidenceTests(unittest.TestCase):
    def test_saved_left_right_math_keeps_binding_in_block_inline_and_table(self):
        for expression, visible in ((r"\left(\frac{1}{2}\right)", "(12)"),
                                    (r"\left[\frac{1}{2}\right]", "[12]")):
            blocks = (
                DocumentIRBlock(id="block", type="formula", order=0, latex=expression),
                DocumentIRBlock(id="inline", type="paragraph", order=0, text="前 $" + expression + "$ 后"),
                DocumentIRBlock(id="table", type="table", order=0,
                    html="<table><tr><td>$" + expression + "$</td></tr></table>"),
            )
            for block in blocks:
                with self.subTest(expression=expression, entry=block.type):
                    ir = document(block)
                    result = render(ir)
                    evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
                    ensure_renderer_integrity(evidence)
                    self.assertEqual(evidence["formula_summary"]["omml_count"], 1)
                    self.assertEqual(evidence["formula_summary"]["fallback_count"], 0)
                    math = xml_of(result.content).find(".//m:oMath", NS)
                    self.assertEqual(text_of(math), visible)
                    self.assertEqual(text_of(math.find(".//m:num", NS)), "1")
                    self.assertEqual(text_of(math.find(".//m:den", NS)), "2")

    def test_saved_script_arguments_preserve_styles_and_reject_style_tampering(self):
        for expression, tag, value, style in ((r"x_{\mathit{out}}", "sub", "out", "i"),
                                             (r"x^{\mathbf{n}}", "sup", "n", "b"),
                                             (r"x_{\boldsymbol{n}}", "sub", "n", "b"),
                                             ("x_{O U T}", "sub", "OUT", "p"),
                                             ("x^{1 2 3}", "sup", "123", "p")):
            with self.subTest(expression=expression):
                ir = document(DocumentIRBlock(id="block", type="formula", order=0, latex=expression))
                result = render(ir)
                evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
                ensure_renderer_integrity(evidence)
                self.assertEqual(evidence["formula_summary"]["omml_count"], 1)
                argument = xml_of(result.content).find(".//m:" + tag, NS)
                self.assertEqual(text_of(argument), value)
                self.assertEqual(argument.find(".//m:sty", NS).get(f"{{{NS['m']}}}val"), style)
                def change_style(root):
                    root.find(".//m:" + tag + "//m:sty", NS).set(f"{{{NS['m']}}}val", "p" if style != "p" else "b")
                with self.assertRaisesRegex(ValueError, "预期绑定"):
                    build_renderer_evidence(ir, changed_docx(result.content, change_style), formula_report=result.formula_report)

    def test_invisible_delimiters_fall_back_whole_in_block_inline_and_table(self):
        for expression in (r"\left.\frac{1}{2}\right|_{0}^{1}",
                           r"\left .\frac{1}{2}\right|_{0}^{1}",
                           r"\left(\frac{1}{2}\right.",
                           r"\left[\frac{1}{2}\right ."):
            delimited = "$" + expression + "$"
            cases = (
                (DocumentIRBlock(id="block", type="formula", order=0, latex=expression), "latex", expression),
                (DocumentIRBlock(id="inline", type="paragraph", order=0, text="前 " + delimited + " 后"), "text", delimited),
                (DocumentIRBlock(id="table", type="table", order=0,
                    html="<table><tr><td>" + delimited + "</td></tr></table>"), "html/0/0", delimited),
            )
            for block, field, source in cases:
                with self.subTest(expression=expression, entry=block.type):
                    ir = document(block)
                    result = render(ir)
                    evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
                    ensure_renderer_integrity(evidence)
                    self.assertEqual(evidence["formula_summary"]["formula_count"], 1)
                    self.assertEqual(evidence["formula_summary"]["fallback_count"], 1)
                    self.assertEqual(evidence["formula_summary"]["reason_counts"], {"unsupported_structure": 1})
                    self.assertIn("formula_text_fallback", evidence["quality_flags"])
                    self.assertEqual(evidence["blocking_quality_flags"], [])
                    entry = result.formula_report["entries"][0]
                    self.assertEqual((entry["mode"], entry["reason"]), ("text_fallback", "unsupported_structure"))
                    self.assertEqual((entry["source"]["block_id"], entry["source"]["field"]), (block.id, field))
                    self.assertEqual(entry["source"]["source_sha256"], hashlib.sha256(source.encode("utf-8")).hexdigest())
                    root = xml_of(result.content)
                    self.assertIn(FORMULA_FALLBACK_NOTICE + source, text_of(root))
                    self.assertEqual(root.findall(".//m:oMath", NS), [])

    def test_empty_math_text_normalization_still_rejects_content_and_node_changes(self):
        ir = document(DocumentIRBlock(id="block", type="formula", order=0, latex=r"\left(\frac{1}{2}\right)"))
        result = render(ir)
        def remove_digit(root):
            root.find(".//m:num//m:t", NS).text = None
        def change_digit(root):
            root.find(".//m:den//m:t", NS).text = "3"
        def add_empty_run(root):
            run = ET.SubElement(root.find(".//m:oMath", NS), f"{{{NS['m']}}}r")
            ET.SubElement(run, f"{{{NS['m']}}}t")
        for change in (remove_digit, change_digit, add_empty_run):
            with self.subTest(change=change.__name__), self.assertRaisesRegex(ValueError, "预期绑定"):
                build_renderer_evidence(ir, changed_docx(result.content, change), formula_report=result.formula_report)

    def test_previously_successful_v1_math_projection_remains_compatible(self):
        ir = document(DocumentIRBlock(id="normal", type="formula", order=0, latex=r"\frac{1}{2}"))
        result = render(ir)
        # 修复前已通过最终字节校验的 v1 签名，避免空文本修复改变成功历史件的读法。
        previous_sha256 = "d21e8504c07b4c5aad1233156f3b558832f06b330204217bd4806ad8daa5a038"
        self.assertEqual(result.formula_report["entries"][0]["expected_output_sha256"], previous_sha256)
        report = copy.deepcopy(result.formula_report)
        report["entries"][0]["expected_output_sha256"] = previous_sha256
        evidence = build_renderer_evidence(ir, result.content, formula_report=report)
        ensure_renderer_integrity(evidence)

    def test_numeric_formulas_register_in_block_inline_and_native_table(self):
        ir = document(DocumentIRBlock(id="inline", type="paragraph", order=0, text="Value $123.45$"),
            DocumentIRBlock(id="block", type="formula", order=1, latex="123.45"),
            DocumentIRBlock(id="cell", type="table", order=2, html="<table><tr><td>$123.45$</td></tr></table>"))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        self.assertEqual(evidence["formula_summary"]["omml_count"], 3)
        self.assertEqual(evidence["docx_quality"]["latex_residue_count"], 0)
        self.assertEqual([text_of(math) for math in xml_of(result.content).findall(".//m:oMath", NS)], ["123.45"] * 3)

    def test_same_formula_binds_actual_block_and_field_after_reordering(self):
        ir = document(DocumentIRBlock(id="later", type="paragraph", order=3, text="later $x^2$"),
            DocumentIRBlock(id="table", type="table", order=2, html="<table><tr><td>$x^2$</td></tr></table>",
                captions=["Table 1: $x^2$"], footnotes=["Note $x^2$"]),
            DocumentIRBlock(id="first", type="paragraph", order=0, text="first $x^2$"))
        result = render(ir)
        build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        root = xml_of(result.content)
        parents = {id(child): parent for parent in root.iter() for child in parent}
        expected = [("first", "text"), ("table", "captions/0"), ("table", "html/0/0"), ("table", "footnotes/0"), ("later", "text")]
        self.assertEqual([(entry["source"]["block_id"], entry["source"]["field"]) for entry in result.formula_report["entries"]], expected)
        for entry in result.formula_report["entries"]:
            anchor = root.find(f".//w:bookmarkStart[@w:name='{entry['anchor']}']", NS)
            paragraph = parents[id(anchor)]
            field = entry["source"]["field"]
            if field == "html/0/0":
                self.assertEqual(parents[id(paragraph)].tag, f"{{{NS['w']}}}tc")
            elif field == "captions/0":
                self.assertTrue(text_of(paragraph).startswith("Table 1:"))
            elif field == "footnotes/0":
                self.assertTrue(text_of(paragraph).startswith("Note "))
            else:
                self.assertTrue(text_of(paragraph).startswith(entry["source"]["block_id"] + " "))

    def test_matching_table_caption_and_note_each_register_their_formula(self):
        annotation = "Table 1: $x^2$"
        ir = document(DocumentIRBlock(id="table", type="table", order=0,
            html="<table><tr><td>body</td></tr></table>",
            captions=[annotation, annotation], footnotes=[annotation, annotation]))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["formula_count"], 2)
        self.assertEqual([entry["source"]["field"] for entry in result.formula_report["entries"]], ["captions/0", "footnotes/0"])

    def test_expanded_table_keeps_markup_and_each_repeated_source_formula(self):
        html = '<table><tr><td rowspan="2" colspan="2"><b>V<sub>OUT</sub></b> $x^2$</td><td>' + "a" * 30001 + '</td></tr><tr><td>tail</td></tr></table>'
        ir = document(DocumentIRBlock(id="large", type="table", order=0, html=html))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["formula_count"], 4)
        self.assertEqual(evidence["formula_summary"]["omml_count"], 2)
        self.assertEqual(evidence["formula_summary"]["semantic_count"], 2)
        self.assertEqual({entry["source"]["field"] for entry in result.formula_report["entries"]}, {"html/0/0"})
        root = xml_of(result.content)
        self.assertEqual(len(root.findall(".//w:tbl", NS)), 1)
        self.assertEqual(len(root.findall(".//w:tr", NS)), 2)
        self.assertEqual([len(row.findall("w:tc", NS)) for row in root.findall(".//w:tr", NS)], [3, 3])
        self.assertEqual(len(root.findall(".//m:sSup", NS)), 2)
        self.assertEqual(text_of(root).count("VOUT"), 2)
        self.assertEqual(text_of(root).count("a" * 30001), 1)

    def test_all_body_entries_preserve_order_and_each_occurrence(self):
        expression = r"\frac{1}{2}+x^2\tag{7}"
        delimited = "$" + expression + "$"
        ir = document(
            DocumentIRBlock(id="heading", type="heading", order=0, text="标题 " + delimited),
            DocumentIRBlock(id="paragraph", type="paragraph", order=1, text="前 <b>粗体 " + delimited + " 后</b>，" + delimited),
            DocumentIRBlock(id="list", type="list", order=2, list_items=["• 列表 " + delimited]),
            DocumentIRBlock(id="formula", type="formula", order=3, latex=expression),
            DocumentIRBlock(id="table", type="table", order=4, html="<table><tr><td><b>表格</b> " + delimited + " <i>尾</i></td></tr></table>", captions=["Table 1: " + delimited], footnotes=["注 " + delimited]),
            DocumentIRBlock(id="context", type="paragraph", order=5, text="条件 " + delimited, metadata={"annotation_role": "table_context"}),
        )
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["formula_count"], 9)
        self.assertEqual(evidence["formula_summary"]["omml_count"], 9)
        self.assertEqual(evidence["formula_summary"]["fallback_count"], 0)
        root = xml_of(result.content)
        self.assertEqual(len(root.findall(".//w:tbl", NS)), 1)
        self.assertEqual(len(root.findall(".//m:f", NS)), 9)
        self.assertEqual(len(root.findall(".//m:sSup", NS)), 9)
        self.assertEqual(text_of(root).count(" (7)"), 9)
        self.assertTrue(all("标题" not in text_of(math) and "表格" not in text_of(math) for math in root.findall(".//m:oMath", NS)))
        self.assertIn(" SEQ Table ", "".join(node.text or "" for node in root.findall(".//w:instrText", NS)))
        self.assertEqual(evidence["blocking_quality_flags"], [])

    def test_mixed_markup_stays_outside_math(self):
        ir = document(DocumentIRBlock(id="t", type="table", order=0, html=r"<table><tr><td><b>before</b> $\frac{1}{2}$ V<sub>OUT</sub> <sup>2</sup> <i>after</i></td></tr></table>"))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        self.assertEqual(evidence["formula_summary"]["omml_count"], 1)
        self.assertEqual(evidence["formula_summary"]["semantic_count"], 2)
        root = xml_of(result.content)
        self.assertEqual(text_of(root.find(".//m:oMath", NS)), "12")
        self.assertTrue(any(text_of(run) == "before" and run.find("w:rPr/w:b", NS) is not None for run in root.findall(".//w:r", NS)))
        self.assertTrue(any(text_of(run) == "after" and run.find("w:rPr/w:i", NS) is not None for run in root.findall(".//w:r", NS)))
        self.assertTrue(any(text_of(run) == "OUT" and run.find("w:rPr/w:vertAlign", NS).get(f"{{{NS['w']}}}val") == "subscript" for run in root.findall(".//w:r", NS) if run.find("w:rPr/w:vertAlign", NS) is not None))
        self.assertNotIn("<b>", text_of(root))

    def test_semantic_scripts_keep_nested_styles_and_line_breaks(self):
        ir = document(DocumentIRBlock(id="p", type="paragraph", order=0,
            text="V<sub><b>High</b><br/><i>Low</i></sub> x<sup><i>2</i></sup>"))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["semantic_count"], 2)
        root = xml_of(result.content)
        self.assertEqual(text_of(root), "VHighLow x2")
        self.assertEqual(len(root.findall(".//w:br", NS)), 1)
        self.assertTrue(any(text_of(run) == "High" and run.find("w:rPr/w:b", NS) is not None
                            for run in root.findall(".//w:r", NS)))
        self.assertTrue(any(text_of(run) == "Low" and run.find("w:rPr/w:i", NS) is not None
                            for run in root.findall(".//w:r", NS)))

    def test_fallback_has_private_source_hash_warning_and_unregistered_residue_remains(self):
        source = "$\\unknown{a<2 & b}$"
        ir = document(DocumentIRBlock(id="p", type="paragraph", order=0, text=source + r" 普通 \unregistered{x}"))
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        self.assertIn(FORMULA_FALLBACK_NOTICE + source, text_of(xml_of(result.content)))
        self.assertEqual(evidence["formula_summary"]["fallback_count"], 1)
        self.assertIn("formula_text_fallback", evidence["quality_flags"])
        self.assertEqual(evidence["docx_quality"]["latex_residue_count"], 1)
        self.assertTrue(any(flag.startswith("docx_latex_residue:") for flag in evidence["quality_flags"]))
        self.assertEqual(evidence["blocking_quality_flags"], [])
        self.assertNotIn("unknown", json.dumps(result.formula_report))
        self.assertNotIn(source, json.dumps(evidence["formula_summary"]))
        self.assertGreater(analyze_docx_quality_bytes(result.content)["latex_residue_count"], 1)

    def test_output_binding_rejects_changed_digit_script_and_math_style(self):
        ir = document(DocumentIRBlock(id="f", type="formula", order=0, latex=r"\frac{x^2}{\mathit{y}}"))
        result = render(ir)
        def digit(root):
            root.find(".//m:sup/m:r/m:t", NS).text = "3"
        def script(root):
            root.find(".//m:sup", NS).tag = f"{{{NS['m']}}}sub"
        def style(root):
            root.find(".//m:rPr/m:sty", NS).set(f"{{{NS['m']}}}val", "b")
        for change in (digit, script, style):
            with self.subTest(change=change.__name__), self.assertRaisesRegex(ValueError, "预期绑定"):
                build_renderer_evidence(ir, changed_docx(result.content, change), formula_report=result.formula_report)

    def test_fallback_binding_rejects_truncation_and_missing_notice(self):
        ir = document(DocumentIRBlock(id="f", type="formula", order=0, latex=r"\unknown{abcdef}"))
        result = render(ir)
        def truncate(root):
            root.findall(".//w:t", NS)[1].text = r"\unknown{abc}"
        def notice(root):
            root.findall(".//w:t", NS)[0].text = ""
        for change in (truncate, notice):
            with self.subTest(change=change.__name__), self.assertRaisesRegex(ValueError, "预期绑定"):
                build_renderer_evidence(ir, changed_docx(result.content, change), formula_report=result.formula_report)

    def test_semantic_binding_rejects_moved_superscript(self):
        ir = document(DocumentIRBlock(id="p", type="paragraph", order=0, text="V<sub>OUT</sub>"))
        result = render(ir)
        def move(root):
            root.find(".//w:vertAlign", NS).set(f"{{{NS['w']}}}val", "superscript")
        with self.assertRaisesRegex(ValueError, "预期绑定"):
            build_renderer_evidence(ir, changed_docx(result.content, move), formula_report=result.formula_report)

    def test_output_binding_rejects_added_run_nodes_and_hidden_properties(self):
        for source, kind in ((r"\unknown{x}", "formula"), ("V<sub>OUT</sub>", "paragraph"), (r"\frac{x}{2}", "formula")):
            ir = document(DocumentIRBlock(id="f", type=kind, order=0, **({"latex": source} if kind == "formula" else {"text": source})))
            result = render(ir)
            for tag in ("noBreakHyphen", "cr", "sym", "fldChar", "instrText", "vanish", "webHidden", "position"):
                def add(root, tag=tag):
                    run = root.find(".//m:r", NS) if result.formula_report["entries"][0]["mode"] == "omml" else root.find(".//w:r", NS)
                    node = ET.Element(f"{{{NS['w']}}}{tag}")
                    if tag in {"vanish", "webHidden", "position"}:
                        properties = ET.SubElement(run, f"{{{NS['w']}}}rPr")
                        properties.append(node)
                        if tag == "position":
                            node.set(f"{{{NS['w']}}}val", "20")
                    else:
                        run.append(node)
                        if tag == "sym":
                            node.set(f"{{{NS['w']}}}char", "0041")
                        elif tag == "fldChar":
                            node.set(f"{{{NS['w']}}}fldCharType", "begin")
                        elif tag == "instrText":
                            node.text = " PAGE "
                with self.subTest(mode=result.formula_report["entries"][0]["mode"], tag=tag), self.assertRaisesRegex(ValueError, "预期绑定"):
                    build_renderer_evidence(ir, changed_docx(result.content, add), formula_report=result.formula_report)

    def test_missing_duplicate_or_forged_anchor_is_rejected(self):
        ir = document(DocumentIRBlock(id="f", type="formula", order=0, latex="x^2"))
        result = render(ir)
        def missing(root):
            root.find(".//w:bookmarkStart", NS).set(f"{{{NS['w']}}}name", "missing")
        def duplicate(root):
            parent = root.find(".//w:p", NS)
            parent.append(copy.deepcopy(parent.find("w:bookmarkStart", NS)))
        def unregistered(root):
            root.find(".//w:p", NS).append(copy.deepcopy(root.find(".//m:oMath", NS)))
        for change in (missing, duplicate, unregistered):
            with self.subTest(change=change.__name__), self.assertRaises(ValueError):
                build_renderer_evidence(ir, changed_docx(result.content, change), formula_report=result.formula_report)

    def test_report_source_and_occurrence_cannot_self_certify(self):
        ir = document(DocumentIRBlock(id="p", type="paragraph", order=0, text="$x^2$ $x^2$"))
        result = render(ir)
        for field, value in (("source_sha256", "0" * 64), ("start", 20), ("block_id", "other")):
            report = copy.deepcopy(result.formula_report)
            report["entries"][0]["source"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_renderer_evidence(ir, result.content, formula_report=report)
        report = copy.deepcopy(result.formula_report)
        report["entries"].pop()
        with self.assertRaises(ValueError):
            build_renderer_evidence(ir, result.content, formula_report=report)

    def test_report_schema_is_strict_and_has_no_success_default(self):
        ir = document(DocumentIRBlock(id="f", type="formula", order=0, latex="x"))
        report = render(ir).formula_report
        invalids = [None, [], {}, {"schema_version": "formula-render/v9", "entries": []}]
        for field, value in (("occurrence", True), ("reason", "bad"), ("mode", "unknown"), ("expected_output_sha256", "bad")):
            invalid = copy.deepcopy(report)
            invalid["entries"][0][field] = value
            invalids.append(invalid)
        invalid = copy.deepcopy(report)
        invalid["entries"][0]["source"]["start"] = False
        invalids.append(invalid)
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_formula_report(invalid)

    def test_legacy_evidence_retains_existing_shape(self):
        ir = document(DocumentIRBlock(id="p", type="paragraph", order=0, text="普通正文"))
        result = render(ir)
        legacy = build_renderer_evidence(ir, result.content)
        current = build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        self.assertNotIn("formula_report", legacy)
        self.assertNotIn("formula_summary", legacy)
        self.assertEqual(current["formula_summary"]["formula_count"], 0)
        self.assertEqual({key: value for key, value in current.items() if not key.startswith("formula_")}, legacy)

    def test_shared_renderer_concurrent_calls_have_separate_reports(self):
        renderer = DocumentIRWordRenderer()
        sources = [document(DocumentIRBlock(id=f"f{index}", type="formula", order=0, latex=source)) for index, source in enumerate((r"\unknown{x}", r"\frac{3}{4}"))]
        def run(ir):
            result = renderer.render_to_result(ir, template_path=None, config_path=None, image_loader=lambda _: None)
            return build_renderer_evidence(ir, result.content, formula_report=result.formula_report)
        with ThreadPoolExecutor(max_workers=2) as pool:
            evidence = list(pool.map(run, sources))
        self.assertEqual([value["formula_summary"]["formula_count"] for value in evidence], [1, 1])
        self.assertEqual([value["formula_summary"]["fallback_count"] for value in evidence], [1, 0])
        self.assertEqual([value["formula_report"]["entries"][0]["source"]["block_id"] for value in evidence], ["f0", "f1"])


if __name__ == "__main__":
    unittest.main()
