"""通过本地正式入口核对 gs-008 片段的值列、来源和交付证据。"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from zipfile import ZipFile

from docx import Document

from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR
from app.services.renderer.content_contract import build_formula_source_coverage
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.logical_table_plan import build_content_table_plan
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from app.services.tables.evidence import TableEvidenceError, read_table_evidence
from app.services.tables.models import canonical_sha256
from app.services.tables.validator import validate_document_tables
from scripts.dev import formal_mineru_conversion, run_local_mineru_conversion
from tests.document_job_list_query_v2_publication_fixtures import pdf_bytes
from tests.test_formula_rendering import NS, changed_docx
from tests.test_table_value_column_span import _CODE, _GS008_ROWS
from tests.test_table_value_column_span_delivery import _gs008_package, _word_value_columns


class TableValueColumnReviewDeliveryTests(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.package = self.root / "mineru.zip"
        self.package.write_bytes(_gs008_package(_GS008_ROWS))
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(pdf_bytes())
        source = MinerUToDocumentIRService().convert_zip(
            self.package, job_id=formal_mineru_conversion.LOCAL_JOB_ID,
            source_file_id=formal_mineru_conversion.LOCAL_SOURCE_FILE_ID, document_language="en",
        ).document
        self.source_report, = validate_document_tables(source).reports
        fragment, = self.source_report.fragments
        cells = {cell.id: cell for cell in self.source_report.cells}
        findings = [finding for finding in self.source_report.findings if finding.flag.code == _CODE]
        self.assertEqual([(f.evidence.row, f.evidence.column, f.evidence.end_column) for f in findings],
                         [(2, 4, 6), (3, 4, 7)])
        self.findings = findings
        self.review_data = [{
            "schema_version": "table-value-column-review/v1",
            "source_pdf_sha256": sha256(self.pdf.read_bytes()).hexdigest(),
            "content_list_sha256": self.source_report.source_content_sha256,
            "json_pointer": fragment.json_pointer,
            "page_index": fragment.page_index,
            "raw_html_sha256": fragment.raw_html_sha256,
            "normalizer_version": self.source_report.normalizer_version,
            "corrections": [
                {"source_row_index": cell.source_row_index, "source_cell_index": cell.source_cell_index,
                 "content_sha256": cell.content_sha256,
                 "original_column_range": [cell.column, cell.column + cell.colspan],
                 "target_column": column, "target_header": header}
                for cell, (column, header) in zip(
                    (cells[f.evidence.cell_id] for f in self.findings), ((5, "TYP"), (6, "MAX")), strict=True,
                )
            ],
        }]
        self.review = self.root / "review.json"
        self.review.write_text(json.dumps(self.review_data), encoding="utf-8")

    def _argv(self, output: Path, *, review: bool = True, package: Path | None = None,
              pdf: Path | None = None) -> list[str]:
        args = [str(package or self.package), "--no-template", "--document-language", "en",
                "--output", str(output), "--source-pdf", str(pdf or self.pdf)]
        if review:
            args += ["--table-value-column-reviews", str(self.review)]
        return args

    def _convert(self, name: str, *, review: bool = True) -> formal_mineru_conversion.FormalMinerUConversionResult:
        args = run_local_mineru_conversion.parse_args(self._argv(self.root / name, review=review))
        return formal_mineru_conversion.run_conversion(**run_local_mineru_conversion.build_conversion_kwargs(args))

    def test_corrected_docx_and_reopened_evidence_bind_only_the_two_reviewed_values(self) -> None:
        result = self._convert("reviewed.docx")
        metadata = result.renderer_metadata
        evidence = read_table_evidence(metadata["table_evidence"])
        table_evidence, = evidence.tables
        self.assertEqual(table_evidence.validation, self.source_report)
        self.assertEqual(evidence.counts.blocker_count, 0)
        self.assertFalse(any(flag.code == _CODE for flag in table_evidence.flags))
        self.assertEqual([(item.finding_id, item.target_column, item.output_row)
                          for item in table_evidence.value_column_corrections],
                         [(self.findings[0].finding_id, 5, 2), (self.findings[1].finding_id, 6, 3)])
        document = DocumentIR.model_validate_json(result.document_ir_path.read_bytes())
        group, = document.metadata.logical_table_groups
        fragment, = group.fragments
        self.assertEqual(fragment.value_column_review.review_sha256,
                         table_evidence.value_column_corrections[0].review_sha256)
        self.assertEqual(fragment.raw_html, f"<table>{_GS008_ROWS}</table>")
        content = result.output_docx_path.read_bytes()
        table, = Document(result.output_docx_path).tables
        self.assertEqual(_word_value_columns(table), [
            (("", 1), ("±5", 1), ("±75", 1), ("μV", 1)),
            (("", 1), ("", 1), ("±100", 1), ("μV", 1)),
        ])
        self.assertEqual([table.rows[row]._tr.tc_lst[7].vMerge for row in (2, 3)], ["restart", "continue"])
        restored = validate_persisted_renderer_content(document, content, metadata)
        self.assertEqual(metadata["table_evidence"], restored["table_evidence"])

        baseline = self._convert("unreviewed.docx", review=False)
        baseline_evidence = read_table_evidence(baseline.renderer_metadata["table_evidence"])
        self.assertEqual(baseline_evidence.counts.blocker_count, 2)
        self.assertNotIn("value_column_corrections", baseline.renderer_metadata["table_evidence"]["tables"][0])
        old_content = baseline.output_docx_path.read_bytes()
        baseline_ir = DocumentIR.model_validate_json(baseline.document_ir_path.read_bytes())
        self.assertEqual(validate_persisted_renderer_content(baseline_ir, old_content, baseline.renderer_metadata)
                         ["table_evidence"], baseline.renderer_metadata["table_evidence"])
        with self.assertRaises(DocumentIntegrityError):
            validate_persisted_renderer_content(document, old_content, metadata)

        def swap_values(xml) -> None:
            # 只交换同一行的两个数值，保留 Word 单元格跨度及标记。
            cells = {node.text: node for node in xml.findall(".//w:tc//w:t", NS) if node.text in {"±5", "±75"}}
            cells["±5"].text, cells["±75"].text = "±75", "±5"

        wrong_column = changed_docx(content, swap_values)
        layout = build_layout_plan(document)
        tables = build_content_table_plan(document, layout)
        for name, wrong_content, template_proof, diagnostic in (
            ("原跨列实物", old_content, baseline.renderer_metadata["template_conformance"],
             "ir_docx_integrity:table_"),
            ("同跨度错列", wrong_column, metadata["template_conformance"], "ir_render_evidence:target_mismatch"),
        ):
            with self.subTest(document=name):
                # 避开单纯的文件指纹不一致，验证表格结构和内容各自拒绝错列。
                refreshed = {
                    **metadata,
                    "formula_source_coverage": build_formula_source_coverage(
                        document, wrong_content, tables, metadata["formula_report"],
                    ),
                    "template_conformance": template_proof,
                }
                with self.assertRaises(DocumentIntegrityError) as rejected:
                    validate_persisted_renderer_content(document, wrong_content, refreshed)
                reasons = rejected.exception.evidence["blocking_quality_flags"]
                self.assertTrue(any(reason.startswith(diagnostic) for reason in reasons), reasons)

    def test_reopening_rejects_missing_or_detached_correction_proof(self) -> None:
        result = self._convert("reviewed-proof.docx")
        metadata = result.renderer_metadata
        for defect in ("缺少修正证据", "核定指纹脱离渲染片段"):
            with self.subTest(defect=defect):
                report = deepcopy(metadata["table_evidence"])
                table, = report["tables"]
                if defect == "缺少修正证据":
                    del table["value_column_corrections"]
                else:
                    table["value_column_corrections"][0]["review_sha256"] = "0" * 64
                # 重新计算顶层指纹，直接检验修正证据和已解除告警的对应关系。
                del report["report_sha256"]
                report["report_sha256"] = canonical_sha256(report)
                with self.assertRaisesRegex(TableEvidenceError, "table_evidence_integrity"):
                    read_table_evidence(report)

        document = DocumentIR.model_validate_json(result.document_ir_path.read_bytes())
        content = result.output_docx_path.read_bytes()
        for missing, diagnostic in (
            ({"table_evidence"}, "ir_render_evidence:binding_mismatch"),
            ({"renderer_content_contract_version", "formula_source_coverage"}, "ir_render_evidence:invalid_contract"),
        ):
            with self.subTest(missing=missing):
                with self.assertRaises(DocumentIntegrityError) as rejected:
                    validate_persisted_renderer_content(
                        document, content, {key: value for key, value in metadata.items() if key not in missing},
                    )
                self.assertIn(diagnostic, rejected.exception.evidence["blocking_quality_flags"])

    def test_cli_rejects_stale_sources_and_partly_invalid_records_before_outputs(self) -> None:
        changed_pdf = self.root / "changed.pdf"
        # 在 EOF 后追加有效注释，保留 PDF 可读性并改变来源指纹。
        changed_pdf.write_bytes(self.pdf.read_bytes() + b"% new source version\n")
        changed_package = self.root / "changed.zip"
        with ZipFile(self.package) as original, ZipFile(changed_package, "w") as changed:
            for name in original.namelist():
                content = original.read(name)
                changed.writestr(name, content + b"\n" if name == "content_list_v2.json" else content)

        for reason, overrides in (
            ("pdf_fingerprint", {"pdf": changed_pdf}),
            ("content_list_fingerprint", {"package": changed_package}),
            ("cell_binding", {}),
        ):
            if reason == "cell_binding":
                self.review_data[0]["corrections"][1]["content_sha256"] = "0" * 64
                self.review.write_text(json.dumps(self.review_data), encoding="utf-8")
            output = self.root / f"rejected-{reason}.docx"
            with self.subTest(reason=reason), mock.patch.object(run_local_mineru_conversion, "configure_logging"):
                with self.assertRaisesRegex(SystemExit, rf"table_value_column_review_invalid.*{reason}"):
                    run_local_mineru_conversion.main(self._argv(output, **overrides))
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".document-ir.json").exists())

    def test_cli_requires_source_pdf_and_direct_mode_for_reviews(self) -> None:
        output = self.root / "invalid-invocation.docx"
        args = self._argv(output)
        pdf_index = args.index("--source-pdf")
        for reason, invocation in (
            ("pdf_source", args[:pdf_index] + args[pdf_index + 2:]),
            ("unsupported_translation_mode", args + ["--translation-mode", "en2zh"]),
        ):
            with self.subTest(reason=reason), mock.patch.object(run_local_mineru_conversion, "configure_logging"):
                with self.assertRaisesRegex(SystemExit, rf"table_value_column_review_invalid.*{reason}"):
                    run_local_mineru_conversion.main(invocation)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".document-ir.json").exists())
