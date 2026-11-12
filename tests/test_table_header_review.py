from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree
from zipfile import ZipFile

from app.domains.translation.models import TranslationTextItem
from app.domains.translation.table_context import TableContextBuilder
from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_header_review import TableHeaderReview, TableHeaderReviewError
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.render_evidence import build_renderer_evidence, validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.tables.evidence import TableEvidence, read_table_evidence
from app.services.tables.grid_builder import build_render_table_grid, build_table_grid
from app.services.tables.models import canonical_sha256


_WORD = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_PDF = b"%PDF-1.7\n% test identity\n"
_MANUAL = ("<table><thead><tr><td rowspan='2' colspan='2'>Limits</td></tr><tr></tr></thead>"
           "<tr><td>Gain</td><td>5</td></tr></table>")


class TableHeaderReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "mineru.zip"
        self.source = PdfCropSource("test-source", checksum(_PDF), _PDF)

    def review(self, html: str, row_count: int) -> TableHeaderReview:
        payload = json.dumps([[{"type": "table", "bbox": [20, 30, 180, 140], "content": {"html": html}}]])
        with ZipFile(self.path, "w") as archive:
            archive.writestr("content_list_v2.json", payload)
        return TableHeaderReview(
            source_pdf_sha256=sha256(_PDF).hexdigest(), content_list_sha256=sha256(payload.encode()).hexdigest(),
            json_pointer="/0/0", page_index=0, raw_html_sha256=sha256(html.encode()).hexdigest(),
            header_row_count=row_count,
        )

    def convert(self, *reviews: TableHeaderReview) -> DocumentIR:
        return MinerUToDocumentIRService().convert_zip(
            self.path, job_id="test-job", source_file_id="test-source", document_language="en",
            placeholder_source_loader=lambda: self.source, table_header_reviews=reviews,
        ).document

    def render(self, document: DocumentIR) -> tuple[list[int], TableEvidence]:
        result = DocumentIRWordRenderer().render_to_result(
            document, template_path=None, config_path=None, image_loader=lambda _asset: None,
        )
        with ZipFile(BytesIO(result.content)) as archive:
            xml = ElementTree.fromstring(archive.read("word/document.xml"))
        table = xml.find("w:body/w:tbl", _WORD)
        self.assertIsNotNone(table)
        rows = table.findall("w:tr", _WORD)
        header_rows = [i for i, row in enumerate(rows) if row.find("w:trPr/w:tblHeader", _WORD) is not None]
        evidence = build_renderer_evidence(document, result.content, render_result=result)
        ensure_renderer_integrity(evidence)
        validate_persisted_renderer_content(document, result.content, evidence)
        table_evidence, = read_table_evidence(evidence["table_evidence"]).tables
        return header_rows, table_evidence

    def test_review_applies_to_grid_word_evidence_and_translation_context(self) -> None:
        review = self.review(_MANUAL, 2)
        baseline = self.convert()
        accepted = self.convert(review)
        accepted = DocumentIR.model_validate_json(accepted.model_dump_json())
        group, = accepted.metadata.logical_table_groups
        original_group, = baseline.metadata.logical_table_groups
        fragment, = group.fragments
        original = build_table_grid(original_group, source_content_sha256=review.content_list_sha256)
        checked = build_table_grid(group, source_content_sha256=review.content_list_sha256)
        self.assertEqual(original.grid.header_rows, [])
        self.assertEqual(checked.grid.header_rows, [0, 1])
        self.assertEqual(original.normalized_fragments, checked.normalized_fragments)
        self.assertEqual(original.grid.raw_html_sha256, checked.grid.raw_html_sha256)
        self.assertEqual(fragment.header_review, review)
        self.assertEqual(fragment.raw_html, _MANUAL)
        self.assertEqual(accepted.blocks[0].html, baseline.blocks[0].html)
        self.assertEqual([(cell.row, cell.column, cell.rowspan, cell.colspan) for cell in checked.grid.cells],
                         [(0, 0, 2, 2), (2, 0, 1, 1), (2, 1, 1, 1)])

        block, = accepted.blocks
        before = build_render_table_grid(block, block_index=0)
        after = build_render_table_grid(block, block_index=0, header_review=review)
        self.assertEqual(before.input_sha256, canonical_sha256([
            "document-ir-table-render-input/v1", block.id, "/blocks/0", block.html,
        ]))
        self.assertNotEqual(before.input_sha256, after.input_sha256)
        old_headers, old_evidence = self.render(baseline)
        self.assertEqual(old_headers, [])
        self.assertNotIn("header_review", old_evidence.validation.fragments[0].model_dump())

        accepted.blocks[0].html = block.html.replace("Limits", "限制").replace("Gain", "增益")
        headers, evidence = self.render(accepted)
        self.assertEqual(headers, [0, 1])
        self.assertEqual(evidence.source_grid.header_rows, [0, 1])
        self.assertEqual(evidence.validation.fragments[0].header_review, review)
        data_cell = TranslationTextItem(id=f"{block.id}.html.0001", text="Gain")
        old_context = TableContextBuilder().build(baseline, (data_cell,))[data_cell.id]
        checked_context = TableContextBuilder().build(accepted, (data_cell,))[data_cell.id]
        self.assertEqual(old_context.header_path, ())
        self.assertEqual(checked_context.header_path, ("限制",))

    def test_native_header_wins_after_source_binding_and_before_review_geometry(self) -> None:
        review = self.review("<table><tr><th colspan='2'>Limits</th></tr>"
                             "<tr><td>Gain</td><td>5</td></tr></table>", 20)
        baseline = self.convert()
        accepted = self.convert(review)
        self.assertEqual(accepted.model_dump_json(), baseline.model_dump_json())
        self.assertNotIn("header_review", accepted.metadata.logical_table_groups[0].fragments[0].model_dump())
        headers, evidence = self.render(accepted)
        self.assertEqual(headers, [0])
        self.assertEqual(evidence.source_grid.header_rows, [0])
        with self.assertRaisesRegex(TableHeaderReviewError, "source_binding"):
            self.convert(review.model_copy(update={"raw_html_sha256": "0" * 64}))

    def test_review_rejects_wrong_source_or_duplicate_binding(self) -> None:
        review = self.review(_MANUAL, 2)
        for update, reason in (
            ({"source_pdf_sha256": "0" * 64}, "pdf_fingerprint"),
            ({"content_list_sha256": "0" * 64}, "source_binding"),
            ({"json_pointer": "/0/1"}, "missing_target"),
            ({"page_index": 1}, "source_binding"),
        ):
            with self.subTest(update=update), self.assertRaisesRegex(TableHeaderReviewError, reason):
                self.convert(review.model_copy(update=update))
        with self.assertRaisesRegex(TableHeaderReviewError, "duplicate_target"):
            self.convert(review, review)
        source = self.source
        for changed in (replace(source, file_id="another-source"), replace(source, content=_PDF + b"changed")):
            self.source = changed
            with self.subTest(source=changed.file_id), self.assertRaisesRegex(TableHeaderReviewError, "pdf_source"):
                self.convert(review)

    def test_review_rejects_header_boundary_crossed_by_rowspan(self) -> None:
        review = self.review(_MANUAL, 1)
        with self.assertRaisesRegex(TableHeaderReviewError, "header_geometry"):
            self.convert(review)

    def test_review_prefix_does_not_absorb_later_upstream_header_cells(self) -> None:
        review = self.review("<table><tr><td>Title</td></tr><tr><th>Row label</th></tr>"
                             "<tr><td>Value</td></tr></table>", 1)
        accepted = self.convert(review)
        source = build_table_grid(accepted.metadata.logical_table_groups[0],
                                  source_content_sha256=review.content_list_sha256)
        self.assertEqual(source.grid.header_rows, [0])
        self.assertTrue(source.grid.cells[1].is_header)
        headers, evidence = self.render(accepted)
        self.assertEqual(headers, [0])
        self.assertEqual(evidence.source_grid.header_rows, [0])

    def test_review_does_not_authorize_removing_continuation_rows(self) -> None:
        tables = [f"<table><tr><th>Pin</th><td>Value</td></tr><tr><td>{index + 1}</td><td>A</td></tr></table>"
                  for index in range(2)]
        payload = json.dumps([
            [{"type": "table", "bbox": [20, 650, 980, 980], "content": {"html": tables[0]}}],
            [{"type": "table", "bbox": [20, 20, 980, 350], "content": {"html": tables[1]}}],
        ])
        with ZipFile(self.path, "w") as archive:
            archive.writestr("content_list_v2.json", payload)
            archive.writestr("layout.json", json.dumps({"pdf_info": [
                {"page_idx": index, "page_size": [1000, 1000]} for index in range(2)
            ]}))
        baseline = self.convert()
        group, = baseline.metadata.logical_table_groups
        self.assertIsNotNone(group.fragments[1].repeated_header_hint)
        reviewed = self.convert(*(TableHeaderReview(
            source_pdf_sha256=sha256(_PDF).hexdigest(), content_list_sha256=sha256(payload.encode()).hexdigest(),
            json_pointer=f"/{index}/0", page_index=index, raw_html_sha256=sha256(html.encode()).hexdigest(),
            header_row_count=1,
        ) for index, html in enumerate(tables)))
        _, baseline_evidence = self.render(baseline)
        headers, evidence = self.render(reviewed)
        self.assertEqual(headers, [0])
        self.assertEqual(evidence.outputs[0].fragments[1].removed_header_rows,
                         baseline_evidence.outputs[0].fragments[1].removed_header_rows)
        self.assertIsNone(evidence.outputs[0].fragments[1].removed_header_rows)
