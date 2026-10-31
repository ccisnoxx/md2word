from __future__ import annotations

# tests/test_document_ir_translation.py: 覆盖 P1 DocumentIR 翻译 provider、术语版本和结构不变性。

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile
from bs4 import BeautifulSoup

from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.domains.translation.models import (
    TermVersionSnapshot,
    TranslationPromptSnapshot,
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTermEntry,
    TranslationTextItem,
)
from app.domains.translation.document_ir_translator import DocumentIRTranslationService, DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.protected_tokens import encode
from app.domains.translation.term_version_service import TermVersionService


class FakeTranslationProvider:
    def __init__(self) -> None:
        self.requests: list[TranslationProviderRequest] = []

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        self.requests.append(request)
        translations = {
            "block_0001.text": "1 特性",
            "block_0002.text": "输入失调电压很低。",
            "block_0003.text": "电气特性",
            "block_0003.html.0000": "参数",
            "block_0003.html.0001": "输入电压",
            "block_0004.list_items.0000": "低噪声",
            "block_0004.list_items.0001": "高压摆率",
            "block_0006.text": "图 1. 引脚图",
        }
        return TranslationProviderResult(
            items=tuple(
                TranslationTextItem(
                    id=item.id,
                    text=(
                        item.text.replace("Features", "特性") if item.id == "block_0001.text" else
                        item.text.replace("Figure", "图").replace("Pin diagram", "引脚图") if item.id == "block_0006.text" else
                        translations[item.id]
                    ),
                )
                for item in request.items
            )
        )


class RecordingTranslationCallRecorder:
    def __init__(self) -> None:
        self.success_requests: list[TranslationProviderRequest] = []
        self.failure_requests: list[TranslationProviderRequest] = []

    def record_success(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult,
        *,
        duration_ms: int,
        integrity=None,
    ) -> None:
        self.success_requests.append(request)

    def record_failure(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        *,
        error: Exception,
        duration_ms: int,
        integrity=None,
    ) -> None:
        self.failure_requests.append(request)


class EchoSingleItemTranslationProvider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[TranslationProviderRequest] = []

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        self.requests.append(request)
        return TranslationProviderResult(
            items=tuple(TranslationTextItem(id=item.id, text=self.text) for item in request.items)
        )


