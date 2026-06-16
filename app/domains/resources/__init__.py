from __future__ import annotations

# app/domains/resources/__init__.py: 暴露资源版本 service 包边界。

from app.domains.resources.service import ResourceVersionService

__all__ = ["ResourceVersionService"]
