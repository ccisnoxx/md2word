from __future__ import annotations

# app/domains/jobs/lifecycle.py: 处理 jobs 的 retry/cancel/cleanup 运维动作，并调用集中 workflow 规则。

import shutil
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.domains.audit.models import ActorContext
from app.domains.jobs.workflow import (
    JobWorkflowViolation,
    build_cancel_transition,
    build_cleanup_local_files_transition,
    build_retry_transition,
)
from app.domains.jobs.models import ConversionOptions, utc_now
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.repository import (
    JobEventRepositoryProtocol,
    JobFileRepositoryProtocol,
    JobSnapshotRepositoryProtocol,
    StageMessageStoreProtocol,
)
from app.domains.jobs.artifact_storage import ArtifactStorageProtocol
from app.domains.jobs.artifacts import JobArtifactService
from app.domains.jobs.stage import JobStageService
from app.domains.jobs.workflow_events import build_job_event_from_intent


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
        job_repository: JobSnapshotRepositoryProtocol,
        job_file_repository: JobFileRepositoryProtocol,
        job_event_repository: JobEventRepositoryProtocol,
        audit_service,
        stage_message_store: StageMessageStoreProtocol,
        stage_service: JobStageService,
        artifact_service: JobArtifactService,
        artifact_storage: ArtifactStorageProtocol,
    ) -> None:
        self.job_repository = job_repository
        self.job_file_repository = job_file_repository
        self.job_event_repository = job_event_repository
        self.audit_service = audit_service
        self.stage_message_store = stage_message_store
        self.stage_service = stage_service
        self.artifact_service = artifact_service
        self.artifact_storage = artifact_storage

    def _append_intent_event(
        self,
        job_id: str,
        *,
        intent,
        trace_id: str,
        message: str | None = None,
        status: str | None = None,
        error_code: str | None = None,
        details: dict | None = None,
    ) -> None:
        """把 lifecycle 领域事件意图映射为当前持久化 JobEvent。"""

        self.job_event_repository.append_event(
            job_id,
            build_job_event_from_intent(
                intent,
                trace_id=trace_id,
                message=message,
                status=status,
                error_code=error_code,
                details=details,
            ),
        )

    def retry_job(
        self,
        job_id: str,
        *,
        reason: str,
        trace_id: str,
        actor: ActorContext | None = None,
    ) -> JobOperationAccepted:
        job = self._get_job_or_404(job_id)
        # retry 的合法性和 reset patch 统一由 workflow 规则层给出。
        try:
            transition = build_retry_transition(job)
        except JobWorkflowViolation as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

        self._delete_pending_stage_messages(job.id)
        updated_job = self.job_repository.update_job(
            job.id,
            updated_at=utc_now(),
            **transition.as_job_update_patch(job),
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
        self._append_intent_event(
            job.id,
            intent=transition.event_intents[0],
            trace_id=trace_id,
            details={"reason": reason, "stage_message_id": stage_message.id},
        )
        self._record_audit(
            actor=actor,
            action="job.retry",
            target_id=job.id,
            trace_id=trace_id,
            reason=reason,
        )
        return JobOperationAccepted(
            job_id=job.id,
            operation="retry",
            accepted=True,
            status="queued",
            message="任务已重新加入后台执行队列。",
        )

    def cancel_job(
        self,
        job_id: str,
        *,
        reason: str,
        trace_id: str,
        actor: ActorContext | None = None,
    ):
        job = self._get_job_or_404(job_id)
        # cancel 是否允许由集中 policy 判定，避免状态约束散落在 service 内。
        try:
            transition = build_cancel_transition(job)
        except JobWorkflowViolation as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

        self._delete_pending_stage_messages(job.id)
        updated = self.job_repository.update_job(
            job.id,
            completed_at=utc_now(),
            updated_at=utc_now(),
            **transition.as_job_update_patch(job),
        )
        self._append_intent_event(
            job.id,
            intent=transition.event_intents[0],
            trace_id=trace_id,
            details={"reason": reason},
        )
        self._record_audit(
            actor=actor,
            action="job.cancel",
            target_id=job.id,
            trace_id=trace_id,
            reason=reason,
        )
        return updated

    def cleanup_local_files(
        self,
        job_id: str,
        *,
        reason: str,
        trace_id: str,
        actor: ActorContext | None = None,
    ) -> CleanupLocalFilesResult:
        job = self._get_job_or_404(job_id)
        # cleanup 仍是运维动作，但状态前置条件统一走 workflow 规则层。
        try:
            transition = build_cleanup_local_files_transition(job)
        except JobWorkflowViolation as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

        job_paths = build_job_paths(self.stage_service.settings.data_path, job.id)
        deleted_paths: list[str] = []
        skipped_paths: list[dict[str, str]] = []

        for file in self.artifact_service.sort_files(self.job_file_repository.list_files(job.id)):
            download = self.artifact_storage.resolve_download(job_paths, file)
            if download.kind == "local_path" and download.path is not None and download.path.exists():
                skipped_paths.append(
                    {
                        "path": str(download.path),
                        "reason": "registered_local_artifact",
                    }
                )

        if job_paths.work_dir.exists():
            shutil.rmtree(job_paths.work_dir)
            deleted_paths.append(str(job_paths.work_dir))

        self._append_intent_event(
            job.id,
            intent=transition.event_intents[0],
            trace_id=trace_id,
            details={
                "reason": reason,
                "deleted_paths": deleted_paths,
                "skipped_paths": skipped_paths,
            },
        )
        self._record_audit(
            actor=actor,
            action="job.cleanup_local_files",
            target_id=job.id,
            trace_id=trace_id,
            reason=reason,
        )

        return CleanupLocalFilesResult(
            job_id=job.id,
            deleted_paths=deleted_paths,
            skipped_paths=skipped_paths,
            status=job.status,
            message="本地运行态文件清理完成。",
        )

    def _get_job_or_404(self, job_id: str):
        job = self.job_repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {job_id}")
        return job

    def _delete_pending_stage_messages(self, job_id: str) -> None:
        for message in self.stage_message_store.list_replayable_stage_messages():
            if message.job_id == job_id:
                self.stage_message_store.delete_stage_message(message.id)

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        target_id: str,
        trace_id: str,
        reason: str,
    ) -> None:
        if actor is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="job",
            target_id=target_id,
            trace_id=trace_id,
            reason=reason,
        )
