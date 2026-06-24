from __future__ import annotations

# app/services/renderer/image_renderer.py: 提供 DocumentIR Word 渲染器的图片、宽度和图注 helper。

import io
from collections.abc import Callable
from typing import Any

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.shared import Cm

from app.services.document_ir.models import DocumentIRAsset, DocumentIRBlock
from app.services.renderer.template_config import TemplateConfigPackage


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]


class WordImageRendererMixin:
    """封装图片、缺图 fallback、bbox 宽度约束和图注渲染逻辑。"""

    def _render_image(
        self,
        document: Any,
        block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None = None,
    ) -> None:
        asset = assets_by_id.get(block.asset_ref or "")
        image_content = image_loader(asset) if asset is not None else None
        annotations = self._image_annotation_texts(block)
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if not image_content:
            self._fill_paragraph(
                paragraph,
                self._image_fallback_text(block),
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
            self._fill_paragraph(
                paragraph,
                self._image_fallback_text(block),
                template_config.caption,
                terminology=template_config.terminology,
            )

        if annotations:
            paragraph.paragraph_format.keep_with_next = True
        for index, caption in enumerate(annotations):
            caption_paragraph = document.add_paragraph()
            if index < len(annotations) - 1:
                caption_paragraph.paragraph_format.keep_with_next = True
            self._fill_paragraph(
                caption_paragraph,
                caption,
                template_config.caption,
                terminology=template_config.terminology,
            )

    def _available_width(
        self,
        document: Any,
        *,
        block: DocumentIRBlock | None = None,
        page_width: float | None = None,
    ) -> Any:
        sections = getattr(document, "sections", None)
        if not sections:
            base_width = Cm(14)
        else:
            section = sections[-1]
            width = section.page_width - section.left_margin - section.right_margin
            base_width = width if width > 0 else Cm(14)

        bbox = block.layout.bbox if block is not None and block.layout is not None else None
        if bbox is None or page_width is None or page_width <= 0:
            return base_width

        ratio = min(max((bbox[2] - bbox[0]) / page_width, 0.45), 1.0)
        min_width = int(Cm(4.5))
        return min(max(int(base_width * ratio), min_width), int(base_width))

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
