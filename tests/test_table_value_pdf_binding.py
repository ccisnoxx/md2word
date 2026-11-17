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
from app.services.tables.quality import BINDING_VALIDATOR_VERSION, default_table_validation_policy, make_finding_id
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


def _table_with_rows(
    count: int, *words: PdfValueColumnWord, merged_after: tuple[int, ...] = (),
) -> tuple[PdfValueColumnPage, tuple[float, float, float, float]]:
    page = _ruled_table()
    bottom = 30.0 + 20.0 * count
    edges = tuple(30.0 + 20.0 * index for index in range(count + 1))
    return replace(
        page,
        height=max(page.height, bottom + 1.0),
        words=(*page.words[:5], *words),
        horizontal_lines=((10.0, 10.0, 350.0), *(
            (100.0, y, 300.0) if index in merged_after else (10.0, y, 350.0)
            for index, y in enumerate(edges)
        )),
        vertical_lines=tuple((x, 10.0, bottom) for x, _, _ in page.vertical_lines),
    ), (9.0, 9.0, 351.0, bottom + 1.0)


def _row_words(name: str, value: str, y: float, x: float = 174.0) -> tuple[PdfValueColumnWord, ...]:
    return (_word(name, 16.0, y), _word("Idle", 106.0, y), _word(value, x, y), _word("μs", 308.0, y))


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
        flag, evidence, _ = next(iter_parameter_value_column_spans(
            self.result, default_table_validation_policy(BINDING_VALIDATOR_VERSION),
        ))
        self.assertEqual(flag.severity, "warning")
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

    def test_invisible_duplicate_boundary_and_extra_content_remain_warnings(self) -> None:
        value = self.page.words[7]
        for changed, reason in (
            (replace(self.page, words=self.page.words[:7] + (replace(value, glyphs=()),) + self.page.words[8:]),
             "value_visibility_unverified"),
            (replace(self.page, words=self.page.words + (_word(value.text, 250.0, 35.0),)),
             "value_word_nonunique"),
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
             "row_anchor_missing"),
            (replace(self.page, words=self.page.words[:-1] + (bad_unit,)), "unit_row_mismatch"),
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
        self.assert_unresolved(self.page, "row_anchor_missing")

        self.result = _grid(_ROW, _ROW)
        corrections, unresolved = self.match(self.page)
        self.assertEqual(corrections, ())
        self.assertEqual(tuple((item.source_row_index, item.reason) for item in unresolved),
                         ((1, "competing_pdf_binding"), (2, "competing_pdf_binding")))
        self.assertEqual(len({item.finding_id for item in unresolved}), 2)

    def test_exact_unique_value_disambiguates_repeated_context(self) -> None:
        self.result = _grid(_ROW, _ROW.replace("3.4e-2", "4.1e-2"))
        page, bbox = _table_with_rows(2, *_row_words("Latency", "3.4e-2", 35.0),
                                     *_row_words("Latency", "4.1e-2", 55.0, 244.0))
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual(unresolved, ())
        self.assertEqual([(item.source_row_index, item.target_header) for item in corrections],
                         [(1, "MIN"), (2, "TYP")])

        typo = replace(page, words=(*page.words[:-2], _word("4.1e-3", 244.0, 55.0), page.words[-1]))
        corrections, unresolved = match_pdf_value_columns(self.result, typo, bbox, layout_sha256="a" * 64)
        self.assertEqual([item.source_row_index for item in corrections], [1])
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved], [(2, "row_anchor_nonunique")])

        invisible = replace(page, words=(*page.words, replace(_word("3.4e-2", 174.0, 55.0), glyphs=())))
        corrections, unresolved = match_pdf_value_columns(self.result, invisible, bbox, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(1, "value_visibility_unverified"), (2, "span_contains_other_content")])

    def test_combination_uses_condition_and_unit_before_accepting_repeated_value(self) -> None:
        self.result = _grid(
            _ROW,
            _ROW.replace("µs", "ms"),
            _ROW.replace("Idle", "Busy"),
        )
        page, bbox = _table_with_rows(
            3, *_row_words("Latency", "3.4e-2", 35.0),
            *_row_words("Latency", "3.4e-2", 55.0, 244.0)[:-1], _word("ms", 308.0, 55.0),
            _word("Latency", 16.0, 75.0), _word("Busy", 106.0, 75.0),
            _word("3.4e-2", 244.0, 75.0), _word("μs", 308.0, 75.0),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual(unresolved, ())
        self.assertEqual([(item.source_row_index, item.target_header) for item in corrections],
                         [(1, "MIN"), (2, "TYP"), (3, "TYP")])

    def test_empty_condition_with_parameter_and_unit_in_same_rowspan(self) -> None:
        self.result = _grid(
            '<tr><td rowspan="2">Latency</td><td></td><td colspan="2">11</td><td rowspan="2">µs</td></tr>',
            '<tr><td></td><td colspan="2">22</td></tr>',
        )
        page, bbox = _table_with_rows(
            2, _word("Latency", 16.0, 42.0), _word("μs", 308.0, 42.0),
            _word("11", 174.0, 35.0), _word("22", 254.0, 55.0), merged_after=(1,),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual(unresolved, ())
        self.assertEqual([(item.source_row_index, item.target_header) for item in corrections],
                         [(1, "MIN"), (2, "TYP")])
        self.assertEqual({item.pdf_binding.unit_bbox for item in corrections}, {page.words[6].bbox})

        split, bbox = _table_with_rows(
            4, _word("Latency", 16.0, 42.0), _word("μs", 308.0, 42.0),
            _word("Latency", 16.0, 82.0), _word("μs", 308.0, 82.0),
            _word("11", 174.0, 35.0), _word("77", 254.0, 55.0),
            _word("88", 174.0, 75.0), _word("22", 254.0, 95.0), merged_after=(1, 3),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, split, bbox, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(1, "rowspan_context_unresolved"), (2, "rowspan_context_unresolved")])

        at_boundary = replace(split, words=(*split.words[:-1], _word("22", 227.0, 95.0)))
        corrections, unresolved = match_pdf_value_columns(self.result, at_boundary, bbox, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(1, "rowspan_context_unresolved"), (2, "column_ambiguous")])

        first, second = (
            '<tr><td rowspan="2">Latency</td><td></td><td colspan="2">11</td><td rowspan="2">µs</td></tr>',
            '<tr><td></td><td></td><td>22</td></tr>',
        )
        self.result = _grid(first, second)
        corrections, unresolved = match_pdf_value_columns(self.result, split, bbox, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(1, "rowspan_context_unresolved")])

        for last, unresolved_rows in (
            ('<tr><td></td><td colspan="2">77</td></tr>', [1, 4]),
            (second.replace("22", "77"), [1]),
        ):
            self.result = _grid(
                first, second.replace("22", "99"),
                '<tr><td rowspan="2">Latency</td><td></td><td>66</td><td></td><td rowspan="2">µs</td></tr>',
                last,
            )
            corrections, unresolved = match_pdf_value_columns(self.result, split, bbox, layout_sha256="a" * 64)
            self.assertEqual(corrections, ())
            self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                             [(row, "rowspan_context_unresolved") for row in unresolved_rows])

        self.result = _grid(first, '<tr><td></td><td colspan="2">22</td></tr>')
        clipped = (bbox[0], bbox[1], bbox[2], 69.0)
        corrections, unresolved = match_pdf_value_columns(self.result, split, clipped, layout_sha256="a" * 64)
        self.assertEqual(corrections, ())
        self.assertEqual({item.reason for item in unresolved}, {"rowspan_context_unresolved"})

    def test_sequence_accepts_only_unique_mapping_between_independent_rows(self) -> None:
        start = _ROW.replace("Latency", "Start").replace("3.4e-2", "70")
        end = _ROW.replace("Latency", "End").replace("3.4e-2", "94")
        self.result = _grid(start, _ROW, _ROW, end)
        page, bbox = _table_with_rows(
            4, *_row_words("Start", "70", 35.0), *_row_words("Latency", "3.4e-2", 55.0),
            *_row_words("Latency", "3.4e-2", 75.0, 244.0), *_row_words("End", "94", 95.0),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual(unresolved, ())
        self.assertEqual([(item.source_row_index, item.target_header) for item in corrections],
                         [(1, "MIN"), (2, "MIN"), (3, "TYP"), (4, "MIN")])

        extra, extra_bbox = _table_with_rows(
            5, *page.words[5:-4], *_row_words("Latency", "3.4e-2", 95.0), *_row_words("End", "94", 115.0),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, extra, extra_bbox, layout_sha256="a" * 64)
        self.assertEqual([item.source_row_index for item in corrections], [1, 4])
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(2, "source_row_band_count_mismatch"), (3, "source_row_band_count_mismatch")])

        no_anchor = '<tr><td>Unknown</td><td>Idle</td><td>99</td><td></td><td>µs</td></tr>'
        self.result = _grid(start, _ROW, _ROW, no_anchor, end)
        corrections, unresolved = match_pdf_value_columns(self.result, extra, extra_bbox, layout_sha256="a" * 64)
        self.assertEqual([item.source_row_index for item in corrections], [1, 5])
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(2, "row_sequence_ambiguous"), (3, "row_sequence_ambiguous")])

        self.result = _grid(end, _ROW, _ROW, start)
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual([item.source_row_index for item in corrections], [1, 4])
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(2, "row_sequence_ambiguous"), (3, "row_sequence_ambiguous")])

    def test_unique_sequence_cannot_split_shared_source_rowspan(self) -> None:
        def cell(name: str, value: str) -> str:
            return _ROW.replace("Latency", name).replace("3.4e-2", value)

        unknown = '<tr><td>Unknown</td><td>Idle</td><td>99</td><td></td><td>ms</td></tr>'
        self.result = _grid(
            cell("Start", "70"),
            '<tr><td rowspan="2">Latency</td><td></td><td colspan="2">11</td><td rowspan="2">µs</td></tr>',
            '<tr><td></td><td colspan="2">22</td></tr>',
            cell("Middle", "71"), unknown, unknown, unknown, unknown, cell("End", "94"),
        )
        page, bbox = _table_with_rows(
            9, *_row_words("Start", "70", 35.0),
            _word("Latency", 16.0, 62.0), _word("μs", 308.0, 62.0),
            _word("11", 174.0, 55.0), _word("77", 254.0, 75.0),
            _word("Latency", 16.0, 102.0), _word("μs", 308.0, 102.0),
            _word("88", 174.0, 95.0), _word("22", 254.0, 115.0),
            *_row_words("Middle", "71", 135.0),
            _word("Latency", 16.0, 162.0), _word("μs", 308.0, 162.0),
            _word("99", 174.0, 155.0), _word("22", 254.0, 175.0),
            *_row_words("End", "94", 195.0), merged_after=(2, 4, 7),
        )
        corrections, unresolved = match_pdf_value_columns(self.result, page, bbox, layout_sha256="a" * 64)
        self.assertEqual([item.source_row_index for item in corrections], [1, 2, 4, 9])
        self.assertEqual([(item.source_row_index, item.reason) for item in unresolved],
                         [(3, "row_sequence_ambiguous")])
