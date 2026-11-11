"""文字栏流与图表混排的实际读序、原生栏边界及历史冻结证据回归。"""
from __future__ import annotations

import base64
from collections import Counter
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
import zipfile

from docx.oxml.ns import qn

from app.services.document_ir.models import (
    DocumentIR, DocumentIRAsset, DocumentIRBlock, DocumentIRBlockLayout,
    DocumentIRMetadata, DocumentIRPage,
)
from app.services.renderer.render_evidence import build_renderer_evidence, validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.word_renderer import DocumentIRWordRenderer


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)
OLD_SCHEDULER = "app.services.renderer.render_plan._complete_two_column_text_region"
TAIL_SCHEDULER = "app.services.renderer.render_plan.complete_two_column_tails"


def body(block_id, order, text, bbox, hint, *, block_type="paragraph", page_index=0):
    return DocumentIRBlock(id=block_id, type=block_type, order=order, text=text,
        level=1 if block_type == "heading" else None, page_index=page_index,
        layout=DocumentIRBlockLayout(page_index=page_index, bbox=bbox, column_hint=hint))


def fragmented_document():
    """左右段落高度不同；右栏续句几何上先于左栏段首，不能按 band 交错。"""
    blocks = [
        body("left_heading", 0, "左栏起始", (10, 70, 180, 90), "left", block_type="heading"),
        body("left_intro", 1, "左栏第一段介绍。", (10, 95, 180, 220), "left"),
        body("left_lower_heading", 2, "下方主题", (10, 270, 180, 290), "left", block_type="heading"),
        body("left_lower", 3, "下方主题的开头，", (10, 300, 180, 450), "left"),
        body("right_continuation", 4, "续接上面的主题。", (220, 60, 390, 140), "right"),
        body("right_formula", 5, None, (220, 175, 390, 195), "right", block_type="formula"),
        body("right_middle", 6, "右栏后续说明。", (220, 230, 390, 260), "right"),
        body("right_tail", 7, "右栏末段。", (220, 420, 390, 500), "right"),
    ]
    blocks[5].latex = "x^2"
    return DocumentIR(schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(job_id="column_order", source_file_id="neutral_source", document_language="zh"),
        pages=[DocumentIRPage(index=0, width=400, height=600)], blocks=blocks)


def mixed_column_document():
    """保留实际混排页的源序和几何拓扑，正文、图片与表格均使用中性内容。"""
    geometry = [
        ("heading", "left", (112, 176, 344, 199)),
        ("paragraph", "left", (111, 212, 485, 303)),
        ("paragraph", "left", (111, 314, 485, 359)),
        ("heading", "left", (112, 375, 367, 396)),
        ("image", "left", (125, 402, 410, 465)),
        ("table", "left", (114, 469, 455, 503)),
        ("heading", "right", (511, 176, 617, 198)),
        ("paragraph", "right", (511, 213, 862, 243)),
        ("paragraph", "right", (511, 244, 725, 258)),
        ("paragraph", "right", (511, 258, 834, 287)),
        ("paragraph", "right", (513, 289, 758, 304)),
        ("paragraph", "right", (511, 304, 823, 334)),
        ("paragraph", "right", (511, 334, 833, 363)),
        ("paragraph", "right", (513, 364, 861, 378)),
        ("paragraph", "right", (513, 380, 736, 393)),
        ("paragraph", "right", (513, 395, 781, 410)),
        ("paragraph", "right", (513, 411, 712, 426)),
        ("heading", "right", (513, 450, 660, 473)),
        ("paragraph", "right", (511, 484, 870, 500)),
        ("paragraph", "right", (513, 500, 805, 515)),
        ("paragraph", "right", (513, 516, 679, 530)),
        ("heading", "left", (112, 577, 351, 601)),
        ("image", "left", (78, 654, 560, 790)),
        ("image", "right", (620, 645, 885, 819)),
    ]
    blocks, assets = [], []
    for index, (block_type, hint, bbox) in enumerate(geometry):
        block = body(f"mixed_{index + 1:02d}", index,
            f"中性正文{index + 1}" if block_type in {"heading", "paragraph"} else None,
            bbox, hint, block_type=block_type)
        block.layout.source_index = index
        if block_type == "table":
            block.html = "<table><tr><td>中性项目</td><td>中性数值</td></tr></table>"
        elif block_type == "image":
            block.asset_ref = f"image_{index}"
            assets.append(DocumentIRAsset(id=block.asset_ref, kind="image", source_path=f"image_{index}.png"))
        blocks.append(block)
    return DocumentIR(schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(job_id="mixed_column", source_file_id="neutral_mixed", document_language="zh"),
        pages=[DocumentIRPage(index=0, width=885, height=1145)], blocks=blocks, assets=assets)


