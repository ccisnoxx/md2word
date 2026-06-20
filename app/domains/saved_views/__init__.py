"""Expose saved_views domain services."""

from __future__ import annotations

# File: app/domains/saved_views/__init__.py
# Purpose: Export saved_views domain service types.

from app.domains.saved_views.service import SavedViewService

__all__ = ["SavedViewService"]
