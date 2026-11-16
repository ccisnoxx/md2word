from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from docx import Document
from pydantic import ValidationError

from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.render_evidence import build_renderer_evidence, validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.tables.evidence import read_table_evidence
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.models import VALUE_COLUMN_SPAN_AMBIGUOUS, canonical_json_bytes, canonical_sha256
from app.services.tables.quality import LEGACY_VALIDATOR_VERSION, VALIDATOR_VERSION, TableValidationReport
from app.services.tables.validator import validate_document_tables, validate_table


def _convert_mineru(pages: list[list[dict]], *, layout: dict | None = None) -> DocumentIR:
    with TemporaryDirectory() as root:
        path = Path(root) / "mineru.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("content_list_v2.json", json.dumps(pages))
            if layout is not None:
                archive.writestr("layout.json", json.dumps(layout))
        return MinerUToDocumentIRService().convert_zip(
            path, job_id="test-job", source_file_id="test-source", document_language="en",
        ).document


def _document(html: str) -> DocumentIR:
    return _convert_mineru([[{"type": "table", "bbox": [20, 30, 180, 140], "content": {"html": html}}]])


def _span_findings(report):
    return tuple(finding for finding in report.findings if finding.flag.code == VALUE_COLUMN_SPAN_AMBIGUOUS)


_TWO_GROUPS = """
<table>
  <tr><td rowspan="2">测试条件</td><td colspan="2">器件 A</td><td colspan="2">器件 B</td><td rowspan="2">单位</td></tr>
  <tr><td>MIN</td><td>MAX</td><td>MIN</td><td>MAX</td></tr>
  <tr><td>输入甲</td><td colspan="2">2.1</td><td colspan="2">2.1</td><td rowspan="3">V</td></tr>
  <tr><td>输入乙</td><td colspan="2"><b>±</b>3.15</td><td>3.15</td><td></td></tr>
  <tr><td>输入丙</td><td>4</td><td colspan="2">3.85</td><td>4</td></tr>
</table>
"""


