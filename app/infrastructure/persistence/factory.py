# File: app/infrastructure/persistence/factory.py
# Purpose: 按 metadata backend 组合显式端口 adapter。

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.cleanup_lock import FileRetentionCleanupLockRepositoryProtocol
from app.domains.files.cleanup_history import FileRetentionCleanupRunHistoryRepositoryProtocol
from app.domains.files.retention_policy import FileRetentionPolicyRepositoryProtocol
from app.domains.jobs.repository import (
    JobEventRepositoryProtocol,
    JobFileRepositoryProtocol,
    JobSnapshotRepositoryProtocol,
    StageMessageStoreProtocol,
)
from app.domains.resources.repository import ResourceVersionRepositoryProtocol
from app.domains.term_rules.repository import TermRuleAssetRepositoryProtocol, TermRuleProposalRepositoryProtocol
from app.domains.translation.repository import TranslationTermRepositoryProtocol
from app.infrastructure.persistence.file import (
    FileAuditEventRepository,
    FileDocumentFileRepository,
    FileDocumentJobEventRepository,
    FileDocumentJobRepository,
    FileJobEventRepository,
    FileJobFileRepository,
    FileJobSnapshotRepository,
    FilePersistenceBackend,
    FileRetentionCleanupLockRepository,
    FileRetentionCleanupRunHistoryRepository,
    FileRetentionPolicyRepository,
    FileStageMessageStore,
)
from app.infrastructure.persistence.mysql import (
    ConnectFactory,
    MysqlAuditEventRepository,
    MysqlDocumentFileRepository,
    MysqlDocumentJobEventRepository,
    MysqlDocumentJobRepository,
    MysqlJobEventRepository,
    MysqlJobFileRepository,
    MysqlJobSnapshotRepository,
    MysqlPersistenceBackend,
    MysqlPersistenceConfig,
    MysqlRetentionCleanupLockRepository,
    MysqlRetentionCleanupRunHistoryRepository,
    MysqlRetentionPolicyRepository,
    MysqlResourceVersionRepository,
    MysqlStageMessageStore,
    MysqlTermRuleAssetRepository,
    MysqlTermRuleProposalRepository,
    MysqlTranslationTermRepository,
)
from app.infrastructure.persistence.sqlite import (
    SqliteAuditEventRepository,
    SqliteDocumentFileRepository,
    SqliteDocumentJobEventRepository,
    SqliteDocumentJobRepository,
    SqliteJobEventRepository,
    SqliteJobFileRepository,
    SqliteJobSnapshotRepository,
    SqlitePersistenceBackend,
    SqliteRetentionCleanupLockRepository,
    SqliteRetentionCleanupRunHistoryRepository,
    SqliteRetentionPolicyRepository,
    SqliteStageMessageStore,
)


@dataclass(frozen=True, slots=True)
class PersistenceAdapters:
    """运行时显式持有的 metadata persistence 端口集合。"""

    backend_name: str
    job_repository: JobSnapshotRepositoryProtocol
    job_file_repository: JobFileRepositoryProtocol
    job_event_repository: JobEventRepositoryProtocol
    audit_event_repository: AuditEventRepositoryProtocol
    document_file_repository: DocumentFileRepositoryProtocol
    file_retention_policy_repository: FileRetentionPolicyRepositoryProtocol
    file_retention_cleanup_lock_repository: FileRetentionCleanupLockRepositoryProtocol
    file_retention_cleanup_run_history_repository: FileRetentionCleanupRunHistoryRepositoryProtocol
    document_job_repository: DocumentJobRepositoryProtocol
    document_job_event_repository: DocumentJobEventRepositoryProtocol
    stage_message_store: StageMessageStoreProtocol
    resource_version_repository: ResourceVersionRepositoryProtocol | None = None
    term_rule_proposal_repository: TermRuleProposalRepositoryProtocol | None = None
    term_rule_asset_repository: TermRuleAssetRepositoryProtocol | None = None
    translation_term_repository: TranslationTermRepositoryProtocol | None = None


