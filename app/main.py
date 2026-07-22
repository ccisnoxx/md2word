# File: app/main.py
# Purpose: 组装 FastAPI 应用及当前进程的运行时依赖。

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_api_error_handlers
from app.api.v1.router import router as api_v1_router
from app.conversion.entrypoint import create_conversion_entrypoint
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.runtime import AppRuntime
from app.domains.term_rules.file_repository import FileTermRuleRepository
from app.infrastructure.persistence import build_persistence_adapters
from app.services.health_service import HealthService
from app.domains.acceptance.service import AcceptanceRunService
from app.domains.audit.service import AuditService
from app.services.auth import AuthService
from app.domains.document_jobs.execution import (
    CeleryDocumentJobTaskQueue,
    CeleryDocumentTranslationBatchTaskQueue,
    DocumentJobExecutionService,
    EagerDocumentJobTaskQueue,
    EagerDocumentTranslationBatchTaskQueue,
)
from app.domains.document_jobs.recovery import DocumentJobRecoveryService
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.service import DocumentJobService
from app.domains.files import FileRetentionPolicyService, FileUploadService
from app.services.document_ir import MinerUToDocumentIRService
from app.domains.jobs.artifact_storage import LocalArtifactStorageAdapter
from app.domains.jobs.artifacts import JobArtifactService
from app.domains.jobs.command import JobCommandService
from app.domains.jobs.dispatch import ExternalWorkerStageDispatcher, InProcessStageDispatcher
from app.domains.jobs.lifecycle import JobLifecycleService
from app.domains.jobs.object_artifact_storage import ObjectArtifactStorageAdapter, S3ArtifactStorageAdapter
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.jobs.query import JobQueryService
from app.domains.jobs.stage import JobStageService
from app.domains.mineru.config import MinerUConfigService
from app.domains.ops.real_alert_delivery import EnvironmentSecretResolver, SlackWebhookAlertDeliveryProvider
from app.services.renderer import DocumentIRWordRenderer
from app.domains.resources.service import ResourceVersionService
from app.domains.saved_views.service import SavedViewService
from app.domains.term_rules.bootstrap import TermRuleBootstrapService
from app.domains.term_rules.import_validation import TermRuleImportValidationService
from app.domains.term_rules.proposals_service import TermRuleProposalService
from app.domains.term_rules.review_service import TermRuleReviewService
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.sync_files import TermRuleFileSyncService
from app.domains.term_rules.versioning_service import TermRuleSetVersionService
from app.domains.terminology.service import TerminologyReleaseService
from app.domains.templates.read_service import TemplateReadService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.provider_config import AiProviderConfigService
from app.domains.translation.profiles_service import TranslationProfileVersionService
from app.domains.translation.proposals_service import TranslationTermProposalService
from app.domains.translation.provider import build_translation_provider
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService
from app.domains.translation.term_version_service import TermVersionService
from app.domains.users.service import InternalUserManagementService

NON_PRODUCTION_ENVS = {"dev", "local", "test"}


def _build_artifact_storage(settings: Settings, artifact_service: JobArtifactService):
    """按配置选择 artifact storage adapter；默认仍保持 local file backend。"""

    if settings.jobs_artifact_storage_backend == "local_object":
        return ObjectArtifactStorageAdapter(
            artifact_service,
            settings.jobs_artifact_object_store_dir,
        ), "local_object"
    if settings.jobs_artifact_storage_backend == "s3":
        return S3ArtifactStorageAdapter(
            artifact_service,
            bucket=settings.jobs_artifact_s3_bucket,
            endpoint_url=settings.jobs_artifact_s3_endpoint_url or None,
            region_name=settings.jobs_artifact_s3_region or None,
            access_key_id=settings.jobs_artifact_s3_access_key_id or None,
            secret_access_key=settings.jobs_artifact_s3_secret_access_key or None,
            key_prefix=settings.jobs_artifact_s3_key_prefix,
            public_base_url=settings.jobs_artifact_s3_public_base_url,
            download_mode=settings.jobs_artifact_s3_download_mode,
            presign_expires_seconds=settings.jobs_artifact_s3_presign_expires_seconds,
        ), "s3"
    return LocalArtifactStorageAdapter(artifact_service), "local_file"


