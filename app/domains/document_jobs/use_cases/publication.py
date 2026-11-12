from __future__ import annotations

# app/domains/document_jobs/use_cases/publication.py: 用例：文档发布、发布记录与发布文件下载、新代请求。

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.audit.models import ActorContext, AuditEvent
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.new_generation import (
    NewGenerationCommitUnknownError,
    NewGenerationConflict,
    NewGenerationSubmission,
    new_generation_eligibility_reason,
    new_generation_request_sha256,
)
from app.domains.document_jobs.preview_evidence import is_preview_storage_error
from app.domains.document_jobs.publication import (
    PublicationConflict,
    PublicationExpectedSource,
    PublicationRecord,
    PublicationSubmission,
    observed_publication_source,
    publication_request_sha256,
    validate_publication_history,
)
from app.domains.document_jobs.publication_evidence import (
    prepare_publication_evidence,
    public_publication_record,
)
from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import (
    ReviewExpectedSource,
    digest,
    observed_review_source,
    review_validity,
)
from app.domains.document_jobs.views.jobs import (
    DocumentJobActionDisabledReasonResponse,
    DocumentJobAvailableActionResponse,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import NewGenerationRequestUnavailable, SYSTEM_LOGGER
from app.domains.document_jobs.use_cases.dispatcher import DocumentJobDispatcher
from app.domains.document_jobs.use_cases.download_tokens import (
    PublicationDownloadClaims,
    build_publication_download_token,
    verify_publication_download_token,
)
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.result_registration import file_lifecycle_unavailable, review_source_descriptor
from app.domains.jobs.models import JobRecord
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.resources.models import utc_now
from app.domains.translation.modes import translation_mode_for_document_job_mode
from app.services.auth.models import AuthenticatedUser


@dataclass(frozen=True)
class PublicationDownloadGrant:
    """最终件下载授权结果：presigned_url 与 token 恰有一个非空。"""

    job: DocumentJobRecord
    record: PublicationRecord
    file: DocumentFileRecord
    expires_at: datetime
    presigned_url: str | None
    token: str | None


class DocumentJobPublication:
    """用例：文档发布、发布记录与发布文件下载、新代请求。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        task_queue: DocumentJobTaskQueueProtocol | None,
        job_resource_snapshot_service: Any | None,
        file_upload_service: Any | None,
        audit_service: Any | None,
        events: DocumentJobEventWriter,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
        dispatcher: DocumentJobDispatcher,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.file_upload_service = file_upload_service
        self.audit_service = audit_service
        self.events = events
        self.access = access
        self.read_model = read_model
        self.dispatcher = dispatcher

    def list_document_publications(self, job_id: str, *, user: AuthenticatedUser):
        """同次 metadata 观察提供完整 expected_source，客户端不计算私有 receipt 摘要。"""
        try:
            job = self._publication_job(job_id, user)
            file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
            records = self.job_repository.list_document_job_publications(job.id)
            _, actions, checks = self.read_model.build_job_read_observation(job, user=user, observed_result=file)
            download_actions = {}
            for record in records:
                try:
                    self._verify_publication_result(job, record.id)
                    download_actions[record.id] = self.read_model.available_action(None)
                except ApplicationError as error:
                    reason = DocumentJobActionDisabledReasonResponse(code=error.reason_code, message=error.message)
                    download_actions[record.id] = DocumentJobAvailableActionResponse(enabled=False,
                        disabled_reason=reason.message, disabled_reason_code=reason.code, disabled_reasons=[reason])
            current = self.job_repository.get_document_job(job.id)
            current_file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
            if current != job or current_file != file:
                raise ApplicationError("conflict", "发布来源已变化，请刷新后核对。", reason_code="publication_source_changed")
            return {"job_id": job.id, "expected_source": observed_publication_source(job, file),
                    "items": [public_publication_record(record) for record in records], "available_actions": actions,
                    "preflight_checks": checks, "download_actions": download_actions}
        except ApplicationError:
            raise
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise ApplicationError("service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None

    def request_new_generation(self, job_id: str, *, user: AuthenticatedUser, request_id: str,
        note: str, expected_source: ReviewExpectedSource, trace_id: str,
    ):
        """先按原 UUID 对账；只有新请求才认证原 PDF 和固定资源并原子接纳。"""
        job = self._new_generation_job(job_id, user, request_id=request_id)
        try:
            key = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError):
            raise ApplicationError("validation_error", "request_id 必须是 UUID。") from None
        note = note.strip()
        if not 1 <= len(note) <= 1000:
            raise ApplicationError("validation_error", "新代原因去除首尾空白后必须为 1..1000 字。")
        fingerprint = new_generation_request_sha256(job_id=job.id, actor_id=user.id,
            expected_source=expected_source, note=note)
        try:
            prior = self.job_repository.get_document_job_generation_request(job.id, request_id=key, actor_id=user.id)
            if prior is not None:
                acceptance, current = prior
                if acceptance.submission_sha256 != fingerprint:
                    raise NewGenerationConflict("new_generation_request_conflict")
                return self._new_generation_response(acceptance, current, replayed=True), False
            reason = new_generation_eligibility_reason(job, max_retries=self.settings.p0_document_job_max_retries)
            if reason is not None:
                raise NewGenerationConflict(reason)
            result_file = self.access.review_api_file(job, conflict_reason="new_generation_source_changed")
            if observed_review_source(job, result_file) != expected_source:
                raise NewGenerationConflict("new_generation_source_changed")
            source = self._verify_new_generation_source(job)
            self._verify_new_generation_resources(job)
            acceptance, current, replayed = self.job_repository.accept_document_job_new_generation(job.id,
                submission=NewGenerationSubmission(request_id=key, actor_id=user.id, note=note,
                    expected_source=expected_source, expected_request_snapshot_sha256=digest(job.request_snapshot),
                    source_file=source, audit_id="audit_" + uuid4().hex, trace_id=trace_id),
                max_retries=self.settings.p0_document_job_max_retries)
        except NewGenerationConflict as error:
            raise ApplicationError("conflict", "新代请求条件已变化，请重新读取。", reason_code=error.reason_code) from None
        except NewGenerationCommitUnknownError:
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_acceptance_unknown") from None
        except ApplicationError:
            raise
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_storage_unavailable") from None
        if not replayed and self.task_queue is not None:
            # 失败归属固定在已接纳的原阶段；eager 已推进或完成时 CAS 不得覆盖它。
            try:
                self.task_queue.enqueue(current.id, trace_id=trace_id)
            except Exception as error:
                SYSTEM_LOGGER.error("新代投递结果未知 job_id=%s generation=%s generation_request_id=%s trace_id=%s exception_type=%s",
                    current.id, acceptance.accepted_generation, key, trace_id, type(error).__name__)
                try:
                    self.dispatcher.mark_enqueue_failed(current, "新代 Worker 投递失败，请按原 request_id 对账。", trace_id=trace_id)
                except Exception as failure:
                    SYSTEM_LOGGER.error("新代投递失败收尾未确认 job_id=%s generation_request_id=%s trace_id=%s exception_type=%s",
                        current.id, key, trace_id, type(failure).__name__)
                raise NewGenerationRequestUnavailable(key, reason_code="worker_enqueue_failed",
                    accepted_generation=acceptance.accepted_generation) from None
            try:
                current = self.job_repository.get_document_job(job.id)
            except Exception as error:
                if not is_preview_storage_error(error):
                    raise
                raise NewGenerationRequestUnavailable(key, reason_code="new_generation_storage_unavailable",
                    accepted_generation=acceptance.accepted_generation) from None
        return self._new_generation_response(acceptance, current, replayed=replayed), not replayed

    def get_generation_request(self, job_id: str, *, request_id: str, user: AuthenticatedUser):
        """只读原接纳事实及当前状态；存储失败不能解释为没有该请求。"""
        self._new_generation_job(job_id, user, request_id=request_id)
        try:
            key = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError):
            raise ApplicationError("validation_error", "request_id 必须是 UUID。") from None
        try:
            result = self.job_repository.get_document_job_generation_request(job_id, request_id=key, actor_id=user.id)
        except NewGenerationConflict as error:
            raise ApplicationError("conflict", "该请求不能由当前身份读取。", reason_code=error.reason_code) from None
        except Exception as error:
            if not isinstance(error, NewGenerationCommitUnknownError) and not is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_acceptance_unknown") from None
        if result is None:
            raise ApplicationError("not_found", "没有找到该新代接受记录。", reason_code="new_generation_request_not_found")
        acceptance, current = result
        return self._new_generation_response(acceptance, current, replayed=True)

    def _new_generation_job(self, job_id: str, user: AuthenticatedUser, *, request_id: str) -> DocumentJobRecord:
        if user.role != "admin" or {"admin_token", "jobs_token"}.intersection(user.token_scopes):
            raise ApplicationError("role_forbidden", "新代命令和对账需要内部 Admin 用户 JWT。", reason_code="admin_required")
        try:
            return self.access.get_authorized_job(job_id, user=user)
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(request_id, reason_code="new_generation_acceptance_unknown") from None

    def _new_generation_response(self, acceptance, current, *, replayed):
        try:
            current = self.access.effective_job(current)
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(acceptance.request_id, reason_code="new_generation_storage_unavailable",
                accepted_generation=acceptance.accepted_generation) from None
        return {"accepted": True, "request_id": acceptance.request_id, "job_id": acceptance.job_id,
            "accepted_generation": acceptance.accepted_generation, "accepted_at": acceptance.accepted_at,
            "source": acceptance.expected_source, "audit_id": acceptance.audit_id, "replayed": replayed,
            "current_generation": current.retry_count, "current_job": {field: getattr(current, field) for field in (
                "id", "status", "stage", "progress", "retry_count", "result_file_id", "quality_status", "review_status", "delivery_status")}}

    def _verify_new_generation_source(self, job: DocumentJobRecord) -> DocumentFileRecord:
        """锁外完整读取原 PDF；仓储随后在接受锁内复核冻结 descriptor。"""
        source = self.read_model.new_generation_source_file(job)
        if self.file_upload_service is None:
            raise ApplicationError("service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable")
        try:
            content = self.file_upload_service.read_file_content(source)
        except FileNotFoundError:
            raise ApplicationError("not_found", "源 PDF 实物不存在。", reason_code="new_generation_source_unavailable") from None
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                raise ApplicationError("not_found", "源 PDF 实物不存在。", reason_code="new_generation_source_unavailable") from None
            raise ApplicationError("service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable") from None
        except ApplicationError as error:
            if error.code == "service_unavailable":
                raise ApplicationError("service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable") from None
            raise NewGenerationConflict("new_generation_source_unavailable") from None
        except ValueError:
            raise NewGenerationConflict("new_generation_source_unavailable") from None
        if len(content) != source.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != source.checksum_sha256:
            raise NewGenerationConflict("new_generation_source_changed")
        return source.model_copy(deep=True)

    def _verify_new_generation_resources(self, job: DocumentJobRecord) -> None:
        """只物化原绑定版本；缺快照、实物或翻译绑定时拒绝，不读取当前默认值。"""
        service = self.job_resource_snapshot_service
        if service is None:
            raise ApplicationError("service_unavailable", "绑定资源服务暂不可用。", reason_code="new_generation_resources_unavailable")
        try:
            snapshot = self.read_model.new_generation_resource_snapshot(job)
            resources_job = JobRecord(id=job.id, source_filename=job.request_snapshot["source_file"]["original_filename"],
                status="completed", translation_mode=translation_mode_for_document_job_mode(job.mode), resource_snapshot=snapshot)
            with TemporaryDirectory(prefix="new-generation-resources-") as temporary:
                materialized = service.materialize(resources_job, build_job_paths(Path(temporary), job.id))
                if materialized.template_path is None or materialized.layout_config_path is None:
                    raise ValueError("原模板实物或版式配置缺失。")
                record = service.load_snapshot_record(snapshot.template)
                for name, path in (("docx_sha256", materialized.template_path), ("layout_config_sha256", materialized.layout_config_path)):
                    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                    if record.payload.get(name) is not None and record.payload[name] != actual:
                        raise ValueError("原模板实物完整性核验失败。")
        except (JobResourceSnapshotError, FileNotFoundError, ValueError, KeyError):
            raise ApplicationError("service_unavailable", "原绑定资源快照或实物不可用。", reason_code="new_generation_resources_unavailable") from None

    def _publication_job(self, job_id, user):
        try:
            return self.access.get_authorized_job(job_id, user=user)
        except ApplicationError as error:
            reason = {"forbidden": "publication_access_denied", "role_forbidden": "publication_access_denied",
                      "not_found": "document_job_not_found"}.get(error.code)
            if reason is None:
                raise
            raise ApplicationError(error.code, error.message, reason_code=reason) from None

    def get_publication_file_for_download(self, job_id: str, publication_id: str, *,
        user: AuthenticatedUser, trace_id: str,
    ) -> tuple[DocumentJobRecord, PublicationRecord, DocumentFileRecord]:
        """仅 JWT 可见任务先授权；无权请求不读取发布私有记录或写目标审计。"""
        if {"admin_token", "jobs_token"}.intersection(user.token_scopes):
            raise ApplicationError("forbidden", "最终件下载需要有效用户 JWT。", reason_code="publication_access_denied")
        job = self._publication_job(job_id, user)
        try:
            record, file = self._verify_publication_result(job, publication_id)
            return job, record, file
        except ApplicationError as error:
            self.record_publication_download_audit(job, user=user, trace_id=trace_id,
                reason_code=error.reason_code)
            raise

    def get_publication_file_for_authorized_download(self, job_id: str, publication_id: str, *,
        result_file_id: str, result_sha256: str,
    ) -> tuple[PublicationRecord, DocumentFileRecord]:
        """能力令牌验签后重验发布与实物；不构造 JWT actor 或伪造下载审计。"""
        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApplicationError("not_found", "文档任务不存在。", reason_code="document_job_not_found")
        return self._verify_publication_result(job, publication_id,
            expected_result=(result_file_id, result_sha256))

    def _verify_publication_result(self, job: DocumentJobRecord, publication_id: str, *,
        expected_result: tuple[str, str] | None = None,
    ) -> tuple[PublicationRecord, DocumentFileRecord]:
        """只认证不可变记录选定的主件，不重跑发布时的预览或当前资源检查。"""
        try:
            records = self.job_repository.list_document_job_publications(job.id)
            try:
                validate_publication_history(job, records)
            except ValueError:
                raise ApplicationError("conflict", "发布记录与任务来源不一致。", reason_code="publication_download_source_changed") from None
            record = next((item for item in records if item.id == publication_id), None)
            if record is None:
                raise ApplicationError("not_found", "发布记录不存在。", reason_code="publication_result_unavailable")
            if (job.deleted_at is not None or job.delivery_status != "published" or job.current_publication_id != record.id
                    or job.result_file_id != record.result_file_id or job.retry_count != record.generation):
                raise ApplicationError("conflict", "发布记录与任务来源不一致。", reason_code="publication_download_source_changed")
            if expected_result is not None and expected_result != (record.result_file_id, record.result_sha256):
                raise ApplicationError("forbidden", "最终件下载链接无效。", reason_code="publication_download_token_invalid")
            file = self.file_repository.get_document_file(record.result_file_id)
            archived = next((item for item in record.files if item.id == record.result_file_id), None)
            if file is None:
                raise ApplicationError("not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable")
            if (file.file_type != "generated_word" or (file.tenant_id, file.company_id, file.job_id) !=
                    (record.tenant_id, record.company_id, record.job_id) or archived is None
                    or file.checksum_sha256 != record.result_sha256
                    or review_source_descriptor(file) != review_source_descriptor(archived)
                    or file.review_source_revision != archived.review_source_revision):
                raise ApplicationError("conflict", "发布结果描述与存档不一致。", reason_code="publication_download_source_changed")
            if file_lifecycle_unavailable(file, self.file_repository, now=utc_now()) or not self.file_repository.is_document_file_protected(file.id):
                raise ApplicationError("conflict", "发布结果当前不可读取。", reason_code="publication_result_unavailable")
            try:
                self.file_upload_service.ensure_publication_physical_exclusive((file,))
                content = self.file_upload_service.read_file_content(file)
            except (PublicationConflict, ValueError):
                raise ApplicationError("conflict", "发布结果物理身份不安全。", reason_code="publication_download_source_changed") from None
            if len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != record.result_sha256:
                raise ApplicationError("conflict", "发布结果完整性核验失败。", reason_code="publication_result_integrity_failed")
            self.check_publication_download_current(job, record, file)
            return record, file
        except FileNotFoundError:
            raise ApplicationError("not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable") from None
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                raise ApplicationError("not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable") from None
            raise ApplicationError("service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise ApplicationError("service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None

    def check_publication_download_current(self, job: DocumentJobRecord, record: PublicationRecord,
        file: DocumentFileRecord,
    ) -> None:
        """字节读取和 presign I/O 之后重查同一记录与保留身份；归档不影响读取。"""
        current = self.job_repository.get_document_job(job.id)
        if (current is None or current.current_publication_id != record.id or current.result_file_id != file.id
                or current.retry_count != record.generation or current.delivery_status != "published" or current.deleted_at is not None
                or (current.tenant_id, current.company_id) != (record.tenant_id, record.company_id)
                or self.file_repository.get_document_file(file.id) != file
                or self.job_repository.list_document_job_publications(job.id) != [record]
                or not self.file_repository.is_document_file_protected(file.id)):
            raise ApplicationError("conflict", "发布结果在读取期间发生变化。", reason_code="publication_download_source_changed")

    def record_publication_download_audit(self, job: DocumentJobRecord, *, user: AuthenticatedUser, trace_id: str,
        record: PublicationRecord | None = None, reason_code: str | None = None,
    ) -> None:
        """授权审计成功才允许路由交付 URL；取件端没有 JWT，不调用此方法。"""
        if self.audit_service is None:
            raise ApplicationError("service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable")
        details = ({"publication_id": record.id, "generation": record.generation,
            "result_file_id": record.result_file_id, "result_sha256": record.result_sha256,
            "classification": "final_delivery"} if record is not None else {"reason_code": reason_code})
        try:
            self.audit_service.record(actor=ActorContext(actor_id=user.id, actor_role=user.role, source="jwt"),
                action="document_job.publication_download_authorize" if record is not None else "document_job.publication_download_rejected",
                target_type="document_job", target_id=job.id, trace_id=trace_id, details=details)
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise ApplicationError("service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable") from None

    def authorize_publication_download(self, job_id: str, publication_id: str, *,
        user: AuthenticatedUser, trace_id: str,
    ) -> PublicationDownloadGrant:
        """签发绑定不可变记录的短期最终件入口；审计失败不交付令牌或预签名 URL。

        本地存储返回签名令牌，由路由拼接下载地址；S3 返回预签名 URL。
        """
        job, record, file = self.get_publication_file_for_download(
            job_id, publication_id, user=user, trace_id=trace_id)
        presigned_url = token = None
        try:
            expires_seconds = self.settings.oss_download_presign_expires_seconds
            if expires_seconds <= 0:
                raise ApplicationError("service_unavailable", "最终件下载有效期配置不可用。", reason_code="publication_storage_unavailable")
            expires_at = (utc_now() + timedelta(seconds=expires_seconds)).replace(microsecond=0)
            if file.storage_provider == "s3":
                presigned_url = self.file_upload_service.create_presigned_download_url(file, expires_seconds=expires_seconds)
            else:
                token = build_publication_download_token(self.settings, PublicationDownloadClaims(job_id=job.id,
                    publication_id=record.id, result_file_id=file.id, result_sha256=record.result_sha256,
                    expires_ts=int(expires_at.timestamp())))
            self.check_publication_download_current(job, record, file)
        except ApplicationError as error:
            self.record_publication_download_audit(job, user=user, trace_id=trace_id, reason_code=error.reason_code)
            raise
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            self.record_publication_download_audit(job, user=user, trace_id=trace_id,
                reason_code="publication_storage_unavailable")
            raise ApplicationError("service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
        self.record_publication_download_audit(job, user=user, trace_id=trace_id, record=record)
        if expires_at <= utc_now():
            raise ApplicationError("forbidden", "最终件下载链接已过期，请重新申请。", reason_code="publication_download_token_expired")
        return PublicationDownloadGrant(job=job, record=record, file=file, expires_at=expires_at,
                                        presigned_url=presigned_url, token=token)

    def resolve_publication_download(self, job_id: str, publication_id: str, *, token: str,
    ) -> tuple[DocumentFileRecord, Path]:
        """能力取件：验签后重验记录、descriptor、真实字节，返回本地安全路径；不伪造 JWT 审计。"""
        claims = verify_publication_download_token(self.settings, job_id=job_id, publication_id=publication_id,
                                                   token=token)
        _record, file = self.get_publication_file_for_authorized_download(job_id, publication_id,
            result_file_id=claims.result_file_id, result_sha256=claims.result_sha256)
        if file.storage_provider == "s3":
            raise ApplicationError("conflict", "发布结果存储身份已变化。", reason_code="publication_download_source_changed")
        return file, self.file_upload_service.resolve_file_object_path(file)

    def publish_document(self, job_id: str, *, user: AuthenticatedUser, request_id: str, note: str,
                         expected_source: PublicationExpectedSource, trace_id: str):
        """先授权和幂等查询，再做锁外认证；提交由单一仓储事务拥有。"""
        if user.role != "admin" or "admin_token" in user.token_scopes or "jobs_token" in user.token_scopes:
            raise ApplicationError("role_forbidden", "只有内部 Admin 用户 JWT 可以发布。", reason_code="admin_required")
        job = self._publication_job(job_id, user)
        try:
            key = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError):
            raise ApplicationError("validation_error", "request_id 必须是 UUID。") from None
        note = note.strip()
        if not note or len(note) > 1000:
            raise ApplicationError("validation_error", "发布备注必须为 1..1000 字。")
        fingerprint = publication_request_sha256(job_id=job.id, actor_id=user.id, expected_source=expected_source, note=note)
        try:
            prior = self.job_repository.list_document_job_publications(job.id)
            replay = next((record for record in prior if record.request_id == key), None)
            if replay is not None:
                if replay.submission_sha256 != fingerprint:
                    raise PublicationConflict("publication_request_conflict")
                return self._publication_response(replay, job, user), False
            if prior or job.current_publication_id is not None or job.delivery_status == "published":
                raise PublicationConflict("publication_already_exists")
            if not self.settings.document_publication_enabled:
                raise ApplicationError("service_unavailable", "文档发布写入当前已停用。", reason_code="publication_disabled")
            if job.deleted_at is not None or job.archived_at is not None or job.status != "succeeded" or job.stage != "completed":
                raise PublicationConflict("publication_state_conflict")
            quality = effective_quality_status(job)
            if quality not in {"passed", "warning"}:
                raise PublicationConflict("publication_quality_" + quality)
            file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
            if observed_publication_source(job, file) != expected_source:
                raise PublicationConflict("publication_source_changed")
            if job.review_status != "approved" or review_validity(job, file, now=utc_now()) is not None:
                raise PublicationConflict("publication_review_invalid")
            evidence = prepare_publication_evidence(job, file_repository=self.file_repository,
                file_service=self.file_upload_service, job_repository=self.job_repository)
            publication_id = "publication_" + uuid4().hex
            now = utc_now()
            audit = AuditEvent(audit_id="audit_" + uuid4().hex, actor_id=user.id, actor_role="admin",
                action="document_job.publish", target_type="document_job", target_id=job.id,
                reason=note, details={"publication_id": publication_id, "generation": job.retry_count,
                    "result_file_id": file.id, "result_sha256": file.checksum_sha256}, trace_id=trace_id, created_at=now)
            files = {item.id: item for item in evidence.files}
            record = PublicationRecord(id=publication_id, job_id=job.id, tenant_id=job.tenant_id, company_id=job.company_id,
                generation=job.retry_count, request_id=key, submission_sha256=fingerprint, published_by=user.id,
                published_at=now, note=note, trace_id=trace_id, source_file_id=job.source_file_id,
                source_sha256=files[job.source_file_id].checksum_sha256, result_file_id=file.id,
                result_sha256=file.checksum_sha256, expected_source=expected_source,
                review_record_id=job.current_review_record_id, review_sequence=job.review_sequence, files=evidence.files,
                quality=evidence.quality, preview=evidence.preview, configuration=evidence.configuration,
                protected_file_ids=tuple(sorted(files)), audit=audit)
            accepted, created = self.job_repository.publish_document_job(job.id, submission=PublicationSubmission(
                record=record, expected_job_sha256=digest(job.model_dump(mode="json")), files=evidence.files))
        except PublicationConflict as error:
            self._publication_rejected(job, user, error.reason_code, trace_id)
            raise ApplicationError("conflict", str(error), reason_code=error.reason_code) from None
        except ApplicationError as error:
            self._publication_rejected(job, user, error.reason_code or "publication_state_conflict", trace_id)
            raise
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            self._publication_rejected(job, user, "publication_storage_unavailable", trace_id)
            raise ApplicationError("service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
        current = self.job_repository.get_document_job(job.id)
        if created:
            self.events.record_event(current, event_type="published", stage="completed", level="info", message="文档已发布。",
                payload={"publication_id": accepted.id}, trace_id=trace_id)
        return self._publication_response(accepted, current, user), created

    def _publication_response(self, record, job, user):
        return {"publication": public_publication_record(record), "available_actions": self.read_model.build_available_actions(job, user=user)}

    def _publication_rejected(self, job, user, reason_code, trace_id):
        if self.audit_service is None:
            raise ApplicationError("service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable")
        try:
            self.audit_service.record(actor=ActorContext(actor_id=user.id, actor_role="admin", source="jwt"),
                action="document_job.publish_rejected", target_type="document_job", target_id=job.id,
                trace_id=trace_id, details={"reason_code": reason_code, "generation": job.retry_count})
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise ApplicationError("service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable") from None
