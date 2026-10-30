from __future__ import annotations

# app/domains/document_jobs/recovery.py：编排任务回调观察、轮询及重放恢复。

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import status

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.domains.document_jobs.models import (
    DocumentJobEventLevel,
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
)
from app.domains.document_jobs.repository import (
    DocumentJobCallbackMessageStoreProtocol,
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.document_jobs.workflow import ACTIVE_DOCUMENT_JOB_STATUSES, TERMINAL_DOCUMENT_JOB_STATUSES
from app.domains.resources.models import utc_now


CALLBACK_MESSAGE_STATUSES = ("pending", "running", "processed", "failed", "ignored")
DOCUMENT_JOB_RECOVERY_STALE_SECONDS = 600
RECENT_PROBLEM_MESSAGE_LIMIT = 5


def is_mineru_polling_job(settings: Settings, job: DocumentJobRecord) -> bool:
    """仅续投轮询模式中已知批次的当前解析，未知首次提交结果不自动重提。"""

    return (
        not settings.mineru_callback_url.strip()
        and job.archived_at is None
        and job.status == "running"
        and job.stage == "parsing"
        and bool(job.mineru_batch_id)
    )


@dataclass(frozen=True, slots=True)
class DocumentJobCallbackProblemSummary:
    """Callback message 排障摘要，不暴露 callback 原始 payload。"""

    message_id: str
    status: str
    error_code: str | None
    error_message: str | None
    attempts: int
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class DocumentJobCallbackObservation:
    """单任务或全局 callback message 观察值。"""

    job_id: str | None
    status_counts: dict[str, int]
    replayable_count: int
    oldest_replayable_age_seconds: int
    recent_problem_messages: list[DocumentJobCallbackProblemSummary] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status_counts": dict(self.status_counts),
            "replayable_count": self.replayable_count,
            "oldest_replayable_age_seconds": self.oldest_replayable_age_seconds,
            "recent_problem_messages": [item.to_dict() for item in self.recent_problem_messages],
        }


@dataclass(frozen=True, slots=True)
class DocumentJobReplayPreview:
    """Recovery replay 的只读 eligibility 结果。"""

    job: DocumentJobRecord | None
    eligible: bool
    missing_gates: list[str]
    warnings: list[str]
    callback_observation: DocumentJobCallbackObservation
    stale_job_detected: bool
    worker_backend: str
    automatic_execution_enabled: bool


@dataclass(frozen=True, slots=True)
class DocumentJobReplayExecutionResult:
    """Recovery replay 执行结果；不会在 HTTP 内同步推进 Word 交付链路。"""

    preview: DocumentJobReplayPreview
    executed: bool
    queued_task_id: str | None
    replayable_callback_messages: int
    ignored_callback_messages: int
    recovery_events_written: int


@dataclass(frozen=True, slots=True)
class DocumentJobStartupRecoveryResult:
    """应用启动时一次性 recovery replay 汇总。"""

    scanned_jobs: int
    eligible_jobs: int
    queued_jobs: int
    ignored_callback_messages: int
    failed_jobs: int
    skipped_reason: str | None = None


