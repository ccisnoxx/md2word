from __future__ import annotations

# app/services/renderer/__init__.py: 导出 DocumentIR 到 Word 的渲染服务。

from app.services.renderer.word_renderer import DocumentIRWordRenderer, ImageContentLoader

__all__ = ["DocumentIRWordRenderer", "ImageContentLoader"]
