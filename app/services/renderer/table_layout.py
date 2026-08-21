from __future__ import annotations

# app/services/renderer/table_layout.py: 纯计算表格列宽、字号适配和容器降级证据。

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import asdict, dataclass

from app.conversion.runtime.table_html_parser import HtmlCell, HtmlTable


EMU_PER_POINT = 12_700
FONT_STEP = 0.5
CELL_HORIZONTAL_PADDING_PT = 8.0
MAX_CONTENT_WEIGHT_UNITS = 48.0
ENGINEERING_CODE_DESCRIPTION_RE = re.compile(
    r"(^|[>\s(（\[【,，;；:：])([A-Za-z]+-\d+)(?=[A-Za-z])"
)


@dataclass(frozen=True, slots=True)
class TableFitDecision:
    """LayoutPlan 中单张语义表格的最终可解释适配决定。"""

    block_id: str
    container: str
    preferred_font_size: float | None
    minimum_font_size: float | None
    selected_font_size: float | None
    available_width: int
    required_width: int
    column_widths: tuple[int, ...]
    source_width_ratio: float | None
    fits: bool
    reason: str
    quality_flags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """返回 evidence 可直接序列化的稳定数据。"""

        return asdict(self)


def choose_table_fit_decision(
    *,
    block_id: str,
    table: HtmlTable,
    container: str,
    available_width: int,
    preferred_font_size: float | None,
    minimum_font_size: float | None,
    source_width_ratio: float | None = None,
) -> TableFitDecision:
    """选择不低于最小字号的最大适配字号，并按最终内容分配列宽。

    ``source_width_ratio`` 只随决定写入 evidence；源 bbox 无法证明 Word
    单元格列宽，因此不参与内容宽度和字号估算。
    """

    column_count = table.max_columns
    if column_count <= 0:
        return TableFitDecision(
            block_id=block_id,
            container=container,
            preferred_font_size=preferred_font_size,
            minimum_font_size=minimum_font_size,
            selected_font_size=preferred_font_size,
            available_width=available_width,
            required_width=0,
            column_widths=(),
            source_width_ratio=source_width_ratio,
            fits=True,
            reason="empty_table",
        )

    minimum_units, content_weights = _column_metrics(table)
    if preferred_font_size is None:
        widths, required_width, _fits = _widths_for_font(
            minimum_units,
            content_weights,
            available_width,
            10.0,
        )
        return TableFitDecision(
            block_id=block_id,
            container=container,
            preferred_font_size=None,
            minimum_font_size=None,
            selected_font_size=None,
            available_width=available_width,
            required_width=required_width,
            column_widths=tuple(widths),
            source_width_ratio=source_width_ratio,
            fits=True,
            reason="font_size_unconfigured",
        )

    effective_minimum = minimum_font_size if minimum_font_size is not None else preferred_font_size
    candidates = _font_candidates(preferred_font_size, effective_minimum)
    last_widths: list[int] = []
    last_required_width = 0
    for candidate in candidates:
        widths, required_width, fits = _widths_for_font(
            minimum_units,
            content_weights,
            available_width,
            candidate,
        )
        last_widths = widths
        last_required_width = required_width
        if not fits:
            continue
        reduced = candidate < preferred_font_size
        flags = (
            (f"table_font_reduced:{block_id}:{preferred_font_size:g}->{candidate:g}",)
            if reduced
            else ()
        )
        return TableFitDecision(
            block_id=block_id,
            container=container,
            preferred_font_size=preferred_font_size,
            minimum_font_size=effective_minimum,
            selected_font_size=candidate,
            available_width=available_width,
            required_width=required_width,
            column_widths=tuple(widths),
            source_width_ratio=source_width_ratio,
            fits=True,
            reason="reduced_font_fits" if reduced else "preferred_font_fits",
            quality_flags=flags,
        )

    return TableFitDecision(
        block_id=block_id,
        container=container,
        preferred_font_size=preferred_font_size,
        minimum_font_size=effective_minimum,
        selected_font_size=effective_minimum,
        available_width=available_width,
        required_width=last_required_width,
        column_widths=tuple(last_widths),
        source_width_ratio=source_width_ratio,
        fits=False,
        reason="minimum_font_unresolved",
        quality_flags=(f"table_fit_unresolved:{block_id}:{container}",),
    )


