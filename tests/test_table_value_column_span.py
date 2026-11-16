"""参数表数值列跨列检测：单个参数值不得静默跨越 MIN/TYP/MAX 等并列数值列。"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from pydantic import ValidationError

from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.tables.models import (
    LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS, VALUE_COLUMN_SPAN_AMBIGUOUS, canonical_json_bytes,
)
from app.services.tables.quality import LEGACY_VALIDATOR_VERSION, TableValidationPolicy, TableValidationReport, canonical_sha256
from app.services.tables.validator import validate_document_tables


_CODE = VALUE_COLUMN_SPAN_AMBIGUOUS
# 摘自 gs-008（OPA228 P7）MinerU HTML：±5 实为 TYP、±100 实为 MAX，却被声明跨多个数值列。
_GS008_ROWS = (
    "<tr><td colspan='2'>PARAMETER</td><td colspan='2'>TEST CONDITIONS</td>"
    "<td>MIN</td><td>TYP</td><td>MAX</td><td>UNIT</td></tr>"
    "<tr><td colspan='8'>OFFSET VOLTAGE</td></tr>"
    "<tr><td rowspan='2'>VOS</td><td rowspan='2'>Input offset voltage</td><td rowspan='2'>U, P grades</td>"
    "<td></td><td colspan='2'>±5</td><td>±75</td><td rowspan='2'>μV</td></tr>"
    "<tr><td>TA = -40°C to +85°C</td><td colspan='3'>±100</td></tr>"
)


class TableValueColumnSpanTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "mineru.zip"

    def findings(self, rows: str, policy: TableValidationPolicy | None = None):
        payload = json.dumps([[{"type": "table", "bbox": [20, 30, 180, 140],
                                "content": {"html": f"<table>{rows}</table>"}}]])
        with ZipFile(self.path, "w") as archive:
            archive.writestr("content_list_v2.json", payload)
        document = MinerUToDocumentIRService().convert_zip(
            self.path, job_id="test-job", source_file_id="test-source", document_language="en").document
        report, = validate_document_tables(
            document, policy=policy, validator_version=LEGACY_VALIDATOR_VERSION, legacy_value_column_replay="blocker",
        ).reports
        return report, [item for item in report.findings if item.flag.code == LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS]

    def test_gs008_values_spanning_value_columns_are_blocked(self) -> None:
        _, findings = self.findings(_GS008_ROWS)
        located = [(item.evidence.row, item.evidence.column, item.evidence.end_column,
                    item.evidence.actual, item.flag.severity) for item in findings]
        # 单列 ±75 与跨两个条件列的空单元格均不命中。
        self.assertEqual(located, [(2, 4, 6, 2, "blocker"), (3, 4, 7, 3, "blocker")])

    def test_legitimate_spans_are_not_reported(self) -> None:
        rows = ("<tr><td>Symbol</td><td>MIN</td><td>NOM</td><td>MAX</td></tr>"
                "<tr><td>e</td><td colspan='3'>0.50BSC</td></tr>"
                "<tr><td>b1</td><td colspan='3'>0.23 REF</td></tr>"
                "<tr><td>TA</td><td colspan='3'>-40 to 125</td></tr>"
                "<tr><td>Range</td><td colspan='3'>2.1e-6 to 3e-6</td></tr>"
                "<tr><td>Note</td><td colspan='3'>See Figure 5</td></tr>")
        self.assertEqual(self.findings(rows)[1], [])

    def test_rows_before_value_label_row_are_not_checked(self) -> None:
        rows = ("<tr><td>Gain</td><td colspan='2'>5</td></tr>"
                "<tr><td>Name</td><td>MIN</td><td>MAX</td></tr>")
        self.assertEqual(self.findings(rows)[1], [])

    def test_unmarked_value_spanning_two_limit_columns_is_blocked(self) -> None:
        for lower, upper in (("Min", "Max"), ("LOW", "HIGH")):
            with self.subTest(lower=lower, upper=upper):
                rows = (f"<tr><td>Symbol</td><td>{lower}</td><td>{upper}</td></tr>"
                        "<tr><td>L</td><td>0.260</td><td>0.460</td></tr>"
                        "<tr><td>L1</td><td colspan='2'>0.525</td></tr>")
                _, findings = self.findings(rows)
                self.assertEqual([(item.evidence.rule_id, item.flag.severity) for item in findings],
                                 [(LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS, "blocker")])

    def test_reference_value_requires_complete_marker(self) -> None:
        rows = ("<tr><td>Symbol</td><td>Min</td><td>Max</td></tr>"
                "<tr><td>Voltage</td><td colspan='2'>1.2 VREF</td></tr>")
        _, findings = self.findings(rows)
        self.assertEqual([(item.evidence.rule_id, item.flag.severity) for item in findings],
                         [(LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS, "blocker")])

    def test_scientific_notation_value_spanning_value_columns_is_blocked(self) -> None:
        rows = ("<tr><td>Symbol</td><td>MIN</td><td>TYP</td><td>MAX</td></tr>"
                "<tr><td>Leakage</td><td></td><td colspan='2'>2.1e-6</td></tr>"
                "<tr><td>Current</td><td colspan='2'>1E+3 µA</td><td></td></tr>"
                "<tr><td>Offset</td><td colspan='3'>−4.5e−2 V</td></tr>"
                "<tr><td>Single</td><td></td><td>3e-6</td><td></td></tr>")
        _, findings = self.findings(rows)
        self.assertEqual([(item.evidence.row, item.flag.severity) for item in findings],
                         [(1, "blocker"), (2, "blocker"), (3, "blocker")])

    def test_policy_can_downgrade_blocker(self) -> None:
        policy = TableValidationPolicy(rule_severities={LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS: "warning"})
        _, findings = self.findings(_GS008_ROWS, policy)
        self.assertEqual({item.flag.severity for item in findings}, {"warning"})

    def test_report_rejects_forged_value_column_count(self) -> None:
        report, _ = self.findings(_GS008_ROWS)
        payload = json.loads(report.model_dump_json())
        TableValidationReport.model_validate_json(canonical_json_bytes(payload))
        # actual 不进入 finding_id；重算报告指纹，确保拒绝来自本规则的跨字段校验。
        index = next(i for i, item in enumerate(payload["findings"])
                     if item["flag"]["code"] == LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS)
        payload["findings"][index]["evidence"]["actual"] = 1
        payload.pop("report_sha256")
        payload["report_sha256"] = canonical_sha256(["table-validation-report/v1", payload])
        with self.assertRaises(ValidationError):
            TableValidationReport.model_validate_json(canonical_json_bytes(payload))


if __name__ == "__main__":
    unittest.main()
