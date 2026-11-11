from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ops.datasheet_quality_metrics import OBSERVATION_VERSION, REPORT_VERSION, build_report, main


OPENABLE = {"status": "succeeded", "docx_available": True, "docx_openable": True}
EXPECTED_BLOCK = {"code": "table_fragment_missing", "scope": "table", "delivery_status": "internal_draft"}


def plan(sample_id: str, **overrides) -> dict:
    return {
        "sample_id": sample_id,
        "mode": "direct",
        "cohort": "expanded",
        "evidence_level": "local_component",
        "expected_outcome": "normal",
        **overrides,
    }


def observed(sample_id: str, **overrides) -> dict:
    return {"sample_id": sample_id, "mode": "direct", "conversion": OPENABLE, **overrides}


def input_payload(plans: list[dict], observations: list[dict]) -> dict:
    return {
        "schema_version": OBSERVATION_VERSION,
        "metadata": {"manifest_version": 1},
        "plan": plans,
        "observations": observations,
    }


class DatasheetQualityMetricsTests(unittest.TestCase):
    def test_plan_denominator_preserves_missing_and_excludes_blocking_cases(self) -> None:
        plans = [
            plan(sample_id) for sample_id in ("success", "missing", "timeout", "bad-docx", "unverified")
        ] + [
            plan(sample_id, expected_outcome="blocked", expected_blocker=EXPECTED_BLOCK)
            for sample_id in ("block-matched", "block-mismatch", "block-absent")
        ]
        observations = [
            observed("success"),
            observed("timeout", conversion={"status": "timeout"}),
            observed("bad-docx", conversion={**OPENABLE, "docx_openable": False}),
            observed("unverified", conversion={"status": "succeeded"}),
            observed("block-matched", blocker=EXPECTED_BLOCK),
            observed("block-mismatch", blocker={**EXPECTED_BLOCK, "delivery_status": "published"}),
        ]

        group = build_report(input_payload(plans, observations))["groups"][0]

        conversion = group["conversion_success"]
        self.assertEqual((conversion["numerator"], conversion["denominator"], conversion["coverage"]), (1, 5, 0.8))
        self.assertEqual(conversion["failure_reasons"], {
            "docx_not_openable": 1, "docx_unverified": 1, "not_run": 1, "timeout": 1,
        })
        self.assertEqual(group["blocking_cases"], {"planned": 3, "matched": 1, "mismatch": 1, "not_measured": 1})

    def test_table_and_token_ratios_retain_expected_counts_without_an_artifact(self) -> None:
        plans = [
            plan("visible", expected_tables=3, expected_tokens={"number": 4, "unit": 2}),
            plan("no-docx", expected_tables=2, expected_tokens={"number": 2, "unit": 1}),
            plan("no-annotation"),
        ]
        observations = [
            observed(
                "visible",
                table={"matched": 2, "assessed": 3, "unexpected": 1, "duplicate": 1},
                tokens={
                    "matched": {"number": 2, "unit": 2},
                    "assessed": {"number": 3, "unit": 2},
                    "duplicates": {"number": 1},
                    "misplaced": {"number": 1},
                    "extras": {"unit": 1},
                },
            ),
            observed("no-docx", conversion={"status": "failed"}),
            observed("no-annotation"),
        ]

        group = build_report(input_payload(plans, observations))["groups"][0]

        tables = group["table_structure"]
        self.assertEqual((tables["numerator"], tables["denominator"], tables["unassessed"]), (2, 5, 2))
        self.assertEqual((tables["unexpected"], tables["duplicate"], tables["unannotated_samples"]), (1, 1, 1))
        tokens = group["technical_tokens"]
        self.assertEqual((tokens["numerator"], tokens["denominator"], tokens["unassessed"]), (4, 9, 4))
        self.assertEqual(tokens["by_kind"]["number"]["value"], 2 / 6)
        self.assertEqual(tokens["by_kind"]["number"]["duplicates"], 1)
        self.assertEqual(tokens["by_kind"]["number"]["misplaced"], 1)
        self.assertEqual(tokens["by_kind"]["unit"]["extras"], 1)

    def test_visual_uses_matched_regions_and_reports_incomplete_coverage(self) -> None:
        plans = [
            plan("matched", expected_visual_pages=2, expected_visual_regions=3),
            plan("unavailable", expected_visual_pages=1, expected_visual_regions=1),
        ]
        observations = [
            observed(
                "matched",
                visual={
                    "matched_pages": 1,
                    "regions": [
                        {"id": "first", "source_bbox": [0, 0, 0.5, 0.5], "result_bbox": [0.25, 0, 0.75, 0.5]},
                        {"id": "second", "source_bbox": [0, 0, 0.5, 0.5], "result_bbox": [0.5, 0, 1, 0.5]},
                    ],
                    "overflow": 1,
                    "clipped": 1,
                    "reason": "reflowed_page",
                },
            ),
            observed("unavailable", missing={"visual": "preview_unavailable"}),
        ]

        report = build_report(input_payload(plans, observations))
        visual = report["groups"][0]["page_visual"]

        self.assertEqual(visual["pages"]["coverage"], 1 / 3)
        self.assertEqual(visual["regions"]["coverage"], 2 / 4)
        self.assertEqual(visual["offset"], {"count": 2, "mean": 0.1875, "p50": 0.125, "p95": 0.25})
        self.assertEqual((visual["overflow"], visual["clipped"]), (1, 1))
        self.assertEqual((visual["overflow_observed_samples"], visual["clipped_observed_samples"]), (1, 1))
        self.assertEqual(report["samples"][1]["visual"]["reason"], "preview_unavailable")

    def test_visual_layout_counts_distinguish_missing_and_observed_zero(self) -> None:
        plans = [
            plan("anchor-only", expected_visual_pages=1, expected_visual_regions=1),
            plan("layout-only"),
        ]
        observations = [
            observed(
                "anchor-only",
                visual={
                    "matched_pages": 1,
                    "regions": [
                        {"id": "heading", "source_bbox": [0, 0, 0.5, 0.5], "result_bbox": [0, 0, 0.5, 0.5]},
                    ],
                },
            ),
            observed("layout-only", visual={"overflow": 0}),
        ]

        report = build_report(input_payload(plans, observations))
        visual = report["groups"][0]["page_visual"]
        self.assertEqual((visual["overflow"], visual["overflow_observed_samples"]), (0, 1))
        self.assertEqual((visual["clipped"], visual["clipped_observed_samples"]), (None, 0))
        self.assertIsNone(report["samples"][0]["visual"]["overflow"])
        self.assertEqual(report["samples"][1]["visual"]["overflow"], 0)

    def test_manual_counts_distinguish_unrecorded_and_observed_zero(self) -> None:
        plans = [plan(sample_id) for sample_id in ("fixed", "zero", "unrecorded")]
        observations = [
            observed(
                "fixed",
                manual={
                    "edits": [
                        {"id": "defect-a", "disposition": "fixed"},
                        {"id": "defect-a", "disposition": "fixed"},
                        {"id": "defect-b", "disposition": "reported"},
                    ],
                    "rounds": [{
                        "id": "round-one",
                        "reviewer": "reviewer-a",
                        "intervals": [
                            {"start_seconds": 0, "end_seconds": 30},
                            {"start_seconds": 50, "end_seconds": 80},
                        ],
                    }],
                },
            ),
            observed(
                "zero",
                manual={
                    "edits": [],
                    "rounds": [{
                        "id": "round-one",
                        "reviewer": "reviewer-a",
                        "intervals": [{"start_seconds": 0}],
                    }],
                },
            ),
            observed("unrecorded", missing={"edits": "no_signoff"}),
        ]

        group = build_report(input_payload(plans, observations))["groups"][0]

        self.assertEqual(group["manual_edits"]["count"], 2)
        self.assertEqual(group["manual_edits"]["mean"], 0.5)
        self.assertEqual(group["manual_edits"]["missing_reasons"], {"no_signoff": 1})
        self.assertEqual(group["manual_review_minutes"]["count"], 1)
        self.assertEqual(group["manual_review_minutes"]["p50"], 1)
        self.assertEqual(group["manual_review_minutes"]["missing_reasons"], {
            "review_time_not_recorded": 1, "incomplete_review_round": 1,
        })

    def test_cost_and_latency_keep_evidence_currency_basis_and_outcome_separate(self) -> None:
        plans = [plan(str(index)) for index in range(1, 21)]
        observations = [
            observed(
                str(index),
                cost={"currency": "USD", "basis": "actual", "reference": "receipt",
                      "complete": True, "components": {"parser": index, "translation": 0}},
                latency={"kind": "local_replay", "seconds": index},
            )
            for index in range(1, 21)
        ]
        plans.extend([plan("estimate"), plan("partial"), plan("timeout", evidence_level="isolated_chain")])
        observations.extend([
            observed(
                "estimate",
                cost={"currency": "EUR", "basis": "estimated", "reference": "tariff-v1",
                      "complete": True, "components": {"parser": 0.1, "translation": 0.2}},
            ),
            observed(
                "partial",
                cost={"currency": "USD", "basis": "actual", "reference": "zero-provider-calls",
                      "complete": False, "components": {"translation": 0}, "reason": "parser_bill_unavailable"},
            ),
            observed(
                "timeout", conversion={"status": "timeout"},
                latency={"kind": "end_to_end", "seconds": 30, "poll_interval_seconds": 5},
            ),
        ])

        report = build_report(input_payload(plans, observations))
        isolated, local = report["groups"]
        euro, usd = local["cost"]["by_currency_and_basis"]

        self.assertEqual((euro["currency"], euro["basis"], euro["p50"]), ("EUR", "estimated", 0.3))
        self.assertEqual((usd["count"], usd["p50"], usd["p95"]), (20, 10, 19))
        self.assertEqual(local["cost"]["missing_reasons"], {"parser_bill_unavailable": 1})
        partial = next(sample for sample in report["samples"] if sample["sample_id"] == "partial")
        self.assertEqual(partial["cost"]["components"], {"translation": 0})
        self.assertIsNone(partial["cost"]["value"])
        self.assertEqual(local["latency_seconds"]["by_kind_and_outcome"]["local_replay"]["succeeded"]["p95"], 19)
        self.assertEqual(isolated["latency_seconds"]["by_kind_and_outcome"]["end_to_end"]["timeout"]["p50"], 30)

    def test_bad_observation_cannot_change_the_fixed_plan_or_inflate_matches(self) -> None:
        plans = [plan("one", expected_tables=1)]
        for observations in (
            [observed("unplanned")],
            [observed("one"), observed("one")],
            [observed("one", table={"matched": 2})],
            [observed("one", conversion={"status": "failed"}, table={"matched": 1})],
        ):
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                build_report(input_payload(plans, observations))

    def test_cli_recomputes_same_report_from_reordered_observations(self) -> None:
        payload = input_payload([plan("b"), plan("a")], [observed("b"), observed("a")])
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "observations.json"
            first_path = Path(temp_dir) / "first.json"
            second_path = Path(temp_dir) / "second.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            main([str(input_path), "--output", str(first_path)])
            payload["plan"].reverse()
            payload["observations"].reverse()
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            main([str(input_path), "--output", str(second_path)])

            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            report = json.loads(first_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], REPORT_VERSION)
            self.assertEqual(report["metadata"], payload["metadata"])


if __name__ == "__main__":
    unittest.main()
