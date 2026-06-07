# File: app/infrastructure/persistence/file/cleanup_runs.py
# Purpose: Persist file-retention cleanup run history for the file metadata backend.

from __future__ import annotations

from app.domains.files.cleanup_history import FileRetentionCleanupRunHistoryRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileRetentionCleanupRunHistoryRepository:
    """用 file backend 读写 cleanup run history metadata。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "config" / "file_retention_cleanup_runs.json"

    def save_run(self, record: FileRetentionCleanupRunHistoryRecord) -> FileRetentionCleanupRunHistoryRecord:
        """创建或替换 cleanup run history 记录。"""

        records = [item for item in self.list_runs() if item.run_id != record.run_id]
        records.append(record)
        self._write_runs(records)
        return record

    def get_run(self, run_id: str) -> FileRetentionCleanupRunHistoryRecord | None:
        """按 run_id 读取 cleanup run history。"""

        for record in self.list_runs():
            if record.run_id == run_id:
                return record
        return None

    def list_runs(self) -> list[FileRetentionCleanupRunHistoryRecord]:
        """读取全部 cleanup run history。"""

        return [
            FileRetentionCleanupRunHistoryRecord.model_validate(item)
            for item in self.backend.read_json(self.path, [])
        ]

    def _write_runs(self, records: list[FileRetentionCleanupRunHistoryRecord]) -> None:
        """稳定排序并写回 cleanup run history 列表。"""

        ordered = sorted(records, key=lambda item: (item.updated_at, item.run_id))
        self.backend.write_json(self.path, [item.model_dump(mode="json") for item in ordered])
