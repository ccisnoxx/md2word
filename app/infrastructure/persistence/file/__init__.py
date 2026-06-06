from __future__ import annotations

# File: app/infrastructure/persistence/file/__init__.py
# Purpose: 导出 file metadata backend 的端口 adapter。

from app.infrastructure.persistence.file.audit import FileAuditEventRepository
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import (
    FileDocumentJobEventRepository,
    FileDocumentJobRepository,
)
from app.infrastructure.persistence.file.files import FileDocumentFileRepository, FileJobFileRepository
from app.infrastructure.persistence.file.jobs import FileJobEventRepository, FileJobSnapshotRepository
from app.infrastructure.persistence.file.retention_policies import FileRetentionPolicyRepository
from app.infrastructure.persistence.file.stage_messages import FileStageMessageStore

__all__ = [
    "FileAuditEventRepository",
    "FileDocumentFileRepository",
    "FileDocumentJobEventRepository",
    "FileDocumentJobRepository",
    "FileJobEventRepository",
    "FileJobFileRepository",
    "FileJobSnapshotRepository",
    "FilePersistenceBackend",
    "FileRetentionPolicyRepository",
    "FileStageMessageStore",
]
