"""用已核实 PDF 的相接线段恢复被截断的表框侧缘。"""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

from app.services.document_ir.pdf_value_column_observer import AxisSegment, Box, PdfValueColumnPage
from app.services.document_ir.table_value_column_review import (
    TABLE_EDGE_CONTACT_TOLERANCE, TABLE_EDGE_SEARCH_LIMIT, TABLE_EDGE_STROKE_OVERHANG,
    PdfValueColumnTableEdge,
)

_Side = Literal["left", "right"]


def _overlaps(first: Box, second: Box) -> bool:
    return max(first[0], second[0]) < min(first[2], second[2]) and max(first[1], second[1]) < min(first[3], second[3])


def _outward_range(left: float, right: float, side: _Side) -> tuple[float, float]:
    return (-right, -left) if side == "left" else (left, right)


def _continuous_wall(segments: tuple[AxisSegment, ...], start: float, end: float) -> bool:
    tolerance = TABLE_EDGE_CONTACT_TOLERANCE
    if segments[0][1] > start + tolerance:
        return False
    reached = segments[0][2]
    for _, top, bottom in segments[1:]:
        if top > reached + tolerance:
            return False
        reached = max(reached, bottom)
    return reached >= end - tolerance


def _side_candidates(
    observation: PdfValueColumnPage, original: Box, layout_box: Box, side: _Side,
) -> list[PdfValueColumnTableEdge]:
    left, top, right, bottom = original
    outward = 1 if side == "right" else -1
    opposite_edge, old_edge = _outward_range(left, right, side)
    _, layout_edge = _outward_range(layout_box[0], layout_box[2], side)
    limit = layout_edge + TABLE_EDGE_SEARCH_LIMIT
    join = TABLE_EDGE_CONTACT_TOLERANCE
    cap = TABLE_EDGE_STROKE_OVERHANG
    walls = defaultdict(set)
    for x, start, end in observation.vertical_lines:
        if (old_edge - cap <= outward * x <= limit
                and abs(outward * x - layout_edge) <= TABLE_EDGE_SEARCH_LIMIT
                and max(start, top) < min(end, bottom)):
            walls[x].add((x, max(start, top), min(end, bottom)))

    horizontals = []
    for segment in observation.horizontal_lines:
        start, level, end = segment
        inner, edge = _outward_range(start, end, side)
        if top <= level <= bottom and opposite_edge - join <= inner <= old_edge - cap and old_edge < edge <= limit:
            horizontals.append((edge, segment))

    candidates = []
    for wall, segments in walls.items():
        wall_edge = outward * wall
        support = tuple(sorted({line for edge, line in horizontals if wall_edge - join <= edge <= wall_edge + cap},
                               key=lambda line: (line[1], line[0], line[2])))
        levels = sorted({line[1] for line in support})
        if len(levels) < 3 or len(levels) != len(support) or min(b - a for a, b in zip(levels, levels[1:])) <= join:
            continue
        verticals = tuple(sorted(segments))
        if not _continuous_wall(verticals, levels[0], levels[-1]):
            continue
        # 伸出墙轴的短线端帽也是现有几何匹配所需的完整线段。
        measured = max(wall_edge, *(_outward_range(line[0], line[2], side)[1] for line in support))
        corrected = (-measured, top, right, bottom) if side == "left" else (left, top, measured, bottom)
        if not 0 <= corrected[0] < corrected[2] <= observation.width:
            continue
        candidates.append(PdfValueColumnTableEdge(
            side=side, layout_bbox=layout_box, corrected_bbox=corrected, wall=wall,
            horizontal_lines=support, vertical_lines=verticals,
        ))
        if len(candidates) > 1:
            break
    return candidates


def _strip_is_clear(
    observation: PdfValueColumnPage, original: Box, candidate: PdfValueColumnTableEdge,
    protected_regions: tuple[Box, ...],
) -> bool:
    side = candidate.side
    left, top, right, bottom = original
    corrected = candidate.corrected_bbox
    strip = (corrected[0], top, left, bottom) if side == "left" else (right, top, corrected[2], bottom)
    if any(max(strip[0], region[0]) <= min(strip[2], region[2])
           and max(strip[1], region[1]) <= min(strip[3], region[3]) for region in protected_regions):
        return False
    if (any(_overlaps(strip, word.bbox) for word in observation.words)
            or any(_overlaps(strip, region) for region in observation.unmapped_glyph_regions)
            or any(_overlaps(strip, region) for region in observation.unsupported_regions)
            or any(_overlaps(strip, region) for region in observation.opaque_fill_regions)):
        return False

    cap = TABLE_EDGE_STROKE_OVERHANG
    join = TABLE_EDGE_CONTACT_TOLERANCE
    outward = 1 if side == "right" else -1
    wall_edge = outward * candidate.wall
    old_edge, new_edge = _outward_range(strip[0], strip[2], side)
    horizontal = set(candidate.horizontal_lines)
    vertical = set(candidate.vertical_lines)
    for stroke in observation.stroke_footprints:
        if not _overlaps(strip, stroke.bbox):
            continue
        if stroke.horizontal:
            if stroke.segment not in horizontal:
                return False
        else:
            x, start, end = stroke.segment
            if (x, max(top, start), min(bottom, end)) not in vertical:
                return False

    for line in observation.horizontal_lines:
        start, level, end = line
        if line in horizontal or not top <= level <= bottom:
            continue
        inner, edge = _outward_range(start, end, side)
        crosses_strip = max(old_edge, inner) < min(new_edge, edge)
        # 同一轴向外继续延伸的横线可能属于共边的相邻表。
        adjoining = wall_edge - join <= inner <= new_edge + join and edge > wall_edge + cap
        if crosses_strip or adjoining:
            return False

    if any(max(top, start) < min(bottom, end) and old_edge < outward * x <= new_edge and x != candidate.wall
           for x, start, end in observation.vertical_lines):
        return False

    for fill in observation.rectangles:
        if not _overlaps(strip, fill):
            continue
        inner, edge = _outward_range(fill[0], fill[2], side)
        if not (corrected[0] <= fill[0] < fill[2] <= corrected[2]
                and top <= fill[1] < fill[3] <= bottom and 0 <= wall_edge - edge <= cap
                and inner <= old_edge - cap):
            return False
        # 色块只有夹在同一侧缘的两条相接横线之间，才归入这次取证范围。
        for upper, lower in zip(candidate.horizontal_lines, candidate.horizontal_lines[1:]):
            if (0 <= fill[1] - upper[1] <= cap and 0 <= lower[1] - fill[3] <= cap
                    and all(line[0] <= fill[0] and fill[2] <= line[2] for line in (upper, lower))):
                break
        else:
            return False
    return True


def find_pdf_table_edge(
    observation: PdfValueColumnPage, original: Box, layout_box: Box, protected_regions: tuple[Box, ...],
) -> PdfValueColumnTableEdge | None:
    """保留原框的上下缘和另一侧，仅接纳一个能证明归属的侧缘。"""
    sides: tuple[_Side, ...] = ("left", "right")
    candidates = [
        candidate for side in sides
        for candidate in _side_candidates(observation, original, layout_box, side)
    ]
    if len(candidates) != 1 or not _strip_is_clear(observation, original, candidates[0], protected_regions):
        return None
    return candidates[0]
