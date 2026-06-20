"""Persistence ports for managed internal users."""

from __future__ import annotations

# File: app/domains/users/repository.py
# Purpose: Define repository protocol for internal user metadata storage.

from typing import Protocol

from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus


class InternalUserRepositoryProtocol(Protocol):
    """Persistence contract shared by file, sqlite, and MySQL user stores."""

    def count_internal_users(self) -> int: ...
    def list_internal_users(
        self,
        *,
        role: InternalUserRole | None = None,
        status: InternalUserStatus | None = None,
    ) -> list[InternalUserRecord]: ...
    def get_internal_user(self, user_id: str) -> InternalUserRecord | None: ...
    def get_internal_user_by_username(self, normalized_username: str) -> InternalUserRecord | None: ...
    def save_internal_user(self, user: InternalUserRecord) -> InternalUserRecord: ...
