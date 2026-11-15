from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from pydantic import ValidationError

from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from app.services.document_ir.table_value_column_review import (
    TableValueColumnCorrection,
    TableValueColumnReview,
    TableValueColumnReviewError,
    attach_table_value_column_reviews,
    resolve_table_value_column_review,
)
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.validator import validate_document_tables


_PDFS = Path(__file__).parent / "fixtures" / "golden_samples" / "pdfs"
_TABLE = (
    "<table><tr><th>Parameter</th><th>MIN</th><th>TYP</th><th>MAX</th><th>UNIT</th></tr>"
    "<tr><td>Offset</td><td colspan='2'>±5</td><td>±75</td><td>µV</td></tr></table>"
)
_RULE = "table_value_column_span_ambiguous"


class TableValueColumnReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.package = Path(directory.name) / "mineru.zip"
        self.source = self.pdf("OPA228_P7.pdf")
        self.payload = self.write_package(_TABLE, _TABLE.replace("Offset", "Drift"))

    @staticmethod
    def pdf(name: str) -> PdfCropSource:
        content = (_PDFS / name).read_bytes()
        return PdfCropSource("source-pdf", checksum(content), content)

    def write_package(self, *html_tables: str) -> bytes:
        payload = json.dumps([[{
            "type": "table", "bbox": [20, 30 + 200 * number, 180, 140 + 200 * number],
            "content": {"html": html},
        } for number, html in enumerate(html_tables)]]).encode()
        self.write_content(payload)
        return payload

    def write_content(self, payload: bytes) -> None:
        with ZipFile(self.package, "w") as archive:
            archive.writestr("content_list_v2.json", payload)

    def convert(self, *reviews: TableValueColumnReview, job_id: str = "job") -> DocumentIR:
        return MinerUToDocumentIRService().convert_zip(
            self.package, job_id=job_id, source_file_id=self.source.file_id, document_language="en",
            placeholder_source_loader=lambda: self.source, table_value_column_reviews=reviews,
        ).document

    def review(self, document: DocumentIR, *, group_index: int = 0) -> TableValueColumnReview:
        group = document.metadata.logical_table_groups[group_index]
        fragment, = group.fragments
        source_hash = document.metadata.mineru_validation.content_list_sha256
        result = build_table_grid(group, source_content_sha256=source_hash)
        cell = next(item for item in result.grid.cells
                    if item.source_row_index == 1 and item.source_cell_index == 1)
        return TableValueColumnReview(
            schema_version="table-value-column-review/v1",
            source_pdf_sha256=self.source.checksum_sha256.removeprefix("sha256:"),
            content_list_sha256=source_hash,
            page_index=fragment.source_span.page_index,
            json_pointer=fragment.source_span.json_pointer,
            raw_html_sha256=fragment.raw_html_sha256,
            normalizer_version=result.normalizer_version,
            corrections=(TableValueColumnCorrection(
                source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
                content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
                target_column=2, target_header="TYP",
            ),),
        )

    def assert_rejected(self, reason: str, *reviews: TableValueColumnReview) -> None:
        with self.assertRaises(TableValueColumnReviewError) as caught:
            self.convert(*reviews)
        self.assertEqual(caught.exception.code, "table_value_column_review_invalid")
        self.assertEqual(caught.exception.reason, reason)

    def test_same_sources_retain_review_and_original_grid_findings(self) -> None:
        baseline = self.convert()
        review = self.review(baseline)
        self.assertNotIn("value_column_review", baseline.model_dump_json())
        baseline_report = validate_document_tables(baseline)
        first = self.convert(review)
        second = self.convert(review, job_id="rerun")
        for candidate in (first, second):
            restored = DocumentIR.model_validate_json(candidate.model_dump_json())
            group = restored.metadata.logical_table_groups[0]
            fragment, = group.fragments
            self.assertEqual(fragment.value_column_review, review)
            self.assertEqual(fragment.value_column_review.review_sha256, review.review_sha256)
            self.assertEqual(fragment.raw_html, _TABLE)
            self.assertEqual(restored.blocks[0].html, baseline.blocks[0].html)
            grid, findings = resolve_table_value_column_review(
                fragment.value_column_review, group, source_content_sha256=review.content_list_sha256,
            )
            self.assertEqual(grid, build_table_grid(baseline.metadata.logical_table_groups[0],
                                                   source_content_sha256=review.content_list_sha256).grid)
            self.assertEqual(validate_document_tables(restored), baseline_report)
            finding, = findings
            self.assertEqual(finding.flag.code, _RULE)
            self.assertIn(finding, baseline_report.reports[0].findings)

    def test_rejects_stale_review_for_replaced_pdf_or_content_list(self) -> None:
        review = self.review(self.convert())
        original_pdf = self.source
        self.source = self.pdf("OPA228_P6.pdf")
        self.assert_rejected("pdf_fingerprint", review)
        self.source = original_pdf
        # JSON 仍可解析，表格 HTML 仍相同，但真实内容列表字节已变化。
        self.write_content(self.payload + b"\n")
        self.assertEqual(self.convert().metadata.logical_table_groups[0].fragments[0].raw_html, _TABLE)
        self.assert_rejected("content_list_fingerprint", review)

    def test_rejects_mismatched_table_binding_and_invalid_source_cell(self) -> None:
        review = self.review(self.convert())
        for update, reason in (
            ({"raw_html_sha256": "0" * 64}, "source_binding"),
            ({"page_index": 1}, "source_binding"),
            ({"json_pointer": "/0/9"}, "missing_target"),
        ):
            with self.subTest(update=update):
                self.assert_rejected(reason, review.model_copy(update=update))
        cell, = review.corrections
        for update, reason in (
            ({"source_cell_index": 9}, "cell_binding"),
            ({"content_sha256": "0" * 64}, "cell_binding"),
            ({"original_column_range": (1, 4)}, "cell_binding"),
            ({"target_column": 3, "target_header": "MAX"}, "target_column"),
            ({"target_column": 1}, "target_column"),
            ({"target_column": True}, "invalid_input"),
        ):
            with self.subTest(update=update):
                changed = cell.model_copy(update=update)
                self.assert_rejected(reason, review.model_copy(update={"corrections": (changed,)}))

    def test_rejects_review_for_span_including_unit_column(self) -> None:
        self.write_package(
            "<table><tr><th>Parameter</th><th>MIN</th><th>TYP</th><th>UNIT</th></tr>"
            "<tr><td>Offset</td><td colspan='3'>±5</td></tr></table>",
        )
        document = self.convert()
        self.assertIn(_RULE, {item.flag.code for item in validate_document_tables(document).reports[0].findings})
        self.assert_rejected("unsupported_shape", self.review(document))

    def test_entire_batch_is_verified_before_any_attachment(self) -> None:
        document = self.convert()
        original = document.model_dump_json()
        first = self.review(document)
        second = self.review(document, group_index=1)
        invalid = second.model_copy(update={"raw_html_sha256": "0" * 64})
        with self.assertRaisesRegex(TableValueColumnReviewError, "source_binding"):
            attach_table_value_column_reviews(
                document, (first, invalid), first.content_list_sha256, lambda: self.source,
            )
        self.assertEqual(document.model_dump_json(), original)
        self.assert_rejected("duplicate_target", first, first)
        self.assert_rejected("duplicate_target", first.model_copy(update={"corrections": first.corrections * 2}))

    def test_persisted_ir_rejects_detached_review(self) -> None:
        review = self.review(self.convert())
        serialized = self.convert(review).model_dump(mode="json")
        fragment = serialized["metadata"]["logical_table_groups"][0]["fragments"][0]
        fragment["value_column_review"]["content_list_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "content_list_fingerprint"):
            DocumentIR.model_validate_json(json.dumps(serialized))
