from __future__ import annotations

# app/domains/document_jobs/use_cases/queries.py: 用例：任务列表、事件、文件与翻译批次查询。

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, get_args

from fastapi import status

from app.core.errors import ApiError
from app.domains.document_jobs.list_query import (
    DocumentJobListProjectionUnavailable,
    DocumentJobListQuery,
    DocumentJobSearchable,
)
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobStatus,
    DocumentJobTranslationBatchRecord,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import DOCUMENT_JOB_LIST_SORTS, DocumentJobListResult
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.document_jobs.workflow import DOCUMENT_JOB_STATUS_GROUPS, TranslationGenerationSummary
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileReaderProtocol
from app.domains.resources.models import utc_now
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.auth.models import AuthenticatedUser


class TranslationGenerationSummarizer(Protocol):
    """按当前 source/config 重算权威代次结论的窄端口，由翻译执行门面实现。"""

    def summarize_generation(
        self,
        job: DocumentJobRecord,
        batches: list[DocumentJobTranslationBatchRecord] | None = None,
    ) -> TranslationGenerationSummary | None:
        ...


@dataclass(frozen=True)
class TranslationBatchListView:
    """翻译批次诊断视图：job 与 batches 来自同一仓储快照；summary 为 None 表示无法给出权威结论。"""

    job: DocumentJobRecord
    batches: list[DocumentJobTranslationBatchRecord]
    summary: TranslationGenerationSummary | None


