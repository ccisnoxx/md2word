"""File-backed persistence adapter for managed internal users."""

from __future__ import annotations

# File: app/infrastructure/persistence/file/internal_users.py
# Purpose: Persist managed internal users in the local file metadata backend.

from app.domains.users.models import InternalUserRecord, InternalUserRole, InternalUserStatus
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileInternalUserRepository:
    """Store all managed internal users in one local JSON metadata file."""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "internal_users.json"

    def count_internal_users(self) -> int:
        return len(self._read_all())

    def list_internal_users(
        self,
        *,
        role: InternalUserRole | None = None,
        status: InternalUserStatus | None = None,
    ) -> list[InternalUserRecord]:
        records = self._read_all()
        if role is not None:
            records = [record for record in records if record.role == role]
        if status is not None:
            records = [record for record in records if record.status == status]
        return records

    def get_internal_user(self, user_id: str) -> InternalUserRecord | None:
        normalized_id = user_id.strip()
        return next((record for record in self._read_all() if record.id == normalized_id), None)

    def get_internal_user_by_username(self, normalized_username: str) -> InternalUserRecord | None:
        username_key = normalized_username.strip().lower()
        return next((record for record in self._read_all() if record.normalized_username == username_key), None)

    def save_internal_user(self, user: InternalUserRecord) -> InternalUserRecord:
        records = self._read_all()
        replaced = False
        for index, record in enumerate(records):
            if record.id == user.id:
                records[index] = user
                replaced = True
                break
            if record.normalized_username == user.normalized_username:
                raise ValueError(f"internal username already exists: {user.normalized_username}")
        if not replaced:
            records.append(user)
        self._write_all(records)
        return user

    def _read_all(self) -> list[InternalUserRecord]:
        payload = self.backend.read_json(self.path, [])
        raw_users = payload.get("users") if isinstance(payload, dict) else payload
        if not isinstance(raw_users, list):
            raise ValueError("internal_users.json must contain a user list")
        return sorted(
            [InternalUserRecord.model_validate(item) for item in raw_users],
            key=lambda record: (record.created_at, record.username, record.id),
        )

    def _write_all(self, records: list[InternalUserRecord]) -> None:
        ordered = sorted(records, key=lambda record: (record.created_at, record.username, record.id))
        self.backend.write_json(
            self.path,
            [record.model_dump(mode="json") for record in ordered],
        )
