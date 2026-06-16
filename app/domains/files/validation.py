from __future__ import annotations

# app/domains/files/validation.py: 提供上传入口共用的 PDF 基础校验。

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import status

from app.core.errors import ApiError


_PDF_MIME_TYPES = {"application/pdf", "application/x-pdf"}
_PAGE_OBJECT_PATTERN = re.compile(rb"/Type\s*/Page\b")


@dataclass(frozen=True, slots=True)
class PdfValidationResult:
    """PDF 基础校验结果；页数为轻量解析得到的保守估计。"""

    size_bytes: int
    page_count: int


def validate_pdf_upload(
    *,
    filename: str,
    content_type: str | None,
    content: bytes,
    max_bytes: int,
    max_pages: int,
) -> PdfValidationResult:
    """校验 PDF 扩展名、MIME、文件头、大小和基础页数上限。"""

    validate_pdf_metadata(
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        max_bytes=max_bytes,
    )
    if not content.startswith(b"%PDF-"):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "上传文件不是合法 PDF。")

    page_count = estimate_pdf_page_count(content)
    if page_count > max_pages:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            f"PDF 页数超过限制 {max_pages} 页。",
        )
    return PdfValidationResult(size_bytes=len(content), page_count=page_count)


def validate_pdf_metadata(
    *,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    max_bytes: int,
) -> None:
    """校验上传授权阶段能获得的 PDF 元数据。"""

    normalized_filename = Path(filename).name.strip()
    if not normalized_filename or not normalized_filename.lower().endswith(".pdf"):
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "上传文件必须是 .pdf 格式。")
    normalized_content_type = _normalize_content_type(content_type)
    if normalized_content_type and normalized_content_type not in _PDF_MIME_TYPES:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            f"不支持的 PDF content-type: {content_type}",
        )
    if size_bytes <= 0:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "上传文件不能为空。")
    if size_bytes > max_bytes:
        raise ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "file_too_large",
            f"上传文件超过大小限制 {max_bytes} bytes。",
        )


def estimate_pdf_page_count(content: bytes) -> int:
    """用无依赖方式估算 PDF 页数；未识别到 page 对象时按 1 页处理。"""

    page_count = len(_PAGE_OBJECT_PATTERN.findall(content))
    return max(1, page_count)


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized or None
