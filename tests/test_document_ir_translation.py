from __future__ import annotations

# tests/test_document_ir_translation.py: 覆盖 P1 DocumentIR 翻译 provider、术语版本和结构不变性。

import tempfile
import unittest
from pathlib import Path

from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock, DocumentIRMetadata
from app.domains.translation.models import (
    TermVersionSnapshot,
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
        self.assertEqual([block.id for block in translated.blocks], [block.id for block in document.blocks])
        self.assertEqual([block.type for block in translated.blocks], [block.type for block in document.blocks])
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
        self.assertNotIn("block_0005", [item.id for item in provider.requests[0].items])

    def _make_document_ir(self) -> DocumentIR:
        return DocumentIR(
            metadata=DocumentIRMetadata(
                job_id="docjob_test",
                source_file_id="file_test",
                document_language="en",
            ),
            blocks=[
                DocumentIRBlock(id="block_0001", type="heading", order=0, text="1 Features", level=1),
                DocumentIRBlock(id="block_0002", type="paragraph", order=1, text="The input offset voltage is low."),
                DocumentIRBlock(
                    id="block_0003",
                    type="table",
                    order=2,
                    text="Electrical Characteristics",
                    html="<table><tr><th>Parameter</th><td>Input voltage</td></tr></table>",
                ),
                DocumentIRBlock(
                    id="block_0004",
                    type="list",
                    order=3,
                    text="Low noise\nHigh slew rate",
                    list_items=["Low noise", "High slew rate"],
                ),
                DocumentIRBlock(id="block_0005", type="formula", order=4, text="E=mc^2", latex="E=mc^2"),
                DocumentIRBlock(id="block_0006", type="image", order=5, text="Figure 1. Pin diagram", asset_ref="asset_0001"),
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
