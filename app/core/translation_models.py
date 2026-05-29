from __future__ import annotations

# app/core/translation_models.py: 定义翻译配置资源在 service 和 conversion 边界间传递的快照。

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationProfileSnapshot:
    """已发布 Translation Profile 的执行时快照，不包含任何 secret。"""

    translation_profile_id: str
    version: str
    snapshot_hash: str
    target_language: str
    domain: str
    prompt_version: str
    model: str | None
    max_pages_per_batch: int
    max_chars_per_batch: int
