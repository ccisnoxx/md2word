"""Persistence ports for Acceptance Center run metadata."""

from __future__ import annotations

# File: app/domains/acceptance/repository.py
# Purpose: Define acceptance run metadata repository contracts.

from typing import Protocol

from app.domains.acceptance.models import AcceptanceRunRecord, AcceptanceRunStatus, AcceptanceRunTier


class AcceptanceRunRepositoryProtocol(Protocol):
    """Persistence contract shared by file, sqlite, and MySQL acceptance stores."""

    def list_acceptance_runs(
        self,
        *,
        tier: AcceptanceRunTier | None = None,
        status: AcceptanceRunStatus | None = None,
        limit: int | None = None,
    ) -> list[AcceptanceRunRecord]: ...
    def get_acceptance_run(self, run_id: str) -> AcceptanceRunRecord | None: ...
    def save_acceptance_run(self, run: AcceptanceRunRecord) -> AcceptanceRunRecord: ...
