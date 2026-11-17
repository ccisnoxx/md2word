from __future__ import annotations

# tests/test_document_ir_layout_contract.py: 覆盖布局、来源账本及 DocumentIR v1/v2 兼容性。

from copy import deepcopy
import unittest
import json
import tempfile
import zipfile
from pathlib import Path

from app.services.document_ir import MinerUToDocumentIRService

from app.services.document_ir.integrity import DocumentIntegrityError, build_source_integrity
from app.services.renderer.render_evidence import build_renderer_metadata
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
    SourceItemLedgerScope,
)
from app.services.document_ir.page_degradation import replace_degraded_pages
from app.services.document_ir.source_item_ledger import (
    ANNOTATION_LEDGER_MISMATCH, LIST_ITEM_COUNT_MISMATCH, LIST_ITEM_LEDGER_MISMATCH,
    apply_target_digests, build_annotation_ledger, build_list_item_ledger, ledger_positions,
    validate_ledger_source_identity,
)


class DocumentIRLayoutContractTests(unittest.TestCase):
    def test_v1_payload_defaults_layout_fields_to_empty(self) -> None:
        payload = {
            "schema_version": "document-ir/v1",
            "metadata": {
                "job_id": "docjob_v1",
                "source_file_id": "file_v1",
                "document_language": "en",
            },
            "blocks": [
                {
                    "id": "block_0001",
                    "type": "paragraph",
                    "order": 0,
                    "text": "Body",
                }
            ],
            "assets": [],
            "quality_flags": [],
        }

        document = DocumentIR.model_validate(payload)

        self.assertEqual(document.schema_version, "document-ir/v1")
        self.assertEqual(document.pages, [])
        self.assertIsNone(document.blocks[0].layout)
        self.assertEqual(document.blocks[0].captions, [])
        self.assertEqual(document.blocks[0].footnotes, [])
        self.assertNotIn("caption_reconciliation", document.blocks[0].metadata)
        self.assertIsNone(document.metadata.mineru_validation)
        self.assertIsNone(document.metadata.source_block_count)
        self.assertEqual(document.metadata.source_type_counts, {})
        self.assertNotIn("source_item_ledger_scope", document.model_dump(mode="json")["metadata"])

        evidence = build_source_integrity(document)
        self.assertEqual(evidence["blocking_quality_flags"], [])

    def test_list_item_ledger_blocks_item_count_drift(self) -> None:
        ledger = {"version": "list-item-ledger/v1", "selected_field": "content/list_items", "mode": "v2_items",
                  "source_item_count": 2, "empty_item_count": 0, "item_count": 2}

        def document(items: list[str], *, with_ledger: bool) -> DocumentIR:
            return DocumentIR(
                schema_version="document-ir/v2",
                metadata=DocumentIRMetadata(job_id="docjob_ledger", source_file_id="file_ledger", document_language="en",
                                            source_block_count=1, source_type_counts={"list": 1}),
                blocks=[DocumentIRBlock(id="block_0001", type="list", order=0, list_items=items,
                                        metadata={"source_type": "list", **({"list_item_ledger": ledger} if with_ledger else {})})],
            )

        intact = build_source_integrity(document(["A", "B"], with_ledger=True))
        self.assertEqual(intact["blocking_quality_flags"], [])
        self.assertEqual(intact["list_item_ledger"], {"version": "list-item-ledger/v1", "block_count": 1,
                                                      "item_count": 2, "mismatch_block_ids": []})

        dropped = build_source_integrity(document(["B"], with_ledger=True))
        self.assertEqual(dropped["blocking_quality_flags"], ["source_ir_integrity:list_item_count_mismatch"])
        self.assertEqual(dropped["list_item_ledger"]["mismatch_block_ids"], ["block_0001"])

        # 历史 IR 没有账本：不报阻断，也不新增证据键。
        legacy = build_source_integrity(document(["B"], with_ledger=False))
        self.assertEqual(legacy["blocking_quality_flags"], [])
        self.assertNotIn("list_item_ledger", legacy)

    def test_v2_list_ledger_checks_content_order_expansion_empty_slots_and_identity(self) -> None:
        ledger = build_list_item_ledger("items", "legacy_items", [
            ("A", ["A"]), ("", []), ({"first": "B", "second": "C"}, ["B", "C"]), ("A", ["A"]),
        ])
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="job", source_file_id="file", document_language="en",
                source_block_count=1, source_type_counts={"list": 1},
                source_item_ledger_scope=SourceItemLedgerScope(
                    version="source-item-ledger-scope/v1", annotation_block_ids=(),
                ),
            ),
            blocks=[DocumentIRBlock(
                id="list", type="list", order=0, list_items=["A", "B", "C", "A"],
                metadata={"source_type": "list", "list_item_ledger": ledger},
            )],
        )
        self.assertEqual(DocumentIR.model_validate_json(document.model_dump_json()), document)
        self.assertEqual(
            (ledger["source_item_count"], ledger["empty_item_count"], ledger["item_count"]), (4, 1, 4),
        )
        self.assertEqual(
            [(item.get("output_index"), item.get("output_start"), item.get("output_end")) for item in ledger["items"]],
            [(0, None, None), (None, None, None), (None, 1, 3), (3, None, None)],
        )
        self.assertEqual(build_source_integrity(document)["list_item_ledger"]["mismatch_block_ids"], [])

        cases = [
            (["A", "C", "A"], LIST_ITEM_COUNT_MISMATCH),
            (["A", "B", "C"], LIST_ITEM_COUNT_MISMATCH),
            (["A", "unexpected", "C", "A"], LIST_ITEM_LEDGER_MISMATCH),
            (["A", "C", "B", "A"], LIST_ITEM_LEDGER_MISMATCH),
        ]
        for texts, flag in cases:
            with self.subTest(texts=texts):
                broken = document.model_copy(deep=True)
                broken.blocks[0].list_items = texts
                self.assertEqual(build_source_integrity(broken)["blocking_quality_flags"], [flag])
                with self.assertRaises(DocumentIntegrityError) as caught:
                    DocumentIR.model_validate_json(broken.model_dump_json())
                self.assertEqual(caught.exception.evidence["blocking_quality_flags"], [flag])
        broken = document.model_copy(deep=True)
        broken.blocks[0].metadata["list_item_ledger"]["items"][3]["output_index"] = 0
        with self.assertRaises(DocumentIntegrityError) as caught:
            DocumentIR.model_validate_json(broken.model_dump_json())
        self.assertEqual(caught.exception.evidence["blocking_quality_flags"], [LIST_ITEM_LEDGER_MISMATCH])

    def test_annotation_ledger_detects_missing_arrays_and_duplicate_source_positions(self) -> None:
        block = DocumentIRBlock(
            id="figure", type="image", order=0, text="图题", captions=["图题"],
            footnotes=["同文脚注", "同文脚注", "末尾脚注"],
            metadata={"caption_text_alias_index": 0, "annotation_ledger": build_annotation_ledger([
                ("figure", "captions", 0, "图题"),
                ("figure", "footnotes", 0, "同文脚注"),
                ("figure", "footnotes", 1, "同文脚注"),
                ("figure", "footnotes", 2, "末尾脚注"),
            ])},
        )
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="job", source_file_id="file", document_language="zh",
                source_item_ledger_scope=SourceItemLedgerScope(
                    version="source-item-ledger-scope/v1", annotation_block_ids=("figure",),
                ),
            ),
            blocks=[block],
        )
        payload = document.model_dump(mode="json")
        self.assertEqual(DocumentIR.model_validate(payload).blocks[0].footnotes, block.footnotes)
        for damage in ("caption", "collapse", "reorder", "duplicate_identity", "drop_ledger_and_arrays", "unknown_version"):
            with self.subTest(damage=damage):
                broken = deepcopy(payload)
                target = broken["blocks"][0]
                if damage == "caption":
                    target["captions"] = []
                elif damage == "collapse":
                    target["footnotes"] = ["同文脚注末尾脚注"]
                elif damage == "reorder":
                    target["footnotes"] = ["末尾脚注", "同文脚注", "同文脚注"]
                elif damage == "duplicate_identity":
                    target["metadata"]["annotation_ledger"]["items"][2]["source_index"] = 0
                elif damage == "drop_ledger_and_arrays":
                    target["captions"] = target["footnotes"] = []
                    del target["metadata"]["annotation_ledger"]
                else:
                    broken["metadata"]["source_item_ledger_scope"]["version"] = "unknown"
                with self.assertRaises(DocumentIntegrityError) as caught:
                    DocumentIR.model_validate(broken)
                self.assertEqual(caught.exception.evidence["blocking_quality_flags"], [ANNOTATION_LEDGER_MISMATCH])

    def test_translated_ledger_checks_target_digest_and_frozen_source_identity(self) -> None:
        def source(text: str) -> DocumentIR:
            return DocumentIR(
                schema_version="document-ir/v2",
                metadata=DocumentIRMetadata(
                    job_id="job", source_file_id="file", document_language="en", translation_item_scope="annotations-v1",
                    source_item_ledger_scope=SourceItemLedgerScope(
                        version="source-item-ledger-scope/v1", annotation_block_ids=("figure",),
                    ),
                ),
                blocks=[
                    DocumentIRBlock(id="list", type="list", order=0, list_items=[text],
                                    metadata={"list_item_ledger": build_list_item_ledger(
                                        "items", "legacy_items", [(text, [text])],
                                    )}),
                    DocumentIRBlock(id="figure", type="image", order=1, footnotes=["Note", "Note"],
                                    metadata={"annotation_ledger": build_annotation_ledger([
                                        ("figure", "footnotes", 0, "Note"), ("figure", "footnotes", 1, "Note"),
                                    ])}),
                ],
            )
        original = source("List")
        translated = original.model_copy(deep=True)
        positions = (("list", "list_items", 0), ("figure", "footnotes", 0), ("figure", "footnotes", 1))
        self.assertEqual(ledger_positions(translated), positions)
        with self.assertRaises(DocumentIntegrityError):
            apply_target_digests(translated, {positions[0]: "条目", positions[1]: "脚注"})
        apply_target_digests(translated, dict(zip(positions, ("条目", "脚注", "脚注"))))
        translated.blocks[0].list_items = ["条目"]
        translated.blocks[1].footnotes = ["脚注", "脚注"]
        translated.metadata.translation_items_applied = True
        restored = DocumentIR.model_validate_json(translated.model_dump_json())
        validate_ledger_source_identity(original, restored)

        with self.assertRaises(DocumentIntegrityError):
            validate_ledger_source_identity(source("Another source"), restored)
        with self.assertRaises(DocumentIntegrityError):
            validate_ledger_source_identity(original, original)
        restored.blocks[1].footnotes[1] = "替换"
        with self.assertRaises(DocumentIntegrityError) as caught:
            DocumentIR.model_validate_json(restored.model_dump_json())
        self.assertEqual(caught.exception.evidence["blocking_quality_flags"], [ANNOTATION_LEDGER_MISMATCH])

    def test_page_degradation_removes_only_annotation_scope_of_replaced_blocks(self) -> None:
        blocks = [
            DocumentIRBlock(id=block_id, type="image", order=page, page_index=page,
                            footnotes=["脚注"], metadata={"annotation_ledger": build_annotation_ledger([
                                (block_id, "footnotes", 0, "脚注"),
                            ])})
            for page, block_id in enumerate(("page_zero", "page_one"))
        ]
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="job", source_file_id="file", document_language="zh",
                source_item_ledger_scope=SourceItemLedgerScope(
                    version="source-item-ledger-scope/v1", annotation_block_ids=("page_zero", "page_one"),
                ),
            ),
            blocks=blocks,
        )
        replaced, _ = replace_degraded_pages(
            document, {0: b"raster"}, {0: {"reason_codes": ["render_failed"]}},
            source_pdf_sha256="a" * 64, dpi=120, trigger="render",
        )
        self.assertEqual(replaced, {"page_zero"})
        restored = DocumentIR.model_validate_json(document.model_dump_json())
        self.assertEqual(restored.metadata.source_item_ledger_scope.annotation_block_ids, ("page_one",))
        self.assertEqual(ledger_positions(restored), (("page_one", "footnotes", 0),))

    def test_list_and_toc_region_flags_project_as_controlled_codes(self) -> None:
        from app.domains.document_jobs.review import _safe_quality_flag
        from app.services.renderer.render_event_summary import controlled_quality_flags

        flags = ["source_ir_integrity:list_item_count_mismatch", "ir_docx_integrity:toc_coalesced_outside_region"]
        self.assertEqual(controlled_quality_flags(flags), flags)
        self.assertTrue(all(_safe_quality_flag(flag) for flag in flags))

    def test_v2_payload_round_trips_page_and_block_layout(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="docjob_v2",
                source_file_id="file_v2",
                document_language="en",
                source_block_count=1,
                source_type_counts={"table": 1},
            ),
            pages=[
                DocumentIRPage(index=0, width=612.0, height=792.0, metadata={"orientation": "portrait"}),
            ],
            blocks=[
                DocumentIRBlock(
                    id="block_0001",
                    type="table",
                    order=0,
                    page_index=0,
                    text="Electrical Characteristics",
                    html="<table><tr><td>Gain</td></tr></table>",
                    layout=DocumentIRBlockLayout(
                        page_index=0,
                        bbox=(72.0, 120.0, 540.0, 240.0),
                        role="body",
                        source_index=3,
                        continuation_heights=[100.0],
                        column_hint="wide",
                    ),
                    captions=["Table 1. Electrical Characteristics"],
                    footnotes=["All values are typical."],
                    metadata={"layout_role_reason": "column_hint=wide;source=bbox"},
                )
            ],
            quality_flags=[
                "layout_wide_table:block_0001",
                "table_continuation:block_0001",
                "layout_caption_binding:block_0001",
            ],
        )

        decoded = DocumentIR.model_validate_json(document.model_dump_json())

        self.assertIsNone(decoded.metadata.mineru_validation)
        self.assertEqual(decoded.schema_version, "document-ir/v2")
        self.assertEqual(decoded.pages[0].width, 612.0)
        self.assertEqual(decoded.metadata.source_block_count, 1)
        self.assertEqual(decoded.metadata.source_type_counts, {"table": 1})
        self.assertEqual(decoded.pages[0].metadata["orientation"], "portrait")
        self.assertEqual(decoded.blocks[0].layout.bbox, (72.0, 120.0, 540.0, 240.0))
        self.assertEqual(decoded.blocks[0].layout.continuation_heights, [100.0])
        self.assertEqual(decoded.blocks[0].layout.column_hint, "wide")
        self.assertEqual(decoded.blocks[0].captions, ["Table 1. Electrical Characteristics"])
        self.assertEqual(decoded.blocks[0].footnotes, ["All values are typical."])
        self.assertEqual(decoded.blocks[0].metadata["layout_role_reason"], "column_hint=wide;source=bbox")
        self.assertIn("layout_wide_table:block_0001", decoded.quality_flags)
        self.assertNotIn("caption_reconciliation", decoded.blocks[0].metadata)

    def test_optional_caption_evidence_round_trips_and_summary_is_bounded_without_originals(self) -> None:
        raw = [{"type": "text", "content": "图5 私有标题图6 连写"}]
        caption_evidence = {
            "rule_version": "caption-reconciliation/v1", "status": "uncertain",
            "originals": [{"json_pointer": "/0/chart_caption", "value": raw, "groups": ["/0/chart_caption"]}],
            "bindings": [], "reasons": ["split_boundary_uncertain"],
        }
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="caption", source_file_id="source", document_language="zh"),
            blocks=[DocumentIRBlock(
                id=f"block_{index:04d}", type="paragraph", order=index, text="正文",
                metadata={"mineru_source": {"json_pointer": f"/{index}"}, "caption_reconciliation": caption_evidence},
            ) for index in range(43)],
            quality_flags=["caption_binding_uncertain"],
        )
        document.blocks.append(DocumentIRBlock(
            id="context", type="paragraph", order=44, text="条件", metadata={
                "source_block_id": "block_0000", "caption_reconciliation": caption_evidence,
            },
        ))
        decoded = DocumentIR.model_validate_json(document.model_dump_json())
        self.assertEqual(decoded, document)
        self.assertEqual(decoded.blocks[0].metadata["caption_reconciliation"]["originals"][0]["value"], raw)
        summary = build_renderer_metadata(decoded)["caption_reconciliation"]
        self.assertEqual(summary["block_count"], 43)
        self.assertEqual(summary["status_counts"], {"uncertain": 43})
        self.assertEqual(summary["reason_counts"], {"split_boundary_uncertain": 43})
        self.assertEqual(len(summary["examples"]), 40)
        self.assertEqual(summary["omitted_example_count"], 3)
        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("私有", serialized)
        self.assertNotIn("originals", serialized)

    def test_new_report_round_trips_without_changing_v2_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mineru.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content_list_v2.json", json.dumps([[{"type": "text", "text": "12 µV"}]]))
            result = MinerUToDocumentIRService().convert_zip(path, job_id="job", source_file_id="file", document_language="en")
        decoded = DocumentIR.model_validate_json(result.document.model_dump_json())
        self.assertEqual(decoded.schema_version, "document-ir/v2")
        self.assertEqual(decoded.metadata.mineru_validation, result.validation_report)
        self.assertEqual(decoded.blocks[0].metadata["mineru_source"]["json_pointer"], "/0/0")

    def test_historical_validation_report_keeps_versions_and_optional_defaults(self):
        document = DocumentIR.model_validate({
            "schema_version": "document-ir/v2",
            "metadata": {
                "job_id": "job", "source_file_id": "file", "document_language": "en",
                "mineru_validation": {
                    "schema_version": "mineru-artifact-validation/v1",
                    "validator_version": "mineru-artifact-validator/v1",
                    "policy_version": "mineru-input-policy/v1",
                    "package_sha256": "0" * 64,
                    "can_convert": True,
                },
            },
        })
        report = document.metadata.mineru_validation
        self.assertEqual(report.validator_version, "mineru-artifact-validator/v1")
        self.assertEqual(report.policy_version, "mineru-input-policy/v1")
        self.assertTrue(report.complete)
        self.assertEqual(report.effective_inventory, {})
        self.assertEqual(report.normalization, {})
        decoded = DocumentIR.model_validate_json(document.model_dump_json())
        self.assertEqual(decoded.metadata.mineru_validation, report)
        self.assertEqual(decoded.schema_version, "document-ir/v2")


if __name__ == "__main__":
    unittest.main()
