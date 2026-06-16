from __future__ import annotations

# app/domains/translation/repository.py: 定义翻译术语版本的持久化端口。

from datetime import datetime
from typing import Protocol

from app.domains.translation.models import (
    TranslationTermEntry,
    TranslationTermMatchTraceRecord,
    TranslationTermProposalRecord,
    TranslationTermProposalStatus,
    TranslationTermSetRecord,
    TranslationTermVersionStatus,
    TranslationTermVersionRecord,
)


class TranslationTermRepositoryProtocol(Protocol):
    """翻译术语版本的 SQL 持久化合同。"""

    def save_set(self, record: TranslationTermSetRecord) -> TranslationTermSetRecord: ...
    def get_set(self, set_id: str) -> TranslationTermSetRecord | None: ...
    def get_set_by_language_pair(self, language_pair: str) -> TranslationTermSetRecord | None: ...
    def list_sets(self) -> list[TranslationTermSetRecord]: ...
    def save_version(self, record: TranslationTermVersionRecord) -> TranslationTermVersionRecord: ...
    def get_version(self, set_id: str, version: str) -> TranslationTermVersionRecord | None: ...
    def list_versions(self, set_id: str) -> list[TranslationTermVersionRecord]: ...
    def replace_version(
        self,
        language_pair: str,
        version: str,
        entries: list[TranslationTermEntry],
        snapshot_hash: str,
        *,
        status: TranslationTermVersionStatus = "published",
        make_default: bool | None = None,
        set_draft: bool = False,
        clear_draft: bool = False,
        published_by: str | None = None,
        published_at: datetime | None = None,
        release_note: str | None = None,
    ) -> None: ...
    def load_version(self, language_pair: str, version: str) -> list[TranslationTermEntry]: ...
    def has_version(self, language_pair: str, version: str) -> bool: ...
    def save_proposal(self, proposal: TranslationTermProposalRecord) -> TranslationTermProposalRecord: ...
    def get_proposal(self, proposal_id: str) -> TranslationTermProposalRecord | None: ...
    def list_proposals(
        self,
        *,
        status: TranslationTermProposalStatus | None = None,
        submitted_by: str | None = None,
    ) -> list[TranslationTermProposalRecord]: ...
    def append_match_trace(self, trace: TranslationTermMatchTraceRecord) -> TranslationTermMatchTraceRecord: ...
    def list_match_traces(self, job_id: str) -> list[TranslationTermMatchTraceRecord]: ...
