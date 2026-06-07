# File: app/domains/files/cleanup_lock.py
# Purpose: Provide a metadata-backed lock contract for future file-retention cleanup automation.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.domains.jobs.models import utc_now


FILE_RETENTION_CLEANUP_LOCK_NAME = "file_retention_cleanup"
FileRetentionCleanupLockStatus = Literal["active", "released"]
FileRetentionCleanupLockEffectiveStatus = Literal["available", "active", "expired", "released"]


class FileRetentionCleanupLockConflict(RuntimeError):
    """表示 cleanup lock 获取、刷新或释放被 fencing/lease 规则拒绝。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FileRetentionCleanupLockRecord(BaseModel):
    """保存单个 cleanup lock 的当前租约和 fencing token。"""

    lock_name: str = FILE_RETENTION_CLEANUP_LOCK_NAME
    owner_id: str
    fencing_token: int
    status: FileRetentionCleanupLockStatus = "active"
    acquired_at: datetime = Field(default_factory=utc_now)
    heartbeat_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    released_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def is_active_at(self, now: datetime) -> bool:
        """判断该锁在指定时间是否仍由当前 owner 持有。"""

        return self.status == "active" and _normalize_datetime(now) <= _normalize_datetime(self.expires_at)


class FileRetentionCleanupLockStatusReport(BaseModel):
    """返回 cleanup lock 的只读 effective status。"""

    lock_name: str = FILE_RETENTION_CLEANUP_LOCK_NAME
    effective_status: FileRetentionCleanupLockEffectiveStatus
    owner_id: str | None = None
    fencing_token: int | None = None
    acquired_at: datetime | None = None
    heartbeat_at: datetime | None = None
    expires_at: datetime | None = None
    released_at: datetime | None = None


class FileRetentionCleanupLockRepositoryProtocol(Protocol):
    """cleanup lock metadata repository 合同。"""

    def save_lock(self, record: FileRetentionCleanupLockRecord) -> FileRetentionCleanupLockRecord: ...
    def get_lock(self, lock_name: str) -> FileRetentionCleanupLockRecord | None: ...


class FileRetentionCleanupLockService:
    """提供 cleanup automation 的 lease/fencing 基础能力，不执行任何清理动作。"""

    def __init__(
        self,
        repository: FileRetentionCleanupLockRepositoryProtocol,
        *,
        lock_name: str = FILE_RETENTION_CLEANUP_LOCK_NAME,
    ) -> None:
        self.repository = repository
        self.lock_name = lock_name

    def acquire(
        self,
        *,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> FileRetentionCleanupLockRecord:
        """获取 cleanup lock；未过期 active lock 存在时拒绝第二个 owner。"""

        normalized_owner = _normalize_owner(owner_id)
        expires_at = _expires_at(ttl_seconds=ttl_seconds, now=now)
        acquired_at = _normalize_datetime(now or utc_now())
        current = self.repository.get_lock(self.lock_name)
        if current is not None and current.is_active_at(acquired_at):
            raise FileRetentionCleanupLockConflict(
                "cleanup_lock_already_held",
                f"cleanup lock 已被 {current.owner_id} 持有，fencing_token={current.fencing_token}。",
            )
        next_token = (current.fencing_token if current is not None else 0) + 1
        record = FileRetentionCleanupLockRecord(
            lock_name=self.lock_name,
            owner_id=normalized_owner,
            fencing_token=next_token,
            status="active",
            acquired_at=acquired_at,
            heartbeat_at=acquired_at,
            expires_at=expires_at,
            released_at=None,
            metadata={key: str(value) for key, value in (metadata or {}).items()},
        )
        return self.repository.save_lock(record)

    def refresh(
        self,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> FileRetentionCleanupLockRecord:
        """刷新当前 owner 的租约；旧 fencing token 不能延长新锁。"""

        current = self._require_current_lock()
        checked_at = _normalize_datetime(now or utc_now())
        self._assert_active_owner(current, owner_id=owner_id, fencing_token=fencing_token, now=checked_at)
        refreshed = current.model_copy(
            update={
                "heartbeat_at": checked_at,
                "expires_at": _expires_at(ttl_seconds=ttl_seconds, now=checked_at),
            }
        )
        return self.repository.save_lock(refreshed)

    def release(
        self,
        *,
        owner_id: str,
        fencing_token: int,
        now: datetime | None = None,
    ) -> FileRetentionCleanupLockRecord:
        """释放当前 owner 的租约；旧 owner/token 不能释放新锁。"""

        current = self._require_current_lock()
        released_at = _normalize_datetime(now or utc_now())
        self._assert_active_owner(current, owner_id=owner_id, fencing_token=fencing_token, now=released_at)
        released = current.model_copy(
            update={
                "status": "released",
                "heartbeat_at": released_at,
                "released_at": released_at,
            }
        )
        return self.repository.save_lock(released)

    def get_status(self, *, now: datetime | None = None) -> FileRetentionCleanupLockStatusReport:
        """读取 cleanup lock effective status，不修改 metadata。"""

        current = self.repository.get_lock(self.lock_name)
        checked_at = _normalize_datetime(now or utc_now())
        if current is None:
            return FileRetentionCleanupLockStatusReport(lock_name=self.lock_name, effective_status="available")
        if current.status == "released":
            effective_status: FileRetentionCleanupLockEffectiveStatus = "released"
        elif current.is_active_at(checked_at):
            effective_status = "active"
        else:
            effective_status = "expired"
        return FileRetentionCleanupLockStatusReport(
            lock_name=current.lock_name,
            effective_status=effective_status,
            owner_id=current.owner_id,
            fencing_token=current.fencing_token,
            acquired_at=current.acquired_at,
            heartbeat_at=current.heartbeat_at,
            expires_at=current.expires_at,
            released_at=current.released_at,
        )

    def _require_current_lock(self) -> FileRetentionCleanupLockRecord:
        """读取当前 lock，不存在时返回标准 conflict。"""

        current = self.repository.get_lock(self.lock_name)
        if current is None:
            raise FileRetentionCleanupLockConflict("cleanup_lock_not_active", "cleanup lock 当前未被持有。")
        return current

    def _assert_active_owner(
        self,
        record: FileRetentionCleanupLockRecord,
        *,
        owner_id: str,
        fencing_token: int,
        now: datetime,
    ) -> None:
        """校验 owner 和 fencing token 仍对应当前 active lock。"""

        normalized_owner = _normalize_owner(owner_id)
        if record.status != "active":
            raise FileRetentionCleanupLockConflict("cleanup_lock_not_active", "cleanup lock 当前不是 active 状态。")
        if not record.is_active_at(now):
            raise FileRetentionCleanupLockConflict("cleanup_lock_expired", "cleanup lock 已过期，需要重新 acquire。")
        if record.owner_id != normalized_owner or record.fencing_token != fencing_token:
            raise FileRetentionCleanupLockConflict(
                "cleanup_lock_fencing_token_mismatch",
                "cleanup lock owner 或 fencing token 不匹配。",
            )


def _normalize_owner(owner_id: str) -> str:
    """规范 owner_id 并拒绝空 owner。"""

    normalized = owner_id.strip()
    if not normalized:
        raise ValueError("owner_id 不能为空。")
    return normalized


def _expires_at(*, ttl_seconds: int, now: datetime | None = None) -> datetime:
    """根据 ttl_seconds 计算租约过期时间。"""

    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds 必须大于 0。")
    return _normalize_datetime(now or utc_now()) + timedelta(seconds=ttl_seconds)


def _normalize_datetime(value: datetime) -> datetime:
    """统一为 timezone-aware UTC-ish datetime，兼容旧 metadata 的 naive 时间。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
