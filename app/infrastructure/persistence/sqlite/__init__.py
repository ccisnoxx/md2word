from __future__ import annotations

# File: app/infrastructure/persistence/sqlite/__init__.py
# Purpose: 导出 sqlite metadata backend 的端口 adapter。

from app.infrastructure.persistence.sqlite.audit import SqliteAuditEventRepository
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import (
    SqliteDocumentJobEventRepository,
    SqliteDocumentJobRepository,
)
from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository, SqliteJobFileRepository
from app.infrastructure.persistence.sqlite.jobs import SqliteJobEventRepository, SqliteJobSnapshotRepository
from app.infrastructure.persistence.sqlite.retention_policies import SqliteRetentionPolicyRepository
from app.infrastructure.persistence.sqlite.stage_messages import SqliteStageMessageStore

__all__ = [
    "SqliteAuditEventRepository",
    "SqliteDocumentFileRepository",
    "SqliteDocumentJobEventRepository",
    "SqliteDocumentJobRepository",
    "SqliteJobEventRepository",
    "SqliteJobFileRepository",
    "SqliteJobSnapshotRepository",
    "SqlitePersistenceBackend",
    "SqliteRetentionPolicyRepository",
    "SqliteStageMessageStore",
]
