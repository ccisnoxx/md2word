from __future__ import annotations

# File: app/domains/document_jobs/incidents.py
# Purpose: Build lightweight document_job incident queue projections without persisting Incident records.

from collections import Counter
from datetime import datetime
from typing import Any, get_args

from fastapi import status

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobStage, DocumentJobStatus
from app.domains.document_jobs.schemas import (
    DocumentJobAvailableActionResponse,
    DocumentJobIncidentBulkItemResponse,
    DocumentJobIncidentBulkResponse,
    DocumentJobIncidentDiagnosticResponse,
    DocumentJobIncidentEventSummaryResponse,
    DocumentJobIncidentEvidenceLinkResponse,
    DocumentJobIncidentFailureType,
    DocumentJobIncidentFileSummaryResponse,
    DocumentJobIncidentListResponse,
    DocumentJobIncidentQueueItemResponse,
    DocumentJobIncidentRetryCountBucket,
    DocumentJobIncidentSort,
    DocumentJobIncidentSummaryResponse,
    DocumentJobResponse,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.auth.models import AuthenticatedUser


DOCUMENT_JOB_INCIDENT_BULK_LIMIT = 50
DEFAULT_STALLED_MINUTES = 10
ACTIVE_DOCUMENT_JOB_STATUSES = {"pending", "queued", "running"}
DOCUMENT_JOB_INCIDENT_FAILURE_TYPES = set(get_args(DocumentJobIncidentFailureType))
DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS = set(get_args(DocumentJobIncidentRetryCountBucket))
DOCUMENT_JOB_INCIDENT_SORTS = set(get_args(DocumentJobIncidentSort))
WORKER_OR_DISPATCH_TOKENS = ("worker", "enqueue", "dispatch", "celery", "queue")
ARTIFACT_MISSING_TOKENS = ("artifact", "missing", "file_missing", "not_found", "object")
TRANSLATION_FAILURE_TOKENS = ("translation", "translator", "provider", "ai_", "term")
CONVERSION_FAILURE_TOKENS = ("mineru", "parse", "render", "convert", "conversion", "upload")


class DocumentJobIncidentService:
    """Lightweight incident queue projection over document_jobs metadata."""

    def __init__(self, document_job_service: Any) -> None:
        self.document_job_service = document_job_service

    def list_incidents(
        self,
        *,
        user: AuthenticatedUser,
        page: int,
        page_size: int,
        status_filter: str | None,
        stage_filter: str | None,
        failure_type: str | None,
        retryable: bool | None,
        retry_count: str | None,
        stalled_minutes: int | None,
        q: str | None,
        sort: str,
    ) -> DocumentJobIncidentListResponse:
        """Return filtered, priority-sorted incident projections for visible document_jobs."""

        self._validate_list_filters(
            status_filter=status_filter,
            stage_filter=stage_filter,
            failure_type=failure_type,
            retry_count=retry_count,
            sort=sort,
        )
        now = utc_now()
        normalized_q = self._normalize_optional_text(q)
        candidates = [
            item
            for job in self.document_job_service.list_visible_jobs(user=user)
            for item in [self._build_item(job, user=user, now=now)]
            if item.is_incident
        ]
        filtered = [
            item
            for item in candidates
            if self._matches_status(item, status_filter)
            and self._matches_stage(item, stage_filter)
            and self._matches_failure_type(item, failure_type)
            and self._matches_retryable(item, retryable)
            and self._matches_retry_count(item, retry_count)
            and self._matches_stalled_minutes(item, stalled_minutes)
            and self._matches_query(item, normalized_q)
        ]
        filtered.sort(key=lambda item: self._sort_key(item, sort), reverse=self._sort_reverse(sort))
        start = (page - 1) * page_size
        return DocumentJobIncidentListResponse(
            items=filtered[start:start + page_size],
            page=page,
            page_size=page_size,
            total=len(filtered),
            summary=self._build_summary(filtered),
        )

    def get_diagnostics(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> DocumentJobIncidentDiagnosticResponse:
        """Return a compact diagnostic packet for the incident drawer."""

        job = self.document_job_service.get_job(job_id, user=user)
        now = utc_now()
        item = self._build_item(job, user=user, now=now)
        events = sorted(
            self.document_job_service.list_events(job_id, user=user),
            key=lambda event: event.created_at,
            reverse=True,
        )[:8]
        files = self.document_job_service.list_files(job_id, user=user)
        return DocumentJobIncidentDiagnosticResponse(
            item=item,
            evidence_links=self._build_evidence_links(job),
            recent_events=[self._build_event_summary(event) for event in events],
            files=[self._build_file_summary(file) for file in files],
        )

    def bulk_retry(
        self,
        *,
        user: AuthenticatedUser,
        job_ids: list[str],
        reason: str | None,
        trace_id: str | None,
    ) -> DocumentJobIncidentBulkResponse:
        """Retry selected retryable incidents and return per-item partial results."""

        normalized = self._validate_bulk_ids(job_ids)
        items: list[DocumentJobIncidentBulkItemResponse] = []
        for job_id in normalized:
            try:
                job = self.document_job_service.get_job(job_id, user=user)
                current_item = self._build_item(job, user=user, now=utc_now())
                if not current_item.retryable:
                    items.append(
                        DocumentJobIncidentBulkItemResponse(
                            job_id=job_id,
                            ok=False,
                            skipped=True,
                            status_code=status.HTTP_409_CONFLICT,
                            error_code="not_retryable",
                            detail=current_item.retry_disabled_reason or "当前异常不可重试。",
                            item=current_item,
                        )
                    )
                    continue
                retried = self.document_job_service.retry_job(
                    job_id,
                    user=user,
                    reason=reason,
                    trace_id=trace_id,
                )
                items.append(
                    DocumentJobIncidentBulkItemResponse(
                        job_id=job_id,
                        ok=True,
                        status_code=status.HTTP_200_OK,
                        item=self._build_item(retried, user=user, now=utc_now()),
                    )
                )
            except ApiError as exc:
                items.append(self._build_failure(job_id, exc))
        return self._build_bulk_response("retry", items)

    def bulk_refresh(
        self,
        *,
        user: AuthenticatedUser,
        job_ids: list[str],
    ) -> DocumentJobIncidentBulkResponse:
        """Return current incident projections for selected jobs without mutation."""

        normalized = self._validate_bulk_ids(job_ids)
        items: list[DocumentJobIncidentBulkItemResponse] = []
        for job_id in normalized:
            try:
                job = self.document_job_service.get_job(job_id, user=user)
                items.append(
                    DocumentJobIncidentBulkItemResponse(
                        job_id=job_id,
                        ok=True,
                        status_code=status.HTTP_200_OK,
                        item=self._build_item(job, user=user, now=utc_now()),
                    )
                )
            except ApiError as exc:
                items.append(self._build_failure(job_id, exc))
        return self._build_bulk_response("refresh", items)

    def _build_item(
        self,
        job: DocumentJobRecord,
        *,
        user: AuthenticatedUser,
        now: datetime,
    ) -> DocumentJobIncidentQueueItemResponse:
        actions = self.document_job_service.build_available_actions(job, user=user)
        retry_action = actions.get("retry")
        retryable = bool(retry_action and retry_action.enabled and retry_action.retryable)
        retry_disabled_reason = retry_action.disabled_reason if retry_action else "后端未返回重试动作。"
        stalled_minutes = self._stalled_minutes(job, now)
        stalled = stalled_minutes is not None and stalled_minutes >= DEFAULT_STALLED_MINUTES
        blocked = job.translation_qa_status == "blocked"
        is_incident = job.status == "failed" or blocked or retryable or stalled
        failure_type = self._classify_failure(job, stalled=stalled)
        priority = self._priority(job, retryable=retryable, stalled=stalled, blocked=blocked)
        suggested_action = self._suggested_action(
            job,
            failure_type=failure_type,
            retryable=retryable,
            retry_disabled_reason=retry_disabled_reason,
            stalled=stalled,
        )
        return DocumentJobIncidentQueueItemResponse(
            job=DocumentJobResponse(
                **job.model_dump(mode="python"),
                available_actions=actions,
            ),
            failure_type=failure_type,
            priority=priority,
            is_incident=is_incident,
            retryable=retryable,
            retry_disabled_reason=None if retryable else retry_disabled_reason,
            stalled=stalled,
            stalled_minutes=stalled_minutes,
            blocked=blocked,
            suggested_action=suggested_action,
            evidence_summary=self._evidence_summary(
                job,
                retry_action=retry_action,
                stalled=stalled,
                stalled_minutes=stalled_minutes,
            ),
        )

    def _validate_list_filters(
        self,
        *,
        status_filter: str | None,
        stage_filter: str | None,
        failure_type: str | None,
        retry_count: str | None,
        sort: str,
    ) -> None:
        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
        if stage_filter is not None and stage_filter not in get_args(DocumentJobStage):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "stage 查询参数非法。")
        if failure_type is not None and failure_type not in DOCUMENT_JOB_INCIDENT_FAILURE_TYPES:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "failure_type 查询参数非法。")
        if retry_count is not None and retry_count not in DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "retry_count 查询参数非法。")
        if sort not in DOCUMENT_JOB_INCIDENT_SORTS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 查询参数非法。")

    def _validate_bulk_ids(self, job_ids: list[str]) -> list[str]:
        normalized = [job_id.strip() for job_id in job_ids]
        if not normalized:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能为空。")
        if len(normalized) > DOCUMENT_JOB_INCIDENT_BULK_LIMIT:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"job_ids 最多支持 {DOCUMENT_JOB_INCIDENT_BULK_LIMIT} 个。",
            )
        if any(not job_id for job_id in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能包含空值。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "job_ids 不能重复。")
        return normalized

    def _classify_failure(self, job: DocumentJobRecord, *, stalled: bool) -> DocumentJobIncidentFailureType:
        if stalled or job.error_code == "document_job_timeout":
            return "timeout_or_stalled"
        haystack = self._failure_haystack(job)
        if any(token in haystack for token in WORKER_OR_DISPATCH_TOKENS):
            return "worker_or_dispatch_failed"
        if self._has_missing_artifact_signal(job, haystack):
            return "artifact_missing"
        if job.translation_qa_status == "blocked":
            return "qa_unavailable"
        if is_translation_document_job_mode(job.mode) and (
            job.failed_stage == "ir_converting" or any(token in haystack for token in TRANSLATION_FAILURE_TOKENS)
        ):
            return "translation_failed"
        if job.status == "failed" and (
            job.failed_stage in {"parsing", "rendering", "uploading"} or any(token in haystack for token in CONVERSION_FAILURE_TOKENS)
        ):
            return "conversion_failed"
        return "unknown"

    def _failure_haystack(self, job: DocumentJobRecord) -> str:
        values = [
            job.failed_stage,
            job.error_code,
            job.error_message,
            job.translation_qa_issue_type,
            job.translation_qa_note,
        ]
        return " ".join(value for value in values if value).casefold()

    def _has_missing_artifact_signal(self, job: DocumentJobRecord, haystack: str) -> bool:
        if job.translation_qa_issue_type == "artifact_missing":
            return True
        if job.status == "succeeded" and job.result_file_id is None:
            return True
        if is_translation_document_job_mode(job.mode) and job.translation_qa_status == "blocked" and job.document_ir_file_id is None:
            return True
        return any(token in haystack for token in ARTIFACT_MISSING_TOKENS)

    def _priority(self, job: DocumentJobRecord, *, retryable: bool, stalled: bool, blocked: bool) -> int:
        if stalled or blocked:
            return 0
        if retryable:
            return 1
        if job.status == "failed":
            return 2
        return 3

    def _suggested_action(
        self,
        job: DocumentJobRecord,
        *,
        failure_type: DocumentJobIncidentFailureType,
        retryable: bool,
        retry_disabled_reason: str | None,
        stalled: bool,
    ) -> str:
        if stalled:
            return "长时间未更新，先刷新状态"
        if job.retry_count >= 2:
            return "多次失败，建议查看事件日志"
        if retryable:
            return "可直接重试"
        if failure_type == "artifact_missing":
            return "缺少产物，先打开详情检查"
        if failure_type == "worker_or_dispatch_failed":
            return "Worker 或投递失败，建议查看事件日志"
        if failure_type == "qa_unavailable":
            return "QA 证据不足，打开 QA 详情检查"
        return retry_disabled_reason or "打开详情查看诊断"

    def _evidence_summary(
        self,
        job: DocumentJobRecord,
        *,
        retry_action: DocumentJobAvailableActionResponse | None,
        stalled: bool,
        stalled_minutes: int | None,
    ) -> list[str]:
        evidence: list[str] = []
        if job.failed_stage:
            evidence.append(f"failed_stage={job.failed_stage}")
        if job.error_code:
            evidence.append(f"error_code={job.error_code}")
        if job.error_message:
            evidence.append(job.error_message)
        if stalled and stalled_minutes is not None:
            evidence.append(f"stalled_minutes={stalled_minutes}")
        if retry_action and not retry_action.enabled and retry_action.disabled_reason:
            evidence.append(retry_action.disabled_reason)
        return evidence[:4]

    def _stalled_minutes(self, job: DocumentJobRecord, now: datetime) -> int | None:
        if job.status not in ACTIVE_DOCUMENT_JOB_STATUSES:
            return None
        if job.timeout_at is not None and job.timeout_at <= now:
            return max(0, int((now - job.timeout_at).total_seconds() // 60))
        return max(0, int((now - job.updated_at).total_seconds() // 60))

    def _matches_status(self, item: DocumentJobIncidentQueueItemResponse, status_filter: str | None) -> bool:
        return status_filter is None or item.job.status == status_filter

    def _matches_stage(self, item: DocumentJobIncidentQueueItemResponse, stage_filter: str | None) -> bool:
        return stage_filter is None or item.job.stage == stage_filter or item.job.failed_stage == stage_filter

    def _matches_failure_type(self, item: DocumentJobIncidentQueueItemResponse, failure_type: str | None) -> bool:
        return failure_type is None or item.failure_type == failure_type

    def _matches_retryable(self, item: DocumentJobIncidentQueueItemResponse, retryable: bool | None) -> bool:
        return retryable is None or item.retryable is retryable

    def _matches_retry_count(self, item: DocumentJobIncidentQueueItemResponse, retry_count: str | None) -> bool:
        if retry_count is None:
            return True
        if retry_count == "0":
            return item.job.retry_count == 0
        if retry_count == "1_2":
            return 1 <= item.job.retry_count <= 2
        return item.job.retry_count >= 3

    def _matches_stalled_minutes(self, item: DocumentJobIncidentQueueItemResponse, stalled_minutes: int | None) -> bool:
        if stalled_minutes is None:
            return True
        return item.stalled_minutes is not None and item.stalled_minutes >= stalled_minutes

    def _matches_query(self, item: DocumentJobIncidentQueueItemResponse, q: str | None) -> bool:
        if q is None:
            return True
        values = [
            *self.document_job_service.document_job_search_values(item.job),
            item.failure_type,
            item.suggested_action,
            *item.evidence_summary,
        ]
        return any(q in value.casefold() for value in values if value)

    def _sort_key(self, item: DocumentJobIncidentQueueItemResponse, sort: str) -> tuple[Any, ...]:
        if sort == "priority":
            return (item.priority, -self._timestamp(item.job.updated_at), item.job.id)
        if sort == "updated_at_asc":
            return (self._timestamp(item.job.updated_at), item.job.id)
        if sort == "updated_at_desc":
            return (self._timestamp(item.job.updated_at), item.job.id)
        if sort == "retry_count_asc":
            return (item.job.retry_count, self._timestamp(item.job.updated_at), item.job.id)
        return (item.job.retry_count, self._timestamp(item.job.updated_at), item.job.id)

    def _sort_reverse(self, sort: str) -> bool:
        return sort in {"updated_at_desc", "retry_count_desc"}

    def _timestamp(self, value: str | datetime) -> float:
        if isinstance(value, datetime):
            return value.timestamp()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

    def _build_summary(self, items: list[DocumentJobIncidentQueueItemResponse]) -> DocumentJobIncidentSummaryResponse:
        statuses = Counter(item.job.status for item in items)
        failure_types = Counter(item.failure_type for item in items)
        failed_count = sum(1 for item in items if item.job.status == "failed")
        retryable_count = sum(1 for item in items if item.retryable)
        return DocumentJobIncidentSummaryResponse(
            total=len(items),
            failed=failed_count,
            blocked=sum(1 for item in items if item.blocked),
            stalled=sum(1 for item in items if item.stalled),
            retryable=retryable_count,
            non_retryable=failed_count - retryable_count,
            by_status=dict(statuses),
            by_failure_type={failure_type: failure_types.get(failure_type, 0) for failure_type in get_args(DocumentJobIncidentFailureType)},
        )

    def _build_evidence_links(self, job: DocumentJobRecord) -> list[DocumentJobIncidentEvidenceLinkResponse]:
        links = [
            DocumentJobIncidentEvidenceLinkResponse(
                kind="detail",
                title="任务详情",
                target=f"/jobs/{job.id}",
                helper="查看完整状态、事件和文件。",
            ),
            DocumentJobIncidentEvidenceLinkResponse(
                kind="events",
                title="事件时间线",
                target=f"/jobs/{job.id}",
                helper="详情页事件区展示完整事件。",
            ),
            DocumentJobIncidentEvidenceLinkResponse(
                kind="files",
                title="任务文件",
                target=f"/jobs/{job.id}",
                helper="详情页文件区展示已登记产物。",
            ),
        ]
        if is_translation_document_job_mode(job.mode):
            links.append(
                DocumentJobIncidentEvidenceLinkResponse(
                    kind="translation_qa",
                    title="翻译 QA",
                    target=f"/jobs/{job.id}/translation-qa",
                    available=job.document_ir_file_id is not None,
                    helper="查看翻译证据与 QA 状态。",
                )
            )
        return links

    def _build_event_summary(self, event: Any) -> DocumentJobIncidentEventSummaryResponse:
        return DocumentJobIncidentEventSummaryResponse(
            id=event.id,
            stage=event.stage,
            level=event.level,
            event_type=event.event_type,
            message=event.message,
            duration_ms=event.duration_ms,
            trace_id=event.trace_id,
            created_at=event.created_at,
        )

    def _build_file_summary(self, file: DocumentFileRecord) -> DocumentJobIncidentFileSummaryResponse:
        return DocumentJobIncidentFileSummaryResponse(
            file_id=file.id,
            file_type=file.file_type,
            original_filename=file.original_filename,
            storage_provider=file.storage_provider,
            status=file.status,
            size_bytes=file.size_bytes,
            expires_at=file.expires_at,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    def _build_failure(self, job_id: str, exc: ApiError) -> DocumentJobIncidentBulkItemResponse:
        return DocumentJobIncidentBulkItemResponse(
            job_id=job_id,
            ok=False,
            status_code=exc.status_code,
            error_code=exc.code,
            detail=exc.message,
        )

    def _build_bulk_response(
        self,
        action: str,
        items: list[DocumentJobIncidentBulkItemResponse],
    ) -> DocumentJobIncidentBulkResponse:
        succeeded = sum(1 for item in items if item.ok)
        skipped = sum(1 for item in items if item.skipped)
        failed = sum(1 for item in items if not item.ok and not item.skipped)
        return DocumentJobIncidentBulkResponse(
            action=action,
            total=len(items),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            items=items,
        )

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
