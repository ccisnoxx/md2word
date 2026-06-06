from __future__ import annotations

# File: app/infrastructure/persistence/mysql/__init__.py
# Purpose: 导出 MySQL metadata backend 的端口 adapter。

from app.infrastructure.persistence.mysql.audit import MysqlAuditEventRepository
from app.infrastructure.persistence.mysql.backend import (
    ConnectFactory,
    MysqlPersistenceBackend,
    MysqlPersistenceConfig,
)
from app.infrastructure.persistence.mysql.document_jobs import (
    MysqlDocumentJobEventRepository,
    MysqlDocumentJobRepository,
)
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository, MysqlJobFileRepository
from app.infrastructure.persistence.mysql.jobs import MysqlJobEventRepository, MysqlJobSnapshotRepository
from app.infrastructure.persistence.mysql.retention_policies import MysqlRetentionPolicyRepository
from app.infrastructure.persistence.mysql.resources import MysqlResourceVersionRepository
from app.infrastructure.persistence.mysql.stage_messages import MysqlStageMessageStore
from app.infrastructure.persistence.mysql.term_assets import MysqlTermRuleAssetRepository, MysqlTranslationTermRepository
from app.infrastructure.persistence.mysql.term_rule_proposals import MysqlTermRuleProposalRepository

__all__ = [
    "ConnectFactory",
    "MysqlAuditEventRepository",
    "MysqlDocumentFileRepository",
    "MysqlDocumentJobEventRepository",
    "MysqlDocumentJobRepository",
    "MysqlJobEventRepository",
    "MysqlJobFileRepository",
    "MysqlJobSnapshotRepository",
    "MysqlPersistenceBackend",
    "MysqlPersistenceConfig",
    "MysqlRetentionPolicyRepository",
    "MysqlResourceVersionRepository",
    "MysqlStageMessageStore",
    "MysqlTermRuleAssetRepository",
    "MysqlTermRuleProposalRepository",
    "MysqlTranslationTermRepository",
]
