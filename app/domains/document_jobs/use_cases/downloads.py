from __future__ import annotations

# app/domains/document_jobs/use_cases/downloads.py: 用例：结果文件与任务文件下载授权、下载审计事件。

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import preview_download_ttl
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import effective_review_job
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import (
    DOCUMENT_JOB_DOWNLOAD_FILE_TYPES,
    DocumentJobDownloadPolicy,
)
from app.domains.document_jobs.use_cases.download_tokens import build_file_download_token, verify_file_download_token
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


@dataclass(frozen=True)
class FileDownloadGrant:
    """任务文件下载授权结果：presigned_url 与 token 恰有一个非空。"""

    job: DocumentJobRecord
    file: DocumentFileRecord
    policy: DocumentJobDownloadPolicy
    expires_at: datetime
    presigned_url: str | None
    token: str | None


@dataclass(frozen=True)
class FileTokenDownload:
    """令牌取件结果：S3 给出 redirect_url，本地存储给出已确认存在的 local_path。"""

    file: DocumentFileRecord
    redirect_url: str | None
    local_path: Path | None


class DocumentJobDownloads:
    """用例：结果文件与任务文件下载授权、下载审计事件。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
        events: DocumentJobEventWriter,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service
        self.events = events
        self.access = access
        self.read_model = read_model

    def authorize_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        file_id: str | None,
        trace_id: str | None,
    ) -> FileDownloadGrant:
        """签发任务文件短期下载凭据并记录授权事件；预览文件的有效期不超过预览证据剩余寿命。"""

        job, file = self.get_file_for_download(job_id, user=user, file_id=file_id)
        policy = self.read_model.build_download_policy(job, file)
        expires_seconds = self._expires_seconds(job, file)
        expires_at = utc_now() + timedelta(seconds=expires_seconds)
        presigned_url = token = None
        if file.storage_provider == "s3":
            presigned_url = self.file_upload_service.create_presigned_download_url(
                file,
                expires_seconds=expires_seconds,
            )
        else:
            token = build_file_download_token(self.settings, job_id=job.id, file_id=file.id, expires_at=expires_at)
        self.record_download_authorized(
            job,
            file,
            policy=policy,
            expires_at=expires_at.isoformat(),
            trace_id=trace_id,
        )
        return FileDownloadGrant(job=job, file=file, policy=policy, expires_at=expires_at,
                                 presigned_url=presigned_url, token=token)

    def resolve_token_download(self, job_id: str, *, token: str) -> FileTokenDownload:
        """验签后按令牌中的 file_id 重新校验文件合同，再给出取件方式。"""

        file_id = verify_file_download_token(self.settings, job_id=job_id, token=token)
        job, file = self.get_file_for_authorized_download(job_id, file_id=file_id)
        if file.storage_provider == "s3":
            download_url = self.file_upload_service.create_presigned_download_url(
                file,
                expires_seconds=self._expires_seconds(job, file),
            )
            return FileTokenDownload(file=file, redirect_url=download_url, local_path=None)
        path = self.file_upload_service.resolve_file_object_path(file)
        if not path.exists():
            raise ApplicationError("not_found", f"文件不存在: {file.id}")
        return FileTokenDownload(file=file, redirect_url=None, local_path=path)

    def _expires_seconds(self, job: DocumentJobRecord, file: DocumentFileRecord) -> int:
        expires_seconds = self.settings.oss_download_presign_expires_seconds
        if file.file_type.startswith("word_preview_"):
            expires_seconds = preview_download_ttl(
                job, file, self.file_repository, self.file_upload_service, expires_seconds=expires_seconds)
        return expires_seconds

    def get_result_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """校验任务权限和完成状态后返回生成 Word 文件。"""

        job = self.access.get_authorized_job(job_id, user=user)
        file = self.access.get_downloadable_completed_result_file(job)
        return effective_review_job(job, file, now=utc_now()), file

    def get_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        file_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """按可见任务签发文件下载前，校验文件归属、状态、过期和类型。"""

        job = self.access.get_authorized_job(job_id, user=user)
        file = (self.access.get_downloadable_completed_result_file(job) if file_id is None
                else self._get_downloadable_task_file(job, file_id=file_id))
        view = effective_review_job(job, file, now=utc_now()) if file.id == job.result_file_id else self.access.effective_job(job)
        return view, file

    def get_result_file_for_authorized_download(
        self,
        job_id: str,
        *,
        file_id: str,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """临时下载 URL 已验签后使用，不再要求 Bearer token。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApplicationError("not_found", f"文档任务不存在: {job_id}")
        file = self.access.get_downloadable_completed_result_file(job)
        if file.id != file_id:
            raise ApplicationError("forbidden", "下载链接与结果文件不匹配。")
        return job, file

    def get_file_for_authorized_download(
        self,
        job_id: str,
        *,
        file_id: str,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """临时下载 URL 已验签后，按 token 中的 file_id 重新校验文件合同。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApplicationError("not_found", f"文档任务不存在: {job_id}")
        return job, self._get_downloadable_task_file(job, file_id=file_id)

    def record_download_authorized(
        self,
        job: DocumentJobRecord,
        file: DocumentFileRecord,
        *,
        policy: DocumentJobDownloadPolicy,
        expires_at: str,
        trace_id: str | None,
    ) -> None:
        """记录结果下载授权事件，不写入长期 URL。"""

        self.events.record_event(
            job,
            event_type="download_authorized",
            stage=job.stage,
            level="info",
            message="任务文件下载链接已授权。",
            payload={
                "generation": job.retry_count,
                "file_id": file.id,
                "file_type": file.file_type,
                "expires_at": expires_at,
                "classification": policy.classification,
                "warning_code": policy.warning_code,
            },
            trace_id=trace_id,
        )

    def _get_downloadable_task_file(self, job: DocumentJobRecord, *, file_id: str) -> DocumentFileRecord:
        self.access.ensure_job_not_deleted(job, reason_code="job_deleted")
        file = self.file_repository.get_document_file(file_id)
        if file is None:
            raise ApplicationError("not_found", f"文件不存在: {file_id}")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id:
            raise ApplicationError("forbidden", "下载文件与文档任务不匹配。")
        if not self.access.file_belongs_to_job(job, file):
            raise ApplicationError("forbidden", "下载文件与文档任务不匹配。")
        if file.file_type not in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES:
            raise ApplicationError("conflict", "该文件类型不支持从任务详情下载。")
        if not self.access.is_current_downloadable_job_file(job, file):
            raise ApplicationError("conflict", "该文件不属于当前任务重试轮次，不能从任务详情下载。", reason_code="file_not_current")
        if file.status != "uploaded":
            raise ApplicationError("conflict", "文件尚未完成上传，不能下载。", reason_code="result_file_not_uploaded")
        self.access.ensure_file_not_expired(file)
        return file
