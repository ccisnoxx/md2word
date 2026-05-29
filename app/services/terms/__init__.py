from __future__ import annotations

# app/services/terms/__init__.py: 导出 P1 只读术语版本加载服务。

from app.services.terms.term_version_service import TermVersionService

__all__ = ["TermVersionService"]
