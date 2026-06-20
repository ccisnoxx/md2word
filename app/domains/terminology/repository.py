from __future__ import annotations

# app/domains/terminology/repository.py: Repository port for terminology governance releases.

from typing import Protocol

from app.domains.terminology.models import TerminologyReleaseRecord, TerminologyReleaseStatus


class TerminologyReleaseRepositoryProtocol(Protocol):
    """Persistence contract for terminology governance package releases."""

    def save_release(self, record: TerminologyReleaseRecord) -> TerminologyReleaseRecord: ...
    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord | None: ...
    def list_releases(
        self,
        *,
        status: TerminologyReleaseStatus | None = None,
        project: str | None = None,
        language_pair: str | None = None,
        content_type: str | None = None,
    ) -> list[TerminologyReleaseRecord]: ...
