from __future__ import annotations

# app/domains/document_jobs/use_cases/access.py: 任务读取授权、有效读投影与任务文件归属判断的共享 owner。

from datetime import datetime
from typing import Any


from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import PREVIEW_FILE_TYPES, verified_current_preview_files
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import effective_review_job
from app.domains.document_jobs.use_cases.common import (
    DOCUMENT_JOB_DOWNLOAD_FILE_TYPES,
    DOCUMENT_JOB_FILE_TYPE_ORDER,
    UNREAD_RESULT,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileReaderProtocol, DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


class DocumentJobAccess:
    """任务读取授权、有效读投影与任务文件归属判断的共享 owner。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
    ) -> None:
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service

    def get_authorized_job(self, job_id: str, *, user: AuthenticatedUser) -> DocumentJobRecord:
        """按 owner/admin 规则读取 document_job。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApplicationError("not_found", f"文档任务不存在: {job_id}")
        self.ensure_visible(job, user)
        return job

    def effective_job(self, job: DocumentJobRecord, *,
                       file_reader: DocumentFileReaderProtocol | None = None) -> DocumentJobRecord:
        """受权后按最新文件 metadata 投影；raw 写快照始终经 _get_job 取得。"""
        binding = job.current_review_binding
        reader = self.file_repository if file_reader is None else file_reader
        file = (reader.get_document_file(job.result_file_id)
                if job.result_file_id is not None and binding is not None and binding.binding_state == "verified" else None)
        return effective_review_job(job, file, now=utc_now())

    def get_job(self, job_id: str, *, user: AuthenticatedUser) -> DocumentJobRecord:
        """返回有效读投影，GET 不修补存储。"""
        return self.effective_job(self.get_authorized_job(job_id, user=user))

    def review_api_file(self, job, *, conflict_reason="quality_evidence_conflict"):
        file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
        if file is not None and ((file.tenant_id, file.company_id, file.job_id, file.file_type)
                != (job.tenant_id, job.company_id, job.id, "generated_word")):
            raise ApplicationError("conflict", "当前主件归属与任务不一致。", reason_code=conflict_reason)
        return file

    def ensure_file_reader_available(self) -> None:
        if self.file_upload_service is not None:
            return
        raise ApplicationError(
            "service_unavailable",
            "翻译 QA 需要文件读取服务。",
        )

    def get_source_file_for_clone(self, job: DocumentJobRecord) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            raise ApplicationError("conflict", "源任务的 source_pdf 文件不存在，不能重新发起。")
        if source_file.file_type != "source_pdf":
            raise ApplicationError("conflict", "源任务文件不是 source_pdf，不能重新发起。")
        if source_file.status != "uploaded":
            raise ApplicationError("conflict", "源 PDF 尚不可用，不能重新发起。")
        if source_file.tenant_id != job.tenant_id or source_file.company_id != job.company_id:
            raise ApplicationError("forbidden", "源 PDF 与任务租户不匹配。")
        if source_file.expires_at is not None and source_file.expires_at <= utc_now():
            raise ApplicationError("conflict", "源 PDF 已过期，不能重新发起。")
        return source_file

    def get_completed_result_file(self, job: DocumentJobRecord, *,
            observed_result: DocumentFileRecord | None | object = UNREAD_RESULT,
            file_reader: DocumentFileReaderProtocol | None = None) -> DocumentFileRecord:
        self.ensure_job_not_deleted(job, reason_code="job_deleted")
        if job.status != "succeeded" or job.stage != "completed":
            raise ApplicationError("conflict", "文档任务尚未成功完成，生成 Word 不可下载。", reason_code="job_not_completed")
        if job.result_file_id is None:
            raise ApplicationError("conflict", "文档任务尚未成功完成，生成 Word 不可下载。", reason_code="result_file_missing")
        reader = self.file_repository if file_reader is None else file_reader
        file = reader.get_document_file(job.result_file_id) if observed_result is UNREAD_RESULT else observed_result
        if file is None:
            raise ApplicationError("not_found", f"结果文件不存在: {job.result_file_id}", reason_code="result_file_missing")
        if ((file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.file_type != "generated_word"):
            raise ApplicationError("conflict", "结果文件与文档任务不匹配。", reason_code="result_file_mismatch")
        if file.status != "uploaded":
            raise ApplicationError("conflict", "结果文件尚未完成上传。", reason_code="result_file_not_uploaded")
        return file

    def get_downloadable_completed_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        file = self.get_completed_result_file(job)
        self.ensure_file_not_expired(file)
        return file

    def list_files_for_job(self, job: DocumentJobRecord) -> list[DocumentFileRecord]:
        candidates = [
            file
            for file in self.file_repository.list_document_files()
            if file.tenant_id == job.tenant_id
            and file.company_id == job.company_id
            and file.file_type in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES
            and self.file_belongs_to_job(job, file)
        ]
        # 完整预览只观测一次；以刚验证的Record筛选列表快照，避免逐页重读全组。
        preview_files = verified_current_preview_files(job, self.file_repository, self.file_upload_service) if any(
            file.file_type in PREVIEW_FILE_TYPES for file in candidates
        ) else {}
        files = [file for file in candidates if (
            preview_files.get(file.id) == file if file.file_type in PREVIEW_FILE_TYPES
            else self.is_current_downloadable_job_file(job, file)
        )]
        return sorted(
            files,
            key=lambda file: (
                DOCUMENT_JOB_FILE_TYPE_ORDER.get(file.file_type, 100),
                file.created_at,
                file.id,
            ),
        )

    def ensure_file_not_expired(self, file: DocumentFileRecord, *, as_of: datetime | None = None,
                               file_reader: DocumentFileReaderProtocol | None = None) -> None:
        if file.deletion_claim is not None:
            raise ApplicationError("conflict", "文件已预留删除。", reason_code="file_deletion_reserved")
        reader = self.file_repository if file_reader is None else file_reader
        if file.expires_at is not None and file.expires_at <= (as_of if as_of is not None else utc_now()) and not reader.is_document_file_protected(file.id):
            raise ApplicationError("conflict", "文件已过期，不能下载。", reason_code="file_expired")

    def file_belongs_to_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        return file.job_id == job.id or file.id == job.source_file_id

    def is_current_downloadable_job_file(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        if file.file_type in PREVIEW_FILE_TYPES:
            # 单件下载每次独立观测，不能使用先前列表的核验结果。
            return verified_current_preview_files(job, self.file_repository, self.file_upload_service).get(file.id) == file
        if file.file_type == "source_pdf":
            return file.id == job.source_file_id
        if file.file_type == "mineru_raw_result" and file.id == job.mineru_raw_result_file_id:
            return True
        if file.file_type == "document_ir":
            if file.id == job.document_ir_file_id:
                return True
            return job.document_ir_file_id is None and file.id == job.source_document_ir_file_id
        if file.file_type == "generated_word":
            # 协议候选只能通过权威完成指针暴露，receipt 或同代 metadata 均不构成授权。
            if job.prepared_result is not None or file.metadata.get("document_job_result_protocol") == 1:
                return (job.status == "succeeded" and job.stage == "completed"
                        and file.id == job.result_file_id and file.status == "uploaded")
            if file.id == job.result_file_id:
                return job.status == "succeeded" and job.stage == "completed"
        return self.file_matches_current_retry_count(job, file)

    def file_matches_current_retry_count(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        retry_count = self.file_retry_count(file)
        if retry_count is None:
            return job.retry_count == 0
        return retry_count == job.retry_count

    @staticmethod
    def file_retry_count(file: DocumentFileRecord) -> int | None:
        raw_value = (file.metadata or {}).get("retry_count")
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str) and raw_value.isdigit():
            return int(raw_value)
        return None

    def ensure_job_not_deleted(self, job: DocumentJobRecord, *, reason_code: str | None = None) -> None:
        if job.deleted_at is not None:
            raise ApplicationError("conflict", "文档任务已删除。", reason_code=reason_code)

    def ensure_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> None:
        if self.is_visible(job, user):
            return
        raise ApplicationError("forbidden", "无权限访问该文档任务。")

    def is_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> bool:
        if job.tenant_id != user.tenant_id or job.company_id != user.company_id:
            return False
        if user.role == "admin":
            return True
        return job.created_by == user.id

    def normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