def build_file_persistence_adapters(data_dir: Path) -> PersistenceAdapters:
    """为 local file metadata backend 构造端口 adapter。"""

    backend = FilePersistenceBackend(data_dir)
    return PersistenceAdapters(
        backend_name="file",
        job_repository=FileJobSnapshotRepository(backend),
        job_file_repository=FileJobFileRepository(backend),
        job_event_repository=FileJobEventRepository(backend),
        audit_event_repository=FileAuditEventRepository(backend),
        document_file_repository=FileDocumentFileRepository(backend),
        file_retention_policy_repository=FileRetentionPolicyRepository(backend),
        file_retention_cleanup_lock_repository=FileRetentionCleanupLockRepository(backend),
        file_retention_cleanup_run_history_repository=FileRetentionCleanupRunHistoryRepository(backend),
        document_job_repository=FileDocumentJobRepository(backend),
        document_job_event_repository=FileDocumentJobEventRepository(backend),
        stage_message_store=FileStageMessageStore(backend),
        resource_version_repository=None,
        term_rule_proposal_repository=None,
        term_rule_asset_repository=None,
        translation_term_repository=None,
    )


def build_sqlite_persistence_adapters(database_path: Path) -> PersistenceAdapters:
    """为 sqlite metadata backend 构造端口 adapter。"""

    backend = SqlitePersistenceBackend(database_path)
    return PersistenceAdapters(
        backend_name="database",
        job_repository=SqliteJobSnapshotRepository(backend),
        job_file_repository=SqliteJobFileRepository(backend),
        job_event_repository=SqliteJobEventRepository(backend),
        audit_event_repository=SqliteAuditEventRepository(backend),
        document_file_repository=SqliteDocumentFileRepository(backend),
        file_retention_policy_repository=SqliteRetentionPolicyRepository(backend),
        file_retention_cleanup_lock_repository=SqliteRetentionCleanupLockRepository(backend),
        file_retention_cleanup_run_history_repository=SqliteRetentionCleanupRunHistoryRepository(backend),
        document_job_repository=SqliteDocumentJobRepository(backend),
        document_job_event_repository=SqliteDocumentJobEventRepository(backend),
        stage_message_store=SqliteStageMessageStore(backend),
        resource_version_repository=None,
        term_rule_proposal_repository=None,
        term_rule_asset_repository=None,
        translation_term_repository=None,
    )


def build_mysql_persistence_adapters(
    config: MysqlPersistenceConfig,
    *,
    connect_factory: ConnectFactory | None = None,
) -> PersistenceAdapters:
    """为 MySQL metadata backend 构造端口 adapter。"""

    backend = MysqlPersistenceBackend(config, connect_factory=connect_factory)
    return PersistenceAdapters(
        backend_name="mysql",
        job_repository=MysqlJobSnapshotRepository(backend),
        job_file_repository=MysqlJobFileRepository(backend),
        job_event_repository=MysqlJobEventRepository(backend),
        audit_event_repository=MysqlAuditEventRepository(backend),
        document_file_repository=MysqlDocumentFileRepository(backend),
        file_retention_policy_repository=MysqlRetentionPolicyRepository(backend),
        file_retention_cleanup_lock_repository=MysqlRetentionCleanupLockRepository(backend),
        file_retention_cleanup_run_history_repository=MysqlRetentionCleanupRunHistoryRepository(backend),
        document_job_repository=MysqlDocumentJobRepository(backend),
        document_job_event_repository=MysqlDocumentJobEventRepository(backend),
        stage_message_store=MysqlStageMessageStore(backend),
        resource_version_repository=MysqlResourceVersionRepository(backend),
        term_rule_proposal_repository=MysqlTermRuleProposalRepository(backend),
        term_rule_asset_repository=MysqlTermRuleAssetRepository(backend),
        translation_term_repository=MysqlTranslationTermRepository(backend),
    )


def build_persistence_adapters(
    settings: Settings,
    *,
    mysql_connect_factory: ConnectFactory | None = None,
) -> PersistenceAdapters:
    """根据 Settings 选择当前 metadata backend，并保持原 backend 名称语义。"""

    if settings.jobs_repository_backend == "database":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        return build_sqlite_persistence_adapters(settings.jobs_metadata_database_file)
    if settings.jobs_repository_backend == "mysql":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        return build_mysql_persistence_adapters(
            MysqlPersistenceConfig(
                host=settings.jobs_mysql_host,
                port=settings.jobs_mysql_port,
                user=settings.jobs_mysql_user,
                password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database,
                charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            ),
            connect_factory=mysql_connect_factory,
        )
    return build_file_persistence_adapters(settings.data_path)
