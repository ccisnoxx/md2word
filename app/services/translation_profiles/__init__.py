from __future__ import annotations

# app/services/translation_profiles/__init__.py: 暴露 Translation Profile service 包边界。

from app.services.translation_profiles.versioning_service import (
    DEFAULT_TRANSLATION_PROFILE_ID,
    TranslationProfileVersionService,
)

__all__ = ["DEFAULT_TRANSLATION_PROFILE_ID", "TranslationProfileVersionService"]
