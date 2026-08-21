from __future__ import annotations

# tests/test_document_ir_layout_contract.py: 覆盖 DocumentIR v1/v2 布局合同兼容性。

import unittest

from app.services.document_ir.integrity import build_source_integrity
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
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

    def test_source_integrity_accepts_explicit_toc_disposition_and_requires_complete_new_semantics(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="docjob_semantics",
                source_file_id="file_semantics",
                document_language="en",
                source_block_count=2,
                source_type_counts={"list": 1, "title": 1},
            ),
            blocks=[
                DocumentIRBlock(
                    id="title",
                    type="paragraph",
                    order=0,
                    text="Table of Contents",
                    layout=DocumentIRBlockLayout(role="body"),
                    metadata={
                        "source_type": "title",
                        "annotation_role": "toc_title",
                        "semantic_decision_reason": "toc_title_and_anchor",
                    },
                ),
                DocumentIRBlock(
                    id="anchor",
                    type="paragraph",
                    order=0,
                    text="",
                    layout=DocumentIRBlockLayout(role="body"),
                    metadata={
                        "source_type": "toc_anchor",
                        "source_block_id": "title",
                        "annotation_role": "toc_anchor",
                        "semantic_decision_reason": "synthetic_toc_anchor",
                    },
                ),
                DocumentIRBlock(
                    id="entries",
                    type="list",
                    order=1,
                    list_items=["Features................ 2"],
                    layout=DocumentIRBlockLayout(role="toc_source"),
                    metadata={
                        "source_type": "list",
                        "semantic_decision_reason": "explicit_toc_region_source",
                    },
                ),
            ],
        )

        evidence = build_source_integrity(document)
        self.assertEqual(evidence["blocking_quality_flags"], [])
        document.blocks[1].metadata.pop("semantic_decision_reason")
        self.assertEqual(build_source_integrity(document)["blocking_quality_flags"], [])
        document.blocks[2].metadata.pop("semantic_decision_reason")
        self.assertIn(
            "source_ir_integrity:semantic_decision_missing:list",
            build_source_integrity(document)["blocking_quality_flags"],
        )

    def test_source_integrity_requires_exact_visual_crop_complement(self) -> None:
        normalization = {
            "reason": "editable_table_extracted_from_containing_image",
            "table_block_id": "table",
            "image_block_id": "image",
            "masked_rect": [0.3, 0.4, 0.7, 0.6],
            "crop_fragment_count": 4,
        }
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="docjob_visual_crop",
                source_file_id="file_visual_crop",
                document_language="en",
                source_block_count=2,
                source_type_counts={"image": 1, "table": 1},
            ),
            assets=[DocumentIRAsset(id="asset_image", kind="image", source_path="drawing.png")],
            blocks=[
                DocumentIRBlock(
                    id="table",
                    type="table",
                    order=0,
                    html="<table><tr><td>DIM</td></tr></table>",
                    layout=DocumentIRBlockLayout(role="body"),
                    metadata={
                        "source_type": "table",
                        "semantic_decision_reason": "source_type_preserved",
                        "visual_overlap_group_id": "visual_overlap:table:image",
                        "visual_overlap_normalization": normalization,
                    },
                ),
                DocumentIRBlock(
                    id="image",
                    type="image",
                    order=1,
                    asset_ref="asset_image",
                    layout=DocumentIRBlockLayout(role="body"),
                    metadata={
                        "source_type": "image",
                        "semantic_decision_reason": "source_type_preserved",
                        "visual_overlap_group_id": "visual_overlap:table:image",
                        "visual_overlap_normalization": normalization,
                        "visual_crop_rects": [
                            [0.0, 0.0, 0.3, 1.0],
                            [0.3, 0.0, 0.7, 0.4],
                            [0.7, 0.0, 1.0, 1.0],
                            [0.3, 0.6, 0.7, 1.0],
                        ],
                    },
                ),
            ],
        )

        self.assertEqual(build_source_integrity(document)["blocking_quality_flags"], [])
        document.blocks[1].metadata["visual_crop_rects"][0] = [0.0, 0.4, 0.3, 0.6]

        self.assertIn(
            "source_ir_integrity:visual_crop_coverage_mismatch:image",
            build_source_integrity(document)["blocking_quality_flags"],
        )

        document.blocks[1].metadata["visual_crop_rects"] = [
            [0.0, 0.0, 0.3, 1.0],
            [0.3, 0.0, 0.7, 0.4],
            [0.7, 0.0, 1.0, 1.0],
            [0.3, 0.6, 0.7, 1.0],
        ]
        for block in document.blocks:
            block.metadata.pop("visual_overlap_group_id")

        flags = build_source_integrity(document)["blocking_quality_flags"]
        self.assertIn("source_ir_integrity:visual_overlap_group_invalid:table", flags)
        self.assertIn("source_ir_integrity:visual_overlap_group_invalid:image", flags)


if __name__ == "__main__":
    unittest.main()
