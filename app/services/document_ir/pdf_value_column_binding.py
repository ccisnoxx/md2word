"""用已核实表区的实际行列、词和单位生成可逐格核验的拟修正。"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
import re

from app.services.document_ir.pdf_value_column_observer import Box, PdfValueColumnPage, PdfValueColumnWord
from app.services.document_ir.pdf_value_column_table_edge import find_pdf_table_edge
from app.services.document_ir.table_value_column_review import (
    LegacyValueColumnReplay, PdfValueColumnBinding, PdfValueColumnTableEdge, PdfValueColumnUnresolved,
    TableValueColumnCorrection,
)
from app.services.tables.grid_builder import TableBuildResult
from app.services.tables.models import TableCell, TableGrid
from app.services.tables.quality import (
    BINDING_VALIDATOR_VERSION, LEGACY_VALIDATOR_VERSION, REVIEWABLE_VALUE_COLUMN_RULES,
    default_table_validation_policy, make_finding_id,
)
from app.services.tables.validator import (
    is_unit_header_label, iter_parameter_value_column_spans, parameter_value_header_label,
)


_Interval = tuple[float, float]
_MARGIN = 0.5
# 区分同一水平描边的坐标舍入与实际相邻的描边。
_LEVEL_TOLERANCE = 0.05
_SIMPLE_SUBSCRIPT = re.compile(
    r"\$(?P<base>[A-Za-z]+)_(?P<subscript>[A-Za-z0-9]|\{[A-Za-z0-9]+\})"
    r"(?:(?P<quotient>/[A-Za-z]+)|\s*=\s*(?P<condition>[-−–+±.A-Za-z0-9°%/·√µμΩ ]+))?\$"
)


def _tokens(value: str) -> tuple[str, ...]:
    # 仅接纳字面量中的微符号、负号等价，保留大小写、比较符与指数。
    return tuple(re.sub(r"(?<![\d.])[−–](?=\d)", "-", value.replace("μ", "µ")).split())


def _context_tokens(value: str) -> tuple[str, ...]:
    return _tokens(value.replace("Ω", "Ω"))


@dataclass(frozen=True)
class _Text:
    tokens: tuple[str, ...]
    heading: bool = False
    context: bool = False
    multiline: bool = False
    subscript_at: int | None = None
    quotient: bool = False

    def word(self, value: str) -> tuple[str, ...]:
        normalized = value.upper() if self.heading else value
        return _context_tokens(normalized) if self.context else _tokens(normalized)

    def matches(self, words: tuple[PdfValueColumnWord, ...]) -> bool:
        if not words or not all(word.glyphs for word in words):
            return False
        if self.multiline:
            lines: list[list[PdfValueColumnWord]] = []
            for word in sorted(words, key=lambda item: (item.bbox[1], item.bbox[0])):
                if not lines or word.bbox[1] - lines[-1][0].bbox[1] > _MARGIN:
                    if lines and word.bbox[1] < max(item.bbox[3] for item in lines[-1]) - _MARGIN:
                        return False
                    lines.append([])
                lines[-1].append(word)
            words = tuple(word for line in lines for word in sorted(line, key=lambda item: item.bbox[0]))
            return tuple(part for word in words for part in self.word(word.text)) == self.tokens
        if tuple(part for word in words for part in self.word(word.text)) != self.tokens:
            return False
        if self.subscript_at is not None and len(words) != len(self.tokens):
            return False
        base_y = words[0].bbox[1]
        for index, word in enumerate(words):
            if index == self.subscript_at:
                base = words[index - 1]
                if not (base_y + _MARGIN < word.bbox[1] < base.bbox[3]
                        and abs(base.bbox[2] - word.bbox[0]) <= _MARGIN):
                    return False
                if self.quotient and abs(word.bbox[2] - words[index + 1].bbox[0]) > _MARGIN:
                    return False
            elif abs(word.bbox[1] - base_y) > _MARGIN:
                return False
        return True


def _source_text(cell: TableCell) -> _Text | None:
    if all(run.type == "text" for run in cell.runs):
        return _Text(_tokens("".join(run.source for run in cell.runs)))
    return None


def _context_text(cell: TableCell, *, unit: bool = False) -> _Text | None:
    if all(run.type in {"text", "line_break"} for run in cell.runs):
        tokens = _context_tokens("".join(" " if run.type == "line_break" else run.source for run in cell.runs))
        return _Text(tokens, context=True, multiline=not unit)
    formulas = [index for index, run in enumerate(cell.runs) if run.type != "text"]
    if len(formulas) != 1:
        return None
    index = formulas[0]
    run = cell.runs[index]
    formula = _SIMPLE_SUBSCRIPT.fullmatch(run.source.strip()) if run.type == "formula" else None
    if formula is None or any(run.source.strip() for run in cell.runs[index + 1:]):
        return None
    prefix = _context_tokens("".join(run.source for run in cell.runs[:index]))
    base = formula["base"]
    condition = _context_tokens(formula["condition"] or "")
    quotient = formula["quotient"]
    if formula["condition"] and not condition:
        return None
    if unit:
        if condition or quotient or (prefix and (len(prefix) != 1 or prefix[0] not in {"p", "n", "µ", "m"}
                                                or base != "V")):
            return None
        base = "".join(prefix) + base
        prefix = ()
    tail = (quotient,) if quotient else ("=", *condition) if condition else ()
    return _Text((*prefix, base, formula["subscript"].strip("{}"), *tail),
                 context=True, subscript_at=len(prefix) + 1, quotient=bool(quotient))


def _x(box: Box) -> _Interval:
    return box[0], box[2]


def _y(box: Box) -> _Interval:
    return box[1], box[3]


def _near(first: _Interval, second: _Interval) -> bool:
    return all(abs(a - b) <= _MARGIN for a, b in zip(first, second, strict=True))


def _inside(outer: _Interval, inner: _Interval, margin: float = 0.0) -> bool:
    return outer[0] + margin <= inner[0] <= inner[1] <= outer[1] - margin


def _overlap(first: _Interval, second: _Interval) -> float:
    return min(first[1], second[1]) - max(first[0], second[0])


def _intersects(first: Box, second: Box) -> bool:
    return _overlap(_x(first), _x(second)) > 0 and _overlap(_y(first), _y(second)) > 0


def _contains(outer: Box, inner: Box, margin: float = 0.0) -> bool:
    return _inside(_x(outer), _x(inner), margin) and _inside(_y(outer), _y(inner), margin)


def _covers(segments: Iterable[_Interval], span: _Interval) -> bool:
    reached = span[0]
    for start, end in sorted(segments):
        if end < reached:
            continue
        if start > reached + _MARGIN:
            return False
        reached = max(reached, end)
        if reached >= span[1] - _MARGIN:
            return True
    return False


@dataclass(frozen=True)
class _Axis:
    position: float
    segments: tuple[_Interval, ...]


def _axes(lines: Iterable[tuple[float, float, float]]) -> tuple[_Axis, ...]:
    axes = []
    segments: list[_Interval] = []
    for axis, start, end in sorted(lines):
        if not segments or axis - position > _LEVEL_TOLERANCE:
            segments = []
            position = axis
            axes.append((position, segments))
        segments.append((start, end))
    return tuple(_Axis(position, tuple(sorted(set(segments)))) for position, segments in axes)


@dataclass(frozen=True)
class _TextBox:
    area: Box
    text: Box


class _Geometry:
    def __init__(self, observation: PdfValueColumnPage, table: Box) -> None:
        self.table = table
        self.words = tuple(word for word in observation.words if _intersects(table, word.bbox))
        self.fills = tuple(rect for rect in observation.rectangles if _contains(table, rect))
        self.unmapped = tuple(area for area in observation.unmapped_glyph_regions if _intersects(table, area))
        self.horizontal = _axes((y, left, right) for left, y, right in observation.horizontal_lines
                                if _inside(_x(table), (left, right)) and table[1] <= y <= table[3])
        self.vertical = _axes((x, top, bottom) for x, top, bottom in observation.vertical_lines
                              if _overlap(_y(table), (top, bottom)) > 0 and table[0] <= x <= table[2])
        initial_words = defaultdict(list)
        for word in self.words:
            initial_words[_context_tokens(word.text.upper())].append(word)
        self._initial_words = initial_words
        self.cell_area = lru_cache(maxsize=512)(self.cell_area)
        self.words_in = lru_cache(maxsize=512)(self.words_in)
        self.text_boxes = lru_cache(maxsize=512)(self.text_boxes)

    def has_unmapped_glyphs(self, area: Box) -> bool:
        return any(_intersects(area, glyph) for glyph in self.unmapped)

    def words_in(self, area: Box) -> tuple[PdfValueColumnWord, ...]:
        # 字框可能轻微伸入相邻栏。保留实质重叠，候选值仍须整体留在栏内。
        return tuple(sorted((word for word in self.words
                             if _overlap(_x(area), _x(word.bbox)) > _MARGIN
                             and _overlap(_y(area), _y(word.bbox)) > _MARGIN),
                            key=lambda word: word.bbox))

    def cell_area(self, word: Box) -> Box | None:
        borders = tuple(line.position for line in self.horizontal if _covers(line.segments, _x(word)))
        top = next((y for y in reversed(borders) if y <= word[1] - _MARGIN), None)
        bottom = next((y for y in borders if y >= word[3] + _MARGIN), None)
        if top is None or bottom is None:
            return None
        walls = tuple(line.position for line in self.vertical if _covers(line.segments, (top, bottom)))
        left = next((x for x in reversed(walls) if x <= word[0] - _MARGIN), None)
        right = next((x for x in walls if x >= word[2] + _MARGIN), None)
        if left is None or right is None or not _contains(self.table, (left, top, right, bottom)):
            return None
        outer = (left, top, right, bottom)
        if (not all(_covers(line.segments, (left, right)) for line in self.horizontal
                    if line.position in (top, bottom))
                or any(top + _MARGIN < line.position < bottom - _MARGIN
                       and any(_overlap(part, (left, right)) > _MARGIN for part in line.segments)
                       for line in self.horizontal)
                or any(left + _MARGIN < line.position < right - _MARGIN
                       and any(_overlap(part, (top, bottom)) > _MARGIN for part in line.segments)
                       for line in self.vertical)):
            return None
        return outer

    def text_boxes(
        self, text: _Text, zone: _Interval, *, include_fills: bool = False,
    ) -> tuple[_TextBox, ...]:
        if not text.tokens:
            return ()
        areas = set()
        for seed in self._initial_words.get(_context_tokens(text.tokens[0].upper()), ()):
            if not _inside(zone, _x(seed.bbox), _MARGIN):
                continue
            actual_cell = self.cell_area(seed.bbox)
            if actual_cell is not None and _inside(zone, _x(actual_cell), -_MARGIN):
                areas.add(actual_cell)
            if include_fills:
                areas.update(rect for rect in self.fills if _contains(rect, seed.bbox, _MARGIN))

        matches = []
        for area in sorted(areas):
            words = self.words_in(area)
            if (not text.matches(words) or not all(_contains(area, word.bbox, _MARGIN) for word in words)
                    or self.has_unmapped_glyphs(area)):
                continue
            matches.append(_TextBox(area, (
                min(word.bbox[0] for word in words), min(word.bbox[1] for word in words),
                max(word.bbox[2] for word in words), max(word.bbox[3] for word in words),
            )))
        return tuple(matches)


@dataclass(frozen=True)
class _Heading:
    column: int
    end_column: int
    box: _TextBox
    value_label: str | None


@dataclass(frozen=True)
class _Header:
    source_row: int
    context: tuple[_Heading, ...]
    numeric: tuple[_Heading, ...]
    unit: _Heading


def _header(rows: dict[int, list[TableCell]], geometry: _Geometry) -> _Header | None:
    profiles = []
    for row_index, cells in rows.items():
        headings = []
        for cell in cells:
            text = _source_text(cell)
            if cell.rowspan != 1 or text is None or not text.tokens:
                continue
            label = " ".join(text.tokens).upper()
            headings.append((cell.column, cell.column + cell.colspan, label))
        numeric = [item for item in headings if item[1] - item[0] == 1 and parameter_value_header_label(item[2])]
        unit = [item for item in headings if item[1] - item[0] == 1 and is_unit_header_label(item[2])]
        if (len(numeric) < 2 or len({parameter_value_header_label(item[2]) for item in numeric}) != len(numeric)
                or len(unit) != 1
                or [item[0] for item in numeric] != list(range(numeric[0][0], unit[0][0]))):
            continue
        context = [item for item in headings if item[1] <= numeric[0][0]]
        if context:
            profiles.append((row_index, context, numeric, unit[0]))
    if len(profiles) != 1:
        return None
    row, context, numeric, unit = profiles[0]
    source_headings = (*context, *numeric, unit)
    options = [geometry.text_boxes(_Text(_tokens(label), heading=True), _x(geometry.table), include_fills=True)
               for _, _, label in source_headings]
    proven = []
    for unit_box in options[-1]:
        observed = []
        for (column, end, label), choices in zip(source_headings, options, strict=True):
            aligned = tuple(box for box in choices if _near(_y(box.area), _y(unit_box.area)))
            if not aligned or len({box.text for box in aligned}) != 1:
                break
            # 同一标题在闭合边框和内缩色块上都有证据时，用可实测的外边框。
            widest = max(aligned, key=lambda box: box.area[2] - box.area[0])
            if not all(_inside(_x(widest.area), _x(box.area)) for box in aligned):
                break
            observed.append(_Heading(column, end, widest, parameter_value_header_label(label)))
        if len(observed) == len(source_headings) and all(
            -_LEVEL_TOLERANCE <= right.box.area[0] - left.box.area[2] <= _MARGIN
            for left, right in zip(observed, observed[1:])
        ):
            proven.append(_Header(row, tuple(observed[:len(context)]), tuple(observed[len(context):-1]), observed[-1]))
    # 边框和内缩色块可以同时印证同一组；不同表头带则仍是歧义。
    unique = set(proven)
    return next(iter(unique)) if len(unique) == 1 else None


@dataclass(frozen=True)
class _Band:
    area: Box
    independent_columns: bool
    requires_alignment: bool


def _data_bands(header: _Header, geometry: _Geometry) -> tuple[_Band, ...]:
    columns = tuple(_x(title.box.area) for title in header.numeric)
    numeric_span = (columns[0][0], columns[-1][1])
    edges = tuple((edge.position, parts) for edge in geometry.horizontal
                  if edge.position >= header.unit.box.area[3] - _MARGIN
                  and (parts := tuple(part for part in edge.segments if _overlap(part, numeric_span) > _MARGIN)))
    if len(edges) < 2:
        return ()

    def style(parts: tuple[_Interval, ...]) -> str | None:
        if len(parts) == len(columns) and all(_near(a, b) for a, b in zip(parts, columns, strict=True)):
            return "segmented"
        if len(parts) == 1 and _inside(parts[0], numeric_span, -_MARGIN):
            return "continuous"
        return None

    boundaries = (columns[0][0], *(column[1] for column in columns))
    data_extent = (edges[0][0], edges[-1][0])
    walls = {
        boundary: tuple(axis for axis in geometry.vertical if abs(axis.position - boundary) <= _MARGIN
                        and any(_overlap(segment, data_extent) > _MARGIN for segment in axis.segments))
        for boundary in boundaries
    }
    bands = []
    for (top, upper), (bottom, lower) in zip(edges, edges[1:]):
        row = top, bottom
        strokes = tuple(axis for axis in geometry.vertical if _inside(numeric_span, (axis.position, axis.position),
                                                                      -_MARGIN)
                        and any(_overlap(segment, row) > _MARGIN for segment in axis.segments))
        present = {boundary for boundary, axes in walls.items() if any(_covers(axis.segments, row) for axis in axes)}
        closed = len(present) == len(boundaries)
        # 邻行可沿列界绘制分段横线。内竖线若断在本行，横线不能证明本行仍分列。
        interrupted = any(walls[boundary] and boundary not in present for boundary in boundaries[1:-1])
        conflicting = any(not any(abs(axis.position - boundary) <= _MARGIN for boundary in boundaries)
                          for axis in strokes)
        styles = style(upper), style(lower)
        independent = (not conflicting and None not in styles
                       and (closed or not interrupted and "segmented" in styles))
        bands.append(_Band((numeric_span[0], top, numeric_span[1], bottom), independent, not closed))
    return tuple(bands)


def _rows_in_cell(
    cell: TableCell, area: Box, bands: tuple[_Band, ...], row: int,
) -> _Band | None:
    first = bisect_left(bands, area[1] - _MARGIN, key=lambda band: band.area[1])
    end = bisect_right(bands, area[3] + _MARGIN, key=lambda band: band.area[3])
    if end - first != cell.rowspan or not _near((bands[first].area[1], bands[end - 1].area[3]), _y(area)):
        return None
    return bands[first + row - cell.row]


def _slot(band: _Band, heading: _Heading) -> Box:
    return heading.box.area[0], band.area[1], heading.box.area[2], band.area[3]


def _word_in_band(text: _Text, geometry: _Geometry, band: _Band, heading: _Heading) -> Box | None:
    area = _slot(band, heading)
    words = geometry.words_in(area)
    if (len(words) == 1 and text.matches(words) and _contains(area, words[0].bbox, _MARGIN)
            and not geometry.has_unmapped_glyphs(area)):
        return words[0].bbox
    return None


def _cell_bands(
    cell: TableCell, text: _Text, row: int, zone: _Heading, bands: tuple[_Band, ...], geometry: _Geometry,
) -> dict[_Band, Box]:
    supported: dict[_Band, list[Box]] = defaultdict(list)
    for seen in geometry.text_boxes(text, _x(zone.box.area)):
        if seen.area[1] >= zone.box.area[3] - _MARGIN:
            band = _rows_in_cell(cell, seen.area, bands, row)
            if band is not None:
                supported[band].append(seen.text)
    return {band: boxes[0] for band, boxes in supported.items() if len(boxes) == 1}


@dataclass(frozen=True)
class _RowMatch:
    candidates: dict[_Band, tuple[Box, ...]]
    reason: str | None = None


def _context_heading(cell: TableCell, header: _Header) -> _Heading | None:
    return next((title for title in header.context if title.column <= cell.column
                 and cell.column + cell.colspan <= title.end_column), None)


def _match_row(
    row: int, active: list[TableCell], header: _Header, bands: tuple[_Band, ...], geometry: _Geometry,
) -> _RowMatch:
    matching: dict[_Band, tuple[Box, ...]] | None = None
    independent = False
    first_numeric = header.numeric[0].column
    numeric = {title.column: title for title in header.numeric}
    for neighbor in active:
        if neighbor.column >= header.unit.column:
            continue
        context = _context_heading(neighbor, header)
        value_title = numeric.get(neighbor.column) if neighbor.rowspan == neighbor.colspan == 1 else None
        if context is None and value_title is None:
            if neighbor.column < first_numeric and any(run.source.strip() for run in neighbor.runs):
                return _RowMatch({}, "row_anchor_missing")
            continue
        text = _context_text(neighbor) if context is not None else _source_text(neighbor)
        failure = "rowspan_context_unresolved" if neighbor.rowspan > 1 else "row_anchor_missing"
        if text is None:
            return _RowMatch({}, failure)
        if not text.tokens:
            continue
        independent |= neighbor.rowspan == 1
        if context is not None:
            supported = _cell_bands(neighbor, text, row, context, bands, geometry)
        else:
            assert value_title is not None
            supported = {band: seen for band in (bands if matching is None else matching)
                         if (seen := _word_in_band(text, geometry, band, value_title)) is not None}
        if matching is None:
            matching = {band: (box,) for band, box in supported.items()}
        else:
            matching = {band: anchors + (box,) for band, anchors in matching.items()
                        if (box := supported.get(band)) is not None and box not in anchors}
        if not matching:
            return _RowMatch({}, failure)
    if not matching:
        return _RowMatch({}, "row_anchor_missing")
    if len(matching) > 1:
        return _RowMatch(matching, "row_anchor_nonunique")
    return _RowMatch(matching, None if independent else "row_anchor_missing")


def _match_unit(
    active: list[TableCell], header: _Header, geometry: _Geometry, bands: tuple[_Band, ...],
    row: int,
) -> dict[_Band, Box]:
    units = [cell for cell in active if cell.column == header.unit.column and cell.colspan == 1]
    if len(units) != 1 or (text := _context_text(units[0], unit=True)) is None or not text.tokens:
        return {}
    return _cell_bands(units[0], text, row, header.unit, bands, geometry)


@dataclass
class _ValueWords:
    count: int = 0
    by_band: dict[_Band, list[PdfValueColumnWord]] = field(default_factory=dict)


def _locate_row(
    context: _RowMatch, units: dict[_Band, Box], words: _ValueWords | None, source_count: int,
) -> _RowMatch:
    if context.reason is None or not context.candidates:
        return context
    if words is None:
        return _RowMatch({}, context.reason)
    possible = {band: hits for band, hits in words.by_band.items() if band in context.candidates}
    if not possible:
        return _RowMatch({}, context.reason)
    if words.count == 1 and source_count != 1:
        return _RowMatch({}, "value_word_nonunique")
    if any(len(hits) != 1 for hits in possible.values()):
        return _RowMatch({}, "value_word_nonunique")
    if not all(hits[0].glyphs for hits in possible.values()):
        return _RowMatch({}, "value_visibility_unverified")
    if not all(_contains(band.area, hits[0].bbox, _MARGIN) for band, hits in possible.items()):
        return _RowMatch({}, "value_ambiguous")
    candidates = {band: context.candidates[band] for band in possible if band in units}
    if not candidates:
        return _RowMatch({}, "unit_row_mismatch")
    return _RowMatch(candidates, None if len(candidates) == 1 else "value_word_nonunique")


@dataclass(frozen=True, slots=True)
class _Alignment:
    size: int
    count: int
    path: _AlignmentStep | None = None


@dataclass(frozen=True, slots=True)
class _AlignmentStep:
    row: int
    band: int
    previous: _AlignmentStep | None


def _best_alignment(left: _Alignment, right: _Alignment) -> _Alignment:
    if left.size == right.size:
        return _Alignment(left.size, 2)
    return left if left.size > right.size else right


def _align_window(
    rows: Iterable[tuple[int, set[int]]], start: int, end: int,
) -> _Alignment:
    # 按最后一个已匹配 band 区分映射。不同的跳步顺序不会重复计数同一映射。
    endings: dict[int, _Alignment] = {}
    empty = _Alignment(0, 1)
    for row, candidates in rows:
        choices = sorted(index for index in candidates if start <= index < end)
        if not choices:
            continue
        prefix = empty
        previous = iter(sorted(endings.items()))
        known = next(previous, None)
        for index in choices:
            while known is not None and known[0] < index:
                prefix = _best_alignment(prefix, known[1])
                known = next(previous, None)
            if prefix.size + 1 < (old := endings.get(index, empty)).size:
                continue
            path = _AlignmentStep(row, index, prefix.path) if prefix.count == 1 else None
            endings[index] = _best_alignment(old, _Alignment(prefix.size + 1, prefix.count, path))
    best = empty
    for ending in endings.values():
        best = _best_alignment(best, ending)
    return best


def _active_cells(cells: list[TableCell], rows: tuple[int, ...]) -> dict[int, list[TableCell]]:
    active: dict[int, list[TableCell]] = defaultdict(list)
    for cell in cells:
        first = bisect_left(rows, cell.row)
        end = bisect_left(rows, cell.row + cell.rowspan)
        for index in range(first, end):
            active[rows[index]].append(cell)
    return active


def _rowspans(cells: list[TableCell], header: _Header) -> Iterable[tuple[TableCell, _Heading]]:
    for cell in cells:
        if cell.rowspan <= 1 or not any(run.source.strip() for run in cell.runs):
            continue
        title = header.unit if cell.column == header.unit.column and cell.colspan == 1 else _context_heading(cell, header)
        if title is not None:
            yield cell, title


def _conflicting_rowspans(
    assigned: Iterable[tuple[int, int]], active: dict[int, list[TableCell]], header: _Header,
    bands: tuple[_Band, ...], geometry: _Geometry,
) -> set[int]:
    source: dict[str, dict[Box, set[int]]] = defaultdict(lambda: defaultdict(set))
    pdf: dict[Box, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for row, index in assigned:
        for cell, title in _rowspans(active[row], header):
            text = _context_text(cell, unit=title is header.unit)
            if text is None:
                continue
            box = _cell_bands(cell, text, row, title, bands, geometry).get(bands[index])
            if box is not None:
                source[cell.id][box].add(row)
                pdf[box][cell.id].add(row)
    # 各行已证明格内相对位置。同一个源合并格只能有一个 PDF 物理格，反向也一样。
    return {row for ownership in (source, pdf) for owners in ownership.values() if len(owners) > 1
            for rows in owners.values() for row in rows}


def _proposal_span_conflicts(
    grid: TableGrid, assigned: set[tuple[int, int]], active: dict[int, list[TableCell]], header: _Header,
    bands: tuple[_Band, ...], geometry: _Geometry,
) -> set[int]:
    relevant = {
        (title, cell.rowspan, _context_text(cell, unit=title is header.unit))
        for row, _ in assigned for cell, title in _rowspans(active[row], header)
    }
    if not relevant:
        return set()
    # 同文源合并格也可能争用被选中的 PDF 物理格，包含没有跨列 finding 的同行。
    covered = {
        row for cell, title in _rowspans(grid.cells, header)
        if (title, cell.rowspan, _context_text(cell, unit=title is header.unit)) in relevant
        for row in range(cell.row, min(cell.row + cell.rowspan, grid.rows))
    }
    independent = _active_cells(grid.cells, tuple(sorted(covered - {row for row, _ in assigned})))
    indices = {band: index for index, band in enumerate(bands)}
    anchors = set(assigned)
    for row, cells in independent.items():
        context = _match_row(row, cells, header, bands, geometry)
        if context.reason is None:
            band = next(iter(context.candidates))
            if band in _match_unit(cells, header, geometry, bands, row):
                anchors.add((row, indices[band]))
    return _conflicting_rowspans(anchors, {**active, **independent}, header, bands, geometry)


def _exact_words(text: _Text, band: _Band, geometry: _Geometry) -> tuple[PdfValueColumnWord, ...]:
    return tuple(word for word in geometry.words_in(band.area) if _tokens(word.text) == text.tokens)


def _verified_value_in_band(text: _Text, band: _Band, value_words: _ValueWords | None) -> bool:
    if value_words is None:
        return False
    # 索引保留所有相交的框，这里沿用格内取词的实质相交阈值。
    words = tuple(word for word in value_words.by_band.get(band, ())
                  if _overlap(_x(band.area), _x(word.bbox)) > _MARGIN
                  and _overlap(_y(band.area), _y(word.bbox)) > _MARGIN)
    return len(words) == 1 and text.matches(words) and _contains(band.area, words[0].bbox, _MARGIN)


def _sequence_choices(
    row: int, cells: list[TableCell], findings: list[TableCell], located: dict[str, _RowMatch],
    units: dict[_Band, Box], grid_width: int, header: _Header, bands: tuple[_Band, ...], geometry: _Geometry,
    words_by_value: dict[tuple[str, ...], _ValueWords],
) -> tuple[set[_Band], bool]:
    if findings:
        options = []
        for finding in findings:
            if finding.rowspan != 1 or (text := _source_text(finding)) is None or len(text.tokens) != 1:
                return set(), False
            value_words = words_by_value.get(text.tokens)
            options.append({band for band in located[finding.id].candidates
                            if band in units and _verified_value_in_band(text, band, value_words)})
        return set.intersection(*options), all(located[cell.id].reason is None for cell in findings)
    if len(cells) == 1 and cells[0].rowspan == 1 and cells[0].column == 0 and cells[0].colspan == grid_width:
        # 只有完整的整宽物理格及精确标题才能作为分节锚点。
        text = _context_text(cells[0])
        if text is None or not text.tokens:
            return set(), False
        zone = header.context[0].box.area[0], header.unit.box.area[2]
        proved = {band for seen in geometry.text_boxes(text, zone)
                  if _near(_x(seen.area), zone) and seen.area[1] >= header.unit.box.area[3] - _MARGIN
                  and (band := _rows_in_cell(cells[0], seen.area, bands, row)) is not None}
        return proved, True
    context = _match_row(row, cells, header, bands, geometry)
    return set(context.candidates).intersection(units), context.reason is None


def _resolve_row_sequence(
    grid: TableGrid, cells: list[TableCell], located: dict[str, _RowMatch], row_units: dict[int, dict[_Band, Box]],
    header: _Header, bands: tuple[_Band, ...], geometry: _Geometry,
    words_by_value: dict[tuple[str, ...], _ValueWords],
) -> None:
    disputed = [cell for cell in cells if len(located[cell.id].candidates) > 1]
    if not disputed:
        return
    source_rows = tuple(range(header.source_row + 1, grid.rows))
    if len(source_rows) != len(bands):
        for cell in disputed:
            located[cell.id] = _RowMatch({}, "source_row_band_count_mismatch")
        return
    findings: dict[int, list[TableCell]] = defaultdict(list)
    for cell in cells:
        findings[cell.row].append(cell)
    active = _active_cells(grid.cells, source_rows)
    indices = {band: index for index, band in enumerate(bands)}
    options = {}
    fixed = []
    for row in source_rows:
        row_cells = active.get(row, [])
        units = row_units[row] if row in row_units else _match_unit(row_cells, header, geometry, bands, row)
        choices, independent = _sequence_choices(row, row_cells, findings[row], located, units,
                                                 grid.columns, header, bands, geometry, words_by_value)
        if independent and len(choices) == 1:
            fixed.append((row, indices[next(iter(choices))]))
        elif choices:
            options[row] = {indices[band] for band in choices}
    if len(fixed) < 2:
        return
    endpoints = [(header.source_row, -1), *fixed, (grid.rows, len(bands))]
    monotonic = all(first[1] < second[1] for first, second in zip(endpoints, endpoints[1:]))
    selected: dict[int, _Band] = {}
    assigned = fixed[:]
    if monotonic:
        for (left_row, left_band), (right_row, right_band) in zip(endpoints, endpoints[1:]):
            chain = _align_window(((row, options[row]) for row in range(left_row + 1, right_row) if row in options),
                                  left_band + 1, right_band)
            if chain.count != 1:
                monotonic = False
                break
            step = chain.path
            while step is not None:
                assigned.append((step.row, step.band))
                if left_band >= 0 and right_band < len(bands):
                    selected[step.row] = bands[step.band]
                step = step.previous
        if monotonic and _conflicting_rowspans(assigned, active, header, bands, geometry):
            monotonic = False
    for cell in disputed:
        if not monotonic:
            located[cell.id] = _RowMatch({}, "row_sequence_ambiguous")
        elif (band := selected.get(cell.row)) is not None:
            located[cell.id] = _RowMatch({band: located[cell.id].candidates[band]})


def _correction(
    cell: TableCell, covered: dict[int, str], located: _RowMatch, units: dict[_Band, Box],
    header: _Header, geometry: _Geometry, layout_sha256: str, version: str,
    original_bbox: Box, table_edge: PdfValueColumnTableEdge | None,
) -> TableValueColumnCorrection | str:
    old_columns = tuple(heading for heading in header.numeric
                        if cell.column <= heading.column < cell.column + cell.colspan)
    if (cell.rowspan != 1 or cell.colspan != len(covered) or cell.row <= header.source_row
            or covered != {heading.column: heading.value_label for heading in old_columns}):
        return "unsupported_cell_shape"
    if located.reason is not None:
        return located.reason
    (band, anchors), = located.candidates.items()
    if not band.independent_columns:
        return "column_ambiguous"
    text = _source_text(cell)
    if text is None or len(text.tokens) != 1:
        return "value_ambiguous"
    words = _exact_words(text, band, geometry)
    if len(words) > 1:
        return "value_word_nonunique"
    if not words:
        return "value_ambiguous"
    word = words[0]
    if not text.matches(words):
        return "value_visibility_unverified"
    columns = tuple(title for title in header.numeric if _inside(_x(title.box.area), _x(word.bbox), _MARGIN))
    if (len(columns) != 1 or columns[0].column not in covered
            or band.requires_alignment and abs(word.bbox[2] - columns[0].box.text[2]) > _MARGIN):
        return "column_ambiguous"
    target = columns[0]
    if not _word_in_band(text, geometry, band, target):
        return "value_ambiguous"
    for heading in old_columns:
        area = _slot(band, heading)
        if heading != target and (geometry.words_in(area) or geometry.has_unmapped_glyphs(area)):
            return "span_contains_other_content"
    unit = units.get(band)
    if unit is None:
        return "unit_row_mismatch"
    return TableValueColumnCorrection(
        source_row_index=cell.source_row_index, source_cell_index=cell.source_cell_index,
        content_sha256=cell.content_sha256, original_column_range=(cell.column, cell.column + cell.colspan),
        target_column=target.column, target_header=covered[target.column].upper(),
        pdf_binding=PdfValueColumnBinding(
            extractor_version=version, layout_sha256=layout_sha256,
            table_bbox=original_bbox, table_edge=table_edge,
            row_range=_y(band.area), column_range=_x(target.box.area),
            header_bbox=target.box.text, value_bbox=word.bbox, unit_bbox=unit,
            row_anchor_bboxes=anchors, glyph_anchors=word.glyphs,
        ),
    )


def _edge_for_header(edge: PdfValueColumnTableEdge, header: _Header) -> PdfValueColumnTableEdge | None:
    """保留与表头、表体和取证边界直接相关的线段，避免逐格重复整表线网。"""
    extreme = header.context[0].box.area if edge.side == "left" else header.unit.box.area
    outer = extreme[0] if edge.side == "left" else extreme[2]
    lines = edge.horizontal_lines
    top, bottom = (min(lines, key=lambda line: abs(line[1] - border)) for border in (extreme[1], extreme[3]))
    body = next((line for line in lines if line[1] > extreme[3] + _MARGIN), None)
    if (abs(outer - edge.wall) > _MARGIN or abs(top[1] - extreme[1]) > _MARGIN
            or abs(bottom[1] - extreme[3]) > _MARGIN or top == bottom or body is None):
        return None
    outermost = (min(lines, key=lambda line: line[0]) if edge.side == "left"
                 else max(lines, key=lambda line: line[2]))
    start = min(line[1] for line in edge.vertical_lines)
    end = max(line[2] for line in edge.vertical_lines)
    return edge.model_copy(update={
        "horizontal_lines": tuple(sorted({top, bottom, body, outermost}, key=lambda line: line[1])),
        "vertical_lines": ((edge.wall, start, end),),
    })


def match_pdf_value_columns(
    result: TableBuildResult, observation: PdfValueColumnPage, table_bbox: Box, *, layout_sha256: str,
    skip_cells: frozenset[tuple[int, int]] = frozenset(),
    layout_bbox: Box | None = None,
    protected_regions: tuple[Box, ...] = (),
    legacy_value_column_replay: LegacyValueColumnReplay | None = None,
) -> tuple[tuple[TableValueColumnCorrection, ...], tuple[PdfValueColumnUnresolved, ...]]:
    """只为独立行列与可见实物吻合的源跨列发现提供核定记录。"""
    grid = result.grid
    by_id = {cell.id: cell for cell in grid.cells}
    version = LEGACY_VALIDATOR_VERSION if legacy_value_column_replay is not None else BINDING_VALIDATOR_VERSION
    policy = default_table_validation_policy(version)
    candidates = [(by_id[flag.cell_id], covered, make_finding_id(grid.table_id, flag, evidence))
                  for flag, evidence, covered in iter_parameter_value_column_spans(
                      result, policy, validator_version=version, legacy_value_column_replay=legacy_value_column_replay,
                  ) if evidence.rule_id in REVIEWABLE_VALUE_COLUMN_RULES
                  and (evidence.source_row_index, evidence.source_cell_index) not in skip_cells]
    if not candidates:
        return (), ()

    source_rows: dict[int, list[TableCell]] = defaultdict(list)
    for cell in grid.cells:
        source_rows[cell.row].append(cell)
    required_rows = tuple(sorted({cell.row for cell, _, _ in candidates}))
    active_rows = _active_cells(grid.cells, required_rows)

    unsupported = any(_intersects(table_bbox, area) for area in observation.unsupported_regions)
    geometry = _Geometry(observation, table_bbox)
    header = None if unsupported else _header(source_rows, geometry)
    table_edge = None
    if header is None and not unsupported and layout_bbox is not None:
        edge = find_pdf_table_edge(observation, table_bbox, layout_bbox, protected_regions)
        if edge is not None:
            corrected_geometry = _Geometry(observation, edge.corrected_bbox)
            corrected_header = _header(source_rows, corrected_geometry)
            if corrected_header is not None:
                table_edge = _edge_for_header(edge, corrected_header)
                if table_edge is not None:
                    geometry, header = corrected_geometry, corrected_header
    bands = _data_bands(header, geometry) if header is not None else ()
    located = {}
    row_units = {}
    words_by_value: dict[tuple[str, ...], _ValueWords] = defaultdict(_ValueWords)
    source_values: Counter[tuple[str, ...]] = Counter()
    if header is not None:
        first_numeric = header.numeric[0]
        data_area = (first_numeric.box.area[0], header.unit.box.area[3] - _MARGIN,
                     header.numeric[-1].box.area[2], geometry.table[3])
        # 未确证可见性、跨边界和不落完整行带的词仍参与全表计数。
        for word in geometry.words:
            if _intersects(data_area, word.bbox):
                matches = words_by_value[_tokens(word.text)]
                matches.count += 1
                first = bisect_right(bands, word.bbox[1], key=lambda band: band.area[3])
                end = bisect_left(bands, word.bbox[3], key=lambda band: band.area[1])
                for index in range(first, end):
                    matches.by_band.setdefault(bands[index], []).append(word)
        for cell in grid.cells:
            if (cell.row > header.source_row
                    and first_numeric.column <= cell.column < cell.column + cell.colspan <= header.unit.column
                    and (text := _source_text(cell)) is not None and len(text.tokens) == 1):
                source_values[text.tokens] += 1
        row_contexts = {row: _match_row(row, cells, header, bands, geometry) for row, cells in active_rows.items()}
        row_units = {row: _match_unit(cells, header, geometry, bands, row) for row, cells in active_rows.items()}
        for cell, _, _ in candidates:
            text = _source_text(cell)
            tokens = text.tokens if text is not None else ()
            located[cell.id] = _locate_row(row_contexts[cell.row], row_units[cell.row],
                                           words_by_value.get(tokens), source_values[tokens])
        _resolve_row_sequence(grid, [cell for cell, _, _ in candidates], located, row_units,
                              header, bands, geometry, words_by_value)
    proposals = []
    for cell, covered, finding_id in candidates:
        if header is None:
            proposal = "unsupported_pdf_geometry" if unsupported else "header_ambiguous"
        else:
            proposal = _correction(cell, covered, located[cell.id], row_units[cell.row], header, geometry,
                                   layout_sha256, observation.extractor_version, table_bbox, table_edge)
        proposals.append((cell, finding_id, proposal))

    values = Counter(item.pdf_binding.value_bbox for _, _, item in proposals
                     if isinstance(item, TableValueColumnCorrection))
    pdf_rows: dict[_Interval, set[int]] = defaultdict(set)
    source_rows_to_pdf: dict[int, set[_Interval]] = defaultdict(set)
    band_indices = {_y(band.area): index for index, band in enumerate(bands)}
    assignments = set()
    for cell, _, item in proposals:
        if isinstance(item, TableValueColumnCorrection):
            row_range = item.pdf_binding.row_range
            pdf_rows[row_range].add(cell.row)
            source_rows_to_pdf[cell.row].add(row_range)
            assignments.add((cell.row, band_indices[row_range]))
        elif header is not None and cell.rowspan == 1 and located[cell.id].reason is None:
            band, = located[cell.id].candidates
            text = _source_text(cell)
            # 列界不明确仍可能已证实同行，这条行证据也约束同组的其他修正。
            if (text is not None and len(text.tokens) == 1 and band in row_units[cell.row]
                    and _verified_value_in_band(text, band, words_by_value.get(text.tokens))):
                assignments.add((cell.row, band_indices[_y(band.area)]))
    conflicts = (_proposal_span_conflicts(grid, assignments, active_rows, header, bands, geometry)
                 if header is not None else set())
    corrections = []
    unresolved = []
    for cell, finding_id, item in proposals:
        if isinstance(item, TableValueColumnCorrection):
            if cell.row in conflicts:
                item = "rowspan_context_unresolved"
            elif (values[item.pdf_binding.value_bbox] == 1 and len(pdf_rows[item.pdf_binding.row_range]) == 1
                    and len(source_rows_to_pdf[cell.row]) == 1):
                corrections.append(item)
                continue
            else:
                item = "competing_pdf_binding"
        unresolved.append(PdfValueColumnUnresolved(
            fragment_id=cell.source_fragment_id, finding_id=finding_id, source_row_index=cell.source_row_index,
            source_cell_index=cell.source_cell_index, reason=item,
        ))
    return tuple(corrections), tuple(unresolved)
