"""管理员同包核定的严格输入和累计人工记录回归。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4
from zipfile import ZipFile

from pydantic import ValidationError

from app.domains.document_jobs.schemas.quality_review import DocumentJobNewGenerationRequest
from app.domains.document_jobs.use_cases.table_value_generation import _verified_reviews
from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnBinding,
    PdfValueColumnUnresolved,
    TableValueColumnCorrection,
    TableValueColumnReview,
    resolve_table_value_column_review,
)
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.models import make_cell_id
from app.services.tables.quality import BINDING_VALIDATOR_VERSION
from app.services.tables.validator import validate_document_tables


def _payload() -> dict:
    return {
        "request_id": str(uuid4()),
        "note": "核对原表",
        "expected_source": {"generation": 0, "result_file_id": None, "result_sha256": None,
            "file_review_source_revision": None, "receipt_sha256": None},
    }


def _manual_review_payload() -> dict:
    return {
        "schema_version": "table-value-column-review/v1",
        "source_pdf_sha256": "1" * 64,
        "content_list_sha256": "2" * 64,
        "page_index": 0,
        "json_pointer": "/0/0",
        "raw_html_sha256": "3" * 64,
        "normalizer_version": "table-html/v1",
        "corrections": [{"source_row_index": 1, "source_cell_index": 1, "content_sha256": "4" * 64,
            "original_column_range": [1, 3], "target_column": 2, "target_header": "HIGH"}],
    }


class TableValueGenerationSchemaTests(TestCase):
    def test_accepts_ordinary_new_generation_and_strict_json_manual_records(self) -> None:
        payload = _payload()
        self.assertIsNone(DocumentJobNewGenerationRequest.model_validate(payload).table_value_column_reviews)
        review = _manual_review_payload()
        request = DocumentJobNewGenerationRequest.model_validate({
            **payload, "action": "replay_table_value_columns", "table_value_column_reviews": [review],
        })
        manual, = request.table_value_column_reviews
        self.assertEqual(manual.model_dump(mode="json"), review)
        self.assertEqual(manual.corrections[0].original_column_range, (1, 3))

    def test_rejects_incomplete_action_forged_provenance_and_noninteger_column(self) -> None:
        base = _payload()
        review = _manual_review_payload()
        with self.assertRaises(ValidationError):
            DocumentJobNewGenerationRequest.model_validate({**base, "table_value_column_reviews": [review]})
        replay = {**base, "action": "replay_table_value_columns"}
        for invalid in (None, []):
            with self.assertRaises(ValidationError):
                DocumentJobNewGenerationRequest.model_validate({**replay, "table_value_column_reviews": invalid})
        for field, value in (("pdf_binding", None), ("original_column_range", ["1", 3])):
            malformed = deepcopy(review)
            malformed["corrections"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                DocumentJobNewGenerationRequest.model_validate({**replay, "table_value_column_reviews": [malformed]})


class TableValueGenerationSelectionTests(TestCase):
    def test_carries_certified_manual_cells_and_leaves_automatic_cells_for_new_observation(self) -> None:
        html = ("<table><tr><th>Parameter</th><th>LOW</th><th>HIGH</th><th>UNIT</th></tr>"
                + "".join(f"<tr><td>Pulse {row}</td><td colspan='2'>{row}</td><td>ms</td></tr>" for row in range(1, 4))
                + "</table>")
        block = {"type": "table", "content": {"html": html}, "bbox": [50, 100, 950, 400]}
        with TemporaryDirectory() as directory:
            archive_path = Path(directory) / "input.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("sample_content_list_v2.json", json.dumps([[block]]))
            document = MinerUToDocumentIRService().convert_zip(
                archive_path, job_id="job", source_file_id="source", document_language="en",
            ).document
        group, = document.metadata.logical_table_groups
        fragment, = group.fragments
        content_sha256 = document.metadata.mineru_validation.content_list_sha256
        grid = build_table_grid(group, source_content_sha256=content_sha256)
        values = {cell.source_row_index: cell for cell in grid.grid.cells if cell.source_cell_index == 1 and cell.colspan == 2}
        pdf_sha256 = "1" * 64
        binding = PdfValueColumnBinding(extractor_version="测试", layout_sha256="2" * 64,
            table_bbox=(50.0, 100.0, 950.0, 400.0), row_range=(200.0, 240.0), column_range=(400.0, 530.0),
            header_bbox=(410.0, 121.0, 418.0, 132.0), value_bbox=(420.0, 204.0, 425.0, 214.0),
            unit_bbox=(550.0, 204.0, 560.0, 214.0), row_anchor_bboxes=((51.0, 204.0, 65.0, 214.0),),
            glyph_anchors=((422.0, 210.0),))
        manual, automatic, fresh = (
            TableValueColumnCorrection(source_row_index=row, source_cell_index=1, content_sha256=values[row].content_sha256,
                original_column_range=(1, 3), target_column=2, target_header="HIGH")
            for row in (1, 2, 3)
        )
        automatic = automatic.model_copy(update={"pdf_binding": binding})
        previous = TableValueColumnReview(schema_version="table-value-column-review/v1",
            source_pdf_sha256=pdf_sha256, content_list_sha256=content_sha256, page_index=fragment.source_span.page_index,
            json_pointer=fragment.source_span.json_pointer, raw_html_sha256=fragment.raw_html_sha256,
            normalizer_version=grid.normalizer_version, corrections=(manual, automatic))
        validation, = validate_document_tables(document, validator_version=BINDING_VALIDATOR_VERSION).reports
        fragment.value_column_review = previous
        submitted = previous.model_copy(update={"corrections": (fresh,)})
        _, (finding,) = resolve_table_value_column_review(submitted, group, source_content_sha256=content_sha256)
        unresolved = PdfValueColumnUnresolved(fragment_id=fragment.fragment_id, finding_id=finding.finding_id,
            source_row_index=3, source_cell_index=1, reason="row_ambiguous")
        certified = [SimpleNamespace(review_sha256=previous.review_sha256,
            source_cell_id=make_cell_id(fragment.fragment_id, row, 1), target_column=2, pdf_binding_sha256=proof)
            for row, proof in ((1, None), (2, binding.binding_sha256))]
        table = SimpleNamespace(logical_group_id=group.logical_group_id, render_state="native",
            value_column_corrections=certified, validation=validation)
        verified = SimpleNamespace(document=document, unresolved_value_columns={finding.finding_id: (unresolved, finding)},
            envelope=SimpleNamespace(report=SimpleNamespace(tables=[table])))
        merged, = _verified_reviews(verified, (submitted,), pdf_sha256=pdf_sha256, content_list_sha256=content_sha256)
        self.assertEqual(merged.corrections, (manual, fresh))
