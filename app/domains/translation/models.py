from __future__ import annotations

# app/domains/translation/models.py: 定义翻译配置资源在 service 和 conversion 边界间传递的快照。

from dataclasses import dataclass, field


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


@dataclass(frozen=True, slots=True)
class TranslationTermEntry:
    """翻译术语表中的一条固定映射。"""

    language_pair: str
    source_term: str
    target_term: str
    version: str


@dataclass(frozen=True, slots=True)
class TermVersionSnapshot:
    """只读术语版本快照，用于任务绑定和翻译 provider 输入。"""

    term_version_id: str
    language_pair: str
    version: str
    snapshot_hash: str
    entries: tuple[TranslationTermEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TranslationTextItem:
    """一次 provider 调用中的最小文本片段。"""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class TranslationProviderRequest:
    """发送给 translation provider 的结构化请求，不包含密钥。"""

    language_pair: str
    source_language: str
    target_language: str
    items: tuple[TranslationTextItem, ...]
    terms: tuple[TranslationTermEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TranslationProviderResult:
    """translation provider 返回的结构化文本结果。"""

    items: tuple[TranslationTextItem, ...]
