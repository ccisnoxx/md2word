# File: app/infrastructure/persistence/file/__init__.py
# Purpose: 导出 file metadata backend 的端口 adapter。

from __future__ import annotations

from app.infrastructure.persistence.file.audit import FileAuditEventRepository
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.cleanup_locks import FileRetentionCleanupLockRepository
from app.infrastructure.persistence.file.cleanup_runs import FileRetentionCleanupRunHistoryRepository
from app.infrastructure.persistence.file.document_jobs import (
    FileDocumentJobCallbackMessageStore,
    FileDocumentJobEventRepository,
    FileDocumentJobRepository,
)
from app.infrastructure.persistence.file.files import FileDocumentFileRepository, FileJobFileRepository
from app.infrastructure.persistence.file.internal_users import FileInternalUserRepository
from app.infrastructure.persistence.file.jobs import FileJobEventRepository, FileJobSnapshotRepository
from app.infrastructure.persistence.file.retention_policies import FileRetentionPolicyRepository
from app.infrastructure.persistence.file.saved_views import FileSavedViewRepository
from app.infrastructure.persistence.file.stage_messages import FileStageMessageStore
from app.infrastructure.persistence.file.terminology_releases import FileTerminologyReleaseRepository

__all__ = [
    "FileAuditEventRepository",
    "FileDocumentFileRepository",
    "FileDocumentJobCallbackMessageStore",
    "FileDocumentJobEventRepository",
    "FileDocumentJobRepository",
    "FileInternalUserRepository",
    "FileJobEventRepository",
    "FileJobFileRepository",
    "FileJobSnapshotRepository",
    "FilePersistenceBackend",
    "FileRetentionCleanupLockRepository",
    "FileRetentionCleanupRunHistoryRepository",
    "FileRetentionPolicyRepository",
    "FileSavedViewRepository",
    "FileStageMessageStore",
    "FileTerminologyReleaseRepository",
]
