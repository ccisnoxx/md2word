from __future__ import annotations

# app/services/renderer/native_table_renderer.py: 按逻辑表格计划写入原生网格表格（单元格 run、合并几何、题注与末注归属）。

from dataclasses import dataclass
from html import escape
from typing import Any, Literal

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tc
from docx.shared import Emu, Pt, Twips
from docx.table import _Cell

from app.conversion.docx_rules.formula import MathSpan, content_math_spans, formula_block_span
from app.services.renderer.block_evidence import LocalTarget, paragraph_target
from app.services.renderer.table_renderer import (
    TableRenderError,
    iter_grid_rows,
    table_annotation_style,
    table_config_for_columns,
)
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.tables.models import CellRun


@dataclass(frozen=True, slots=True)
class NativeCellPart:
    """来源账与 writer 共用的确定 native 视图；offset 按该视图连续计算。"""

    kind: Literal["inline", "protected_token", "line_break", "formula"]
    source: str
    offset: int
    bold: bool
    italic: bool
    spans: tuple[MathSpan, ...]
    literal: str | None = None


def native_cell_parts(runs: list[CellRun]) -> tuple[NativeCellPart, ...]:
    """只恢复同 marks 的有序 run 流；保护 token、换行和强公式维持原分界。"""
    parts: list[NativeCellPart] = []
    pending: list[CellRun] = []
    offset = 0

    def flush():
        nonlocal offset
        if not pending:
            return
        first = pending[0]
        chunks = []
        for run in pending:
            value = escape(run.source, quote=False)
            if run.type in {"subscript", "superscript"}:
                tag = "sub" if run.type == "subscript" else "sup"
                chunks.append(f"<{tag}>{value}</{tag}>")
            else:
                chunks.append(run.source if run.type == "formula" else value)
        source = "".join(chunks)
        for enabled, tag in ((first.italic, "i"), (first.bold, "b")):
            if enabled:
                source = f"<{tag}>{source}</{tag}>"
        # typed script 与显式数学均完整登记；共享扫描器负责脚本 base 的整体绑定。
        spans = content_math_spans(source)
        parts.append(NativeCellPart("inline", source, offset, first.bold, first.italic, spans))
        offset += len(source)
        pending.clear()

    for run in runs:
        strong_formula = run.type == "formula" and not content_math_spans(run.source)
        if run.type in {"protected_token", "line_break"} or strong_formula:
            flush()
            source = "<br/>" if run.type == "line_break" else run.source if strong_formula else escape(run.source, quote=False)
            spans = (formula_block_span(run.source),) if strong_formula else ()
            parts.append(NativeCellPart("formula" if strong_formula else run.type, source, offset,
                run.bold, run.italic, spans, run.source))
            offset += len(source)
            continue
        if pending and (pending[0].bold, pending[0].italic) != (run.bold, run.italic):
            flush()
        pending.append(run)
    flush()
    return tuple(parts)



