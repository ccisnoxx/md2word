from __future__ import annotations

# app/services/jobs/command.py: 负责 jobs 的创建、上传落盘和 callback 入队入口。

import shutil
from uuid import uuid4

from app.core.config import Settings
from app.core.job_models import ConversionOptions, JobFile, JobRecord, SourcePdfJobContext
from app.core.job_workflow import build_job_created_intent, build_mineru_callback_received_intent
from app.core.job_paths import build_job_paths, ensure_job_dirs
from app.repositories.protocols import JobRepositoryProtocol
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.stage import JobStageService
from app.services.jobs.workflow_events import build_job_event_from_intent


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
            lifecycle_status="uploaded",
            execution_status="idle",
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
            build_job_event_from_intent(
                build_job_created_intent(
                    source_kind="mineru_package",
                    source_filename=source_filename,
                    options=options,
                ),
                trace_id=trace_id,
                message="任务已创建，等待后台转换。",
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
            lifecycle_status="uploaded",
            execution_status="idle",
            source_pdf_context=SourcePdfJobContext(),
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
            build_job_event_from_intent(
                build_job_created_intent(
                    source_kind="source_pdf",
                    source_filename=source_filename,
                    options=options,
                ),
                trace_id=trace_id,
                message="PDF 任务已创建，等待提交 MinerU。",
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
            build_job_event_from_intent(
                build_mineru_callback_received_intent(normalized_payload),
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
            if data_id and job.read_mineru_data_id() == data_id:
                return job
        for job in self.repository.list_jobs():
            if batch_id and job.read_mineru_batch_id() == batch_id:
                return job
        raise FileNotFoundError("未找到与回调匹配的任务")