def _build_stage_dispatcher(settings: Settings, stage_service: JobStageService):
    """按 worker 模式选择 API 请求进程的 stage 调度端口。"""

    if settings.jobs_worker_mode == "external":
        return ExternalWorkerStageDispatcher(), "external_worker"
    return InProcessStageDispatcher(stage_service), "background_tasks"


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


def _validate_runtime_guardrails(settings: Settings) -> None:
    """阻止近生产环境以 open jobs 访问模式启动。"""

    production_like = (
        settings.app_env.strip().lower() not in NON_PRODUCTION_ENVS
        or settings.public_deployment_mode == "single_tenant_public"
    )
    if production_like and settings.jobs_access_mode == "open":
        raise RuntimeError(
            "JOBS_ACCESS_MODE=open 不允许用于生产或 single_tenant_public 部署；"
            "请改用 JOBS_ACCESS_MODE=token 或 admin，并配置对应 token。"
        )


def build_runtime(settings: Settings | None = None) -> AppRuntime:
    """构建当前进程共享运行时，并注入 API、任务、文件和只读观测服务依赖。"""

    resolved_settings = settings or Settings()
    _validate_runtime_guardrails(resolved_settings)
    configure_logging(resolved_settings.app_env, resolved_settings.log_format)
    persistence_adapters = build_persistence_adapters(resolved_settings)
    repository_backend = persistence_adapters.backend_name
    job_repository = persistence_adapters.job_repository
    job_file_repository = persistence_adapters.job_file_repository
    job_event_repository = persistence_adapters.job_event_repository
    audit_event_repository = persistence_adapters.audit_event_repository
    acceptance_run_repository = persistence_adapters.acceptance_run_repository
    document_file_repository = persistence_adapters.document_file_repository
    file_retention_policy_repository = persistence_adapters.file_retention_policy_repository
    file_retention_cleanup_lock_repository = persistence_adapters.file_retention_cleanup_lock_repository
    file_retention_cleanup_run_history_repository = persistence_adapters.file_retention_cleanup_run_history_repository
    document_job_repository = persistence_adapters.document_job_repository
    document_job_event_repository = persistence_adapters.document_job_event_repository
    document_job_callback_message_store = persistence_adapters.document_job_callback_message_store
    document_job_translation_batch_repository = persistence_adapters.document_job_translation_batch_repository
    internal_user_repository = persistence_adapters.internal_user_repository
    saved_view_repository = persistence_adapters.saved_view_repository
    terminology_release_repository = persistence_adapters.terminology_release_repository
    stage_message_store = persistence_adapters.stage_message_store
    audit_service = AuditService(audit_event_repository)
    acceptance_run_service = AcceptanceRunService(acceptance_run_repository)
    acceptance_run_service.bootstrap_default_runs_if_empty()
    auth_service = AuthService(resolved_settings, internal_user_repository)
    internal_user_management_service = InternalUserManagementService(internal_user_repository)
    file_retention_policy_service = FileRetentionPolicyService(
        resolved_settings,
        file_retention_policy_repository,
        document_file_repository,
    )
    file_upload_service = FileUploadService(
        resolved_settings,
        document_file_repository,
        retention_days_resolver=file_retention_policy_service.resolve_retention_days,
    )
    document_ir_service = MinerUToDocumentIRService()
    ai_provider_config_service = AiProviderConfigService(resolved_settings)
    mineru_config_service = MinerUConfigService(resolved_settings)
    translation_provider = build_translation_provider(
        resolved_settings,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    document_ir_translation_service = DocumentIRTranslationService(translation_provider)
    translation_audit_service = TranslationAuditService(
        resolved_settings,
        file_upload_service,
        config_resolver=ai_provider_config_service.get_effective_config,
    )
    term_version_service = TermVersionService(
        resolved_settings.translation_terms_file,
        default_term_version_id=resolved_settings.default_translation_term_version_id,
        repository=persistence_adapters.translation_term_repository,
    )
    term_version_service.bootstrap_repository_from_csv_if_empty()
    resource_version_service = (
        ResourceVersionService(persistence_adapters.resource_version_repository)
        if persistence_adapters.resource_version_repository is not None
        else None
    )
    job_resource_snapshot_service = JobResourceSnapshotService(
        resolved_settings,
        resource_version_service,
        persistence_adapters.translation_term_repository,
    )
    template_read_service = TemplateReadService(
        resolved_settings,
        resource_version_service,
        audit_service,
        document_job_repository=document_job_repository,
    )
    document_word_renderer = DocumentIRWordRenderer()
    document_job_execution_service = DocumentJobExecutionService(
        resolved_settings,
        document_job_repository,
        document_job_event_repository,
        document_job_callback_message_store,
        document_job_translation_batch_repository,
        document_file_repository,
        file_upload_service,
        document_ir_service,
        template_read_service,
        document_word_renderer,
        mineru_config_service.get_effective_config,
        document_ir_translation_service,
        term_version_service,
        translation_audit_service,
    )
    document_job_task_queue = _build_document_job_task_queue(resolved_settings, document_job_execution_service)
    document_translation_batch_task_queue = _build_document_translation_batch_task_queue(
        resolved_settings,
        document_job_execution_service,
    )
    document_job_execution_service.set_translation_batch_task_queue(document_translation_batch_task_queue)
    document_job_recovery_service = DocumentJobRecoveryService(
        resolved_settings,
        document_job_repository,
        document_job_event_repository,
        document_job_callback_message_store,
        document_job_task_queue,
    )
    document_job_service = DocumentJobService(
        resolved_settings,
        document_job_repository,
        document_job_event_repository,
        document_file_repository,
        document_job_task_queue,
        template_read_service,
        term_version_service,
        job_resource_snapshot_service,
        document_job_translation_batch_repository=document_job_translation_batch_repository,
        file_upload_service=file_upload_service,
    )
    document_job_incident_service = DocumentJobIncidentService(document_job_service)
    saved_view_service = SavedViewService(saved_view_repository)
    term_rule_repository = FileTermRuleRepository(resolved_settings.term_rules_store_file)
    term_rule_service = TermRuleService(
        term_rule_repository,
        resolved_settings.term_rules_runtime_yaml_file,
        resolved_settings.term_rules_seed_file,
    )
    term_rule_import_validation_service = TermRuleImportValidationService()
    term_rule_file_sync_service = TermRuleFileSyncService(
        term_rule_repository,
        resolved_settings.term_rules_runtime_yaml_file,
        resolved_settings.term_rules_seed_file,
        repository_backend="file",
    )
    term_rule_set_version_service = (
        TermRuleSetVersionService(
            repository=term_rule_repository,
            runtime_yaml_path=resolved_settings.term_rules_runtime_yaml_file,
            resource_version_service=resource_version_service,
            audit_service=audit_service,
            asset_repository=persistence_adapters.term_rule_asset_repository,
        )
        if resource_version_service is not None
        else None
    )
    term_rule_proposal_service = (
        TermRuleProposalService(
            repository=persistence_adapters.term_rule_proposal_repository,
            term_rule_service=term_rule_service,
            term_rule_set_version_service=term_rule_set_version_service,
            audit_service=audit_service,
        )
        if persistence_adapters.term_rule_proposal_repository is not None
        and term_rule_set_version_service is not None
        else None
    )
    term_rule_review_service = (
        TermRuleReviewService(
            repository=persistence_adapters.term_rule_review_repository,
            term_rule_service=term_rule_service,
            term_rule_set_version_service=term_rule_set_version_service,
            audit_service=audit_service,
        )
        if persistence_adapters.term_rule_review_repository is not None
        and term_rule_set_version_service is not None
        else None
    )
    translation_profile_service = (
        TranslationProfileVersionService(resolved_settings, resource_version_service, audit_service)
        if resource_version_service is not None
        else None
    )
    translation_term_set_version_service = (
        TranslationTermSetVersionService(persistence_adapters.translation_term_repository, audit_service)
        if persistence_adapters.translation_term_repository is not None
        else None
    )
    translation_term_proposal_service = (
        TranslationTermProposalService(
            repository=persistence_adapters.translation_term_repository,
            term_set_version_service=translation_term_set_version_service,
            audit_service=audit_service,
        )
        if persistence_adapters.translation_term_repository is not None
        and translation_term_set_version_service is not None
        else None
    )
    terminology_release_service = TerminologyReleaseService(
        terminology_release_repository,
        translation_term_repository=persistence_adapters.translation_term_repository,
        resource_version_service=resource_version_service,
    )
    if term_rule_set_version_service is not None:
        term_rule_set_version_service.bootstrap_seed_as_default_if_empty(resolved_settings.term_rules_seed_file)
    else:
        TermRuleBootstrapService(
            term_rule_repository,
            resolved_settings.term_rules_runtime_yaml_file,
            resolved_settings.term_rules_seed_file,
            repository_backend="file",
        ).bootstrap()
    if translation_profile_service is not None:
        translation_profile_service.bootstrap_default_profiles_if_missing()
    template_read_service.get_default_template_id()
    template_read_service.bootstrap_manifest_versions()
    artifact_service = JobArtifactService()
    artifact_storage, artifact_storage_backend = _build_artifact_storage(resolved_settings, artifact_service)
    conversion_entrypoint = create_conversion_entrypoint()
    stage_service = JobStageService(
        resolved_settings,
        job_repository,
        job_file_repository,
        job_event_repository,
        conversion_entrypoint,
        artifact_storage,
        stage_message_store=stage_message_store,
        mineru_config_resolver=mineru_config_service.get_effective_config,
        stage_worker_id=(
            resolved_settings.jobs_worker_id
            if resolved_settings.jobs_worker_mode == "external"
            else "in_process"
        ),
        resolve_template_path=template_read_service.resolve_job_template_path,
        resolve_layout_config_path=template_read_service.resolve_job_layout_config_path,
        resolve_subscript_config_path=lambda: resolved_settings.subscript_config_path,
        resolve_translation_profile_snapshot=(
            translation_profile_service.resolve_default_snapshot
            if translation_profile_service is not None
            else None
        ),
        resource_snapshot_service=job_resource_snapshot_service,
    )
    stage_dispatcher, stage_dispatcher_backend = _build_stage_dispatcher(resolved_settings, stage_service)
    health_service = HealthService(
        resolved_settings,
        stage_message_store,
        effective_repository_backend=repository_backend,
        stage_message_store_backend=repository_backend,
        artifact_storage_backend=artifact_storage_backend,
        stage_dispatcher_backend=stage_dispatcher_backend,
        job_repository=job_repository,
        document_job_repository=document_job_repository,
        document_job_callback_message_store=document_job_callback_message_store,
        internal_user_repository=internal_user_repository,
        audit_event_repository=audit_event_repository,
        resource_version_repository=resource_version_service.repository if resource_version_service is not None else None,
        default_template_id_getter=template_read_service.get_default_template_id,
        ai_provider_config_service=ai_provider_config_service,
        mineru_config_service=mineru_config_service,
    )
    command_service = JobCommandService(
        resolved_settings,
        job_repository,
        job_file_repository,
        job_event_repository,
        stage_service,
        artifact_storage,
        job_resource_snapshot_service,
    )
    lifecycle_service = JobLifecycleService(
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_service=audit_service,
        stage_message_store=stage_message_store,
        stage_service=stage_service,
        artifact_service=artifact_service,
        artifact_storage=artifact_storage,
        resource_snapshot_service=job_resource_snapshot_service,
    )
    query_service = JobQueryService(job_repository, job_file_repository, job_event_repository)
    alert_delivery_provider = SlackWebhookAlertDeliveryProvider()
    secret_resolver = EnvironmentSecretResolver()
    return AppRuntime(
        settings=resolved_settings,
        persistence_adapters=persistence_adapters,
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_event_repository=audit_event_repository,
        acceptance_run_repository=acceptance_run_repository,
        document_file_repository=document_file_repository,
        file_retention_policy_repository=file_retention_policy_repository,
        file_retention_cleanup_lock_repository=file_retention_cleanup_lock_repository,
        file_retention_cleanup_run_history_repository=file_retention_cleanup_run_history_repository,
        document_job_repository=document_job_repository,
        document_job_event_repository=document_job_event_repository,
        document_job_callback_message_store=document_job_callback_message_store,
        document_job_translation_batch_repository=document_job_translation_batch_repository,
        internal_user_repository=internal_user_repository,
        saved_view_repository=saved_view_repository,
        terminology_release_repository=terminology_release_repository,
        audit_service=audit_service,
        acceptance_run_service=acceptance_run_service,
        auth_service=auth_service,
        internal_user_management_service=internal_user_management_service,
        file_upload_service=file_upload_service,
        file_retention_policy_service=file_retention_policy_service,
        document_ir_service=document_ir_service,
        ai_provider_config_service=ai_provider_config_service,
        mineru_config_service=mineru_config_service,
        translation_provider=translation_provider,
        document_ir_translation_service=document_ir_translation_service,
        translation_audit_service=translation_audit_service,
        term_version_service=term_version_service,
        document_word_renderer=document_word_renderer,
        document_job_service=document_job_service,
        document_job_incident_service=document_job_incident_service,
        saved_view_service=saved_view_service,
        document_job_execution_service=document_job_execution_service,
        document_job_recovery_service=document_job_recovery_service,
        document_job_task_queue=document_job_task_queue,
        health_service=health_service,
        template_read_service=template_read_service,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=term_rule_import_validation_service,
        term_rule_file_sync_service=term_rule_file_sync_service,
        term_rule_set_version_service=term_rule_set_version_service,
        term_rule_proposal_service=term_rule_proposal_service,
        term_rule_review_service=term_rule_review_service,
        translation_term_set_version_service=translation_term_set_version_service,
        translation_term_proposal_service=translation_term_proposal_service,
        terminology_release_service=terminology_release_service,
        translation_profile_service=translation_profile_service,
        resource_version_service=resource_version_service,
        job_resource_snapshot_service=job_resource_snapshot_service,
        artifact_service=artifact_service,
        artifact_storage=artifact_storage,
        command_service=command_service,
        lifecycle_service=lifecycle_service,
        query_service=query_service,
        stage_service=stage_service,
        stage_dispatcher=stage_dispatcher,
        stage_message_store=stage_message_store,
        alert_delivery_provider=alert_delivery_provider,
        secret_resolver=secret_resolver,
    )


def create_app(runtime: AppRuntime | None = None) -> FastAPI:
    app_runtime = runtime or build_runtime()
    # 测试和嵌入式调用可直接注入 runtime；应用边界仍需保证 seed 版本已完成幂等登记。
    app_runtime.template_read_service.bootstrap_manifest_versions()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        replay_tasks = [
            asyncio.create_task(asyncio.to_thread(app.state.runtime.stage_dispatcher.replay_pending)),
            asyncio.create_task(
                asyncio.to_thread(
                    app.state.runtime.document_job_recovery_service.run_startup_recovery,
                    trace_id="startup",
                )
            ),
        ]
        try:
            yield
        finally:
            for replay_task in replay_tasks:
                if not replay_task.done():
                    replay_task.cancel()

    app = FastAPI(title=app_runtime.settings.app_name, lifespan=lifespan)
    app.state.runtime = app_runtime
    register_api_error_handlers(app)

    if app_runtime.settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_runtime.settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    access_logger = logging.getLogger("access")
    system_logger = logging.getLogger("system")

    @app.middleware("http")
    async def trace_logging_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
        request.state.trace_id = trace_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            system_logger.exception(
                "[trace_id=%s method=%s path=%s status=exception duration_ms=%.1f]",
                trace_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Trace-Id"] = trace_id
        access_logger.info(
            "[trace_id=%s method=%s path=%s status_code=%s duration_ms=%.1f]",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    app.include_router(api_v1_router)
    return app


class LazyDefaultApp:
    """延迟构建默认 ASGI app，避免 import app.main 时立刻读取真实 .env 并连接外部依赖。"""

    def __init__(self) -> None:
        self._app: FastAPI | None = None

    def _get_app(self) -> FastAPI:
        if self._app is None:
            self._app = create_app()
        return self._app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        await self._get_app()(scope, receive, send)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_app(), name)


app = LazyDefaultApp()
