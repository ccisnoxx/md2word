"""通过正式转换验证显式源标题编号层级及源内容保真。"""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.conversion.docx_rules.text_semantics import infer_heading_level
from app.services.document_ir import MinerUToDocumentIRService


class DocumentIRNumberedHeadingLevelsTests(unittest.TestCase):
    def _convert_pages(self, pages):
        with tempfile.TemporaryDirectory(prefix="numbered_heading_levels_") as directory:
            zip_path = Path(directory) / "result.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("result/content_list_v2.json", json.dumps(pages, ensure_ascii=False))
            return MinerUToDocumentIRService().convert_zip(
                zip_path,
                job_id="numbered_heading_job",
                source_file_id="numbered_heading_source",
                document_language="zh",
            )

    def test_flat_source_levels_follow_number_depth_one_through_six(self) -> None:
        texts = [
            "1 概述",
            "1.2 功能",
            "1.2.3 参数",
            "1.2.3.4 条件",
            "1.2.3.4.5 特性",
            "1.2.3.4.5.6 细节",
        ]
        result = self._convert_pages([[{"type": "title", "text": text, "text_level": 1} for text in texts]])
        self.assertEqual([block.type for block in result.document.blocks], ["heading"] * 6)
        self.assertEqual([block.level for block in result.document.blocks], [1, 2, 3, 4, 5, 6])
        self.assertEqual([block.text for block in result.document.blocks], texts)
        self.assertEqual([block.metadata["text_level"] for block in result.document.blocks], [1] * 6)

    def test_number_depth_beyond_six_is_clipped_to_six(self) -> None:
        texts = ["1.2.3.4.5.6.7 第七层", "1.2.3.4.5.6.7.8.9.10 更深层"]
        result = self._convert_pages([[{"type": "heading", "text": text, "text_level": 1} for text in texts]])
        self.assertEqual([block.level for block in result.document.blocks], [6, 6])
        self.assertEqual([block.text for block in result.document.blocks], texts)

    def test_numbering_overrides_deeper_source_levels(self) -> None:
        blocks = [
            {"type": "heading", "text": "1 总览", "text_level": 6},
            {"type": "heading", "text": "1.2 功能", "level": 5},
            {"type": "heading", "text": "1.2.3 参数", "text_level": "invalid"},
        ]
        result = self._convert_pages([blocks])
        self.assertEqual([block.level for block in result.document.blocks], [1, 2, 3])

    def test_existing_chapter_section_part_and_appendix_formats_use_level_one(self) -> None:
        texts = [
            "第一章 概述",
            "第2节 参数",
            "第三部分 补充",
            "Chapter IV Overview",
            "SECTION 2 Operation",
            "Part 3 Notes",
            "附录A 参数",
            "Appendix B Ratings",
            "appendix 2 Extra",
        ]
        result = self._convert_pages([[{"type": "title", "text": text, "text_level": 6} for text in texts]])
        self.assertEqual([block.level for block in result.document.blocks], [1] * len(texts))
        self.assertEqual([block.text for block in result.document.blocks], texts)

    def test_unnumbered_headings_keep_source_parsing_defaults_and_clipping(self) -> None:
        cases = [
            ({"text_level": 4}, 4),
            ({"text_level": 6}, 6),
            ({"text_level": "5"}, 5),
            ({"level": "4"}, 4),
            ({"text_level": 4, "level": 6}, 4),
            ({}, 1),
            ({"text_level": None, "level": 6}, 1),
            ({"text_level": "invalid"}, 1),
            ({"text_level": 0}, 1),
            ({"level": -2}, 1),
            ({"text_level": 8}, 6),
        ]
        blocks = [{"type": "heading", "text": "无编号标题", **fields} for fields, _expected in cases]
        result = self._convert_pages([blocks])
        self.assertEqual([block.level for block in result.document.blocks], [expected for _fields, expected in cases])
        self.assertTrue(all(block.type == "heading" for block in result.document.blocks))

    def test_numbered_paragraphs_are_not_promoted(self) -> None:
        blocks = [
            {"type": "paragraph", "text": "1.2 这是正文内容", "level": 6},
            {"type": "text", "text": "1.2.3.4 仍是普通正文"},
            {"type": "paragraph", "text": "附录A 仅作正文提及"},
        ]
        result = self._convert_pages([blocks])
        self.assertEqual([block.type for block in result.document.blocks], ["paragraph"] * 3)
        self.assertEqual([block.level for block in result.document.blocks], [None] * 3)
        self.assertEqual([block.text for block in result.document.blocks], [block["text"] for block in blocks])

    def test_existing_text_level_heading_classification_is_preserved(self) -> None:
        result = self._convert_pages([[{"type": "text", "text": "1.2.3.4 电气特性", "text_level": 1}]])
        block = result.document.blocks[0]
        self.assertEqual((block.type, block.level), ("heading", 4))
        self.assertEqual(block.metadata["source_type"], "text")
        self.assertEqual(block.metadata["text_level"], 1)

    def test_rich_title_uses_existing_visible_text_extraction(self) -> None:
        blocks = [{
            "type": "title",
            "text_level": 1,
            "content": {"title_content": [
                {"type": "text", "content": "1.2.3.4.5 "},
                {"type": "text", "content": "电气参数"},
            ]},
        }]
        result = self._convert_pages([blocks])
        block = result.document.blocks[0]
        self.assertEqual((block.text, block.level), ("1.2.3.4.5 电气参数", 5))

    def test_text_order_ids_source_inventory_and_locators_are_preserved(self) -> None:
        pages = [
            [
                {"type": "title", "text": "2.1 REG_VDD", "text_level": 1},
                {"type": "paragraph", "text": "2.1 这里只是正文"},
            ],
            [
                {"type": "heading", "text": "无编号标题", "text_level": 4},
                {"type": "text", "text": "普通正文"},
            ],
        ]
        result = self._convert_pages(pages)
        document = result.document
        self.assertEqual([block.text for block in document.blocks], ["2.1 REG_VDD", "2.1 这里只是正文", "无编号标题", "普通正文"])
        self.assertEqual([block.type for block in document.blocks], ["heading", "paragraph", "heading", "paragraph"])
        self.assertEqual([block.level for block in document.blocks], [2, None, 4, None])
        self.assertEqual([block.id for block in document.blocks], ["block_0001", "block_0002", "block_0003", "block_0004"])
        self.assertEqual([block.order for block in document.blocks], [0, 1, 2, 3])
        self.assertEqual([block.page_index for block in document.blocks], [0, 0, 1, 1])
        expected_locators = [
            {"json_pointer": "/0/0", "page_index": 0, "source_index_in_page": 0, "source_index": 0, "source_type": "title"},
            {"json_pointer": "/0/1", "page_index": 0, "source_index_in_page": 1, "source_index": 1, "source_type": "paragraph"},
            {"json_pointer": "/1/0", "page_index": 1, "source_index_in_page": 0, "source_index": 2, "source_type": "heading"},
            {"json_pointer": "/1/1", "page_index": 1, "source_index_in_page": 1, "source_index": 3, "source_type": "text"},
        ]
        self.assertEqual([block.metadata["mineru_source"] for block in document.blocks], expected_locators)
        self.assertEqual(document.metadata.source_block_count, 4)
        self.assertEqual(document.metadata.source_type_counts, {"title": 1, "paragraph": 1, "heading": 1, "text": 1})
        self.assertEqual(result.validation_report.inventory["raw_block_count"], 4)
        self.assertTrue(result.validation_report.can_convert)
        for block in document.blocks:
            self.assertNotIn("semantic_normalization", block.metadata)

    def test_legacy_heading_inference_keeps_three_level_compatibility(self) -> None:
        cases = [
            ("1 Overview", 1),
            ("1.2 Features", 2),
            ("1.2.3.4 Deep Heading", 3),
            ("1.2.3.4.5.6.7 Deeper Heading", 3),
            ("Plain Heading", 2),
            ("第一章 概述", 1),
            ("Appendix A Ratings", 1),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(infer_heading_level(text), expected)


if __name__ == "__main__":
    unittest.main()
