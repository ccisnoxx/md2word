"""公式在真实抽取、编码请求和回填之间不得成为可改写正文。"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.conversion.docx_rules.mineru_content import coerce_text_list, join_text_fragments
from app.domains.translation.document_ir_translator import DocumentIRTranslationError, DocumentIRTranslationService
from app.domains.translation.models import TranslationProviderResult, TranslationTextItem
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata
from app.services.renderer import DocumentIRWordRenderer


class _RewriteVisibleMathProvider:
    """主动改写遇到的数学文字，同时正常翻译上下文；占位符原样返回。"""

    def __init__(self) -> None:
        self.requests = []

    def translate(self, request):
        self.requests.append(request)
        return TranslationProviderResult(items=tuple(
            TranslationTextItem(
                id=item.id,
                text=item.text.replace("High", "被篡改高").replace("Low", "被篡改低")
                .replace("Before", "前文").replace("After", "后文").replace("Body", "正文"),
            )
            for item in request.items
        ))


def _document(*, html: str | None = None, text: str | None = None) -> DocumentIR:
    return DocumentIR(
        schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(job_id="job", source_file_id="source", document_language="en"),
        blocks=[DocumentIRBlock(
            id="block_0001", type="table" if html is not None else "paragraph", order=0,
            html=html, text=text,
        )],
    )


class FormulaTranslationBoundaryTests(unittest.TestCase):
    def test_math_dom_is_not_sent_and_non_math_ids_keep_all_text_node_indices(self):
        html = r"<table><tr><td>Before<eq>\text{High <b>Low</b>}</eq>After</td><td>Body</td></tr></table>"
        document = _document(html=html)
        original = document.model_dump(mode="json")
        provider = _RewriteVisibleMathProvider()
        service = DocumentIRTranslationService(provider)

        targets, items = service.extract_translation_items(document)
        translated = service.translate(document, term_version=None)

        self.assertEqual([item.id for item in items], [
            "block_0001.html.0000", "block_0001.html.0004", "block_0001.html.0005",
        ])
        self.assertEqual([target.index for target in targets], [0, 4, 5])
        self.assertEqual([item.text for item in provider.requests[0].items], ["Before", "After", "Body"])
        source_eq = BeautifulSoup(html, "html.parser").eq
        result = BeautifulSoup(translated.blocks[0].html, "html.parser")
        self.assertEqual(result.eq.decode_contents(), source_eq.decode_contents())
        self.assertIn("前文", result.get_text())
        self.assertIn("后文", result.get_text())
        self.assertIn("正文", result.get_text())
        self.assertNotIn("被篡改", result.get_text())
        self.assertEqual(document.model_dump(mode="json"), original)

    def test_existing_codec_delimiters_protect_math_from_active_rewrite(self):
        formulas = (r"$\text{High Low}$", r"$$\text{High Low}$$", r"\(\text{High Low}\)", r"\[\text{High Low}\]")
        for formula in formulas:
            for in_table in (False, True):
                with self.subTest(formula=formula, in_table=in_table):
                    text = f"Before {formula} After"
                    document = _document(html=f"<table><tr><td>{text}</td></tr></table>") if in_table else _document(text=text)
                    provider = _RewriteVisibleMathProvider()
                    translated = DocumentIRTranslationService(provider).translate(document, term_version=None)
                    output = BeautifulSoup(translated.blocks[0].html, "html.parser").get_text() if in_table else translated.blocks[0].text
                    self.assertEqual(output, f"前文 {formula} 后文")
                    self.assertEqual(len(provider.requests), 1)
                    self.assertNotIn("High", provider.requests[0].items[0].text)
                    self.assertNotIn("Low", provider.requests[0].items[0].text)

    def test_cross_node_math_fails_before_provider_audit_or_partial_apply(self):
        fragments = (
            r"$\text{High <b>Low</b>}$",
            r"\(<i>x</i>+1\)",
            r"\fr<b>ac</b>{1}{2}",
            "x<sup>2</sup>",
            "V<sub>OUT</sub>",
            "V<sub><b>High</b></sub>",
            "x<sup><i>2</i></sup>",
        )
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                document = _document(html=f"<table><tr><td>Before {fragment} After</td></tr></table>")
                original = document.model_dump(mode="json")
                provider = _RewriteVisibleMathProvider()
                service = DocumentIRTranslationService(provider)
                recorder = Mock()
                with patch.object(service, "apply_replacements") as apply:
                    with self.assertRaises(DocumentIRTranslationError) as caught:
                        service.translate(document, term_version=None, call_recorder=recorder)
                error = caught.exception
                self.assertEqual(error.code, "translation_formula_boundary_unprotected")
                self.assertEqual(str(error), "公式翻译保护边界无法完整闭合，已停止翻译。")
                self.assertIsNone(error.evidence)
                self.assertEqual(error.formula_protection, {
                    "code": error.code, "formula_count": 1, "unprotected_count": 1,
                })
                self.assertEqual(provider.requests, [])
                recorder.record_success.assert_not_called()
                recorder.record_failure.assert_not_called()
                apply.assert_not_called()
                self.assertEqual(document.model_dump(mode="json"), original)

    def test_bare_math_guard_applies_to_plan_and_direct_request_preparation(self):
        for text in (r"Before \frac{High}{Low} After", "Before x^2 After", "Before V_{OUT} After", r"Before R_{\theta JA} After", r"Before x_{\text{A B}} After"):
            with self.subTest(text=text):
                document = _document(text=text)
                service = DocumentIRTranslationService(_RewriteVisibleMathProvider())
                with self.assertRaises(DocumentIRTranslationError) as planned:
                    service.build_translation_plan(document, max_pages_per_batch=1, max_chars_per_batch=8000, batch_id_prefix="batch")
                with self.assertRaises(DocumentIRTranslationError) as prepared:
                    service.build_provider_request(
                        document, [TranslationTextItem(id="manual", text=text)],
                        term_version=None, language_pair="en2zh", batch_id="batch",
                    )
                self.assertEqual(planned.exception.code, "translation_formula_boundary_unprotected")
                self.assertEqual(prepared.exception.formula_protection, planned.exception.formula_protection)
                self.assertEqual(service.provider.requests, [])

    def test_unclosed_script_markup_is_rejected_before_provider_in_both_inputs(self):
        for text in ("Before V<sub><b>High", "Before x<sup><i>2", "Before V<sub>High</sup>",
                     "Before V<sub>$OUT$</sub>", r"Before V<sub>\(OUT\)</sub>", "Before V<sub><eq>OUT</eq></sub>",
                     r"Before V<sub>\frac{a}{b}</sub>", "Before V<sub>x^2</sub>"):
            for in_table in (False, True):
                with self.subTest(text=text, in_table=in_table):
                    document = _document(html=f"<table><tr><td>{text}</td></tr></table>") if in_table else _document(text=text)
                    provider = _RewriteVisibleMathProvider()
                    with self.assertRaises(DocumentIRTranslationError) as caught:
                        DocumentIRTranslationService(provider).translate(document, term_version=None)
                    self.assertEqual(caught.exception.code, "translation_formula_boundary_unprotected")
                    self.assertEqual(provider.requests, [])

    def test_non_math_paths_currency_and_identifiers_remain_translatable(self):
        text = r"Before \\server\share C:\manual\input.txt value_name costs $12 and \$20 After"
        provider = _RewriteVisibleMathProvider()
        translated = DocumentIRTranslationService(provider).translate(_document(text=text), term_version=None)
        self.assertEqual(translated.blocks[0].text, text.replace("Before", "前文").replace("After", "后文"))
        self.assertEqual(len(provider.requests), 1)

    def test_semantic_rich_fragments_preserve_raw_formula_and_annotation_boundaries(self):
        formula = r"  \text{High  Low} + x^2  "
        nodes = [
            {"type": "text", "content": "Before "},
            {"type": "equation_inline", "content": formula},
            {"type": "text", "content": " After"},
        ]
        self.assertEqual(join_text_fragments(nodes), f"Before ${formula}$ After")
        self.assertEqual(coerce_text_list(nodes), ["Before", f"${formula}$", "After"])

    def test_mineru_to_translation_to_docx_keeps_math_and_raw_table_html(self):
        formula = r"\text{High  Low}"
        html = rf"<table><tr><td>Before<eq>{formula}</eq>After</td><td rowspan='2'>Body</td></tr><tr><td>Body</td></tr></table>"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mineru.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content_list_v2.json", json.dumps([
                    {"type": "paragraph", "content": {"paragraph_content": [
                        {"type": "text", "content": "Before "},
                        {"type": "equation_inline", "content": formula},
                        {"type": "text", "content": " After"},
                    ]}, "page_idx": 0},
                    {"type": "table", "table_body": html, "page_idx": 0,
                     "table_caption": [{"type": "text", "content": "Table 1 Body "}, {"type": "equation_inline", "content": formula}],
                     "table_footnote": [{"type": "text", "content": "Note: "}, {"type": "equation_inline", "content": formula}]},
                ]))
            document = MinerUToDocumentIRService().convert_zip(
                path, job_id="job", source_file_id="source", document_language="en",
            ).document
        table = next(block for block in document.blocks if block.type == "table")
        self.assertEqual(table.html, html)
        self.assertTrue(any(f"${formula}$" in caption for caption in table.captions))
        self.assertEqual(table.footnotes, [f"Note: ${formula}$"])
        provider = _RewriteVisibleMathProvider()
        translated = DocumentIRTranslationService(provider).translate(document, term_version=None)
        content = DocumentIRWordRenderer().render_to_bytes(translated, template_path=None, config_path=None, image_loader=lambda _asset: None)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        math_texts = [node.text for node in root.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}t")]
        self.assertIn("High  Low", math_texts)
        self.assertIn("前文", "".join(root.itertext()))
        self.assertNotIn("被篡改", "".join(root.itertext()))
        self.assertEqual(len(list(root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"))), 1)

    def test_local_fake_preflight_shares_guard_and_direct_has_zero_provider_calls(self):
        from scripts.dev.formal_mineru_conversion import FormalMinerUConversionRequest, _translate_if_needed

        document = _document(html=r"<table><tr><td>Before $x<b>+1</b>$ After</td></tr></table>")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = FormalMinerUConversionRequest(input_path=root / "source.zip", output_path=root / "result.docx", translation_mode="en2zh")
            with patch("scripts.dev.formal_mineru_conversion._build_openai_provider") as build_provider:
                with self.assertRaises(DocumentIRTranslationError):
                    _translate_if_needed(document, request)
                build_provider.assert_not_called()
            direct = FormalMinerUConversionRequest(input_path=root / "source.zip", output_path=root / "result.docx", translation_mode="direct")
            with patch.object(DocumentIRTranslationService, "build_translation_plan") as plan:
                self.assertIs(_translate_if_needed(document, direct), document)
                plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
