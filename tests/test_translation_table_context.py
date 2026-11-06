"""B06 只读上下文的输入、Token、预算与既有来源合同；不评价真实翻译语义。"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.core.config import Settings
from app.domains.translation.document_ir_translator import DocumentIRTranslationError, DocumentIRTranslationService
from app.domains.translation.integrity import INTEGRITY_INSTRUCTION, TranslationIntegrityError
from app.domains.translation.models import TranslationPromptSnapshot, TranslationProviderResult, TranslationTextItem
from app.domains.translation.provider import OpenAICompatibleTranslationProvider, TranslationProviderResponseError
from app.domains.translation.table_context import MAX_TABLE_CONTEXT_CHARS, context_char_count
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata


class EchoProvider:
    def __init__(self):
        self.requests = []

    def translate(self, request):
        self.requests.append(request)
        return TranslationProviderResult(request.items)


def document(html):
    return DocumentIR(
        schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(job_id="job", source_file_id="source", document_language="en"),
        blocks=[DocumentIRBlock(id="table", type="table", order=0, html=html, page_index=0)],
    )


def prompt_snapshot():
    markdown = "Translate naturally."
    return TranslationPromptSnapshot(
        id="prompt", name="固定测试", markdown=markdown,
        content_hash="sha256:" + hashlib.sha256(markdown.encode()).hexdigest(), built_in=False,
    )


class TableContextTests(unittest.TestCase):
    def setUp(self):
        self.provider = EchoProvider()
        self.service = DocumentIRTranslationService(self.provider, table_context_enabled=True)
        self.serializer = OpenAICompatibleTranslationProvider(Settings(_env_file=None))

    def prepare(self, doc, *, service=None, items=None, **kwargs):
        service = service or self.service
        if items is None:
            _, items = service.extract_translation_items(doc)
        return service.build_provider_request(
            doc, items, term_version=None, language_pair="en2zh", prompt=prompt_snapshot(),
            batch_id="batch", attempt=2, split_level=1, parent_batch_id="root", page_start=1, page_end=1,
            **kwargs,
        )

    def test_default_off_matches_prechange_user_and_system_bytes(self):
        doc = document("<table><tr><td>Typical</td></tr></table>")
        service = DocumentIRTranslationService(self.provider)
        with patch("app.domains.translation.document_ir_translator.TableContextBuilder", side_effect=AssertionError("关闭时不得构建上下文")):
            request = self.prepare(doc, service=service).request
        expected_user = '''{
  "language_pair": "en2zh",
  "glossary": [],
  "items": [
    {
      "id": "table.html.0000",
      "text": "Typical"
    }
  ]
}'''
        expected_system = (
            "Translate naturally.\n\nLanguage pair: en2zh; source=en; target=zh. "
            "Return only JSON with an items array. Preserve every item id exactly.\n\n"
            + INTEGRITY_INSTRUCTION
        )
        self.assertEqual(self.serializer._user_prompt(request).encode(), expected_user.encode())
        self.assertEqual(self.serializer._system_prompt(request).encode(), expected_system.encode())
        self.assertEqual(request.table_contexts, ())
        self.assertFalse(Settings(_env_file=None).translation_table_context_enabled)

    def test_merged_multilevel_headers_rowspan_parameters_eq_and_source_are_preserved(self):
        html = (
            '<table><thead><tr><th rowspan="2">Parameter</th><th colspan="2">Limits</th></tr>'
            '<tr><th>Low</th><th>High</th></tr></thead><tbody>'
            '<tr><td rowspan="2">Voltage 5 V</td><td>Typical</td><td>Before<eq>secret <b>eq</b> 99</eq>After</td></tr>'
            '<tr><td>Reserved</td><td>Other</td></tr></tbody></table>'
        )
        doc = document(html)
        before = doc.model_dump(mode="json")
        enabled = self.prepare(doc)
        disabled = self.prepare(doc, service=DocumentIRTranslationService(self.provider))
        self.assertEqual(enabled.source_items, disabled.source_items)
        self.assertEqual(enabled.encoded_batch, disabled.encoded_batch)
        self.assertEqual(replace(enabled.request, table_contexts=()), disabled.request)
        contexts = {context.item_id: context for context in enabled.request.table_contexts}
        typical = contexts["table.html.0005"]
        self.assertEqual((typical.row, typical.column, typical.rowspan, typical.colspan), (2, 1, 1, 1))
        self.assertEqual(typical.header_path, ("Limits", "Low"))
        self.assertTrue(typical.row_parameters[0].startswith("Voltage {{MD2W_PT_v1_"))
        self.assertEqual(contexts["table.html.0011"].header_path, ("Limits", "Low"))
        self.assertTrue(contexts["table.html.0011"].row_parameters[0].startswith("Voltage "))
        self.assertEqual((contexts["table.html.0000"].rowspan, contexts["table.html.0001"].colspan), (2, 2))
        ids = [item.id for item in enabled.request.items]
        self.assertNotIn("table.html.0007", ids)
        self.assertNotIn("table.html.0008", ids)
        self.assertNotIn("table.html.0009", ids)
        self.assertIn("table.html.0010", ids)
        serialized = self.serializer._user_prompt(enabled.request)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("99", json.dumps([c.to_payload() for c in contexts.values()]))
        self.assertNotIn("5 V", serialized)
        for prepared in (enabled, disabled):
            result = TranslationProviderResult(prepared.request.items)
            checked = self.service.validator.validate(prepared.source_items, prepared.encoded_batch, result)
            if prepared is enabled:
                evidence = checked.evidence
            else:
                self.assertEqual(checked.evidence, evidence)
        translated = self.service.translate(doc, term_version=None)
        self.assertEqual(BeautifulSoup(translated.blocks[0].html, "html.parser").eq, BeautifulSoup(html, "html.parser").eq)
        self.assertEqual(doc.model_dump(mode="json"), before)
        self.assertEqual(asdict(enabled.request)["items"], asdict(disabled.request)["items"])
        with self.assertRaises(FrozenInstanceError):
            typical.row = 9
        self.assertNotIn("Voltage", repr(typical))

    def test_context_technical_fields_use_separate_namespace_and_cannot_be_returned(self):
        doc = document('<table><tr><th>Model OPA228 at 25°C</th></tr><tr><td>Typical</td></tr></table>')
        prepared = self.prepare(doc)
        context = prepared.request.table_contexts[-1]
        header = context.header_path[0]
        self.assertNotIn("OPA228", header)
        self.assertNotIn("25°C", header)
        tokens = re.findall(r"\{\{MD2W_PT_v1_\d+_\d+\}\}", header)
        self.assertEqual(len(tokens), 2)
        self.assertTrue(all(not token.startswith(prepared.encoded_batch.namespace) for token in tokens))
        returned = list(prepared.request.items)
        returned[-1] = replace(returned[-1], text=returned[-1].text + tokens[0])
        with self.assertRaises(TranslationIntegrityError) as caught:
            self.service.validator.validate(prepared.source_items, prepared.encoded_batch, TranslationProviderResult(tuple(returned)))
        self.assertEqual(caught.exception.code, "translation_integrity_placeholder_unknown")
        payload = {"items": [{"id": item.id, "text": item.text} for item in prepared.request.items]}
        payload["items"][-1]["context"] = context.to_payload()
        with self.assertRaises(TranslationProviderResponseError):
            self.serializer._parse_json_response(json.dumps(payload), finish_reason="stop", usage={}, response_id=None)
        self.assertIn("只读参考", self.serializer._system_prompt(prepared.request))
        self.assertEqual(prepared.request.prompt_content_hash, prompt_snapshot().content_hash)

    def test_missing_headers_and_non_cell_caption_keep_original_ids(self):
        doc = document('<table><caption>Caption</caption><tr><td>Typical</td><td>Other</td></tr></table>')
        prepared = self.prepare(doc)
        self.assertEqual([item.id for item in prepared.request.items], [f"table.html.{i:04d}" for i in range(3)])
        self.assertEqual([c.item_id for c in prepared.request.table_contexts], ["table.html.0001", "table.html.0002"])
        self.assertTrue(all(not c.header_path for c in prepared.request.table_contexts))
        disabled = self.prepare(doc, service=DocumentIRTranslationService(self.provider))
        self.assertEqual(prepared.source_items, disabled.source_items)
        with patch.object(self.provider, "translate", side_effect=lambda request: TranslationProviderResult(tuple(
            replace(item, text="标题" if item.text == "Caption" else item.text) for item in request.items
        ))):
            translated = self.service.translate(doc, term_version=None)
        self.assertEqual(BeautifulSoup(translated.blocks[0].html, "html.parser").caption.get_text(), "标题")

    def test_row_headers_are_not_inherited_as_column_headers(self):
        doc = document('<table><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr>'
                       '<tr><th scope="row">First</th><td>High</td></tr>'
                       '<tr><th scope="row">Second</th><td>Low</td></tr></table>')
        contexts = self.prepare(doc).request.table_contexts
        self.assertEqual(contexts[-2].header_path, ("Parameter",))
        self.assertEqual(contexts[-1].header_path, ("Value",))
        self.assertEqual(contexts[-1].row_parameters, ("Second",))
        self.assertNotIn("First", json.dumps(contexts[-2].to_payload()))

    def test_source_reserved_token_namespace_collision_stays_separate(self):
        doc = document('<table><tr><th>Header {{MD2W_PT_v1_0_1}} 5 V</th></tr><tr><td>Typical</td></tr></table>')
        prepared = self.prepare(doc)
        self.assertEqual(prepared.encoded_batch.namespace, "{{MD2W_PT_v1_1_")
        text = prepared.request.table_contexts[-1].header_path[0]
        self.assertNotIn(prepared.encoded_batch.namespace, text)
        self.assertNotIn("5 V", text)
        self.assertNotIn("{{MD2W_PT_v1_0_1}}", text)

    def test_context_preserves_explicit_line_boundaries_without_splitting_inline_words(self):
        for header in ("5 V<br>Typical", "<p>5 V</p><div>Typical</div>", "<ul><li>5 V</li><li>Typical</li></ul>"):
            with self.subTest(header=header):
                doc = document(f'<table><tr><th>{header}</th><th>Parameter</th></tr>'
                               '<tr><td>Output</td><td>25°C<br>Condition</td></tr></table>')
                prepared = self.prepare(doc)
                output = next(item for item in prepared.source_items if item.text == "Output")
                context = next(c for c in prepared.request.table_contexts if c.item_id == output.id)
                self.assertRegex(context.header_path[0], r"^\{\{MD2W_PT_v1_\d+_\d+\}\}\n+Typical$")
                self.assertRegex(context.row_parameters[0], r"^\{\{MD2W_PT_v1_\d+_\d+\}\}\nCondition$")
        doc = document('<table><tr><th><b>OPA</b>228 Ty<i>pi</i>cal<eq>Secret<br>99</eq></th></tr>'
                       '<tr><td>Output</td></tr></table>')
        context = self.prepare(doc).request.table_contexts[-1]
        self.assertRegex(context.header_path[0], r"^\{\{MD2W_PT_v1_\d+_\d+\}\} Typical$")
        self.assertNotIn("Secret", context.header_path[0])

    def test_scope_enumerations_are_case_insensitive(self):
        for row_scope in ("ROW", "RoWgRoUp"):
            with self.subTest(scope=row_scope):
                doc = document(f'<table><tr><th scope="{row_scope}">Row title</th><th>Value</th></tr>'
                               '<tr><td>Output</td><td>Typical</td></tr></table>')
                self.assertEqual(self.prepare(doc).request.table_contexts[-2].header_path, ())
        for column_scope in ("COL", "CoLgRoUp"):
            with self.subTest(scope=column_scope):
                doc = document(f'<table><tr><th scope="{column_scope}">Column title</th><td>Condition</td></tr>'
                               '<tr><td>Output</td><td>Typical</td></tr></table>')
                self.assertEqual(self.prepare(doc).request.table_contexts[-2].header_path, ("Column title",))

    def test_page_and_item_limits_keep_original_plan_contract(self):
        doc = document('<table><tr><td>First</td></tr></table>')
        doc.blocks.append(DocumentIRBlock(id="second", type="table", order=1, page_index=2,
                                         html='<table><tr><td>Second</td></tr></table>'))
        batches = self.service.build_translation_plan(doc, max_pages_per_batch=1, max_chars_per_batch=8000, batch_id_prefix="b")[2]
        self.assertEqual([(b.page_start, b.page_end, b.item_count) for b in batches], [(1, 1, 1), (3, 3, 1)])
        legacy = DocumentIRTranslationService(self.provider, max_items_per_request=1)
        self.assertEqual(len(self.prepare(doc, service=legacy).request.items), 2)

    def test_ambiguous_implicit_cell_closure_fails_before_call(self):
        for html in ('<table><tr><td>First<td>Second</table>', '<table><tr><td>First<tr><td>Second</table>'):
            with self.subTest(html=html), self.assertRaises(DocumentIRTranslationError) as caught:
                self.service.translate(document(html), term_version=None)
            self.assertEqual(caught.exception.code, "translation_table_context_unmapped")
        self.assertEqual(self.provider.requests, [])

    def test_context_cost_splits_deterministically_and_direct_build_checks_limits(self):
        doc = document('<table><tr><th>Header</th></tr><tr><td>Typical</td></tr><tr><td>Other</td></tr></table>')
        service = DocumentIRTranslationService(self.provider, table_context_enabled=True, max_chars_per_request=400)
        targets, items, batches = service.build_translation_plan(doc, max_pages_per_batch=1, max_chars_per_batch=400, batch_id_prefix="b")
        self.assertEqual([batch.item_count for batch in batches], [1, 1, 1])
        self.assertEqual(sum(b.char_count for b in batches), sum(len(i.text) for i in items))
        self.assertEqual((targets, items, batches), service.build_translation_plan(doc, max_pages_per_batch=1, max_chars_per_batch=400, batch_id_prefix="b"))
        by_id = {item.id: item for item in items}
        for batch in batches:
            prepared = self.prepare(doc, service=service, items=[by_id[i] for i in batch.item_ids])
            cost = sum(len(i.text) for i in prepared.request.items) + sum(context_char_count(c) for c in prepared.request.table_contexts)
            self.assertLessEqual(cost, 400)
        with self.assertRaises(TranslationIntegrityError) as caught:
            self.prepare(doc, service=service)
        self.assertEqual(caught.exception.code, "translation_request_budget_exceeded")
        item_limited = DocumentIRTranslationService(self.provider, table_context_enabled=True, max_items_per_request=1)
        self.assertEqual([b.item_count for b in item_limited.build_translation_plan(doc, max_pages_per_batch=1, max_chars_per_batch=8000, batch_id_prefix="b")[2]], [1, 1, 1])
        with self.assertRaises(TranslationIntegrityError):
            self.prepare(doc, service=item_limited)

    def test_minimum_context_or_body_over_budget_fails_before_provider(self):
        for text, limit in (("Typical", 20), ("Long body text", 4)):
            doc = document(f'<table><tr><td>{text}</td></tr></table>')
            service = DocumentIRTranslationService(self.provider, table_context_enabled=True, max_chars_per_request=limit)
            with self.assertRaises(DocumentIRTranslationError) as caught:
                service.translate(doc, term_version=None)
            self.assertEqual(caught.exception.code, "translation_request_budget_exceeded")
            self.assertEqual(caught.exception.evidence.stage, "budget")
            with self.assertRaises(TranslationIntegrityError):
                self.prepare(doc, service=service)
        self.assertEqual(self.provider.requests, [])

    def test_budget_selects_whole_headers_before_row_text_and_short_body_gets_more(self):
        header = "Header " + "context " * 12
        peer = "Parameter " + "details " * 12 + "5 V"
        doc = document(f'<table><tr><th>{header}</th><th>Other</th></tr><tr><td>Short</td><td>{peer}</td></tr></table>')
        items = self.service.extract_translation_items(doc)[1]
        short_item = items[2]
        baseline = self.prepare(doc, items=[short_item]).request.table_contexts[0]
        header_only = replace(baseline, row_parameters=(), truncated=True)
        limit = len(short_item.text) + context_char_count(header_only) + 2
        short = self.prepare(doc, items=[short_item], max_chars_per_request=limit).request.table_contexts[0]
        long_doc = document(doc.blocks[0].html.replace("Short", "Long body " * 8))
        long_item = self.service.extract_translation_items(long_doc)[1][2]
        long = self.prepare(long_doc, items=[long_item], max_chars_per_request=limit).request.table_contexts[0]
        self.assertEqual(short.header_path, (header.strip(),))
        self.assertEqual(short.row_parameters, ())
        self.assertTrue(short.truncated)
        self.assertEqual(long.header_path, ())
        self.assertTrue(long.truncated)
        self.assertLess(context_char_count(long), context_char_count(short))
        huge = document('<table><tr><th>' + "descriptive " * 200 + '</th></tr><tr><td>Short</td></tr></table>')
        prepared = self.prepare(huge, items=[self.service.extract_translation_items(huge)[1][-1]])
        self.assertTrue(prepared.request.table_contexts[0].truncated)
        self.assertLessEqual(context_char_count(prepared.request.table_contexts[0]), MAX_TABLE_CONTEXT_CHARS)

    def test_settings_environment_reaches_real_runtime_service(self):
        from app.main import build_runtime
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"TRANSLATION_TABLE_CONTEXT_ENABLED": "true"}):
            settings = Settings(_env_file=None, data_dir=directory, jobs_repository_backend="file", translation_provider_backend="disabled")
            runtime = build_runtime(settings)
            self.assertTrue(runtime.document_ir_translation_service.table_context_enabled)
            prepared = self.prepare(document('<table><tr><td>Typical</td></tr></table>'), service=runtime.document_ir_translation_service)
            self.assertEqual(len(prepared.request.table_contexts), 1)
            self.assertTrue(Path(directory).is_dir())


if __name__ == "__main__":
    unittest.main()
