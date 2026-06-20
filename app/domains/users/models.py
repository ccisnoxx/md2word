"""Domain models for managed internal users."""

from __future__ import annotations

# File: app/domains/users/models.py
# Purpose: Define managed internal user records stored by metadata repositories.

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


InternalUserRole = Literal["admin", "operator"]
InternalUserStatus = Literal["active", "disabled"]


def utc_now() -> datetime:
    """Return the current UTC timestamp for internal user records."""

    return datetime.now(timezone.utc)


def normalize_username(username: str) -> str:
    """Normalize usernames for case-insensitive uniqueness and login lookup."""

    return username.strip().lower()


class InternalUserRecord(BaseModel):
    """Managed internal account record; password_hash never leaves backend APIs."""

    id: str
    username: str
    normalized_username: str = ""
    password_hash: str
    role: InternalUserRole
    tenant_id: str = "default"
    company_id: str = "default"
    department_id: str = "default_department"
    status: InternalUserStatus = "active"
    display_name: str | None = None
    token_version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = None
    updated_by: str | None = None

    @model_validator(mode="after")
    def normalize_identity(self) -> "InternalUserRecord":
        """Keep legacy config users compatible while enforcing normalized usernames."""

        username = self.username.strip()
        if not username:
            raise ValueError("username must not be blank")
        self.username = username
        normalized_username = self.normalized_username.strip().lower() if self.normalized_username else ""
        self.normalized_username = normalized_username or normalize_username(username)
        self.department_id = self.department_id.strip() or "default_department"
        if self.token_version < 1:
            raise ValueError("token_version must be positive")
        return self
