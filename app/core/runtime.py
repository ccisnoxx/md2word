# 文件：app/core/runtime.py
# 用途： 保存 FastAPI 进程内共享的应用服务和边界端口。

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.config import Settings

if TYPE_CHECKING:
    from app.domains.acceptance.repository import AcceptanceRunRepositoryProtocol
    from app.domains.audit.repository import AuditEventRepositoryProtocol
    from app.domains.document_jobs.repository import (
        DocumentJobCallbackMessageStoreProtocol,
        DocumentJobEventRepositoryProtocol,
        DocumentJobRepositoryProtocol,
        DocumentJobTranslationBatchRepositoryProtocol,
    )
    from app.domains.document_jobs.recovery import DocumentJobRecoveryService
    from app.domains.files.repository import DocumentFileRepositoryProtocol
    from app.domains.jobs.repository import (
        JobEventRepositoryProtocol,
        JobFileRepositoryProtocol,
        JobSnapshotRepositoryProtocol,
        StageMessageStoreProtocol,
    )
    from app.domains.jobs.artifact_storage import ArtifactStorageProtocol
    from app.domains.jobs.dispatch import StageDispatcherProtocol
    from app.domains.saved_views.repository import SavedViewRepositoryProtocol
    from app.domains.users.repository import InternalUserRepositoryProtocol
    from app.infrastructure.persistence import PersistenceAdapters


@dataclass(slots=True)
class AppRuntime:
    """集中保存当前 FastAPI 进程的共享服务、repository 和外部边界端口。"""

    settings: Settings
    persistence_adapters: PersistenceAdapters
    job_repository: JobSnapshotRepositoryProtocol
    job_file_repository: JobFileRepositoryProtocol
    job_event_repository: JobEventRepositoryProtocol
    audit_event_repository: AuditEventRepositoryProtocol
    acceptance_run_repository: AcceptanceRunRepositoryProtocol
    document_file_repository: DocumentFileRepositoryProtocol
    file_retention_policy_repository: Any
    file_retention_cleanup_lock_repository: Any
    file_retention_cleanup_run_history_repository: Any
    document_job_repository: DocumentJobRepositoryProtocol
    document_job_event_repository: DocumentJobEventRepositoryProtocol
    document_job_callback_message_store: DocumentJobCallbackMessageStoreProtocol
    document_job_translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol
    internal_user_repository: InternalUserRepositoryProtocol
    saved_view_repository: SavedViewRepositoryProtocol
    terminology_release_repository: Any
    audit_service: Any
    acceptance_run_service: Any
    auth_service: Any
    internal_user_management_service: Any
    file_upload_service: Any
    file_retention_policy_service: Any
    document_ir_service: Any
    ai_provider_config_service: Any
    mineru_config_service: Any
    translation_provider: Any
    document_ir_translation_service: Any
    translation_audit_service: Any
    term_version_service: Any
    document_word_renderer: Any
    document_job_service: Any
    document_job_incident_service: Any
    saved_view_service: Any
    document_job_execution_service: Any
    document_job_recovery_service: DocumentJobRecoveryService
    document_job_task_queue: Any | None
    health_service: Any
    template_read_service: Any
    term_rule_service: Any
    term_rule_import_validation_service: Any
    term_rule_file_sync_service: Any
    term_rule_set_version_service: Any | None
    term_rule_proposal_service: Any | None
    term_rule_review_service: Any | None
    translation_term_set_version_service: Any | None
    translation_term_proposal_service: Any | None
    terminology_release_service: Any
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
    word_preview_service: Any | None = None
    alert_delivery_provider: Any | None = None
    secret_resolver: Any | None = None
