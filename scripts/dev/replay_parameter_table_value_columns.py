"""回放三份固定 MinerU 结果，验收参数数值列报告和 Word 网格。"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from docx import Document
from docx.table import Table

from app.domains.document_jobs.quality_review_projection import project_table_item
from app.services.document_ir.table_placeholder import PdfCropSource
from app.services.tables.evidence import read_table_evidence
from scripts.dev.formal_mineru_conversion import LOCAL_SOURCE_FILE_ID, run_conversion
from scripts.dev.run_datasheet_quality_baseline import MANIFEST, RESOURCES, ROOT, expected_cell_shapes, sha256

_PACKAGE_SHA256 = {
    "sn74-v4-ambiguous": "55bf063ac6dd25dd07d087981c4ec644390bed84517bf962594b550acfeeea53",
    "sn74-v4-matching": "239a6439f05c6cf0e4eb1e9fc9ff8f456f3e082f5a6f43690042b872191b1b52",
    "opa228-p7-location": "f132b22f6631d269d93e78a48da839e8bb5aefd96fc80397fa80f21611e0117b",
}
_OPA228_PDF = ROOT / "tests/fixtures/golden_samples/pdfs/OPA228_P7.pdf"
_OPA228_PDF_SHA256 = "0afe536bc8ff50b8a30c5da25fbd54ea4226179c7cceb16fb331671c71da077f"
_SN74_VALUES = ("2.1", "3.15", "3.85")


def verify_input(path: Path, expected: str) -> None:
    if not path.is_file():
        raise ValueError(f"缺少回归输入：{path}")
    if sha256(path) != expected:
        raise ValueError(f"回归输入指纹不匹配：{path}")


def finding_positions(items) -> Counter:
    return Counter(
        (item.source_page_index, item.source_row_index, item.column, item.end_column,
         item.value.replace("μ", "µ"), (item.unit or "").replace("μ", "µ"),
         tuple(column.label for column in item.columns))
        for item in items
    )


def replay(
    sample_id: str, package: Path, source: PdfCropSource, output: Path, sn74_annotation: dict,
) -> dict:
    result = run_conversion(
        input_path=str(package), output_path=str(output / f"{sample_id}.docx"),
        **{name: str(path) for name, path in RESOURCES.items()}, no_template=False,
        use_mineru_header_footer=False, document_language="en", translation_mode="direct",
        job_id=sample_id, placeholder_source=source,
    )
    report = read_table_evidence(result.renderer_metadata["table_evidence"])
    is_opa228 = sample_id == "opa228-p7-location"
    pointer = "/0/1" if is_opa228 else "/1/6"
    native = [item for item in report.tables if any(fragment.json_pointer == pointer for fragment in item.validation.fragments)]
    if len(native) != 1 or len(native[0].outputs) != 1 or native[0].render_state != "native":
        raise ValueError(f"{sample_id} 未生成唯一的目标原生 Word 表格。")
    target = native[0]
    view = project_table_item(target)
    findings = view.value_column_findings
    if findings is None:
        raise ValueError(f"{sample_id} 缺少数值列归属检查证据。")
    positions = finding_positions(findings)
    if is_opa228:
        expected = Counter({
            (0, 2, 4, 6, "±5", "µV", ("MIN", "TYP")): 1,
            (0, 3, 4, 7, "±100", "µV", ("MIN", "TYP", "MAX")): 1,
        })
        if expected - positions:
            raise ValueError(f"{sample_id} 未定位两处指定的 VOS 值。")
    else:
        expected = Counter(
            (1, row, start, start + 2, value, "V", ("MIN", "MAX"))
            for row, value in enumerate(_SN74_VALUES, 3)
            for start in (3, 5)
        ) if sample_id == "sn74-v4-ambiguous" else Counter()
        if positions != expected:
            raise ValueError(f"{sample_id} 的 5.2 表数值跨列与独立标注不一致。")
        if not expected and any(project_table_item(table).value_column_findings != [] for table in report.tables):
            raise ValueError(f"{sample_id} 存在未检查或误报的表格。")

    source_shape = target.source_grid
    source_merges = {(cell.row, cell.column, cell.rowspan, cell.colspan) for cell in target.validation.cells
                     if cell.rowspan > 1 or cell.colspan > 1}
    if not is_opa228:
        expected_merges = set(map(tuple, sn74_annotation["merges"]))
        expected_merges.update((row, start, 1, end - start) for _, row, start, end, *_ in expected)
        if (source_shape.rows, source_shape.columns, source_merges) != (
            sn74_annotation["rows"], sn74_annotation["columns"], expected_merges,
        ):
            raise ValueError(f"{sample_id} 的源合并与独立标注不一致。")

    word = Document(result.output_docx_path)
    actual = target.outputs[0].actual
    physical = word.element.xpath(".//w:tbl")[actual.table_index]
    actual_shapes = [[(cell.grid_span, cell.vMerge) for cell in row.tc_lst] for row in physical.tr_lst]
    if len(physical.tblGrid.gridCol_lst) != source_shape.columns or actual_shapes != expected_cell_shapes(
        {"rows": source_shape.rows, "columns": source_shape.columns, "merges": source_merges}
    ):
        raise ValueError(f"{sample_id} 的实际 Word 网格没有保留源合并。")
    word_table = Table(physical, word)
    word_values = {(row, start): value for _, row, start, _, value, *_ in expected}
    if sample_id == "sn74-v4-matching":
        # 正例同时核对数值在 MIN、MAX 为空，合并数本身无法证明数值列归属。
        word_values = {
            (row, column): value if column in (3, 5) else ""
            for row, value in enumerate(_SN74_VALUES, 3) for column in (3, 4, 5, 6)
        }
    for (row, column), expected_value in word_values.items():
        actual_value = "".join(node.text or "" for node in word_table.cell(row, column)._tc.xpath(".//w:t|.//m:t"))
        if actual_value.strip() != expected_value:
            raise ValueError(f"{sample_id} 的 Word 值与验收标注不一致（行 {row}，列 {column}）。")

    return {
        "sample_id": sample_id,
        "package_sha256": _PACKAGE_SHA256[sample_id],
        "source_pdf_sha256": source.checksum_sha256.removeprefix("sha256:"),
        "docx_sha256": sha256(result.output_docx_path),
        "table_report_sha256": report.report_sha256,
        "native_tables": report.counts.native_count,
        "source_pointer": pointer,
        "source_rows": source_shape.rows,
        "source_columns": source_shape.columns,
        "preserved_merges": len(source_merges),
        "table_index": actual.table_index,
        "value_column_findings": [item.model_dump(mode="json") for item in findings],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sn74-pdf", required=True, type=Path, help="两个 v4 结果的提交源 PDF")
    for sample_id in _PACKAGE_SHA256:
        parser.add_argument(f"--{sample_id}", required=True, type=Path, help="固定的 MinerU ZIP")
    parser.add_argument("--output", required=True, type=Path, help="新建回放输出目录")
    args = parser.parse_args()
    sn74 = next(sample for sample in json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]
                if sample["sample_id"] == "gsx-sn74ac244-specs")
    sn74_annotation = next(item for item in sn74["tables"] if item["source_pointers"] == ["/1/6"])
    inputs = {name: getattr(args, name.replace("-", "_")) for name in _PACKAGE_SHA256}
    verify_input(args.sn74_pdf, sn74["pdf_sha256"])
    verify_input(_OPA228_PDF, _OPA228_PDF_SHA256)
    for sample_id, package in inputs.items():
        verify_input(package, _PACKAGE_SHA256[sample_id])
    sn74_source = PdfCropSource(LOCAL_SOURCE_FILE_ID, "sha256:" + sn74["pdf_sha256"], args.sn74_pdf.read_bytes())
    opa228_source = PdfCropSource(LOCAL_SOURCE_FILE_ID, "sha256:" + _OPA228_PDF_SHA256, _OPA228_PDF.read_bytes())
    args.output.mkdir(parents=True, exist_ok=False)
    observations = []
    for sample_id, package in inputs.items():
        source = opa228_source if sample_id == "opa228-p7-location" else sn74_source
        observation = replay(sample_id, package, source, args.output, sn74_annotation)
        observations.append(observation)
        print(f"{sample_id}：原生 Word 网格通过，目标表发现 {len(observation['value_column_findings'])} 项。")
    (args.output / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
