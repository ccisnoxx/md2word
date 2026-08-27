from __future__ import annotations

# tests/test_document_ir_mineru_converter_layout.py: 覆盖 MinerU -> DocumentIR v2 layout signal 提取。

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docx import Document

from app.conversion.docx_rules.mineru_content import find_final_promotional_page
from app.conversion.docx_rules.text_semantics import parse_decimal_list_marker
from app.services.document_ir.integrity import DocumentIntegrityError, build_source_integrity
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.evidence import build_renderer_evidence
from app.services.renderer.layout_plan import build_layout_plan


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MinerUToDocumentIRLayoutTests(unittest.TestCase):
    def test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            both_path = temp_path / "both.zip"
            self._write_zip(
                both_path,
                blocks=[{"type": "text", "text": "legacy content", "page_idx": 0}],
                v2_blocks=[
                    [
                        {
                            "type": "paragraph",
                            "content": {"paragraph_content": [{"type": "text", "content": "v2 content"}]},
                            "bbox": [10, 10, 100, 30],
                        }
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [200, 300]}]},
            )
            legacy_path = temp_path / "legacy.zip"
            self._write_zip(
                legacy_path,
                blocks=[{"type": "text", "text": "legacy content", "page_idx": 0}],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [200, 300]}]},
            )

            both = MinerUToDocumentIRService().convert_zip(
                both_path,
                job_id="docjob_v2_priority",
                source_file_id="file_v2_priority",
                document_language="en",
            )
            legacy = MinerUToDocumentIRService().convert_zip(
                legacy_path,
                job_id="docjob_legacy_fallback",
                source_file_id="file_legacy_fallback",
                document_language="en",
            )

        self.assertEqual([block.text for block in both.document.blocks], ["v2 content"])
        self.assertEqual([block.text for block in legacy.document.blocks], ["legacy content"])

    def test_convert_zip_binds_layout_and_assets_to_content_list_result_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "selected/content_list_v2.json",
                    json.dumps(
                        [
                            {
                                "type": "image",
                                "img_path": "shared.png",
                                "bbox": [72, 120, 300, 300],
                                "page_idx": 0,
                            }
                        ]
                    ),
                )
                archive.writestr(
                    "selected/layout.json",
                    json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]}),
                )
                archive.writestr("selected/images/shared.png", b"selected-image")
                archive.writestr(
                    "outside/layout.json",
                    json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [1000, 1000]}]}),
                )
                archive.writestr("outside/images/shared.png", b"outside-image")

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_result_root",
                source_file_id="file_result_root",
                document_language="en",
            )

        self.assertEqual((result.document.pages[0].width, result.document.pages[0].height), (612, 792))
        self.assertEqual(result.image_assets[0].source_path, "images/shared.png")
        self.assertEqual(result.image_assets[0].content, b"selected-image")

    def test_convert_zip_rejects_multiple_mineru_result_roots(self) -> None:
        cases = {
            "多个结果根": ["first/content_list_v2.json", "second/content_list_v2.json"],
            "同根多个 v2": ["result/first_content_list_v2.json", "result/second_content_list_v2.json"],
            "同根多个 legacy": ["result/first_content_list.json", "result/second_content_list.json"],
        }
        for label, content_paths in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                with zipfile.ZipFile(zip_path, "w") as archive:
                    for content_path in content_paths:
                        archive.writestr(content_path, "[]")

                with self.assertRaisesRegex(ValueError, "无法唯一"):
                    MinerUToDocumentIRService().convert_zip(
                        zip_path,
                        job_id="docjob_multiple_roots",
                        source_file_id="file_multiple_roots",
                        document_language="en",
                    )

    def test_convert_zip_rejects_cross_root_or_ambiguous_basename_assets(self) -> None:
        cases = {
            "跨根资产": {"outside/images/shared.png": b"outside-image"},
            "同根 basename 重名": {
                "selected/first/shared.png": b"first-image",
                "selected/second/shared.png": b"second-image",
            },
        }
        for label, images in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                with zipfile.ZipFile(zip_path, "w") as archive:
                    archive.writestr(
                        "selected/content_list_v2.json",
                        json.dumps(
                            [
                                {
                                    "type": "image",
                                    "img_path": "shared.png",
                                    "bbox": [72, 120, 300, 300],
                                    "page_idx": 0,
                                }
                            ]
                        ),
                    )
                    for image_path, content in images.items():
                        archive.writestr(image_path, content)

                with self.assertRaisesRegex(DocumentIntegrityError, "payload_missing:image"):
                    MinerUToDocumentIRService().convert_zip(
                        zip_path,
                        job_id="docjob_invalid_asset_binding",
                        source_file_id="file_invalid_asset_binding",
                        document_language="en",
                    )

    def test_convert_zip_prefers_exact_asset_path_and_limits_basename_fallback_to_one_match(self) -> None:
        positive_cases = {
            "精确相对路径优先": (
                "images/shared.png",
                {
                    "selected/images/shared.png": b"exact-image",
                    "selected/other/shared.png": b"other-image",
                },
                b"exact-image",
            ),
            "唯一 basename fallback": (
                "shared.png",
                {"selected/images/shared.png": b"unique-image"},
                b"unique-image",
            ),
        }
        for label, (raw_path, images, expected_content) in positive_cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                with zipfile.ZipFile(zip_path, "w") as archive:
                    archive.writestr(
                        "selected/content_list_v2.json",
                        json.dumps(
                            [
                                {
                                    "type": "image",
                                    "img_path": raw_path,
                                    "bbox": [72, 120, 300, 300],
                                    "page_idx": 0,
                                }
                            ]
                        ),
                    )
                    for image_path, content in images.items():
                        archive.writestr(image_path, content)

                result = MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_asset_path_contract",
                    source_file_id="file_asset_path_contract",
                    document_language="en",
                )

            self.assertEqual(result.image_assets[0].content, expected_content)

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "selected/content_list_v2.json",
                    json.dumps(
                        [
                            {
                                "type": "image",
                                "img_path": "../outside/shared.png",
                                "bbox": [72, 120, 300, 300],
                                "page_idx": 0,
                            }
                        ]
                    ),
                )
                archive.writestr("outside/shared.png", b"outside-image")

            with self.assertRaisesRegex(DocumentIntegrityError, "payload_missing:image"):
                MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_asset_path_escape",
                    source_file_id="file_asset_path_escape",
                    document_language="en",
                )

    def test_convert_zip_scales_physical_page_size_uniformly_to_cover_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[{"type": "text", "text": "Portrait", "bbox": [0, 0, 942, 879], "page_idx": 0}],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [595, 841]}]},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_scaled_portrait",
                source_file_id="file_scaled_portrait",
                document_language="en",
            )

        page = result.document.pages[0]
        self.assertEqual(page.width, 942)
        self.assertAlmostEqual(page.height, 841 * (942 / 595))
        self.assertAlmostEqual(page.width / page.height, 595 / 841)
        self.assertGreaterEqual(page.height, 879)
        self.assertEqual(page.metadata["orientation"], "portrait")

    def test_convert_zip_structures_v2_multiline_lists_and_preserves_math_sources(self) -> None:
        fraction = r"\frac {\left(V _ {I N} - V _ {S}\right)}{R _ {S} + 5 0 0 \Omega} \leq 5 \mathrm{mA}"
        total_delay = r"\mathrm{总} t _ {s} = \sqrt {\left(t _ {s , C M 7 5 0 1}\right) ^ {2}}"
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "paragraph",
                            "content": {
                                "paragraph_content": [
                                    {"type": "text", "content": "- Low offset "},
                                    {"type": "equation_inline", "content": r"12\mu \mathrm{V}"},
                                    {"type": "text", "content": "\n- Low noise\n- Stable output"},
                                ]
                            },
                            "bbox": [10, 20, 180, 90],
                        },
                        {
                            "type": "paragraph",
                            "content": {
                                "paragraph_content": [
                                    {"type": "text", "content": "■ Sensors\nThermocouple\nRTD"}
                                ]
                            },
                            "bbox": [10, 100, 180, 150],
                        },
                        {
                            "type": "paragraph",
                            "content": {"paragraph_content": [{"type": "text", "content": "ordinary\nbody"}]},
                            "bbox": [10, 160, 180, 190],
                        },
                        {
                            "type": "paragraph",
                            "content": {
                                "paragraph_content": [
                                    {"type": "text", "content": "Input "},
                                    {"type": "equation_inline", "content": r"V _ {I N}"},
                                    {"type": "text", "content": " stays visible"},
                                ]
                            },
                            "bbox": [10, 200, 180, 230],
                        },
                        {
                            "type": "list",
                            "content": {
                                "list_items": [
                                    {
                                        "item_content": [
                                            {"type": "text", "content": "Limit "},
                                            {"type": "equation_inline", "content": r"I _ {O U T}"},
                                        ]
                                    }
                                ]
                            },
                            "bbox": [10, 232, 180, 238],
                        },
                        {
                            "type": "equation_interline",
                            "content": {"math_content": fraction, "math_type": "latex", "image_source": {"path": "images/a.png"}},
                            "bbox": [10, 240, 180, 270],
                        },
                        {
                            "type": "equation_interline",
                            "content": {"math_content": total_delay, "math_type": "latex"},
                            "bbox": [10, 280, 180, 310],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [200, 400]}]},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_v2_rich_text",
                source_file_id="file_v2_rich_text",
                document_language="en",
            )

        blocks = result.document.blocks
        self.assertEqual(blocks[0].type, "list")
        self.assertEqual(blocks[0].list_items, [r"- Low offset $12\mu \mathrm{V}$", "- Low noise", "- Stable output"])
        self.assertEqual(blocks[1].list_items, ["■ Sensors\nThermocouple\nRTD"])
        self.assertEqual(blocks[2].type, "paragraph")
        self.assertEqual(blocks[2].text, "ordinary body")
        self.assertEqual(blocks[3].text, r"Input $V _ {I N}$ stays visible")
        self.assertEqual(blocks[4].list_items, [r"Limit $I _ {O U T}$"])
        self.assertEqual(blocks[5].latex, fraction)
        self.assertEqual(blocks[6].latex, total_delay)

    def test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/chart.png"},
                                "content": "",
                                "chart_caption": [
                                    {"type": "text", "content": "图 1 输出 "},
                                    {"type": "equation_inline", "content": r"V _ {O U T}"},
                                ],
                                "chart_footnote": [{"type": "text", "content": "测试条件：25°C"}],
                            },
                            "bbox": [10, 20, 180, 160],
                        }
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [200, 300]}]},
                images={"images/chart.png": b"chart-bytes"},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_nested_chart",
                source_file_id="file_nested_chart",
                document_language="zh",
            )

        block = result.document.blocks[0]
        self.assertEqual(block.type, "image")
        self.assertEqual(block.metadata["source_type"], "chart")
        self.assertEqual(block.asset_ref, result.document.assets[0].id)
        self.assertEqual(result.image_assets[0].content, b"chart-bytes")
        self.assertEqual(result.document.assets[0].mime_type, "image/png")
        self.assertEqual(
            result.document.assets[0].checksum_sha256,
            f"sha256:{hashlib.sha256(b'chart-bytes').hexdigest()}",
        )
        self.assertEqual(block.captions, [r"图 1 输出 $V _ {O U T}$"])
        self.assertEqual(block.footnotes, ["测试条件：25°C"])
        self.assertEqual(result.document.metadata.source_block_count, 1)
        self.assertEqual(result.document.metadata.source_type_counts, {"chart": 1})
        self.assertNotIn("unsupported_block_type:chart", result.document.quality_flags)

    def test_convert_zip_preserves_multiple_logical_caption_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/strings.png"},
                                "chart_caption": ["图 1 第一条", "图 2 第二条"],
                            },
                            "bbox": [10, 20, 180, 160],
                        }
                    ],
                    [
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/groups.png"},
                                "chart_caption": [
                                    [{"type": "text", "content": "图 3 第三条"}],
                                    [
                                        {"type": "text", "content": "图 4 输出 "},
                                        {"type": "equation_inline", "content": r"V _ {O U T}"},
                                    ],
                                ],
                            },
                            "bbox": [10, 20, 180, 160],
                        }
                    ],
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": 0, "page_size": [200, 300]},
                        {"page_idx": 1, "page_size": [200, 300]},
                    ]
                },
                images={"images/strings.png": MINIMAL_PNG_BYTES, "images/groups.png": MINIMAL_PNG_BYTES},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_caption_groups",
                source_file_id="file_caption_groups",
                document_language="zh",
            )

        self.assertEqual(result.document.blocks[0].captions, ["图 1 第一条", "图 2 第二条"])
        self.assertEqual(result.document.blocks[1].captions, ["图 3 第三条", r"图 4 输出 $V _ {O U T}$"])

    def test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/left.png"},
                                "chart_caption": [
                                    {"type": "text", "content": "图 33 通道隔离度 (  "},
                                    {"type": "equation_inline", "content": r"\pm"},
                                    {"type": "text", "content": " 18V)"},
                                ],
                            },
                            "bbox": [10, 80, 170, 220],
                        },
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/right.png"},
                                "chart_caption": [
                                    {"type": "text", "content": "图 34 输出摆幅 (  "},
                                    {"type": "equation_inline", "content": r"\pm"},
                                    {"type": "text", "content": " 15V)"},
                                ],
                            },
                            "bbox": [220, 82, 380, 220],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [400, 600]}]},
                images={"images/left.png": MINIMAL_PNG_BYTES, "images/right.png": MINIMAL_PNG_BYTES},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_rich_caption_pair",
                source_file_id="file_rich_caption_pair",
                document_language="zh",
            )
            image_bytes = {asset.asset_id: asset.content for asset in result.image_assets}
            content = DocumentIRWordRenderer().render_to_bytes(
                result.document,
                template_path=None,
                config_path=None,
                image_loader=lambda asset: image_bytes.get(asset.id),
            )

        self.assertEqual(result.document.blocks[0].captions, [r"图 33 通道隔离度 ( $\pm$ 18V)"])
        rendered = Document(io.BytesIO(content))
        self.assertNotIn("±", [paragraph.text.strip() for paragraph in rendered.paragraphs])
        self.assertNotIn("18V)", [paragraph.text.strip() for paragraph in rendered.paragraphs])
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            document_xml = docx_zip.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        math_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
        paragraph_texts = [
            "".join(
                node.text or ""
                for node in paragraph.iter()
                if node.tag in {f"{word_ns}t", f"{math_ns}t"}
            )
            for paragraph in root.iter(f"{word_ns}p")
        ]
        figure_33_paragraph = next(text for text in paragraph_texts if "通道隔离度" in text)
        self.assertIn("±", figure_33_paragraph)
        self.assertIn("18V)", figure_33_paragraph)
        xml = document_xml.decode("utf-8")
        self.assertNotIn('<w:br w:type="column"', xml)
        self.assertNotIn("<w:tabs>", xml)
        self.assertEqual(xml.count('w:val="md2word:paired_visual_row"'), 1)
        tables = list(root.iter(f"{word_ns}tbl"))
        self.assertEqual(len(tables), 1)
        cells = list(tables[0].iter(f"{word_ns}tc"))
        self.assertEqual(len(cells), 2)
        cell_texts = [
            "".join(
                node.text or ""
                for node in cell.iter()
                if node.tag in {f"{word_ns}t", f"{math_ns}t"}
            )
            for cell in cells
        ]
        self.assertIn("图 33 通道隔离度", cell_texts[0])
        self.assertIn("±", cell_texts[0])
        self.assertIn("18V)", cell_texts[0])
        self.assertNotIn("图 34", cell_texts[0])
        self.assertIn("图 34 输出摆幅", cell_texts[1])
        self.assertIn("±", cell_texts[1])
        self.assertIn("15V)", cell_texts[1])
        self.assertNotIn("图 33", cell_texts[1])
        borders = tables[0].find(f"./{word_ns}tblPr/{word_ns}tblBorders")
        self.assertIsNotNone(borders)
        assert borders is not None
        self.assertEqual(len(borders), 6)
        self.assertTrue(all(border.get(f"{word_ns}val") == "nil" for border in borders))
        self.assertIn(" SEQ 图 \\r 33 \\* ARABIC ", xml)
        self.assertIn(" SEQ 图 \\r 34 \\* ARABIC ", xml)

    def test_convert_zip_fails_closed_when_declared_formula_payload_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "equation_interline",
                            "content": {"math_type": "latex", "image_source": {"path": "images/missing.png"}},
                            "bbox": [10, 20, 180, 60],
                        }
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [200, 300]}]},
            )

            with self.assertRaisesRegex(DocumentIntegrityError, "payload_missing:equation_interline"):
                MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_missing_formula",
                    source_file_id="file_missing_formula",
                    document_language="zh",
                )

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
        self.assertEqual(document.blocks[4].layout.role, "body")
        self.assertEqual(document.blocks[5].layout.role, "page_footer")
        self.assertEqual(
            document.blocks[4].metadata["semantic_decision_reason"],
            "ambiguous_margin_decoration_preserved_as_body",
        )
        self.assertIn("semantic_decoration_ambiguous:4", document.quality_flags)
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
                        "content": {
                            "image_source": {"path": "images/"},
                            "table_caption": [],
                            "table_footnote": [],
                            "html": "",
                            "table_type": "simple_table",
                            "table_nest_level": 1,
                        },
                        "bbox": [72, 40, 540, 280],
                        "page_idx": 2,
                    },
                    {
                        "type": "table",
                        "content": {
                            "image_source": {"path": "images/"},
                            "table_caption": [],
                            "table_footnote": [],
                            "html": "<table><tr><td>保留正文</td></tr></table>",
                            "table_type": "simple_table",
                            "table_nest_level": 1,
                        },
                        "bbox": [72, 300, 540, 480],
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

        self.assertEqual(len(result.document.blocks), 2)
        self.assertEqual(result.document.blocks[0].type, "table")
        self.assertEqual(result.document.blocks[0].layout.continuation_heights, [200.0, 240.0])
        self.assertEqual(result.document.blocks[1].html, "<table><tr><td>保留正文</td></tr></table>")
        self.assertEqual(result.document.metadata.source_block_count, 2)
        self.assertEqual(result.document.metadata.source_type_counts, {"table": 2})

    def test_convert_zip_keeps_contentful_or_orphan_empty_tables_fail_closed(self) -> None:
        real_table = {
            "type": "table",
            "table_body": "<table><tr><td>Part</td></tr></table>",
            "bbox": [72, 120, 540, 300],
            "page_idx": 0,
        }

        def nested_empty_table(**content: Any) -> dict[str, Any]:
            return {
                "type": "table",
                "content": {
                    "image_source": {"path": "images/"},
                    "html": "",
                    "table_type": "simple_table",
                    **content,
                },
                "bbox": [72, 40, 540, 280],
                "page_idx": 1,
            }

        cases = {
            "明确 text": [real_table, nested_empty_table(text="表格正文仍需保留")],
            "明确 description": [real_table, nested_empty_table(description="表格说明仍需保留")],
            "明确题注": [real_table, nested_empty_table(table_caption=["表 1 参数"])],
            "明确脚注": [real_table, nested_empty_table(table_footnote=["注：典型值"])],
            "孤立空表": [{**nested_empty_table(), "page_idx": 0}],
        }
        for label, blocks in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                self._write_zip(
                    zip_path,
                    blocks=blocks,
                    layout={
                        "pdf_info": [
                            {"page_idx": page_index, "page_size": [612, 792]}
                            for page_index in range(max(block["page_idx"] for block in blocks) + 1)
                        ]
                    },
                )

                with self.assertRaisesRegex(DocumentIntegrityError, "payload_missing:table"):
                    MinerUToDocumentIRService().convert_zip(
                        zip_path,
                        job_id="docjob_ambiguous_empty_table",
                        source_file_id="file_ambiguous_empty_table",
                        document_language="zh",
                    )

    def test_convert_zip_rejects_nonempty_html_without_a_table_body(self) -> None:
        for source_type in ("table", "text"):
            with self.subTest(source_type=source_type), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                self._write_zip(
                    zip_path,
                    blocks=[
                        {
                            "type": source_type,
                            "text": "表体解析失败时保留的独立说明",
                            "table_body": "<table><tr><td>未闭合表体",
                            "table_caption": ["表 1 参数"],
                            "bbox": [72, 120, 540, 300],
                            "page_idx": 0,
                        }
                    ],
                    layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
                )

                with self.assertRaisesRegex(DocumentIntegrityError, "payload_missing:table"):
                    MinerUToDocumentIRService().convert_zip(
                        zip_path,
                        job_id="docjob_invalid_table_body",
                        source_file_id="file_invalid_table_body",
                        document_language="zh",
                    )

    def test_convert_zip_accepts_structural_table_with_empty_cells(self) -> None:
        for source_type in ("table", "text"):
            with self.subTest(source_type=source_type), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                self._write_zip(
                    zip_path,
                    blocks=[
                        {
                            "type": source_type,
                            "table_body": "<table><tr><th></th><td> </td></tr></table>",
                            "bbox": [72, 120, 540, 300],
                            "page_idx": 0,
                        }
                    ],
                    layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
                )

                result = MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_empty_table_cells",
                    source_file_id="file_empty_table_cells",
                    document_language="zh",
                )

                self.assertEqual(result.document.blocks[0].type, "table")
                self.assertEqual(result.document.blocks[0].html, "<table><tr><th></th><td> </td></tr></table>")

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

    def test_convert_zip_normalizes_sparse_visual_tables_after_strict_caption_reassociation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "table",
                            "content": {
                                "image_source": {"path": "images/figure-19.png"},
                                "table_caption": [],
                                "html": "<table><tr><td>A</td><td>B</td><td>C</td></tr></table>",
                            },
                            "bbox": [40, 80, 270, 240],
                        },
                        {
                            "type": "table",
                            "content": {
                                "image_source": {"path": "images/figure-20.png"},
                                "table_caption": [{"type": "text", "content": "图 20 第二张曲线"}],
                                "html": "<table><tr><td>D</td><td>E</td><td>F</td></tr></table>",
                            },
                            "bbox": [310, 82, 540, 242],
                        },
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/figure-21.png"},
                                "chart_caption": [
                                    {"type": "text", "content": "图 19 第一张曲线"},
                                    {"type": "text", "content": "图 21 第三张曲线"},
                                ],
                            },
                            "bbox": [120, 280, 460, 460],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={
                    "images/figure-19.png": MINIMAL_PNG_BYTES,
                    "images/figure-20.png": MINIMAL_PNG_BYTES,
                    "images/figure-21.png": MINIMAL_PNG_BYTES,
                },
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_sparse_visual_tables",
                source_file_id="file_sparse_visual_tables",
                document_language="zh",
            )

        self.assertEqual([block.type for block in result.document.blocks], ["image", "image", "image"])
        self.assertEqual(
            [block.captions for block in result.document.blocks],
            [["图 19 第一张曲线"], ["图 20 第二张曲线"], ["图 21 第三张曲线"]],
        )
        self.assertEqual(result.document.metadata.source_type_counts, {"chart": 3})
        self.assertEqual(
            [asset.source_path for asset in result.image_assets],
            ["images/figure-19.png", "images/figure-20.png", "images/figure-21.png"],
        )
        self.assertEqual(build_source_integrity(result.document)["blocking_quality_flags"], [])

    def test_convert_zip_keeps_flat_rich_caption_group_for_plain_charts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/left.png"},
                                "chart_caption": [
                                    {"type": "text", "content": "图 1 第一段"},
                                    {"type": "text", "content": "图 2 第二段"},
                                ],
                            },
                            "bbox": [40, 80, 270, 240],
                        },
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/right.png"},
                                "chart_caption": [],
                            },
                            "bbox": [310, 82, 540, 242],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={"images/left.png": MINIMAL_PNG_BYTES, "images/right.png": MINIMAL_PNG_BYTES},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_plain_rich_caption_group",
                source_file_id="file_plain_rich_caption_group",
                document_language="zh",
            )

        self.assertEqual(
            [block.captions for block in result.document.blocks],
            [["图 1 第一段图 2 第二段"], []],
        )

    def test_convert_zip_does_not_normalize_unaligned_sparse_visual_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "table",
                            "content": {
                                "image_source": {"path": "images/left.png"},
                                "table_caption": [],
                                "html": "<table><tr><td>A</td><td>B</td></tr></table>",
                            },
                            "bbox": [40, 80, 270, 240],
                        },
                        {
                            "type": "table",
                            "content": {
                                "image_source": {"path": "images/right.png"},
                                "table_caption": [{"type": "text", "content": "图 2 第二张曲线"}],
                                "html": "<table><tr><td>C</td><td>D</td></tr></table>",
                            },
                            "bbox": [310, 300, 540, 460],
                        },
                        {
                            "type": "chart",
                            "content": {
                                "image_source": {"path": "images/bottom.png"},
                                "chart_caption": [
                                    {"type": "text", "content": "图 1 第一张曲线"},
                                    {"type": "text", "content": "图 3 第三张曲线"},
                                ],
                            },
                            "bbox": [120, 500, 460, 680],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={
                    "images/left.png": MINIMAL_PNG_BYTES,
                    "images/right.png": MINIMAL_PNG_BYTES,
                    "images/bottom.png": MINIMAL_PNG_BYTES,
                },
            )

            with self.assertRaisesRegex(DocumentIntegrityError, "caption_subject_unresolved:block_0002"):
                MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_unaligned_sparse_visual_tables",
                    source_file_id="file_unaligned_sparse_visual_tables",
                    document_language="zh",
                )

    def test_convert_zip_keeps_real_single_row_table_with_image_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "content": {
                            "image_source": {"path": "images/table.png"},
                            "table_caption": ["表 1 参数"],
                            "html": "<table><tr><td>VIN</td><td>5V</td></tr></table>",
                        },
                        "bbox": [40, 80, 270, 160],
                        "page_idx": 0,
                    }
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={"images/table.png": MINIMAL_PNG_BYTES},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_real_single_row_table",
                source_file_id="file_real_single_row_table",
                document_language="zh",
            )

        self.assertEqual(result.document.blocks[0].type, "table")
        self.assertEqual(result.document.blocks[0].captions, ["表 1 参数"])
        self.assertEqual(result.document.metadata.source_type_counts, {"table": 1})

    def test_convert_zip_reassigns_figure_caption_from_table_to_unique_image_group(self) -> None:
        blocks = [
            {"type": "title", "text": "Measurement", "bbox": [40, 30, 300, 60], "page_idx": 0},
            {"type": "image", "img_path": "images/a.png", "bbox": [40, 80, 250, 180], "page_idx": 0},
            {"type": "image", "img_path": "images/b.png", "bbox": [40, 200, 250, 320], "page_idx": 0},
            {"type": "image", "img_path": "images/c.png", "bbox": [280, 190, 560, 330], "page_idx": 0},
            {"type": "paragraph", "text": "A. Test note", "bbox": [40, 340, 300, 360], "page_idx": 0},
            {
                "type": "table",
                "table_caption": ["Figure 6-1. Load Circuit and Voltage Waveforms"],
                "table_body": "<table><tr><td>TEST</td><td>S1</td></tr></table>",
                "bbox": [180, 400, 420, 470],
                "page_idx": 0,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={
                    "images/a.png": MINIMAL_PNG_BYTES,
                    "images/b.png": MINIMAL_PNG_BYTES,
                    "images/c.png": MINIMAL_PNG_BYTES,
                },
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_figure_group_caption",
                source_file_id="file_figure_group_caption",
                document_language="en",
            )

        table = next(block for block in result.document.blocks if block.type == "table")
        caption = next(
            block
            for block in result.document.blocks
            if block.metadata.get("annotation_role") == "standalone_caption"
        )
        images = [block for block in result.document.blocks if block.type == "image"]
        self.assertEqual(table.captions, [])
        self.assertEqual(caption.text, "Figure 6-1. Load Circuit and Voltage Waveforms")
        self.assertEqual(caption.metadata["subject_block_ids"], [block.id for block in images])
        self.assertTrue(all(block.metadata["content_group_id"] == caption.metadata["content_group_id"] for block in images))
        self.assertLess(result.document.blocks.index(caption), result.document.blocks.index(table))
        self.assertEqual(caption.layout.bbox, (40.0, 399.0, 560.0, 400.0))
        self.assertEqual(caption.layout.column_hint, "wide")
        self.assertIn("figure_caption_reassigned_to_image_group:block_0006", result.document.quality_flags)

    def test_convert_zip_promotes_single_title_like_annotation_to_aligned_image_group_caption(self) -> None:
        blocks = [
            {
                "type": "image",
                "content": {
                    "image_source": {"path": "images/left.png"},
                    "image_caption": [],
                    "image_footnote": [],
                },
                "bbox": [70, 300, 280, 500],
                "page_idx": 0,
            },
            {
                "type": "image",
                "content": {
                    "image_source": {"path": "images/right.png"},
                    "image_caption": [],
                    "image_footnote": [{"type": "text", "content": "Shared Logic Diagram"}],
                },
                "bbox": [320, 302, 530, 502],
                "page_idx": 0,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
                images={"images/left.png": MINIMAL_PNG_BYTES, "images/right.png": MINIMAL_PNG_BYTES},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_shared_image_caption",
                source_file_id="file_shared_image_caption",
                document_language="en",
            )

        left, right, caption = result.document.blocks
        self.assertEqual(left.footnotes, [])
        self.assertEqual(right.footnotes, [])
        self.assertEqual(caption.type, "paragraph")
        self.assertEqual(caption.text, "Shared Logic Diagram")
        self.assertEqual(caption.metadata["annotation_role"], "standalone_caption")
        self.assertEqual(caption.metadata["subject_block_ids"], [left.id, right.id])
        self.assertEqual(caption.layout.bbox, (70.0, 503.0, 530.0, 504.0))
        self.assertEqual(caption.layout.column_hint, "wide")
        plan = build_layout_plan(result.document)
        self.assertEqual([region.kind for region in plan.pages[0].regions], ["paired_visual_row", "one_col"])
        self.assertEqual([block.id for block in plan.pages[0].regions[0].blocks], [left.id, right.id])
        self.assertEqual([block.id for block in plan.pages[0].regions[1].blocks], [caption.id])
        image_bytes = {asset.asset_id: asset.content for asset in result.image_assets}
        word_content = DocumentIRWordRenderer().render_to_bytes(
            result.document,
            template_path=None,
            config_path=None,
            image_loader=lambda asset: image_bytes.get(asset.id),
        )
        evidence = build_renderer_evidence(result.document, word_content)
        self.assertEqual(evidence["visible_payload_evidence"]["counts"]["annotation"], {"expected": 1, "covered": 1})
        self.assertIn("shared_image_caption_group:block_0001:block_0002", result.document.quality_flags)

    def test_convert_zip_blocks_figure_caption_on_table_without_unique_image_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "table_caption": ["Figure 2. Ambiguous visual"],
                        "table_body": "<table><tr><td>VALUE</td></tr></table>",
                        "bbox": [80, 300, 520, 420],
                        "page_idx": 0,
                    }
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]},
            )

            with self.assertRaisesRegex(DocumentIntegrityError, "caption_subject_unresolved:block_0001"):
                MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_ambiguous_figure_caption",
                    source_file_id="file_ambiguous_figure_caption",
                    document_language="en",
                )

    def test_convert_zip_normalizes_unique_table_contained_in_image_without_losing_editable_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "table",
                        "content": {
                            "image_source": {"path": "images/table.png"},
                            "html": "<table><tr><td>DIM</td><td>20</td></tr></table>",
                        },
                        "bbox": [300, 400, 500, 500],
                        "page_idx": 0,
                    },
                    {
                        "type": "image",
                        "content": {"image_source": {"path": "images/drawing.png"}},
                        "bbox": [100, 100, 700, 700],
                        "page_idx": 0,
                    },
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [800, 800]}]},
                images={"images/table.png": MINIMAL_PNG_BYTES, "images/drawing.png": MINIMAL_PNG_BYTES},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_visual_overlap",
                source_file_id="file_visual_overlap",
                document_language="en",
            )
            image_bytes = {asset.asset_id: asset.content for asset in result.image_assets}
            word_content = DocumentIRWordRenderer().render_to_bytes(
                result.document,
                template_path=None,
                config_path=None,
                image_loader=lambda asset: image_bytes.get(asset.id),
            )
            evidence = build_renderer_evidence(result.document, word_content)

        table, image = result.document.blocks
        self.assertEqual(table.type, "table")
        self.assertEqual(image.type, "image")
        self.assertEqual(table.metadata["visual_overlap_group_id"], image.metadata["visual_overlap_group_id"])
        self.assertEqual(
            image.metadata["visual_crop_rects"],
            [
                [0.0, 0.0, 1 / 3, 1.0],
                [1 / 3, 0.0, 2 / 3, 0.5],
                [2 / 3, 0.0, 1.0, 1.0],
                [1 / 3, 2 / 3, 2 / 3, 1.0],
            ],
        )
        round_tripped = type(result.document).model_validate_json(result.document.model_dump_json())
        self.assertEqual(round_tripped.blocks[1].metadata["visual_crop_rects"], image.metadata["visual_crop_rects"])
        self.assertEqual(evidence["expected_inline_shape_count"], 4)
        self.assertEqual(evidence["inline_shape_count"], 4)
        self.assertEqual(evidence["expected_table_count"], 1)
        self.assertEqual(evidence["table_count"], 1)
        self.assertEqual(evidence["docx_quality"]["layout_table_count"], 1)
        self.assertEqual(evidence["docx_quality"]["visual_table_composite_count"], 1)
        self.assertEqual(evidence["blocking_quality_flags"], [])
        self.assertEqual(len(evidence["visual_overlap_normalizations"]), 1)
        self.assertEqual(
            evidence["visual_table_composite_evidence"]["rendered_group_ids"],
            [image.metadata["visual_overlap_group_id"]],
        )
        with zipfile.ZipFile(io.BytesIO(word_content)) as docx_zip:
            document_xml = docx_zip.read("word/document.xml").decode("utf-8")
        self.assertEqual(document_xml.count("<a:srcRect"), 4)
        self.assertEqual(document_xml.count("<w:tab/>"), 0)
        self.assertIn("md2word:visual_table_composite:visual_overlap:block_0001:block_0002", document_xml)
        self.assertEqual(document_xml.count("<w:tbl>"), 2)
        self.assertIn("DIM", document_xml)
        self.assertIn("20", document_xml)

    def test_convert_zip_reassigns_figure_caption_to_contained_table_image_composite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[
                    {
                        "type": "image",
                        "content": {"image_source": {"path": "images/drawing.png"}},
                        "bbox": [100, 100, 700, 700],
                        "page_idx": 0,
                    },
                    {
                        "type": "table",
                        "content": {
                            "image_source": {"path": "images/table.png"},
                            "table_caption": [{"type": "text", "content": "Figure 23. Package outline"}],
                            "html": "<table><tr><td>DIM</td><td>20</td></tr></table>",
                        },
                        "bbox": [450, 180, 650, 420],
                        "page_idx": 0,
                    },
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [800, 800]}]},
                images={"images/table.png": MINIMAL_PNG_BYTES, "images/drawing.png": MINIMAL_PNG_BYTES},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_visual_overlap_caption",
                source_file_id="file_visual_overlap_caption",
                document_language="en",
            )

        image = next(block for block in result.document.blocks if block.type == "image")
        table = next(block for block in result.document.blocks if block.type == "table")
        caption = next(
            block
            for block in result.document.blocks
            if block.metadata.get("annotation_role") == "standalone_caption"
        )
        self.assertEqual(table.captions, [])
        self.assertEqual(caption.text, "Figure 23. Package outline")
        self.assertEqual(caption.metadata["subject_block_ids"], [image.id, table.id])
        self.assertGreater(result.document.blocks.index(caption), result.document.blocks.index(table))
        self.assertEqual(image.metadata["visual_overlap_group_id"], table.metadata["visual_overlap_group_id"])
        self.assertFalse(any(block.metadata.get("caption_owner_unresolved") for block in result.document.blocks))
        self.assertIn(
            "figure_caption_reassigned_to_visual_composite:block_0001:block_0002",
            result.document.quality_flags,
        )

    def test_convert_zip_blocks_ambiguous_table_image_containment(self) -> None:
        blocks = [
            {
                "type": "table",
                "content": {
                    "image_source": {"path": "images/table.png"},
                    "html": "<table><tr><td>DIM</td></tr></table>",
                },
                "bbox": [300, 400, 500, 500],
                "page_idx": 0,
            },
            {
                "type": "image",
                "content": {"image_source": {"path": "images/drawing-a.png"}},
                "bbox": [100, 100, 700, 700],
                "page_idx": 0,
            },
            {
                "type": "image",
                "content": {"image_source": {"path": "images/drawing-b.png"}},
                "bbox": [80, 80, 720, 720],
                "page_idx": 0,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": 0, "page_size": [800, 800]}]},
                images={
                    "images/table.png": MINIMAL_PNG_BYTES,
                    "images/drawing-a.png": MINIMAL_PNG_BYTES,
                    "images/drawing-b.png": MINIMAL_PNG_BYTES,
                },
            )

            with self.assertRaisesRegex(DocumentIntegrityError, "visual_overlap_unresolved"):
                MinerUToDocumentIRService().convert_zip(
                    zip_path,
                    job_id="docjob_ambiguous_visual_overlap",
                    source_file_id="file_ambiguous_visual_overlap",
                    document_language="en",
                )

    def test_convert_zip_blocks_unsafe_table_image_normalization_inputs(self) -> None:
        cases = {
            "无效 HTML": (
                [300, 400, 500, 500],
                "not a table",
                {"images/table.png": MINIMAL_PNG_BYTES, "images/drawing.png": MINIMAL_PNG_BYTES},
            ),
            "图片资产缺失": (
                [300, 400, 500, 500],
                "<table><tr><td>DIM</td></tr></table>",
                {"images/table.png": MINIMAL_PNG_BYTES},
            ),
            "表区超过半幅": (
                [120, 120, 680, 680],
                "<table><tr><td>DIM</td></tr></table>",
                {"images/table.png": MINIMAL_PNG_BYTES, "images/drawing.png": MINIMAL_PNG_BYTES},
            ),
        }
        for label, (table_bbox, html, images) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "mineru.zip"
                self._write_zip(
                    zip_path,
                    blocks=[
                        {
                            "type": "table",
                            "content": {"image_source": {"path": "images/table.png"}, "html": html},
                            "bbox": table_bbox,
                            "page_idx": 0,
                        },
                        {
                            "type": "image",
                            "content": {"image_source": {"path": "images/drawing.png"}},
                            "bbox": [100, 100, 700, 700],
                            "page_idx": 0,
                        },
                    ],
                    layout={"pdf_info": [{"page_idx": 0, "page_size": [800, 800]}]},
                    images=images,
                )

                with self.assertRaisesRegex(DocumentIntegrityError, "visual_overlap_unresolved"):
                    MinerUToDocumentIRService().convert_zip(
                        zip_path,
                        job_id="docjob_unsafe_visual_overlap",
                        source_file_id="file_unsafe_visual_overlap",
                        document_language="en",
                    )

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
                        "table_caption": [
                            {"type": "text", "content": condition[:64]},
                            {"type": "text", "content": condition[64:]},
                        ],
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
        self.assertEqual(document.blocks[2].footnotes, [r"Note: $V_{OS}$"])
        self.assertEqual(document.blocks[2].layout.column_hint, "wide")
        self.assertEqual(document.blocks[3].type, "image")
        self.assertEqual(document.blocks[3].captions, ["Figure 1. Noise"])
        self.assertEqual(result.image_assets[0].source_path, "images/chart.png")

    def test_semantic_normalization_distinguishes_true_decorations_from_body_content(self) -> None:
        blocks = [
            {"type": "page_header", "text": "ACME CONFIDENTIAL", "bbox": [30, 10, 200, 30], "page_idx": 0},
            {"type": "text", "text": "Page zero body", "bbox": [30, 100, 500, 140], "page_idx": 0},
            {"type": "page_number", "text": "1", "bbox": [290, 740, 310, 760], "page_idx": 0},
            {"type": "page_header", "text": "ACME CONFIDENTIAL", "bbox": [30, 10, 200, 30], "page_idx": 1},
            {"type": "text", "text": "Page one body", "bbox": [30, 100, 500, 140], "page_idx": 1},
            {
                "type": "page_header",
                "text": "Unique edge engineering label",
                "bbox": [30, 10, 260, 30],
                "page_idx": 2,
            },
            {"type": "text", "text": "Page two body", "bbox": [30, 100, 500, 140], "page_idx": 2},
            {
                "type": "page_footer",
                "text": "IMPORTANT NOTICE AND DISCLAIMER " + "This document remains technical body content. " * 8,
                "bbox": [30, 120, 560, 500],
                "page_idx": 3,
            },
            {"type": "page_header", "text": "Visible label without layout metadata"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": index, "page_size": [612, 792]} for index in range(4)]},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_semantic_decorations",
                source_file_id="file_semantic_decorations",
                document_language="en",
            )

        document = result.document
        self.assertEqual(document.blocks[0].layout.role, "page_header")
        self.assertEqual(document.blocks[2].layout.role, "page_number")
        self.assertEqual(document.blocks[3].layout.role, "page_header")
        self.assertEqual(document.blocks[5].layout.role, "body")
        self.assertEqual(document.blocks[5].metadata["semantic_decision_reason"], "ambiguous_margin_decoration_preserved_as_body")
        self.assertEqual(document.blocks[7].layout.role, "body")
        self.assertEqual(document.blocks[7].metadata["semantic_decision_reason"], "decoration_candidate_promoted_to_body")
        self.assertEqual(document.blocks[8].layout.role, "body")
        self.assertEqual(document.blocks[8].metadata["semantic_decision_reason"], "ambiguous_decoration_preserved_as_body")
        self.assertTrue(all(block.metadata.get("semantic_decision_reason") for block in document.blocks))
        self.assertIn("semantic_decoration_ambiguous:5", document.quality_flags)
        self.assertIn("semantic_decoration_promoted:7", document.quality_flags)
        self.assertIn("semantic_decoration_ambiguous:8", document.quality_flags)

    def test_semantic_normalization_keeps_page_subject_labels_beside_true_decorations(self) -> None:
        blocks = [
            {"type": "page_header", "text": "ACME COMPONENTS", "bbox": [40, 20, 170, 60], "page_idx": 0},
            {"type": "page_header", "text": "www.example.test", "bbox": [40, 80, 150, 95], "page_idx": 0},
            {
                "type": "page_header",
                "text": "PACKAGE MATERIALS INFORMATION",
                "bbox": [510, 25, 940, 55],
                "page_idx": 0,
            },
            {"type": "page_header", "text": "10-Aug-2026", "bbox": [860, 80, 940, 97], "page_idx": 0},
            {
                "type": "table",
                "table_body": "<table><tr><td>Device</td><td>Package</td></tr></table>",
                "bbox": [90, 145, 910, 710],
                "page_idx": 0,
            },
            {"type": "page_header", "text": "ACME COMPONENTS", "bbox": [40, 20, 170, 60], "page_idx": 1},
            {"type": "page_header", "text": "www.example.test", "bbox": [40, 80, 150, 95], "page_idx": 1},
            {"type": "text", "text": "Ordinary product body", "bbox": [80, 130, 900, 180], "page_idx": 1},
            {"type": "page_header", "text": "ACME COMPONENTS", "bbox": [40, 20, 170, 60], "page_idx": 2},
            {"type": "page_header", "text": "www.example.test", "bbox": [40, 80, 150, 95], "page_idx": 2},
            {"type": "text", "text": "More product body", "bbox": [80, 130, 900, 180], "page_idx": 2},
            {"type": "page_header", "text": "ACME COMPONENTS", "bbox": [40, 20, 170, 60], "page_idx": 3},
            {"type": "page_header", "text": "www.example.test", "bbox": [40, 80, 150, 95], "page_idx": 3},
            {"type": "page_header", "text": "DB0020A", "bbox": [90, 74, 210, 95], "page_idx": 3},
            {"type": "page_header", "text": "PACKAGE OUTLINE", "bbox": [660, 44, 910, 65], "page_idx": 3},
            {"type": "page_header", "text": "SSOP - 2 mm max height", "bbox": [650, 76, 910, 96], "page_idx": 3},
            {"type": "image", "img_path": "images/chart.png", "bbox": [85, 128, 915, 800], "page_idx": 3},
            {"type": "title", "text": "NOTES:", "bbox": [85, 820, 150, 840], "page_idx": 3},
            {
                "type": "page_header",
                "text": "PACKAGE MATERIALS INFORMATION",
                "bbox": [510, 25, 940, 55],
                "page_idx": 4,
            },
            {
                "type": "table",
                "table_body": "<table><tr><td>Device</td><td>Package</td></tr></table>",
                "bbox": [90, 145, 910, 710],
                "page_idx": 4,
            },
            *[
                {
                    "type": "text",
                    "text": f"Ordinary body page {page_index}",
                    "bbox": [80, 130, 900, 180],
                    "page_idx": page_index,
                }
                for page_index in range(5, 12)
            ],
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": index, "page_size": [1000, 1000]} for index in range(12)]},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_page_subject_labels",
                source_file_id="file_page_subject_labels",
                document_language="en",
            )

        blocks_by_text = {
            text: [block for block in result.document.blocks if block.text == text]
            for text in {block.text for block in result.document.blocks if block.text}
        }
        self.assertTrue(all(block.layout.role == "page_header" for block in blocks_by_text["ACME COMPONENTS"]))
        self.assertTrue(all(block.layout.role == "page_header" for block in blocks_by_text["www.example.test"]))
        section_headers = blocks_by_text["PACKAGE MATERIALS INFORMATION"]
        self.assertEqual(len(section_headers), 2)
        self.assertTrue(all(block.layout.role == "body" for block in section_headers))
        self.assertTrue(
            all(
                block.metadata["semantic_decision_reason"] == "decoration_candidate_promoted_by_page_subject"
                for block in section_headers
            )
        )
        by_text = {text: blocks[0] for text, blocks in blocks_by_text.items()}
        self.assertEqual(by_text["10-Aug-2026"].layout.role, "page_header")
        for text in (
            "DB0020A",
            "PACKAGE OUTLINE",
            "SSOP - 2 mm max height",
        ):
            with self.subTest(text=text):
                self.assertEqual(by_text[text].layout.role, "body")
                self.assertEqual(
                    by_text[text].metadata["semantic_decision_reason"],
                    "decoration_candidate_promoted_by_page_subject",
                )

    def test_semantic_normalization_keeps_aligned_top_edge_navigation_as_decoration(self) -> None:
        blocks = [
            {"type": "page_header", "text": "Ordering and quality", "bbox": [230, 6, 345, 35], "page_idx": 0},
            {"type": "page_header", "text": "Technical documentation", "bbox": [365, 8, 495, 36], "page_idx": 0},
            {"type": "page_header", "text": "Design and development", "bbox": [515, 6, 640, 35], "page_idx": 0},
            {"type": "page_header", "text": "Support and training", "bbox": [660, 6, 765, 35], "page_idx": 0},
            {"type": "text", "text": "Ordinary body", "bbox": [80, 100, 900, 160], "page_idx": 0},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": 0, "page_size": [1000, 1000]}]},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_aligned_top_navigation",
                source_file_id="file_aligned_top_navigation",
                document_language="en",
            )

        navigation = result.document.blocks[:4]
        self.assertTrue(all(block.layout.role == "page_header" for block in navigation))
        self.assertTrue(
            all(block.metadata["semantic_decision_reason"] == "aligned_margin_decoration_group" for block in navigation)
        )

    def test_semantic_normalization_filters_empty_text_blocks_with_explicit_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [
                        {
                            "type": "paragraph",
                            "content": {"paragraph_content": []},
                            "bbox": [30, 80, 560, 120],
                        },
                        {
                            "type": "paragraph",
                            "content": {
                                "paragraph_content": [{"type": "text", "content": "正文保持可见"}]
                            },
                            "bbox": [30, 140, 560, 180],
                        },
                    ]
                ],
                layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_empty_text_disposition",
                source_file_id="file_empty_text_disposition",
                document_language="zh",
            )

        empty_block, body_block = result.document.blocks
        self.assertEqual(empty_block.layout.role, "filtered")
        self.assertEqual(empty_block.metadata["semantic_decision_reason"], "empty_text_block_filtered")
        self.assertIsNone(empty_block.text)
        self.assertEqual(body_block.layout.role, "body")
        self.assertEqual(body_block.text, "正文保持可见")
        self.assertEqual(result.document.metadata.source_block_count, 2)

    def test_semantic_normalization_promotes_only_continuous_decimal_sequences_to_lists(self) -> None:
        def rich_block(source_type: str, text: str, top: int) -> dict[str, Any]:
            field_name = "title_content" if source_type == "title" else "paragraph_content"
            return {
                "type": source_type,
                "content": {field_name: [{"type": "text", "content": text}]},
                "bbox": [30, top, 560, top + 30],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=[],
                v2_blocks=[
                    [rich_block("title", "1. 独立编号标题", 40)],
                    [
                        rich_block("title", "1.第一步", 40),
                        rich_block("paragraph", r"2.$V_{OUT}$", 80),
                        rich_block("paragraph", "3．第三步", 120),
                        rich_block("paragraph", "4、第四步", 160),
                    ],
                    [rich_block("paragraph", "1. 孤立编号正文句。", 40)],
                    [
                        rich_block("paragraph", "2.2V operation", 40),
                        rich_block("paragraph", "3.3V operation", 80),
                    ],
                ],
                layout={
                    "pdf_info": [
                        {"page_idx": page_index, "page_size": [612, 792]}
                        for page_index in range(4)
                    ]
                },
            )

            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_decimal_sequences",
                source_file_id="file_decimal_sequences",
                document_language="zh",
            )

        isolated_heading, *remaining_blocks = result.document.blocks
        sequence = remaining_blocks[:4]
        isolated_paragraph, first_voltage, second_voltage = remaining_blocks[4:]
        self.assertEqual(isolated_heading.type, "heading")
        self.assertEqual(isolated_heading.metadata["semantic_decision_reason"], "source_title_preserved")
        self.assertEqual([block.type for block in sequence], ["list", "list", "list", "list"])
        self.assertEqual(
            [block.list_items for block in sequence],
            [["1.第一步"], [r"2.$V_{OUT}$"], ["3．第三步"], ["4、第四步"]],
        )
        self.assertTrue(
            all(block.metadata["semantic_decision_reason"] == "sequential_decimal_list" for block in sequence)
        )
        self.assertEqual(isolated_paragraph.type, "paragraph")
        self.assertEqual(isolated_paragraph.text, "1. 孤立编号正文句。")
        self.assertEqual([first_voltage.type, second_voltage.type], ["paragraph", "paragraph"])
        self.assertEqual([first_voltage.text, second_voltage.text], ["2.2V operation", "3.3V operation"])

    def test_decimal_list_marker_distinguishes_markers_from_decimal_values(self) -> None:
        self.assertEqual(parse_decimal_list_marker("1. text"), (1, "text"))
        self.assertEqual(parse_decimal_list_marker("1.中文"), (1, "中文"))
        self.assertEqual(parse_decimal_list_marker(r"1.$V_{OUT}$"), (1, r"$V_{OUT}$"))
        self.assertEqual(parse_decimal_list_marker("2．中文"), (2, "中文"))
        self.assertEqual(parse_decimal_list_marker("3、中文"), (3, "中文"))
        self.assertIsNone(parse_decimal_list_marker("2.2V operation"))
        self.assertIsNone(parse_decimal_list_marker("3.3V operation"))

    def test_semantic_normalization_resolves_title_page_note_and_explicit_toc_roles(self) -> None:
        blocks = [
            {"type": "title", "text": "Table of Contents", "bbox": [30, 40, 300, 70], "page_idx": 0},
            {"type": "text", "text": "Product Overview................ 2", "bbox": [30, 80, 500, 105], "page_idx": 0},
            {"type": "text", "text": "Electrical Characteristics..... 4", "bbox": [30, 110, 500, 135], "page_idx": 0},
            {"type": "text", "text": "Package Information............ 8", "bbox": [30, 140, 500, 165], "page_idx": 0},
            {"type": "title", "text": "Product Overview", "bbox": [30, 210, 400, 240], "page_idx": 0},
            {
                "type": "title",
                "text": "Changes from Revision G to Revision H",
                "bbox": [30, 260, 500, 290],
                "page_idx": 0,
            },
            {"type": "title", "text": "Figure 12. Timing", "bbox": [30, 310, 300, 340], "page_idx": 0},
            {"type": "title", "text": "NOTES:", "bbox": [30, 360, 160, 390], "page_idx": 0},
            {"type": "page_footnote", "text": "1. Typical value.", "bbox": [30, 650, 300, 680], "page_idx": 0},
            {"type": "text", "text": "Ordinary text", "text_level": 1, "bbox": [30, 420, 300, 450], "page_idx": 0},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            self._write_zip(
                zip_path,
                blocks=blocks,
                layout={"pdf_info": [{"page_idx": 0, "page_size": [612, 792]}]},
            )
            result = MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="docjob_semantic_titles",
                source_file_id="file_semantic_titles",
                document_language="en",
            )

        blocks_by_source = {
            block.metadata.get("source_type"): block
            for block in result.document.blocks
            if block.metadata.get("source_type") not in {"title"}
        }
        source_titles = [
            block for block in result.document.blocks if block.metadata.get("source_type") == "title"
        ]
        self.assertEqual(source_titles[0].metadata["annotation_role"], "toc_title")
        toc_sources = [block for block in result.document.blocks if block.layout.role == "toc_source"]
        self.assertEqual(len(toc_sources), 3)
        toc_anchors = [
            block for block in result.document.blocks if block.metadata.get("annotation_role") == "toc_anchor"
        ]
        self.assertEqual(len(toc_anchors), 1)
        self.assertEqual(source_titles[1].type, "heading")
        self.assertEqual(source_titles[1].text, "Product Overview")
        self.assertEqual(source_titles[2].metadata["annotation_role"], "group_label")
        self.assertEqual(source_titles[3].metadata["annotation_role"], "standalone_caption")
        self.assertEqual(source_titles[4].metadata["annotation_role"], "group_label")
        self.assertEqual(blocks_by_source["page_footnote"].metadata["annotation_role"], "page_note")
        self.assertEqual(blocks_by_source["text"].type, "paragraph")

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
        v2_blocks: list[Any] | None = None,
        layout: dict | None,
        images: dict[str, bytes] | None = None,
    ) -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("content_list.json", json.dumps(blocks, ensure_ascii=False))
            if v2_blocks is not None:
                archive.writestr("result_content_list_v2.json", json.dumps(v2_blocks, ensure_ascii=False))
            if layout is not None:
                archive.writestr("layout.json", json.dumps(layout, ensure_ascii=False))
            for image_path, content in (images or {"images/chart.png": b"fake-image"}).items():
                archive.writestr(image_path, content)


if __name__ == "__main__":
    unittest.main()
