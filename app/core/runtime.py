from __future__ import annotations

# app/core/runtime.py: 保存 FastAPI 进程内共享的应用服务和边界端口。

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.config import Settings

if TYPE_CHECKING:
    from app.domains.audit.repository import AuditEventRepositoryProtocol
    from app.domains.document_jobs.repository import (
        DocumentJobEventRepositoryProtocol,
        DocumentJobRepositoryProtocol,
    )
    from app.domains.files.repository import DocumentFileRepositoryProtocol
    from app.domains.jobs.repository import (
        JobEventRepositoryProtocol,
        JobFileRepositoryProtocol,
        JobSnapshotRepositoryProtocol,
        StageMessageStoreProtocol,
    )
    from app.domains.jobs.artifact_storage import ArtifactStorageProtocol
    from app.domains.jobs.dispatch import StageDispatcherProtocol
    from app.infrastructure.persistence import PersistenceAdapters


@dataclass(slots=True)
class AppRuntime:
    settings: Settings
    persistence_adapters: PersistenceAdapters
    job_repository: JobSnapshotRepositoryProtocol
    job_file_repository: JobFileRepositoryProtocol
    job_event_repository: JobEventRepositoryProtocol
    audit_event_repository: AuditEventRepositoryProtocol
    document_file_repository: DocumentFileRepositoryProtocol
    document_job_repository: DocumentJobRepositoryProtocol
    document_job_event_repository: DocumentJobEventRepositoryProtocol
    audit_service: Any
    auth_service: Any
    file_upload_service: Any
    document_ir_service: Any
    translation_provider: Any
    document_ir_translation_service: Any
    translation_audit_service: Any
    term_version_service: Any
    document_word_renderer: Any
    document_job_service: Any
    document_job_execution_service: Any
    document_job_task_queue: Any | None
    health_service: Any
    template_read_service: Any
    term_rule_service: Any
    term_rule_import_validation_service: Any
    term_rule_file_sync_service: Any
    term_rule_set_version_service: Any | None
    translation_profile_service: Any | None
    resource_version_service: Any | None
    job_resource_snapshot_service: Any
    artifact_service: Any
    artifact_storage: ArtifactStorageProtocol
    command_service: Any
    lifecycle_service: Any
    query_service: Any
    stage_service: Any
    stage_dispatcher: StageDispatcherProtocol
    stage_message_store: StageMessageStoreProtocol
