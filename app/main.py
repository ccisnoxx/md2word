from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.conversion.entrypoint import create_conversion_entrypoint
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.runtime import AppRuntime
from app.repositories.file_job_repository import FileJobRepository
from app.services.health_service import HealthService
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.command import JobCommandService
from app.services.jobs.lifecycle import JobLifecycleService
from app.services.jobs.query import JobQueryService
from app.services.jobs.stage import JobStageService
from app.services.templates.read_service import TemplateReadService


def build_runtime(settings: Settings | None = None) -> AppRuntime:
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.app_env)
    repository = FileJobRepository(resolved_settings.data_path)
    health_service = HealthService(resolved_settings)
    template_read_service = TemplateReadService(resolved_settings)
    artifact_service = JobArtifactService()
    conversion_entrypoint = create_conversion_entrypoint()
    stage_service = JobStageService(resolved_settings, repository, conversion_entrypoint, artifact_service)
    command_service = JobCommandService(resolved_settings, repository, stage_service, artifact_service)
    lifecycle_service = JobLifecycleService(
        repository=repository,
        stage_repository=repository,
        stage_service=stage_service,
        artifact_service=artifact_service,
    )
    query_service = JobQueryService(repository)
    return AppRuntime(
        settings=resolved_settings,
        repository=repository,
        health_service=health_service,
        template_read_service=template_read_service,
        artifact_service=artifact_service,
        command_service=command_service,
        lifecycle_service=lifecycle_service,
        query_service=query_service,
        stage_service=stage_service,
    )


def create_app(runtime: AppRuntime | None = None) -> FastAPI:
    app_runtime = runtime or build_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        replay_task = asyncio.create_task(asyncio.to_thread(app.state.runtime.stage_service.replay_pending))
        try:
            yield
        finally:
            if not replay_task.done():
                replay_task.cancel()

    app = FastAPI(title=app_runtime.settings.app_name, lifespan=lifespan)
    app.state.runtime = app_runtime

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
                "[trace_id=%s] %s %s -> exception %.1fms",
                trace_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Trace-Id"] = trace_id
        access_logger.info(
            "[trace_id=%s] %s %s -> %s %.1fms",
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
