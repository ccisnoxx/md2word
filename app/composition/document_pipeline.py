from __future__ import annotations

# app/composition/document_pipeline.py: 装配 MinerU→DocumentIR→翻译→Word 渲染→预览的正式文档流水线、
# Worker 投递端口、启动恢复与 document_jobs 应用层用例。

from dataclasses import dataclass
from typing import Any

from app.composition.platform import PlatformServices
from app.core.config import Settings
from app.domains.document_jobs.execution import (
    CeleryDocumentJobTaskQueue,
    CeleryDocumentTranslationBatchTaskQueue,
    DocumentJobExecutionService,
    EagerDocumentJobTaskQueue,
    EagerDocumentTranslationBatchTaskQueue,
)
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.recovery import DocumentJobRecoveryService
from app.domains.document_jobs.use_cases import DocumentJobUseCases, build_document_job_use_cases
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.mineru.config import MinerUConfigService
from app.domains.templates.read_service import TemplateReadService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.provider import build_translation_provider
from app.domains.translation.provider_config import AiProviderConfigService
from app.domains.translation.term_version_service import TermVersionService
from app.infrastructure.pdf_crop import PopplerPdfPageRasterizer, PopplerPdfTableCropProvider
from app.infrastructure.persistence import PersistenceAdapters
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.page_degradation import PageDegradationPolicy
from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider
from app.services.renderer import DocumentIRWordRenderer


@dataclass(frozen=True)
class DocumentPipeline:
    document_ir_service: MinerUToDocumentIRService
    ai_provider_config_service: AiProviderConfigService
    mineru_config_service: MinerUConfigService
    translation_provider: Any
    document_ir_translation_service: DocumentIRTranslationService
    translation_audit_service: TranslationAuditService
    term_version_service: TermVersionService
    job_resource_snapshot_service: JobResourceSnapshotService
    template_read_service: TemplateReadService
    document_word_renderer: DocumentIRWordRenderer
    word_preview_service: DocumentJobPreviewService
    document_job_execution_service: DocumentJobExecutionService
    document_job_task_queue: Any | None
    document_job_recovery_service: DocumentJobRecoveryService
    document_job_use_cases: DocumentJobUseCases
    document_job_incident_service: DocumentJobIncidentService


def _build_document_job_task_queue(
    settings: Settings,
    execution_service: DocumentJobExecutionService,
):
    """按配置选择 document_jobs Worker 投递端口。"""

    if settings.document_jobs_worker_backend == "celery":
        return CeleryDocumentJobTaskQueue(settings)
    if settings.document_jobs_worker_backend == "eager":
        return EagerDocumentJobTaskQueue(execution_service)
    return None


def _build_document_translation_batch_task_queue(
    settings: Settings,
    execution_service: DocumentJobExecutionService,
):
    """按配置选择 translation provider batch task 投递端口。"""

    if settings.document_jobs_worker_backend == "celery":
        return CeleryDocumentTranslationBatchTaskQueue(settings)
    if settings.document_jobs_worker_backend == "eager":
        return EagerDocumentTranslationBatchTaskQueue(execution_service)
    return None


