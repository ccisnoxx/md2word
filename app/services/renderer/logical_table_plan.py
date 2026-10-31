"""逻辑表输出计划的唯一 owner；源账本与当前 HTML 渲染视图保持分离。"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any

from app.services.document_ir.integrity import is_visible_body_block
from app.services.document_ir.logical_table_group import VERSION as LOGICAL_TABLE_GROUPS_VERSION, validate_logical_table_groups
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, LogicalTableGroup, TableFragment
from app.services.document_ir.table_annotations import is_table_context_annotation
from app.services.renderer.layout_plan import LayoutPage, LayoutPlan, LayoutRegion, split_two_col_blocks
from app.services.renderer.table_renderer import TableRenderError, iter_grid_rows
from app.services.renderer.text_renderer import CAPTION_RE
from app.services.tables.grid_builder import RenderTableBuildResult, build_render_table_grid
from app.services.tables.html_normalizer import (
    MAX_CELLS, MAX_GRID_SLOTS, MAX_OCCUPANCY_CHECKS, MAX_RAW_HTML_BYTES, TableBuildError,
)
from app.services.tables.models import TableGrid, canonical_sha256


TABLE_RENDERING_VERSION = "table-rendering/v1"
TABLE_RENDERING_POLICY = "logical-table-renderer/v1"
QUALITY_BLOCKERS = frozenset({
    "table_fragment_missing", "table_render_layout_incompatible",
})
QUALITY_WARNINGS = frozenset({"table_render_header_not_removed", "table_render_continuation_uncertain"})
SAFE_COUNT_KEYS = (
    "source_table_block_count", "output_table_count", "consumed_block_count", "fragment_count",
    "empty_fragment_count", "missing_fragment_count",
)
_CONTINUED = re.compile(r"[（(]\s*(?:continued|续表?)\s*[）)]|\bcontinued\b|(?<![\u3400-\u9fff])续表?(?![\u3400-\u9fff])", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FragmentRenderPlan:
    """一条真实来源对应一条输出记录；零行和共享表头不伪造新 Word 行。"""

    source: TableFragment
    block_index: int | None
    render: RenderTableBuildResult | None
    removed_header_rows: int
    output_start: int
    output_end: int
    bookmark: str | None
    bookmark_id: int | None

    @property
    def status(self) -> str:
        if self.render is None:
            return self.source.html_state
        return "header_only" if self.output_start == self.output_end else "rendered"


@dataclass(frozen=True, slots=True)
class TableRenderUnit:
    """一个输出原生表，包含可由实际 OOXML 核对的来源覆盖与行区间。"""

    key: str
    logical_group_id: str
    anchor_block_index: int
    fragments: tuple[FragmentRenderPlan, ...]
    is_group_primary: bool
    columns: int
    rows: int
    header_rows: int
    captions: tuple[str, ...]
    footnotes: tuple[str, ...]
    blocking_quality_flags: tuple[str, ...]
    warning_flags: tuple[str, ...]
    continuation_diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LogicalTableRenderPlan:
    """调用局部计划；renderer 和 evidence 从相同输入独立重建，不存实例缓存。"""

    units: tuple[TableRenderUnit, ...]
    consumed_block_ids: frozenset[str]
    input_sha256: str

    def output_pages(self, layout: LayoutPlan) -> list[LayoutPage]:
        """仅输出账跳过续片；原 LayoutPlan 仍完整保留所有来源块。"""
        pages = []
        for page in layout.pages:
            regions = [LayoutRegion(region.kind, [block for block in region.blocks
                       if block.id not in self.consumed_block_ids]) for region in page.regions]
            regions = [region for region in regions if region.blocks]
            consumed_page = any(block.id in self.consumed_block_ids for region in page.regions for block in region.blocks)
            empty_source_page = any(fragment.render is None and fragment.source.source_span.page_index == page.index
                                    for unit in self.units for fragment in unit.fragments)
            if regions or not (consumed_page or empty_source_page):
                pages.append(replace(page, regions=regions))
        return pages


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _header_prefix(grid: TableGrid, *, block_index: int) -> int:
    """只承认从首行开始、整行显式 th 且 span 闭合的连续前缀。"""
    count = 0
    for row, owners in iter_grid_rows(grid, block_index=block_index):
        if (not owners or any(not cell.is_header for cell in owners)
                or sum(cell.colspan for cell in owners) != grid.columns):
            break
        count = row + 1
    if any(cell.row < count < cell.row + cell.rowspan for cell in grid.cells):
        return 0
    return count


def _header_signature(grid: TableGrid, count: int) -> list[Any] | None:
    if count <= 0 or count > grid.rows or any(cell.row < count < cell.row + cell.rowspan for cell in grid.cells):
        return None
    # 保守使用完整语义 runs；不会把不同单位、大小写、脚本、公式或 marks 当作重复。
    return [[cell.row, cell.column, cell.rowspan, cell.colspan, cell.is_header,
             [[run.type, run.target if run.target is not None else run.source, run.bold, run.italic]
              for run in cell.runs]] for cell in grid.cells if cell.row < count]


def _continuation_caption(text: str, primary: tuple[str, ...]) -> bool:
    if text in primary:
        return True
    if is_table_context_annotation(text):
        return False
    match = CAPTION_RE.match(text)
    if match is None or match.group("label").lower() not in {"table", "表"}:
        return False
    tail = _CONTINUED.sub("", match.group("tail")).strip(" .．:：-–—")
    for caption in primary:
        first = CAPTION_RE.match(caption)
        if (first is not None and first.group("label").lower() in {"table", "表"}
                and int(first.group("number")) == int(match.group("number"))
                and (not tail or tail == first.group("tail").strip(" .．:：-–—"))):
            return True
    return False


def _layout_positions(layout: LayoutPlan) -> dict[int, tuple[int, tuple[Any, ...]]]:
    """复用正式双栏分流顺序；位置账不按 source 数组邻接猜测。"""
    result = {}
    position = 0
    for page in layout.pages:
        landscape = bool(page.width and page.height and page.width > page.height)
        for region in page.regions:
            streams = (split_two_col_blocks(region.blocks) if region.kind == "two_col" else (region.blocks,))
            for side, stream in enumerate(streams):
                for block in stream:
                    if is_visible_body_block(block):
                        result[id(block)] = (position, (landscape, region.kind, side))
                        position += 1
    return result


def _build_current(block: DocumentIRBlock, index: int) -> RenderTableBuildResult:
    try:
        result = build_render_table_grid(block, block_index=index)
    except TableBuildError as error:
        raise TableRenderError(error.code, block_index=index) from error
    if (result.grid.rows <= 0 or result.grid.columns <= 0 or any(
            item.code in {"table_span_invalid", "table_span_collision", "table_span_out_of_bounds"}
            for item in result.diagnostics)):
        raise TableRenderError("table_render_geometry", block_index=index)
    for _row in iter_grid_rows(result.grid, block_index=index):
        pass
    return result


def _build_group_current(
    group: LogicalTableGroup, indices: dict[str, int], document: DocumentIR, placeholder_ids: set[str],
) -> list[tuple[TableFragment, int, RenderTableBuildResult]]:
    """按删除前的完整组递增计费，超限即停止，不先持有超预算的整组 Grid。"""
    members = []
    html_bytes = cells = slots = checks = 0
    for fragment in group.fragments:
        if fragment.block_id is None or fragment.fragment_id in placeholder_ids:
            continue
        index = indices[fragment.block_id]
        try:
            html_bytes += len((document.blocks[index].html or "").encode("utf-8"))
        except UnicodeEncodeError:
            raise TableRenderError("table_html_encoding", block_index=index) from None
        if html_bytes > MAX_RAW_HTML_BYTES:
            raise TableRenderError("table_build_limit", block_index=index)
        current = _build_current(document.blocks[index], index)
        cells += len(current.grid.cells)
        slots += current.grid.rows * current.grid.columns
        checks += sum(cell.rowspan * cell.colspan for cell in current.grid.cells)
        if cells > MAX_CELLS or slots > MAX_GRID_SLOTS or checks > MAX_OCCUPANCY_CHECKS:
            raise TableRenderError("table_build_limit", block_index=index)
        members.append((fragment, index, current))
    return members


def build_logical_table_render_plan(document: DocumentIR, layout: LayoutPlan) -> LogicalTableRenderPlan | None:
    """仅消费经过 IR owner 复核的组合同；旧无组 IR 不改变输出。"""
    validate_logical_table_groups(document)
    if document.metadata.logical_table_groups_version is None:
        return None
    if document.metadata.logical_table_groups_version != LOGICAL_TABLE_GROUPS_VERSION:
        raise ValueError("逻辑表格来源合同无效：table_render_group_version。")
    from app.services.document_ir.table_placeholder import decode_placeholders
    placeholder_ids = {item.fragment_id for item in decode_placeholders(document)}
    indices = {block.id: index for index, block in enumerate(document.blocks)}
    positions = _layout_positions(layout)
    units: list[TableRenderUnit] = []
    consumed: set[str] = set()
    bookmark_index = 1_000_000
    for group in document.metadata.logical_table_groups:
        present = _build_group_current(group, indices, document, placeholder_ids)
        # 页边装饰不属于正文输出；其源表也不能被正文组消费。
        if not any(is_visible_body_block(document.blocks[index]) for _, index, _ in present):
            continue
        missing = any(fragment.html_state != "present" for fragment in group.fragments)
        diagnostics = tuple(dict.fromkeys(item.reason for item in group.diagnostics))
        blockers = (["table_fragment_missing"] if missing else [])
        compatible = not missing or all(fragment.html_state == "present" or fragment.fragment_id in placeholder_ids
                                        for fragment in group.fragments)
        source_members = [fragment.fragment_id for fragment, _, _ in present]
        verified = {(relation.from_fragment_id, relation.to_fragment_id) for relation in group.continuation_relations
                    if relation.kind == "verified_continuation"}
        if any(pair not in verified for pair in zip(source_members, source_members[1:])):
            compatible = False
        if len(present) > 1:
            layout_compatible = True
            locations = [positions.get(id(document.blocks[index])) for _, index, _ in present]
            if (any(location is None for location in locations) or
                    len({location[1] for location in locations if location is not None}) != 1 or
                    [location[0] for location in locations if location is not None] !=
                    list(range(locations[0][0], locations[0][0] + len(present))) or
                    len({current.grid.columns for _, _, current in present}) != 1):
                layout_compatible = False
            first_captions = _unique(document.blocks[present[0][1]].captions)
            final_notes = set(_unique(document.blocks[present[-1][1]].footnotes))
            if (any(not _continuation_caption(caption, first_captions) for _, index, _ in present[1:]
                    for caption in _unique(document.blocks[index].captions)) or
                    any(set(_unique(document.blocks[index].footnotes)) - final_notes for _, index, _ in present[:-1])):
                layout_compatible = False
            if not layout_compatible:
                compatible = False
                blockers.append("table_render_layout_incompatible")
        batches = [present] if compatible else [[member] for member in present]
        for batch in batches:
            anchor_index = batch[0][1]
            first_grid = batch[0][2].grid
            header_rows = _header_prefix(first_grid, block_index=anchor_index)
            # 实物锚点绑定当前输入和布局，不能拿同一源账本的旧译文 DOCX 冒充本次结果。
            key = "md2word-table-" + canonical_sha256([
                TABLE_RENDERING_POLICY, group.logical_group_id,
                [[fragment.fragment_id, current.input_sha256, document.blocks[index].captions,
                  document.blocks[index].footnotes, positions.get(id(document.blocks[index])),
                  document.blocks[index].layout.model_dump(mode="json") if document.blocks[index].layout else None]
                 for fragment, index, current in batch], blockers, diagnostics,
            ])[:32]
            fragment_plans = []
            warnings = ["table_render_continuation_uncertain"] if diagnostics else []
            offset = 0
            main_bookmark = None
            main_bookmark_id = None
            for member_index, (fragment, index, current) in enumerate(batch):
                removed = 0
                if member_index:
                    hint = fragment.repeated_header_hint
                    if (hint is not None and hint.row_count == header_rows and
                            _header_signature(current.grid, hint.row_count) == _header_signature(first_grid, header_rows)
                            and header_rows > 0):
                        removed = header_rows
                    else:
                        warnings.append("table_render_header_not_removed")
                end = offset + current.grid.rows - removed
                if end > offset:
                    bookmark = "_md2tf_" + canonical_sha256([TABLE_RENDERING_POLICY, fragment.fragment_id, current.input_sha256])[:30]
                    bookmark_id = bookmark_index
                    bookmark_index += 1
                    if member_index == 0:
                        main_bookmark, main_bookmark_id = bookmark, bookmark_id
                else:
                    bookmark, bookmark_id = main_bookmark, main_bookmark_id
                fragment_plans.append(FragmentRenderPlan(fragment, index, current, removed, offset, end,
                                                         bookmark, bookmark_id))
                offset = end
            owner_ids = {fragment.block_id for fragment, _, _ in batch}
            for fragment in group.fragments:
                if fragment.block_id is None and fragment.render_owner_block_id in owner_ids:
                    fragment_plans.append(FragmentRenderPlan(fragment, None, None, 0, 0, 0, None, None))
            fragment_plans.sort(key=lambda fragment: fragment.source.source_span.source_index)
            units.append(TableRenderUnit(
                key, group.logical_group_id, anchor_index, tuple(fragment_plans), anchor_index == present[0][1],
                first_grid.columns, offset,
                header_rows, _unique(document.blocks[anchor_index].captions),
                _unique(document.blocks[batch[-1][1]].footnotes), tuple(dict.fromkeys(blockers)),
                tuple(dict.fromkeys(warnings)), diagnostics,
            ))
            consumed.update(document.blocks[index].id for _, index, _ in batch[1:])
    units.sort(key=lambda unit: positions.get(id(document.blocks[unit.anchor_block_index]), (len(positions), ()))[0])
    fingerprint = canonical_sha256([TABLE_RENDERING_POLICY, [
        [index, block.id, block.html, block.captions, block.footnotes,
         block.layout.model_dump(mode="json") if block.layout else None]
        for index, block in enumerate(document.blocks) if block.type == "table"
    ], [[unit.key, [fragment.source.fragment_id for fragment in unit.fragments]] for unit in units]])
    return LogicalTableRenderPlan(tuple(units), frozenset(consumed), fingerprint)


def build_content_table_plan(document: DocumentIR, layout: LayoutPlan) -> LogicalTableRenderPlan:
    """v2 的所有原生表共用源 grid；历史无组只建立内存 render-view 身份。"""
    original = build_logical_table_render_plan(document, layout)
    units = list(original.units) if original else []
    covered = {fragment.source.block_id for unit in units for fragment in unit.fragments}
    for index, block in enumerate(document.blocks):
        if block.type != "table" or block.id in covered or not is_visible_body_block(block) or not (block.html or "").strip():
            continue
        current = _build_current(block, index)
        source = current.grid.source_fragments[0]
        fragment = TableFragment(fragment_id=source.fragment_id, source_span=source.source_span,
            block_id=block.id, render_owner_block_id=block.id, raw_fragment={"html": block.html},
            raw_html_pointer="/html", html_state="present", raw_html_sha256=source.raw_html_sha256)
        bookmark = "_md2tf_" + canonical_sha256([TABLE_RENDERING_POLICY, fragment.fragment_id, current.input_sha256])[:30]
        units.append(TableRenderUnit("md2word-table-" + canonical_sha256(["standalone/v2", current.input_sha256])[:32],
            current.grid.table_id, index,
            (FragmentRenderPlan(fragment, index, current, 0, 0, current.grid.rows, bookmark, None),),
            True, current.grid.columns, current.grid.rows, _header_prefix(current.grid, block_index=index),
            _unique(block.captions), _unique(block.footnotes), (), (), ()))
    positions = _layout_positions(layout)
    units.sort(key=lambda unit: positions.get(id(document.blocks[unit.anchor_block_index]), (len(positions), ()))[0])
    return LogicalTableRenderPlan(tuple(units), original.consumed_block_ids if original else frozenset(),
        canonical_sha256(["table-render-input/v2", original.input_sha256 if original else None,
                          [[unit.key, [fragment.render.input_sha256 if fragment.render else None
                                       for fragment in unit.fragments]] for unit in units]]))


def table_unit_contracts(document: DocumentIR, plan: LogicalTableRenderPlan):
    """逐源记录行与注释选择；复用原 header/续题裁决，不删除 consumed 成员。"""
    from app.services.renderer.render_plan import TableAnnotationPlan, TableFragmentPlan, TableUnitPlan
    result = []
    for unit in plan.units:
        members = list(dict.fromkeys(fragment.source.render_owner_block_id for fragment in unit.fragments))
        anchor = document.blocks[unit.anchor_block_index]
        rendered_members = [document.blocks[fragment.block_index] for fragment in unit.fragments if fragment.render is not None]
        note_owner = rendered_members[-1]
        selected = {}
        for field, owner, values in (("captions", anchor, unit.captions), ("footnotes", note_owner, unit.footnotes)):
            for value in values:
                index = next(i for i, text in enumerate(getattr(owner, field)) if text.strip() == value)
                selected[field, value] = (owner.id, field, index)
        annotations = []
        for block in document.blocks:
            if block.id not in members:
                continue
            for field in ("captions", "footnotes"):
                for item_index, raw in enumerate(getattr(block, field)):
                    text = raw.strip()
                    if not text:
                        continue
                    representative = selected.get((field, text))
                    if representative is None and field == "captions" and _continuation_caption(text, unit.captions):
                        candidates = [selected[field, value] for value in unit.captions
                                      if _continuation_caption(text, (value,))]
                        if len(candidates) != 1:
                            raise ValueError("ir_render_evidence:target_mismatch")
                        representative = candidates[0]
                    if representative is None:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    own = representative == (block.id, field, item_index)
                    annotations.append(TableAnnotationPlan(block_id=block.id, field=field, item_index=item_index,
                        role="note" if field == "footnotes" else "context" if is_table_context_annotation(text) else "caption",
                        disposition="rendered" if own else "coalesced",
                        representative_block_id=None if own else representative[0],
                        representative_field=None if own else representative[1],
                        representative_item_index=None if own else representative[2],
                        reason=None if own else "table_annotation_coalesced"))
        fragments = []
        primary_scope = None
        for fragment in unit.fragments:
            scope = ("table-scope:" + canonical_sha256([unit.key, fragment.source.fragment_id])
                     if fragment.status == "rendered" else None)
            if primary_scope is None and scope is not None:
                primary_scope = scope
            fragments.append(TableFragmentPlan(fragment_id=fragment.source.fragment_id,
                block_id=fragment.source.block_id, render_owner_block_id=fragment.source.render_owner_block_id,
                render_input_sha256=fragment.render.input_sha256 if fragment.render else None,
                render_fragment_id=fragment.render.grid.source_fragments[0].fragment_id if fragment.render else None,
                status=fragment.status, source_rows=[0, fragment.render.grid.rows if fragment.render else 0],
                retained_source_rows=[fragment.removed_header_rows, fragment.render.grid.rows] if fragment.render else [0, 0],
                output_rows=[fragment.output_start, fragment.output_end],
                removed_header_rows=[0, fragment.removed_header_rows] if fragment.removed_header_rows else None,
                shared_header_rows=[0, fragment.removed_header_rows] if fragment.removed_header_rows else None,
                content_scope_id=scope, repeated_header_ref=primary_scope if fragment.removed_header_rows else None))
        result.append(TableUnitPlan(unit_id=unit.key, logical_group_id=unit.logical_group_id,
            anchor_block_id=anchor.id, member_block_ids=members, fragments=fragments, annotations=annotations))
    return result
