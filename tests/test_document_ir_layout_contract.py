from __future__ import annotations

# tests/test_document_ir_layout_contract.py: 覆盖 DocumentIR v1/v2 布局合同兼容性。

import unittest

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

    def test_v2_payload_round_trips_page_and_block_layout(self) -> None:
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="docjob_v2",
                source_file_id="file_v2",
                document_language="en",
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
        self.assertEqual(decoded.pages[0].metadata["orientation"], "portrait")
        self.assertEqual(decoded.blocks[0].layout.bbox, (72.0, 120.0, 540.0, 240.0))
        self.assertEqual(decoded.blocks[0].layout.continuation_heights, [100.0])
        self.assertEqual(decoded.blocks[0].layout.column_hint, "wide")
        self.assertEqual(decoded.blocks[0].captions, ["Table 1. Electrical Characteristics"])
        self.assertEqual(decoded.blocks[0].footnotes, ["All values are typical."])
        self.assertEqual(decoded.blocks[0].metadata["layout_role_reason"], "column_hint=wide;source=bbox")
        self.assertIn("layout_wide_table:block_0001", decoded.quality_flags)


if __name__ == "__main__":
    unittest.main()
