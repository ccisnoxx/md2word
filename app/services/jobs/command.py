from __future__ import annotations

# app/services/jobs/command.py: 负责 jobs 的创建、上传落盘和 callback 入队入口。

import shutil
from uuid import uuid4

from app.core.config import Settings
from app.core.job_models import ConversionOptions, JobFile, JobRecord, SourcePdfJobContext
from app.core.job_workflow import build_job_created_intent, build_mineru_callback_received_intent
from app.core.job_paths import build_job_paths, ensure_job_dirs
from app.repositories.protocols import JobEventRepositoryProtocol, JobFileRepositoryProtocol, JobSnapshotRepositoryProtocol
from app.services.jobs.artifact_storage import ArtifactStorageProtocol
from app.services.jobs.resource_snapshots import JobResourceSnapshotService
from app.services.jobs.stage import JobStageService
from app.services.jobs.workflow_events import build_job_event_from_intent


class JobCommandService:
    def __init__(
        self,
        settings: Settings,
        job_repository: JobSnapshotRepositoryProtocol,
        job_file_repository: JobFileRepositoryProtocol,
        job_event_repository: JobEventRepositoryProtocol,
        stage_service: JobStageService,
        artifact_storage: ArtifactStorageProtocol,
        resource_snapshot_service: JobResourceSnapshotService,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.job_file_repository = job_file_repository
        self.job_event_repository = job_event_repository
        self.stage_service = stage_service
        self.artifact_storage = artifact_storage
        self.resource_snapshot_service = resource_snapshot_service

    def create_job_from_saved_upload(
        self,
        *,
        temp_upload_path,
        source_filename: str,
        options: ConversionOptions,
        trace_id: str,
    ):
        job_id = f"job_{uuid4().hex[:12]}"
        resource_snapshot = self.resource_snapshot_service.build_snapshot(
            options=options,
            source_kind="mineru_package",
            job_id=job_id,
        )
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
            resource_snapshot=resource_snapshot,
        )
        self.job_repository.create_job(job)
        self.job_file_repository.upsert_file(
            job_id,
            self.artifact_storage.build_registered_file("source_package", job_paths),
        )
        self.job_event_repository.append_event(
            job_id,
            build_job_event_from_intent(
                build_job_created_intent(
                    source_kind="mineru_package",
                    source_filename=source_filename,
                    options=options,
                    resource_snapshot=resource_snapshot,
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
        resource_snapshot = self.resource_snapshot_service.build_snapshot(
            options=options,
            source_kind="source_pdf",
            job_id=job_id,
        )
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
            resource_snapshot=resource_snapshot,
        )
        self.job_repository.create_job(job)
        self.job_file_repository.upsert_file(
            job_id,
            self.artifact_storage.build_registered_file("source_pdf", job_paths),
        )
        self.job_event_repository.append_event(
            job_id,
            build_job_event_from_intent(
                build_job_created_intent(
                    source_kind="source_pdf",
                    source_filename=source_filename,
                    options=options,
                    resource_snapshot=resource_snapshot,
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
        self.job_event_repository.append_event(
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
            job = self.job_repository.get_job(data_id)
            if job is not None:
                return job
        for job in self.job_repository.list_jobs():
            if data_id and job.read_mineru_data_id() == data_id:
                return job
        for job in self.job_repository.list_jobs():
            if batch_id and job.read_mineru_batch_id() == batch_id:
                return job
        raise FileNotFoundError("未找到与回调匹配的任务")
