from __future__ import annotations

# tests/test_document_ir_layout_contract.py: 覆盖 DocumentIR v1/v2 布局合同兼容性。

import unittest
import json
import tempfile
import zipfile
from pathlib import Path

from app.services.document_ir import MinerUToDocumentIRService

from app.services.document_ir.integrity import build_source_integrity
from app.services.renderer.evidence import build_renderer_metadata
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
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

        evidence = build_source_integrity(document)
        self.assertEqual(evidence["blocking_quality_flags"], [])

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
