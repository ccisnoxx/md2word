from __future__ import annotations

# app/domains/term_rules/__init__.py: 暴露术语规则 service 包边界。

from app.domains.term_rules.versioning_service import TermRuleSetVersionService

__all__ = ["TermRuleSetVersionService"]
