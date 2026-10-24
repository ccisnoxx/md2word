"""RND-505 页推断、证据等级、有界合同及局部读取失败。"""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.services.document_ir.models import DocumentIRBlock, DocumentIRBlockLayout, DocumentIRPage
from app.services.preview import page_mapping as mapper
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.renderer.block_evidence import SourceProjection
from app.services.renderer.evidence import build_renderer_evidence, validate_persisted_render_evidence, validate_render_result
from tests.test_renderer_render_plan import make_ir, render


def mapping_result(pages=(0, 1, 2), *, order=None, kinds=None):
    blocks = [DocumentIRBlock(id=f"b{i}", type=(kinds or {}).get(i, "paragraph"), order=i,
        text=f"Editable source paragraph {i}.", layout=DocumentIRBlockLayout(page_index=page,
        bbox=(0, 30 * i, 100, 30 * i + 20))) for i, page in enumerate(pages)]
    ir = make_ir([blocks[index] for index in order] if order is not None else blocks)
    ir.schema_version = "document-ir/v2"
    ir.pages = [DocumentIRPage(index=page, width=400.0, height=600.0) for page in sorted(set(pages))]
    return render(ir)


def binding_for(result, pages=5, **changes):
    values = dict(source_pdf_file_id="source", document_ir_file_id="ir", input_ir_sha256=result.plan.input_ir_sha256,
        plan_sha256=result.plan.plan_sha256, source_generation=0, result_file_id="result",
        docx_sha256="sha256:" + result.block_evidence.docx_sha256, run_id="run", attempt=1,
        profile_sha256="sha256:" + "0" * 64, preview_pdf_file_id="pdf", preview_pdf_sha256="sha256:" + "1" * 64,
        page_count=pages)
    values.update(changes)
    return mapper.MappingBinding(**values)


def mapped(result, pages=5, *, trace=None, proof=True, binding=None):
    return mapper.build_page_mapping(binding=binding or binding_for(result, pages), plan=result.plan,
        block_evidence=trace or result.block_evidence,
        block_anchor_evidence=result.block_anchor_evidence if proof else None)


def locations(value):
    return {entry["block_id"]: entry["location"] for entry in value["entries"]}


