from __future__ import annotations

import shutil
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.job_models import ConversionOptions, JobEvent, utc_now
from app.core.job_paths import build_job_paths
from app.repositories.protocols import JobRepositoryProtocol, StageMessageRepositoryProtocol
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.stage import JobStageService


@dataclass(frozen=True, slots=True)
class JobOperationAccepted:
    job_id: str
    operation: str
    accepted: bool
    status: str
    message: str


@dataclass(frozen=True, slots=True)
class CleanupLocalFilesResult:
    job_id: str
    deleted_paths: list[str]
    skipped_paths: list[dict[str, str]]
    status: str
    message: str


class JobLifecycleService:
    def __init__(
        self,
        *,
        repository: JobRepositoryProtocol,
        stage_repository: StageMessageRepositoryProtocol,
        stage_service: JobStageService,
        artifact_service: JobArtifactService,
    ) -> None:
        self.repository = repository
        self.stage_repository = stage_repository
        self.stage_service = stage_service
        self.artifact_service = artifact_service

    def retry_job(self, job_id: str, *, reason: str, trace_id: str) -> JobOperationAccepted:
        job = self._get_job_or_404(job_id)
        if job.status not in {"failed", "canceled"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"当前状态 `{job.status}` 不允许 retry。",
            )

        self._delete_pending_stage_messages(job.id)
        updated_job = self.repository.update_job(
            job.id,
            status="uploaded",
            progress=0,
            error_code=None,
            error_message=None,
            result_ready=False,
            started_at=None,
            completed_at=None,
            updated_at=utc_now(),
            mineru_batch_id=None if job.source_kind == "source_pdf" else job.mineru_batch_id,
            mineru_data_id=None if job.source_kind == "source_pdf" else job.mineru_data_id,
            mineru_callback_seed=None if job.source_kind == "source_pdf" else job.mineru_callback_seed,
            mineru_status=None if job.source_kind == "source_pdf" else job.mineru_status,
        )
        options = ConversionOptions(
            template_id=job.template_id,
            translation_mode=job.translation_mode,
            document_language=job.document_language,
            use_mineru_header_footer=job.use_mineru_header_footer,
        )
        if job.source_kind == "source_pdf":
            stage_message = self.stage_service.enqueue_mineru_submission(updated_job, options, trace_id)
        else:
            stage_message = self.stage_service.enqueue_conversion(updated_job, options, trace_id)
        self.repository.append_event(
            job.id,
            JobEvent(
                stage="job_retry_requested",
                message="任务已重新加入后台执行队列。",
                status="accepted",
                details={"reason": reason, "stage_message_id": stage_message.id},
                trace_id=trace_id,
            ),
        )
        return JobOperationAccepted(
            job_id=job.id,
            operation="retry",
            accepted=True,
            status="queued",
            message="任务已重新加入后台执行队列。",
        )

    def cancel_job(self, job_id: str, *, reason: str, trace_id: str):
        job = self._get_job_or_404(job_id)
        if job.status in {"completed", "failed", "canceled"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"当前状态 `{job.status}` 不允许 cancel。",
            )
        if job.status == "converting":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前任务正在执行中，暂不支持中断式取消。",
            )

        self._delete_pending_stage_messages(job.id)
        updated = self.repository.update_job(
            job.id,
            status="canceled",
            progress=100,
            error_code=None,
            error_message=None,
            result_ready=False,
            completed_at=utc_now(),
            updated_at=utc_now(),
        )
        self.repository.append_event(
            job.id,
            JobEvent(
                stage="job_canceled",
                message="任务已取消。",
                status="succeeded",
                details={"reason": reason},
                trace_id=trace_id,
            ),
        )
        return updated

    def cleanup_local_files(self, job_id: str, *, reason: str, trace_id: str) -> CleanupLocalFilesResult:
        job = self._get_job_or_404(job_id)
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"当前状态 `{job.status}` 不允许 cleanup-local-files。",
            )

        job_paths = build_job_paths(self.stage_service.settings.data_path, job.id)
        deleted_paths: list[str] = []
        skipped_paths: list[dict[str, str]] = []

        for file in self.artifact_service.sort_files(self.repository.list_files(job.id)):
            artifact_path = self.artifact_service.resolve_download_path(job_paths, file)
            if artifact_path.exists():
                skipped_paths.append(
                    {
                        "path": str(artifact_path),
                        "reason": "registered_local_artifact",
                    }
                )

        if job_paths.work_dir.exists():
            shutil.rmtree(job_paths.work_dir)
            deleted_paths.append(str(job_paths.work_dir))

        self.repository.append_event(
            job.id,
            JobEvent(
                stage="cleanup_local_files",
                message="本地运行态文件清理完成。",
                status="succeeded",
                details={
                    "reason": reason,
                    "deleted_paths": deleted_paths,
                    "skipped_paths": skipped_paths,
                },
                trace_id=trace_id,
            ),
        )

        return CleanupLocalFilesResult(
            job_id=job.id,
            deleted_paths=deleted_paths,
            skipped_paths=skipped_paths,
            status=job.status,
            message="本地运行态文件清理完成。",
        )

    def _get_job_or_404(self, job_id: str):
        job = self.repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {job_id}")
        return job

    def _delete_pending_stage_messages(self, job_id: str) -> None:
        for message in self.stage_repository.list_pending_stage_messages():
            if message.job_id == job_id:
                self.stage_repository.delete_stage_message(message.id)