def build_document_pipeline(
    settings: Settings,
    adapters: PersistenceAdapters,
    platform: PlatformServices,
) -> DocumentPipeline:
    """只构造，不执行种子写入；翻译术语 CSV 导入等 bootstrap 由 composition.startup 统一执行。"""

    file_upload_service = platform.file_upload_service
    audit_service = platform.audit_service
    document_ir_service = MinerUToDocumentIRService(pdf_crop_provider=PopplerPdfTableCropProvider(),
                                                    page_rasterizer=PopplerPdfPageRasterizer(),
                                                    degradation_policy=PageDegradationPolicy(
                                                        max_page_ratio=settings.page_degradation_max_ratio,
                                                        allow_single_page=settings.page_degradation_allow_single_page))
    ai_provider_config_service = AiProviderConfigService(settings)
    mineru_config_service = MinerUConfigService(settings)
    translation_provider = build_translation_provider(
        settings,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    document_ir_translation_service = DocumentIRTranslationService(
        translation_provider, table_context_enabled=settings.translation_table_context_enabled,
    )
    translation_audit_service = TranslationAuditService(
        settings,
        file_upload_service,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    term_version_service = TermVersionService(
        settings.translation_terms_file,
        default_term_version_id=settings.default_translation_term_version_id,
        repository=adapters.translation_term_repository,
    )
    job_resource_snapshot_service = JobResourceSnapshotService(
        settings,
        platform.resource_version_service,
        adapters.translation_term_repository,
    )
    template_read_service = TemplateReadService(
        settings,
        platform.resource_version_service,
        audit_service,
        document_job_repository=adapters.document_job_repository,
    )
    document_word_renderer = DocumentIRWordRenderer()
    # 启动期校验页面质量策略配置，配置非法时在构造预览与执行服务前失败。
    settings.page_quality_policy()
    preview_provider = SandboxWordPreviewProvider(
        backend=settings.word_preview_backend, launcher=settings.word_preview_launcher,
        profile_path=settings.word_preview_profile_path, profile_id=settings.word_preview_profile_id,
        profile_sha256=settings.word_preview_profile_sha256,
    )
    word_preview_service = DocumentJobPreviewService(
        settings, adapters.document_job_repository, adapters.document_job_event_repository,
        adapters.document_file_repository, file_upload_service, audit_service=audit_service,
        provider=preview_provider, observer=preview_provider,
    )
    document_job_execution_service = DocumentJobExecutionService(
        settings,
        adapters.document_job_repository,
        adapters.document_job_event_repository,
        adapters.document_job_callback_message_store,
        adapters.document_job_translation_batch_repository,
        adapters.document_file_repository,
        file_upload_service,
        document_ir_service,
        template_read_service,
        document_word_renderer,
        mineru_config_service.get_effective_config,
        document_ir_translation_service,
        term_version_service,
        translation_audit_service,
        job_resource_snapshot_service,
        word_preview_service=word_preview_service,
    )
    document_job_task_queue = _build_document_job_task_queue(settings, document_job_execution_service)
    # 批次队列依赖已构造的执行服务，执行服务又持有翻译协作者，因此在两者都就绪后回填。
    document_job_execution_service.translation_batches.set_translation_batch_task_queue(
        _build_document_translation_batch_task_queue(settings, document_job_execution_service))
    document_job_recovery_service = DocumentJobRecoveryService(
        settings,
        adapters.document_job_repository,
        adapters.document_job_event_repository,
        adapters.document_job_callback_message_store,
        document_job_task_queue,
    )
    document_job_use_cases = build_document_job_use_cases(
        settings,
        adapters.document_job_repository,
        adapters.document_job_event_repository,
        adapters.document_file_repository,
        document_job_task_queue,
        template_read_service,
        term_version_service,
        job_resource_snapshot_service,
        document_job_translation_batch_repository=adapters.document_job_translation_batch_repository,
        file_upload_service=file_upload_service,
        word_preview_service=word_preview_service,
        audit_service=audit_service,
        translation_generation_summarizer=document_job_execution_service.translation_batches,
    )
    return DocumentPipeline(
        document_ir_service=document_ir_service,
        ai_provider_config_service=ai_provider_config_service,
        mineru_config_service=mineru_config_service,
        translation_provider=translation_provider,
        document_ir_translation_service=document_ir_translation_service,
        translation_audit_service=translation_audit_service,
        term_version_service=term_version_service,
        job_resource_snapshot_service=job_resource_snapshot_service,
        template_read_service=template_read_service,
        document_word_renderer=document_word_renderer,
        word_preview_service=word_preview_service,
        document_job_execution_service=document_job_execution_service,
        document_job_task_queue=document_job_task_queue,
        document_job_recovery_service=document_job_recovery_service,
        document_job_use_cases=document_job_use_cases,
        document_job_incident_service=DocumentJobIncidentService(
            file_repository=adapters.document_file_repository,
            access=document_job_use_cases.access,
            read_model=document_job_use_cases.read_model,
            queries=document_job_use_cases.queries,
            submission=document_job_use_cases.submission,
        ),
    )