class ParameterTableValueColumnBindingTests(unittest.TestCase):
    def test_source_td_groups_distinguish_same_value_and_inherit_unit(self) -> None:
        contribution = validate_document_tables(_document(_TWO_GROUPS))
        findings = _span_findings(contribution)
        actual = []
        for finding in findings:
            evidence = finding.evidence
            span = evidence.value_column_span
            actual.append((evidence.source_row_index, evidence.column, evidence.end_column, span.value, span.unit,
                           tuple((item.column, item.label, item.group_start_column) for item in span.columns)))
            self.assertEqual(finding.flag.severity, "warning")
            self.assertEqual(evidence.page_index, 0)
            self.assertIsNotNone(evidence.cell_id)
        self.assertEqual(actual, [
            (2, 1, 3, "2.1", "V", ((1, "MIN", 1), (2, "MAX", 1))),
            (2, 3, 5, "2.1", "V", ((3, "MIN", 3), (4, "MAX", 3))),
            (3, 1, 3, "±3.15", "V", ((1, "MIN", 1), (2, "MAX", 1))),
        ])
        self.assertEqual(len({finding.finding_id for finding in findings}), 3)

    def test_later_explicit_header_keeps_same_implicit_column_layout_for_earlier_data(self) -> None:
        document = _document("""
            <table>
              <tr><td>Parameter</td><td>MIN</td><td>MAX</td><td>UNIT</td></tr>
              <tr><td>Gain</td><td colspan="2">2.1</td><td>V</td></tr>
              <tr><th>Parameter</th><th>MIN</th><th>MAX</th><th>UNIT</th></tr>
              <tr><td>Attenuation</td><td colspan="2">2.2</td><td>V</td></tr>
            </table>
        """)
        findings = _span_findings(validate_document_tables(document))
        self.assertEqual(
            [(item.evidence.source_row_index, item.evidence.value_column_span.value) for item in findings],
            [(1, "2.1"), (3, "2.2")],
        )

    def test_only_verified_continuation_without_local_header_uses_preceding_columns(self) -> None:
        source = ("<table><tr><th>Parameter</th><th>MIN</th><th>MAX</th></tr>"
                  "<tr><td>Gain</td><td>1</td><td>2</td></tr></table>")
        continuation = '<table><tr><td>Unity gain</td><td colspan="2">2.2</td></tr></table>'
        layout = {"pdf_info": [{"page_idx": index, "page_size": [1000, 1000]} for index in range(2)]}
        for second_number, verified in (("4-1", True), ("4-2", False)):
            with self.subTest(second_number=second_number):
                pages = [[{
                    "type": "table", "bbox": bbox,
                    "content": {"table_caption": [{"type": "text", "content": caption}], "html": html},
                }] for caption, bbox, html in (
                    ("Table 4-1. Limits", [20, 650, 980, 980], source),
                    (f"Table {second_number}. Limits (continued)", [20, 20, 980, 350], continuation),
                )]
                document = _convert_mineru(pages, layout=layout)
                relations = [relation for group in document.metadata.logical_table_groups
                             for relation in group.continuation_relations]
                findings = _span_findings(validate_document_tables(document))
                if not verified:
                    self.assertEqual(relations, [])
                    self.assertEqual(findings, ())
                    continue
                relation, = relations
                self.assertEqual(relation.kind, "verified_continuation")
                self.assertEqual(relation.evidence_codes, ["adjacent_page_geometry", "same_table_number_continued"])
                finding, = findings
                evidence = finding.evidence
                self.assertEqual((evidence.page_index, evidence.source_row_index, evidence.fragment_id),
                                 (1, 0, relation.to_fragment_id))
                self.assertEqual(evidence.value_column_span.value, "2.2")
                self.assertEqual(tuple((item.column, item.label) for item in evidence.value_column_span.columns),
                                 ((1, "MIN"), (2, "MAX")))

    def test_recognizes_header_families_and_ignores_titles_empty_cells_and_single_columns(self) -> None:
        cases = (
            ("th", ("Min.", "Typical", "Maximum"), ("TYP", "MAX")),
            ("td", ("LOW", "NOM", "HIGH"), ("NOM", "HIGH")),
            ("td", ("最小值", "典型值", "最大"), ("典型", "最大")),
        )
        for cell, labels, expected in cases:
            with self.subTest(labels=labels):
                header = "".join(f"<{cell}>{label}</{cell}>" for label in labels)
                document = _document(f"""
                    <table>
                      <tr><th colspan="4">工作条件 3</th></tr>
                      <tr><{cell}>参数</{cell}>{header}</tr>
                      <tr><td colspan="4">输入范围 1</td></tr>
                      <tr><td>输入甲</td><td>0</td><td colspan="2">−2.5e-3 μV/√Hz</td></tr>
                      <tr><td>输入乙</td><td colspan="2"></td><td>50</td></tr>
                      <tr><td>输入丙</td><td rowspan="2">6</td><td>7</td><td>8</td></tr>
                      <tr><td>输入丁</td><td>7</td><td>8</td></tr>
                    </table>
                """)
                finding, = _span_findings(validate_document_tables(document))
                self.assertEqual(finding.evidence.source_row_index, 3)
                span = finding.evidence.value_column_span
                self.assertEqual(tuple(item.label for item in span.columns), expected)
                self.assertEqual((span.value, span.unit), ("−2.5e-3", "μV/√Hz"))

    def test_value_is_bound_to_original_source_and_evidence_rejects_outside_columns(self) -> None:
        document = _document(_TWO_GROUPS)
        group, = document.metadata.logical_table_groups
        source_hash = document.metadata.mineru_validation.content_list_sha256
        result = build_table_grid(group, source_content_sha256=source_hash)
        report = validate_table(result, group)
        value = next(cell for cell in result.grid.cells if cell.source_row_index == 2 and cell.column == 1)
        changed = value.runs[0].model_copy(update={"target": "9"})
        cells = [cell.model_copy(update={"runs": [changed]}) if cell.id == value.id else cell
                 for cell in result.grid.cells]
        translated = replace(result, grid=result.grid.model_copy(update={"cells": cells}))
        self.assertEqual(validate_table(translated, group), report)

        submitted = report.model_dump(mode="json", exclude={"report_sha256"})
        finding = next(item for item in submitted["findings"] if item["flag"]["code"] == VALUE_COLUMN_SPAN_AMBIGUOUS)
        finding["evidence"]["value_column_span"]["columns"] = [
            {"column": 0, "label": "MIN", "group_start_column": 0},
            {"column": 1, "label": "MAX", "group_start_column": 0},
        ]
        submitted["report_sha256"] = canonical_sha256(["table-validation-report/v1", submitted])
        with self.assertRaises(ValidationError):
            TableValidationReport.model_validate_json(canonical_json_bytes(submitted))

    def test_recomputes_each_report_version_and_retains_editable_spans(self) -> None:
        document = _document(_TWO_GROUPS)
        rendered = DocumentIRWordRenderer().render_to_result(
            document, template_path=None, config_path=None, image_loader=lambda _asset: None,
        )
        word = Document(BytesIO(rendered.content))
        table, = word.tables
        self.assertEqual(table.rows[2].cells[1]._tc.grid_span, 2)
        self.assertEqual(table.rows[2].cells[3]._tc.grid_span, 2)

        for version, count in ((LEGACY_VALIDATOR_VERSION, 0), (VALIDATOR_VERSION, 3)):
            with self.subTest(version=version):
                evidence = build_renderer_evidence(
                    document, rendered.content, render_result=rendered, _table_validator_version=version,
                )
                ensure_renderer_integrity(evidence)
                report = read_table_evidence(evidence["table_evidence"])
                item, = report.tables
                self.assertEqual(report.validator_version, version)
                self.assertEqual(len(_span_findings(item.validation)), count)
                restored = validate_persisted_renderer_content(document, rendered.content, evidence)
                self.assertEqual(restored["table_evidence"], evidence["table_evidence"])


if __name__ == "__main__":
    unittest.main()
