"""公式子集扩展后的历史降级认证与已登记 OMML 残留扫描回归。"""

from __future__ import annotations

import copy
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from dataclasses import replace
from unittest.mock import patch
from xml.etree import ElementTree as ET

from docx import Document

from app.conversion.docx_rules.formula import (
    FORMULA_FALLBACK_NOTICE,
    FormulaParseError,
    _OmmlParser,
    formula_block_span,
    output_sha256,
    render_formula,
)
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata
from app.services.renderer.docx_quality import analyze_docx_quality_bytes, build_docx_quality_flags
from app.services.renderer.render_evidence import (
    build_renderer_evidence, formula_source_inventory, validate_persisted_renderer_content,
)
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.renderer.content_contract import build_formula_source_coverage
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.logical_table_plan import build_content_table_plan
from app.services.renderer.table_renderer import prepare_table_input
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.renderer.word_renderer import DocumentIRWordRenderer, _RenderContext


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def document(*blocks: DocumentIRBlock) -> DocumentIR:
    return DocumentIR(metadata=DocumentIRMetadata(job_id="formula_history", source_file_id="formula_source",
        document_language="zh"), blocks=list(blocks))


def render(ir: DocumentIR):
    return DocumentIRWordRenderer().render_to_result(ir, template_path=None, config_path=None,
        image_loader=lambda _: None)


def render_before_literal_support(ir: DocumentIR):
    """只在造历史夹具期间恢复旧 parser，读取验证使用当前正式实现。"""
    parse_command = _OmmlParser._parse_command

    def old_command(parser):
        if parser.source[parser.position:parser.position + 2] in {r"\_", r"\%"}:
            raise FormulaParseError("invalid_syntax")
        return parse_command(parser)

    with patch.object(_OmmlParser, "_parse_command", old_command):
        return render(ir)


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


def xml_of(content: bytes):
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        return ET.fromstring(package.read("word/document.xml"))


