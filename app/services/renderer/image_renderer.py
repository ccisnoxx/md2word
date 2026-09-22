from __future__ import annotations

# app/services/renderer/image_renderer.py: 提供 DocumentIR Word 渲染器的图片、宽度和图注 helper。

import io
from collections.abc import Callable
from typing import Any

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from app.services.document_ir.integrity import (
    complement_crop_rects,
    drawingml_crop_offsets,
    visual_crop_rects,
    visual_overlap_mask,
)
from app.services.document_ir.models import DocumentIRAsset, DocumentIRBlock
from app.services.renderer.table_layout import TableFitDecision
from app.services.renderer.template_config import TemplateConfigPackage


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]


class WordImageRendererMixin:
    """封装图片、缺图回退策略、bbox 宽度约束和图注渲染逻辑。"""

    def _render_image(
        self,
        document: Any,
        block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None = None,
        page_height: float | None = None,
        caption_bookmarks: Any | None = None,
        page_break_before: bool = False,
        column_break_before: bool = False,
    ) -> None:
        available_width = self._available_width(document, block=block, page_width=page_width)
        available_height = self._available_height(document, block=block, page_height=page_height)
        self._render_image_content(
            document,
            block,
            assets_by_id,
            template_config,
            image_loader,
            available_width=available_width,
            available_height=available_height,
            caption_bookmarks=caption_bookmarks,
            page_break_before=page_break_before,
            column_break_before=column_break_before,
        )

    def _render_image_content(
        self,
        container: Any,
        block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        available_width: Any,
        available_height: Any | None,
        caption_bookmarks: Any | None,
        initial_paragraph: Any | None = None,
        page_break_before: bool = False,
        column_break_before: bool = False,
    ) -> None:
        asset = assets_by_id.get(block.asset_ref or "")
        image_content = image_loader(asset) if asset is not None else None
        annotations = self._image_annotation_texts(block)
        paragraph = initial_paragraph or container.add_paragraph()
        crop_rects = visual_crop_rects(block)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if crop_rects else WD_ALIGN_PARAGRAPH.CENTER
        self._apply_paragraph_breaks(
            paragraph,
            page_break_before=page_break_before,
            column_break_before=column_break_before,
        )
        if not image_content:
            fallback_text = self._image_fallback_text(block)
            if not self._fill_caption_paragraph(
                paragraph,
                fallback_text,
                template_config.caption,
                terminology=template_config.terminology,
                caption_bookmarks=caption_bookmarks,
            ):
                self._fill_paragraph(
                    paragraph,
                    fallback_text,
                    template_config.caption,
                    terminology=template_config.terminology,
                )
            return

        try:
            if crop_rects:
                raise ValueError("裁剪图片必须由表图复合关系区域渲染")
            else:
                run = paragraph.add_run()
                inline_shape = run.add_picture(io.BytesIO(image_content), width=available_width)
                self._fit_inline_shape_height(inline_shape, available_height)
                self._mark_image_asset_identity(inline_shape, asset.id)
        except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
            paragraph.text = ""
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before,
                column_break_before=column_break_before,
            )
            fallback_text = self._image_fallback_text(block)
            if not self._fill_caption_paragraph(
                paragraph,
                fallback_text,
                template_config.caption,
                terminology=template_config.terminology,
                caption_bookmarks=caption_bookmarks,
            ):
                self._fill_paragraph(
                    paragraph,
                    fallback_text,
                    template_config.caption,
                    terminology=template_config.terminology,
                )
            return

        self._render_image_annotations(
            container,
            annotations,
            template_config,
            caption_bookmarks=caption_bookmarks,
            anchor_paragraph=paragraph,
        )

    def _render_image_annotations(
        self,
        container: Any,
        annotations: list[str],
        template_config: TemplateConfigPackage,
        *,
        caption_bookmarks: Any | None,
        anchor_paragraph: Any | None = None,
    ) -> None:
        """在图片或表图复合容器之后统一输出题注与图注。"""

        if annotations and anchor_paragraph is not None:
            anchor_paragraph.paragraph_format.keep_with_next = True
        for index, caption in enumerate(annotations):
            caption_paragraph = container.add_paragraph()
            if index < len(annotations) - 1:
                caption_paragraph.paragraph_format.keep_with_next = True
            if not self._fill_caption_paragraph(
                caption_paragraph,
                caption,
                template_config.caption,
                terminology=template_config.terminology,
                caption_bookmarks=caption_bookmarks,
            ):
                self._fill_paragraph(
                    caption_paragraph,
                    caption,
                    template_config.caption,
                    terminology=template_config.terminology,
                )

    def _render_visual_table_composite(
        self,
        document: Any,
        image_block: DocumentIRBlock,
        table_block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None,
        caption_bookmarks: Any | None,
        reference_bookmarks: Any | None,
        fit_decision: TableFitDecision | None,
        page_break_before: bool = False,
    ) -> None:
        """用原生布局表把可编辑表格嵌回机械图的关系位置。"""

        asset = assets_by_id.get(image_block.asset_ref or "")
        image_content = image_loader(asset) if asset is not None else None
        mask = visual_overlap_mask(image_block)
        crop_rects = visual_crop_rects(image_block)
        group_id = image_block.metadata.get("visual_overlap_group_id")
        if not image_content or mask is None or crop_rects != complement_crop_rects(mask) or not isinstance(group_id, str):
            paragraph = document.add_paragraph()
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before,
                column_break_before=False,
            )
            self._fill_paragraph(
                paragraph,
                self._image_fallback_text(image_block),
                template_config.caption,
                terminology=template_config.terminology,
            )
            self._render_table(
                document,
                table_block,
                template_config,
                caption_bookmarks=caption_bookmarks,
                reference_bookmarks=reference_bookmarks,
                fit_decision=fit_decision,
            )
            return

        # LayoutPlan 已按当前单栏 full-width 计算 mask；这里不能再按源图片 bbox 二次缩窄。
        available_width, _column_count = self._content_width_and_columns(document)
        left, top, right, bottom = mask
        columns = [value for value in (left, right - left, 1 - right) if value > 0]
        rows = [value for value in (top, bottom - top, 1 - bottom) if value > 0]
        layout_table = document.add_table(rows=len(rows), cols=len(columns))
        layout_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        layout_table.autofit = False
        self._set_table_width(layout_table, available_width)
        self._mark_visual_table_composite(layout_table, group_id)
        self._remove_layout_table_borders(layout_table)

        column_widths = [max(int(available_width * ratio), 1) for ratio in columns]
        column_widths[-1] += int(available_width) - sum(column_widths)
        for column, width in zip(layout_table.columns, column_widths, strict=True):
            column.width = width
        for row in layout_table.rows:
            self._ensure_layout_row_cant_split(row)
            for cell in row.cells:
                self._zero_layout_cell_margins(cell)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

        top_row = 0 if top > 0 else None
        middle_row = 1 if top > 0 else 0
        bottom_row = middle_row + 1 if bottom < 1 else None
        left_column = 0 if left > 0 else None
        center_column = 1 if left > 0 else 0
        right_column = center_column + 1 if right < 1 else None
        crop_cells: list[tuple[Any, tuple[float, float, float, float]]] = []
        if left_column is not None:
            cell = self._merge_layout_column(layout_table, left_column)
            crop_cells.append((cell, (0.0, 0.0, left, 1.0)))
        if top_row is not None:
            crop_cells.append((layout_table.cell(top_row, center_column), (left, 0.0, right, top)))
        if bottom_row is not None:
            crop_cells.append((layout_table.cell(bottom_row, center_column), (left, bottom, right, 1.0)))
        if right_column is not None:
            cell = self._merge_layout_column(layout_table, right_column)
            crop_cells.append((cell, (right, 0.0, 1.0, 1.0)))

        anchor_paragraph = None
        for index, (cell, crop_rect) in enumerate(crop_cells):
            paragraph = cell.paragraphs[0]
            self._prepare_layout_paragraph(paragraph)
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before and index == 0,
                column_break_before=False,
            )
            self._add_cropped_picture(
                paragraph,
                image_content,
                asset.id,
                available_width=available_width,
                crop_rect=crop_rect,
            )
            anchor_paragraph = paragraph

        table_cell = layout_table.cell(middle_row, center_column)
        initial_paragraph = table_cell.paragraphs[0]
        table_cell._tc.remove(initial_paragraph._p)
        self._render_table(
            table_cell,
            table_block,
            template_config,
            caption_bookmarks=caption_bookmarks,
            reference_bookmarks=reference_bookmarks,
            fit_decision=fit_decision,
        )
        self._render_image_annotations(
            document,
            self._image_annotation_texts(image_block),
            template_config,
            caption_bookmarks=caption_bookmarks,
            anchor_paragraph=anchor_paragraph,
        )

    def _mark_visual_table_composite(self, table: Any, group_id: str) -> None:
        description = OxmlElement("w:tblDescription")
        description.set(qn("w:val"), f"md2word:visual_table_composite:{group_id}")
        table._tbl.tblPr.append(description)

    def _merge_layout_column(self, table: Any, column_index: int) -> Any:
        return table.cell(0, column_index).merge(table.cell(len(table.rows) - 1, column_index))

    def _ensure_layout_row_cant_split(self, row: Any) -> None:
        properties = row._tr.get_or_add_trPr()
        if properties.find(qn("w:cantSplit")) is None:
            properties.append(OxmlElement("w:cantSplit"))

    def _zero_layout_cell_margins(self, cell: Any) -> None:
        properties = cell._tc.get_or_add_tcPr()
        margins = properties.find(qn("w:tcMar"))
        if margins is None:
            margins = OxmlElement("w:tcMar")
            properties.append(margins)
        for edge in ("top", "start", "bottom", "end"):
            margin = margins.find(qn(f"w:{edge}"))
            if margin is None:
                margin = OxmlElement(f"w:{edge}")
                margins.append(margin)
            margin.set(qn("w:w"), "0")
            margin.set(qn("w:type"), "dxa")

    def _prepare_layout_paragraph(self, paragraph: Any) -> None:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)

    def _add_cropped_picture(
        self,
        paragraph: Any,
        image_content: bytes,
        asset_id: str,
        *,
        available_width: Any,
        crop_rect: tuple[float, float, float, float],
    ) -> Any:
        """使用 DrawingML 原生 srcRect 保留整图中的一个非表格区域。"""

        left, top, right, bottom = crop_rect
        crop_width = right - left
        crop_height = bottom - top
        run = paragraph.add_run()
        run.font.size = Pt(1)
        inline_shape = run.add_picture(
            io.BytesIO(image_content),
            width=max(int(available_width * crop_width), 1),
        )
        inline_shape.height = max(int(inline_shape.height * crop_height / crop_width), 1)
        blip_fill = inline_shape._inline.graphic.graphicData.pic.blipFill
        src_rect = OxmlElement("a:srcRect")
        crop_left, crop_top, crop_right, crop_bottom = drawingml_crop_offsets(crop_rect)
        src_rect.set("l", str(crop_left))
        src_rect.set("t", str(crop_top))
        src_rect.set("r", str(crop_right))
        src_rect.set("b", str(crop_bottom))
        blip_fill.insert(1, src_rect)
        self._mark_image_asset_identity(inline_shape, asset_id)
        return inline_shape

    def _mark_image_asset_identity(self, inline_shape: Any, asset_id: str) -> None:
        """把稳定资产身份写入 drawing，供 DOCX evidence 关联媒体关系。"""

        inline_shape._inline.docPr.set("descr", f"md2word:asset:{asset_id}")

    def _render_paired_visual_row(
        self,
        document: Any,
        left: DocumentIRBlock,
        right: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None,
        page_height: float | None,
        caption_bookmarks: Any | None,
        page_break_before: bool = False,
        column_break_before: bool = False,
    ) -> None:
        """用带稳定标记的无边框 1×2 Word 表格承载严格图片对。"""

        content_width, _column_count = self._content_width_and_columns(document)
        cell_width = max(content_width // 2, 1)
        table = document.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        self._mark_paired_visual_table(table)
        self._remove_layout_table_borders(table)
        row = table.rows[0]
        row_properties = row._tr.get_or_add_trPr()
        row_properties.append(OxmlElement("w:cantSplit"))
        for index, (cell, block) in enumerate(zip(row.cells, (left, right), strict=True)):
            cell.width = cell_width
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            available_width = min(
                self._available_width(document, block=block, page_width=page_width),
                cell_width,
            )
            available_height = self._available_height(document, block=block, page_height=page_height)
            self._render_image_content(
                cell,
                block,
                assets_by_id,
                template_config,
                image_loader,
                available_width=available_width,
                available_height=available_height,
                caption_bookmarks=caption_bookmarks,
                initial_paragraph=cell.paragraphs[0],
                page_break_before=page_break_before and index == 0,
                column_break_before=column_break_before and index == 0,
            )
            # 整行已经禁止拆分，单元格段落再逐段 keepNext 会让 WPS 连续图片行成组后整体后移。
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = False

    def _mark_paired_visual_table(self, table: Any) -> None:
        description = OxmlElement("w:tblDescription")
        description.set(qn("w:val"), "md2word:paired_visual_row")
        table._tbl.tblPr.append(description)

    def _remove_layout_table_borders(self, table: Any) -> None:
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement(f"w:{edge}")
            border.set(qn("w:val"), "nil")
            borders.append(border)
        table._tbl.tblPr.insert_element_before(
            borders,
            "w:shd",
            "w:tblLayout",
            "w:tblCellMar",
            "w:tblLook",
            "w:tblCaption",
            "w:tblDescription",
        )

    def _apply_paragraph_breaks(
        self,
        paragraph: Any,
        *,
        page_break_before: bool,
        column_break_before: bool,
    ) -> None:
        if page_break_before:
            paragraph.paragraph_format.page_break_before = True
        if column_break_before:
            paragraph.add_run().add_break(WD_BREAK.COLUMN)

    def _available_width(
        self,
        document: Any,
        *,
        block: DocumentIRBlock | None = None,
        page_width: float | None = None,
    ) -> Any:
        base_width, column_count = self._content_width_and_columns(document)

        bbox = block.layout.bbox if block is not None and block.layout is not None else None
        if bbox is None or page_width is None or page_width <= 0:
            return base_width

        source_column_width = page_width / column_count
        ratio = min(max((bbox[2] - bbox[0]) / source_column_width, 0.0), 1.0)
        return max(min(int(base_width * ratio), int(base_width)), 1)

    def _available_height(
        self,
        document: Any,
        *,
        block: DocumentIRBlock | None = None,
        page_height: float | None = None,
    ) -> Any | None:
        """按源页相对高度限制图片，避免只按宽度放大后破坏同页内容组。"""

        sections = getattr(document, "sections", None)
        bbox = block.layout.bbox if block is not None and block.layout is not None else None
        if not sections or bbox is None or page_height is None or page_height <= 0:
            return None
        section = sections[-1]
        content_height = section.page_height - section.top_margin - section.bottom_margin
        source_height = bbox[3] - bbox[1]
        if content_height <= 0 or source_height <= 0:
            return None
        ratio = min(source_height / page_height, 1.0)
        return max(int(content_height * ratio), 1)

    def _fit_inline_shape_height(self, inline_shape: Any, available_height: Any | None) -> None:
        """高度超限时等比缩小图片，不拉伸或放大源资产。"""

        if available_height is None or inline_shape.height <= available_height:
            return
        original_height = int(inline_shape.height)
        target_height = int(available_height)
        inline_shape.width = max(int(inline_shape.width * target_height / original_height), 1)
        inline_shape.height = target_height

    def _image_fallback_text(self, block: DocumentIRBlock) -> str:
        captions = self._image_annotation_texts(block)
        return captions[0] if captions else block.text or ""

    def _image_annotation_texts(self, block: DocumentIRBlock) -> list[str]:
        values: list[str] = []
        values.extend(block.captions)
        metadata_caption = block.metadata.get("caption")
        if isinstance(metadata_caption, str):
            values.append(metadata_caption)
        values.extend(block.footnotes)

        seen: set[str] = set()
        texts: list[str] = []
        for value in values:
            text = value.strip()
            if text and text not in seen:
                texts.append(text)
                seen.add(text)
        return texts
