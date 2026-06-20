"""Business service for managed internal user lifecycle operations."""

from __future__ import annotations

# File: app/domains/users/service.py
# Purpose: Enforce internal user validation, last-admin protection, and token invalidation.

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import status as http_status

from app.core.errors import ApiError
from app.domains.users.models import (
    InternalUserRecord,
    InternalUserRole,
    InternalUserStatus,
    normalize_username,
    utc_now,
)
from app.domains.users.repository import InternalUserRepositoryProtocol
from app.services.auth.service import hash_password, verify_password


MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True, slots=True)
class InternalUserUpdateResult:
    """Result of an admin user update with safe audit-ready change details."""

    user: InternalUserRecord
    changed_fields: dict[str, dict[str, Any]]
    status_changed_to: InternalUserStatus | None = None


class InternalUserManagementService:
    """Manage internal users without exposing password hashes through API models."""

    def __init__(self, repository: InternalUserRepositoryProtocol) -> None:
        self.repository = repository

    def list_users(
        self,
        *,
        role: InternalUserRole | None = None,
        status: InternalUserStatus | None = None,
        keyword: str | None = None,
    ) -> list[InternalUserRecord]:
        """List users with repository role/status filters and service keyword matching."""

        records = self.repository.list_internal_users(role=role, status=status)
        normalized_keyword = (keyword or "").strip().lower()
        if not normalized_keyword:
            return records
        return [
            record
            for record in records
            if normalized_keyword in record.username.lower()
            or normalized_keyword in record.normalized_username
            or normalized_keyword in (record.display_name or "").lower()
            or normalized_keyword in record.id.lower()
        ]

    def create_user(
        self,
        *,
        username: str,
        display_name: str | None,
        department_id: str,
        role: InternalUserRole,
        status: InternalUserStatus,
        initial_password: str,
        actor_id: str,
    ) -> InternalUserRecord:
        """Create a managed user after case-insensitive uniqueness and password checks."""

        normalized_username = self._validate_username(username)
        self._validate_password(initial_password)
        if self.repository.get_internal_user_by_username(normalized_username) is not None:
            raise ApiError(http_status.HTTP_409_CONFLICT, "user_conflict", "用户名已存在。")
        now = utc_now()
        record = InternalUserRecord(
            id=f"user_{uuid4().hex[:12]}",
            username=username.strip(),
            normalized_username=normalized_username,
            password_hash=hash_password(initial_password),
            role=role,
            department_id=self._normalize_department_id(department_id),
            status=status,
            display_name=self._normalize_optional_text(display_name),
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            updated_by=actor_id,
        )
        return self.repository.save_internal_user(record)

    def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None,
        display_name_provided: bool,
        department_id: str | None,
        department_id_provided: bool,
        role: InternalUserRole | None,
        status_value: InternalUserStatus | None,
        actor_id: str,
    ) -> InternalUserUpdateResult:
        """Update safe user fields and prevent disabling or downgrading the last active admin."""

        record = self._get_user_or_404(user_id)
        new_role = role or record.role
        new_status = status_value or record.status
        self._ensure_not_last_active_admin(record, new_role=new_role, new_status=new_status)

        changes: dict[str, dict[str, Any]] = {}
        normalized_display_name = self._normalize_optional_text(display_name)
        if display_name_provided and normalized_display_name != record.display_name:
            changes["display_name"] = {"from": record.display_name, "to": normalized_display_name}
            record.display_name = normalized_display_name
        if department_id_provided:
            normalized_department_id = self._normalize_department_id(department_id)
            if normalized_department_id != record.department_id:
                changes["department_id"] = {"from": record.department_id, "to": normalized_department_id}
                record.department_id = normalized_department_id
                record.token_version += 1
        if role is not None and role != record.role:
            changes["role"] = {"from": record.role, "to": role}
            record.role = role
            record.token_version += 1
        status_changed_to: InternalUserStatus | None = None
        if status_value is not None and status_value != record.status:
            changes["status"] = {"from": record.status, "to": status_value}
            record.status = status_value
            status_changed_to = status_value
            record.token_version += 1
        if changes:
            record.updated_at = utc_now()
            record.updated_by = actor_id
            record = self.repository.save_internal_user(record)
        return InternalUserUpdateResult(user=record, changed_fields=changes, status_changed_to=status_changed_to)

    def reset_password(self, user_id: str, *, new_password: str, actor_id: str) -> InternalUserRecord:
        """Reset a user's password and invalidate all existing JWTs for that user."""

        self._validate_password(new_password)
        record = self._get_user_or_404(user_id)
        record.password_hash = hash_password(new_password)
        record.token_version += 1
        record.updated_at = utc_now()
        record.updated_by = actor_id
        return self.repository.save_internal_user(record)

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> InternalUserRecord:
        """Change the current user's own password after verifying the existing password."""

        self._validate_password(new_password)
        record = self._get_user_or_404(user_id)
        if record.status != "active" or not verify_password(current_password, record.password_hash):
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "当前密码不正确。")
        record.password_hash = hash_password(new_password)
        record.token_version += 1
        record.updated_at = utc_now()
        record.updated_by = user_id
        return self.repository.save_internal_user(record)

    def _get_user_or_404(self, user_id: str) -> InternalUserRecord:
        record = self.repository.get_internal_user(user_id.strip())
        if record is None:
            raise ApiError(http_status.HTTP_404_NOT_FOUND, "not_found", "用户不存在。")
        return record

    def _validate_username(self, username: str) -> str:
        normalized = normalize_username(username)
        if not normalized:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "用户名不能为空。")
        return normalized

    def _validate_password(self, password: str) -> None:
        if not password or not password.strip():
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "密码不能为空。")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "密码不符合最小强度要求。")

    def _ensure_not_last_active_admin(
        self,
        record: InternalUserRecord,
        *,
        new_role: InternalUserRole,
        new_status: InternalUserStatus,
    ) -> None:
        if record.role != "admin" or record.status != "active":
            return
        if new_role == "admin" and new_status == "active":
            return
        other_active_admins = [
            user
            for user in self.repository.list_internal_users(role="admin", status="active")
            if user.id != record.id
        ]
        if not other_active_admins:
            raise ApiError(http_status.HTTP_409_CONFLICT, "last_admin_conflict", "不能禁用或降级最后一个可用管理员。")

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_department_id(self, value: str | None) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "department_id 不能为空。")
        return normalized