class DocumentJobQueries:
    """用例：任务列表、事件、文件与翻译批次查询。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        event_repository: DocumentJobEventRepositoryProtocol,
        document_job_translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol | None,
        translation_generation_summarizer: TranslationGenerationSummarizer | None,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
    ) -> None:
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.document_job_translation_batch_repository = document_job_translation_batch_repository
        self.translation_generation_summarizer = translation_generation_summarizer
        self.access = access
        self.read_model = read_model

    def list_jobs(
        self,
        *,
        user: AuthenticatedUser,
        page: int,
        page_size: int,
        status_filter: str | None,
        status_group: str | None = None,
        translation_qa_status: str | None = None,
        q: str | None = None,
        sort: str = "created_at_desc",
        include_archived: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> DocumentJobListResult:
        """返回当前用户可见的 document_jobs 分页列表。"""

        if status_filter is not None and status_group is not None:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 与 status_group 不能同时使用。")
        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
        if status_group is not None and status_group not in DOCUMENT_JOB_STATUS_GROUPS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status_group 查询参数非法。")
        translation_qa_filters = set(get_args(DocumentJobTranslationQaStatus)) | {"all"}
        if translation_qa_status is not None and translation_qa_status not in translation_qa_filters:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "translation_qa_status 查询参数非法。")
        if sort not in DOCUMENT_JOB_LIST_SORTS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 查询参数非法。")
        if created_from is not None and created_to is not None and created_from > created_to:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "created_from 不能晚于 created_to。")
        normalized_q = self.access.normalize_optional_text(q)
        query = DocumentJobListQuery(
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            created_by=None if user.role == "admin" else user.id,
            page=page,
            page_size=page_size,
            statuses=(status_filter,) if status_filter is not None else (
                tuple(DOCUMENT_JOB_STATUS_GROUPS[status_group]) if status_group is not None else None
            ),
            translation_qa_status=translation_qa_status,
            q=normalized_q.casefold() if normalized_q is not None else None,
            sort=sort,
            include_archived=include_archived,
            created_from=created_from,
            created_to=created_to,
            as_of=utc_now(),
        )
        try:
            result = self.job_repository.query_document_jobs(query)
            # 明确的 None 也属于本次观察，不能在页面动作阶段重读成另一个结果。
            items = [self.read_model.build_job_read_view(job, user=user,
                observed_result=result.observed_results[job.id], as_of=query.as_of,
                check_publication_evidence=False) for job in result.items]
        except DocumentJobListProjectionUnavailable as error:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable",
                "任务列表查询事实尚未就绪，请完成校准后重试。") from error
        return DocumentJobListResult(
            items=items,
            total=result.total,
            summary=result.summary,
            filtered_summary=result.filtered_summary,
            translation_qa_summary=result.translation_qa_summary,
        )

    def list_events(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentJobEventRecord]:
        """先按任务权限校验，再返回事件列表。"""

        self.access.get_job(job_id, user=user)
        return self.event_repository.list_document_job_events(job_id)

    def list_translation_batches(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> list[DocumentJobTranslationBatchRecord]:
        """只读返回任务当前 retry_count generation 的翻译 provider 批次诊断。"""

        job = self.access.get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            return []
        if self.document_job_translation_batch_repository is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次诊断仓储未配置。")
        return self.document_job_translation_batch_repository.list_translation_batches(
            job.id,
            generation=job.retry_count,
        )

    def get_translation_batch_view(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> TranslationBatchListView:
        """在同一仓储快照上返回已授权任务、当前代批次与权威代次结论。"""

        job, batches = self.get_translation_batch_snapshot(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            # direct 任务不加载翻译资源，结论恒为空。
            return TranslationBatchListView(job=job, batches=batches, summary=None)
        if self.translation_generation_summarizer is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次结论服务未配置。")
        return TranslationBatchListView(
            job=job,
            batches=batches,
            summary=self.translation_generation_summarizer.summarize_generation(job, batches),
        )

    def get_translation_batch_snapshot(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> tuple[DocumentJobRecord, list[DocumentJobTranslationBatchRecord]]:
        """在同一仓储快照上返回已授权任务与当前代批次。"""

        # 先做一次轻量鉴权，再让仓储在同一锁快照中读取真正的当前 job 和批次代次。
        # 不能把鉴权读取到的 retry_count 带入 snapshot，否则换代窗口会混合新 job 与旧批次。
        job = self.access.get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            return job, []
        if self.document_job_translation_batch_repository is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次诊断仓储未配置。")
        snapshot_job, batches = self.document_job_translation_batch_repository.get_translation_batch_snapshot(
            job.id,
        )
        if not self.access.is_visible(snapshot_job, user):
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "文档任务不存在。")
        # 当前三类 adapter 的 generation=None 快照会带回历史记录；按同一锁快照返回的
        # job.retry_count 过滤，避免历史批次进入当前代 API 投影。
        return self.access.effective_job(snapshot_job), [batch for batch in batches if batch.generation == snapshot_job.retry_count]

    def list_visible_jobs(
        self,
        *,
        user: AuthenticatedUser,
        include_archived: bool = False,
        file_reader: DocumentFileReaderProtocol | None = None,
    ) -> list[DocumentJobRecord]:
        """按可见性取得有效读投影，供异常队列使用。"""

        return [
            self.access.effective_job(job, file_reader=file_reader)
            for job in self.job_repository.list_document_jobs()
            if self.access.is_visible(job, user)
            and job.deleted_at is None
            and (include_archived or job.archived_at is None)
        ]

    def document_job_search_values(self, job: DocumentJobSearchable) -> list[str]:
        """Return the shared document_job search fields used by queue projections."""

        return self._document_job_search_values(job)

    def list_files(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentFileRecord]:
        """先按任务权限校验，再返回任务上下文内可展示的文件元数据。"""

        job = self.access.get_job(job_id, user=user)
        return self.access.list_files_for_job(job)

    def _document_job_search_values(self, job: DocumentJobSearchable) -> list[str]:
        source_file = job.request_snapshot.get("source_file")
        source_filename = None
        if isinstance(source_file, dict):
            raw_filename = source_file.get("original_filename")
            if isinstance(raw_filename, str):
                source_filename = raw_filename
        return [
            value
            for value in (
                job.id,
                job.source_file_id,
                source_filename,
                job.error_code,
                job.error_message,
            )
            if value
        ]
