from __future__ import annotations

# app/domains/document_jobs/use_cases/__init__.py: document_jobs 应用层用例集合与装配入口。
#
# 依赖方向：用例（submission/lifecycle_commands/publication/quality_review/table_references/
# translation_qa/downloads/queries）只依赖共享组件（events/access/read_model/review_writer/
# dispatcher/request_snapshot），用例之间互不依赖；共享组件之间只允许 read_model/review_writer/
# request_snapshot -> access、review_writer/dispatcher -> events。

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.dispatcher import DocumentJobDispatcher
from app.domains.document_jobs.use_cases.downloads import DocumentJobDownloads
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.document_jobs.use_cases.lifecycle_commands import DocumentJobLifecycleCommands
from app.domains.document_jobs.use_cases.publication import DocumentJobPublication
from app.domains.document_jobs.use_cases.quality_review import DocumentJobQualityReview
from app.domains.document_jobs.use_cases.queries import DocumentJobQueries
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.document_jobs.use_cases.request_snapshot import DocumentJobRequestSnapshots
from app.domains.document_jobs.use_cases.review_writer import DocumentReviewWriter
from app.domains.document_jobs.use_cases.submission import DocumentJobSubmission
from app.domains.document_jobs.use_cases.table_references import DocumentJobTableReferences
from app.domains.document_jobs.use_cases.translation_qa import DocumentJobTranslationQa
from app.domains.files.repository import DocumentFileRepositoryProtocol


@dataclass(frozen=True)
class DocumentJobUseCases:
    """进程内共享的 document_jobs 用例与共享组件；router、异常中心直接按用例取用。"""

    events: DocumentJobEventWriter
    access: DocumentJobAccess
    read_model: DocumentJobReadModel
    review_writer: DocumentReviewWriter
    dispatcher: DocumentJobDispatcher
    request_snapshot: DocumentJobRequestSnapshots
    submission: DocumentJobSubmission
    lifecycle_commands: DocumentJobLifecycleCommands
    publication: DocumentJobPublication
    quality_review: DocumentJobQualityReview
    table_references: DocumentJobTableReferences
    translation_qa: DocumentJobTranslationQa
    downloads: DocumentJobDownloads
    queries: DocumentJobQueries


def build_document_job_use_cases(
    settings: Settings,
    job_repository: DocumentJobRepositoryProtocol,
    event_repository: DocumentJobEventRepositoryProtocol,
    file_repository: DocumentFileRepositoryProtocol,
    task_queue: DocumentJobTaskQueueProtocol | None = None,
    template_read_service: Any | None = None,
    term_version_service: Any | None = None,
    job_resource_snapshot_service: Any | None = None,
    document_job_translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol | None = None,
    file_upload_service: Any | None = None,
    word_preview_service: Any | None = None,
    audit_service: Any | None = None,
) -> DocumentJobUseCases:
    """按依赖方向构造全部组件；参数顺序与默认值沿用拆分前的应用服务构造函数。"""

    events = DocumentJobEventWriter(event_repository=event_repository)
    access = DocumentJobAccess(job_repository=job_repository, file_repository=file_repository,
                               file_upload_service=file_upload_service)
    read_model = DocumentJobReadModel(settings=settings, job_repository=job_repository, file_repository=file_repository,
                                      job_resource_snapshot_service=job_resource_snapshot_service,
                                      file_upload_service=file_upload_service, access=access)
    review_writer = DocumentReviewWriter(job_repository=job_repository, file_repository=file_repository,
                                         file_upload_service=file_upload_service, events=events, access=access)
    dispatcher = DocumentJobDispatcher(settings=settings, job_repository=job_repository, task_queue=task_queue,
                                       events=events)
    request_snapshot = DocumentJobRequestSnapshots(settings=settings, template_read_service=template_read_service,
                                                   term_version_service=term_version_service,
                                                   job_resource_snapshot_service=job_resource_snapshot_service,
                                                   access=access)
    return DocumentJobUseCases(
        events=events,
        access=access,
        read_model=read_model,
        review_writer=review_writer,
        dispatcher=dispatcher,
        request_snapshot=request_snapshot,
        submission=DocumentJobSubmission(
            settings=settings, job_repository=job_repository, file_repository=file_repository, task_queue=task_queue,
            word_preview_service=word_preview_service, events=events, access=access, read_model=read_model,
            dispatcher=dispatcher, request_snapshot=request_snapshot),
        lifecycle_commands=DocumentJobLifecycleCommands(
            job_repository=job_repository, file_upload_service=file_upload_service, events=events, access=access,
            read_model=read_model),
        publication=DocumentJobPublication(
            settings=settings, job_repository=job_repository, file_repository=file_repository, task_queue=task_queue,
            job_resource_snapshot_service=job_resource_snapshot_service, file_upload_service=file_upload_service,
            audit_service=audit_service, events=events, access=access, read_model=read_model, dispatcher=dispatcher),
        quality_review=DocumentJobQualityReview(
            job_repository=job_repository, file_repository=file_repository, file_upload_service=file_upload_service,
            access=access, read_model=read_model, review_writer=review_writer),
        table_references=DocumentJobTableReferences(
            file_repository=file_repository, file_upload_service=file_upload_service, access=access),
        translation_qa=DocumentJobTranslationQa(
            file_repository=file_repository, file_upload_service=file_upload_service, access=access,
            review_writer=review_writer),
        downloads=DocumentJobDownloads(
            job_repository=job_repository, file_repository=file_repository, events=events, access=access),
        queries=DocumentJobQueries(
            job_repository=job_repository, event_repository=event_repository,
            document_job_translation_batch_repository=document_job_translation_batch_repository, access=access,
            read_model=read_model),
    )
