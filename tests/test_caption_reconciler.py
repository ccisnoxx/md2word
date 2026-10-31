"""通过源块与回执观察严格题注规则，不调用外部解析或翻译设施。"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from unittest.mock import patch

from app.services.document_ir import caption_reconciler as reconciler
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_annotations import is_table_context_annotation


def source(index: int, captions: object = None, *, kind: str = "chart", page: int | None = 0,
           bbox: list[int] | None = None) -> dict:
    block = {
        "type": kind, "page_idx": page,
        "_mineru_source": {"json_pointer": f"/{index}", "source_index": index,
                           "source_index_in_page": index, "page_index": page, "source_type": kind},
    }
    if captions is not None:
        block["content"] = {f"{kind}_caption": captions}
    if bbox is not None:
        block["bbox"] = bbox
    return block


class CaptionReconcilerTests(unittest.TestCase):
    def test_family_sequence_binding_keeps_originals_and_input_immutable(self) -> None:
        blocks = [source(0, [], kind="image"), source(1, ["Figure 6 B", "Figure 5 A"], kind="figure"),
                  source(2, [], kind="table"), source(3, ["Table 2 B", "Table 1 A"], kind="table")]
        original = copy.deepcopy(blocks)
        results = reconciler.reconcile_captions(blocks)
        self.assertEqual([result.captions for result in results], [["Figure 5 A"], ["Figure 6 B"], ["Table 1 A"], ["Table 2 B"]])
        self.assertEqual(blocks, original)
        self.assertEqual(results, reconciler.reconcile_captions(blocks))
        self.assertEqual(results[0].evidence["originals"], [])
        self.assertEqual(results[1].evidence["originals"], [{
            "json_pointer": "/1/content/figure_caption", "value": ["Figure 6 B", "Figure 5 A"],
            "groups": ["/1/content/figure_caption/0", "/1/content/figure_caption/1"],
        }])
        self.assertEqual(results[0].evidence["bindings"][0]["donor_index"], 1)
        self.assertEqual(results[0].evidence["bindings"][0]["target_index"], 0)
        self.assertNotEqual(results[0].evidence["group_id"], results[2].evidence["group_id"])
        self.assertEqual(results[0].evidence["members"], [0, 1])
        self.assertNotIn("members", results[1].evidence)

    def test_reliable_rich_newlines_preserve_formulas_units_and_raw_spans(self) -> None:
        rich = [{"type": "text", "content": "图 24 失调 ("},
                {"type": "equation_inline", "content": r"\pm"},
                {"type": "text", "content": " 18 V)\n续行单位 µV\n图 25 增益 2 kΩ"}]
        blocks = [source(0, []), source(1, rich)]
        results = reconciler.reconcile_captions(blocks)
        self.assertEqual([result.captions for result in results], [["图 24 失调 ($\\pm$ 18 V) 续行单位 µV"], ["图 25 增益 2 kΩ"]])
        self.assertEqual(results[1].evidence["originals"][0]["value"], rich)
        spans = [span for result in results for receipt in result.evidence["bindings"] for span in receipt["source_spans"]]
        for index, node in enumerate(rich):
            pointer = f"/1/content/chart_caption/{index}/content"
            ranges = sorted((span["start"], span["end"]) for span in spans if span["json_pointer"] == pointer)
            self.assertEqual("".join(node["content"][start:end] for start, end in ranges), node["content"])

    def test_existing_one_to_one_is_not_sorted_again(self) -> None:
        blocks = [source(0, ["图 6 B"]), source(1, ["图 5 A"])]
        results = reconciler.reconcile_captions(blocks)
        self.assertEqual([result.captions for result in results], [["图 6 B"], ["图 5 A"]])
        self.assertEqual([result.evidence["status"] for result in results], ["unchanged", "unchanged"])
        self.assertTrue(all(not result.evidence["bindings"] for result in results))

    def test_rejected_candidates_remain_visible_and_have_stable_reasons(self) -> None:
        cases = [
            (["图 5 A", "图 7 B"], "non_contiguous_numbers"),
            (["图 5 A", "图 5 B"], "duplicate_number"),
            (["图 5 A", "Figure 6 B"], "mixed_labels"),
            (["图 5 A"], "count_mismatch"),
            (["图 5.1 A", "图 6.1 B"], "unsupported_number"),
            (["Figure XII. A", "Figure XIII. B"], "unsupported_number"),
            (["图 5(a) A", "图 6(b) B"], "unsupported_number"),
            (["图 5、6共同说明"], "unsupported_number"),
            (["图 5～6 共同说明", "图 6 B"], "unsupported_number"),
            (["图 5~6 共同说明", "图 6 B"], "unsupported_number"),
            (["图 5 - 6 共同说明", "图 6 B"], "unsupported_number"),
            (["图 5至6 共同说明", "图 6 B"], "unsupported_number"),
            (["图 5到6 共同说明", "图 6 B"], "unsupported_number"),
            (["Figure 5 – 6 response", "Figure 6 B"], "unsupported_number"),
            (["Figure 5 and 6 response", "Figure 6 B"], "unsupported_number"),
            (["Table 5 to 6 response", "Table 6 B"], "unsupported_number"),
            (["图 5 与图 6 比较"], "split_boundary_uncertain"),
            ([{"type": "text", "content": "图 5 A"}, {"type": "text", "content": "图 6 B"}], "split_boundary_uncertain"),
        ]
        for captions, reason in cases:
            with self.subTest(reason=reason, captions=captions):
                blocks = [source(0, []), source(1, captions)]
                original = copy.deepcopy(blocks)
                results = reconciler.reconcile_captions(blocks)
                self.assertEqual(results[0].captions, [])
                self.assertTrue(results[1].captions)
                self.assertTrue(all(reason in result.evidence["reasons"] for result in results))
                self.assertEqual(blocks, original)
                self.assertEqual(results[1].evidence["originals"][0]["value"], captions)

    def test_page_source_and_body_boundaries_prevent_reassociation(self) -> None:
        for reason, blocks in [
            ("cross_page", [source(0, []), source(1, ["图 5 A", "图 6 B"], page=1)]),
            ("non_contiguous_source", [source(0, []), source(2, ["图 5 A", "图 6 B"])]),
            ("missing_page", [source(0, [], page=None), source(1, ["图 5 A", "图 6 B"], page=None)]),
        ]:
            with self.subTest(reason=reason):
                results = reconciler.reconcile_captions(blocks)
                self.assertEqual([result.captions for result in results], [[], ["图 5 A", "图 6 B"]])
                self.assertTrue(all(reason in result.evidence["reasons"] for result in results))
        separated = [source(0, []), {**source(1, kind="text"), "text": "正文"}, source(2, ["图 5 A", "图 6 B"])]
        results = reconciler.reconcile_captions(separated)
        self.assertEqual(results[0].captions, [])
        self.assertEqual(results[2].captions, ["图 5 A", "图 6 B"])

    def test_table_conditions_have_explicit_boundaries_or_remain_annotations(self) -> None:
        cases = [
            ("Table 1 Limits\nat TA = 25°C (unless otherwise noted)", ["Table 1 Limits", "at TA = 25°C (unless otherwise noted)"], "rebound"),
            ("Table 1 Limits unless otherwise noted", ["Table 1 Limits unless otherwise noted"], "uncertain"),
        ]
        for raw, expected, status in cases:
            with self.subTest(raw=raw):
                result = reconciler.reconcile_captions([source(0, raw, kind="table")])[0]
                self.assertEqual(result.captions, expected)
                self.assertEqual(result.evidence["status"], status)
        blocks = [source(0, [], kind="table"), source(1, ["Table 1 A", "Table 2 B", "at TA = 25°C"], kind="table")]
        results = reconciler.reconcile_captions(blocks)
        self.assertEqual(results[0].captions, [])
        self.assertIn("competing_subjects", results[1].evidence["reasons"])
        repeated = "Table 1 Limits\nTable 1 Limits\nat TA = 25°C"
        result = reconciler.reconcile_captions([source(0, repeated, kind="table")])[0]
        self.assertEqual(result.captions, ["Table 1 Limits Table 1 Limits at TA = 25°C"])
        self.assertEqual(result.evidence["status"], "uncertain")
        self.assertIn("duplicate_number", result.evidence["reasons"])

    def test_paragraph_binding_is_evidence_only_and_competition_is_not_guessed(self) -> None:
        image = source(0, [], bbox=[10, 10, 90, 80])
        paragraph = {**source(1, kind="text", bbox=[10, 85, 90, 95]), "text": "图 5 响应"}
        blocks = [image, paragraph]
        original = copy.deepcopy(blocks)
        results = reconciler.reconcile_captions(blocks)
        self.assertEqual(blocks, original)
        self.assertEqual(results[0].captions, [])
        self.assertIsNone(results[1].evidence)
        self.assertEqual(results[0].evidence["status"], "evidence_only")
        self.assertTrue(results[0].evidence["bindings"][0]["evidence_only"])
        cases = [
            ("competing_subjects", [image, paragraph, source(2, [], bbox=[10, 100, 90, 170])]),
            ("missing_layout", [source(0, []), paragraph]),
            ("cross_page", [image, {**paragraph, "page_idx": 1}]),
            ("not_caption_title", [image, {**paragraph, "text": "见图 5 的响应"}]),
            ("layout_mismatch", [image, {**paragraph, "bbox": [100, 85, 190, 95]}]),
        ]
        for reason, blocks in cases:
            with self.subTest(reason=reason):
                result = reconciler.reconcile_captions(blocks)[0]
                self.assertEqual(result.captions, [])
                self.assertEqual(result.evidence["status"], "uncertain")
                self.assertIn(reason, result.evidence["reasons"])
                self.assertEqual(result.evidence["bindings"], [])
        table = source(1, [], kind="table", bbox=[10, 100, 90, 180])
        table_title = {**source(0, kind="paragraph", bbox=[10, 80, 90, 95]), "text": "Table 1 Limits"}
        self.assertEqual(reconciler.reconcile_captions([table_title, table])[1].evidence["status"], "evidence_only")

    def test_plain_missing_caption_has_no_uncertainty_and_evidence_is_not_reconsumed(self) -> None:
        blocks = [source(0, []), source(1, [])]
        blocks[0]["metadata"] = {"caption_reconciliation": {"originals": [{"caption": "图 999 旧证据"}]}}
        results = reconciler.reconcile_captions(blocks)
        self.assertTrue(all(result.evidence["status"] == "unchanged" for result in results))
        self.assertEqual([result.captions for result in results], [[], []])
        plain = reconciler.reconcile_captions([source(0, ["Noise Density", "Frequency Response"])])[0]
        self.assertEqual(plain.captions, ["Noise Density", "Frequency Response"])
        self.assertEqual(plain.evidence["status"], "unchanged")
        self.assertEqual(plain.evidence["reasons"], [])
        conditions = "at TA = 25°C\nwith VS = 5V"
        table = reconciler.reconcile_captions([source(0, conditions, kind="table")])[0]
        self.assertEqual(table.captions, ["at TA = 25°C with VS = 5V"])
        self.assertEqual(table.evidence["status"], "unchanged")
        self.assertTrue(is_table_context_annotation("Table conditions at TA = 25°C (unless otherwise noted)"))

    def test_candidate_text_or_span_damage_fails_closed_without_source_text(self) -> None:
        blocks = [source(0, []), source(1, "图 5 私有甲\n图 6 私有乙")]
        splitter = reconciler._split_group

        def corrupt_text(group, family):
            fragments = splitter(group, family)
            if fragments:
                fragments[0] = replace(fragments[0], text=fragments[0].text.replace("私有甲", "损坏"))
            return fragments

        with patch.object(reconciler, "_split_group", side_effect=corrupt_text):
            with self.assertRaises(DocumentIntegrityError) as caught:
                reconciler.reconcile_captions(blocks)
        self.assertIn("fragment_conservation", str(caught.exception))
        self.assertNotIn("私有", str(caught.exception.evidence))
        group = reconciler._groups("图 5 私有甲", "/1/chart_caption", 1)[0]
        fragment = splitter(group, "figure")[0]
        for assignments in ([], [[fragment], [fragment]]):
            with self.subTest(assignments=len(assignments)), self.assertRaises(DocumentIntegrityError):
                reconciler._validate_repair([group], assignments, [[piece.text for piece in row] for row in assignments])
        with self.assertRaises(DocumentIntegrityError):
            reconciler._validate_repair([group], [[fragment]], [[]])


if __name__ == "__main__":
    unittest.main()
