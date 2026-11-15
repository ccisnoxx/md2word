"""验证自动核定接纳时的来源配对、未决和人工优先级。"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from zipfile import ZipFile

from pydantic import ValidationError

from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.pdf_value_column_observer import PdfObservationUnavailable, PdfValueColumnPage
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnBinding, TableValueColumnCorrection, TableValueColumnReview, TableValueColumnReviewError,
)
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.validator import validate_document_tables


_HTML = (
    "<table><tr><td>Parameter</td><td>MIN</td><td>TYP</td><td>MAX</td><td>UNIT</td></tr>"
    "<tr><td>Offset</td><td colspan='2'>±5</td><td>±75</td><td>µV</td></tr>"
    "<tr><td>Drift</td><td colspan='3'>±100</td><td>µV</td></tr></table>"
)
_FRAME = (612, 792)
_FIRST_BOX = (54, 100, 556, 220)
_PDF_FIXTURE = Path(__file__).parent / "fixtures" / "golden_samples" / "pdfs" / "OPA228_P7.pdf"
_OBSERVER = "app.services.document_ir.pdf_value_column_observer.observe_pdf_value_column_page"
_MATCHER = "app.services.document_ir.pdf_value_column_binding.match_pdf_value_columns"


class PdfValueColumnIntegrationTests(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.package = Path(directory.name) / "mineru.zip"
        self.source = PdfCropSource("pdf", checksum(content := _PDF_FIXTURE.read_bytes()), content)
        self.write_package()

    def write_package(
        self, *, origin: str | None = "sample_origin.pdf", layout: bool = True,
        boxes: tuple[tuple[int, int, int, int], ...] = (_FIRST_BOX,),
    ) -> None:
        blocks = []
        layout_tables = []
        for index, box in enumerate(boxes):
            blocks.append({
                "type": "table", "content": {"html": _HTML},
                "bbox": [int(value * 1000 / _FRAME[axis % 2]) for axis, value in enumerate(box)],
            })
            layout_tables.append({
                "type": "table", "index": index, "bbox": box,
                "blocks": [{"type": "table_body", "index": index, "bbox": box}],
            })
        with ZipFile(self.package, "w") as archive:
            archive.writestr("sample_content_list_v2.json", json.dumps([blocks]))
            if origin is not None:
                archive.writestr(origin, self.source.content)
            if layout:
                archive.writestr("sample_layout.json", json.dumps({
                    "_version_name": "3.1.8",
                    "pdf_info": [{"page_idx": 0, "page_size": _FRAME, "para_blocks": layout_tables}],
                }))

    def convert(self, *manual: TableValueColumnReview, auto: bool = True) -> DocumentIR:
        return MinerUToDocumentIRService().convert_zip(
            self.package, job_id="job", source_file_id="pdf", document_language="en",
            placeholder_source_loader=lambda: self.source,
            table_value_column_reviews=manual, auto_table_value_columns=auto,
        ).document

    @staticmethod
    def _cell_correction(result, source_row: int, target: int, header: str) -> TableValueColumnCorrection:
        cell = next(cell for cell in result.grid.cells
                    if (cell.source_row_index, cell.source_cell_index) == (source_row, 1))
        return TableValueColumnCorrection(
            source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
            content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
            target_column=target, target_header=header,
        )

    def manual_review(self, document: DocumentIR) -> TableValueColumnReview:
        group, = document.metadata.logical_table_groups
        fragment, = group.fragments
        content_hash = document.metadata.mineru_validation.content_list_sha256
        result = build_table_grid(group, source_content_sha256=content_hash)
        return TableValueColumnReview(
            schema_version="table-value-column-review/v1",
            source_pdf_sha256=self.source.checksum_sha256.removeprefix("sha256:"),
            content_list_sha256=content_hash, page_index=0, json_pointer="/0/0",
            raw_html_sha256=fragment.raw_html_sha256, normalizer_version=result.normalizer_version,
            corrections=(self._cell_correction(result, 1, 1, "MIN"),),
        )

    @staticmethod
    def _binding(table_bbox, layout_sha256: str) -> PdfValueColumnBinding:
        return PdfValueColumnBinding(
            extractor_version="fixture",
            layout_sha256=layout_sha256, table_bbox=table_bbox,
            row_range=(140.0, 160.0), column_range=(465.0, 515.0),
            header_bbox=(480.0, 110.0, 500.0, 120.0), value_bbox=(476.0, 145.0, 499.0, 155.0),
            unit_bbox=(520.0, 145.0, 536.0, 155.0), row_anchor_bboxes=((110.0, 146.0, 132.0, 155.0),),
            glyph_anchors=((475.999, 154.0), (483.0, 154.0), (488.0, 154.0), (494.0, 154.0)),
        )

    def test_only_verified_paired_package_and_unique_layout_can_initiate_pdf_observation(self) -> None:
        for fixture, reason in (
            ({"origin": None}, "source_pair_unverified"),
            ({"origin": "other_origin.pdf"}, "source_pair_unverified"),
            ({"layout": False}, "layout_unverified"),
            ({"boxes": (_FIRST_BOX, _FIRST_BOX)}, "table_layout_unverified"),
        ):
            with self.subTest(fixture=fixture), mock.patch(_OBSERVER) as observe:
                self.write_package(**fixture)
                document = self.convert()
                observe.assert_not_called()
                self.assertTrue(all(not fragment.value_column_review for group in document.metadata.logical_table_groups
                                    for fragment in group.fragments))
                self.assertEqual({issue.reason for issue in document.metadata.pdf_value_column_unresolved}, {reason})
                original = {finding.finding_id for report in validate_document_tables(document).reports
                            for finding in report.findings if finding.flag.code == "table_value_column_span_ambiguous"}
                self.assertEqual({issue.finding_id for issue in document.metadata.pdf_value_column_unresolved}, original)
                self.assertNotIn("pdf_value_column_unresolved", self.convert(auto=False).model_dump_json())

    def test_unavailable_observation_is_memoized_across_tables_on_the_page(self) -> None:
        self.write_package(boxes=(_FIRST_BOX, (54, 300, 556, 420)))
        with mock.patch(_OBSERVER, side_effect=PdfObservationUnavailable("pdf_text_unavailable")) as observe:
            document = self.convert()
        self.assertEqual(observe.call_count, 1)
        self.assertEqual(len(document.metadata.pdf_value_column_unresolved), 4)
        self.assertEqual({issue.reason for issue in document.metadata.pdf_value_column_unresolved}, {"pdf_text_unavailable"})

    def test_accepted_manual_record_owns_the_cell_and_joins_automatic_review(self) -> None:
        baseline = self.convert(auto=False)
        manual = self.manual_review(baseline)
        observed = PdfValueColumnPage(*_FRAME, 1, (), (), (), (), "fixture")

        def inspect_source(path: Path, *, page_index: int) -> PdfValueColumnPage:
            self.assertEqual(page_index, 0)
            self.assertEqual(path.read_bytes(), self.source.content)
            return observed

        def proposal(result, observation, table_bbox, *, layout_sha256, skip_cells):
            self.assertIs(observation, observed)
            self.assertEqual(skip_cells, {(1, 1)})
            correction = self._cell_correction(result, 2, 3, "MAX").model_copy(
                update={"pdf_binding": self._binding(table_bbox, layout_sha256)},
            )
            return (correction,), ()

        with mock.patch(_OBSERVER, side_effect=inspect_source), mock.patch(_MATCHER, side_effect=proposal):
            document = self.convert(manual)
        fragment = document.metadata.logical_table_groups[0].fragments[0]
        manual_applied, automatic_applied = fragment.value_column_review.corrections
        self.assertEqual(manual_applied, manual.corrections[0])
        self.assertIsNotNone(automatic_applied.pdf_binding)
        self.assertEqual(automatic_applied.target_header, "MAX")
        self.assertEqual(validate_document_tables(document), validate_document_tables(baseline))
        self.assertEqual(DocumentIR.model_validate_json(document.model_dump_json()), document)

        payload = document.model_dump(mode="json")
        review = payload["metadata"]["logical_table_groups"][0]["fragments"][0]["value_column_review"]
        self.assertNotIn("pdf_binding", review["corrections"][0])
        review["corrections"][1]["pdf_binding"]["table_bbox"][0] += 1
        with self.assertRaisesRegex(ValidationError, "pdf_binding_geometry"):
            DocumentIR.model_validate_json(json.dumps(payload))

    def test_stale_or_forged_manual_record_cannot_enter_pdf_review(self) -> None:
        manual = self.manual_review(self.convert(auto=False))
        forged = manual.corrections[0].model_copy(
            update={"pdf_binding": self._binding(_FIRST_BOX, "0" * 64)},
        )
        for review, reason, auto in (
            (manual.model_copy(update={"source_pdf_sha256": "0" * 64}), "pdf_fingerprint", True),
            (manual.model_copy(update={"corrections": (forged,)}), "invalid_input", True),
            (manual.model_copy(update={"corrections": (forged,)}), "invalid_input", False),
        ):
            with self.subTest(reason=reason, auto=auto), mock.patch(_OBSERVER) as observe:
                with self.assertRaisesRegex(TableValueColumnReviewError, reason):
                    self.convert(manual, review, auto=auto)
                observe.assert_not_called()