class DocumentIRTranslationTests(unittest.TestCase):
    def test_term_version_service_loads_csv_and_builds_canonical_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,input offset voltage,输入失调电压,v1\n"
                "en2zh,slew rate,压摆率,v1\n",
                encoding="utf-8",
            )
            service = TermVersionService(terms_path, default_term_version_id="en2zh@v1")

            snapshot = service.resolve_for_job(None, language_pair="en2zh")

        self.assertEqual(snapshot.term_version_id, "en2zh@v1")
        self.assertEqual(snapshot.language_pair, "en2zh")
        self.assertEqual(snapshot.version, "v1")
        self.assertTrue(snapshot.snapshot_hash.startswith("sha256:"))
        self.assertEqual(
            [(entry.source_term, entry.target_term) for entry in snapshot.entries],
            [("input offset voltage", "输入失调电压"), ("slew rate", "压摆率")],
        )

    def test_term_version_service_uses_current_language_pair_with_default_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh,input offset voltage,输入失调电压,v1\n"
                "ru2zh,Постоянное обратное напряжение диода,反向直流电压,v1\n",
                encoding="utf-8",
            )
            service = TermVersionService(terms_path, default_term_version_id="en2zh@v1")

            snapshot = service.resolve_for_job(None, language_pair="ru2zh")

        self.assertEqual(snapshot.term_version_id, "ru2zh@v1")
        self.assertEqual(snapshot.language_pair, "ru2zh")
        self.assertEqual(snapshot.entries[0].target_term, "反向直流电压")

    def test_zh2en_provider_request_carries_bound_prompt_and_language_direction(self) -> None:
        provider = FakeTranslationProvider()
        service = DocumentIRTranslationService(provider)
        prompt = TranslationPromptSnapshot(
            id="zh2en@v1",
            name="中译英",
            markdown="# bound-zh2en",
            content_hash="sha256:bound",
            built_in=True,
        )

        request = service.build_provider_request(
            self._make_document_ir(),
            [TranslationTextItem(id="item-1", text="输入失调电压")],
            term_version=None,
            language_pair="zh2en",
            prompt=prompt,
            batch_id="batch-1",
        ).request

        self.assertEqual(request.source_language, "zh")
        self.assertEqual(request.target_language, "en")
        self.assertEqual(request.prompt_id, prompt.id)
        self.assertEqual(request.prompt_content_hash, prompt.content_hash)
        self.assertEqual(request.system_prompt_markdown, prompt.markdown)

    def test_term_version_service_rejects_duplicate_normalized_terms_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh, ADC ,模数转换器,v1\n"
                "en2zh,adc,重复项,v1\n",
                encoding="utf-8",
            )
            service = TermVersionService(terms_path, default_term_version_id="en2zh@v1")

            with self.assertRaises(ValueError) as context:
                service.resolve_for_job(None, language_pair="en2zh")

        self.assertIn("重复 normalized_source_term", str(context.exception))

    def test_term_version_service_keep_first_import_reports_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "translation_terms.csv"
            terms_path.write_text(
                "language_pair,source_term,target_term,version\n"
                "en2zh, ADC ,模数转换器,v1\n"
                "en2zh,adc,重复项,v1\n"
                "en2zh,DAC,数模转换器,v1\n",
                encoding="utf-8",
            )
            service = TermVersionService(terms_path, default_term_version_id="en2zh@v1")

            entries, report = service.load_csv_entries_for_import(dedupe="keep_first")

        self.assertEqual([(entry.source_term, entry.target_term) for entry in entries], [("ADC", "模数转换器"), ("DAC", "数模转换器")])
        self.assertEqual(report.imported_rows, 2)
        self.assertEqual(report.duplicate_rows, 1)
        self.assertEqual(report.duplicates[0].kept_row_number, 2)

    def test_document_ir_translation_rewrites_text_nodes_without_touching_structure_or_assets(self) -> None:
        provider = FakeTranslationProvider()
        service = DocumentIRTranslationService(provider)
        document = self._make_document_ir()
        terms = TermVersionSnapshot(
            term_version_id="en2zh@v1",
            language_pair="en2zh",
            version="v1",
            snapshot_hash="sha256:" + "0" * 64,
            entries=(
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="input offset voltage",
                    target_term="输入失调电压",
                    version="v1",
                ),
            ),
        )

        translated = service.translate(document, term_version=terms)

        self.assertEqual(translated.schema_version, document.schema_version)
        self.assertEqual(translated.pages, document.pages)
        self.assertEqual([block.id for block in translated.blocks], [block.id for block in document.blocks])
        self.assertEqual([block.type for block in translated.blocks], [block.type for block in document.blocks])
        self.assertEqual([block.layout for block in translated.blocks], [block.layout for block in document.blocks])
        self.assertEqual([block.captions for block in translated.blocks], [block.captions for block in document.blocks])
        self.assertEqual([block.footnotes for block in translated.blocks], [block.footnotes for block in document.blocks])
        self.assertEqual(translated.assets, document.assets)
        self.assertEqual(document.blocks[1].text, "The input offset voltage is low.")
        self.assertEqual(translated.metadata.document_language, "zh")
        self.assertEqual(translated.blocks[0].text, "1 特性")
        self.assertEqual(translated.blocks[1].text, "输入失调电压很低。")
        self.assertIn("<th>参数</th>", translated.blocks[2].html)
        self.assertIn("<td>输入电压</td>", translated.blocks[2].html)
        self.assertEqual(translated.blocks[3].list_items, ["低噪声", "高压摆率"])
        self.assertEqual(translated.blocks[4].latex, "E=mc^2")
        self.assertEqual(translated.blocks[5].text, "图 1. 引脚图")
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(provider.requests[0].terms, terms.entries)
        self.assertEqual([trace.source_term for trace in provider.requests[0].term_traces], ["input offset voltage"])
        self.assertNotIn("block_0005", [item.id for item in provider.requests[0].items])

    def test_document_ir_translation_batches_provider_requests_and_preserves_order(self) -> None:
        provider = FakeTranslationProvider()
        recorder = RecordingTranslationCallRecorder()
        service = DocumentIRTranslationService(provider, max_items_per_request=3, max_chars_per_request=10_000)
        document = self._make_document_ir()
        terms = TermVersionSnapshot(
            term_version_id="en2zh@v1",
            language_pair="en2zh",
            version="v1",
            snapshot_hash="sha256:" + "0" * 64,
            entries=(
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="input offset voltage",
                    target_term="输入失调电压",
                    version="v1",
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="low noise",
                    target_term="低噪声",
                    version="v1",
                ),
            ),
        )

        translated = service.translate(document, term_version=terms, call_recorder=recorder)

        self.assertEqual([len(request.items) for request in provider.requests], [3, 3, 2])
        self.assertEqual(recorder.success_requests, provider.requests)
        self.assertEqual(recorder.failure_requests, [])
        self.assertEqual([request.items[0].id for request in provider.requests], ["block_0001.text", "block_0003.html.0000", "block_0004.list_items.0001"])
        self.assertEqual([trace.batch_id for trace in provider.requests[0].term_traces], ["document_ir_provider_request_0001"])
        self.assertEqual([trace.batch_id for trace in provider.requests[1].term_traces], ["document_ir_provider_request_0002"])
        self.assertEqual(translated.blocks[0].text, "1 特性")
        self.assertEqual(translated.blocks[1].text, "输入失调电压很低。")
        self.assertEqual(translated.blocks[3].list_items, ["低噪声", "高压摆率"])

    def test_document_ir_translation_plan_splits_by_page_window(self) -> None:
        provider = FakeTranslationProvider()
        service = DocumentIRTranslationService(provider, max_items_per_request=100)
        document = self._make_document_ir()
        document.pages.append(DocumentIRPage(index=1, width=612.0, height=792.0))
        document.blocks[5].layout.page_index = 1

        _targets, items, plans = service.build_translation_plan(
            document,
            max_pages_per_batch=1,
            max_chars_per_batch=10_000,
            batch_id_prefix="batch_page",
        )

        self.assertEqual(len(items), 8)
        self.assertEqual([plan.batch_id for plan in plans], ["batch_page_0001", "batch_page_0002"])
        self.assertEqual([(plan.page_start, plan.page_end) for plan in plans], [(1, 1), (2, 2)])
        self.assertEqual(sum(plan.item_count for plan in plans), 8)

    def test_document_ir_translation_plan_splits_by_char_limit(self) -> None:
        provider = FakeTranslationProvider()
        service = DocumentIRTranslationService(provider, max_items_per_request=100)
        document = self._make_document_ir()

        _targets, items, plans = service.build_translation_plan(
            document,
            max_pages_per_batch=20,
            max_chars_per_batch=60,
            batch_id_prefix="batch_chars",
        )

        self.assertEqual(len(items), 8)
        self.assertGreater(len(plans), 1)
        self.assertEqual(sum(plan.item_count for plan in plans), 8)
        self.assertTrue(all(plan.char_count <= 60 for plan in plans))

    def test_document_ir_translation_supports_ru2zh_language_pair_and_terms(self) -> None:
        provider = EchoSingleItemTranslationProvider("反向直流电压")
        service = DocumentIRTranslationService(provider)
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="docjob_ru", source_file_id="file_ru", document_language="ru"),
            pages=[DocumentIRPage(index=0, width=612.0, height=792.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_0001",
                    type="paragraph",
                    order=0,
                    text="Постоянное обратное напряжение диода",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 72.0, 540.0, 96.0), role="body"),
                ),
            ],
            assets=[],
        )
        terms = TermVersionSnapshot(
            term_version_id="ru2zh@v1",
            language_pair="ru2zh",
            version="v1",
            snapshot_hash="sha256:" + "2" * 64,
            entries=(
                TranslationTermEntry(
                    language_pair="ru2zh",
                    source_term="Постоянное обратное напряжение диода",
                    target_term="反向直流电压",
                    version="v1",
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="input offset voltage",
                    target_term="输入失调电压",
                    version="v1",
                ),
            ),
        )

        translated = service.translate(document, term_version=terms, language_pair="ru2zh")

        self.assertEqual(translated.metadata.document_language, "zh")
        self.assertEqual(translated.blocks[0].text, "反向直流电压")
        request = provider.requests[0]
        self.assertEqual(request.language_pair, "ru2zh")
        self.assertEqual(request.source_language, "ru")
        self.assertEqual(request.target_language, "zh")
        self.assertEqual([term.language_pair for term in request.terms], ["ru2zh"])

    def test_document_ir_translation_injects_only_matched_terms_with_trace(self) -> None:
        provider = FakeTranslationProvider()
        recorder = RecordingTranslationCallRecorder()
        service = DocumentIRTranslationService(provider)
        document = self._make_document_ir()
        document.blocks[1].text = (
            " ".join(["leading"] * 20)
            + " input offset voltage "
            + " ".join(["trailing"] * 20)
        )
        terms = TermVersionSnapshot(
            term_version_id="en2zh@v1",
            language_pair="en2zh",
            version="v1",
            snapshot_hash="sha256:" + "1" * 64,
            entries=(
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="offset voltage",
                    target_term="偏移电压",
                    version="v1",
                    priority=999,
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="input offset voltage",
                    target_term="输入失调电压",
                    version="v1",
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="low noise",
                    target_term="低噪声",
                    version="v1",
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="LOW NOISE",
                    target_term="不应命中",
                    version="v1",
                    case_sensitive=True,
                    priority=1000,
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="slew rate",
                    target_term="压摆率",
                    version="v1",
                    priority=5,
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="High slew rate",
                    target_term="禁用术语",
                    version="v1",
                    status="disabled",
                    priority=1000,
                ),
                TranslationTermEntry(
                    language_pair="en2zh",
                    source_term="unused term",
                    target_term="未使用术语",
                    version="v1",
                    priority=1000,
                ),
            ),
        )

        service.translate(document, term_version=terms, call_recorder=recorder)

        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(
            [term.source_term for term in request.terms],
            ["input offset voltage", "slew rate", "low noise"],
        )
        self.assertEqual(
            [trace.source_term for trace in request.term_traces],
            [term.source_term for term in request.terms],
        )
        self.assertTrue(all(trace.injected_to_glossary for trace in request.term_traces))
        self.assertEqual(
            [trace.segment_id for trace in request.term_traces],
            ["block_0002.text", "block_0004.list_items.0001", "block_0004.list_items.0000"],
        )
        input_trace = next(trace for trace in request.term_traces if trace.source_term == "input offset voltage")
        paragraph_text = next(item.text for item in request.items if item.id == "block_0002.text")
        self.assertLessEqual(len(input_trace.context_snippet or ""), 120)
        self.assertNotEqual(input_trace.context_snippet, paragraph_text)
        self.assertEqual(recorder.success_requests, [request])
        self.assertEqual(recorder.failure_requests, [])

    def test_encoded_budget_splits_deterministically_and_keeps_source_char_count(self) -> None:
        document = self._make_document_ir()
        document.blocks = [
            DocumentIRBlock(id=f"value_{index}", type="paragraph", order=index, text="High 5 V")
            for index in range(3)
        ]
        provider = Mock()
        provider.translate.side_effect = lambda request: TranslationProviderResult(tuple(
            TranslationTextItem(item.id, item.text.replace("High", "高")) for item in request.items
        ))
        service = DocumentIRTranslationService(provider, max_chars_per_request=30)
        _targets, items, plans = service.build_translation_plan(
            document, max_pages_per_batch=20, max_chars_per_batch=30, batch_id_prefix="budget",
        )
        self.assertEqual([plan.item_count for plan in plans], [1, 1, 1])
        self.assertEqual([plan.char_count for plan in plans], [len("High 5 V")] * 3)
        translated = service.translate(document, term_version=None)
        self.assertEqual(provider.translate.call_count, 3)
        for call in provider.translate.call_args_list:
            request = call.args[0]
            self.assertLessEqual(sum(len(item.text) for item in request.items), 30)
            self.assertIn("{{MD2W_PT_v1_0_1}}", request.items[0].text)
        self.assertEqual([block.text for block in translated.blocks], ["高 5 V"] * 3)
        self.assertEqual(sum(len(item.text) for item in items), 24)

    def test_single_encoded_item_budget_failure_happens_before_provider_and_audit(self) -> None:
        document = self._make_document_ir()
        document.blocks = [DocumentIRBlock(id="value", type="paragraph", order=0, text="5 V")]
        provider, recorder = Mock(), Mock()
        service = DocumentIRTranslationService(provider, max_chars_per_request=10)
        with self.assertRaises(DocumentIRTranslationError) as context:
            service.translate(document, term_version=None, call_recorder=recorder)
        self.assertEqual(context.exception.code, "translation_request_budget_exceeded")
        self.assertEqual(context.exception.evidence.stage, "budget")
        self.assertIsNone(context.exception.evidence.response_sha256)
        provider.translate.assert_not_called()
        recorder.record_success.assert_not_called()
        recorder.record_failure.assert_not_called()
        with self.assertRaises(TranslationIntegrityError):
            service.build_provider_request(document, [TranslationTextItem("a", "5 V")], term_version=None, language_pair="en2zh", batch_id="existing")

    def test_protected_spans_exclude_terms_without_changing_natural_term_offsets(self) -> None:
        service = DocumentIRTranslationService(Mock())
        source = "Typical OPA228 amplifier at 5 V"
        terms = TermVersionSnapshot("terms", "en2zh", "v1", "sha256:terms", tuple(
            TranslationTermEntry("en2zh", source_term, "译法", "v1")
            for source_term in ("OPA228 amplifier", "OPA228", "amplifier", "5 V", "Typical")
        ))
        prepared = service.build_provider_request(
            self._make_document_ir(), [TranslationTextItem("a", source)],
            term_version=terms, language_pair="en2zh", batch_id="batch",
        )
        self.assertEqual([entry.source_term for entry in prepared.request.terms], ["amplifier", "Typical"])
        amplifier = prepared.request.term_traces[0]
        self.assertEqual((amplifier.match_start, amplifier.match_end), (source.index("amplifier"), source.index("amplifier") + len("amplifier")))
        self.assertEqual(amplifier.context_snippet, source)
        self.assertNotIn("OPA228", prepared.request.items[0].text)
        self.assertEqual(prepared.encoded_batch, encode(prepared.source_items))

    def test_bad_second_item_or_later_batch_never_applies_partial_replacements(self) -> None:
        for max_items in (10, 1):
            with self.subTest(max_items=max_items):
                provider, recorder = Mock(), Mock()
                document = self._make_document_ir()
                document.blocks = [
                    DocumentIRBlock(id="first", type="paragraph", order=0, text="Typical OPA228"),
                    DocumentIRBlock(id="second", type="paragraph", order=1, text="High 25°C"),
                ]
                before = document.model_dump(mode="json")
                def respond(request):
                    return TranslationProviderResult(tuple(
                        TranslationTextItem(item.id, item.text.replace("Typical", "典型值").replace("High", "高") + ("; 999 V" if item.id == "second.text" else ""))
                        for item in request.items
                    ))
                provider.translate.side_effect = respond
                service = DocumentIRTranslationService(provider, max_items_per_request=max_items)
                with patch.object(service, "apply_replacements", wraps=service.apply_replacements) as apply:
                    with self.assertRaises(DocumentIRTranslationError) as context:
                        service.translate(document, term_version=None, call_recorder=recorder)
                apply.assert_not_called()
                self.assertEqual(context.exception.code, "translation_integrity_technical_mismatch")
                self.assertEqual(document.model_dump(mode="json"), before)
                self.assertEqual(recorder.record_failure.call_count, 1)
                self.assertEqual(recorder.record_success.call_count, 0 if max_items == 10 else 1)
                self.assertEqual(recorder.record_failure.call_args.kwargs["integrity"].status, "failed")

    def test_audit_failure_is_visible_and_never_creates_a_second_audit(self) -> None:
        provider, recorder = Mock(), Mock()
        provider.translate.side_effect = lambda request: TranslationProviderResult(request.items)
        recorder.record_success.side_effect = OSError("审计存储失败")
        service = DocumentIRTranslationService(provider)
        with patch.object(service, "apply_replacements", wraps=service.apply_replacements) as apply:
            with self.assertRaisesRegex(OSError, "审计存储失败"):
                service.translate(self._make_document_ir(), term_version=None, call_recorder=recorder)
        apply.assert_not_called()
        recorder.record_success.assert_called_once()
        recorder.record_failure.assert_not_called()

    def test_opa228_public_fixture_uses_formal_converter_fake_provider_and_validator(self) -> None:
        from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
        fixture = Path(__file__).parent / "fixtures/component_pdf_samples/samples/texas-instruments/op-amp/ti-opamp-opa228-p1-smoke/mineru/component_content_list_v2.json"
        provider = Mock()
        def translate_request(request):
            return TranslationProviderResult(tuple(TranslationTextItem(
                item.id, item.text.replace("Typical", "典型值").replace("Precision", "精密").replace("Operational Amplifier", "运算放大器").replace("Parameter", "参数")
            ) for item in request.items))
        provider.translate.side_effect = translate_request
        with tempfile.TemporaryDirectory(prefix="translation_integrity_opa228_") as temp_dir:
            archive_path = Path(temp_dir) / "mineru.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.write(fixture, "component_content_list_v2.json")
            document = MinerUToDocumentIRService().convert_zip(
                archive_path, job_id="opa228-integrity", source_file_id="public-fixture", document_language="en",
            ).document
            source = document.model_dump(mode="json")
            service = DocumentIRTranslationService(provider)
            with patch("socket.socket", side_effect=AssertionError("离线验收禁止网络")):
                translated = service.translate(document, term_version=None)
        self.assertEqual(document.model_dump(mode="json"), source)
        self.assertEqual(translated.pages, document.pages)
        self.assertEqual(translated.assets, document.assets)
        self.assertEqual(translated.quality_flags, document.quality_flags)
        for old, new in zip(document.blocks, translated.blocks):
            unchanged = {key: value for key, value in old.model_dump(mode="json").items() if key not in {"text", "html", "list_items"}}
            self.assertEqual({key: value for key, value in new.model_dump(mode="json").items() if key not in {"text", "html", "list_items"}}, unchanged)
            if old.type == "formula":
                self.assertEqual(new, old)
            if old.html:
                def skeleton(html):
                    return [(tag.name, tag.attrs) for tag in BeautifulSoup(html, "html.parser").find_all(True)]
                self.assertEqual(skeleton(new.html), skeleton(old.html))
        all_text = "\n".join(item.text for item in service.extract_translation_items(translated)[1])
        for literal in ("OPA228", "3 nV/sqrt(Hz)", "10 V/us"):
            self.assertIn(literal, all_text)
        self.assertIn("精密", all_text)
        self.assertGreater(provider.translate.call_count, 0)
        self.assertTrue(any("{{MD2W_PT_v1_" in item.text for call in provider.translate.call_args_list for item in call.args[0].items))

    def _make_document_ir(self) -> DocumentIR:
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="docjob_test",
                source_file_id="file_test",
                document_language="en",
            ),
            pages=[DocumentIRPage(index=0, width=612.0, height=792.0)],
            blocks=[
                DocumentIRBlock(
                    id="block_0001",
                    type="heading",
                    order=0,
                    text="1 Features",
                    level=1,
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 72.0, 240.0, 96.0), role="body"),
                ),
                DocumentIRBlock(
                    id="block_0002",
                    type="paragraph",
                    order=1,
                    text="The input offset voltage is low.",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 110.0, 540.0, 140.0), role="body"),
                ),
                DocumentIRBlock(
                    id="block_0003",
                    type="table",
                    order=2,
                    text="Electrical Characteristics",
                    html="<table><tr><th>Parameter</th><td>Input voltage</td></tr></table>",
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=(72.0, 150.0, 540.0, 260.0),
                        role="body",
                        continuation_heights=[80.0],
                    ),
                    captions=["Table 1. Electrical Characteristics"],
                    footnotes=["All values are typical."],
                ),
                DocumentIRBlock(
                    id="block_0004",
                    type="list",
                    order=3,
                    text="Low noise\nHigh slew rate",
                    list_items=["Low noise", "High slew rate"],
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 280.0, 300.0, 330.0), role="body"),
                ),
                DocumentIRBlock(
                    id="block_0005",
                    type="formula",
                    order=4,
                    text="E=mc^2",
                    latex="E=mc^2",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 350.0, 240.0, 380.0), role="body"),
                ),
                DocumentIRBlock(
                    id="block_0006",
                    type="image",
                    order=5,
                    text="Figure 1. Pin diagram",
                    asset_ref="asset_0001",
                    layout=DocumentIRBlockLayout(page_index=0, bbox=(72.0, 400.0, 360.0, 540.0), role="body"),
                    captions=["Figure 1. Pin diagram"],
                ),
            ],
            assets=[
                DocumentIRAsset(
                    id="asset_0001",
                    kind="image",
                    source_path="images/pin.png",
                    file_id="file_image",
                    object_key="document-files/tenant/file_image/pin.png",
                    mime_type="image/png",
                    checksum_sha256="sha256-image",
                )
            ],
            quality_flags=["sample_flag"],
        )


if __name__ == "__main__":
    unittest.main()