class DocumentJobRecoveryService:
    """收口 document_jobs 任务可靠性和 callback replay 的边界服务。"""

    def __init__(
        self,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        event_repository: DocumentJobEventRepositoryProtocol,
        callback_message_store: DocumentJobCallbackMessageStoreProtocol,
        task_queue: DocumentJobTaskQueueProtocol | None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.callback_message_store = callback_message_store
        self.task_queue = task_queue
        self.logger = logging.getLogger("business")

    def build_callback_observation(self, job_id: str | None = None) -> DocumentJobCallbackObservation:
        """汇总 callback message 状态和 replayable 年龄，不读取 payload 正文。"""

        now = utc_now()
        status_counts = self.callback_message_store.count_callback_messages_by_status(job_id)
        normalized_counts = {status: int(status_counts.get(status, 0)) for status in CALLBACK_MESSAGE_STATUSES}
        replayable_messages = self.callback_message_store.list_replayable_callback_messages(job_id)
        oldest_age_seconds = 0
        if replayable_messages:
            oldest = min((message.updated_at or message.created_at) for message in replayable_messages)
            oldest_age_seconds = max(0, int((now - oldest).total_seconds()))
        recent_problem_messages = self._build_recent_problem_messages(job_id)
        return DocumentJobCallbackObservation(
            job_id=job_id,
            status_counts=normalized_counts,
            replayable_count=len(replayable_messages),
            oldest_replayable_age_seconds=oldest_age_seconds,
            recent_problem_messages=recent_problem_messages,
        )

    def preview_replay(self, job_id: str) -> DocumentJobReplayPreview:
        """只读判断某个 document_job 是否可执行 replay recovery。"""

        job = self.job_repository.get_document_job(job_id)
        callback_observation = self.build_callback_observation(job_id)
        stale_job_detected = self._is_stale_active_job(job) if job is not None else False
        missing_gates: list[str] = []
        warnings: list[str] = []
        if job is None:
            missing_gates.append("target_not_found")
        elif job.archived_at is not None:
            missing_gates.append("target_archived")
        elif job.status in TERMINAL_DOCUMENT_JOB_STATUSES:
            if callback_observation.replayable_count == 0:
                missing_gates.append("status_terminal_no_replayable_callback")
            else:
                warnings.append("terminal_callback_messages_will_be_ignored")
        elif job.status in ACTIVE_DOCUMENT_JOB_STATUSES:
            if callback_observation.replayable_count == 0 and not self._active_job_needs_enqueue_replay(job, stale_job_detected):
                missing_gates.append("no_replayable_work")
            if self.task_queue is None:
                missing_gates.append("document_jobs_worker_backend_disabled")
        else:
            missing_gates.append("status_not_replayable")
        if job is not None and job.status in ACTIVE_DOCUMENT_JOB_STATUSES and self.settings.document_jobs_worker_backend == "eager":
            warnings.append("manual_replay_enqueue_only_with_eager_backend")
        return DocumentJobReplayPreview(
            job=job,
            eligible=job is not None and not missing_gates,
            missing_gates=_unique_preserve_order(missing_gates),
            warnings=_unique_preserve_order(warnings),
            callback_observation=callback_observation,
            stale_job_detected=stale_job_detected,
            worker_backend=self.settings.document_jobs_worker_backend,
            automatic_execution_enabled=self.settings.document_jobs_worker_backend in {"celery", "eager"},
        )

    def execute_replay(
        self,
        job_id: str,
        *,
        trace_id: str | None,
        run_inline: bool = False,
    ) -> DocumentJobReplayExecutionResult:
        """执行 recovery replay：终态只清理 callback；非终态只投递 Worker。"""

        preview = self.preview_replay(job_id)
        if not preview.eligible or preview.job is None:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"document_job replay 不满足执行条件: {', '.join(preview.missing_gates) or 'unknown'}",
            )
        job = preview.job
        replayable_messages = self.callback_message_store.list_replayable_callback_messages(job.id)
        ignored_count = 0
        recovery_events_written = 0
        queued_task_id: str | None = None
        if job.status in TERMINAL_DOCUMENT_JOB_STATUSES:
            for message in replayable_messages:
                ignored = self.callback_message_store.mark_callback_message_ignored(
                    message.id,
                    error_code="job_terminal_recovery_cleanup",
                    error_message=f"Recovery cleanup 忽略终态任务 callback: status={job.status}",
                    updated_at=utc_now(),
                )
                self._record_event(
                    job,
                    event_type="recovery_callback_ignored",
                    level="warning",
                    message="Recovery replay 已忽略终态任务的 callback message。",
                    payload={
                        "message_id": ignored.id,
                        "callback_status": ignored.status,
                        "error_code": ignored.error_code,
                        "worker_backend": self.settings.document_jobs_worker_backend,
                    },
                    trace_id=trace_id,
                )
                ignored_count += 1
                recovery_events_written += 1
        else:
            if self.task_queue is None:
                raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "document_jobs worker 未启用。")
            queued_task_id = self.task_queue.enqueue(job.id, trace_id=trace_id, run_inline=run_inline)
            self._record_event(
                job,
                event_type="recovery_replay_queued",
                level="warning" if preview.stale_job_detected else "info",
                message="Recovery replay 已投递 document_jobs Worker。",
                payload={
                    "queued_task_id": queued_task_id,
                    "worker_backend": self.settings.document_jobs_worker_backend,
                    "run_inline": run_inline,
                    "replayable_callback_messages": len(replayable_messages),
                    "stale_job_detected": preview.stale_job_detected,
                    "callback_status_counts": preview.callback_observation.status_counts,
                },
                trace_id=trace_id,
            )
            recovery_events_written += 1
        return DocumentJobReplayExecutionResult(
            preview=preview,
            executed=True,
            queued_task_id=queued_task_id,
            replayable_callback_messages=len(replayable_messages),
            ignored_callback_messages=ignored_count,
            recovery_events_written=recovery_events_written,
        )

    def run_startup_recovery(
        self, *, trace_id: str | None = "startup", polling_only: bool = False,
    ) -> DocumentJobStartupRecoveryResult:
        """进程启动后尝试重放可恢复 document_jobs；单任务失败只记录日志不阻断启动。"""

        if self.task_queue is None:
            self.logger.warning(
                "[trace_id=%s document_jobs_recovery=startup status=skipped reason=worker_backend_disabled]",
                trace_id,
            )
            return DocumentJobStartupRecoveryResult(
                scanned_jobs=0,
                eligible_jobs=0,
                queued_jobs=0,
                ignored_callback_messages=0,
                failed_jobs=0,
                skipped_reason="document_jobs_worker_backend_disabled",
            )
        jobs = self.job_repository.list_document_jobs()
        eligible_jobs = 0
        queued_jobs = 0
        ignored_callback_messages = 0
        failed_jobs = 0
        run_inline = self.settings.document_jobs_worker_backend == "eager"
        for job in jobs:
            if polling_only and not is_mineru_polling_job(self.settings, job):
                continue
            try:
                preview = self.preview_replay(job.id)
                if not preview.eligible:
                    continue
                eligible_jobs += 1
                result = self.execute_replay(job.id, trace_id=trace_id, run_inline=run_inline)
                if result.queued_task_id is not None or (result.preview.job and result.preview.job.status not in TERMINAL_DOCUMENT_JOB_STATUSES):
                    queued_jobs += 1
                ignored_callback_messages += result.ignored_callback_messages
            except Exception:
                failed_jobs += 1
                self.logger.exception(
                    "[trace_id=%s document_jobs_recovery=startup job_id=%s status=failed]",
                    trace_id,
                    job.id,
                )
        return DocumentJobStartupRecoveryResult(
            scanned_jobs=len(jobs),
            eligible_jobs=eligible_jobs,
            queued_jobs=queued_jobs,
            ignored_callback_messages=ignored_callback_messages,
            failed_jobs=failed_jobs,
        )

    def _build_recent_problem_messages(self, job_id: str | None) -> list[DocumentJobCallbackProblemSummary]:
        messages = self.callback_message_store.list_callback_messages(
            job_id,
            statuses={"failed", "ignored"},
        )
        messages.sort(key=lambda message: (message.updated_at, message.id), reverse=True)
        return [
            DocumentJobCallbackProblemSummary(
                message_id=message.id,
                status=message.status,
                error_code=message.error_code,
                error_message=message.error_message,
                attempts=message.attempts,
                updated_at=message.updated_at,
            )
            for message in messages[:RECENT_PROBLEM_MESSAGE_LIMIT]
        ]

    def _active_job_needs_enqueue_replay(self, job: DocumentJobRecord, stale_job_detected: bool) -> bool:
        return is_mineru_polling_job(self.settings, job) or job.status in {"pending", "queued"} or stale_job_detected

    def _is_stale_active_job(self, job: DocumentJobRecord | None) -> bool:
        if job is None or job.archived_at is not None or job.status not in ACTIVE_DOCUMENT_JOB_STATUSES:
            return False
        age_seconds = max(0, int((utc_now() - job.updated_at).total_seconds()))
        return age_seconds >= DOCUMENT_JOB_RECOVERY_STALE_SECONDS

    def _record_event(
        self,
        job: DocumentJobRecord,
        *,
        event_type: DocumentJobEventType,
        level: DocumentJobEventLevel,
        message: str,
        payload: dict[str, Any],
        trace_id: str | None,
    ) -> None:
        event = DocumentJobEventRecord(
            id=f"evt_{uuid4().hex[:12]}",
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            stage=job.stage,
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
            trace_id=trace_id,
        )
        self.event_repository.append_document_job_event(job.id, event)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
