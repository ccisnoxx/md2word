"""按真实来源顺序构建临时稀疏占位，保留全部 cell 与中性结构诊断。"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Literal

from app.services.document_ir.models import DocumentIRBlock, LogicalTableGroup, SourceSpan
from app.services.tables.html_normalizer import (
    MAX_CELLS, MAX_GRID_SLOTS, MAX_OCCUPANCY_CHECKS, MAX_RAW_HTML_BYTES, NORMALIZER_VERSION,
    NormalizedTableFragment, TableBuildError, TableDiagnostic, normalize_table_fragment,
)
from app.services.tables.models import (
    TableCell, TableGrid, TableSourceFragment, canonical_sha256, cell_content_sha256, make_cell_id, raw_html_set_sha256,
)


@dataclass(frozen=True, slots=True)
class NormalizedFragmentHTML:
    fragment_id: str
    normalized_html: str | None


@dataclass(frozen=True, slots=True)
class TableBuildResult:
    normalizer_version: str
    grid: TableGrid
    normalized_fragments: tuple[NormalizedFragmentHTML, ...]
    diagnostics: tuple[TableDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class RenderTableBuildResult:
    """仅供当前 IR 渲染的内存结果；不是 MinerU 来源构建结果或可登记 Artifact。"""

    input_kind: Literal["document_ir_render_view"]
    block_id: str
    input_sha256: str
    normalizer_version: str
    grid: TableGrid
    diagnostics: tuple[TableDiagnostic, ...]


def build_render_table_grid(block: DocumentIRBlock, *, block_index: int) -> RenderTableBuildResult:
    """从当前 HTML 和真实数组位置投影，使用独立身份域且不读取或改写源账本。"""
    if block.type != "table" or type(block_index) is not int or block_index < 0:
        raise ValueError("表格渲染输入无效：table_render_input。")
    raw = block.html
    # 先检查 HTML 预算，避免 canonical 封套为超限输入再分配大副本。
    try:
        raw_bytes = raw.encode("utf-8") if raw is not None else None
        if raw_bytes is not None and len(raw_bytes) > MAX_RAW_HTML_BYTES:
            raise TableBuildError("table_build_limit", fragment_id="")
        pointer = f"/blocks/{block_index}"
        fingerprint = canonical_sha256(["document-ir-table-render-input/v1", block.id, pointer, raw])
    except UnicodeEncodeError:
        raise TableBuildError("table_html_encoding", fragment_id="") from None
    fragment_id = "table-fragment:" + canonical_sha256(["document-ir-table-render-fragment/v1", fingerprint])
    fragment = TableSourceFragment(
        fragment_id=fragment_id,
        source_span=SourceSpan(json_pointer=pointer, source_index=block_index, source_type="table"),
        html_state="missing" if raw is None else "present" if raw.strip() else "empty",
        raw_html=raw, raw_html_sha256=hashlib.sha256(raw_bytes).hexdigest() if raw_bytes is not None else None,
    )
    del raw_bytes
    built = _build_table_grid(
        [fragment], table_id="logical-table:" + canonical_sha256(["document-ir-table-render-table/v1", fingerprint]),
        source_content_sha256=fingerprint, render_view=True,
    )
    return RenderTableBuildResult("document_ir_render_view", block.id, fingerprint,
                                  built.normalizer_version, built.grid, built.diagnostics)


def build_table_grid(group: LogicalTableGroup, *, source_content_sha256: str) -> TableBuildResult:
    """只接受已校验逻辑组；不重分组、不修复技术文字、不回写上游。"""
    fragments = [TableSourceFragment(
        fragment_id=fragment.fragment_id, source_span=fragment.source_span,
        html_state=fragment.html_state, raw_html=fragment.raw_html,
        raw_html_sha256=fragment.raw_html_sha256, repeated_header_hint=fragment.repeated_header_hint,
    ) for fragment in group.fragments]
    return _build_table_grid(fragments, table_id=group.logical_group_id,
                             source_content_sha256=source_content_sha256)


def _build_table_grid(fragments: list[TableSourceFragment], *, table_id: str,
                      source_content_sha256: str, render_view: bool = False) -> TableBuildResult:
    """共用占位和诊断；仅渲染视图选择 Word 既有脚本优先级，源入口保持默认。"""
    # 先复用模型验证身份、来源顺序及 hash；损坏输入不进入解析和占位分配。
    root = dict(schema_version="canonical-table/v1", table_id=table_id,
                source_content_sha256=source_content_sha256, raw_html_sha256=raw_html_set_sha256(fragments),
                source_fragments=fragments)
    TableGrid(**root, rows=0, columns=0, cells=[])
    normalized: list[NormalizedTableFragment] = []
    cell_count = 0
    row_count = 0
    for fragment in fragments:
        parsed = (normalize_table_fragment(fragment, render_script_precedence=True)
                  if render_view else normalize_table_fragment(fragment))
        cell_count += sum(len(row.cells) for row in parsed.rows)
        row_count += len(parsed.rows)
        if cell_count > MAX_CELLS:
            raise TableBuildError("table_build_limit", fragment_id=fragment.fragment_id)
        normalized.append(parsed)

    cells: list[TableCell] = []
    diagnostics: list[TableDiagnostic] = []
    header_rows: list[int] = []
    occupied_rows: list[tuple[str, int, dict[int, list[str]]]] = []
    offset = 0
    columns = 0
    checks = 0
    for fragment in normalized:
        diagnostics.extend(replace(diagnostic, row=offset + diagnostic.source_row_index)
                           if diagnostic.source_row_index is not None else diagnostic
                           for diagnostic in fragment.diagnostics)
        local_rows = len(fragment.rows)
        occupancy: dict[int, dict[int, list[str]]] = {}
        headers: dict[str, bool] = {}
        for source_row, row in enumerate(fragment.rows):
            cursor = 0
            for source_cell in row.cells:
                row_slots = occupancy.setdefault(source_row, {})
                while cursor in row_slots:
                    checks += 1
                    if checks > MAX_OCCUPANCY_CHECKS:
                        raise TableBuildError("table_build_limit", fragment_id=fragment.fragment_id,
                                              source_row_index=source_row, source_cell_index=source_cell.source_cell_index)
                    cursor += 1
                end_column = cursor + source_cell.colspan
                columns = max(columns, end_column)
                visible_end = min(local_rows, source_row + source_cell.rowspan)
                rectangle_checks = (visible_end - source_row) * source_cell.colspan
                # 只为片内真实行分配占位；声明的越界 span 原值留在 cell 中。
                if (row_count * columns > MAX_GRID_SLOTS or
                        checks + rectangle_checks > MAX_OCCUPANCY_CHECKS):
                    raise TableBuildError("table_build_limit", fragment_id=fragment.fragment_id,
                                          source_row_index=source_row, source_cell_index=source_cell.source_cell_index)
                checks += rectangle_checks
                identity = make_cell_id(fragment.fragment_id, source_row, source_cell.source_cell_index)
                cell = TableCell(
                    id=identity, source_fragment_id=fragment.fragment_id, source_row_index=source_row,
                    source_cell_index=source_cell.source_cell_index, row=offset + source_row, column=cursor,
                    rowspan=source_cell.rowspan, colspan=source_cell.colspan, is_header=source_cell.is_header,
                    runs=list(source_cell.runs), content_sha256=cell_content_sha256(source_cell.runs),
                )
                cells.append(cell)
                headers[identity] = cell.is_header
                location = dict(fragment_id=fragment.fragment_id, cell_id=identity,
                                source_row_index=source_row, source_cell_index=source_cell.source_cell_index)
                if source_row + cell.rowspan > local_rows:
                    diagnostics.append(TableDiagnostic("table_span_out_of_bounds", **location,
                                                       row=cell.row, column=cell.column))
                conflicts: set[str] = set()
                for occupied_row in range(source_row, visible_end):
                    slots = occupancy.setdefault(occupied_row, {})
                    for column in range(cursor, end_column):
                        owners = slots.setdefault(column, [])
                        for other in owners:
                            checks += 1
                            if checks > MAX_OCCUPANCY_CHECKS:
                                raise TableBuildError("table_build_limit", fragment_id=fragment.fragment_id,
                                                      source_row_index=source_row,
                                                      source_cell_index=source_cell.source_cell_index)
                            if other not in conflicts:
                                diagnostics.append(TableDiagnostic("table_span_collision", **location,
                                                                   related_cell_id=other, row=offset + occupied_row,
                                                                   column=column))
                                conflicts.add(other)
                        owners.append(identity)
                cursor = end_column
            row_slots = occupancy.get(source_row, {})
            if (row.cells and all(cell.is_header for cell in row.cells) and
                    all(headers[owner] for owners in row_slots.values() for owner in owners)):
                header_rows.append(offset + source_row)
            occupied_rows.append((fragment.fragment_id, source_row, row_slots))
        offset += local_rows

    # 全局列数确定后只扫描已有列键，以半开区间记录缺口，不构造稠密空矩阵。
    for global_row, (fragment_id, source_row, slots) in enumerate(occupied_rows):
        cursor = 0
        for column in sorted(slots):
            if column > cursor:
                diagnostics.append(TableDiagnostic("table_grid_hole", fragment_id,
                                                   source_row_index=source_row, row=global_row,
                                                   column=cursor, end_column=column))
            cursor = column + 1
        if cursor < columns:
            diagnostics.append(TableDiagnostic("table_grid_hole", fragment_id,
                                               source_row_index=source_row, row=global_row,
                                               column=cursor, end_column=columns))
    grid = TableGrid(**root, rows=row_count, columns=columns, cells=cells, header_rows=header_rows)
    return TableBuildResult(NORMALIZER_VERSION, grid, tuple(
        NormalizedFragmentHTML(fragment.fragment_id, fragment.normalized_html) for fragment in normalized
    ), tuple(diagnostics))
