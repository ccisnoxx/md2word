"""从既有网格读取坐标，以原 DOM 文本构造输入上下文，不拥有另一套表格网格。"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.domains.translation.models import TranslationTableContext, TranslationTextItem
from app.domains.translation.protected_tokens import EncodedTokenBatch, encode
from app.services.document_ir.models import DocumentIR
from app.services.tables.grid_builder import build_render_table_grid
from app.services.tables.html_normalizer import TableBuildError


MAX_TABLE_CONTEXT_CHARS = 1024


class TableContextMappingError(ValueError):
    """原 DOM 与共享网格不能可靠关联时的安全错误。"""

    def __init__(self) -> None:
        super().__init__("表格上下文无法与原始单元格可靠对应。")


def context_char_count(context: TranslationTableContext) -> int:
    """预算计入独立 context JSON 值的字符，包括字段、坐标和 JSON 空白。"""
    return len(json.dumps(context.to_payload(), ensure_ascii=False, indent=2))


def _context_cell_text(cell: Tag) -> str:
    """只在明确换行或块级边界分隔文字，普通内联节点仍连续，数学子树整体排除。"""
    projected = deepcopy(cell)
    for equation in projected.find_all("eq"):
        equation.decompose()
    for boundary in projected.find_all(["br", "hr", "p", "div", "li", "ul", "ol", "dl", "dt", "dd", "blockquote", "pre"]):
        if boundary.name in {"br", "hr"}:
            boundary.replace_with("\n")
        else:
            boundary.insert_before("\n")
            boundary.insert_after("\n")
    return "".join(str(node) for node in projected.find_all(string=True)).strip()


class TableContextBuilder:
    """保留原非空节点索引，只投影明确表头与同行覆盖格，不推测语义分组。"""

    def build(self, document_ir: DocumentIR, items: tuple[TranslationTextItem, ...]) -> dict[str, TranslationTableContext]:
        requested = {item.id for item in items}
        contexts: dict[str, TranslationTableContext] = {}
        for block_index, block in enumerate(document_ir.blocks):
            if block.type != "table" or not block.html or not any(
                item_id.startswith(f"{block.id}.html.") for item_id in requested
            ):
                continue
            soup = BeautifulSoup(block.html, "html.parser")
            # caption 等非单元格正文仍走旧翻译路径；临时网格只读取格内内容。
            grid_soup = deepcopy(soup)
            outside_text = [node for node in grid_soup.find_all(string=True)
                            if str(node).strip() and node.find_parent(["td", "th"]) is None]
            for node in outside_text:
                node.extract()
            grid_block = block.model_copy(update={"html": str(grid_soup)}) if outside_text else block
            try:
                built = build_render_table_grid(grid_block, block_index=block_index)
            except TableBuildError:
                raise TableContextMappingError() from None
            # 两种 parser 的隐式闭合可能不同，不能按 zip 静默截断或改变原节点归属。
            rows = soup.find_all("tr")
            if len(rows) != built.grid.rows or any(row.find_parent("tr") is not None for row in rows):
                raise TableContextMappingError()
            source_cells = {}
            for row_index, row in enumerate(rows):
                for cell_index, cell in enumerate(row.find_all(["th", "td"])):
                    if cell.find_parent(["th", "td"]) is not None or cell.find_parent("tr") is not row:
                        raise TableContextMappingError()
                    source_cells[(row_index, cell_index)] = cell
            grid_cells = {(cell.source_row_index, cell.source_cell_index): cell for cell in built.grid.cells}
            if source_cells.keys() != grid_cells.keys():
                raise TableContextMappingError()
            by_dom_id = {id(source_cells[key]): grid_cells[key] for key in grid_cells}
            scopes = {cell.id: (source_cells[key].get("scope") or "").lower() for key, cell in grid_cells.items()}
            column_headers = {
                cell.id for key, cell in grid_cells.items()
                if cell.is_header and scopes[cell.id] not in {"row", "rowgroup"}
                and (cell.row in built.grid.header_rows or scopes[cell.id] in {"col", "colgroup"})
            }
            texts = {
                grid_cells[key].id: _context_cell_text(cell)
                for key, cell in source_cells.items()
            }
            text_index = 0
            for node in soup.find_all(string=True):
                if not str(node).strip():
                    continue
                item_id = f"{block.id}.html.{text_index:04d}"
                text_index += 1
                if item_id not in requested or node.find_parent("eq") is not None:
                    continue
                dom_cell = node.find_parent(["td", "th"])
                if dom_cell is None:
                    continue
                cell = by_dom_id.get(id(dom_cell))
                if cell is None:
                    raise TableContextMappingError()
                headers = tuple(texts[other.id] for other in built.grid.cells if (
                    other.id in column_headers and other.row < cell.row
                    and other.column < cell.column + cell.colspan
                    and cell.column < other.column + other.colspan and texts[other.id]
                ))
                parameters = tuple(texts[other.id] for other in built.grid.cells if (
                    other.id != cell.id and other.row <= cell.row < other.row + other.rowspan
                    and texts[other.id]
                ))
                contexts[item_id] = TranslationTableContext(
                    item_id=item_id, table_id=built.grid.table_id, row=cell.row, column=cell.column,
                    rowspan=cell.rowspan, colspan=cell.colspan, header_path=headers, row_parameters=parameters,
                )
        return contexts

    def encode_and_select(
        self, raw: dict[str, TranslationTableContext], encoded: EncodedTokenBatch, *, max_chars: int,
    ) -> tuple[TranslationTableContext, ...]:
        """先保护全部技术文字，再按每项剩余空间选择完整段；不截断任何占位符。"""
        selected = [raw[item.id] for item in encoded.items if item.id in raw]
        # dummy 只占用正文命名空间，既不发给 Provider，也不进入正文 ledger。
        fields = [TranslationTextItem("reserved", encoded.namespace)]
        for context in selected:
            for text in (*context.header_path, *context.row_parameters):
                fields.append(TranslationTextItem(str(len(fields)), text))
        protected = iter(encode(tuple(fields)).items[1:])
        body_lengths = {item.id: len(item.text) for item in encoded.items}
        result = []
        for context in selected:
            headers = tuple(next(protected).text for _ in context.header_path)
            parameters = tuple(next(protected).text for _ in context.row_parameters)
            limit = min(MAX_TABLE_CONTEXT_CHARS, max_chars - body_lengths[context.item_id])
            chosen = replace(context, header_path=(), row_parameters=(), truncated=bool(headers or parameters))
            omitted = False
            for field_name, segments in (("header_path", headers), ("row_parameters", parameters)):
                for segment in segments:
                    candidate = replace(chosen, **{field_name: (*getattr(chosen, field_name), segment)}, truncated=False)
                    if context_char_count(candidate) <= limit:
                        chosen = candidate
                    else:
                        omitted = True
            result.append(replace(chosen, truncated=omitted))
        return tuple(result)
