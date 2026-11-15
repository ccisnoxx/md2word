"""用另一种实际 PDF 表格验证本地转换及 Word 数值列归属。"""

import json
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from zipfile import ZipFile

from docx import Document

from app.services.document_ir.models import DocumentIR
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from app.services.tables.evidence import read_table_evidence
from scripts.dev import formal_mineru_conversion, run_local_mineru_conversion
from tests.test_pdf_value_column_observer import make_pdf


def _ruled_table_package(root: Path, *, manual_review_case: bool = False) -> tuple[Path, Path]:
    """默认第三个值压列界。人工核定场景的列明确，但独立条件跨两行。"""
    column_edges = (50, 140, 200, 280, 380, 450)
    row_edges = (430, 390, 350, 310, 270)
    drawing = ["0 G 0.35 w 1 J"]
    drawing.extend(f"{x} 270 m {x} 430 l S" for x in column_edges)
    drawing.extend(f"50 {y} m 450 {y} l S" for y in row_edges)
    last_condition = "on standby" if manual_review_case else "idle"
    for y, words in (
        (406, ((60, "Parameter"), (147, "Mode"), (209, "LOW"), (289, "HIGH"), (390, "UNIT"))),
        (366, ((60, "Reset dwell"), (147, "active"), (320, "7.2e-4"), (390, "s"))),
        (326, ((60, "Cool-down"), (147, "inactive"), (222, "43"), (390, "ms"))),
        (286, ((60, "Lockout"), (147, "on" if manual_review_case else "idle"),
               (320 if manual_review_case else 275, "48"), (390, "ms"))),
    ):
        drawing.extend(f"BT /F1 10 Tf {x} {y} Td ({word}) Tj ET" for x, word in words)
    if manual_review_case:
        drawing.append("BT /F1 10 Tf 147 276 Td (standby) Tj ET")
    content = make_pdf(("\n".join(drawing) + "\n").encode("ascii"), width=500, height=500)
    pdf_path = root / "qualification-profile.pdf"
    pdf_path.write_bytes(content)

    html = (
        "<table><tr><th>Parameter</th><th>Mode</th><th>LOW</th><th>HIGH</th><th>UNIT</th></tr>"
        '<tr><td>Reset dwell</td><td>active</td><td colspan="2">7.2e-4</td><td>s</td></tr>'
        '<tr><td>Cool-down</td><td>inactive</td><td colspan="2">43</td><td>ms</td></tr>'
        f'<tr><td>Lockout</td><td>{last_condition}</td><td colspan="2">48</td><td>ms</td></tr></table>'
    )
    block = {
        "type": "table", "bbox": [100, 140, 900, 460],
        "content": {"html": html, "table_caption": [], "table_footnote": []},
    }
    point_box = [50, 70, 450, 230]
    body = {"type": "table_body", "index": 0, "bbox": point_box, "lines": [
        {"spans": [{"type": "table", "html": html, "bbox": point_box}]},
    ]}
    table = {"type": "table", "index": 0, "bbox": point_box, "blocks": [body]}
    layout = {"_version_name": "3.4.4", "pdf_info": [
        {"page_idx": 0, "page_size": [500, 500], "para_blocks": [table], "preproc_blocks": [table]},
    ]}
    archive_path = root / "qualification-profile.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("qualification_origin.pdf", content)
        archive.writestr("qualification_content_list_v2.json", json.dumps([[block]]))
        archive.writestr("layout.json", json.dumps(layout))
    return archive_path, pdf_path


@skipUnless(all(which(tool) for tool in ("pdfinfo", "pdftotext", "pdftocairo", "pdftohtml")), "需要实际 Poppler")
class PdfValueColumnPopplerTests(TestCase):
    def test_ruled_limits_bind_both_directions_and_keep_border_value_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package, source_pdf = _ruled_table_package(root)
            args = run_local_mineru_conversion.parse_args([
                str(package), "--no-template", "--document-language", "en",
                "--source-pdf", str(source_pdf), "--auto-table-value-columns",
                "--output", str(root / "result.docx"),
            ])
            result = formal_mineru_conversion.run_conversion(**run_local_mineru_conversion.build_conversion_kwargs(args))
            ir = DocumentIR.model_validate_json(result.document_ir_path.read_bytes())
            metadata = validate_persisted_renderer_content(
                ir, result.output_docx_path.read_bytes(), result.renderer_metadata,
            )
            report = read_table_evidence(metadata["table_evidence"])
            table_evidence, = report.tables
            self.assertEqual(report.status, "blocked")
            self.assertEqual(report.counts.blocker_count, 1)
            self.assertEqual(
                [(item.output_row, item.target_column) for item in table_evidence.value_column_corrections],
                [(1, 3), (2, 2)],
            )
            self.assertTrue(all(item.pdf_binding_sha256 for item in table_evidence.value_column_corrections))
            remaining, = ir.metadata.pdf_value_column_unresolved
            self.assertEqual(remaining.source_row_index, 3)
            self.assertIn(remaining.finding_id, {flag.identity for flag in table_evidence.flags})
            word, = Document(result.output_docx_path).tables
            self.assertEqual([cell.text for cell in word.rows[0].cells][2:], ["LOW", "HIGH", "UNIT"])
            self.assertEqual(
                [[(cell.text, cell.grid_span) for cell in row.cells[2:]] for row in word.rows[1:]],
                [[("", 1), ("7.2e-4", 1), ("s", 1)],
                 [("43", 1), ("", 1), ("ms", 1)],
                 [("48", 2), ("48", 2), ("ms", 1)]],
            )
