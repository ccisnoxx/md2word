from __future__ import annotations

# app/services/document_ir/__init__.py: 导出 DocumentIR 转换服务。

from app.services.document_ir.mineru_converter import (
    MinerUImageAsset,
    MinerUToDocumentIRResult,
    MinerUToDocumentIRService,
)

__all__ = [
    "MinerUImageAsset",
    "MinerUToDocumentIRResult",
    "MinerUToDocumentIRService",
]
