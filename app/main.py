# 文件： app/main.py
# 用途： 进程入口：按领域装配函数组装运行时（AppRuntime），并创建 FastAPI 应用。

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_api_error_handlers
from app.api.middleware import install_trace_logging_middleware
from app.api.v1.router import router as api_v1_router
from app.composition.document_pipeline import build_document_pipeline
from app.composition.health import build_observability_services
from app.composition.platform import build_platform_services
from app.composition.startup import run_startup_bootstrap
from app.composition.terminology import build_terminology_services
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.runtime import AppRuntime
from app.infrastructure.persistence import build_persistence_adapters


def _validate_runtime_guardrails(settings: Settings) -> None:
    """阻止近生产环境以 open jobs 访问模式启动。"""

    if settings.production_like and settings.jobs_access_mode == "open":
        raise RuntimeError(
            "JOBS_ACCESS_MODE=open 不允许用于生产或 single_tenant_public 部署；"
            "请改用 JOBS_ACCESS_MODE=token 或 admin，并配置对应 token。"
        )


def build_runtime(settings: Settings | None = None) -> AppRuntime:
    """构建当前进程共享运行时：先构造全部服务，再统一执行启动 bootstrap，最后装配健康检查。"""

    resolved_settings = settings or Settings()
    _validate_runtime_guardrails(resolved_settings)
    configure_logging(resolved_settings.app_env, resolved_settings.log_format)
    # 持久化适配器在此构造（测试按 app.main.build_persistence_adapters 替换后端）。
    adapters = build_persistence_adapters(resolved_settings)
    platform = build_platform_services(resolved_settings, adapters)
    pipeline = build_document_pipeline(resolved_settings, adapters, platform)
    terminology = build_terminology_services(resolved_settings, adapters, platform)
    run_startup_bootstrap(resolved_settings, platform, pipeline, terminology)
    observability = build_observability_services(resolved_settings, adapters, platform, pipeline)
    return AppRuntime(
        settings=resolved_settings,
        persistence_adapters=adapters,
        job_event_repository=adapters.job_event_repository,
        audit_event_repository=adapters.audit_event_repository,
        acceptance_run_repository=adapters.acceptance_run_repository,
        document_file_repository=adapters.document_file_repository,
        file_retention_policy_repository=adapters.file_retention_policy_repository,
        file_retention_cleanup_lock_repository=adapters.file_retention_cleanup_lock_repository,
        file_retention_cleanup_run_history_repository=adapters.file_retention_cleanup_run_history_repository,
        document_job_repository=adapters.document_job_repository,
        document_job_event_repository=adapters.document_job_event_repository,
        document_job_callback_message_store=adapters.document_job_callback_message_store,
        document_job_translation_batch_repository=adapters.document_job_translation_batch_repository,
        internal_user_repository=adapters.internal_user_repository,
        saved_view_repository=adapters.saved_view_repository,
        terminology_release_repository=adapters.terminology_release_repository,
        audit_service=platform.audit_service,
        acceptance_run_service=platform.acceptance_run_service,
        auth_service=platform.auth_service,
        internal_user_management_service=platform.internal_user_management_service,
        file_upload_service=platform.file_upload_service,
        file_retention_policy_service=platform.file_retention_policy_service,
        document_ir_service=pipeline.document_ir_service,
        ai_provider_config_service=pipeline.ai_provider_config_service,
        mineru_config_service=pipeline.mineru_config_service,
        translation_provider=pipeline.translation_provider,
        document_ir_translation_service=pipeline.document_ir_translation_service,
        translation_audit_service=pipeline.translation_audit_service,
        term_version_service=pipeline.term_version_service,
        document_word_renderer=pipeline.document_word_renderer,
        document_job_use_cases=pipeline.document_job_use_cases,
        document_job_incident_service=pipeline.document_job_incident_service,
        saved_view_service=platform.saved_view_service,
        document_job_execution_service=pipeline.document_job_execution_service,
        word_preview_service=pipeline.word_preview_service,
        document_job_recovery_service=pipeline.document_job_recovery_service,
        document_job_task_queue=pipeline.document_job_task_queue,
        health_service=observability.health_service,
        template_read_service=pipeline.template_read_service,
        term_rule_service=terminology.term_rule_service,
        term_rule_import_validation_service=terminology.term_rule_import_validation_service,
        term_rule_file_sync_service=terminology.term_rule_file_sync_service,
        term_rule_set_version_service=terminology.term_rule_set_version_service,
        term_rule_proposal_service=terminology.term_rule_proposal_service,
        term_rule_review_service=terminology.term_rule_review_service,
        translation_term_set_version_service=terminology.translation_term_set_version_service,
        translation_term_proposal_service=terminology.translation_term_proposal_service,
        terminology_release_service=terminology.terminology_release_service,
        translation_profile_service=terminology.translation_profile_service,
        resource_version_service=platform.resource_version_service,
        job_resource_snapshot_service=pipeline.job_resource_snapshot_service,
        alert_delivery_provider=observability.alert_delivery_provider,
        secret_resolver=observability.secret_resolver,
    )


def create_app(runtime: AppRuntime | None = None) -> FastAPI:
    app_runtime = runtime or build_runtime()
    # 测试和嵌入式调用可直接注入 runtime；应用边界仍需保证 seed 版本已完成幂等登记。
    app_runtime.template_read_service.bootstrap_manifest_versions()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recovery_task = asyncio.create_task(
            asyncio.to_thread(
                app.state.runtime.document_job_recovery_service.run_startup_recovery,
                trace_id="startup",
            )
        )
        try:
            yield
        finally:
            if not recovery_task.done():
                recovery_task.cancel()

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

    install_trace_logging_middleware(app)

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