def render(document):
    return DocumentIRWordRenderer().render_to_result(document, template_path=None, config_path=None,
        image_loader=lambda _asset: PNG_BYTES)


def document_xml(content):
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        return ET.fromstring(package.read("word/document.xml"))


def text_content(node):
    return "".join(item.text or "" for item in node.iter() if item.tag in {qn("w:t"), qn("m:t")})


class TwoColumnReadingOrderTests(unittest.TestCase):
    def assert_mixed_column_targets(self, document, result, expected_columns):
        """直接核对段落所处的实际分节和 column break，覆盖图片 overlay 后的输出。"""
        root = document_xml(result.content)
        xml_body = root.find("w:body", NS)
        positions, pending = {}, []
        for index, node in enumerate(xml_body):
            pending.append((index, node))
            section = node if node.tag == qn("w:sectPr") else node.find("./w:pPr/w:sectPr", NS)
            if section is None:
                continue
            columns = section.find("w:cols", NS)
            count = int(columns.get(qn("w:num"), "1")) if columns is not None else 1
            column = 0
            for child_index, child in pending:
                positions[child_index] = (count, column)
                column += len(child.findall(".//w:br[@w:type='column']", NS))
            pending.clear()
        records = {record.block_id: record for record in result.block_evidence.block_render_map}
        self.assertEqual(Counter(record.block_id for record in result.block_evidence.block_render_map),
            Counter(block.id for block in document.blocks))
        for block_id, expected in expected_columns.items():
            record = records[block_id]
            self.assertEqual(len(record.targets), 1)
            target = record.targets[0]
            node = root
            for child_index in target.child_path:
                node = node[child_index]
            self.assertEqual(node.tag, qn("w:p"))
            self.assertEqual(text_content(node), next(block.text for block in document.blocks if block.id == block_id))
            self.assertEqual(positions[target.child_path[1]], expected, block_id)
        return root

    def test_mixed_page_repairs_only_proven_right_tails_in_actual_native_columns(self):
        document = mixed_column_document()
        before = document.model_dump_json()
        layout = build_layout_plan(document)
        regions = [(region.kind, [block.id for block in region.blocks]) for region in layout.pages[0].regions]
        self.assertEqual([kind for kind, _ in regions],
            ["two_col", "one_col", "two_col", "one_col", "two_col", "one_col", "two_col"])
        self.assertEqual(regions[1][1], ["mixed_14"])
        self.assertEqual(regions[5][1], ["mixed_20", "mixed_21", "mixed_22"])

        with patch(TAIL_SCHEDULER, side_effect=lambda page, source: page.regions):
            previous = render(document)
        current = render(document)

        tails = ("mixed_14", "mixed_20", "mixed_21")
        self.assert_mixed_column_targets(document, previous, {block_id: (1, 0) for block_id in tails})
        root = self.assert_mixed_column_targets(document, current,
            {**{block_id: (2, 1) for block_id in tails}, "mixed_22": (1, 0)})
        decisions = {decision.block_id: decision for decision in current.plan.decisions}
        self.assertEqual(decisions["mixed_13"].section_id, decisions["mixed_14"].section_id)
        self.assertEqual({decisions[block_id].section_id for block_id in ("mixed_19", "mixed_20", "mixed_21")},
            {decisions["mixed_19"].section_id})
        operations = [block_id for operation in current.plan.operations for block_id in operation.block_ids]
        self.assertEqual(Counter(operations), Counter(block.id for block in document.blocks))
        self.assertEqual([block_id for block_id in operations if block_id in tails], list(tails))
        self.assertEqual(len(root.findall(".//w:tbl", NS)), 1)
        self.assertEqual(len(root.findall(".//w:drawing", NS)), 3)
        self.assertEqual(current.plan.table_units, previous.plan.table_units)
        self.assertEqual(current.image_layout_report, previous.image_layout_report)
        self.assertTrue(any(span["reasons"] for span in current.image_layout_report["spans"]))
        evidence = build_renderer_evidence(document, current.content, layout, render_result=current)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["layout_region_count"], len(regions))
        self.assertEqual([(region.kind, [block.id for block in region.blocks]) for region in layout.pages[0].regions], regions)
        self.assertEqual(document.model_dump_json(), before)

    def test_mixed_tail_requires_source_continuity_same_column_and_close_geometry(self):
        cases = []
        for name in ("missing_bbox", "missing_hint", "wide", "other_column", "missing_source_index",
                     "source_gap", "order_gap", "single_column_gap", "horizontal_offset", "heading"):
            document = mixed_column_document()
            tail = document.blocks[13]
            if name == "missing_bbox":
                tail.layout.bbox = None
            elif name == "missing_hint":
                tail.layout.column_hint = None
            elif name == "wide":
                tail.layout.column_hint = "wide"
                tail.type, tail.text = "table", None
                tail.html = "<table><tr><td>宽表必须单栏</td></tr></table>"
            elif name == "other_column":
                tail.layout.column_hint = "left"
            elif name == "missing_source_index":
                tail.layout.source_index = None
            elif name == "source_gap":
                tail.layout.source_index += 50
            elif name == "order_gap":
                tail.order += 50
            elif name == "single_column_gap":
                document.blocks[12].layout.bbox = (511, 334, 833, 355)
            elif name == "horizontal_offset":
                tail.layout.bbox = (540, 364, 861, 378)
            elif name == "heading":
                tail.type, tail.level = "heading", 1
            cases.append((name, document))
        for name, document in cases:
            with self.subTest(name=name):
                with patch(TAIL_SCHEDULER, side_effect=lambda page, source: page.regions):
                    previous = render(document)
                current = render(document)
                old = next(item for item in previous.plan.decisions if item.block_id == "mixed_14")
                new = next(item for item in current.plan.decisions if item.block_id == "mixed_14")
                self.assertEqual(current.plan.sections[int(new.section_id.split("_")[1])].columns,
                    previous.plan.sections[int(old.section_id.split("_")[1])].columns)
                if name != "wide":
                    self.assert_mixed_column_targets(document, current, {"mixed_14": (1, 0)})
                ensure_renderer_integrity(build_renderer_evidence(document, current.content, render_result=current))

    def test_confirmed_image_group_stays_independent_of_mixed_tail_repair(self):
        document = mixed_column_document()
        document.blocks[-2].layout.bbox = (78, 654, 480, 790)
        document.blocks[-1].layout.bbox = (500, 654, 885, 790)
        with patch(TAIL_SCHEDULER, side_effect=lambda page, source: page.regions):
            previous = render(document)

        current = render(document)

        root = self.assert_mixed_column_targets(document, current,
            {"mixed_14": (2, 1), "mixed_20": (2, 1), "mixed_21": (2, 1), "mixed_22": (1, 0)})
        self.assertEqual(len(root.findall(".//w:tbl", NS)), 2)
        self.assertEqual(current.image_layout_report, previous.image_layout_report)
        self.assertEqual(current.image_layout_report["spans"][-1]["mode"], "group")
        ensure_renderer_integrity(build_renderer_evidence(document, current.content, render_result=current))

    def test_mixed_previous_frozen_trace_and_content_survive_tail_schedule_change(self):
        document = mixed_column_document()
        with patch(TAIL_SCHEDULER, side_effect=lambda page, source: page.regions):
            previous = render(document)
            previous_evidence = build_renderer_evidence(document, previous.content, render_result=previous)
            ensure_renderer_integrity(previous_evidence)
        current = render(document)
        stored_ir = DocumentIR.model_validate_json(document.model_dump_json())
        stored_evidence = json.loads(json.dumps(previous_evidence))

        restored = validate_persisted_renderer_content(stored_ir, previous.content, stored_evidence)

        self.assertNotEqual(current.plan.operations, previous.plan.operations)
        self.assertEqual(current.plan.table_units, previous.plan.table_units)
        self.assertEqual(restored["render_trace_status"], "complete")
        self.assertEqual(restored["render_plan"], stored_evidence["render_plan"])
        self.assertEqual(restored["block_render_evidence"], stored_evidence["block_render_evidence"])
        self.assertEqual(restored["layout_region_count"], stored_evidence["layout_region_count"])

    def assert_trace_order(self, document, result, expected_ids):
        """按实际 XML 目标位置核对读序，不能把源序库存本身当作输出次序。"""
        root = document_xml(result.content)
        records = result.block_evidence.block_render_map
        self.assertEqual(Counter(record.block_id for record in records), Counter(block.id for block in document.blocks))
        located = []
        blocks = {block.id: block for block in document.blocks}
        for record in records:
            self.assertEqual(len(record.targets), 1, record.block_id)
            target = record.targets[0]
            self.assertEqual(target.part, "word/document.xml")
            node = root
            for index in target.child_path:
                node = node[index]
            self.assertEqual(node.tag, qn("w:p"))
            block = blocks[record.block_id]
            self.assertEqual(text_content(node), "x2" if block.type == "formula" else block.text or "")
            located.append((target.child_path, record.block_id))
        self.assertEqual([block_id for _, block_id in sorted(located)], expected_ids)
        return root

    def test_staggered_text_columns_follow_complete_source_flow_and_restore_single_column(self):
        document = fragmented_document()
        before = document.model_dump_json()
        layout = build_layout_plan(document)
        original_regions = [(region.kind, [block.id for block in region.blocks]) for region in layout.pages[0].regions]
        self.assertGreater(len(original_regions), 1)
        self.assertIn("two_col", [kind for kind, _ in original_regions])

        result = render(document)

        expected = [block.id for block in document.blocks]
        self.assertEqual([block_id for operation in result.plan.operations if operation.kind == "block"
            for block_id in operation.block_ids], expected)
        root = self.assert_trace_order(document, result, expected)
        paragraphs = [text_content(node) for node in root.findall("./w:body/w:p", NS) if text_content(node)]
        self.assertEqual(paragraphs, [block.text if block.type != "formula" else "x2" for block in document.blocks])
        self.assertLess(paragraphs.index("下方主题的开头，"), paragraphs.index("续接上面的主题。"))
        self.assertEqual(len(root.findall(".//w:br[@w:type='column']", NS)), 1)
        self.assertEqual(len(root.findall(".//w:cols[@w:num='2']", NS)), 1)
        self.assertEqual(root.find("./w:body/w:sectPr/w:cols", NS).get(qn("w:num")), "1")
        self.assertEqual([section.columns for section in result.plan.sections], ["inherit", 2, 1])
        self.assertEqual([section.start_kind for section in result.plan.sections], ["initial", "continuous", "continuous"])
        self.assertFalse(root.findall(".//w:tbl", NS))
        evidence = build_renderer_evidence(document, result.content, layout, render_result=result)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["render_trace_status"], "complete")
        self.assertEqual(evidence["layout_region_count"], len(original_regions))
        self.assertEqual([(region.kind, [block.id for block in region.blocks]) for region in layout.pages[0].regions], original_regions)
        self.assertEqual(document.model_dump_json(), before)

    def test_merged_cross_column_and_cross_page_text_keeps_empty_donor_inventory(self):
        document = fragmented_document()
        document.blocks[3].text += "跨栏合并尾句。跨页合并尾句。"
        document.blocks[4].text = ""
        following = fragmented_document()
        for block in following.blocks:
            block.id = "next_" + block.id
            block.order += len(document.blocks)
            block.page_index = block.layout.page_index = 1
        following.blocks[0].type, following.blocks[0].text = "paragraph", ""
        document.blocks.extend(following.blocks)
        document.pages.append(DocumentIRPage(index=1, width=400, height=600))

        result = render(document)

        expected = [block.id for block in document.blocks]
        self.assertEqual(Counter(block_id for operation in result.plan.operations if operation.kind == "block"
            for block_id in operation.block_ids), Counter(expected))
        root = self.assert_trace_order(document, result, expected)
        visible = text_content(root)
        for phrase in ("跨栏合并尾句。", "跨页合并尾句。"):
            self.assertEqual(visible.count(phrase), 1)
        records = {record.block_id: record for record in result.block_evidence.block_render_map}
        for block_id in ("right_continuation", "next_left_heading"):
            self.assertEqual(records[block_id].disposition, "rendered")
            self.assertEqual(records[block_id].reason_code, "empty_content")
            self.assertFalse(records[block_id].content_visible)
        self.assertEqual(len(root.findall(".//w:br[@w:type='column']", NS)), 2)
        ensure_renderer_integrity(build_renderer_evidence(document, result.content, render_result=result))

    def test_semantic_page_break_uses_scheduled_left_start_instead_of_geometric_right_heading(self):
        for left_type in ("heading", "paragraph"):
            with self.subTest(left_type=left_type):
                document = fragmented_document()
                document.blocks[0].type = left_type
                document.blocks[0].level = 1 if left_type == "heading" else None
                document.blocks[4].type, document.blocks[4].level = "heading", 1
                document.blocks[4].text = "右栏起始标题"
                document.blocks[4].layout.bbox = (220, 20, 390, 45)
                for block in document.blocks:
                    block.order += 1
                    block.page_index = block.layout.page_index = 1
                document.blocks.insert(0, body("previous_page", 0, "前页正文。", (10, 60, 390, 100), "wide"))
                document.pages.append(DocumentIRPage(index=1, width=400, height=600))
                layout = build_layout_plan(document)
                self.assertEqual(layout.pages[1].regions[0].blocks[0].id, "right_continuation")
                self.assertIn("two_col", [region.kind for region in layout.pages[1].regions])

                result = render(document)

                root = self.assert_trace_order(document, result, [block.id for block in document.blocks])
                expected = ["left_heading"] if left_type == "heading" else []
                self.assertEqual([decision.block_id for decision in result.plan.decisions if decision.page_break_before], expected)
                paragraphs = root.findall("./w:body/w:p", NS)
                break_paragraphs = [node for node in paragraphs if node.find("./w:pPr/w:pageBreakBefore", NS) is not None]
                self.assertEqual([text_content(node) for node in break_paragraphs], ["左栏起始"] if expected else [])
                right_heading = next(node for node in paragraphs if text_content(node) == "右栏起始标题")
                self.assertIsNone(right_heading.find("./w:pPr/w:pageBreakBefore", NS))
                column_breaks = [node for node in paragraphs if node.find(".//w:br[@w:type='column']", NS) is not None]
                self.assertEqual(len(column_breaks), 1)
                self.assertTrue(all(paragraphs.index(node) < paragraphs.index(column_breaks[0]) for node in break_paragraphs))
                self.assertFalse(root.findall(".//w:br[@w:type='page']", NS))
                ensure_renderer_integrity(build_renderer_evidence(document, result.content, layout, render_result=result))

    def test_ineligible_pages_preserve_existing_plan_and_xml(self):
        cases = []
        for hint in ("wide", None):
            document = fragmented_document()
            document.blocks[2].layout.column_hint = hint
            cases.append((f"hint_{hint}", document))
        document = fragmented_document()
        document.blocks[2].layout = None
        cases.append(("missing_layout", document))
        for block_type in ("table", "image", "list"):
            document = fragmented_document()
            block = document.blocks[2]
            block.type, block.text = block_type, None
            if block_type == "table":
                block.html = "<table><tr><td>中性数据</td></tr></table>"
            elif block_type == "list":
                block.list_items = ["保留列表项"]
            else:
                block.asset_ref = "neutral_image"
                document.assets = [DocumentIRAsset(id="neutral_image", kind="image", source_path="neutral.png")]
            cases.append((block_type, document))
        for name, indices in (("alternating_columns", [0, 1, 4, 2, 3, 5, 6, 7]),
                              ("right_before_left", [4, 5, 6, 7, 0, 1, 2, 3])):
            document = fragmented_document()
            document.blocks = [document.blocks[index] for index in indices]
            for index, block in enumerate(document.blocks):
                block.order = index
            cases.append((name, document))
        document = fragmented_document()
        document.pages[0].width = None
        cases.append(("missing_page_width", document))
        document = fragmented_document()
        for block in document.blocks:
            block.layout.bbox = None
        cases.append(("missing_geometry", document))
        document = fragmented_document()
        document.blocks = [
            body("upper_left", 0, "上左", (10, 60, 180, 120), "left"),
            body("upper_right", 1, "上右", (220, 65, 390, 125), "right"),
            body("single_column_gap", 2, "单栏过渡", (10, 170, 180, 230), "left"),
            body("lower_left", 3, "下左", (10, 310, 180, 400), "left"),
            body("lower_right", 4, "下右", (220, 315, 390, 400), "right"),
        ]
        cases.append(("real_single_column_gap", document))

        for name, document in cases:
            with self.subTest(name=name):
                with patch(OLD_SCHEDULER, return_value=None):
                    previous = render(document)
                current = render(document)
                self.assertEqual(current.plan.model_dump(mode="json"), previous.plan.model_dump(mode="json"))
                self.assertEqual(ET.tostring(document_xml(current.content)), ET.tostring(document_xml(previous.content)))
                self.assertEqual(current.block_evidence.block_render_map, previous.block_evidence.block_render_map)

    def test_persisted_v2_content_and_frozen_trace_accept_previous_column_schedule(self):
        document = fragmented_document()
        for block in document.blocks:
            block.order += 1
            block.page_index = block.layout.page_index = 1
        table = body("content_table", 0, None, (10, 60, 390, 120), "wide", block_type="table")
        table.html = "<table><tr><td>项目</td><td>数值</td></tr><tr><td>示例</td><td>1</td></tr></table>"
        document.blocks.insert(0, table)
        document.pages.append(DocumentIRPage(index=1, width=400, height=600))
        layout = build_layout_plan(document)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # 在夹具生成阶段冻结修复前的真实 writer 输出；恢复阶段不再启用旧调度补丁。
            with patch(OLD_SCHEDULER, return_value=None):
                old_result = render(document)
                old_evidence = build_renderer_evidence(document, old_result.content, layout, render_result=old_result)
                ensure_renderer_integrity(old_evidence)
            (root / "previous.docx").write_bytes(old_result.content)
            (root / "previous-ir.json").write_text(document.model_dump_json(), encoding="utf-8")
            (root / "previous-evidence.json").write_text(json.dumps(old_evidence, ensure_ascii=False), encoding="utf-8")

            current = render(document)
            stored_content = (root / "previous.docx").read_bytes()
            stored_ir = DocumentIR.model_validate_json((root / "previous-ir.json").read_text(encoding="utf-8"))
            stored_evidence = json.loads((root / "previous-evidence.json").read_text(encoding="utf-8"))
            restored = validate_persisted_renderer_content(stored_ir, stored_content, stored_evidence)

            old_paragraphs = [text_content(node) for node in document_xml(stored_content).findall("./w:body/w:p", NS)]
            self.assertLess(old_paragraphs.index("续接上面的主题。"), old_paragraphs.index("下方主题的开头，"))
            self.assertNotEqual(current.plan.operations, old_result.plan.operations)
            self.assertEqual(current.plan.table_units, old_result.plan.table_units)
            self.assertEqual([operation for operation in current.plan.operations if operation.kind == "logical_table"],
                [operation for operation in old_result.plan.operations if operation.kind == "logical_table"])
            self.assertEqual(restored["renderer_content_contract_version"], "renderer-content/v2")
            self.assertEqual(restored["render_trace_status"], "complete")
            self.assertEqual(restored["render_plan"], stored_evidence["render_plan"])
            self.assertEqual(restored["block_render_evidence"], stored_evidence["block_render_evidence"])
            self.assertEqual(restored["layout_region_count"], sum(len(page.regions) for page in layout.pages))
            self.assertEqual(stored_content, old_result.content)
            self.assertEqual((root / "previous.docx").read_bytes(), old_result.content)


if __name__ == "__main__":
    unittest.main()