class FormulaRenderingCompatibilityTests(unittest.TestCase):
    def test_legacy_expanded_table_keeps_repeated_formula_occurrences_and_binding(self):
        block = DocumentIRBlock(id="large", type="table", order=0,
            html='<table><tr><td rowspan="2" colspan="2"><b>V<sub>OUT</sub></b> $x^2$</td><td>'
                + "a" * 30001 + '</td></tr><tr><td>tail</td></tr></table>')
        ir = document(block)
        word = Document()
        sources = formula_source_inventory(ir)
        context = _RenderContext(caption_bookmarks={}, formula_sources=sources)
        word.part._md2word_formula_context = context
        config = TemplateConfigPackage()
        model, strategy = prepare_table_input(block, config)
        self.assertEqual(strategy, "expanded")
        renderer = DocumentIRWordRenderer()
        # 历史 writer 与旧库存共同造夹具；当前正式生成仍独立验证 native 合并语义。
        renderer._render_expanded_table(word, model, model.max_columns,
            renderer._available_table_width(word), config, block_id=block.id)
        output = io.BytesIO()
        word.save(output)
        content = output.getvalue()
        report = {"schema_version": "formula-render/v1", "entries": context.formula_entries}
        evidence = build_renderer_evidence(ir, content, formula_report=report)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["formula_count"], 4)
        self.assertEqual(evidence["formula_summary"]["omml_count"], 2)
        self.assertEqual(evidence["formula_summary"]["semantic_count"], 2)
        self.assertEqual([entry["source"] for entry in report["entries"]], sources)
        self.assertEqual(len({entry["anchor"] for entry in report["entries"]}), 4)
        root = xml_of(content)
        self.assertEqual([len(row.findall("w:tc", NS)) for row in root.findall(".//w:tr", NS)], [3, 3])
        self.assertEqual(len(root.findall(".//m:sSup", NS)), 2)
        visible = "".join(node.text or "" for node in root.iter()
            if node.tag in {f"{{{NS['w']}}}t", f"{{{NS['m']}}}t"})
        self.assertEqual(visible.count("VOUT"), 2)
        self.assertEqual(visible.count("a" * 30001), 1)
        self.assertEqual(visible.count("tail"), 1)
        self.assertTrue(any(node.text == "OUT" and run.find("w:rPr/w:b", NS) is not None
            for run in root.findall(".//w:r", NS) for node in run.findall("w:t", NS)))

        def corrupt_repeated_formula(root):
            root.findall(".//m:sSup/m:sup//m:t", NS)[1].text = "3"

        with self.assertRaisesRegex(ValueError, "预期绑定"):
            build_renderer_evidence(ir, changed_docx(content, corrupt_repeated_formula), formula_report=report)

    def test_unreadable_legacy_docx_keeps_quality_unavailable_without_version_marker(self):
        evidence = build_renderer_evidence(document(), b"not-a-docx")
        self.assertEqual(evidence["docx_quality"], {})
        self.assertEqual(evidence["quality_flags"], ["docx_quality_unavailable"])
        self.assertEqual(evidence["blocking_quality_flags"], [])

    def test_omml_uses_effective_body_caption_and_compact_table_font_size(self):
        ir = document(DocumentIRBlock(id="formula", type="formula", order=0, latex=r"\frac{x_1}{y^2}"),
            DocumentIRBlock(id="inline", type="paragraph", order=1, text=r"正文 $x^2$"),
            DocumentIRBlock(id="table", type="table", order=2,
                html=r"<table><tr><td>$I_{OUT}=0,V_{FB}=V_{REF}\times105\%$</td>"
                     + "<td>1</td>" * 6 + "</tr></table>", captions=[r"Table 1: 条件 $x^2$"]))
        for explicit_size in (True, False):
            with self.subTest(explicit_size=explicit_size), tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "layout.yaml"
                sizes = ("10.5", "9", "8.5") if explicit_size else ("null", "null", "null")
                config.write_text(f"schema_version: template-config/v1\nnormal:\n  font_size: {sizes[0]}\n"
                    f"table_content:\n  font_size: {sizes[1]}\n"
                    f"  min_font_size: {'7.5' if explicit_size else 'null'}\n"
                    f"caption:\n  font_size: {sizes[2]}\n", encoding="utf-8")
                result = DocumentIRWordRenderer().render_to_result(ir, template_path=None,
                    config_path=config, image_loader=lambda _: None)
                math = xml_of(result.content).findall(".//m:oMath", NS)
                self.assertEqual(len(math), 4)
                for equation, expected in zip(math, ("21", "21", "17", "16"), strict=True):
                    for run in equation.findall(".//m:r", NS):
                        properties = run.findall("w:rPr", NS)
                        self.assertEqual(len(properties), int(explicit_size))
                        if explicit_size:
                            for tag in ("w:sz", "w:szCs"):
                                self.assertEqual(properties[0].find(tag, NS).get(f"{{{NS['w']}}}val"), expected)
                            self.assertLess(list(run).index(properties[0]),
                                list(run).index(run.find("m:t", NS)))
                evidence = build_renderer_evidence(ir, result.content, render_result=result)
                ensure_renderer_integrity(evidence)
                self.assertEqual(evidence["formula_summary"]["fallback_count"], 0)

    def old_table(self):
        ir = document(DocumentIRBlock(id="table", type="table", order=0,
            html=r"<table><tr><td>前 <b>V<sub>OUT</sub></b> Table 1: $105\%$ 中 $V\_MAX$ 后 $x^2$</td></tr></table>",
            captions=[r"Table 1: 上限 $V\_MAX$ 与 $105\%$"],
            footnotes=[r"注：下限 $V\_MIN$，比例 $105\%$，重复 $105\%$"]))
        return ir, render_before_literal_support(ir)

    def restored_evidence(self, ir, old, content, report):
        """重建外围身份，确保负例由叶内容或来源绑定拒绝，而非旧文件整体 hash。"""
        tables = build_content_table_plan(ir, build_layout_plan(ir))
        coverage = build_formula_source_coverage(ir, content, tables, report)
        return build_renderer_evidence(ir, content, formula_report=report,
            image_layout_report=old.image_layout_report,
            renderer_content_contract_version=old.renderer_content_contract_version,
            formula_source_coverage=coverage)

    def test_old_table_caption_and_note_keep_authenticated_fallback_after_parser_upgrade(self):
        ir, old = self.old_table()
        for source in (r"105\%", r"V\_MAX", r"V\_MIN"):
            self.assertEqual(render_formula(formula_block_span(source)).mode, "omml")
        self.assertEqual(sum(entry["mode"] == "text_fallback" for entry in old.formula_report["entries"]), 7)
        self.assertEqual({entry["source"]["field"] for entry in old.formula_report["entries"]},
            {"html/0/0", "captions/0", "footnotes/0"})
        evidence = build_renderer_evidence(ir, old.content, render_result=old)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["formula_summary"]["fallback_count"], 7)
        self.assertEqual(evidence["docx_quality"]["latex_residue_count"], 0)
        self.assertIn("formula_text_fallback", evidence["quality_flags"])
        ensure_renderer_integrity(self.restored_evidence(ir, old, old.content, old.formula_report))

    def test_old_fallback_rejects_missing_notice_changed_value_and_removed_formula(self):
        ir, old = self.old_table()

        def remove_notice(root):
            next(node for node in root.findall(".//w:t", NS) if node.text == FORMULA_FALLBACK_NOTICE).text = ""

        def change_value(root):
            next(node for node in root.findall(".//w:t", NS) if node.text == r"$105\%$").text = r"$106\%$"

        def remove_formula(root):
            paragraph = next(node for node in root.findall(".//w:p", NS)
                if any(child.tag == f"{{{NS['w']}}}bookmarkStart" and child.get(f"{{{NS['w']}}}name", "").startswith("md2w_formula_")
                       for child in node))
            children = list(paragraph)
            start = next(i for i, child in enumerate(children) if child.tag == f"{{{NS['w']}}}bookmarkStart"
                and child.get(f"{{{NS['w']}}}name", "").startswith("md2w_formula_"))
            bookmark_id = children[start].get(f"{{{NS['w']}}}id")
            end = next(i for i in range(start + 1, len(children)) if children[i].tag == f"{{{NS['w']}}}bookmarkEnd"
                and children[i].get(f"{{{NS['w']}}}id") == bookmark_id)
            for child in children[start:end + 1]:
                paragraph.remove(child)

        for change in (remove_notice, change_value, remove_formula):
            with self.subTest(change=change.__name__):
                content = changed_docx(old.content, change)
                with self.assertRaises(ValueError):
                    analyze_docx_quality_bytes(content, formula_report=old.formula_report)
                with self.assertRaises(DocumentIntegrityError):
                    build_renderer_evidence(ir, content, render_result=old)

    def test_old_report_rejects_mode_source_and_occurrence_misalignment(self):
        ir, old = self.old_table()
        mode = copy.deepcopy(old.formula_report)
        mode["entries"][0].update(mode="omml", reason=None)
        source = copy.deepcopy(old.formula_report)
        source["entries"][0]["source"]["field"] = "footnotes/0"
        order = copy.deepcopy(old.formula_report)
        order["entries"][0], order["entries"][1] = order["entries"][1], order["entries"][0]
        for report in (mode, source, order):
            with self.subTest(report=report), self.assertRaises(DocumentIntegrityError):
                build_renderer_evidence(ir, old.content, render_result=replace(old, formula_report=report))

    def test_old_fallback_does_not_exempt_cell_text_and_ref_fields(self):
        ir, old = self.old_table()

        def change_text(root):
            cell = root.find(".//w:tc", NS)
            next(node for node in cell.findall(".//w:t", NS) if node.text == "前 ").text = "改 "

        def change_reference(root):
            cell = root.find(".//w:tc", NS)
            next(node for node in cell.findall(".//w:instrText", NS) if " REF " in node.text).text = " PAGE "

        for change in (change_text, change_reference):
            with self.subTest(change=change.__name__):
                content = changed_docx(old.content, change)
                self.assertEqual(analyze_docx_quality_bytes(content,
                    formula_report=old.formula_report)["latex_residue_count"], 0)
                with self.assertRaisesRegex(DocumentIntegrityError, "target_mismatch"):
                    self.restored_evidence(ir, old, content, old.formula_report)

    def test_old_fallback_still_requires_notice_and_exact_source_with_refreshed_output_hash(self):
        ir = document(DocumentIRBlock(id="table", type="table", order=0,
            html=r"<table><tr><td>$105\%$</td></tr></table>"))
        old = render_before_literal_support(ir)
        for before, after in ((FORMULA_FALLBACK_NOTICE, ""), (r"$105\%$", r"$106\%$")):
            def change(root):
                next(node for node in root.findall(".//w:t", NS) if node.text == before).text = after

            with self.subTest(before=before):
                content = changed_docx(old.content, change)
                paragraph = xml_of(content).find(".//w:tc/w:p", NS)
                children = list(paragraph)
                start = next(i for i, node in enumerate(children) if node.tag == f"{{{NS['w']}}}bookmarkStart"
                    and node.get(f"{{{NS['w']}}}name") == old.formula_report["entries"][0]["anchor"])
                bookmark_id = children[start].get(f"{{{NS['w']}}}id")
                end = next(i for i in range(start + 1, len(children)) if children[i].tag == f"{{{NS['w']}}}bookmarkEnd"
                    and children[i].get(f"{{{NS['w']}}}id") == bookmark_id)
                report = copy.deepcopy(old.formula_report)
                report["entries"][0]["expected_output_sha256"] = output_sha256(children[start + 1:end])
                self.assertEqual(analyze_docx_quality_bytes(content, formula_report=report)["latex_residue_count"], 0)
                with self.assertRaisesRegex(DocumentIntegrityError, "target_mismatch"):
                    self.restored_evidence(ir, old, content, report)

    def test_old_identical_formulas_cannot_swap_sources_or_order_with_refreshed_coverage(self):
        ir, old = self.old_table()
        originals = old.formula_report["entries"]
        caption = next(i for i, entry in enumerate(originals)
            if entry["source"]["field"] == "captions/0" and entry["source"]["source_sha256"] == originals[-1]["source"]["source_sha256"])
        cell = next(i for i, entry in enumerate(originals)
            if entry["source"]["field"] == "html/0/0" and entry["source"]["source_sha256"] == originals[-1]["source"]["source_sha256"])
        for left, right in ((caption, cell), (len(originals) - 2, len(originals) - 1)):
            report = copy.deepcopy(old.formula_report)
            entries = report["entries"]
            entries[left]["source"], entries[right]["source"] = entries[right]["source"], entries[left]["source"]
            with self.subTest(pair=(left, right)):
                analyze_docx_quality_bytes(old.content, formula_report=report)
                with self.assertRaisesRegex(DocumentIntegrityError, "target_mismatch"):
                    self.restored_evidence(ir, old, old.content, report)

    def test_authenticated_omml_literals_are_not_latex_residue_at_three_entries(self):
        expression = r"V\_MAX+V\_MIN+V\_RMS"
        ir = document(DocumentIRBlock(id="formula", type="formula", order=0, latex=expression),
            DocumentIRBlock(id="inline", type="paragraph", order=1, text="前 $" + expression + "$ 后"),
            DocumentIRBlock(id="table", type="table", order=2,
                html="<table><tr><td>$" + expression + "$</td></tr></table>"))
        result = render(ir)
        self.assertEqual([entry["mode"] for entry in result.formula_report["entries"]], ["omml"] * 3)
        quality = analyze_docx_quality_bytes(result.content, formula_report=result.formula_report)
        self.assertEqual(quality["latex_residue_count"], 0)
        self.assertGreater(analyze_docx_quality_bytes(result.content)["latex_residue_count"], 0)
        evidence = build_renderer_evidence(ir, result.content, render_result=result)
        ensure_renderer_integrity(evidence)
        self.assertFalse(any(flag.startswith("docx_latex_residue:") for flag in evidence["quality_flags"]))

    def test_omml_exemption_keeps_unregistered_body_residue_visible(self):
        result = render(document(DocumentIRBlock(id="formula", type="formula", order=0, latex=r"V\_MAX")))

        def add_residue(root):
            paragraph = ET.Element(f"{{{NS['w']}}}p")
            run = ET.SubElement(paragraph, f"{{{NS['w']}}}r")
            ET.SubElement(run, f"{{{NS['w']}}}t").text = r"普通正文遗留 \frac{1}{2} 与 _RMS"
            root.find("w:body", NS).insert(0, paragraph)

        quality = analyze_docx_quality_bytes(changed_docx(result.content, add_residue),
            formula_report=result.formula_report)
        self.assertEqual(quality["latex_residue_count"], 2)
        self.assertIn(r"\frac", quality["latex_residue_examples"])
        self.assertIn("_RMS", quality["latex_residue_examples"])

    def test_source_literal_identifiers_keep_text_and_require_formal_source_authentication(self):
        text = "供电节点 4V_VDD，技术标识符 V_MAX 与 file_name 保持字面文本。"
        ir = document(DocumentIRBlock(id="literal", type="paragraph", order=0, text=text))
        result = render(ir)
        self.assertEqual(result.formula_report["entries"], [])
        self.assertEqual("".join(node.text or "" for node in xml_of(result.content).findall(".//w:t", NS)), text)
        self.assertEqual(xml_of(result.content).findall(".//m:oMath", NS), [])
        quality = build_renderer_evidence(ir, result.content, render_result=result)["docx_quality"]
        self.assertEqual(quality["analysis_version"], "docx-quality/v2")
        self.assertEqual(quality["latex_residue_count"], 0)
        # 仅有格式合法的空报告不能宣称正文已获源认证；无报告旧扫描也不改变。
        for report in (None, {"schema_version": "formula-render/v1", "entries": []}):
            with self.subTest(report=report):
                self.assertGreater(analyze_docx_quality_bytes(result.content, formula_report=report)["latex_residue_count"], 0)

        def add_unregistered_identifier(root):
            paragraph = ET.SubElement(root.find("w:body", NS), f"{{{NS['w']}}}p")
            run = ET.SubElement(paragraph, f"{{{NS['w']}}}r")
            ET.SubElement(run, f"{{{NS['w']}}}t").text = "源中没有的 unknown_token"

        changed = changed_docx(result.content, add_unregistered_identifier)
        aggregate = build_renderer_evidence(ir, changed, formula_report=result.formula_report,
            image_layout_report=result.image_layout_report)
        self.assertEqual(aggregate["docx_quality"]["latex_residue_examples"], ["_token"])
        with self.assertRaises(DocumentIntegrityError):
            build_renderer_evidence(ir, changed, render_result=replace(result, content=changed))

    def test_identifier_exemption_keeps_explicit_script_and_tex_residue(self):
        ir = document(DocumentIRBlock(id="literal", type="paragraph", order=0,
            text="源节点 4V_VDD 与 V_MAX 保持可见。"))
        result = render(ir)

        def add_residue(root):
            paragraph = ET.SubElement(root.find("w:body", NS), f"{{{NS['w']}}}p")
            run = ET.SubElement(paragraph, f"{{{NS['w']}}}r")
            ET.SubElement(run, f"{{{NS['w']}}}t").text = r"残留 _RMS、V_{OUT}、x^2、\frac{1}{2}、$V_MAX$"

        quality = build_renderer_evidence(ir, changed_docx(result.content, add_residue),
            formula_report=result.formula_report, image_layout_report=result.image_layout_report)["docx_quality"]
        self.assertEqual(quality["latex_residue_count"], 5)
        self.assertEqual(quality["latex_residue_examples"], ["_RMS", "_{OUT}", "^2", r"\frac", "$V_MAX$"])

    def test_legacy_quality_is_recomputed_and_compared_without_relaxing_v2_recovery(self):
        ir = document(DocumentIRBlock(id="literal", type="paragraph", order=0,
            text="供电节点 4V_VDD 保持原文，普通技术说明继续作为可编辑的正文呈现。"))
        result = render(ir)
        for formal in (False, True):
            with self.subTest(formal=formal):
                current = (build_renderer_evidence(ir, result.content, render_result=result) if formal else
                    build_renderer_evidence(ir, result.content, formula_report=result.formula_report))
                legacy = copy.deepcopy(current)
                legacy["docx_quality"] = analyze_docx_quality_bytes(result.content, formula_report=result.formula_report)
                legacy["quality_flags"] = build_docx_quality_flags(legacy["docx_quality"])
                self.assertEqual(legacy["docx_quality"]["latex_residue_examples"], ["_VDD"])
                restored = validate_persisted_renderer_content(ir, result.content, legacy)
                self.assertEqual(restored["docx_quality"], legacy["docx_quality"])
                self.assertEqual(restored["quality_flags"], ["docx_latex_residue:1"])
                self.assertEqual(validate_persisted_renderer_content(ir, result.content, current)["docx_quality"],
                    current["docx_quality"])
                for quality in ({**legacy["docx_quality"], "latex_residue_count": 0},
                                {**current["docx_quality"], "analysis_version": "docx-quality/v999"}):
                    bad = copy.deepcopy(legacy)
                    bad["docx_quality"] = quality
                    with self.subTest(quality=quality), self.assertRaises(DocumentIntegrityError if formal else ValueError):
                        validate_persisted_renderer_content(ir, result.content, bad)

    def test_omml_exemption_rejects_changed_hash_and_anchor(self):
        result = render(document(DocumentIRBlock(id="formula", type="formula", order=0, latex=r"V\_MAX")))
        report = copy.deepcopy(result.formula_report)
        report["entries"][0]["expected_output_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "预期绑定"):
            analyze_docx_quality_bytes(result.content, formula_report=report)

        anchor_name = report["entries"][0]["anchor"]

        def change_anchor(root):
            root.find(f".//w:bookmarkStart[@w:name='{anchor_name}']", NS).set(
                f"{{{NS['w']}}}name", "md2w_formula_999999")

        with self.assertRaisesRegex(ValueError, "锚点"):
            analyze_docx_quality_bytes(changed_docx(result.content, change_anchor), formula_report=result.formula_report)


if __name__ == "__main__":
    unittest.main()