def _column_metrics(table: HtmlTable) -> tuple[list[float], list[float]]:
    minimum_units = [1.0] * table.max_columns
    content_weights = [1.0] * table.max_columns
    explicit_weights = [0.0] * table.max_columns
    for start, cell in _iter_logical_cells(table):
        span = min(cell.colspan, table.max_columns - start)
        if span <= 0:
            continue
        text = cell.text.strip()
        unbreakable = max(_unbreakable_units(text), 1.0) / span
        content = min(max(_display_units(text), unbreakable), MAX_CONTENT_WEIGHT_UNITS) / span
        for column in range(start, start + span):
            minimum_units[column] = max(minimum_units[column], unbreakable)
            content_weights[column] = max(content_weights[column], content)
            if cell.width_hint is not None:
                explicit_weights[column] = max(explicit_weights[column], cell.width_hint / span)
    if any(explicit_weights):
        content_weights = [explicit or content for explicit, content in zip(explicit_weights, content_weights, strict=True)]
    return minimum_units, content_weights


def _iter_logical_cells(table: HtmlTable) -> Iterator[tuple[int, HtmlCell]]:
    occupied_until: dict[int, int] = {}
    for row_index, row in enumerate(table.rows):
        column = 0
        for cell in row:
            while occupied_until.get(column, -1) >= row_index:
                column += 1
            yield column, cell
            if cell.rowspan > 1:
                for covered in range(column, column + cell.colspan):
                    occupied_until[covered] = row_index + cell.rowspan - 1
            column += cell.colspan


def _font_candidates(preferred: float, minimum: float) -> list[float]:
    candidates: list[float] = []
    current = preferred
    while current > minimum:
        candidates.append(round(current, 2))
        current -= FONT_STEP
    if not candidates or candidates[-1] != minimum:
        candidates.append(minimum)
    return candidates


def _widths_for_font(
    minimum_units: list[float],
    content_weights: list[float],
    available_width: int,
    font_size: float,
) -> tuple[list[int], int, bool]:
    minimum_widths = [
        max(int((units * font_size * 0.55 + CELL_HORIZONTAL_PADDING_PT) * EMU_PER_POINT), 1)
        for units in minimum_units
    ]
    required_width = sum(minimum_widths)
    fits = required_width <= available_width
    if not fits:
        return _scaled_widths(minimum_widths, available_width), required_width, False

    remaining = available_width - required_width
    total_weight = sum(content_weights) or float(len(content_weights))
    widths = [
        minimum_width + int(remaining * weight / total_weight)
        for minimum_width, weight in zip(minimum_widths, content_weights, strict=True)
    ]
    widths[-1] += available_width - sum(widths)
    return widths, required_width, True


def _scaled_widths(widths: list[int], available_width: int) -> list[int]:
    total = sum(widths) or 1
    scaled = [max(int(available_width * width / total), 1) for width in widths]
    scaled[-1] += available_width - sum(scaled)
    return scaled


def _display_units(text: str) -> float:
    return sum(_character_units(character) for character in text)


def _unbreakable_units(text: str) -> float:
    text = insert_engineering_token_breaks(text)
    longest = 0.0
    segment: list[str] = []
    for character in text:
        if character.isspace() or _is_cjk(character):
            longest = max(longest, _segment_unbreakable_units("".join(segment)))
            segment.clear()
            if _is_cjk(character):
                longest = max(longest, _character_units(character))
            continue
        segment.append(character)
    return max(longest, _segment_unbreakable_units("".join(segment)))


def _segment_unbreakable_units(segment: str) -> float:
    """只在左括号前拆分连续工程 token，右侧标点保持在同一片段。"""

    longest = 0.0
    current = 0.0
    for character in segment:
        if character in "([（【":
            longest = max(longest, current)
            current = _character_units(character)
            continue
        current += _character_units(character)
    return max(longest, current)


def insert_engineering_token_breaks(text: str) -> str:
    """在连字符编号与紧邻说明词之间补可见空格，给 Word 稳定换行点。"""

    return ENGINEERING_CODE_DESCRIPTION_RE.sub(r"\1\2 ", text)


def _character_units(character: str) -> float:
    if _is_cjk(character):
        return 2.0
    if re.match(r"\w", character, re.UNICODE):
        return 1.0
    return 0.7


def _is_cjk(character: str) -> bool:
    return unicodedata.east_asian_width(character) in {"W", "F"}
