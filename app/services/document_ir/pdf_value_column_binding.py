"""用已核实表区的实际行列、词和单位生成可逐格核验的拟修正。"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
import re

from app.services.document_ir.pdf_value_column_observer import Box, PdfValueColumnPage, PdfValueColumnWord
from app.services.document_ir.pdf_value_column_table_edge import find_pdf_table_edge
from app.services.document_ir.table_value_column_review import (
    LegacyValueColumnReplay, PdfValueColumnBinding, PdfValueColumnTableEdge, PdfValueColumnUnresolved,
    TableValueColumnCorrection,
)
from app.services.tables.grid_builder import TableBuildResult
from app.services.tables.models import TableCell
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
    r"(?:\s*=\s*(?P<condition>[-−–+.A-Za-z0-9°%/·√µμΩ ]+))?\$"
)


def _tokens(value: str) -> tuple[str, ...]:
    # 仅接纳字面量中的微符号、负号等价，保留大小写、比较符与指数。
    return tuple(re.sub(r"(?<![\d.])[−–](?=\d)", "-", value.replace("μ", "µ")).split())


@dataclass(frozen=True)
class _Text:
    tokens: tuple[str, ...]
    subscript: bool = False
    heading: bool = False

    def word(self, value: str) -> tuple[str, ...]:
        return _tokens(value.upper() if self.heading else value)

    def matches(self, words: tuple[PdfValueColumnWord, ...]) -> bool:
        if not words or not all(word.glyphs for word in words):
            return False
        if tuple(part for word in words for part in self.word(word.text)) != self.tokens:
            return False
        base_y = words[0].bbox[1]
        for index, word in enumerate(words):
            if index == 1 and self.subscript:
                if not (base_y + _MARGIN < word.bbox[1] < words[0].bbox[3]
                        and abs(words[0].bbox[2] - word.bbox[0]) <= _MARGIN):
                    return False
            elif abs(word.bbox[1] - base_y) > _MARGIN:
                return False
        return True


def _source_text(cell: TableCell) -> _Text | None:
    value = "".join(run.source for run in cell.runs).strip()
    if all(run.type == "text" for run in cell.runs):
        return _Text(_tokens(value))
    formula = _SIMPLE_SUBSCRIPT.fullmatch(value)
    if formula is not None and sum(run.type == "formula" for run in cell.runs) == 1:
        condition = _tokens(formula["condition"] or "")
        tokens = (formula["base"], formula["subscript"].strip("{}"))
        if formula["condition"] and not condition:
            return None
        return _Text(tokens + (("=",) + condition if condition else ()), subscript=True)
    return None


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
            initial_words[_tokens(word.text.upper())].append(word)
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
        for seed in self._initial_words.get(_tokens(text.tokens[0].upper()), ()):
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
            if cell.rowspan != 1 or text is None or text.subscript or not text.tokens:
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
    eligible = tuple(band for band in bands if _inside(_y(area), _y(band.area), -_MARGIN))
    if (len(eligible) != cell.rowspan or not _near(
            (eligible[0].area[1], eligible[-1].area[3]), _y(area))):
        return None
    return eligible[row - cell.row]


def _slot(band: _Band, heading: _Heading) -> Box:
    return heading.box.area[0], band.area[1], heading.box.area[2], band.area[3]


def _word_in_band(text: _Text, geometry: _Geometry, band: _Band, heading: _Heading) -> Box | None:
    area = _slot(band, heading)
    words = geometry.words_in(area)
    if (len(words) == 1 and text.matches(words) and _contains(area, words[0].bbox, _MARGIN)
            and not geometry.has_unmapped_glyphs(area)):
        return words[0].bbox
    return None


def _match_row(
    cell: TableCell, active: list[TableCell], header: _Header, bands: tuple[_Band, ...], geometry: _Geometry,
) -> tuple[_Band, tuple[Box, ...]] | None:
    matching: dict[_Band, tuple[Box, ...]] = {band: () for band in bands}
    has_independent_row_anchor = False
    first_numeric = header.numeric[0].column
    numeric = {title.column: title for title in header.numeric}
    for neighbor in active:
        if neighbor.id == cell.id or neighbor.column >= header.unit.column:
            continue
        context = next((title for title in header.context if title.column <= neighbor.column
                        and neighbor.column + neighbor.colspan <= title.end_column), None)
        value_title = numeric.get(neighbor.column) if neighbor.rowspan == neighbor.colspan == 1 else None
        if context is None and value_title is None:
            if neighbor.column < first_numeric and any(run.source.strip() for run in neighbor.runs):
                return None
            continue
        text = _source_text(neighbor)
        if text is None:
            return None
        if not text.tokens:
            continue
        has_independent_row_anchor |= neighbor.rowspan == 1
        if context is not None:
            supported = defaultdict(list)
            for seen in geometry.text_boxes(text, _x(context.box.area)):
                if seen.area[1] < context.box.area[3] - _MARGIN:
                    continue
                band = _rows_in_cell(neighbor, seen.area, bands, cell.row)
                if band is not None:
                    supported[band].append(seen.text)
            matching = {band: anchors + (supported[band][0],) for band, anchors in matching.items()
                        if len(supported[band]) == 1}
        else:
            matching = {band: anchors + (seen,) for band, anchors in matching.items()
                        if (seen := _word_in_band(text, geometry, band, value_title)) is not None}
        if not matching:
            return None
    return next(iter(matching.items())) if has_independent_row_anchor and len(matching) == 1 else None


def _match_unit(
    active: list[TableCell], header: _Header, geometry: _Geometry, bands: tuple[_Band, ...],
    band: _Band, row: int,
) -> Box | None:
    units = [cell for cell in active if cell.column == header.unit.column and cell.colspan == 1]
    if len(units) != 1 or (text := _source_text(units[0])) is None or text.subscript or len(text.tokens) != 1:
        return None
    actual_units = tuple(seen.text for seen in geometry.text_boxes(text, _x(header.unit.box.area))
                         if _rows_in_cell(units[0], seen.area, bands, row) == band)
    return actual_units[0] if len(actual_units) == 1 else None


def _correction(
    cell: TableCell, covered: dict[int, str], active: list[TableCell], header: _Header, geometry: _Geometry,
    bands: tuple[_Band, ...], layout_sha256: str, version: str,
    original_bbox: Box, table_edge: PdfValueColumnTableEdge | None,
) -> TableValueColumnCorrection | str:
    old_columns = tuple(heading for heading in header.numeric
                        if cell.column <= heading.column < cell.column + cell.colspan)
    if (cell.rowspan != 1 or cell.colspan != len(covered) or cell.row <= header.source_row
            or covered != {heading.column: heading.value_label for heading in old_columns}):
        return "unsupported_cell_shape"
    located = _match_row(cell, active, header, bands, geometry)
    if located is None:
        return "row_ambiguous"
    band, anchors = located
    if not band.independent_columns:
        return "column_ambiguous"
    text = _source_text(cell)
    if text is None or len(text.tokens) != 1:
        return "value_ambiguous"
    words = tuple(word for word in geometry.words_in(band.area) if _tokens(word.text) == text.tokens)
    if len(words) != 1:
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
    unit = _match_unit(active, header, geometry, bands, band, cell.row)
    if unit is None:
        return "unit_mismatch"
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
    required_rows = {cell.row for cell, _, _ in candidates}
    active_rows = defaultdict(list)
    for cell in grid.cells:
        for row in range(cell.row, cell.row + cell.rowspan):
            if row in required_rows:
                active_rows[row].append(cell)

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
    proposals = []
    for cell, covered, finding_id in candidates:
        if header is None:
            proposal = "unsupported_pdf_geometry" if unsupported else "header_ambiguous"
        else:
            proposal = _correction(cell, covered, active_rows[cell.row], header, geometry, bands,
                                   layout_sha256, observation.extractor_version, table_bbox, table_edge)
        proposals.append((cell, finding_id, proposal))

    values = Counter(item.pdf_binding.value_bbox for _, _, item in proposals
                     if isinstance(item, TableValueColumnCorrection))
    pdf_rows: dict[_Interval, set[int]] = defaultdict(set)
    source_rows_to_pdf: dict[int, set[_Interval]] = defaultdict(set)
    for cell, _, item in proposals:
        if isinstance(item, TableValueColumnCorrection):
            pdf_rows[item.pdf_binding.row_range].add(cell.row)
            source_rows_to_pdf[cell.row].add(item.pdf_binding.row_range)
    corrections = []
    unresolved = []
    for cell, finding_id, item in proposals:
        if isinstance(item, TableValueColumnCorrection):
            if (values[item.pdf_binding.value_bbox] == 1 and len(pdf_rows[item.pdf_binding.row_range]) == 1
                    and len(source_rows_to_pdf[cell.row]) == 1):
                corrections.append(item)
                continue
            item = "competing_pdf_binding"
        unresolved.append(PdfValueColumnUnresolved(
            fragment_id=cell.source_fragment_id, finding_id=finding_id, source_row_index=cell.source_row_index,
            source_cell_index=cell.source_cell_index, reason=item,
        ))
    return tuple(corrections), tuple(unresolved)
