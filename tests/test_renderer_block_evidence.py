"""RND-501 的实际对象归属、共享、失败与安全投影合同。"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import yaml
from docx import Document
from docx.oxml.ns import qn

from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIRAsset, DocumentIRBlock, DocumentIRBlockLayout, DocumentIRPage
from app.services.renderer.block_evidence import BlockRenderEvidence, PackageIndex
from app.services.renderer.block_anchors import block_bookmark_name
from app.services.renderer.evidence import (build_renderer_evidence, build_renderer_aggregate_evidence,
    build_renderer_event_summary, controlled_quality_flags, ensure_renderer_integrity, validate_render_result)
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.renderer.image_evidence import image_anchor
from tests.test_image_group_rendering import image_ir, image_loader
from tests.test_renderer_render_plan import make_ir, render
from tests.test_document_ir_word_renderer_layout import MINIMAL_PNG_BYTES
from tests.test_document_ir_logical_table_group import convert_payload, table


def paired_image_ir(left_caption, right_caption):
    ir = make_ir([DocumentIRBlock(id=side, type="image", order=i, asset_ref=side,
        captions=[caption] if caption is not None else [],
        layout=DocumentIRBlockLayout(page_index=0, bbox=bbox, column_hint=side))
        for i, (side, caption, bbox) in enumerate((("left", left_caption, (0, 20, 170, 120)),
            ("right", right_caption, (220, 20, 390, 120))))])
    ir.schema_version = "document-ir/v2"
    ir.pages = [DocumentIRPage(index=0, width=400.0, height=600.0)]
    ir.assets = [DocumentIRAsset(id=side, kind="image", source_path=side+".png") for side in ("left", "right")]
    return ir


class BlockEvidenceTests(TestCase):
    def assert_bound(self, ir, result):
        evidence = build_renderer_evidence(ir, result.content, render_result=result)
        ensure_renderer_integrity(evidence)
        self.assertEqual(evidence["block_render_evidence"]["docx_sha256"], hashlib.sha256(result.content).hexdigest())
        self.assertEqual(BlockRenderEvidence.model_validate_json(result.block_evidence.model_dump_json()), result.block_evidence)
        return {record.block_id: record for record in result.block_evidence.block_render_map}

    def test_all_body_objects_annotations_and_empty_objects_keep_exact_owners(self):
        ir = make_ir([
            DocumentIRBlock(id="heading", type="heading", order=0, text="1 Overview"),
            DocumentIRBlock(id="body", type="paragraph", order=1, text="Visible paragraph with retained semantic content."),
            DocumentIRBlock(id="list", type="list", order=2, list_items=["First item", ""]),
            DocumentIRBlock(id="formula", type="formula", order=3, latex=r"\frac{a}{b}"),
            DocumentIRBlock(id="table", type="table", order=4, html="<table><tr><th>Parameter</th><th>Value</th></tr><tr><td>Voltage</td><td>5 V</td></tr></table>",
                captions=["Table 1 Parameters", "VCC = 5 V, TA = 25°C"], footnotes=["Note: retained source table note."]),
            DocumentIRBlock(id="image", type="image", order=5, asset_ref="asset", captions=["Figure 1 Example", "Extra annotation"], footnotes=["Image note"]),
            *[DocumentIRBlock(id=kind+"_empty", type=kind, order=6+i) for i, kind in enumerate(("paragraph", "heading"))],
            DocumentIRBlock(id="empty_list", type="list", order=9, list_items=[]),
        ])
        ir.assets = [DocumentIRAsset(id="asset", kind="image", source_path="image.png")]
        before = ir.model_dump_json()
        result = render(ir, image_loader=lambda asset: MINIMAL_PNG_BYTES)
        records = self.assert_bound(ir, result)
        self.assertEqual(ir.model_dump_json(), before)
        self.assertEqual(set(records), {b.id for b in ir.blocks})
        self.assertEqual([t.role for t in records["table"].targets], ["caption", "context", "table", "note"])
        self.assertEqual([t.role for t in records["image"].targets], ["image", "caption", "caption", "caption"])
        self.assertEqual([t.item_index for t in records["list"].targets], [0, 1])
        for kind in ("paragraph", "heading"):
            record = records[kind+"_empty"]
            self.assertEqual((record.disposition, record.reason_code, record.content_visible), ("rendered", "empty_content", False))
            self.assertEqual(record.targets[0].element_kind, "paragraph")
        self.assertEqual((records["empty_list"].disposition, records["empty_list"].reason_code, records["empty_list"].targets), ("not_emitted", "empty_list", []))
        self.assertEqual(records["table"].bookmark_name, block_bookmark_name(records["table"].anchor_ref))
        self.assertIn("_md2word_table_1", records["table"].targets[0].bookmark_names)
        self.assertEqual(records["image"].bookmark_name, image_anchor("image", "captions/0"))
        self.assertEqual(records["body"].bookmark_name, block_bookmark_name(records["body"].anchor_ref))
        self.assertTrue(all(r.word_page is None for r in records.values()))
        self.assertNotIn(b"render-block:", result.content)

    def test_toc_coalesces_only_entries_and_keeps_mixed_list_items(self):
        ir = make_ir([
            DocumentIRBlock(id="first", type="paragraph", order=0, text="1 Overview ........ 3"),
            DocumentIRBlock(id="mixed", type="list", order=1, list_items=["2 Detail ........ 4", "Normal list item", ""]),
            DocumentIRBlock(id="last", type="paragraph", order=2, text="3 Summary ........ 8"),
        ])
        result = render(ir)
        records = self.assert_bound(ir, result)
        self.assertEqual(records["last"].disposition, "coalesced")
        self.assertEqual([i.disposition for i in records["mixed"].items], ["coalesced", "rendered", "rendered"])
        self.assertEqual(records["mixed"].disposition, "rendered")
        representative = records["first"].targets[0].child_path
        self.assertEqual(records["last"].targets[0].child_path, representative)
        index = PackageIndex(result.content)
        node = index.nodes["word/document.xml", tuple(representative)]
        self.assertEqual(len([n for n in node.iter(qn("w:instrText")) if "TOC" in (n.text or "")]), 1)
        self.assertIn("Normal list item", [p.text for p in Document(io.BytesIO(result.content)).paragraphs])

    def test_grouped_three_cells_and_all_annotations_have_individual_owners(self):
        ir = image_ir(count=3)
        result = render(ir, image_loader=image_loader)
        records = self.assert_bound(ir, result)
        index = PackageIndex(result.content)
        owners = []
        for block in ir.blocks:
            record = records[block.id]
            self.assertEqual([target.role for target in record.targets], ["image", "caption", "caption", "caption"])
            self.assertEqual([target.element_kind for target in record.targets], ["drawing", "paragraph", "paragraph", "paragraph"])
            nodes = [index.nodes[target.part, tuple(target.child_path)] for target in record.targets]
            cells = [next(node.iterancestors(qn("w:tc"))) for node in nodes]
            self.assertTrue(all(cell is cells[0] for cell in cells))
            owners.append(cells[0])
            self.assertEqual(record.bookmark_name, image_anchor(block.id, "captions/0"))
            self.assertEqual(record.targets[1].actual["math_object_count"], 1)
        self.assertEqual(len(set(owners)), 3)
        self.assertEqual([operation.block_ids for operation in result.plan.operations if operation.kind == "block"], [[block.id for block in ir.blocks]])
        metadata = build_renderer_evidence(ir, result.content, render_result=result)
        self.assertEqual(metadata["content_table_count"], 0)
        self.assertEqual(metadata["layout_table_count"], 1)
        self.assertEqual(len(result.formula_report["entries"]), 3)

    def test_cell_math_captions_reject_missing_swapped_or_foreign_owners(self):
        for caption in (r"\frac{a}{b}", "Gain $x+y$"):
            with self.subTest(caption=caption):
                ir = paired_image_ir(caption, caption)
                result = render(ir, image_loader=lambda asset: MINIMAL_PNG_BYTES)
                records = self.assert_bound(ir, result)
                index = PackageIndex(result.content)
                actual_math = list(index.roots["word/document.xml"].iter(qn("m:oMath")))
                self.assertEqual(len(actual_math), 2)
                for number, side in enumerate(("left", "right")):
                    target = records[side].targets[1]
                    self.assertEqual((target.element_kind, target.role, target.item_index), ("paragraph", "caption", 0))
                    self.assertEqual(list(index.nodes[target.part, tuple(target.child_path)].iter(qn("m:oMath"))), [actual_math[number]])
                for failure in ("drop_caption", "swap_caption", "swap_all", "math_kind_on_drawing", "image_paragraph_as_caption"):
                    with self.subTest(failure=failure):
                        trace = result.block_evidence.model_copy(deep=True)
                        left, right = trace.block_render_map
                        if failure == "drop_caption":
                            left.targets.pop()
                            trace.counts["target_count"] -= 1
                        elif failure == "swap_caption":
                            left.targets[1], right.targets[1] = right.targets[1], left.targets[1]
                        elif failure == "swap_all":
                            left.targets, right.targets = right.targets, left.targets
                        elif failure == "math_kind_on_drawing":
                            left.targets[0].element_kind = "math"
                        else:
                            drawing = index.nodes[left.targets[0].part, tuple(left.targets[0].child_path)]
                            paragraph = next(drawing.iterancestors(qn("w:p")))
                            part, path = index.paths[paragraph]
                            kind, actual, bookmarks = index.project(part, path)
                            left.targets[1] = left.targets[1].model_copy(update={"part": part, "child_path": list(path),
                                "element_kind": kind, "actual": actual, "bookmark_names": bookmarks})
                        with self.assertRaises(DocumentIntegrityError):
                            validate_render_result(ir, result.content, replace(result, block_evidence=trace))

    def test_cell_caption_tabs_empty_sides_and_runtime_ownership_are_preserved(self):
        for left, right in ((None, None), ("Gain $x+y$", None), (None, r"\frac{a}{b}"),
                ("A\tX", "B"), ("A", "Y\tB")):
            with self.subTest(left=left, right=right):
                ir = paired_image_ir(left, right)
                result = render(ir, image_loader=lambda asset: MINIMAL_PNG_BYTES)
                records = self.assert_bound(ir, result)
                index = PackageIndex(result.content)
                for side, caption in (("left", left), ("right", right)):
                    targets = [target for target in records[side].targets if target.role == "caption"]
                    self.assertEqual(len(targets), int(caption is not None))
                    if caption is not None:
                        node = index.nodes[targets[0].part, tuple(targets[0].child_path)]
                        self.assertEqual(len(list(node.iter(qn("w:tab")))), int("\t" in caption))
                with self.assertRaises(DocumentIntegrityError):
                    validate_render_result(ir, result.content, replace(result, _ownership=None))
                with self.assertRaises(FrozenInstanceError):
                    result._ownership.docx_sha256 = "0" * 64
                self.assertIsInstance(result._ownership.images[0].targets, tuple)
                self.assertNotIn("_ownership", json.dumps(build_renderer_evidence(ir, result.content, render_result=result)))

    def test_linked_physical_decoration_replacement_survives_orientation_and_columns(self):
        blocks = []
        for page in range(3):
            for i, role in enumerate(("page_header", "page_header", "page_footer", "page_number")):
                blocks.append(DocumentIRBlock(id=f"d{page}_{i}", type="paragraph", order=len(blocks), text=f"Decoration {page} {i}",
                    layout=DocumentIRBlockLayout(page_index=page, role=role)))
            for side, bbox in (("left", (0, 30, 170, 130)), ("right", (220, 30, 390, 130))):
                blocks.append(DocumentIRBlock(id=f"body{page}_{side}", type="paragraph", order=len(blocks), text=f"Body {page} {side} retains editable text.",
                    layout=DocumentIRBlockLayout(page_index=page, bbox=bbox, column_hint=side)))
        ir = make_ir(blocks)
        ir.schema_version = "document-ir/v2"
        ir.pages = [DocumentIRPage(index=i, width=400.0 if i != 1 else 700.0, height=600.0) for i in range(3)]
        config = TemplateConfigPackage(header={"enabled": True}, footer={"enabled": True})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(yaml.safe_dump(config.model_dump(mode="json")), encoding="utf-8")
            result = render(ir, config_path=path)
        records = self.assert_bound(ir, result)
        for page in (0, 1):
            for i in range(4):
                self.assertEqual((records[f"d{page}_{i}"].disposition, records[f"d{page}_{i}"].targets), ("superseded", []))
        for a, b in (("d2_0", "d2_1"), ("d2_2", "d2_3")):
            left, right = records[a].targets[0], records[b].targets[0]
            self.assertEqual((left.part, left.child_path, left.sharing_group), (right.part, right.child_path, right.sharing_group))
            self.assertEqual((left.participant_order, right.participant_order), (0, 1))
            self.assertEqual(left.actual["referenced_section_indices"], list(range(len(result.plan.sections))))

    def test_disabled_and_custom_footer_are_suppressed_without_targets(self):
        ir = make_ir([DocumentIRBlock(id=role, type="paragraph", order=i, text="Source decoration",
            layout=DocumentIRBlockLayout(page_index=0, role=role)) for i, role in enumerate(("page_header", "page_footer", "page_number"))])
        ir.schema_version = "document-ir/v2"
        ir.pages = [DocumentIRPage(index=0)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(yaml.safe_dump(TemplateConfigPackage(footer={"enabled": True, "left_text": "Custom"}).model_dump(mode="json")), encoding="utf-8")
            result = render(ir, config_path=path)
        records = self.assert_bound(ir, result)
        self.assertEqual(records["page_header"].reason_code, "decoration_disabled")
        for role in ("page_footer", "page_number"):
            self.assertEqual((records[role].disposition, records[role].reason_code, records[role].targets), ("suppressed", "custom_footer", []))

    def test_verified_empty_fragments_project_to_original_owner_only(self):
        ir = convert_payload([table(0, "1"), {"type": "table_placeholder", "page_idx": 1, "bbox": [10, 10, 90, 50]}])
        before = ir.model_dump_json()
        result = render(ir)
        record = self.assert_bound(ir, result)[ir.blocks[0].id]
        self.assertEqual(record.provenance.status, "verified_ir205")
        self.assertEqual(len(record.provenance.fragment_ids), 2)
        self.assertEqual(len(record.provenance.source_spans), 2)
        self.assertEqual(len([t for t in record.targets if t.element_kind == "table"]), 1)
        self.assertEqual(ir.model_dump_json(), before)
        legacy = make_ir([DocumentIRBlock(id="legacy", type="paragraph", order=0, text="Legacy source remains unknown.", metadata={"source_spans": [{"json_pointer": "/forged"}]})])
        self.assertEqual(render(legacy).block_evidence.block_render_map[0].provenance.status, "unavailable")
        self.assertEqual(render(legacy).block_evidence.block_render_map[0].provenance.source_spans, [])

    def test_invalid_binding_missing_owner_and_forged_or_swapped_targets_fail_closed(self):
        ir = make_ir([DocumentIRBlock(id="a", type="paragraph", order=0, text="First retained paragraph."), DocumentIRBlock(id="b", type="paragraph", order=1, text="Second retained paragraph.")])
        result = render(ir)
        for failure in ("hash", "missing", "locator", "swap", "sharing", "nan"):
            with self.subTest(failure=failure):
                trace = result.block_evidence.model_copy(deep=True)
                if failure == "hash":
                    trace.docx_sha256 = "0" * 64
                elif failure == "missing":
                    trace.block_render_map.pop()
                elif failure == "locator":
                    trace.block_render_map[0].targets[0].child_path = [0, 999]
                elif failure == "swap":
                    trace.block_render_map[0].targets, trace.block_render_map[1].targets = trace.block_render_map[1].targets, trace.block_render_map[0].targets
                elif failure == "sharing":
                    trace.block_render_map[0].targets[0].sharing_group = "forged"
                else:
                    trace.block_render_map[0].targets[0].actual["bad"] = float("nan")
                with self.assertRaises(DocumentIntegrityError) as raised:
                    validate_render_result(ir, result.content, replace(result, block_evidence=trace))
                self.assertNotIn('"block_render_map"', str(raised.exception.evidence))
        evidence = build_renderer_evidence(ir, result.content)
        self.assertEqual(evidence["render_trace_status"], "unavailable")
        self.assertNotIn("render_trace_status", build_renderer_aggregate_evidence(ir, result.content))

    def test_safe_projection_retains_report_and_counts_without_free_values(self):
        ir = convert_payload([{"type": "text", "text": "This body must never appear in renderer events.", "page_idx": 0}])
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, render_result=result)
        canary = "PRIVATE_CANARY_BODY_OR_PATH"
        evidence["layout_missing_block_ids"] = [canary]
        evidence["layout_quality_flags"] += [canary]
        evidence["source_integrity"]["ir_source_type_counts"][canary] = 2
        evidence["docx_quality"]["latex_residue_examples"] = [canary]
        evidence["object_key"] = canary
        evidence["unknown_metadata"] = canary
        evidence["mineru_validation"]["inventory"]["secret"] = canary
        evidence["mineru_validation"]["warnings"][0]["facts"]["secret"] = canary
        summary = build_renderer_event_summary(evidence)
        self.assertNotIn(canary, json.dumps(summary))
        self.assertEqual(build_renderer_event_summary(summary), summary)
        self.assertNotIn("render_plan", summary)
        self.assertNotIn("block_render_evidence", summary)
        self.assertEqual(summary["layout_missing_block_count"], 1)
        self.assertEqual(summary["source_integrity"]["ir_source_type_counts"]["unknown"], 2)
        self.assertEqual(summary["mineru_validation"]["warning_count"], evidence["mineru_validation"]["warning_count"])
        self.assertEqual(summary["mineru_validation"]["warnings"][0]["code"], "mineru_bbox_missing")
        self.assertEqual(controlled_quality_flags([canary, "ir_docx_integrity:table_count_mismatch", "docx_latex_residue:2"]), ["ir_docx_integrity:table_count_mismatch", "docx_latex_residue:2"])
        evidence["blocking_quality_flags"] = [canary, "ir_docx_integrity:table_count_mismatch"]
        with self.assertRaises(DocumentIntegrityError) as raised:
            ensure_renderer_integrity(evidence)
        self.assertNotIn(canary, str(raised.exception))
        self.assertNotIn(canary, json.dumps(raised.exception.evidence))

    def test_private_trace_preserves_original_block_ids_and_toc_references(self):
        canary = "PRIVATE_BLOCK_ID_WITH_SOURCE_PATH"
        first, second = canary + "/first", canary + "/second"
        ir = make_ir([
            DocumentIRBlock(id=first, type="paragraph", order=0, text="1 Overview ........ 3"),
            DocumentIRBlock(id=second, type="paragraph", order=1, text="2 Details ........ 4"),
        ])
        result = render(ir)
        evidence = build_renderer_evidence(ir, result.content, render_result=result)
        self.assertEqual([record.block_id for record in result.block_evidence.block_render_map], [first, second])
        self.assertEqual(result.block_evidence.block_render_map[1].representative_block_id, first)
        self.assertEqual(result.plan.decisions[1].text_policies[0].representative_block_id, first)
        self.assertIn(canary, json.dumps(evidence))
        self.assertNotIn(canary, json.dumps(build_renderer_event_summary(evidence)))
