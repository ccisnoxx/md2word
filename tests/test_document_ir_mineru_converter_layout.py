from __future__ import annotations

# tests/test_document_ir_mineru_converter_layout.py: 覆盖 MinerU -> DocumentIR v2 layout signal 提取。

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.mineru_content import find_final_promotional_page
from app.services.document_ir import MinerUToDocumentIRService


class MinerUToDocumentIRLayoutTests(unittest.TestCase):
    def test_shared_final_promotional_page_rule_is_conservative(self) -> None:
        image = {"type": "image", "img_path": "images/qr.png", "bbox": [100, 100, 300, 300], "page_idx": 2}
        positive = [
            {"type": "text", "text": "可使用微信扫码进入芯片助手小程序", "page_idx": 2},
            image,
        ]
        self.assertEqual(find_final_promotional_page(positive), 2)

        cases = {
            "单个关键词": [{"type": "text", "text": "微信公众号", "page_idx": 2}, image],
            "无资产": [{"type": "text", "text": "微信扫码进入小程序", "page_idx": 2}],
            "方形技术图": [{"type": "text", "text": "产品封装图", "page_idx": 2}, image],
            "免责声明": [
                {"type": "text", "text": "微信扫码进入小程序" + "本资料仅供技术开发人员参考。" * 20, "page_idx": 2},
                image,
            ],
            "版本表": [
                {"type": "text", "text": "微信扫码进入小程序", "page_idx": 2},
                {"type": "table", "table_body": "<table><tr><td>V1</td></tr></table>", "page_idx": 2},
                image,
            ],
            "编号标题": [
                {"type": "title", "text": "7 Version update 微信扫码进入小程序", "page_idx": 2},
                image,
            ],
            "编号题注": [
                {"type": "text", "text": "微信扫码进入小程序", "page_idx": 2},
                {**image, "image_caption": ["图 8 技术框图"]},
            ],
            "公式": [
                {"type": "text", "text": "微信扫码进入小程序", "page_idx": 2},
                {"type": "equation", "latex": "V=IR", "page_idx": 2},
                image,
            ],
            "列表": [
                {"type": "text", "text": "微信扫码进入小程序", "page_idx": 2},
                {"type": "list", "list_items": ["技术参数"], "page_idx": 2},
                image,
            ],
            "非最后页": [
                {"type": "text", "text": "微信扫码进入小程序", "page_idx": 1},
                {**image, "page_idx": 1},
                {"type": "text", "text": "最后一页技术正文", "page_idx": 2},
            ],
        }
        for label, blocks in cases.items():
            with self.subTest(label=label):
                self.assertIsNone(find_final_promotional_page(blocks))

    def test_convert_zip_removes_final_promotional_page_blocks_pages_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {"type": "text", "text": "正文", "bbox": [72, 80, 200, 100], "page_idx": 0},
                    {
                        "type": "image",
                        "img_path": "images/chart.png",
                        "image_caption": ["图 1 正文图片"],
                        "bbox": [72, 120, 300, 300],
                        "page_idx": 0,
                    },
                    {"type": "text", "text": "可使用微信扫码进入芯片助手小程序", "bbox": [72, 80, 300, 120], "page_idx": 1},
                    {
                        "type": "image",
                        "img_path": "images/qr.png",
                        "bbox": [150, 180, 350, 380],
                        "page_idx": 1,
                    },
                    {"type": "footer", "text": "www.example.com", "bbox": [72, 740, 300, 760], "page_idx": 1},
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [612, 792]},
                        {"page_idx": 1, "page_size": [612, 792]},
                    ]
                },
                images={"images/chart.png": b"body-image", "images/qr.png": b"qr-image"},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_promo",
                source_file_id="file_promo",
                document_language="zh",
            )

        self.assertEqual([page.index for page in result.document.pages], [0])
        self.assertEqual({block.page_index for block in result.document.blocks}, {0})
        self.assertEqual([asset.source_path for asset in result.document.assets], ["images/chart.png"])
        self.assertEqual([asset.source_path for asset in result.image_assets], ["images/chart.png"])
        self.assertIn("final_promotional_page_filtered:1", result.document.quality_flags)

    def test_convert_zip_uses_physical_final_page_from_layout_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {"type": "text", "text": "微信扫码进入小程序", "page_idx": 1},
                    {"type": "image", "img_path": "images/qr.png", "page_idx": 1},
                ],
                layout={"pdf_info": [{"page_idx": index, "page_size": [612, 792]} for index in range(3)]},
                images={"images/qr.png": b"qr-image"},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_non_final_promo",
                source_file_id="file_non_final_promo",
                document_language="zh",
            )

        self.assertEqual([page.index for page in result.document.pages], [0, 1, 2])
        self.assertNotIn("final_promotional_page_filtered:1", result.document.quality_flags)
        self.assertEqual(len(result.image_assets), 1)

    def test_convert_zip_filters_final_promotional_page_without_layout_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {"type": "text", "text": "微信扫码进入小程序", "page_idx": 3},
                    {"type": "image", "img_path": "images/qr.png", "page_idx": 3},
                ],
                layout=None,
                images={"images/qr.png": b"qr-image"},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_promo_without_layout",
                source_file_id="file_promo_without_layout",
                document_language="zh",
            )

        self.assertEqual(result.document.pages, [])
        self.assertEqual(result.document.blocks, [])
        self.assertEqual(result.document.assets, [])
        self.assertEqual(result.image_assets, [])
        self.assertIn("final_promotional_page_filtered:3", result.document.quality_flags)

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

    def test_convert_zip_merges_real_mineru_empty_table_continuations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "table_body": "<table><tr><td>Part</td></tr></table>",
                        "bbox": [72, 120, 540, 300],
                        "page_idx": 0,
                    },
                    {
                        "type": "table",
                        "img_path": "",
                        "html": "",
                        "bbox": [72, 50, 540, 250],
                        "page_idx": 1,
                    },
                    {
                        "type": "table",
                        "html": "",
                        "image_source": {"path": "images/"},
                        "bbox": [72, 40, 540, 280],
                        "page_idx": 2,
                    },
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [612, 792]},
                        {"page_idx": 1, "page_size": [612, 792]},
                        {"page_idx": 2, "page_size": [612, 792]},
                    ]
                },
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_real_continuation",
                source_file_id="file_real_continuation",
                document_language="en",
            )

        self.assertEqual(len(result.document.blocks), 1)
        self.assertEqual(result.document.blocks[0].type, "table")
        self.assertEqual(result.document.blocks[0].layout.continuation_heights, [200.0, 240.0])

    def test_convert_zip_reassociates_only_strict_numbered_image_groups(self) -> None:
        blocks = [
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": [], "bbox": [10, 10, 90, 90], "page_idx": 0},
            {
                "type": "chart",
                "img_path": "images/chart.png",
                "chart_caption": ["图 3 响应", "图 5 响应"],
                "bbox": [110, 10, 190, 90],
                "page_idx": 0,
            },
            {
                "type": "chart",
                "img_path": "images/chart.png",
                "chart_caption": ["图 4 响应"],
                "bbox": [10, 110, 90, 190],
                "page_idx": 0,
            },
            {
                "type": "chart",
                "img_path": "images/chart.png",
                "chart_caption": ["图 6 响应"],
                "bbox": [110, 110, 190, 190],
                "page_idx": 0,
            },
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": ["图 7 正确"], "bbox": [10, 10, 90, 90], "page_idx": 1},
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": ["图 8 正确"], "bbox": [110, 10, 190, 90], "page_idx": 1},
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": [], "bbox": [10, 10, 90, 90], "page_idx": 2},
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": ["图 9 数量不足"], "bbox": [110, 10, 190, 90], "page_idx": 2},
            {"type": "chart", "img_path": "images/chart.png", "chart_caption": [], "bbox": [10, 10, 90, 90], "page_idx": 3},
            {
                "type": "chart",
                "img_path": "images/chart.png",
                "chart_caption": ["图 11 不连续", "图 13 不连续"],
                "bbox": [110, 10, 190, 90],
                "page_idx": 3,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": index, "page_size": [200, 300]} for index in range(4)]},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_captions",
                source_file_id="file_captions",
                document_language="zh",
            )

        captions_by_page = {
            page_index: [block.captions for block in result.document.blocks if block.page_index == page_index]
            for page_index in range(4)
        }
        self.assertEqual(captions_by_page[0], [["图 3 响应"], ["图 4 响应"], ["图 5 响应"], ["图 6 响应"]])
        self.assertEqual(captions_by_page[1], [["图 7 正确"], ["图 8 正确"]])
        self.assertEqual(captions_by_page[2], [[], ["图 9 数量不足"]])
        self.assertEqual(captions_by_page[3], [[], ["图 11 不连续", "图 13 不连续"]])

    def test_convert_zip_demotes_table_condition_caption_to_context_paragraph(self) -> None:
        condition = (
            "at TA = +25°C, VS = ±5 V to ±15 V, VCM = VOUT = VS / 2, "
            "and RL = 10 kΩ connected to VS / 2 (unless otherwise noted)"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "table_caption": [condition],
                        "table_body": "<table><tr><th>PARAMETER</th><th>VALUE</th></tr></table>",
                        "bbox": [40, 120, 572, 260],
                        "page_idx": 0,
                    }
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_context",
                source_file_id="file_context",
                document_language="en",
            )

        document = result.document
        self.assertEqual([block.type for block in document.blocks], ["paragraph", "table"])
        self.assertEqual(document.blocks[0].id, "block_0001_context_0001")
        self.assertEqual(document.blocks[0].text, condition)
        self.assertEqual(document.blocks[0].metadata["annotation_role"], "table_context")
        self.assertEqual(document.blocks[0].metadata["source_block_id"], "block_0001")
        self.assertEqual(document.blocks[1].id, "block_0001")
        self.assertEqual(document.blocks[1].captions, [])
        self.assertIsNone(document.blocks[1].text)
        self.assertIn("layout_table_context_binding:block_0001", document.quality_flags)
        self.assertNotIn("layout_caption_binding:block_0001", document.quality_flags)
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

    def _write_zip(
        self,
        zip_path: Path,
        *,
        blocks: list[Any],
        layout: dict | None,
        images: dict[str, bytes] | None = None,
    ) -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("content_list.json", json.dumps(blocks, ensure_ascii=False))
            if layout is not None:
                archive.writestr("layout.json", json.dumps(layout, ensure_ascii=False))
            for image_path, content in (images or {"images/chart.png": b"fake-image"}).items():
                archive.writestr(image_path, content)


if __name__ == "__main__":
    unittest.main()
