from __future__ import annotations

# app/services/translation/__init__.py: 导出 DocumentIR 翻译服务和 provider 边界。

from app.services.translation.document_ir_translator import DocumentIRTranslationService
from app.services.translation.provider import (
    DisabledTranslationProvider,
    OpenAICompatibleTranslationProvider,
    TranslationProvider,
    build_translation_provider,
)

__all__ = [
    "DisabledTranslationProvider",
    "DocumentIRTranslationService",
    "OpenAICompatibleTranslationProvider",
    "TranslationProvider",
    "build_translation_provider",
]