class WordNativeTableRendererMixin:
    """原生网格表格写入；表格创建、列宽、行标志与占位图由 WordTableRendererMixin 提供。"""

    def _append_grid_cell(self, tr: Any, table: Any, width: int, span: int,
                          *, merge: str | None = None) -> Any:
        """局部 _Cell 不触发 Table._cells 的全表代理重建；CT_Tc.new 自带必需 p。"""
        tc = CT_Tc.new()
        tr.append(tc)
        cell = _Cell(tc, table)
        cell.width = width
        if span > 1:
            tc.grid_span = span
        if merge is not None:
            tc.vMerge = merge
        return cell

    def _format_table_cell(self, cell: Any, is_header: bool, template_config: TemplateConfigPackage) -> None:
        """大小表共用外观配置；合并延续不写内容但继承 owner 的表头外观。"""
        paragraph = cell.paragraphs[0]
        self._apply_table_header_run_style(paragraph, is_header, template_config)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_header else WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        if is_header and template_config.table_style.header_fill:
            self._set_cell_fill(cell, template_config.table_style.header_fill)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def _fill_native_grid_runs(self, paragraph, runs, config, *, reference_bookmarks=None):
        """保留 native run 的脚本/保护边界，普通文字继续原 text owner 叶链。"""
        style = config.table_content
        self._apply_named_style(paragraph, style.word_style_name)
        self._apply_paragraph_style(paragraph, style)
        for part in native_cell_parts(runs):
            run_style = style.model_copy(update={"bold": part.bold or style.bold, "italic": part.italic or style.italic})
            if part.kind == "line_break":
                paragraph.add_run().add_break()
            elif part.kind == "protected_token":
                self._add_text_run(paragraph, part.literal, run_style, bold=bool(run_style.bold), italic=bool(run_style.italic),
                    reference_bookmarks=reference_bookmarks)
            elif part.kind == "formula":
                self._append_formula(paragraph, part.spans[0], run_style,
                    bold=bool(run_style.bold), italic=bool(run_style.italic), _native_marks=True,
                    _native_references=reference_bookmarks)
            else:
                self._render_mixed_math(paragraph, part.source, run_style, config.terminology,
                    reference_bookmarks, _native_literal=True, _spans=part.spans)

    def _append_native_rows(self, table, fragment, width, config, context):
        """每个来源 cell 写一次；垂直合并的延续只继承几何，不复制文字或公式。"""
        widths = [Twips(Emu(value).twips) for value in self._table_column_widths(fragment.render.grid.columns, width)]
        created = []
        for source_row, row_cells in iter_grid_rows(fragment.render.grid, block_index=fragment.block_index):
            if source_row < fragment.removed_header_rows:
                continue
            tr = OxmlElement("w:tr")
            table._tbl.append(tr)
            created.append(tr)
            properties = tr.get_or_add_trPr()
            self._ensure_row_flag(properties, "w:cantSplit")
            cursor = 0
            for owner in row_cells:
                while cursor < owner.column:
                    self._append_grid_cell(tr, table, widths[cursor], 1)
                    cursor += 1
                continuation = owner.row < source_row
                cell = self._append_grid_cell(tr, table, sum(widths[owner.column:owner.column + owner.colspan]),
                    owner.colspan, merge="continue" if continuation else "restart" if owner.rowspan > 1 else None)
                header = owner.row == 0 or owner.is_header
                if not continuation:
                    self._set_formula_source(table, fragment.source.block_id,
                        f"html/{owner.source_row_index}/{owner.source_cell_index}")
                    try:
                        self._fill_native_grid_runs(cell.paragraphs[0], owner.runs, config,
                            reference_bookmarks=context.caption_bookmarks)
                    except ValueError as error:
                        # OOXML 拒绝非法字符时仍失败关闭，公开错误不携带单元格原文。
                        raise TableRenderError("table_render_failed", block_index=fragment.block_index) from error
                self._format_table_cell(cell, header, config)
                cursor = owner.column + owner.colspan
            while cursor < fragment.render.grid.columns:
                self._append_grid_cell(tr, table, widths[cursor], 1)
                cursor += 1
            for paragraph in tr.iter(qn("w:p")):
                paragraph.get_or_add_pPr().get_or_add_keepNext().val = False
        return tuple(created)

    def _render_native_unit(self, document, unit, contract, blocks, config, context, *, page_break_before=False):
        """表只由 unit 创建；行、题注和末注分别归实际来源 owner。"""
        collector = context.collector
        annotations, scopes = [], []

        def annotation(item):
            block = blocks[item.block_id]
            text = getattr(block, item.field)[item.item_index].strip()
            paragraph = document.add_paragraph()
            self._set_formula_source(document, block.id, f"{item.field}/{item.item_index}")
            style = config.table_note if item.role == "note" else getattr(config, table_annotation_style(text))
            if item.role != "note":
                paragraph.paragraph_format.keep_with_next = True
                if page_break_before and not annotations:
                    paragraph.paragraph_format.page_break_before = True
            if (item.role != "caption" or not unit.is_group_primary or not self._fill_caption_paragraph(paragraph, text, style,
                    terminology=config.terminology, caption_bookmarks=context.caption_bookmarks)):
                self._fill_paragraph(paragraph, text, style, terminology=config.terminology,
                    reference_bookmarks=context.caption_bookmarks if item.role != "caption" else None)
            target = paragraph_target(paragraph, item.role, item.item_index)
            collector.add(block.id, [target])
            annotations.append((block.id, item.field, item.item_index, target))

        for item in contract.annotations:
            if item.disposition == "rendered" and item.role != "note":
                annotation(item)
        if unit.blocking_quality_flags:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            reasons = []
            if "table_fragment_missing" in unit.blocking_quality_flags:
                reasons.append("来源表格存在空白或缺失片段，未补造内容")
            if "table_render_layout_incompatible" in unit.blocking_quality_flags:
                reasons.append("续表布局或中间说明不兼容，已保留各片原生表格")
            self._fill_paragraph(paragraph, "表格诊断：" + "；".join(reasons) + "。", config.table_note,
                terminology=config.terminology)
            collector.add(contract.anchor_block_id, [paragraph_target(paragraph, "body")])
        width = self._available_table_width(document)
        table_config = table_config_for_columns(config, unit.columns)
        table = self._add_configured_table(document, 0, unit.columns, width, table_config)
        machine = OxmlElement("w:tblCaption")
        machine.set(qn("w:val"), unit.key)
        table._tbl.tblPr.append(machine)
        fragments = {fragment.fragment_id: fragment for fragment in contract.fragments}
        for fragment in unit.fragments:
            if fragment.render is None or fragment.status == "header_only":
                continue
            rows = self._append_native_rows(table, fragment, width, table_config, context)
            for output_index, row in enumerate(rows, fragment.output_start):
                if output_index < unit.header_rows:
                    self._ensure_row_flag(row.get_or_add_trPr(), "w:tblHeader", value="true")
            first = next(rows[0].iter(qn("w:p")))
            scope = fragments[fragment.source.fragment_id]
            target = LocalTarget(first, document.part, "table", content_scope_id=scope.content_scope_id,
                scope_table=table._tbl, scope_rows=rows)
            collector.add(fragment.source.block_id, [target])
            collector.records[fragment.source.block_id].reason_code = "table_fragment_rows"
            scopes.append((fragment.source.block_id, target))
            context.fragment_markers.append((fragment.bookmark, first))
        if context.placeholders:
            self._render_table_placeholders(document, {fragment.source.fragment_id for fragment in unit.fragments},
                context.assets, context.image_loader, context, config)
        for item in contract.annotations:
            if item.disposition == "rendered" and item.role == "note":
                annotation(item)
        for fragment in unit.fragments:
            block_id = fragment.source.block_id
            if block_id is not None and any(target.content_scope_id is not None for target in collector.targets[block_id]):
                collector.records[block_id].reason_code = "table_fragment_rows"
            if block_id is not None and fragment.status == "header_only" and not collector.targets[block_id]:
                record = collector.records[block_id]
                record.disposition, record.reason_code = "coalesced", "table_header_coalesced"
                record.representative_block_id = contract.anchor_block_id
        collector.tables.append((unit.key, table._tbl, document.part, tuple(scopes), tuple(annotations)))

