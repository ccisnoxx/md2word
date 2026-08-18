from __future__ import annotations

# app/services/renderer/image_renderer.py: 提供 DocumentIR Word 渲染器的图片、宽度和图注 helper。

import io
from collections.abc import Callable
from typing import Any

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from app.services.document_ir.models import DocumentIRAsset, DocumentIRBlock
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
        caption_bookmarks: Any | None = None,
    ) -> None:
        asset = assets_by_id.get(block.asset_ref or "")
        image_content = image_loader(asset) if asset is not None else None
        annotations = self._image_annotation_texts(block)
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
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
            available_width = self._available_width(document, block=block, page_width=page_width)
            run = paragraph.add_run()
            run.add_picture(io.BytesIO(image_content), width=available_width)
        except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
            paragraph.text = ""
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

        if annotations:
            paragraph.paragraph_format.keep_with_next = True
        for index, caption in enumerate(annotations):
            caption_paragraph = document.add_paragraph()
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

    def _render_two_column_image_row(
        self,
        document: Any,
        left: DocumentIRBlock,
        right: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None,
        caption_bookmarks: Any | None,
        keep_with_next: bool,
    ) -> None:
        """用原生中心制表位渲染一行两张图片，避免逐行分节触发分页。"""

        content_width, _column_count = self._content_width_and_columns(document)
        image_paragraph = document.add_paragraph()
        self._configure_image_row_tabs(image_paragraph, content_width)
        rendered: list[bool] = []
        for block in (left, right):
            image_paragraph.add_run("\t")
            asset = assets_by_id.get(block.asset_ref or "")
            image_content = image_loader(asset) if asset is not None else None
            if image_content:
                try:
                    width = min(
                        self._available_width(document, block=block, page_width=page_width),
                        max(content_width // 2, 1),
                    )
                    image_paragraph.add_run().add_picture(io.BytesIO(image_content), width=width)
                    rendered.append(True)
                    continue
                except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
                    pass
            rendered.append(False)

        annotations: list[list[str]] = []
        for block, was_rendered in zip((left, right), rendered, strict=True):
            values = self._image_annotation_texts(block)
            if not values and not was_rendered:
                fallback = self._image_fallback_text(block)
                values = [fallback] if fallback else []
            annotations.append(values)
        if keep_with_next:
            image_paragraph.paragraph_format.keep_with_next = True
        if not any(annotations):
            return

        image_paragraph.paragraph_format.keep_with_next = True
        caption_paragraph = document.add_paragraph()
        self._configure_image_row_tabs(caption_paragraph, content_width)
        if keep_with_next:
            caption_paragraph.paragraph_format.keep_with_next = True
        for captions in annotations:
            caption_paragraph.add_run("\t")
            if not captions:
                continue
            caption = captions[0]
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

    def _configure_image_row_tabs(self, paragraph: Any, content_width: int) -> None:
        tab_stops = paragraph.paragraph_format.tab_stops
        tab_stops.add_tab_stop(content_width // 4, WD_TAB_ALIGNMENT.CENTER)
        tab_stops.add_tab_stop(content_width * 3 // 4, WD_TAB_ALIGNMENT.CENTER)

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
