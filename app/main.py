from __future__ import annotations

# app/main.py: 组装 FastAPI 应用和当前单进程运行时依赖。

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_api_error_handlers
from app.api.v1.router import router as api_v1_router
from app.conversion.entrypoint import create_conversion_entrypoint
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.runtime import AppRuntime
from app.repositories.database_job_repository import DatabaseJobRepository
from app.repositories.file_job_repository import FileJobRepository
from app.repositories.file_term_rule_repository import FileTermRuleRepository
from app.repositories.mysql_job_repository import MysqlJobRepository, MysqlJobRepositoryConfig
from app.services.health_service import HealthService
from app.services.audit import AuditService
from app.services.jobs.artifact_storage import LocalArtifactStorageAdapter
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.command import JobCommandService
from app.services.jobs.dispatch import ExternalWorkerStageDispatcher, InProcessStageDispatcher
from app.services.jobs.lifecycle import JobLifecycleService
from app.services.jobs.object_artifact_storage import ObjectArtifactStorageAdapter, S3ArtifactStorageAdapter
from app.services.jobs.resource_snapshots import JobResourceSnapshotService
from app.services.jobs.query import JobQueryService
from app.services.jobs.stage import JobStageService
from app.services.resource_versions import ResourceVersionService
from app.services.term_rules.bootstrap import TermRuleBootstrapService
from app.services.term_rules.import_validation import TermRuleImportValidationService
from app.services.term_rules.service import TermRuleService
from app.services.term_rules.sync_files import TermRuleFileSyncService
from app.services.term_rules.versioning_service import TermRuleSetVersionService
from app.services.templates.read_service import TemplateReadService
from app.services.translation_profiles import TranslationProfileVersionService


def _build_job_metadata_repository(settings: Settings):
    """按配置选择 jobs metadata store；默认仍保持 file backend。"""

    if settings.jobs_repository_backend == "database":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        return DatabaseJobRepository(settings.jobs_metadata_database_file), "database"
    if settings.jobs_repository_backend == "mysql":
        settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        return MysqlJobRepository(
            MysqlJobRepositoryConfig(
                host=settings.jobs_mysql_host,
                port=settings.jobs_mysql_port,
                user=settings.jobs_mysql_user,
                password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database,
                charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            )
        ), "mysql"
    return FileJobRepository(settings.data_path), "file"


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


def build_runtime(settings: Settings | None = None) -> AppRuntime:
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.app_env, resolved_settings.log_format)
    repository, repository_backend = _build_job_metadata_repository(resolved_settings)
    job_repository = repository
    job_file_repository = repository
    job_event_repository = repository
    audit_event_repository = repository
    stage_message_store = repository
    audit_service = AuditService(audit_event_repository)
    resource_version_service = (
        ResourceVersionService(repository)
        if repository_backend == "mysql"
        else None
    )
    template_read_service = TemplateReadService(resolved_settings, resource_version_service, audit_service)
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
        )
        if resource_version_service is not None
        else None
    )
    translation_profile_service = (
        TranslationProfileVersionService(resolved_settings, resource_version_service, audit_service)
        if resource_version_service is not None
        else None
    )
    job_resource_snapshot_service = JobResourceSnapshotService(resolved_settings, resource_version_service)
    TermRuleBootstrapService(
        term_rule_repository,
        resolved_settings.term_rules_runtime_yaml_file,
        resolved_settings.term_rules_seed_file,
        repository_backend="file",
    ).bootstrap()
    template_read_service.get_default_template_id()
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
        stage_worker_id=(
            resolved_settings.jobs_worker_id
            if resolved_settings.jobs_worker_mode == "external"
            else "in_process"
        ),
        resolve_template_path=template_read_service.resolve_job_template_path,
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
        audit_event_repository=audit_event_repository,
        resource_version_repository=resource_version_service.repository if resource_version_service is not None else None,
        default_template_id_getter=template_read_service.get_default_template_id,
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
    )
    query_service = JobQueryService(job_repository, job_file_repository, job_event_repository)
    return AppRuntime(
        settings=resolved_settings,
        repository=repository,
        job_repository=job_repository,
        job_file_repository=job_file_repository,
        job_event_repository=job_event_repository,
        audit_event_repository=audit_event_repository,
        audit_service=audit_service,
        health_service=health_service,
        template_read_service=template_read_service,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=term_rule_import_validation_service,
        term_rule_file_sync_service=term_rule_file_sync_service,
        term_rule_set_version_service=term_rule_set_version_service,
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
    )


def create_app(runtime: AppRuntime | None = None) -> FastAPI:
    app_runtime = runtime or build_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        replay_task = asyncio.create_task(asyncio.to_thread(app.state.runtime.stage_dispatcher.replay_pending))
        try:
            yield
        finally:
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


app = create_app()
