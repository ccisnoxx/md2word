from __future__ import annotations

# app/domains/translation/models.py: 定义翻译配置资源在 service 和 conversion 边界间传递的快照。

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


TranslationTermStatus = Literal["editing", "publishable", "deprecated", "active", "disabled"]
TranslationTermVersionStatus = Literal["draft", "published", "archived"]
TranslationTermProposalStatus = Literal["pending", "approved", "rejected", "published"]
TranslationTermProposalAction = Literal["add", "update", "delete"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def derive_translation_term_set_id(language_pair: str) -> str:
    """从语言方向派生第一版固定 Translation Term Set ID。"""

    return f"translation-terms-{language_pair.strip().lower()}"


def normalize_translation_source_term(source_term: str) -> str:
    """生成大小写不敏感的翻译术语唯一键。"""

    return " ".join(source_term.strip().split()).lower()


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
    recommended_translations: tuple[str, ...] = field(default_factory=tuple)
    forbidden_translations: tuple[str, ...] = field(default_factory=tuple)
    synonyms: tuple[str, ...] = field(default_factory=tuple)
    set_id: str = ""
    normalized_source_term: str = ""
    case_sensitive: bool = False
    status: TranslationTermStatus = "active"
    priority: int = 0
    project: str | None = None
    content_type: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    maintainer: str | None = None
    domain: str | None = None
    category: str | None = None
    note: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.set_id:
            object.__setattr__(self, "set_id", derive_translation_term_set_id(self.language_pair))
        if not self.normalized_source_term:
            object.__setattr__(self, "normalized_source_term", normalize_translation_source_term(self.source_term))


@dataclass(frozen=True, slots=True)
class TranslationTermSetRecord:
    """Translation Term Set 默认指针和 draft 指针。"""

    set_id: str
    language_pair: str
    default_version: str | None = None
    draft_version: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class TranslationTermVersionRecord:
    """Translation Term Set 的单个 draft/published/archived 版本。"""

    set_id: str
    language_pair: str
    version: str
    status: TranslationTermVersionStatus
    snapshot_hash: str
    term_count: int
    published_by: str | None = None
    published_at: datetime | None = None
    release_note: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class TranslationTermProposalChangeRecord:
    """Translation Term Proposal 内的一条 add/update/delete 变更。"""

    proposal_id: str
    seq: int
    action: TranslationTermProposalAction
    source_term: str
    normalized_source_term: str = ""
    target_term: str | None = None
    case_sensitive: bool | None = None
    status: TranslationTermStatus | None = None
    priority: int | None = None
    domain: str | None = None
    category: str | None = None
    note: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.normalized_source_term:
            object.__setattr__(self, "normalized_source_term", normalize_translation_source_term(self.source_term))


@dataclass(frozen=True, slots=True)
class TranslationTermProposalRecord:
    """operator 提交、admin 审核的翻译术语建议。"""

    id: str
    status: TranslationTermProposalStatus
    submitted_by: str
    source_job_id: str | None = None
    source_file_id: str | None = None
    observed_translation_term_set_id: str | None = None
    observed_translation_term_version: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    published_translation_term_set_id: str | None = None
    published_translation_term_version: str | None = None
    published_at: datetime | None = None
    changes: tuple[TranslationTermProposalChangeRecord, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class TranslationTermMatchTraceRecord:
    """segment/batch 粒度的术语命中 trace，不保存完整原文或 prompt。"""

    id: str
    job_id: str
    translation_term_set_id: str
    translation_term_version: str
    source_term: str
    target_term: str
    segment_id: str | None = None
    batch_id: str | None = None
    match_start: int | None = None
    match_end: int | None = None
    context_snippet: str | None = None
    injected_to_glossary: bool = False
    provider_trace_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)


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
    term_traces: tuple[TranslationTermMatchTraceRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TranslationProviderResult:
    """translation provider 返回的结构化文本结果。"""

    items: tuple[TranslationTextItem, ...]
