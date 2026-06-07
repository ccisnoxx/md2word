# File: app/infrastructure/persistence/file/cleanup_locks.py
# Purpose: Persist file-retention cleanup locks for the file metadata backend.

from __future__ import annotations

from app.domains.files.cleanup_lock import FileRetentionCleanupLockRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileRetentionCleanupLockRepository:
    """用 file backend 读写 cleanup lock metadata。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "config" / "file_retention_cleanup_locks.json"

    def save_lock(self, record: FileRetentionCleanupLockRecord) -> FileRetentionCleanupLockRecord:
        """创建或替换 cleanup lock 记录。"""

        records = [item for item in self._list_locks() if item.lock_name != record.lock_name]
        records.append(record)
        ordered = sorted(records, key=lambda item: item.lock_name)
        self.backend.write_json(self.path, [item.model_dump(mode="json") for item in ordered])
        return record

    def get_lock(self, lock_name: str) -> FileRetentionCleanupLockRecord | None:
        """按 lock_name 读取 cleanup lock。"""

        for record in self._list_locks():
            if record.lock_name == lock_name:
                return record
        return None

    def _list_locks(self) -> list[FileRetentionCleanupLockRecord]:
        """读取全部 cleanup lock 记录。"""

        return [
            FileRetentionCleanupLockRecord.model_validate(item)
            for item in self.backend.read_json(self.path, [])
        ]
