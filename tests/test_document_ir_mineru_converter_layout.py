from __future__ import annotations

# tests/test_document_ir_mineru_converter_layout.py: 覆盖 MinerU -> DocumentIR v2 layout signal 提取。

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from app.services.document_ir import MinerUToDocumentIRService


class MinerUToDocumentIRLayoutTests(unittest.TestCase):
    def test_convert_zip_outputs_v2_pages_layout_roles_and_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {"type": "title", "text": "1 Features", "text_level": 1, "bbox": [72, 80, 180, 100], "page_idx": 0},
                    {"type": "list", "list_items": ["Low noise", "High slew rate"], "bbox": [72, 120, 260, 180], "page_idx": 0},
                    {
                        "type": "chart",
                        "img_path": "images/chart.png",
                        "chart_caption": ["Noise Density"],
                        "chart_footnote": ["Typical values."],
                        "bbox": [72, 200, 360, 320],
                        "page_idx": 0,
                    },
                    {
                        "type": "table",
                        "table_caption": ["Device Information"],
                        "table_footnote": ["All packages are listed in the addendum."],
                        "table_body": "<table><tr><td>Part</td></tr></table>",
                        "bbox": [72, 340, 540, 430],
                        "page_idx": 0,
                        "continuation_heights": [120],
                    },
                    {"type": "header", "text": "Header text", "bbox": [72, 20, 200, 40], "page_idx": 0},
                    {"type": "footer", "text": "Footer text", "bbox": [72, 740, 300, 760], "page_idx": 0},
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_layout",
                source_file_id="file_layout",
                document_language="en",
            )

        document = result.document
        self.assertEqual(document.schema_version, "document-ir/v2")
        self.assertEqual(document.pages[0].width, 612)
        self.assertEqual(document.pages[0].height, 792)
        self.assertEqual(document.pages[0].metadata["page_size_source"], "layout.json")
        self.assertEqual(document.pages[0].metadata["orientation"], "portrait")
        self.assertEqual(document.blocks[0].layout.bbox, (72.0, 80.0, 180.0, 100.0))
        self.assertEqual(document.blocks[0].layout.column_hint, "left")
        self.assertEqual(document.blocks[1].list_items, ["Low noise", "High slew rate"])
        self.assertEqual(document.blocks[1].layout.column_hint, "left")
        self.assertEqual(document.blocks[2].type, "image")
        self.assertEqual(document.blocks[2].text, "Noise Density")
        self.assertEqual(document.blocks[2].layout.column_hint, "left")
        self.assertEqual(document.blocks[2].captions, ["Noise Density"])
        self.assertEqual(document.blocks[2].footnotes, ["Typical values."])
        self.assertEqual(document.blocks[2].metadata["layout_role_reason"], "column_hint=left;bbox_width=288.00;page_width=612.00")
        self.assertEqual(document.blocks[3].captions, ["Device Information"])
        self.assertEqual(document.blocks[3].footnotes, ["All packages are listed in the addendum."])
        self.assertEqual(document.blocks[3].layout.continuation_heights, [120.0])
        self.assertEqual(document.blocks[3].layout.column_hint, "wide")
        self.assertEqual(document.blocks[3].metadata["layout_role_reason"], "column_hint=wide;bbox_width=468.00;page_width=612.00")
        self.assertEqual(document.blocks[4].layout.role, "page_header")
        self.assertEqual(document.blocks[5].layout.role, "page_footer")
        self.assertNotIn("unsupported_block_type:header", document.quality_flags)
        self.assertIn("table_continuation:block_0004", document.quality_flags)
        self.assertIn("layout_wide_table:block_0004", document.quality_flags)
        self.assertIn("layout_caption_binding:block_0003", document.quality_flags)
        self.assertIn("layout_footnote_binding:block_0004", document.quality_flags)
        self.assertEqual(len(result.image_assets), 1)

    def test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "table_caption": ["Wide table"],
                        "table_body": "<table><tr><td>Part</td></tr></table>",
                        "bbox": [72, 120, 720, 240],
                        "page_idx": 0,
                    },
                    {"type": "table_placeholder", "bbox": [72, 50, 720, 250], "page_idx": 1},
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [792, 612]},
                        {"page_idx": 1, "page_size": [792, 612]},
                    ]
                },
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_continuation",
                source_file_id="file_continuation",
                document_language="en",
            )

        document = result.document
        self.assertEqual([page.metadata["orientation"] for page in document.pages], ["landscape", "landscape"])
        self.assertEqual(len(document.blocks), 1)
        self.assertEqual(document.blocks[0].type, "table")
        self.assertEqual(document.blocks[0].layout.column_hint, "wide")
        self.assertEqual(document.blocks[0].layout.continuation_heights, [200.0])
        self.assertIn("table_continuation:block_0001", document.quality_flags)
        self.assertIn("layout_wide_table:block_0001", document.quality_flags)

    def test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    [
                        {
                            "type": "text",
                            "text": "1 Features........................ 1\n2 Specifications.................. 2\n3 Pins............................ 3",
                            "bbox": [72, 80, 280, 160],
                        },
                        {
                            "type": "equation_interline",
                            "content": [{"type": "text", "content": r"V_{OS}"}],
                            "bbox": [72, 180, 180, 210],
                        },
                    ],
                    [
                        {
                            "type": "table",
                            "content": [{"html": "<table><tr><td>VOS</td></tr></table>"}],
                            "table_caption": [[{"type": "text", "content": "Electrical Characteristics"}]],
                            "table_footnote": [
                                {"type": "text", "content": "Note:"},
                                {"type": "equation_inline", "content": r"V_{OS}"},
                            ],
                            "bbox": [72, 80, 540, 260],
                        },
                        {
                            "type": "image",
                            "content": [{"img_path": "images/chart.png"}],
                            "caption": [{"type": "text", "content": "Figure 1. Noise"}],
                            "bbox": [72, 300, 360, 480],
                        },
                    ],
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [612, 792]},
                        {"page_idx": 1, "page_size": [612, 792]},
                    ]
                },
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_nested",
                source_file_id="file_nested",
                document_language="en",
            )

        document = result.document
        self.assertEqual([page.index for page in document.pages], [0, 1])
        self.assertEqual([block.page_index for block in document.blocks], [0, 0, 1, 1])
        self.assertEqual(document.blocks[0].type, "list")
        self.assertEqual(
            document.blocks[0].list_items,
            ["1 Features........................ 1", "2 Specifications.................. 2", "3 Pins............................ 3"],
        )
        self.assertEqual(document.blocks[1].type, "formula")
        self.assertEqual(document.blocks[1].latex, "V_{OS}")
        self.assertEqual(document.blocks[2].type, "table")
        self.assertEqual(document.blocks[2].html, "<table><tr><td>VOS</td></tr></table>")
        self.assertEqual(document.blocks[2].captions, ["Electrical Characteristics"])
        self.assertEqual(document.blocks[2].footnotes, ["Note: V<sub>OS</sub>"])
        self.assertEqual(document.blocks[2].layout.column_hint, "wide")
        self.assertEqual(document.blocks[3].type, "image")
        self.assertEqual(document.blocks[3].captions, ["Figure 1. Noise"])
        self.assertEqual(result.image_assets[0].source_path, "images/chart.png")

    def test_convert_zip_records_missing_layout_source_and_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(zip_path, blocks=[{"type": "text", "text": "Body", "page_idx": 0}], layout=None)

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_missing_layout",
                source_file_id="file_missing_layout",
                document_language="en",
            )

        self.assertEqual(result.document.schema_version, "document-ir/v2")
        self.assertEqual(result.document.pages[0].index, 0)
        self.assertIn("middle_json_missing", result.document.quality_flags)
        self.assertIn("layout_bbox_missing:block_0001", result.document.quality_flags)

    def _write_zip(self, zip_path: Path, *, blocks: list[Any], layout: dict | None) -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("content_list.json", json.dumps(blocks, ensure_ascii=False))
            if layout is not None:
                archive.writestr("layout.json", json.dumps(layout, ensure_ascii=False))
            archive.writestr("images/chart.png", b"fake-image")


if __name__ == "__main__":
    unittest.main()
