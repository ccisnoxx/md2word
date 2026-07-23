from __future__ import annotations

# tests/test_document_ir_translation.py: 覆盖 P1 DocumentIR 翻译 provider、术语版本和结构不变性。

import tempfile
import unittest
from pathlib import Path

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
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
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
                TranslationTextItem(id=item.id, text=translations[item.id])
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
    ) -> None:
        self.success_requests.append(request)

    def record_failure(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        *,
        error: Exception,
        duration_ms: int,
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
        )

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
            max_chars_per_batch=20,
            batch_id_prefix="batch_chars",
        )

        self.assertEqual(len(items), 8)
        self.assertGreater(len(plans), 1)
        self.assertEqual(sum(plan.item_count for plan in plans), 8)
        self.assertTrue(all(plan.char_count <= 20 or plan.item_count == 1 for plan in plans))

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
