"""通过本地正式入口验证 PDF 数值列核定的实物和交付证据。"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from docx import Document

from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.pdf_value_column_observer import PdfValueColumnPage
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnBinding,
    PdfValueColumnUnresolved,
    TableValueColumnCorrection,
    TableValueColumnReviewError,
)
from app.services.renderer.content_contract import build_formula_source_coverage
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.logical_table_plan import build_content_table_plan
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from app.services.tables.evidence import read_table_evidence
from app.services.tables.models import canonical_sha256
from app.services.tables.quality import TableValidationPolicy, make_finding_id
from app.services.tables.validator import iter_parameter_value_column_spans
from scripts.dev import formal_mineru_conversion, run_local_mineru_conversion
from tests.document_job_list_query_v2_publication_fixtures import pdf_bytes
from tests.test_formula_rendering import NS, changed_docx
from tests.test_table_value_column_span import _CODE, _GS008_ROWS
from tests.test_table_value_column_span_delivery import _word_value_columns


class TableValuePdfBindingDeliveryTests(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.package = self.root / "mineru"
        self.package.mkdir()
        self.pdf = self.package / "sample_origin.pdf"
        self.pdf.write_bytes(pdf_bytes())
        blocks = [[{"type": "table", "bbox": [125, 250, 875, 750],
                    "content": {"html": f"<table>{_GS008_ROWS}</table>"}}]]
        (self.package / "sample_content_list_v2.json").write_text(json.dumps(blocks), encoding="utf-8")
        bbox = [9, 18, 63, 54]
        body = {"type": "table_body", "index": 0, "bbox": bbox,
                "lines": [{"bbox": bbox, "spans": [{"type": "table", "bbox": bbox,
                                                     "html": f"<table>{_GS008_ROWS}</table>"}]}]}
        table = {"type": "table", "index": 0, "bbox": bbox, "blocks": [body]}
        layout = {"_version_name": "3.1.8", "pdf_info": [{
            "page_idx": 0, "page_size": [72, 72], "para_blocks": [table], "preproc_blocks": [table],
        }]}
        self.layout_path = self.package / "sample_layout.json"
        self.layout_path.write_text(json.dumps(layout), encoding="utf-8")

    def _argv(self, name: str, *, pdf: Path | None = None) -> list[str]:
        return [str(self.package), "--no-template", "--document-language", "en", "--output",
                str(self.root / name), "--source-pdf", str(pdf or self.pdf), "--auto-table-value-columns"]

    def _convert(self, name: str, *, pdf: Path | None = None) -> formal_mineru_conversion.FormalMinerUConversionResult:
        parsed = run_local_mineru_conversion.parse_args(self._argv(name, pdf=pdf))
        return formal_mineru_conversion.run_conversion(**run_local_mineru_conversion.build_conversion_kwargs(parsed))

    def test_cli_requires_source_pdf_and_original_layout(self) -> None:
        output = self.root / "rejected.docx"
        args = self._argv(output.name)
        index = args.index("--source-pdf")
        for invocation, diagnostic in (
            (args[:index] + args[index + 2:], "必须提供 --source-pdf"),
            (args + ["--translation-mode", "en2zh"], "仅支持原排版转换"),
        ):
            with self.subTest(diagnostic=diagnostic), mock.patch.object(run_local_mineru_conversion, "configure_logging"):
                with self.assertRaisesRegex(SystemExit, diagnostic):
                    run_local_mineru_conversion.main(invocation)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".document-ir.json").exists())

    def test_same_named_different_pdf_preserves_word_blockers_and_source_locations(self) -> None:
        other_dir = self.root / "other-source"
        other_dir.mkdir()
        other_pdf = other_dir / self.pdf.name
        other_pdf.write_bytes(self.pdf.read_bytes() + b"% separate fingerprint\n")
        result = self._convert("unpaired.docx", pdf=other_pdf)
        evidence = read_table_evidence(result.renderer_metadata["table_evidence"])
        table_evidence, = evidence.tables
        self.assertEqual((evidence.status, evidence.counts.blocker_count), ("blocked", 2))
        self.assertIsNone(table_evidence.value_column_corrections)
        finding_ids = {finding.finding_id for finding in table_evidence.validation.findings if finding.flag.code == _CODE}
        self.assertEqual({issue.finding_id for issue in result.pdf_value_column_unresolved}, finding_ids)
        self.assertEqual({(issue.source_row_index, issue.source_cell_index) for issue in result.pdf_value_column_unresolved},
                         {(2, 4), (3, 1)})
        self.assertEqual({issue.reason for issue in result.pdf_value_column_unresolved}, {"source_pair_unverified"})
        document = DocumentIR.model_validate_json(result.document_ir_path.read_bytes())
        self.assertEqual(document.metadata.pdf_value_column_unresolved, result.pdf_value_column_unresolved)
        table, = Document(result.output_docx_path).tables
        self.assertEqual([row[1] for row in _word_value_columns(table)], [("±5", 2), ("±100", 3)])

    def _one_proposed_binding(self, source, observation, table_bbox, *, layout_sha256, skip_cells, layout_bbox,
                              protected_regions, legacy_value_column_replay):
        """替换坐标取证结果，保留修正接纳、渲染和实物认证链路。"""
        self.assertEqual(skip_cells, frozenset())
        self.assertIsNone(legacy_value_column_replay)
        self.assertEqual(layout_sha256, sha256(self.layout_path.read_bytes()).hexdigest())
        first, second = iter_parameter_value_column_spans(source, TableValidationPolicy())
        _, located, _ = first
        cell = next(cell for cell in source.grid.cells if cell.id == located.cell_id)
        proof = PdfValueColumnBinding(
            extractor_version=observation.extractor_version, layout_sha256=layout_sha256, table_bbox=table_bbox,
            row_range=(27.0, 33.0), column_range=(38.0, 45.0), header_bbox=(40.0, 19.0, 43.0, 20.0),
            value_bbox=(40.5, 28.0, 43.0, 30.0), unit_bbox=(59.0, 28.0, 62.0, 30.0),
            row_anchor_bboxes=((48.0, 28.0, 51.0, 30.0),), glyph_anchors=((40.6, 29.8), (42.0, 29.8)),
        )
        correction = TableValueColumnCorrection(
            source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
            content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
            target_column=5, target_header="TYP", pdf_binding=proof,
        )
        blocked, location, _ = second
        issue = PdfValueColumnUnresolved(
            fragment_id=blocked.fragment_id, finding_id=make_finding_id(source.grid.table_id, blocked, location),
            source_row_index=location.source_row_index, source_cell_index=location.source_cell_index,
            reason="row_ambiguous",
        )
        return (correction,), (issue,)

    def test_pdf_provenance_and_blocker_resolution_require_actual_word_on_reopening(self) -> None:
        page = PdfValueColumnPage(width=72.0, height=72.0, page_count=1, words=(), rectangles=(),
                                  horizontal_lines=(), vertical_lines=(), extractor_version="synthetic-test")
        with (
            mock.patch("app.services.document_ir.pdf_value_column_observer.observe_pdf_value_column_page", return_value=page),
            mock.patch("app.services.document_ir.pdf_value_column_binding.match_pdf_value_columns",
                       side_effect=self._one_proposed_binding),
        ):
            result = self._convert("certified.docx")

        metadata = result.renderer_metadata
        evidence = read_table_evidence(metadata["table_evidence"])
        table, = evidence.tables
        self.assertEqual((evidence.status, evidence.counts.blocker_count), ("blocked", 1))
        self.assertEqual(len([finding for finding in table.validation.findings if finding.flag.code == _CODE]), 2)
        unreviewed, = result.pdf_value_column_unresolved
        self.assertEqual([flag.identity for flag in table.flags if flag.code == _CODE], [unreviewed.finding_id])
        correction, = table.value_column_corrections
        document = DocumentIR.model_validate_json(result.document_ir_path.read_bytes())
        source_group, = document.metadata.logical_table_groups
        source_fragment, = source_group.fragments
        review = source_fragment.value_column_review
        source_correction, = review.corrections
        self.assertEqual(correction.pdf_binding_sha256, source_correction.pdf_binding.binding_sha256)
        self.assertEqual((correction.output_row, correction.target_column), (2, 5))
        word_table, = Document(result.output_docx_path).tables
        self.assertEqual(_word_value_columns(word_table)[0], (("", 1), ("±5", 1), ("±75", 1), ("μV", 1)))
        content = result.output_docx_path.read_bytes()
        self.assertEqual(validate_persisted_renderer_content(document, content, metadata)["table_evidence"],
                         metadata["table_evidence"])
        with self.assertRaisesRegex(TableValueColumnReviewError, "invalid_input"):
            formal_mineru_conversion.parse_table_value_column_reviews(f"[{review.model_dump_json()}]".encode())

        for replacement in (None, "0" * 64):
            with self.subTest(provenance=replacement):
                tampered = deepcopy(metadata)
                report = tampered["table_evidence"]
                item, = report["tables"][0]["value_column_corrections"]
                if replacement is None:
                    del item["pdf_binding_sha256"]
                else:
                    item["pdf_binding_sha256"] = replacement
                del report["report_sha256"]
                report["report_sha256"] = canonical_sha256(report)
                with self.assertRaises(DocumentIntegrityError) as rejected:
                    validate_persisted_renderer_content(document, content, tampered)
                self.assertIn("ir_render_evidence:binding_mismatch", rejected.exception.evidence["blocking_quality_flags"])

        def swap_values(xml) -> None:
            nodes = {node.text: node for node in xml.findall(".//w:tc//w:t", NS) if node.text in {"±5", "±75"}}
            nodes["±5"].text, nodes["±75"].text = "±75", "±5"

        wrong_column = changed_docx(content, swap_values)
        plan = build_content_table_plan(document, build_layout_plan(document))
        # 重新计算覆盖证据，直接检验实际格位门禁而非仅靠文件散列拒绝。
        refreshed = {**metadata, "formula_source_coverage": build_formula_source_coverage(
            document, wrong_column, plan, metadata["formula_report"],
        )}
        with self.assertRaises(DocumentIntegrityError) as rejected:
            validate_persisted_renderer_content(document, wrong_column, refreshed)
        self.assertIn("ir_render_evidence:target_mismatch", rejected.exception.evidence["blocking_quality_flags"])
