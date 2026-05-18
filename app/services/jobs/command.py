from __future__ import annotations

import shutil
from uuid import uuid4

from app.core.config import Settings
from app.core.job_models import ConversionOptions, JobEvent, JobFile, JobRecord
from app.core.job_paths import build_job_paths, ensure_job_dirs
from app.repositories.protocols import JobRepositoryProtocol
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.stage import JobStageService


class JobCommandService:
    def __init__(
        self,
        settings: Settings,
        repository: JobRepositoryProtocol,
        stage_service: JobStageService,
        artifact_service: JobArtifactService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.stage_service = stage_service
        self.artifact_service = artifact_service

    def create_job_from_saved_upload(
        self,
        *,
        temp_upload_path,
        source_filename: str,
        options: ConversionOptions,
        trace_id: str,
    ):
        job_id = f"job_{uuid4().hex[:12]}"
        job_paths = build_job_paths(self.settings.data_path, job_id)
        ensure_job_dirs(job_paths)
        shutil.move(str(temp_upload_path), str(job_paths.source_package))

        job = JobRecord(
            id=job_id,
            source_filename=source_filename,
            status="uploaded",
            progress=0,
            source_kind="mineru_package",
            translation_mode=options.translation_mode,
            document_language=options.document_language,
            use_mineru_header_footer=options.use_mineru_header_footer,
            template_id=options.template_id,
        )
        self.repository.create_job(job)
        self.repository.upsert_file(
            job_id,
            self.artifact_service.build_registered_file("source_package", job_paths),
        )
        self.repository.append_event(
            job_id,
            JobEvent(
                stage="job_created",
                message="任务已创建，等待后台转换。",
                status="accepted",
                details={
                    "source_filename": source_filename,
                    "translation_mode": options.translation_mode,
                    "document_language": options.document_language,
                },
                trace_id=trace_id,
            ),
        )
        stage_message = self.stage_service.enqueue_conversion(job, options, trace_id)
        return job, stage_message

    def create_job_from_pdf_upload(
        self,
        *,
        temp_upload_path,
        source_filename: str,
        options: ConversionOptions,
        trace_id: str,
    ):
        job_id = f"job_{uuid4().hex[:12]}"
        job_paths = build_job_paths(self.settings.data_path, job_id)
        ensure_job_dirs(job_paths)
        shutil.move(str(temp_upload_path), str(job_paths.source_pdf))

        job = JobRecord(
            id=job_id,
            source_filename=source_filename,
            status="uploaded",
            progress=0,
            source_kind="source_pdf",
            translation_mode=options.translation_mode,
            document_language=options.document_language,
            use_mineru_header_footer=options.use_mineru_header_footer,
            template_id=options.template_id,
        )
        self.repository.create_job(job)
        self.repository.upsert_file(
            job_id,
            self.artifact_service.build_registered_file("source_pdf", job_paths),
        )
        self.repository.append_event(
            job_id,
            JobEvent(
                stage="job_created",
                message="PDF 任务已创建，等待提交 MinerU。",
                status="accepted",
                details={
                    "source_filename": source_filename,
                    "source_kind": "source_pdf",
                    "translation_mode": options.translation_mode,
                    "document_language": options.document_language,
                },
                trace_id=trace_id,
            ),
        )
        stage_message = self.stage_service.enqueue_mineru_submission(job, options, trace_id)
        return job, stage_message

    def enqueue_callback(
        self,
        normalized_payload: dict,
        trace_id: str,
        job: JobRecord | None = None,
    ):
        resolved_job = job or self.find_job_for_callback(normalized_payload)
        stage_message = self.stage_service.enqueue_process_callback(resolved_job, normalized_payload, trace_id)
        self.repository.append_event(
            resolved_job.id,
            JobEvent(
                stage="mineru_callback_received",
                message="收到 MinerU callback，等待后台处理。",
                status="accepted",
                details={
                    "batch_id": normalized_payload.get("batch_id"),
                    "data_id": normalized_payload.get("data_id"),
                    "state": normalized_payload.get("state"),
                },
                trace_id=trace_id,
            ),
        )
        return resolved_job, stage_message

    def find_job_for_callback(self, payload: dict) -> JobRecord:
        data_id = payload.get("data_id")
        batch_id = payload.get("batch_id")
        if isinstance(data_id, str):
            job = self.repository.get_job(data_id)
            if job is not None:
                return job
        for job in self.repository.list_jobs():
            if data_id and job.mineru_data_id == data_id:
                return job
        for job in self.repository.list_jobs():
            if batch_id and job.mineru_batch_id == batch_id:
                return job
        raise FileNotFoundError("未找到与回调匹配的任务")
