from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from app.services.document_ir.mineru_converter import MinerUToDocumentIRService
from app.services.document_ir.pdf_value_column_binding import match_pdf_value_columns
from app.services.document_ir.pdf_value_column_observer import PdfValueColumnPage, PdfValueColumnWord
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.quality import TableValidationPolicy, make_finding_id
from app.services.tables.validator import iter_parameter_value_column_spans


_HEAD = (
    "<tr><th>Parameter</th><th>Condition</th><th>Minimum</th><th>Typical</th><th>Units</th></tr>"
)
_ROW = "<tr><td>Latency</td><td>Idle</td><td colspan='2'>3.4e-2</td><td>µs</td></tr>"
_BBOX = (9.0, 9.0, 351.0, 51.0)


def _word(text: str, x: float, y: float, *, width: float | None = None) -> PdfValueColumnWord:
    length = width if width is not None else len(text) * 4.0
    return PdfValueColumnWord(
        text, (x, y, x + length, y + 8.0),
        tuple((x + index * length / len(text), y + 7.0) for index in range(len(text))),
    )


def _ruled_table() -> PdfValueColumnPage:
    return PdfValueColumnPage(
        width=400.0, height=200.0, page_count=1, extractor_version="fixture",
        words=(
            _word("Parameter", 16.0, 15.0), _word("Condition", 106.0, 15.0), _word("Minimum", 190.0, 15.0),
            _word("Typical", 251.0, 15.0), _word("Units", 309.0, 15.0),
            _word("Latency", 16.0, 35.0), _word("Idle", 106.0, 35.0), _word("3.4e-2", 174.0, 35.0),
            _word("μs", 308.0, 35.0),
        ),
        rectangles=(),
        horizontal_lines=tuple((10.0, y, 350.0) for y in (10.0, 30.0, 50.0)),
        vertical_lines=tuple((x, 10.0, 50.0) for x in (10.0, 100.0, 170.0, 230.0, 300.0, 350.0)),
    )


def _grid(*rows: str):
    source = [[{
        "type": "table", "bbox": list(_BBOX), "content": {"html": "<table>" + _HEAD + "".join(rows) + "</table>"},
    }]]
    with TemporaryDirectory() as directory:
        package = Path(directory) / "table.zip"
        with ZipFile(package, "w") as archive:
            archive.writestr("content_list_v2.json", json.dumps(source))
        document = MinerUToDocumentIRService().convert_zip(
            package, job_id="job", source_file_id="pdf", document_language="en",
        ).document
    group, = document.metadata.logical_table_groups
    return build_table_grid(group, source_content_sha256=document.metadata.mineru_validation.content_list_sha256)


class PdfValueColumnBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = _grid(_ROW)
        self.page = _ruled_table()

    def match(self, page: PdfValueColumnPage, *, skip=frozenset()):
        return match_pdf_value_columns(self.result, page, _BBOX, layout_sha256="a" * 64, skip_cells=skip)

    def assert_unresolved(self, page: PdfValueColumnPage, reason: str) -> None:
        corrections, unresolved = self.match(page)
        self.assertEqual(corrections, ())
        item, = unresolved
        flag, evidence, _ = next(iter_parameter_value_column_spans(self.result, TableValidationPolicy()))
        self.assertEqual(flag.severity, "blocker")
        self.assertEqual(item.finding_id, make_finding_id(self.result.grid.table_id, flag, evidence))
        self.assertEqual((item.source_row_index, item.source_cell_index, item.reason), (1, 2, reason))

    def test_closed_unshaded_columns_use_original_alias_but_bind_to_canonical_min(self) -> None:
        corrections, unresolved = self.match(self.page)
        self.assertEqual(unresolved, ())
        correction, = corrections
        self.assertEqual((correction.target_column, correction.target_header), (2, "MIN"))
        self.assertEqual(correction.original_column_range, (2, 4))
        binding = correction.pdf_binding
        self.assertEqual(binding.column_range, (170.0, 230.0))
        self.assertEqual(binding.row_range, (30.0, 50.0))
        self.assertEqual(binding.value_bbox, self.page.words[7].bbox)
        self.assertEqual(binding.unit_bbox, self.page.words[8].bbox)
        self.assertEqual(binding.row_anchor_bboxes, tuple(word.bbox for word in self.page.words[5:7]))
        self.assertEqual(self.match(self.page, skip=frozenset({(1, 2)})), ((), ()))

    def test_invisible_duplicate_boundary_and_extra_content_remain_blockers(self) -> None:
        value = self.page.words[7]
        for changed, reason in (
            (replace(self.page, words=self.page.words[:7] + (replace(value, glyphs=()),) + self.page.words[8:]),
             "value_visibility_unverified"),
            (replace(self.page, words=self.page.words + (_word(value.text, 250.0, 35.0),)),
             "value_ambiguous"),
            (replace(self.page, words=self.page.words[:7] + (_word(value.text, 220.0, 35.0),) + self.page.words[8:]),
             "column_ambiguous"),
            (replace(self.page, words=self.page.words + (_word("0.05", 250.0, 35.0),)),
             "span_contains_other_content"),
            (replace(self.page, unmapped_glyph_regions=((248.0, 36.0, 251.0, 41.0),)),
             "span_contains_other_content"),
            (replace(self.page, words=self.page.words + (_word("−", 170.6, 35.0),)),
             "value_ambiguous"),
        ):
            with self.subTest(reason=reason, page=changed):
                self.assert_unresolved(changed, reason)

    def test_rejects_missing_column_lines_row_conflict_and_wrong_unit(self) -> None:
        vertical = tuple((left, top, 30.0 if left == 230.0 else bottom)
                         for left, top, bottom in self.page.vertical_lines)
        bad_condition = replace(self.page.words[6], text="Busy")
        bad_unit = replace(self.page.words[8], text="μA")
        for page, reason in (
            (replace(self.page, vertical_lines=vertical), "column_ambiguous"),
            (replace(self.page, words=self.page.words[:6] + (bad_condition,) + self.page.words[7:]),
             "row_ambiguous"),
            (replace(self.page, words=self.page.words[:-1] + (bad_unit,)), "unit_mismatch"),
            (replace(self.page, unsupported_regions=((250.0, 34.0, 290.0, 42.0),)), "unsupported_pdf_geometry"),
        ):
            with self.subTest(reason=reason):
                self.assert_unresolved(page, reason)

    def test_segmented_edges_cannot_override_an_interrupted_numeric_wall(self) -> None:
        self.result = _grid(
            _ROW, "<tr><td>Rate</td><td>Busy</td><td>7</td><td>9</td><td>µs</td></tr>",
        )
        column_edges = (10.0, 100.0, 170.0, 230.0, 300.0, 350.0)
        adjacent = tuple(zip(column_edges, column_edges[1:]))
        open_wall = replace(
            self.page,
            words=(*self.page.words[:7], _word("3.4e-2", 255.0, 35.0), self.page.words[8],
                   _word("Rate", 16.0, 55.0), _word("Busy", 106.0, 55.0),
                   _word("7", 205.0, 55.0), _word("9", 263.0, 55.0), _word("μs", 308.0, 55.0)),
            horizontal_lines=tuple((left, y, right) for y in (10.0, 30.0, 50.0, 70.0) for left, right in adjacent),
            vertical_lines=tuple((x, 10.0, 70.0) for x in column_edges if x != 230.0) + ((230.0, 10.0, 30.0),),
        )
        table_bbox = (9.0, 9.0, 351.0, 71.0)
        corrections, unresolved = match_pdf_value_columns(self.result, open_wall, table_bbox, layout_sha256="a" * 64)
        self.assertEqual(unresolved, ())
        self.assertEqual([item.target_header for item in corrections], ["TYP"])

        # 第二行的内竖线抵达共享横线，却未伸入候选行，对应实际横向合并。
        merged = replace(open_wall, vertical_lines=open_wall.vertical_lines + ((230.0, 50.0, 70.0),))
        corrections, unresolved = match_pdf_value_columns(self.result, merged, table_bbox, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved], [(1, "column_ambiguous")])

    def test_ordinal_only_or_competing_pdf_row_cannot_bind(self) -> None:
        self.result = _grid(_ROW.replace("Latency", "").replace("Idle", ""))
        self.assert_unresolved(self.page, "row_ambiguous")

        self.result = _grid(_ROW, _ROW)
        corrections, unresolved = self.match(self.page)
        self.assertEqual(corrections, ())
        self.assertEqual(tuple((item.source_row_index, item.reason) for item in unresolved),
                         ((1, "competing_pdf_binding"), (2, "competing_pdf_binding")))
        self.assertEqual(len({item.finding_id for item in unresolved}), 2)