class PreviewPageMappingTests(TestCase):
    def test_persisted_toc_representative_must_match_policy_and_real_owner(self):
        ir = make_ir([
            DocumentIRBlock(id="first", type="paragraph", order=0, text="1 Overview ........ 3"),
            DocumentIRBlock(id="mixed", type="list", order=1,
                list_items=["2 Detail ........ 4", "Normal list item", "3 Summary ........ 8"]),
            DocumentIRBlock(id="merged", type="paragraph", order=2, text="4 Appendix ........ 9"),
            DocumentIRBlock(id="tail", type="paragraph", order=3, text="Ordinary body tail."),
        ])
        result = render(ir)
        restored = validate_persisted_render_evidence(ir, result.content,
            render_plan=result.plan, block_render_evidence=result.block_evidence)
        self.assertIsNotNone(restored)
        value = mapped(result)
        entries = {entry["block_id"]: entry for entry in value["entries"]}
        self.assertEqual([entries[block]["location"]["preview_page_index"]
            for block in ("first", "mixed", "merged", "tail")], [0, 2, 0, 4])
        self.assertEqual(entries["merged"]["bookmark_name"], entries["first"]["bookmark_name"])
        self.assertEqual(entries["mixed"]["disposition"], "rendered")
        self.assertEqual(entries["mixed"]["representative_block_id"], "first")
        self.assertNotEqual(entries["mixed"]["bookmark_name"], entries["first"]["bookmark_name"])
        for block_id, field, value in (("merged", "representative_block_id", "tail"),
                ("merged", "representative_block_id", None), ("merged", "representative_block_id", "missing"),
                ("mixed", "representative_block_id", "tail"), ("mixed", "representative_block_id", None),
                ("first", "representative_block_id", "tail"), ("merged", "disposition", "rendered"),
                ("mixed", "disposition", "coalesced")):
            with self.subTest(block_id=block_id, field=field, value=value):
                trace = result.block_evidence.model_copy(deep=True)
                record = next(record for record in trace.block_render_map if record.block_id == block_id)
                if field == "disposition":
                    trace.counts[record.disposition] -= 1
                    trace.counts[value] += 1
                setattr(record, field, value)
                self.assertTrue(validate_persisted_render_evidence(ir, result.content,
                    render_plan=result.plan, block_render_evidence=trace) is None, "记录归属或状态与实际策略不符时不得认证。")
                restored = build_renderer_evidence(ir, result.content, render_plan=result.plan,
                    block_render_evidence=trace, block_anchor_evidence=result.block_anchor_evidence,
                    formula_report=result.formula_report, image_layout_report=result.image_layout_report)
                self.assertEqual(restored["render_trace_status"], "unavailable")
                self.assertNotIn("block_anchor_evidence", restored)
                unavailable = mapper.build_page_mapping(binding=binding_for(result), plan=restored.get("render_plan"),
                    block_evidence=restored.get("block_render_evidence"), block_anchor_evidence=restored.get("block_anchor_evidence"))
                self.assertEqual((unavailable["status"], unavailable["reason_code"], unavailable["entries"]),
                    ("unavailable", "legacy_evidence_missing", []))
                with self.assertRaises(DocumentIntegrityError):
                    validate_render_result(ir, result.content, replace(result, block_evidence=trace))

    def test_mixed_toc_list_can_be_its_own_representative(self):
        ir = make_ir([
            DocumentIRBlock(id="mixed", type="list", order=0,
                list_items=["1 Overview ........ 3", "Normal list item", "2 Detail ........ 4"]),
            DocumentIRBlock(id="merged", type="paragraph", order=1, text="3 Appendix ........ 8"),
            DocumentIRBlock(id="tail", type="paragraph", order=2, text="Ordinary body tail."),
        ])
        result = render(ir)
        restored = validate_persisted_render_evidence(ir, result.content,
            render_plan=result.plan, block_render_evidence=result.block_evidence)
        self.assertIsNotNone(restored)
        record = result.block_evidence.block_render_map[0]
        self.assertEqual((record.disposition, record.representative_block_id), ("rendered", "mixed"))
        entries = {entry["block_id"]: entry for entry in mapped(result)["entries"]}
        self.assertEqual(entries["mixed"]["bookmark_name"], entries["merged"]["bookmark_name"])
        self.assertEqual([entries[block]["location"]["preview_page_index"]
            for block in ("mixed", "merged", "tail")], [0, 0, 4])

    def test_sparse_source_rank_ratio_keeps_low_confidence_and_null_range(self):
        result = mapping_result((2, 8, 15))
        value = mapped(result)
        self.assertEqual([e["location"]["preview_page_index"] for e in value["entries"]], [0, 2, 4])
        self.assertEqual(value["status"], "degraded")
        for entry in value["entries"]:
            self.assertEqual((entry["location"]["kind"], entry["location"]["confidence"], entry["location"]["reason_code"]),
                             ("estimated_start", "low", "source_page_ratio"))
            self.assertIsNone(entry["location"]["page_range"])
            self.assertEqual(entry["source"]["provenance_status"], "legacy_layout")
        self.assertEqual(mapper.read_page_mapping(value, binding=binding_for(result)), value)

    def test_single_source_page_uses_real_output_order_even_when_ir_array_differs(self):
        result = mapping_result((0, 0, 0), order=(2, 0, 1))
        self.assertEqual([r.block_id for r in result.block_evidence.block_render_map], ["b2", "b0", "b1"])
        value = mapped(result)
        self.assertEqual([entry["block_id"] for entry in value["entries"]], ["b0", "b1", "b2"])
        self.assertEqual([entry["location"]["preview_page_index"] for entry in value["entries"]], [0, 2, 4])
        self.assertTrue(all(entry["location"]["reason_code"] == "source_page_rank_degenerate" for entry in value["entries"]))

    def test_nearest_output_distance_tie_uses_previous_direct_owner(self):
        result = mapping_result()
        trace = result.block_evidence.model_copy(deep=True)
        trace.block_render_map[1].provenance = SourceProjection(status="unavailable")
        value = mapped(result, trace=trace)
        middle = locations(value)["b1"]
        self.assertEqual((middle["preview_page_index"], middle["reason_code"], middle["nearest_block_id"]), (0, "nearest_output", "b0"))
        self.assertEqual(value["entries"][1]["source"]["provenance_status"], "unavailable")

    def test_no_source_candidates_ratio_uses_lower_page_on_midpoint(self):
        result = mapping_result()
        trace = result.block_evidence.model_copy(deep=True)
        for record in trace.block_render_map:
            record.provenance = SourceProjection(status="unavailable")
        value = mapped(result, pages=2, trace=trace)
        self.assertEqual([entry["location"]["preview_page_index"] for entry in value["entries"]], [0, 0, 1])
        self.assertTrue(all(e["location"]["reason_code"] == "output_order_ratio" for e in value["entries"]))
        solo = mapping_result((0,))
        self.assertEqual(mapped(solo)["entries"][0]["location"]["preview_page_index"], 0)

    def test_single_page_only_certifies_real_body_targets_and_anchor_is_independent(self):
        result = mapping_result()
        present, missing = mapped(result, pages=1), mapped(result, pages=1, proof=False)
        self.assertEqual(present["status"], "available")
        self.assertEqual(missing["status"], "degraded")
        for entry in missing["entries"]:
            self.assertEqual((entry["bookmark_name"], entry["anchor_reason_code"]), (None, "anchor_missing"))
            self.assertEqual((entry["location"]["preview_page_index"], entry["location"]["confidence"]), (0, "high"))
        self.assertEqual(present["entries"][0]["source"], missing["entries"][0]["source"])

    def test_suppressed_and_decoration_entries_retain_owner_and_only_navigation_fallback(self):
        result = mapping_result()
        trace = result.block_evidence.model_copy(deep=True)
        suppressed = trace.block_render_map[1]
        suppressed.disposition, suppressed.targets = "suppressed", []
        header = trace.block_render_map[2]
        header.targets[0].part, header.targets[0].role = "word/header1.xml", "header"
        value = mapped(result, pages=1, trace=trace)
        for entry in value["entries"]:
            if entry["block_id"] == "b0":
                continue
            self.assertEqual(entry["location"], mapper._location())
            self.assertEqual((entry["fallback"]["page_index"], entry["fallback"]["confidence"]), (0, "low"))
            self.assertIsNotNone(entry["source"]["layout_page_index"])

    def test_all_nonbody_trace_retains_entries_instead_of_unknown_empty_report(self):
        result = mapping_result()
        trace = result.block_evidence.model_copy(deep=True)
        for record in trace.block_render_map:
            record.disposition, record.targets = "not_emitted", []
        value = mapped(result, trace=trace)
        self.assertEqual((value["status"], value["reason_code"], value["counts"]["total"]), ("unavailable", "no_target", 3))
        self.assertEqual(len(value["entries"]), 3)
        self.assertTrue(all(e["fallback"] is None and e["location"]["preview_page_index"] is None for e in value["entries"]))
        self.assertEqual(mapper.read_page_mapping(value, binding=binding_for(result)), value)

    def test_coalesced_uses_proven_representative_and_cycle_is_unavailable(self):
        ir = make_ir([DocumentIRBlock(id="first", type="paragraph", order=0, text="1 Overview ........ 3"),
                      DocumentIRBlock(id="last", type="paragraph", order=1, text="2 Detail ........ 4")])
        result = render(ir)
        value = mapped(result, pages=1)
        first, last = value["entries"]
        self.assertEqual(last["disposition"], "coalesced")
        self.assertEqual(last["representative_block_id"], "first")
        self.assertEqual(last["bookmark_name"], first["bookmark_name"])
        self.assertEqual(last["location"], first["location"])
        trace = result.block_evidence.model_copy(deep=True)
        trace.block_render_map[0].disposition = "coalesced"
        trace.block_render_map[0].representative_block_id = "last"
        invalid = mapped(result, trace=trace)
        self.assertEqual((invalid["status"], invalid["reason_code"]), ("unavailable", "invalid_mapping"))

    def test_missing_trace_preview_and_identities_have_small_explainable_shape(self):
        result = mapping_result()
        binding = binding_for(result)
        legacy = mapper.build_page_mapping(binding=binding, plan=None, block_evidence=None)
        self.assertEqual((legacy["reason_code"], legacy["counts"]["total"], legacy["entries"]), ("legacy_evidence_missing", None, []))
        no_preview = binding.model_copy(update={"preview_pdf_file_id": None, "preview_pdf_sha256": None, "page_count": None})
        self.assertEqual(mapped(result, binding=no_preview)["reason_code"], "preview_unavailable")
        for field, value in (("input_ir_sha256", "f"*64), ("plan_sha256", "f"*64), ("docx_sha256", "sha256:"+"f"*64)):
            with self.subTest(field=field):
                self.assertEqual(mapped(result, binding=binding.model_copy(update={field: value}))["reason_code"], "invalid_mapping")
        self.assertEqual(mapped(result, binding=binding.model_copy(update={"source_pdf_file_id": None}))["reason_code"], "legacy_evidence_missing")

    def test_reader_rejects_hash_binding_version_nonfinite_and_untrusted_count_keys(self):
        result = mapping_result()
        value, binding = mapped(result), binding_for(result)
        for field, replacement in (("source_generation", 1), ("result_file_id", "other"), ("run_id", "other"),
                                   ("attempt", 2), ("profile_sha256", "sha256:"+"f"*64),
                                   ("preview_pdf_sha256", "sha256:"+"f"*64), ("page_count", 9)):
            with self.subTest(binding=field):
                self.assertEqual(mapper.read_page_mapping(value, binding=binding.model_copy(update={field: replacement}))["reason_code"], "invalid_mapping")
        changes = [lambda v: v.update(schema_version="unknown"), lambda v: v.update(mapping_sha256="f"*64),
            lambda v: v["entries"][0]["source"].update(bbox=[float("nan")]),
            lambda v: v["counts"].update(canary=1), lambda v: v["entries"][0]["location"].update(preview_page_index=9)]
        for change in changes:
            changed = deepcopy(value)
            change(changed)
            self.assertEqual(mapper.read_page_mapping(changed, binding=binding)["status"], "unavailable")
        empty = mapper.unavailable_mapping(binding, "legacy_evidence_missing")
        empty["counts"]["canary"] = 1
        empty = mapper._seal({k: v for k, v in empty.items() if k != "mapping_sha256"})
        self.assertEqual(mapper.read_page_mapping(empty, binding=binding)["reason_code"], "invalid_mapping")
        self.assertNotIn("canary", mapper.mapping_summary(empty)["counts"])

    def test_fixed_byte_and_entry_limits_never_publish_partial_entries(self):
        result = mapping_result()
        with patch.object(mapper, "MAX_MAPPING_ENTRIES", 2):
            value = mapped(result)
            self.assertEqual((value["reason_code"], value["entries"], value["counts"]["total"]), ("limit_exceeded", [], 3))
        trace = result.block_evidence.model_copy(deep=True)
        trace.block_render_map[0].provenance.source_spans = [{"source_path": "x" * mapper.MAX_MAPPING_BYTES}]
        value = mapped(result, trace=trace)
        self.assertEqual((value["reason_code"], value["entries"], value["counts"]["total"]), ("limit_exceeded", [], 3))
        self.assertLess(len(__import__("json").dumps(value)), 2048)

    def test_verified_multi_spans_preserve_fragment_source_without_inventing_word_range(self):
        from tests.test_document_ir_logical_table_group import convert_payload, table
        ir = convert_payload([table(0, "1"), table(1, "2"), table(2, "3")])
        result = render(ir)
        value = mapped(result)
        for entry, record in zip(value["entries"], result.block_evidence.block_render_map, strict=True):
            self.assertEqual(entry["source"]["source_spans"], record.provenance.source_spans)
            self.assertIsNone(entry["location"]["page_range"])
