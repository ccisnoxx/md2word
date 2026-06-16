# File: app/infrastructure/persistence/file/retention_policies.py
# Purpose: Persist document_files retention policies for the file metadata backend.

from __future__ import annotations

from typing import Any

from app.domains.files.retention_policy import FileRetentionPolicyRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileRetentionPolicyRepository:
    """用 file backend 读写 document_files retention policy metadata。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend
        self.path = backend.data_dir / "config" / "file_retention_policies.json"

    def create_policy(self, record: FileRetentionPolicyRecord) -> FileRetentionPolicyRecord:
        """创建策略记录；如果 ID 已存在则覆盖同 ID 记录。"""

        records = [item for item in self.list_policies() if item.policy_id != record.policy_id]
        records.append(record)
        self._write_policies(records)
        return record

    def get_policy(self, policy_id: str) -> FileRetentionPolicyRecord | None:
        """按 policy_id 读取策略记录。"""

        for record in self.list_policies():
            if record.policy_id == policy_id:
                return record
        return None

    def list_policies(self) -> list[FileRetentionPolicyRecord]:
        """读取全部策略记录。"""

        return [
            FileRetentionPolicyRecord.model_validate(item)
            for item in self.backend.read_json(self.path, [])
        ]

    def update_policy(self, policy_id: str, **patch: Any) -> FileRetentionPolicyRecord:
        """更新策略记录；不存在时抛出 FileNotFoundError。"""

        existing = self.get_policy(policy_id)
        if existing is None:
            raise FileNotFoundError(f"保留策略不存在: {policy_id}")
        updated = FileRetentionPolicyRecord(**existing.model_copy(update=patch).model_dump(mode="python"))
        records = [item for item in self.list_policies() if item.policy_id != policy_id]
        records.append(updated)
        self._write_policies(records)
        return updated

    def _write_policies(self, records: list[FileRetentionPolicyRecord]) -> None:
        """稳定排序并写回策略列表。"""

        ordered = sorted(records, key=lambda item: (item.created_at, item.policy_id))
        self.backend.write_json(self.path, [item.model_dump(mode="json") for item in ordered])
