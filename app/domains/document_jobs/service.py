from __future__ import annotations

from uuid import UUID
from app.domains.document_jobs.publication import (
    PublicationConflict, PublicationExpectedSource, PublicationRecord, PublicationSubmission,
    observed_publication_source, publication_request_sha256, validate_publication_history,
)
from app.domains.document_jobs.publication_evidence import prepare_publication_evidence, public_publication_record
from app.domains.document_jobs.review import digest, review_validity
from app.domains.audit.models import AuditEvent, ActorContext
from app.domains.document_jobs.preview import _is_preview_storage_error
from app.domains.files.result_registration import file_lifecycle_unavailable

# 文件：app/domains/document_jobs/service.py
# 用途：创建、投递、查询 document_jobs 并记录任务事件。

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, get_args
from urllib.parse import quote
from uuid import uuid4

from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
from fastapi import status

from app.core.config import Settings
from app.domains.document_jobs.preview import PREVIEW_FILE_TYPES, verified_current_preview_files
from app.domains.document_jobs.preview_state import PreviewRetryResult
from app.domains.document_jobs.review import (
    ReviewBinding, ReviewIssueType, ReviewRecord, ReviewStatus, ReviewSubmission, effective_review_job,
    ReviewExpectedSource, ReviewSubmissionConflict, observed_review_source, review_validity, digest,
    receipt_identity, receipt_matches_file,
)
from app.domains.files.result_registration import review_source_descriptor
from app.domains.document_jobs.base_quality import fresh_quality_summary
from app.domains.document_jobs.new_generation import (
    NewGenerationCommitUnknownError, NewGenerationConflict, NewGenerationSubmission,
    new_generation_eligibility_reason, new_generation_request_sha256,
)
from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.document_jobs.list_query import DocumentJobListQuery, DocumentJobListProjectionUnavailable
from app.domains.document_jobs.delivery_state import translation_qa_projection
from app.domains.document_jobs.models import (
    DocumentJobEventLevel,
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobMode,
    DocumentJobRecord,
    DocumentJobStage,
    DocumentJobStatus,
    DocumentJobTranslationBatchRecord,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.schemas import (
    DocumentJobActionDisabledReasonResponse,
    DocumentJobTableReferenceListResponse,
    DocumentJobTableReferenceResponse,
    DocumentJobAvailableActionResponse,
    DocumentJobDownloadClassification,
    DocumentJobTranslationQaAiCallResponse,
    DocumentJobTranslationQaArtifactsResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaSegmentResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaSummaryResponse,
    DocumentJobTranslationQaTermTraceResponse,
)
from app.domains.document_jobs.workflow import (
    ARCHIVABLE_DOCUMENT_JOB_STATUSES,
    CANCELABLE_DOCUMENT_JOB_STATUSES,
    DOCUMENT_JOB_STATUS_GROUPS,
)
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import ConversionOptions, JobRecord, JobResourceSnapshot
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.resources.models import utc_now
from app.domains.translation.modes import (
    TranslationMode,
    document_job_mode_for_translation_mode,
    is_translation_document_job_mode,
    normalize_translation_mode,
    spec_for_document_job_mode,
    translation_mode_for_document_job_mode,
)
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.services.document_ir.models import DocumentIR, TableReferenceProvenance
from app.services.document_ir.table_reference_assets import (
    CHECKSUM_RE, INLINE_MIME_TYPES, RASTER_EXTENSIONS, TABLE_REFERENCE_ROLE,
    DecodedTableReference, decode_table_references,
)
from app.services.renderer.evidence import is_valid_table_rendering_evidence
from app.services.auth.models import AuthenticatedUser


DOCUMENT_JOB_LIST_SORTS = {"created_at_desc", "created_at_asc", "updated_at_desc", "updated_at_asc"}
DOCUMENT_JOB_DOWNLOAD_FILE_TYPES: set[DocumentFileType] = {
    *PREVIEW_FILE_TYPES,
    "source_pdf",
    "mineru_raw_result",
    "document_ir",
    "image_assets_archive",
    "generated_word",
    "ai_call_log",
    "ai_debug_archive",
}
DOCUMENT_JOB_FILE_TYPE_ORDER = {
    "source_pdf": 0,
    "generated_word": 10,
    "mineru_raw_result": 20,
    "document_ir": 30,
    "image_assets_archive": 40,
    "ai_call_log": 50,
    "ai_debug_archive": 60,
}
DOCUMENT_JOB_DELETE_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
DEFAULT_DOCUMENT_JOB_DELETE_REASON = "admin_preview_confirm_delete"
_UNREAD_RESULT = object()
_SYSTEM_LOGGER = logging.getLogger("system")


class NewGenerationRequestUnavailable(ApiError):
    """503 的命令对账上下文；未知结果不携带否定接受声明。"""

    def __init__(self, request_id: str, *, reason_code: str, accepted_generation: int | None = None):
        message = ("新代请求暂不可确认，请保留原 request_id 对账。" if accepted_generation is None
            else "新代已接受，Worker 投递结果未确认，请保留原 request_id 对账。" if reason_code == "worker_enqueue_failed"
            else "新代已接受，当前状态暂不可读取，请保留原 request_id 对账。")
        super().__init__(503, "service_unavailable", message,
            reason_code=reason_code)
        self.generation_request_id = request_id
        self.accepted_generation = accepted_generation


@dataclass(frozen=True)
class _ReviewCommit:
    job: DocumentJobRecord
    accepted_record_id: str
    accepted_sequence: int


@dataclass(frozen=True)
class DocumentJobDownloadPolicy:
    """同次签发和动作投影共用的只读分类，不作为授权凭证持久化。"""

    classification: DocumentJobDownloadClassification | None = None
    warning_code: str | None = None
    warning_message: str | None = None


@dataclass(frozen=True)
class _TableReferenceSnapshot:
    job: DocumentJobRecord
    file: DocumentFileRecord
    document: DocumentIR
    references: list[DecodedTableReference]
    provenance: TableReferenceProvenance | None


@dataclass(frozen=True)
class TableReferenceContent:
    """完成快照与完整性检查后，交给认证 HTTP 响应及审计的安全读取结果。"""

    content: bytes
    mime_type: str
    filename: str
    file_id: str
    ir_file_id: str
    generation: int


@dataclass(frozen=True)
class DocumentJobListResult:
    """列表筛选、统计与行响应共享同次观察的任务和动作。"""

    items: list[tuple[DocumentJobRecord, dict[str, DocumentJobAvailableActionResponse]]]
    total: int
    summary: dict[str, int]
    filtered_summary: dict[str, int]
    translation_qa_summary: dict[str, int]


@dataclass(frozen=True)
class DocumentJobDeletePlanFile:
    """任务删除计划中的单个文件决策，不暴露 object_key 或本地路径。"""

    file_id: str
    file_type: str | None
    storage_provider: str | None
    status_before: str | None
    status_after: str | None
    size_bytes: int | None
    action: str
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: dict[str, Any] | None = None

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "size_bytes": self.size_bytes,
            "action": self.action,
            "outcome": self.outcome,
            "reason": self.reason,
            "deleted": self.deleted,
            "metadata_updated": self.metadata_updated,
            "s3_delete_contract": self.s3_delete_contract,
        }


@dataclass(frozen=True)
class DocumentJobDeletePlan:
    """任务删除预览或执行结果；router 负责转换为 API response model。"""

    job: DocumentJobRecord
    action_mode: str
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int]
    files: list[DocumentJobDeletePlanFile]
    safety: dict[str, bool]


class _DocumentJobSearchable(Protocol):
    id: str
    source_file_id: str
    request_snapshot: dict[str, Any]
    error_code: str | None
    error_message: str | None


class DocumentJobService:
    """P0 document_jobs 应用服务；按配置创建任务后投递 Worker。"""

    def __init__(
        self,
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
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.template_read_service = template_read_service
        self.term_version_service = term_version_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.document_job_translation_batch_repository = document_job_translation_batch_repository
        self.file_upload_service = file_upload_service
        self.word_preview_service = word_preview_service
        self.audit_service = audit_service

    def list_document_publications(self, job_id: str, *, user: AuthenticatedUser):
        """同次 metadata 观察提供完整 expected_source，客户端不计算私有 receipt 摘要。"""
        try:
            job = self._publication_job(job_id, user)
            file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
            records = self.job_repository.list_document_job_publications(job.id)
            _, actions, checks = self._build_job_read_observation(job, user=user, observed_result=file)
            download_actions = {}
            for record in records:
                try:
                    self._verify_publication_result(job, record.id)
                    download_actions[record.id] = self._available_action(None)
                except ApiError as error:
                    reason = DocumentJobActionDisabledReasonResponse(code=error.reason_code, message=error.message)
                    download_actions[record.id] = DocumentJobAvailableActionResponse(enabled=False,
                        disabled_reason=reason.message, disabled_reason_code=reason.code, disabled_reasons=[reason])
            current = self.job_repository.get_document_job(job.id)
            current_file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
            if current != job or current_file != file:
                raise ApiError(409, "conflict", "发布来源已变化，请刷新后核对。", reason_code="publication_source_changed")
            return {"job_id": job.id, "expected_source": observed_publication_source(job, file),
                    "items": [public_publication_record(record) for record in records], "available_actions": actions,
                    "preflight_checks": checks, "download_actions": download_actions}
        except ApiError:
            raise
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise ApiError(503, "service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None

    def request_new_generation(self, job_id: str, *, user: AuthenticatedUser, request_id: str,
        note: str, expected_source: ReviewExpectedSource, trace_id: str,
    ):
        """先按原 UUID 对账；只有新请求才认证原 PDF 和固定资源并原子接纳。"""
        job = self._new_generation_job(job_id, user, request_id=request_id)
        try:
            key = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError):
            raise ApiError(422, "validation_error", "request_id 必须是 UUID。") from None
        note = note.strip()
        if not 1 <= len(note) <= 1000:
            raise ApiError(422, "validation_error", "新代原因去除首尾空白后必须为 1..1000 字。")
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
            result_file = self._review_api_file(job, conflict_reason="new_generation_source_changed")
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
            raise ApiError(409, "conflict", "新代请求条件已变化，请重新读取。", reason_code=error.reason_code) from None
        except NewGenerationCommitUnknownError:
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_acceptance_unknown") from None
        except ApiError:
            raise
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_storage_unavailable") from None
        if not replayed and self.task_queue is not None:
            # 失败归属固定在已接纳的原阶段；eager 已推进或完成时 CAS 不得覆盖它。
            try:
                self.task_queue.enqueue(current.id, trace_id=trace_id)
            except Exception as error:
                _SYSTEM_LOGGER.error("新代投递结果未知 job_id=%s generation=%s generation_request_id=%s trace_id=%s exception_type=%s",
                    current.id, acceptance.accepted_generation, key, trace_id, type(error).__name__)
                try:
                    self._mark_enqueue_failed(current, "新代 Worker 投递失败，请按原 request_id 对账。", trace_id=trace_id)
                except Exception as failure:
                    _SYSTEM_LOGGER.error("新代投递失败收尾未确认 job_id=%s generation_request_id=%s trace_id=%s exception_type=%s",
                        current.id, key, trace_id, type(failure).__name__)
                raise NewGenerationRequestUnavailable(key, reason_code="worker_enqueue_failed",
                    accepted_generation=acceptance.accepted_generation) from None
            try:
                current = self.job_repository.get_document_job(job.id)
            except Exception as error:
                if not _is_preview_storage_error(error):
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
            raise ApiError(422, "validation_error", "request_id 必须是 UUID。") from None
        try:
            result = self.job_repository.get_document_job_generation_request(job_id, request_id=key, actor_id=user.id)
        except NewGenerationConflict as error:
            raise ApiError(409, "conflict", "该请求不能由当前身份读取。", reason_code=error.reason_code) from None
        except Exception as error:
            if not isinstance(error, NewGenerationCommitUnknownError) and not _is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(key, reason_code="new_generation_acceptance_unknown") from None
        if result is None:
            raise ApiError(404, "not_found", "没有找到该新代接受记录。", reason_code="new_generation_request_not_found")
        acceptance, current = result
        return self._new_generation_response(acceptance, current, replayed=True)

    def _new_generation_job(self, job_id: str, user: AuthenticatedUser, *, request_id: str) -> DocumentJobRecord:
        if user.role != "admin" or {"admin_token", "jobs_token"}.intersection(user.token_scopes):
            raise ApiError(403, "role_forbidden", "新代命令和对账需要内部 Admin 用户 JWT。", reason_code="admin_required")
        try:
            return self._get_job(job_id, user=user)
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(request_id, reason_code="new_generation_acceptance_unknown") from None

    def _new_generation_response(self, acceptance, current, *, replayed):
        try:
            current = self._effective_job(current)
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise NewGenerationRequestUnavailable(acceptance.request_id, reason_code="new_generation_storage_unavailable",
                accepted_generation=acceptance.accepted_generation) from None
        return {"accepted": True, "request_id": acceptance.request_id, "job_id": acceptance.job_id,
            "accepted_generation": acceptance.accepted_generation, "accepted_at": acceptance.accepted_at,
            "source": acceptance.expected_source, "audit_id": acceptance.audit_id, "replayed": replayed,
            "current_generation": current.retry_count, "current_job": {field: getattr(current, field) for field in (
                "id", "status", "stage", "progress", "retry_count", "result_file_id", "quality_status", "review_status", "delivery_status")}}

    def _new_generation_source_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        """动作与命令共用同一 metadata 准入，物理认证仍由命令执行。"""
        source = self.file_repository.get_document_file(job.source_file_id)
        if (source is None or source.file_type != "source_pdf" or source.mime_type != "application/pdf"
                or (source.tenant_id, source.company_id) != (job.tenant_id, job.company_id)
                or source.status != "uploaded" or source.deletion_claim is not None or source.size_bytes <= 0 or not source.checksum_sha256
                or source.expires_at is not None and source.expires_at <= utc_now()):
            raise NewGenerationConflict("new_generation_source_unavailable")
        original = job.request_snapshot.get("source_file")
        if not isinstance(original, dict) or any(original.get(field) != getattr(source, field) for field in (
                "id", "object_key", "original_filename", "mime_type", "size_bytes", "checksum_sha256")):
            raise NewGenerationConflict("new_generation_source_changed")
        return source

    def _verify_new_generation_source(self, job: DocumentJobRecord) -> DocumentFileRecord:
        """锁外完整读取原 PDF；仓储随后在接受锁内复核冻结 descriptor。"""
        source = self._new_generation_source_file(job)
        if self.file_upload_service is None:
            raise ApiError(503, "service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable")
        try:
            content = self.file_upload_service.read_file_content(source)
        except FileNotFoundError:
            raise ApiError(404, "not_found", "源 PDF 实物不存在。", reason_code="new_generation_source_unavailable") from None
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                raise ApiError(404, "not_found", "源 PDF 实物不存在。", reason_code="new_generation_source_unavailable") from None
            raise ApiError(503, "service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable") from None
        except ApiError as error:
            if error.status_code == 503:
                raise ApiError(503, "service_unavailable", "源文件存储暂不可用。", reason_code="new_generation_storage_unavailable") from None
            raise NewGenerationConflict("new_generation_source_unavailable") from None
        except ValueError:
            raise NewGenerationConflict("new_generation_source_unavailable") from None
        if len(content) != source.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != source.checksum_sha256:
            raise NewGenerationConflict("new_generation_source_changed")
        return source.model_copy(deep=True)

    @staticmethod
    def _new_generation_resource_snapshot(job: DocumentJobRecord) -> JobResourceSnapshot:
        resources = job.request_snapshot.get("resources")
        if not isinstance(resources, dict):
            raise ValueError("原资源快照缺失。")
        if not is_translation_document_job_mode(job.mode):
            # direct 历史惰性字段不参与认证；只在读取副本忽略，原快照仍完整保留。
            resources = {key: value for key, value in resources.items() if key not in (
                "translation_profile", "translation_term_set", "translation_prompt_id", "translation_prompt_content_hash")}
        snapshot = JobResourceSnapshot.model_validate(resources)
        if (job.request_snapshot.get("mode") != job.mode or job.request_snapshot.get("template_version_id") != job.template_version_id
                or job.request_snapshot.get("translation_mode") != translation_mode_for_document_job_mode(job.mode)
                or job.request_snapshot.get("document_language") != job.document_language
                or snapshot.template is None or snapshot.term_rule_set is None
                or f"{snapshot.template.resource_id}@{snapshot.template.version}" != job.template_version_id):
            raise ValueError("原资源快照不完整或与任务不一致。")
        return snapshot

    def _verify_new_generation_resources(self, job: DocumentJobRecord) -> None:
        """只物化原绑定版本；缺快照、实物或翻译绑定时拒绝，不读取当前默认值。"""
        service = self.job_resource_snapshot_service
        if service is None:
            raise ApiError(503, "service_unavailable", "绑定资源服务暂不可用。", reason_code="new_generation_resources_unavailable")
        try:
            snapshot = self._new_generation_resource_snapshot(job)
            resources_job = JobRecord(id=job.id, source_filename=job.request_snapshot["source_file"]["original_filename"],
                status="completed", translation_mode=translation_mode_for_document_job_mode(job.mode), resource_snapshot=snapshot)
            with TemporaryDirectory(prefix="new-generation-resources-") as temporary:
                materialized = service.materialize(resources_job, build_job_paths(Path(temporary), job.id))
                if materialized.template_path is None or materialized.layout_config_path is None:
                    raise ValueError("原模板实物或版式配置缺失。")
                record = service._load_snapshot_record(snapshot.template)
                for name, path in (("docx_sha256", materialized.template_path), ("layout_config_sha256", materialized.layout_config_path)):
                    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                    if record.payload.get(name) is not None and record.payload[name] != actual:
                        raise ValueError("原模板实物完整性核验失败。")
        except (JobResourceSnapshotError, FileNotFoundError, ValueError, KeyError):
            raise ApiError(503, "service_unavailable", "原绑定资源快照或实物不可用。", reason_code="new_generation_resources_unavailable") from None

    def _publication_job(self, job_id, user):
        try:
            return self._get_job(job_id, user=user)
        except ApiError as error:
            reason = {403: "publication_access_denied", 404: "document_job_not_found"}.get(error.status_code)
            if reason is None:
                raise
            raise ApiError(error.status_code, error.code, error.message, reason_code=reason) from None

    def get_publication_file_for_download(self, job_id: str, publication_id: str, *,
        user: AuthenticatedUser, trace_id: str,
    ) -> tuple[DocumentJobRecord, PublicationRecord, DocumentFileRecord]:
        """仅 JWT 可见任务先授权；无权请求不读取发布私有记录或写目标审计。"""
        if {"admin_token", "jobs_token"}.intersection(user.token_scopes):
            raise ApiError(403, "forbidden", "最终件下载需要有效用户 JWT。", reason_code="publication_access_denied")
        job = self._publication_job(job_id, user)
        try:
            record, file = self._verify_publication_result(job, publication_id)
            return job, record, file
        except ApiError as error:
            self.record_publication_download_audit(job, user=user, trace_id=trace_id,
                reason_code=error.reason_code)
            raise

    def get_publication_file_for_authorized_download(self, job_id: str, publication_id: str, *,
        result_file_id: str, result_sha256: str,
    ) -> tuple[PublicationRecord, DocumentFileRecord]:
        """能力令牌验签后重验发布与实物；不构造 JWT actor 或伪造下载审计。"""
        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApiError(404, "not_found", "文档任务不存在。", reason_code="document_job_not_found")
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
                raise ApiError(409, "conflict", "发布记录与任务来源不一致。", reason_code="publication_download_source_changed") from None
            record = next((item for item in records if item.id == publication_id), None)
            if record is None:
                raise ApiError(404, "not_found", "发布记录不存在。", reason_code="publication_result_unavailable")
            if (job.deleted_at is not None or job.delivery_status != "published" or job.current_publication_id != record.id
                    or job.result_file_id != record.result_file_id or job.retry_count != record.generation):
                raise ApiError(409, "conflict", "发布记录与任务来源不一致。", reason_code="publication_download_source_changed")
            if expected_result is not None and expected_result != (record.result_file_id, record.result_sha256):
                raise ApiError(403, "forbidden", "最终件下载链接无效。", reason_code="publication_download_token_invalid")
            file = self.file_repository.get_document_file(record.result_file_id)
            archived = next((item for item in record.files if item.id == record.result_file_id), None)
            if file is None:
                raise ApiError(404, "not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable")
            if (file.file_type != "generated_word" or (file.tenant_id, file.company_id, file.job_id) !=
                    (record.tenant_id, record.company_id, record.job_id) or archived is None
                    or file.checksum_sha256 != record.result_sha256
                    or review_source_descriptor(file) != review_source_descriptor(archived)
                    or file.review_source_revision != archived.review_source_revision):
                raise ApiError(409, "conflict", "发布结果描述与存档不一致。", reason_code="publication_download_source_changed")
            if file_lifecycle_unavailable(file, self.file_repository, now=utc_now()) or not self.file_repository.is_document_file_protected(file.id):
                raise ApiError(409, "conflict", "发布结果当前不可读取。", reason_code="publication_result_unavailable")
            try:
                self.file_upload_service.ensure_publication_physical_exclusive((file,))
                content = self.file_upload_service.read_file_content(file)
            except (PublicationConflict, ValueError):
                raise ApiError(409, "conflict", "发布结果物理身份不安全。", reason_code="publication_download_source_changed") from None
            if len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != record.result_sha256:
                raise ApiError(409, "conflict", "发布结果完整性核验失败。", reason_code="publication_result_integrity_failed")
            self.check_publication_download_current(job, record, file)
            return record, file
        except FileNotFoundError:
            raise ApiError(404, "not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable") from None
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                raise ApiError(404, "not_found", "发布结果实物不存在。", reason_code="publication_result_unavailable") from None
            raise ApiError(503, "service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise ApiError(503, "service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None

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
            raise ApiError(409, "conflict", "发布结果在读取期间发生变化。", reason_code="publication_download_source_changed")

    def record_publication_download_audit(self, job: DocumentJobRecord, *, user: AuthenticatedUser, trace_id: str,
        record: PublicationRecord | None = None, reason_code: str | None = None,
    ) -> None:
        """授权审计成功才允许路由交付 URL；取件端没有 JWT，不调用此方法。"""
        if self.audit_service is None:
            raise ApiError(503, "service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable")
        details = ({"publication_id": record.id, "generation": record.generation,
            "result_file_id": record.result_file_id, "result_sha256": record.result_sha256,
            "classification": "final_delivery"} if record is not None else {"reason_code": reason_code})
        try:
            self.audit_service.record(actor=ActorContext(actor_id=user.id, actor_role=user.role, source="jwt"),
                action="document_job.publication_download_authorize" if record is not None else "document_job.publication_download_rejected",
                target_type="document_job", target_id=job.id, trace_id=trace_id, details=details)
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise ApiError(503, "service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable") from None

    def publish_document(self, job_id: str, *, user: AuthenticatedUser, request_id: str, note: str,
                         expected_source: PublicationExpectedSource, trace_id: str):
        """先授权和幂等查询，再做锁外认证；提交由单一仓储事务拥有。"""
        if user.role != "admin" or "admin_token" in user.token_scopes or "jobs_token" in user.token_scopes:
            raise ApiError(403, "role_forbidden", "只有内部 Admin 用户 JWT 可以发布。", reason_code="admin_required")
        job = self._publication_job(job_id, user)
        try:
            key = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError):
            raise ApiError(422, "validation_error", "request_id 必须是 UUID。") from None
        note = note.strip()
        if not note or len(note) > 1000:
            raise ApiError(422, "validation_error", "发布备注必须为 1..1000 字。")
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
                raise ApiError(503, "service_unavailable", "文档发布写入当前已停用。", reason_code="publication_disabled")
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
            raise ApiError(409, "conflict", str(error), reason_code=error.reason_code) from None
        except ApiError as error:
            self._publication_rejected(job, user, error.reason_code or "publication_state_conflict", trace_id)
            raise
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            self._publication_rejected(job, user, "publication_storage_unavailable", trace_id)
            raise ApiError(503, "service_unavailable", "发布存储暂不可用。", reason_code="publication_storage_unavailable") from None
        current = self.job_repository.get_document_job(job.id)
        if created:
            self.record_event(current, event_type="published", stage="completed", level="info", message="文档已发布。",
                payload={"publication_id": accepted.id}, trace_id=trace_id)
        return self._publication_response(accepted, current, user), created

    def _publication_response(self, record, job, user):
        return {"publication": public_publication_record(record), "available_actions": self.build_available_actions(job, user=user)}

    def _publication_rejected(self, job, user, reason_code, trace_id):
        if self.audit_service is None:
            raise ApiError(503, "service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable")
        try:
            self.audit_service.record(actor=ActorContext(actor_id=user.id, actor_role="admin", source="jwt"),
                action="document_job.publish_rejected", target_type="document_job", target_id=job.id,
                trace_id=trace_id, details={"reason_code": reason_code, "generation": job.retry_count})
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise ApiError(503, "service_unavailable", "发布审计暂不可用。", reason_code="publication_audit_unavailable") from None

    def create_job(
        self,
        *,
        user: AuthenticatedUser,
        source_file_id: str,
        mode: DocumentJobMode | None,
        translation_mode: TranslationMode | None,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        debug_full_text: bool,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """创建待处理 document_job，并在启用 Worker 后按 job_id 投递。"""

        source_file = self._get_source_file_for_create(source_file_id, user)
        mode = self._resolve_document_job_mode(mode=mode, translation_mode=translation_mode)
        self._ensure_document_language_allowed(mode, document_language)
        self._ensure_debug_full_text_allowed(user, debug_full_text)
        self._ensure_direct_translation_selection_absent(
            mode,
            term_version_id=term_version_id,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=debug_full_text,
        )
        normalized_template_version_id = self._resolve_template_version_id(
            template_version_id,
            allow_draft=user.role == "admin",
        )
        normalized_term_version_id = self._resolve_term_version_id(
            mode,
            self._legacy_translation_term_version_id(mode, term_version_id, translation_term_version),
        )
        debug_full_text_enabled = self._resolve_debug_full_text_enabled(mode, debug_full_text)
        now = utc_now()
        job_id = f"docjob_{uuid4().hex[:12]}"
        request_snapshot = self._build_request_snapshot(
            source_file,
            mode=mode,
            document_language=document_language,
            template_version_id=normalized_template_version_id,
            term_version_id=normalized_term_version_id,
            debug_full_text_enabled=debug_full_text_enabled,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            resource_snapshot=self._build_resource_snapshot(
                job_id=job_id,
                mode=mode,
                document_language=document_language,
                template_version_id=normalized_template_version_id if self._normalize_optional_text(template_version_id) else None,
                term_rule_set_id=term_rule_set_id,
                term_rule_set_version=term_rule_set_version,
                term_rule_department_id=user.department_id,
                translation_term_set_id=translation_term_set_id,
                translation_term_version=translation_term_version,
                translation_profile_id=translation_profile_id,
                translation_profile_version=translation_profile_version,
                allow_draft_template=user.role == "admin",
            ),
        )
        job = DocumentJobRecord(
            id=job_id,
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            created_by=user.id,
            source_file_id=source_file.id,
            mode=mode,
            document_language=document_language,
            status="pending",
            stage="uploaded",
            progress=0,
            quality_summary=fresh_quality_summary(0),
            template_version_id=normalized_template_version_id,
            term_version_id=normalized_term_version_id,
            debug_full_text_enabled=debug_full_text_enabled,
            timeout_at=now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            request_snapshot=request_snapshot,
            created_at=now,
            updated_at=now,
        )
        self.job_repository.create_document_job(job)
        self.file_repository.update_document_file(source_file.id, job_id=job.id, updated_at=now)
        self.record_event(
            job,
            event_type="job_created",
            stage="uploaded",
            level="info",
            message="文档任务已创建，等待投递 Worker。",
            payload={
                "source_file_id": source_file.id,
                "mode": mode,
                "translation_mode": translation_mode_for_document_job_mode(mode),
                "template_version_id": normalized_template_version_id,
                "term_version_id": normalized_term_version_id,
                "term_assets": request_snapshot.get("term_assets"),
                "resources": request_snapshot.get("resources"),
                "debug_full_text_enabled": debug_full_text_enabled,
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return job
        return self._enqueue_created_job(job, trace_id=trace_id)

    def _get_job(self, job_id: str, *, user: AuthenticatedUser) -> DocumentJobRecord:
        """按 owner/admin 规则读取 document_job。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        self._ensure_visible(job, user)
        return job

    def _effective_job(self, job: DocumentJobRecord) -> DocumentJobRecord:
        """受权后按最新文件 metadata 投影；raw 写快照始终经 _get_job 取得。"""
        binding = job.current_review_binding
        file = (self.file_repository.get_document_file(job.result_file_id)
                if job.result_file_id is not None and binding is not None and binding.binding_state == "verified" else None)
        return effective_review_job(job, file, now=utc_now())

    def get_job(self, job_id: str, *, user: AuthenticatedUser) -> DocumentJobRecord:
        """返回有效读投影，GET 不修补存储。"""
        return self._effective_job(self._get_job(job_id, user=user))

    def _review_api_job(self, job_id, user):
        """只在新接口的授权入口附固定原因，不改变旧端点错误。"""
        try:
            return self._get_job(job_id, user=user)
        except ApiError as exc:
            reason = {403: "review_access_denied", 404: "document_job_not_found"}.get(exc.status_code)
            if reason is None:
                raise
            raise ApiError(exc.status_code, exc.code, exc.message, reason_code=reason) from None

    def _review_api_file(self, job, *, conflict_reason="quality_evidence_conflict"):
        file = self.file_repository.get_document_file(job.result_file_id) if job.result_file_id else None
        if file is not None and ((file.tenant_id, file.company_id, file.job_id, file.file_type)
                != (job.tenant_id, job.company_id, job.id, "generated_word")):
            raise ApiError(409, "conflict", "当前主件归属与任务不一致。", reason_code=conflict_reason)
        return file

    @staticmethod
    def _review_read_identity(job, *, preview=False):
        fields = {"tenant_id", "company_id", "created_by", "source_file_id", "retry_count", "document_ir_file_id",
            "result_file_id", "prepared_result", "status", "stage", "quality_status", "quality_summary",
            "review_status", "delivery_status", "current_review_record_id", "current_review_binding", "review_sequence",
            "deleted_at", "archived_at", "template_version_id", "mode", "document_language"}
        if preview:
            fields.update({"word_preview_state", "request_snapshot"})
        return digest(job.model_dump(mode="json", include=fields))

    def _finish_review_read(self, job, file, user, *, preview=False, artifacts=()):
        """全部相关 I/O 后复核同次来源；不重试，也不把读投影写回仓储。"""
        current = self._review_api_job(job.id, user)
        if (self._review_read_identity(current, preview=preview) != self._review_read_identity(job, preview=preview)
                or self._review_api_file(current) != file):
            raise ApiError(409, "conflict", "质量来源已变化，请重新读取。", reason_code="quality_source_changed")
        for artifact in artifacts:
            if (self.file_repository.get_document_file(artifact.id) != artifact
                    or artifact.expires_at is None or file_lifecycle_unavailable(artifact, self.file_repository, now=utc_now())):
                raise ApiError(409, "conflict", "质量产物来源已变化，请重新读取。", reason_code="quality_source_changed")

    def _current_review_record(self, job):
        if job.current_review_record_id is None:
            return None
        records = self.job_repository.list_document_job_reviews(job.id, after_sequence=job.review_sequence - 1, limit=1)
        if (len(records) != 1 or records[0].id != job.current_review_record_id
                or records[0].sequence != job.review_sequence):
            raise ValueError("当前复核指针与正式历史不一致。")
        return records[0]

    @staticmethod
    def _review_cursor(cursor, kind, job_id, limit):
        from app.domains.document_jobs.quality_review_projection import decode_cursor, InvalidReviewCursor
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApiError(422, "validation_error", "分页数量必须为 1 到 100 的整数。")
        try:
            return decode_cursor(cursor, kind=kind, job_id=job_id) if cursor is not None else None
        except InvalidReviewCursor:
            raise ApiError(400, "invalid_request", "分页游标无效。", reason_code="invalid_review_cursor") from None

    @staticmethod
    def _review_cursor_binding(parsed, expected):
        if parsed is not None and any(getattr(parsed, key) != value for key, value in expected.items()):
            raise ApiError(409, "conflict", "质量分页来源已变化，请重新读取。", reason_code="quality_source_changed")

    def get_document_quality(self, job_id, *, user):
        from app.domains.document_jobs.quality_review_projection import project_source, project_quality_summary, project_review
        from app.domains.document_jobs.schemas import DocumentQualityResponse
        job = self._review_api_job(job_id, user)
        file = self._review_api_file(job)
        view, actions = self.build_job_read_view(job, user=user, observed_result=file)
        summary, producers = project_quality_summary(job.quality_summary, generation=job.retry_count)
        review = project_review(self._current_review_record(job), effective_status=view.review_status,
            validity_reason=review_validity(job, file, now=utc_now()))
        response = DocumentQualityResponse(job_id=job.id, source=project_source(job, file),
            states={"execution_status": view.status, "quality_status": view.quality_status,
                "review_status": view.review_status, "delivery_status": view.delivery_status},
            summary=summary, producers=producers, review=review, available_actions=actions)
        self._finish_review_read(job, file, user)
        return response

    def get_document_review(self, job_id, *, user):
        from app.domains.document_jobs.quality_review_projection import project_source, project_review
        from app.domains.document_jobs.schemas import DocumentCurrentReviewResponse
        job = self._review_api_job(job_id, user)
        file = self._review_api_file(job)
        view, actions = self.build_job_read_view(job, user=user, observed_result=file)
        response = DocumentCurrentReviewResponse(job_id=job.id, source=project_source(job, file),
            review=project_review(self._current_review_record(job), effective_status=view.review_status,
                validity_reason=review_validity(job, file, now=utc_now())), available_actions=actions)
        self._finish_review_read(job, file, user)
        return response

    def list_document_review_blocks(self, job_id, *, user, limit=50, cursor=None,
            source_page_index=None, block_type=None, problem="all", severity="all"):
        """授权内容出口由独立 reader 拥有快照和有界投影。"""
        from app.domains.document_jobs.review_content import list_blocks
        return list_blocks(self, job_id, user=user, limit=limit, cursor=cursor,
            source_page_index=source_page_index, block_type=block_type, problem=problem, severity=severity)

    def get_document_review_block(self, job_id, block_id, *, user, snapshot_id, limit=20, cursor=None):
        """只读取当前 IR 中的稳定块，不接受任意文件或对象路径。"""
        from app.domains.document_jobs.review_content import get_block
        return get_block(self, job_id, block_id, user=user, snapshot_id=snapshot_id, limit=limit, cursor=cursor)

    def get_document_review_history(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            HistoryCursor, encode_cursor, paginate_history, project_review_history_item,
        )
        from app.domains.document_jobs.schemas import DocumentReviewHistoryResponse
        job = self._review_api_job(job_id, user)
        parsed = self._review_cursor(cursor, "history", job.id, limit)
        after, through = (parsed.after_sequence, parsed.through_sequence) if parsed else (0, job.review_sequence)
        if not 0 <= after <= through <= job.review_sequence:
            raise ApiError(400, "invalid_request", "复核历史游标窗口无效。", reason_code="invalid_review_cursor")
        records = self.job_repository.list_document_job_reviews(job.id, after_sequence=after, limit=limit + 1)
        items, next_after = paginate_history(records, after_sequence=after, through_sequence=through, limit=limit)
        self._review_api_job(job.id, user)
        return DocumentReviewHistoryResponse(job_id=job.id, through_sequence=through,
            items=[project_review_history_item(record) for record in items], next_cursor=encode_cursor(
                HistoryCursor(job_id=job.id, after_sequence=next_after, through_sequence=through)) if next_after is not None else None)

    def get_document_quality_tables(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            TableCursor, encode_cursor, project_source, project_table_item, project_table_report,
        )
        from app.domains.document_jobs.schemas import DocumentQualityTablesResponse
        job = self._review_api_job(job_id, user)
        parsed = self._review_cursor(cursor, "tables", job.id, limit)
        file = self._review_api_file(job)
        self._review_cursor_binding(parsed, dict(generation=job.retry_count,
            ir_file_id=job.document_ir_file_id, result_file_id=job.result_file_id))
        evidence = self.get_table_evidence(job.id, user=user, generation=job.retry_count,
            ir_file_id=job.document_ir_file_id, result_file_id=job.result_file_id)
        binding = dict(generation=job.retry_count, ir_file_id=job.document_ir_file_id,
            result_file_id=job.result_file_id, report_sha256=evidence.report_sha256)
        self._review_cursor_binding(parsed, binding)
        start = parsed.next_index if parsed else 0
        if start > len(evidence.tables):
            raise ApiError(400, "invalid_request", "表格分页游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentQualityTablesResponse(job_id=job.id, source=project_source(job, file),
            availability=evidence.evidence_status, reason_code=None,
            report=project_table_report(evidence) if evidence.evidence_status == "available" else None,
            items=[project_table_item(table) for table in evidence.tables[start:end]], next_cursor=encode_cursor(
                TableCursor(job_id=job.id, **binding, next_index=end)) if end < len(evidence.tables) else None)
        self._finish_review_read(job, file, user)
        return response

    def _read_api_preview(self, job, *, include_page_quality=False):
        from app.domains.document_jobs.preview import read_current_preview_evidence, _PreviewStorageError, _frozen_page_policy
        from app.domains.document_jobs.preview_state import _confirmed
        from app.services.preview.models import PreviewPolicy
        try:
            if include_page_quality:
                quality_policy = _frozen_page_policy(job)
                if quality_policy is None:
                    return "legacy_unavailable", None
                if not quality_policy.enabled:
                    return "disabled", None
            policy = job.request_snapshot.get("word_preview")
            if policy is None or PreviewPolicy.model_validate(policy).backend == "disabled":
                return "disabled", None
            state = job.word_preview_state
            if state is None or not _confirmed(state.current_run):
                return "not_ready", None
            if self.file_upload_service is None:
                raise _PreviewStorageError()
            evidence = read_current_preview_evidence(job, self.file_repository, self.file_upload_service,
                include_page_quality=include_page_quality)
        except _PreviewStorageError:
            raise ApiError(503, "service_unavailable", "质量产物存储暂不可用。", reason_code="quality_storage_unavailable") from None
        except ValueError:
            raise ApiError(409, "conflict", "预览质量证据无法认证。", reason_code="quality_evidence_conflict") from None
        if not evidence.observation.available or state.current_run.status != "succeeded":
            return "unavailable", evidence
        if include_page_quality and evidence.page_quality_run is None:
            return "not_ready", evidence
        return "available", evidence

    def get_document_preview(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            PreviewCursor, encode_cursor, project_source, project_preview_run, project_preview_page,
        )
        from app.domains.document_jobs.schemas import DocumentPreviewResponse
        job = self._review_api_job(job_id, user)
        parsed = self._review_cursor(cursor, "preview", job.id, limit)
        file = self._review_api_file(job)
        state = job.word_preview_state
        run = state.current_run if state else None
        binding = dict(generation=job.retry_count, result_file_id=job.result_file_id,
            run_id=run.run_id if run else None, revision=state.revision if state else None,
            attempt=run.attempt_count if run else None, manifest_file_id=run.manifest_file_id if run else None)
        self._review_cursor_binding(parsed, binding)
        availability, evidence = self._read_api_preview(job)
        body = evidence.manifest if evidence and availability == "available" else None
        pages = body["pages"] if body else []
        start = parsed.next_index if parsed else 0
        if start > len(pages):
            raise ApiError(400, "invalid_request", "预览分页游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentPreviewResponse(job_id=job.id, source=project_source(job, file),
            status=run.status if run else (availability if availability in {"disabled", "not_ready"} else "unavailable"), availability=availability,
            reason_code="preview_artifact_unavailable" if availability == "unavailable" else None,
            run=project_preview_run(state, run) if run else None, pdf_file_id=body["pdf_file_id"] if body else None,
            page_count=body["page_count"] if body else None, items=[project_preview_page(page) for page in pages[start:end]],
            next_cursor=encode_cursor(PreviewCursor(job_id=job.id, **binding, next_index=end)) if end < len(pages) else None)
        artifacts = evidence.observation.files if evidence and evidence.observation.available else ()
        self._finish_review_read(job, file, user, preview=True, artifacts=artifacts)
        return response

    def get_document_quality_pages(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            PageCursor, encode_cursor, project_source, project_page_report, project_page_item,
        )
        from app.domains.document_jobs.schemas import DocumentQualityPagesResponse
        job = self._review_api_job(job_id, user)
        parsed = self._review_cursor(cursor, "pages", job.id, limit)
        file = self._review_api_file(job)
        state = job.word_preview_state
        run = state.current_run if state else None
        binding = dict(generation=job.retry_count, result_file_id=job.result_file_id,
            run_id=run.run_id if run else None, revision=state.revision if state else None,
            attempt=run.attempt_count if run else None, manifest_file_id=run.manifest_file_id if run else None)
        self._review_cursor_binding(parsed, binding)
        availability, evidence = self._read_api_preview(job, include_page_quality=True)
        report = evidence.page_quality_run if evidence and availability == "available" else None
        binding["run_sha256"] = report["run_sha256"] if report else None
        self._review_cursor_binding(parsed, binding)
        pages = report["pages"] if report else []
        start = parsed.next_index if parsed else 0
        if start > len(pages):
            raise ApiError(400, "invalid_request", "页面质量游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentQualityPagesResponse(job_id=job.id, source=project_source(job, file),
            availability=availability, reason_code="preview_artifact_unavailable" if availability == "unavailable" else None,
            report=project_page_report(report, revision=state.revision, manifest_file_id=run.manifest_file_id) if report else None,
            items=[project_page_item(page) for page in pages[start:end]], next_cursor=encode_cursor(
                PageCursor(job_id=job.id, **binding, next_index=end)) if end < len(pages) else None)
        artifacts = evidence.observation.files if evidence and evidence.observation.available else ()
        self._finish_review_read(job, file, user, preview=True, artifacts=artifacts)
        return response

    def submit_document_review_with_source(self, job_id, *, user, review_status, expected_source,
            issue_type=None, note=None, trace_id=None):
        from app.domains.document_jobs.schemas import DocumentReviewUpdateResponse
        expected = ReviewExpectedSource.model_validate(expected_source)
        committed = self._submit_document_review(self._review_api_job(job_id, user), user=user,
            review_status=review_status, issue_type=issue_type, note=note, trace_id=trace_id, expected_source=expected)
        try:
            current = self.get_document_review(job_id, user=user)
        except ApiError as exc:
            # 正式记录已提交；后置读取故障不能伪装成未接受的前置冲突。
            raise RuntimeError("复核已进入正式提交后的响应读取阶段。") from exc
        return DocumentReviewUpdateResponse(job_id=job_id, accepted_record_id=committed.accepted_record_id,
            accepted_sequence=committed.accepted_sequence, source=current.source,
            review=current.review, available_actions=current.available_actions)

    def get_table_evidence(self, job_id: str, *, user: AuthenticatedUser, generation: int,
                           ir_file_id: str | None, result_file_id: str | None, table_id: str | None = None):
        """供审核复用的受控内部查询；不返回存储记录，也不注册 HTTP 路由。"""
        from app.domains.document_jobs.table_evidence import (
            TableEvidenceView, has_evidence, verify_report, ensure_selected_result_descriptor, recheck_verified_report,
        )
        if not isinstance(user, AuthenticatedUser):
            raise ApiError(401, "unauthorized", "表格证据查询需要认证。")
        from app.services.tables.evidence import TableEvidenceError
        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if (type(generation) is not int or generation != job.retry_count or ir_file_id != job.document_ir_file_id
                or result_file_id != job.result_file_id):
            raise ApiError(409, "conflict", "表格证据所属任务快照已变化，请刷新。", reason_code="quality_source_changed")
        base = dict(job_id=job.id, generation=job.retry_count, ir_file_id=ir_file_id, result_file_id=result_file_id)
        if result_file_id is None:
            return TableEvidenceView(**base, evidence_status="not_ready", summary={"status": "pending"}, tables=[])
        result = self._get_completed_result_file(job)
        try:
            ensure_selected_result_descriptor(job, result)
        except TableEvidenceError:
            raise ApiError(409, "conflict", "当前主件与选定表格证据凭据冲突，请刷新。", reason_code="quality_evidence_conflict") from None
        if not has_evidence(result.metadata):
            return TableEvidenceView(**base, evidence_status="legacy_unavailable", summary={"status": "pending"}, tables=[])
        if self.file_upload_service is None:
            raise ApiError(503, "service_unavailable", "表格证据存储暂不可用。", reason_code="quality_storage_unavailable")
        try:
            verified = verify_report(job, result, file_repository=self.file_repository,
                file_service=self.file_upload_service, job_repository=self.job_repository)
        except FileNotFoundError:
            raise ApiError(404, "not_found", "表格证据文件或内容不存在。", reason_code="quality_artifact_missing") from None
        except TableEvidenceError:
            raise ApiError(409, "conflict", "表格证据绑定或当前快照无效，请刷新。", reason_code="quality_evidence_conflict") from None
        except RuntimeError:
            raise ApiError(503, "service_unavailable", "表格证据存储暂不可用。", reason_code="quality_storage_unavailable") from None
        current = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(current)
        if (current.retry_count, current.document_ir_file_id, current.result_file_id) != (generation, ir_file_id, result_file_id):
            raise ApiError(409, "conflict", "表格证据所属任务快照已变化，请刷新。", reason_code="quality_source_changed")
        try:
            recheck_verified_report(verified, file_repository=self.file_repository, job_repository=self.job_repository)
        except TableEvidenceError:
            raise ApiError(409, "conflict", "表格证据绑定或当前快照无效，请刷新。", reason_code="quality_evidence_conflict") from None
        envelope, summary = verified.envelope, verified.summary
        tables = envelope.report.tables
        if table_id is not None:
            tables = [table for table in tables if table.table_id == table_id]
            if not tables:
                raise ApiError(404, "not_found", "当前报告未引用该表格。")
        return TableEvidenceView(**base, evidence_status="available", report_file_id=summary["report_file_id"],
            report_sha256=envelope.report.report_sha256, summary=summary,
            tables=[table.model_dump(mode="json", warnings=False) for table in tables])

    def list_table_references(
        self, job_id: str, *, user: AuthenticatedUser, block_id: str | None = None,
    ) -> DocumentJobTableReferenceListResponse:
        """从当前选中 IR 读取审核导航；列表不探测每张远端图片的实际字节。"""
        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        ir_file_id = job.document_ir_file_id or job.source_document_ir_file_id
        if ir_file_id is None:
            return DocumentJobTableReferenceListResponse(job_id=job.id, generation=job.retry_count,
                                                        ir_file_id=None, evidence_status="not_ready")
        snapshot = self._load_table_reference_snapshot(job)
        return self._list_table_references_snapshot(snapshot, user=user, block_id=block_id)

    def _list_table_references_snapshot(
        self, snapshot: _TableReferenceSnapshot, *, user: AuthenticatedUser, block_id: str | None = None,
    ) -> DocumentJobTableReferenceListResponse:
        """只投影已认证观察；新内容 reader 可复用原 IR，免于重复读取字节。"""
        job, ir_file_id = snapshot.job, snapshot.file.id
        items: list[DocumentJobTableReferenceResponse] = []
        for reference in snapshot.references:
            if block_id is not None and reference.block_id != block_id:
                continue
            asset = reference.asset
            file = self._get_table_reference_file(snapshot, reference) if asset is not None else None
            availability = self._table_reference_availability(file) if asset is not None else "source_" + reference.detail.source_status
            content_path = None
            if availability == "available":
                content_path = (f"/api/v1/document-jobs/{quote(job.id, safe='')}/table-references/"
                                f"{quote(asset.id, safe='')}/content?generation={job.retry_count}&ir_file_id={quote(ir_file_id, safe='')}")
            items.append(DocumentJobTableReferenceResponse(
                block_id=reference.block_id, fragment_id=reference.fragment.fragment_id,
                logical_group_id=reference.logical_group_id, page_index=reference.fragment.source_span.page_index,
                bbox=reference.fragment.source_span.bbox, asset_id=asset.id if asset else None,
                file_id=asset.file_id if asset else None, source_status=reference.detail.source_status,
                availability=availability, mime_type=asset.mime_type if asset else None,
                checksum_sha256=asset.checksum_sha256 if asset else None, size_bytes=file.size_bytes if file else None,
                warning_codes=(["missing_table_reference"] if reference.detail.source_status == "missing" else
                               ["invalid_table_reference"] if reference.detail.source_status == "invalid" else []),
                display_supported=asset is not None and asset.mime_type in INLINE_MIME_TYPES, content_path=content_path,
            ))
        self._recheck_table_reference_snapshot(snapshot, user=user)
        return DocumentJobTableReferenceListResponse(
            job_id=job.id, generation=job.retry_count, ir_file_id=ir_file_id,
            evidence_status="registered" if snapshot.document.metadata.table_references_version else "legacy_unavailable",
            items=items,
        )

    def read_table_reference_content(
        self, job_id: str, asset_id: str, *, user: AuthenticatedUser,
        generation: int, ir_file_id: str, disposition: str,
    ) -> TableReferenceContent:
        """每次重新鉴权并核验 IR/图像实际字节，慢读后再次确认当前快照。"""
        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if generation != job.retry_count or ir_file_id != (job.document_ir_file_id or job.source_document_ir_file_id):
            raise ApiError(409, "conflict", "表格参考图所属任务快照已变化，请刷新列表。")
        snapshot = self._load_table_reference_snapshot(job)
        reference = next((item for item in snapshot.references if item.asset is not None and item.asset.id == asset_id), None)
        if reference is None:
            raise ApiError(404, "not_found", "当前文档未引用该表格参考图。")
        file = self._get_table_reference_file(snapshot, reference)
        availability = self._table_reference_availability(file)
        if availability == "missing":
            raise ApiError(404, "not_found", "表格参考图文件不存在。")
        if availability != "available":
            raise ApiError(409, "conflict", "表格参考图当前不可用。")
        if disposition == "inline" and file.mime_type not in INLINE_MIME_TYPES:
            raise ApiError(409, "conflict", "该栅格格式请使用附件下载。")
        content = self._read_table_reference_bytes(file)
        self._check_table_reference_bytes(file, content)
        self._recheck_table_reference_snapshot(snapshot, user=user)
        if self.file_repository.get_document_file(file.id) != file:
            raise ApiError(409, "conflict", "表格参考图文件状态已变化，请刷新列表。")
        self._ensure_file_not_expired(file)
        return TableReferenceContent(content, file.mime_type,
                                     f"table_reference_{asset_id.split(':')[-1]}.{RASTER_EXTENSIONS[file.mime_type]}",
                                     file.id, snapshot.file.id, generation)

    def _load_table_reference_snapshot(self, job: DocumentJobRecord) -> _TableReferenceSnapshot:
        ir_id = job.document_ir_file_id or job.source_document_ir_file_id
        file = self.file_repository.get_document_file(ir_id) if ir_id else None
        if file is None:
            raise ApiError(404, "not_found", "当前文档 IR 文件不存在。")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id or file.job_id != job.id:
            raise ApiError(403, "forbidden", "当前文档 IR 与任务归属不匹配。")
        if file.file_type != "document_ir" or file.status != "uploaded" or file.mime_type != "application/json":
            raise ApiError(409, "conflict", "当前文档 IR 文件不可用。")
        self._ensure_file_not_expired(file)
        content = self._read_table_reference_bytes(file)
        self._check_table_reference_bytes(file, content)
        try:
            document = DocumentIR.model_validate_json(content)
        except (ValueError, TypeError, KeyError) as error:
            raise ApiError(409, "conflict", "当前文档的表格参考资产合同无效。") from error
        return self._table_reference_snapshot(job, file, document)

    def _table_reference_snapshot(
        self, job: DocumentJobRecord, file: DocumentFileRecord, document: DocumentIR,
    ) -> _TableReferenceSnapshot:
        """沿原引用 owner 校验已认证 IR 的绑定及转换来源，不执行额外对象读取。"""
        try:
            references = decode_table_references(document, require_bound=True)
            provenance = (TableReferenceProvenance.model_validate(document.metadata.mineru_validation_input)
                          if document.metadata.table_references_version else None)
        except (ValueError, TypeError, KeyError) as error:
            raise ApiError(409, "conflict", "当前文档的表格参考资产合同无效。") from error
        if document.metadata.job_id != job.id or document.metadata.source_file_id != job.source_file_id:
            raise ApiError(409, "conflict", "当前文档来源与任务不匹配。")
        if provenance is not None:
            file_retry = file.metadata.get("retry_count")
            if (type(file_retry) is not int or not provenance.retry_count <= file_retry <= job.retry_count or
                    file.metadata.get("source_file_id") != job.source_file_id or
                    file.metadata.get("mineru_validation_input") != provenance.model_dump() or
                    document.metadata.mineru_validation is None or
                    document.metadata.mineru_validation.package_sha256 != provenance.mineru_raw_result_sha256.removeprefix("sha256:")):
                raise ApiError(409, "conflict", "当前文档的转换来源校验不一致。")
        return _TableReferenceSnapshot(job, file, document, references, provenance)

    def _get_table_reference_file(
        self, snapshot: _TableReferenceSnapshot, reference: DecodedTableReference,
    ) -> DocumentFileRecord | None:
        asset, provenance, job = reference.asset, snapshot.provenance, snapshot.job
        file = self.file_repository.get_document_file(asset.file_id)
        if file is None:
            return None
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id or file.job_id != job.id:
            raise ApiError(403, "forbidden", "表格参考图与任务归属不匹配。")
        expected = {"asset_role": TABLE_REFERENCE_ROLE, "asset_id": asset.id, "block_id": reference.block_id,
                    "fragment_id": reference.fragment.fragment_id, "logical_group_id": reference.logical_group_id,
                    "source_file_id": job.source_file_id, "source_path": asset.source_path,
                    "mineru_raw_result_file_id": provenance.mineru_raw_result_file_id, "retry_count": provenance.retry_count}
        if (file.file_type != "image_asset" or file.mime_type != asset.mime_type or
                file.checksum_sha256 != asset.checksum_sha256 or file.size_bytes <= 0 or
                type(file.metadata.get("retry_count")) is not int or
                any(file.metadata.get(key) != value for key, value in expected.items())):
            raise ApiError(409, "conflict", "表格参考图的角色、来源或完整性校验不一致。")
        return file

    @staticmethod
    def _table_reference_availability(file: DocumentFileRecord | None) -> str:
        if file is None:
            return "missing"
        if file.status == "deleted":
            return "deleted"
        if file.status == "expired" or file.expires_at is not None and file.expires_at <= utc_now():
            return "expired"
        return "available" if file.status == "uploaded" else "not_uploaded"

    def _read_table_reference_bytes(self, file: DocumentFileRecord) -> bytes:
        if self.file_upload_service is None:
            raise ApiError(503, "service_unavailable", "表格参考资产存储当前不可用。")
        try:
            return self.file_upload_service.read_file_content(file)
        except FileNotFoundError as error:
            raise ApiError(404, "not_found", "表格参考资产内容不存在。") from error
        except Exception as error:
            # S3 错误只读取受控 code，不能把 bucket、key 或原始异常返回客户端。
            response = getattr(error, "response", None)
            details = response.get("Error") if isinstance(response, dict) else None
            if isinstance(details, dict) and details.get("Code") in {"NoSuchKey", "404", "NotFound"}:
                raise ApiError(404, "not_found", "表格参考资产内容不存在。") from error
            raise ApiError(503, "service_unavailable", "表格参考资产存储当前不可用。") from error

    @staticmethod
    def _check_table_reference_bytes(file: DocumentFileRecord, content: bytes) -> None:
        if (not isinstance(file.checksum_sha256, str) or CHECKSUM_RE.fullmatch(file.checksum_sha256) is None or
                len(content) != file.size_bytes or "sha256:" + hashlib.sha256(content).hexdigest() != file.checksum_sha256):
            raise ApiError(409, "conflict", "表格参考资产内容校验不一致。")

    def _recheck_table_reference_snapshot(self, snapshot: _TableReferenceSnapshot, *, user: AuthenticatedUser) -> None:
        current = self.get_job(snapshot.job.id, user=user)
        self._ensure_job_not_deleted(current)
        if (current.retry_count != snapshot.job.retry_count or
                (current.document_ir_file_id or current.source_document_ir_file_id) != snapshot.file.id or
                self.file_repository.get_document_file(snapshot.file.id) != snapshot.file):
            raise ApiError(409, "conflict", "表格参考图所属任务快照已变化，请刷新列表。")
        self._ensure_file_not_expired(snapshot.file)

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
        normalized_q = self._normalize_optional_text(q)
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
            items = [self.build_job_read_view(job, user=user,
                observed_result=result.observed_results[job.id], as_of=query.as_of) for job in result.items]
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

        self.get_job(job_id, user=user)
        return self.event_repository.list_document_job_events(job_id)

    def list_translation_batches(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> list[DocumentJobTranslationBatchRecord]:
        """只读返回任务当前 retry_count generation 的翻译 provider 批次诊断。"""

        job = self.get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            return []
        if self.document_job_translation_batch_repository is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次诊断仓储未配置。")
        return self.document_job_translation_batch_repository.list_translation_batches(
            job.id,
            generation=job.retry_count,
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
        job = self.get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            return job, []
        if self.document_job_translation_batch_repository is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次诊断仓储未配置。")
        snapshot_job, batches = self.document_job_translation_batch_repository.get_translation_batch_snapshot(
            job.id,
        )
        if not self._is_visible(snapshot_job, user):
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "文档任务不存在。")
        # 当前三类 adapter 的 generation=None 快照会带回历史记录；按同一锁快照返回的
        # job.retry_count 过滤，避免历史批次进入当前代 API 投影。
        return self._effective_job(snapshot_job), [batch for batch in batches if batch.generation == snapshot_job.retry_count]

    def list_visible_jobs(
        self,
        *,
        user: AuthenticatedUser,
        include_archived: bool = False,
    ) -> list[DocumentJobRecord]:
        """按可见性取得有效读投影，供异常队列使用。"""

        return [
            self._effective_job(job)
            for job in self.job_repository.list_document_jobs()
            if self._is_visible(job, user)
            and job.deleted_at is None
            and (include_archived or job.archived_at is None)
        ]

    def document_job_search_values(self, job: _DocumentJobSearchable) -> list[str]:
        """Return the shared document_job search fields used by queue projections."""

        return self._document_job_search_values(job)

    def list_files(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentFileRecord]:
        """先按任务权限校验，再返回任务上下文内可展示的文件元数据。"""

        job = self.get_job(job_id, user=user)
        return self._list_files_for_job(job)

    def build_available_actions(
        self, job: DocumentJobRecord, *, user: AuthenticatedUser,
    ) -> dict[str, DocumentJobAvailableActionResponse]:
        """保留已有动作入口；字段与动作组合响应使用同次 read view。"""
        return self.build_job_read_view(job, user=user)[1]

    def build_job_read_view(
        self,
        job: DocumentJobRecord,
        *,
        user: AuthenticatedUser,
        observed_result: DocumentFileRecord | None | object = _UNREAD_RESULT,
        as_of: datetime | None = None,
    ) -> tuple[DocumentJobRecord, dict[str, DocumentJobAvailableActionResponse]]:
        """保留公共二元组合同，内部观察同时拥有发布检查。"""
        view, actions, _ = self._build_job_read_observation(job, user=user, observed_result=observed_result, as_of=as_of)
        return view, actions

    def _build_job_read_observation(
        self, job: DocumentJobRecord, *, user: AuthenticatedUser,
        observed_result: DocumentFileRecord | None | object = _UNREAD_RESULT,
        as_of: datetime | None = None,
    ):
        """同次来源和唯一深度检查同时产出状态、动作及前置检查。"""


        job, download = self._build_result_read_view(job, observed_result=observed_result, as_of=as_of)
        retry_disabled_reason = self._retry_disabled_reason(job)
        publish, checks = self._build_publish_action(job, user=user, download=download)
        actions = {
            "download": download,
            "retry": self._available_action(retry_disabled_reason, retryable=retry_disabled_reason is None),
            "cancel": self._available_action(self._cancel_disabled_reason(job)),
            "archive": self._available_action(self._archive_disabled_reason(job)),
            "unarchive": self._available_action(self._unarchive_disabled_reason(job)),
            "clone": self._available_action(self._clone_disabled_reason(job, user=user)),
            "delete": self._available_action(self._delete_disabled_reason(job, user=user)),
            "publish": publish,
            "new_generation": self._build_new_generation_action(job, user=user),
        }
        if actions["publish"].enabled and job.delivery_status != "published":
            job = job.model_copy(update={"delivery_status": "ready_to_publish"})
        return job, actions, checks

    def _build_new_generation_action(self, job: DocumentJobRecord, *, user: AuthenticatedUser):
        """后端给出可执行资格；POST 仍独立认证实物并在接受锁内重核。"""
        reason = ("admin_required" if user.role != "admin" or {"admin_token", "jobs_token"}.intersection(user.token_scopes)
            else new_generation_eligibility_reason(job, max_retries=self.settings.p0_document_job_max_retries))
        if reason is None:
            try:
                self._new_generation_resource_snapshot(job)
            except ValueError:
                reason = "new_generation_resources_unavailable"
            if self.job_resource_snapshot_service is None:
                reason = "new_generation_resources_unavailable"
        if reason is None:
            try:
                self._new_generation_source_file(job)
            except NewGenerationConflict as error:
                reason = error.reason_code
        messages = {"admin_required": "只有内部 Admin 用户 JWT 可以开始新代。",
            "new_generation_state_invalid": "只有未发布、未归档删除的成功任务可以开始新代。",
            "new_generation_budget_exhausted": "任务的共享重试预算已用尽。",
            "new_generation_resources_unavailable": "原绑定资源快照不可用。",
            "new_generation_source_unavailable": "原源 PDF 当前不可用。",
            "new_generation_source_changed": "原源 PDF 的登记来源已变化。",
            "publication_immutable": "已发布任务不可原地开始新代。"}
        message = messages.get(reason, "任务当前不允许开始新代。") if reason else None
        return DocumentJobAvailableActionResponse(enabled=reason is None, disabled_reason=message,
            disabled_reason_code=reason, disabled_reasons=[DocumentJobActionDisabledReasonResponse(code=reason, message=message)] if reason else [])

    def build_download_policy(
        self, job: DocumentJobRecord, file: DocumentFileRecord,
    ) -> DocumentJobDownloadPolicy:
        """签发已校验当前 file，以同一 metadata 观察决定有效复核及警告。"""
        if file.file_type != "generated_word" or file.id != job.result_file_id:
            return DocumentJobDownloadPolicy()
        view = effective_review_job(job, file, now=utc_now())
        return self._download_policy_for_view(view, file)

    def _download_policy_for_view(
        self,
        job: DocumentJobRecord,
        file: DocumentFileRecord,
    ) -> DocumentJobDownloadPolicy:
        """为已通过下载校验的文件生成分类；普通 Artifact 不冒充当前主件。"""

        if file.file_type != "generated_word" or file.id != job.result_file_id:
            return DocumentJobDownloadPolicy()
        if job.quality_status == "blocked":
            warning = ("quality_blocked_not_deliverable", "该文档存在严重质量问题，仅供内部排查，不可交付或发布。")
        elif job.review_status == "blocked":
            warning = ("review_blocked_not_deliverable", "该文档复核已阻断，仅供内部排查，不可交付或发布。")
        elif job.review_status == "needs_fix":
            warning = ("review_needs_fix_not_deliverable", "该文档复核要求修正，仅供内部使用，不可交付或发布。")
        elif job.review_status == "unreviewed":
            warning = ("document_unreviewed_not_deliverable", "该文档尚未复核，仅供内部使用，不可交付或发布。")
        elif job.quality_status == "pending":
            warning = ("quality_pending_not_deliverable", "该文档尚无质量结论，仅供内部使用，不可交付或发布。")
        else:
            return DocumentJobDownloadPolicy(classification="internal_only")
        return DocumentJobDownloadPolicy(
            classification="internal_only", warning_code=warning[0], warning_message=warning[1],
        )

    def get_translation_qa(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        limit: int,
    ) -> DocumentJobTranslationQaResponse:
        """读取翻译 QA 证据摘要；只消费已有 artifact，不触发任何任务执行。"""

        job = self.get_job(job_id, user=user)
        qa = self._build_translation_qa_state(job)
        if not is_translation_document_job_mode(job.mode):
            return self._build_unavailable_translation_qa(job, qa, reason="unsupported_mode")
        self._ensure_file_reader_available()

        files = self._list_files_for_job(job)
        ai_log_files = self._uploaded_files_by_type(files, "ai_call_log")
        debug_archive_files = self._uploaded_files_by_type(files, "ai_debug_archive")
        ai_calls, term_traces = self._read_ai_call_log_summaries(ai_log_files)
        source_texts, ai_translation_texts, source_reason = self._read_debug_archive_texts(debug_archive_files)
        document_ir_file = self._select_document_ir_file(job, files)
        artifacts = self._build_translation_qa_artifacts(
            document_ir_file=document_ir_file,
            ai_log_files=ai_log_files,
            debug_archive_files=debug_archive_files,
        )
        if document_ir_file is None:
            return self._build_unavailable_translation_qa(
                job,
                qa,
                reason="document_ir_missing",
                artifacts=artifacts,
                ai_calls=ai_calls,
                term_traces=term_traces,
                source_reason=source_reason,
            )

        document_ir = self._read_document_ir(document_ir_file)
        if document_ir is None:
            return self._build_unavailable_translation_qa(
                job,
                qa,
                reason="document_ir_unreadable",
                artifacts=artifacts,
                ai_calls=ai_calls,
                term_traces=term_traces,
                source_reason=source_reason,
            )

        all_segments = self._build_translation_qa_segments(
            document_ir,
            source_texts=source_texts,
            ai_translation_texts=ai_translation_texts,
        )
        returned_segments = all_segments[:limit]
        summary = DocumentJobTranslationQaSummaryResponse(
            final_segment_count=len(all_segments),
            returned_segment_count=len(returned_segments),
            quality_flags=document_ir.quality_flags,
            ai_call_count=len(ai_calls),
            ai_call_statuses=dict(Counter(call.status or "unknown" for call in ai_calls)),
            term_trace_count=len(term_traces),
            debug_full_text_enabled=job.debug_full_text_enabled,
            source_comparison_available=source_reason is None,
            source_comparison_reason=source_reason,
        )
        return DocumentJobTranslationQaResponse(
            job_id=job.id,
            available=True,
            availability_reason=None,
            qa=qa,
            artifacts=artifacts,
            summary=summary,
            segments=returned_segments,
            term_traces=term_traces,
            ai_calls=ai_calls,
        )

    def update_translation_qa(
        self, job_id: str, *, user: AuthenticatedUser, qa_status: DocumentJobTranslationQaStatus,
        issue_type: DocumentJobTranslationQaIssueType | None, note: str | None, trace_id: str | None,
    ) -> DocumentJobRecord:
        """旧翻译入口保留模式及六值边界，正式写入交由统一复核端口。"""
        job = self._get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "翻译 QA 仅支持翻译任务。")
        return self._submit_document_review(job, user=user, review_status=qa_status,
                                            issue_type=issue_type, note=note, trace_id=trace_id).job

    def submit_document_review(
        self, job_id: str, *, user: AuthenticatedUser, review_status: ReviewStatus,
        issue_type: ReviewIssueType | None = None, note: str | None = None, trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """两模式共用的受权内部入口；不读取翻译诊断或触发生产者。"""
        return self._submit_document_review(self._get_job(job_id, user=user), user=user,
            review_status=review_status, issue_type=issue_type, note=note, trace_id=trace_id).job

    def list_document_reviews(
        self, job_id: str, *, user: AuthenticatedUser, after_sequence: int = 0, limit: int = 100,
    ) -> list[ReviewRecord]:
        """先鉴权任务，再按 job 和有界序号读取历史；不提供裸记录 ID 查询。"""
        job = self._get_job(job_id, user=user)
        return self.job_repository.list_document_job_reviews(job.id, after_sequence=after_sequence, limit=limit)

    def _submit_document_review(
        self, job: DocumentJobRecord, *, user: AuthenticatedUser, review_status: ReviewStatus,
        issue_type: ReviewIssueType | None, note: str | None, trace_id: str | None,
        expected_source: ReviewExpectedSource | None = None,
    ) -> _ReviewCommit:
        def conflict(message, reason):
            return ApiError(409, "conflict", message,
                reason_code=reason if expected_source is not None else None)

        if job.deleted_at is not None or job.delivery_status == "published":
            raise conflict("已删除或已发布任务不能修改复核。", "review_state_conflict")
        result_file, actual_hash = None, None
        if expected_source is not None:
            result_file = self._review_api_file(job, conflict_reason="review_result_integrity_conflict")
            if observed_review_source(job, result_file) != expected_source:
                raise conflict("复核来源已变化，请重新读取。", "review_source_changed")
        if review_status == "approved":
            if effective_quality_status(job) == "blocked":
                raise conflict("质量阻断的任务不能批准复核。", "review_quality_blocked")
            try:
                if expected_source is None:
                    result_file = self._get_downloadable_completed_result_file(job)
                else:
                    result_file = self._get_completed_result_file(job, observed_result=result_file)
                    self._ensure_file_not_expired(result_file)
            except ApiError as exc:
                if expected_source is not None:
                    reason = ("review_result_integrity_conflict" if exc.reason_code == "result_file_mismatch"
                        else "review_result_unavailable")
                    raise conflict("当前主 DOCX 不可用，不能批准复核。", reason) from None
                if exc.status_code != status.HTTP_404_NOT_FOUND or exc.code != "not_found":
                    raise
                raise ApiError(status.HTTP_409_CONFLICT, "conflict", "当前主 DOCX 未登记，不能批准复核。") from exc
            if "table_rendering" in result_file.metadata:
                rendering = result_file.metadata["table_rendering"]
                if (
                    self._file_retry_count(result_file) != job.retry_count
                    or not is_valid_table_rendering_evidence(rendering)
                    or rendering.get("quality_status") not in ("passed", "warning")
                    or rendering["blocking_quality_flags"]
                ):
                    reason = ("review_result_integrity_conflict" if self._file_retry_count(result_file) != job.retry_count
                        or not is_valid_table_rendering_evidence(rendering) else "review_quality_blocked")
                    raise conflict("表格质量受阻或渲染证据无效，不能批准。", reason)
            if expected_source is not None and self.file_upload_service is None:
                raise ApiError(503, "service_unavailable", "复核文件存储暂不可用。", reason_code="quality_storage_unavailable")
            self._ensure_file_reader_available()
            try:
                content = self.file_upload_service.read_file_content(result_file)
            except FileNotFoundError as exc:
                raise conflict("当前主 DOCX 不可用，不能批准复核。", "review_result_unavailable") from exc
            except Exception as exc:
                from app.domains.document_jobs.preview import _is_preview_storage_error
                if expected_source is not None and _is_preview_storage_error(exc):
                    raise ApiError(503, "service_unavailable", "复核文件存储暂不可用。", reason_code="quality_storage_unavailable") from None
                raise
            actual_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
            if (len(content) != result_file.size_bytes or
                (result_file.checksum_sha256 is not None and result_file.checksum_sha256 != actual_hash)
                or (job.prepared_result is not None and not receipt_matches_file(result_file, job.prepared_result))):
                raise conflict("当前主 DOCX 与登记或选定凭据的完整性描述不一致。", "review_result_integrity_conflict")
            latest = self.file_repository.get_document_file(result_file.id)
            if (latest is None or latest.review_source_revision != result_file.review_source_revision
                    or review_source_descriptor(latest) != review_source_descriptor(result_file)):
                raise conflict("复核期间主件来源已变化，请重新读取。", "review_source_changed")
        elif expected_source is None and job.result_file_id is not None:
            result_file = self.file_repository.get_document_file(job.result_file_id)
            if result_file is not None and ((result_file.tenant_id, result_file.company_id, result_file.job_id)
                                          != (job.tenant_id, job.company_id, job.id)):
                result_file = None
        if expected_source is not None:
            latest = self._review_api_file(job, conflict_reason="review_result_integrity_conflict")
            if (observed_review_source(job, latest) != expected_source or
                    latest is not None and review_source_descriptor(latest) != review_source_descriptor(result_file)):
                raise conflict("复核来源已变化，请重新读取。", "review_source_changed")
        now = utc_now()
        binding = ReviewBinding(generation=job.retry_count, result_file_id=job.result_file_id,
            binding_state="verified" if actual_hash else ("no_result" if job.result_file_id is None else "unverified_result"),
            result_sha256=actual_hash, file_review_source_revision=result_file.review_source_revision if result_file else None,
            descriptor=review_source_descriptor(result_file) if result_file else None, receipt_sha256=receipt_identity(job))
        submission = ReviewSubmission(record_id=f"review_{uuid4().hex}", status=review_status, issue_type=issue_type,
            note=self._normalize_optional_text(note), reviewed_by=user.id, reviewed_at=now, reviewer_role=user.role,
            binding=binding, expected_source=expected_source)
        try:
            updated = self.job_repository.update_document_job_review_if_current(job.id, submission=submission)
        except ReviewSubmissionConflict as exc:
            raise conflict("复核提交条件已变化，请重新读取。", exc.reason_code) from None
        if updated is None:
            raise conflict("任务代数、当前主件或复核条件已变化，请刷新后重试。", "review_source_changed")
        effective = self._effective_job(updated)
        self.record_event(updated, event_type="translation_qa_updated", stage=updated.stage, level="info",
            message="文档复核状态已更新。", payload={
                "observed_review_status": job.review_status, "record_status": submission.status,
                "review_status": effective.review_status, "status": effective.review_status,
                "issue_type": translation_qa_projection(updated)["translation_qa_issue_type"] if is_translation_document_job_mode(job.mode) else issue_type,
                "reviewed_by": user.id, "generation": updated.retry_count, "result_file_id": updated.result_file_id,
                "checksum_sha256": actual_hash, "note_length": len(submission.note or ""),
                "review_record_id": updated.current_review_record_id, "review_sequence": updated.review_sequence,
            }, trace_id=trace_id)
        return _ReviewCommit(effective, updated.current_review_record_id, updated.review_sequence)

    def get_result_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """校验任务权限和完成状态后返回生成 Word 文件。"""

        job = self._get_job(job_id, user=user)
        file = self._get_downloadable_completed_result_file(job)
        return effective_review_job(job, file, now=utc_now()), file

    def get_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        file_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """按可见任务签发文件下载前，校验文件归属、状态、过期和类型。"""

        job = self._get_job(job_id, user=user)
        file = (self._get_downloadable_completed_result_file(job) if file_id is None
                else self._get_downloadable_task_file(job, file_id=file_id))
        view = effective_review_job(job, file, now=utc_now()) if file.id == job.result_file_id else self._effective_job(job)
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
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        file = self._get_downloadable_completed_result_file(job)
        if file.id != file_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接与结果文件不匹配。")
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
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        return job, self._get_downloadable_task_file(job, file_id=file_id)

    def retry_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        use_latest_term_assets: bool = False,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """对可重试失败任务按原 job_id 重新投递，保留既有中间产物用于幂等恢复。"""

        job = self._get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        self._ensure_resource_selection_allowed(
            user=user,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if job.archived_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "已归档文档任务不允许重试。")
        self._ensure_retry_allowed(job)
        self._ensure_direct_translation_selection_absent(
            job.mode,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        now = utc_now()
        retry_count = job.retry_count + 1
        patch = self._build_retry_patch(
            job,
            retry_count=retry_count,
            now=now,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        retried = self.job_repository.retry_document_job(
            job.id, expected_retry_count=job.retry_count,
            max_retries=self.settings.p0_document_job_max_retries, **patch,
        )
        if retried is None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "任务状态或重试代数已变化，无法重试。")
        self.record_event(
            retried,
            event_type="retry_requested",
            stage=retried.stage,
            level="info",
            message="文档任务已请求重试。",
            payload={
                "retry_count": retry_count,
                "reason": self._normalize_optional_text(reason),
                "previous_error_code": job.error_code,
                "previous_failed_stage": job.failed_stage,
                "previous_prepared_result_file_id": job.prepared_result.file.id if job.prepared_result else None,
                "resume_stage": retried.stage,
                "use_latest_term_assets": use_latest_term_assets,
                "term_assets": retried.request_snapshot.get("term_assets"),
                "resources": retried.request_snapshot.get("resources"),
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return retried
        try:
            self.task_queue.enqueue(retried.id, trace_id=trace_id)
        except RuntimeError as exc:
            failed = self._mark_enqueue_failed(retried, str(exc), trace_id=trace_id)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or retried

    def retry_word_preview(self, job_id: str, *, user: AuthenticatedUser, reason: str, request_id: str,
                           trace_id: str | None = None) -> PreviewRetryResult:
        """内部应用入口；沿用 owner/Admin 范围，不增加 HTTP 重试路由。"""
        job = self.get_job(job_id, user=user)
        if self.word_preview_service is None:
            raise ApiError(503, "service_unavailable", "Word 预览应用服务未配置。")
        return self.word_preview_service.retry(job, user=user, reason=reason, request_id=request_id, trace_id=trace_id)

    def clone_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        config_strategy: str,
        document_language: str | None = None,
        template_version_id: str | None = None,
        term_version_id: str | None = None,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        debug_full_text: bool | None = None,
        trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """把源任务复制为一个新 document_job；不修改源任务，也不复用 retry 语义。"""

        source_job = self._get_job(job_id, user=user)
        self._ensure_job_not_deleted(source_job)
        source_file = self._get_source_file_for_clone(source_job)
        explicit_values = {
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_rule_set_id": term_rule_set_id,
            "term_rule_set_version": term_rule_set_version,
            "translation_term_set_id": translation_term_set_id,
            "translation_term_version": translation_term_version,
            "translation_profile_id": translation_profile_id,
            "translation_profile_version": translation_profile_version,
        }
        if config_strategy != "select_published_versions" and any(
            self._normalize_optional_text(value) for value in explicit_values.values()
        ):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "只有 select_published_versions 支持显式资源版本。")
        if config_strategy == "select_published_versions":
            self._ensure_resource_selection_allowed(user=user, **explicit_values)
        elif config_strategy not in {"keep_source_snapshot", "use_current_defaults"}:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "config_strategy 非法。")
        requested_debug_full_text = bool(debug_full_text)
        inherited_debug_full_text = (
            config_strategy == "keep_source_snapshot"
            and debug_full_text is None
            and source_job.debug_full_text_enabled
        )
        self._ensure_debug_full_text_allowed(user, requested_debug_full_text or inherited_debug_full_text)
        self._ensure_direct_translation_selection_absent(
            source_job.mode,
            term_version_id=term_version_id,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=requested_debug_full_text,
        )

        now = utc_now()
        new_job_id = f"docjob_{uuid4().hex[:12]}"
        normalized_document_language = document_language or source_job.document_language
        self._ensure_document_language_allowed(source_job.mode, normalized_document_language)
        clone_config = self._resolve_clone_config(
            source_job,
            source_file,
            new_job_id=new_job_id,
            config_strategy=config_strategy,
            document_language=normalized_document_language,
            template_version_id=template_version_id,
            term_version_id=term_version_id,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=debug_full_text,
            reason=reason,
        )
        cloned = DocumentJobRecord(
            id=new_job_id,
            tenant_id=source_job.tenant_id,
            company_id=source_job.company_id,
            created_by=user.id,
            source_file_id=source_file.id,
            source_job_id=source_job.id,
            mode=source_job.mode,
            document_language=normalized_document_language,
            status="pending",
            stage="uploaded",
            progress=0,
            quality_summary=fresh_quality_summary(0),
            template_version_id=clone_config["template_version_id"],
            term_version_id=clone_config["term_version_id"],
            debug_full_text_enabled=clone_config["debug_full_text_enabled"],
            timeout_at=now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            request_snapshot=clone_config["request_snapshot"],
            created_at=now,
            updated_at=now,
        )
        self.job_repository.create_document_job(cloned)
        self.record_event(
            cloned,
            event_type="job_cloned",
            stage="uploaded",
            level="info",
            message="文档任务已重新发起为新任务。",
            payload={
                "source_job_id": source_job.id,
                "source_file_id": source_file.id,
                "config_strategy": config_strategy,
                "reason": self._normalize_optional_text(reason),
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return cloned
        return self._enqueue_created_job(cloned, trace_id=trace_id)

    def archive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """归档终态 document_job，仅隐藏列表记录，不删除文件或事件。"""

        job = self._get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is not None:
            return self._effective_job(job)
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 succeeded、failed、canceled 终态任务允许归档。")
        now = utc_now()
        archived = self.job_repository.update_document_job_lifecycle_if_current(job.id,
            expected_retry_count=job.retry_count, action="archive", actor_id=user.id, occurred_at=now)
        if archived is None:
            raise ApiError(409, "conflict", "任务代次或终态已变化，不能归档旧来源。")
        self.record_event(
            archived,
            event_type="job_archived",
            stage=archived.stage,
            level="info",
            message="文档任务已归档并从默认列表隐藏。",
            payload={"archived_by": user.id, "status": archived.status},
            trace_id=trace_id,
        )
        return self._effective_job(archived)

    def unarchive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """恢复误归档 document_job；只更新归档元数据，不触碰文件或状态。"""

        job = self._get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is None:
            return self._effective_job(job)
        now = utc_now()
        restored = self.job_repository.update_document_job(
            job.id,
            archived_at=None,
            archived_by=None,
            updated_at=now,
        )
        self.record_event(
            restored,
            event_type="job_unarchived",
            stage=restored.stage,
            level="info",
            message="文档任务已取消归档并恢复到默认列表。",
            payload={"restored_by": user.id, "status": restored.status},
            trace_id=trace_id,
        )
        return self._effective_job(restored)

    def preview_delete_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> DocumentJobDeletePlan:
        """构建 Admin-only 任务删除计划；不修改任务、文件、事件或审计。"""

        job = self._get_job(job_id, user=user)
        self._ensure_delete_allowed(job, user=user)
        return self._build_delete_plan(job, action_mode="delete_preview")

    def delete_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        confirmation: str | None,
        preview_hash: str,
        trace_id: str | None,
    ) -> DocumentJobDeletePlan:
        """按预览 hash 执行 Admin-only 任务删除，保留任务 metadata 和审计证据。"""

        job = self._get_job(job_id, user=user)
        self._ensure_delete_allowed(job, user=user)
        normalized_reason = self._normalize_optional_text(reason) or DEFAULT_DOCUMENT_JOB_DELETE_REASON
        if confirmation is not None:
            expected_confirmation = self._delete_confirmation_phrase(job)
            if confirmation != expected_confirmation:
                raise ApiError(
                    status.HTTP_400_BAD_REQUEST,
                    "invalid_request",
                    f"confirmation 必须为 {expected_confirmation}。",
                )
        preview = self._build_delete_plan(job, action_mode="delete_preview")
        if preview.preview_hash != preview_hash:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "删除预览已过期，请重新预览后再执行。")

        delete_file_ids = [item.file_id for item in preview.files if item.action == "delete"]
        if delete_file_ids and self.file_upload_service is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "文件清理服务不可用，无法删除任务文件。")
        # deleted_at 是持久生命周期预留；确认赢得本代后，才允许取得文件删除 claim。
        now = utc_now()
        try:
            deleted = self.job_repository.update_document_job_lifecycle_if_current(job.id,
                expected_retry_count=job.retry_count, action="delete", actor_id=user.id, occurred_at=now,
                delete_reason=normalized_reason)
        except Exception as error:
            if not _is_preview_storage_error(error):
                raise
            raise ApiError(503, "service_unavailable", "任务删除预留暂不可确认，请先核对原任务状态。",
                reason_code="document_job_deletion_unknown") from None
        if deleted is None:
            raise ApiError(409, "conflict", "任务代次、发布或删除状态已变化，未执行文件删除。")
        executed_files = preview.files
        if delete_file_ids:
            try:
                physical_delete = self.file_upload_service.execute_document_job_physical_delete(delete_file_ids)
            except Exception as error:
                _SYSTEM_LOGGER.error("任务删除预留已提交，文件清理结果未确认 job_id=%s generation=%s trace_id=%s exception_type=%s",
                    deleted.id, deleted.retry_count, trace_id, type(error).__name__)
                raise
            physical_items = {item.file_id: item for item in physical_delete.items}
            executed_files = [
                self._delete_plan_file_from_physical_item(physical_items[item.file_id], action="delete")
                if item.file_id in physical_items
                else item
                for item in preview.files
            ]

        self.record_event(
            deleted,
            event_type="job_deleted",
            stage=deleted.stage,
            level="info",
            message="文档任务已删除，任务 metadata、事件和审计证据已保留。",
            payload={
                "deleted_by": user.id,
                "delete_reason_length": len(normalized_reason),
                "files": self._delete_plan_totals(executed_files),
            },
            trace_id=trace_id,
        )
        return self._build_delete_plan(
            self._effective_job(deleted),
            action_mode="delete_execute",
            files=executed_files,
            physical_delete_executed=bool(delete_file_ids),
            metadata_mutated=True,
            audit_events_written=True,
            preview_hash=preview.preview_hash,
        )

    def cancel_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """把未终态 document_job 标记为 canceled，保留所有文件和事件。"""

        job = self._get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "已归档文档任务不允许取消。")
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 pending、queued、running 任务允许取消。")
        now = utc_now()
        canceled = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses=CANCELABLE_DOCUMENT_JOB_STATUSES,
            allowed_stages={
                "uploaded", "parsing", "parsed", "ir_converting", "translating",
                "translation_validating", "rendering", "quality_checking", "uploading",
            },
            expected_retry_count=job.retry_count,
            status="canceled",
            stage="canceled",
            canceled_at=now,
            updated_at=now,
        )
        if canceled is None:
            latest = self.job_repository.get_document_job(job.id) or job
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"任务状态已变化，无法取消: status={latest.status} stage={latest.stage}",
            )
        self.record_event(
            canceled,
            event_type="job_canceled",
            stage="canceled",
            level="info",
            message="文档任务已取消，文件和事件记录已保留。",
            payload={
                "canceled_by": user.id,
                "previous_status": job.status,
                "previous_stage": job.stage,
            },
            trace_id=trace_id,
        )
        return canceled

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

        self.record_event(
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

    def record_event(
        self,
        job: DocumentJobRecord,
        *,
        event_type: DocumentJobEventType,
        stage: DocumentJobStage,
        level: DocumentJobEventLevel,
        message: str,
        payload: dict,
        trace_id: str | None,
        duration_ms: int | None = None,
    ) -> DocumentJobEventRecord:
        """写入 document_job 事件；调用方负责保证 payload 不包含敏感全文。"""

        event = DocumentJobEventRecord(
            id=f"event_{uuid4().hex[:12]}",
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            stage=stage,
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self.event_repository.append_document_job_event(job.id, event)
        return event

    def _enqueue_created_job(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        queued = self._mark_created_job_queued(job, trace_id=trace_id)
        try:
            self.task_queue.enqueue(queued.id, trace_id=trace_id)
        except RuntimeError as exc:
            failed = self._mark_enqueue_failed(queued, str(exc), trace_id=trace_id)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or queued

    def _mark_created_job_queued(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        now = utc_now()
        queued = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={"pending"}, allowed_stages={"uploaded"},
            expected_retry_count=job.retry_count, require_no_prepared_result=True,
            status="queued",
            stage="uploaded",
            progress=max(job.progress, 5),
            updated_at=now,
        )
        if queued is None:
            return self.job_repository.get_document_job(job.id) or job
        self.record_event(
            queued,
            event_type="stage_started",
            stage="uploaded",
            level="info",
            message="文档任务已投递 Worker。",
            payload={"worker_backend": self.settings.document_jobs_worker_backend},
            trace_id=trace_id,
        )
        return queued

    def _mark_enqueue_failed(
        self,
        job: DocumentJobRecord,
        error_message: str,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        failed = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={job.status}, allowed_stages={job.stage},
            expected_retry_count=job.retry_count, require_no_prepared_result=True,
            status="failed",
            stage="failed",
            failed_stage="uploaded",
            error_code="worker_enqueue_failed",
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
        if failed is None:
            return self.job_repository.get_document_job(job.id) or job
        self.record_event(
            failed,
            event_type="stage_failed",
            stage="uploaded",
            level="error",
            message="Worker 投递失败。",
            payload={"error_code": "worker_enqueue_failed"},
            trace_id=trace_id,
        )
        return failed

    def _ensure_retry_allowed(self, job: DocumentJobRecord) -> None:
        reason = self._retry_disabled_reason(job)
        if reason is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", reason)

    def _is_retryable_failure(self, job: DocumentJobRecord) -> bool:
        if job.error_code in {"document_job_invalid_input"}:
            return False
        return True

    def _build_retry_patch(
        self,
        job: DocumentJobRecord,
        *,
        retry_count: int,
        now,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        term_rule_department_id: str | None = None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict:
        resume_status, resume_stage, resume_progress = self._retry_resume_state(job)
        patch = {
            "status": resume_status,
            "stage": resume_stage,
            "progress": resume_progress,
            "failed_stage": None,
            "error_code": None,
            "error_message": None,
            "retry_count": retry_count,
            "timeout_at": now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        next_request_snapshot = self._build_retry_request_snapshot(
            job,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if next_request_snapshot is not None:
            patch["request_snapshot"] = next_request_snapshot
            selected_term_version = self._legacy_translation_term_version_id(
                job.mode,
                None if use_latest_term_assets else job.term_version_id,
                None if use_latest_term_assets else translation_term_version,
            )
            patch["term_version_id"] = self._resolve_term_version_id(job.mode, selected_term_version)
        if job.failed_stage == "parsing" and job.mineru_raw_result_file_id is None:
            patch["mineru_batch_id"] = None
            patch["mineru_data_id"] = None
            patch["mineru_callback_seed"] = None
        return patch

    def _retry_resume_state(self, job: DocumentJobRecord) -> tuple[str, str, int]:
        """按已持久化产物选择最早可安全恢复的阶段。"""

        if job.result_file_id is not None:
            return "running", "uploading", max(job.progress, 90)
        if job.document_ir_file_id is not None:
            return "running", "rendering", max(job.progress, 60)
        if job.mineru_raw_result_file_id is not None:
            return "running", "parsed", max(job.progress, 30)
        return ("queued", "uploaded", 5) if self.task_queue is not None else ("pending", "uploaded", 0)

    def _build_translation_qa_state(self, job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
        return DocumentJobTranslationQaStateResponse(
            **{key.removeprefix("translation_qa_"): value for key, value in translation_qa_projection(job).items()}
        )

    def _build_unavailable_translation_qa(
        self,
        job: DocumentJobRecord,
        qa: DocumentJobTranslationQaStateResponse,
        *,
        reason: str,
        artifacts: DocumentJobTranslationQaArtifactsResponse | None = None,
        ai_calls: list[DocumentJobTranslationQaAiCallResponse] | None = None,
        term_traces: list[DocumentJobTranslationQaTermTraceResponse] | None = None,
        source_reason: str | None = None,
    ) -> DocumentJobTranslationQaResponse:
        ai_call_items = ai_calls or []
        term_trace_items = term_traces or []
        return DocumentJobTranslationQaResponse(
            job_id=job.id,
            available=False,
            availability_reason=reason,
            qa=qa,
            artifacts=artifacts or DocumentJobTranslationQaArtifactsResponse(),
            summary=DocumentJobTranslationQaSummaryResponse(
                ai_call_count=len(ai_call_items),
                ai_call_statuses=dict(Counter(call.status or "unknown" for call in ai_call_items)),
                term_trace_count=len(term_trace_items),
                debug_full_text_enabled=job.debug_full_text_enabled,
                source_comparison_available=False,
                source_comparison_reason=source_reason,
            ),
            segments=[],
            term_traces=term_trace_items,
            ai_calls=ai_call_items,
        )

    def _ensure_file_reader_available(self) -> None:
        if self.file_upload_service is not None:
            return
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_unavailable",
            "翻译 QA 需要文件读取服务。",
        )

    def _uploaded_files_by_type(self, files: list[DocumentFileRecord], file_type: DocumentFileType) -> list[DocumentFileRecord]:
        return [
            file
            for file in files
            if file.file_type == file_type and file.status == "uploaded"
        ]

    def _select_document_ir_file(
        self,
        job: DocumentJobRecord,
        files: list[DocumentFileRecord],
    ) -> DocumentFileRecord | None:
        if job.document_ir_file_id:
            file = self.file_repository.get_document_file(job.document_ir_file_id)
            if file is not None and file.job_id == job.id and file.file_type == "document_ir" and file.status == "uploaded":
                return file
        candidates = self._uploaded_files_by_type(files, "document_ir")
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[-1]

    def _build_translation_qa_artifacts(
        self,
        *,
        document_ir_file: DocumentFileRecord | None,
        ai_log_files: list[DocumentFileRecord],
        debug_archive_files: list[DocumentFileRecord],
    ) -> DocumentJobTranslationQaArtifactsResponse:
        latest_debug_archive = self._latest_file(debug_archive_files)
        now = utc_now()
        return DocumentJobTranslationQaArtifactsResponse(
            document_ir_file_id=document_ir_file.id if document_ir_file is not None else None,
            ai_call_log_file_ids=[file.id for file in ai_log_files],
            ai_debug_archive_file_ids=[file.id for file in debug_archive_files],
            ai_debug_archive_expires_at=latest_debug_archive.expires_at if latest_debug_archive is not None else None,
            ai_debug_archive_expired=(
                latest_debug_archive.expires_at is not None and latest_debug_archive.expires_at <= now
                if latest_debug_archive is not None
                else False
            ),
            ai_debug_archive_contains_full_text=bool(
                latest_debug_archive is not None
                and latest_debug_archive.metadata.get("contains_full_text") is True
            ),
        )

    def _latest_file(self, files: list[DocumentFileRecord]) -> DocumentFileRecord | None:
        if not files:
            return None
        return sorted(files, key=lambda item: (item.created_at, item.id))[-1]

    def _read_document_ir(self, file: DocumentFileRecord) -> DocumentIR | None:
        try:
            return DocumentIR.model_validate_json(self.file_upload_service.read_file_content(file))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _read_ai_call_log_summaries(
        self,
        files: list[DocumentFileRecord],
    ) -> tuple[list[DocumentJobTranslationQaAiCallResponse], list[DocumentJobTranslationQaTermTraceResponse]]:
        ai_calls: list[DocumentJobTranslationQaAiCallResponse] = []
        term_traces: list[DocumentJobTranslationQaTermTraceResponse] = []
        for file in files:
            payload = self._read_json_file(file)
            if payload is None:
                continue
            request_summary = self._read_record(payload.get("request"))
            error = self._read_record(payload.get("error"))
            ai_calls.append(
                DocumentJobTranslationQaAiCallResponse(
                    file_id=file.id,
                    call_id=self._read_string(payload.get("call_id")),
                    status=self._read_string(payload.get("status")),
                    provider=self._read_record(payload.get("provider")) or {},
                    language_pair=self._read_string(payload.get("language_pair")),
                    source_language=self._read_string(payload.get("source_language")),
                    target_language=self._read_string(payload.get("target_language")),
                    term_version_id=self._read_string(payload.get("term_version_id")),
                    term_snapshot_hash=self._read_string(payload.get("term_snapshot_hash")),
                    term_count=self._read_int(payload.get("term_count")),
                    item_count=self._read_int(request_summary.get("item_count") if request_summary else None),
                    char_count=self._read_int(request_summary.get("char_count") if request_summary else None),
                    duration_ms=self._read_optional_int(payload.get("duration_ms")),
                    created_at=self._read_string(payload.get("created_at")),
                    error_type=self._read_string(error.get("type") if error else None),
                    error_message=self._read_string(error.get("message") if error else None),
                )
            )
            for raw_trace in self._read_list(payload.get("glossary_trace")):
                trace = self._read_record(raw_trace)
                if trace is None:
                    continue
                term_traces.append(
                    DocumentJobTranslationQaTermTraceResponse(
                        segment_id=self._read_string(trace.get("segment_id")),
                        batch_id=self._read_string(trace.get("batch_id")),
                        translation_term_set_id=self._read_string(trace.get("translation_term_set_id")),
                        translation_term_version=self._read_string(trace.get("translation_term_version")),
                        source_term=self._read_string(trace.get("source_term")),
                        target_term=self._read_string(trace.get("target_term")),
                        match_start=self._read_optional_int(trace.get("match_start")),
                        match_end=self._read_optional_int(trace.get("match_end")),
                        context=self._read_record(trace.get("context")),
                        injected_to_glossary=bool(trace.get("injected_to_glossary")),
                        provider_trace_id=self._read_string(trace.get("provider_trace_id")),
                    )
                )
        return ai_calls, term_traces

    def _read_debug_archive_texts(
        self,
        files: list[DocumentFileRecord],
    ) -> tuple[dict[str, str], dict[str, str], str | None]:
        if not files:
            return {}, {}, "ai_debug_archive_missing"
        now = utc_now()
        available_files = [
            file
            for file in files
            if file.expires_at is None or file.expires_at > now
        ]
        if not available_files:
            return {}, {}, "ai_debug_archive_expired"
        source_texts: dict[str, str] = {}
        ai_translation_texts: dict[str, str] = {}
        for file in available_files:
            payload = self._read_json_file(file)
            if payload is None:
                continue
            prompt = self._read_record(payload.get("prompt")) or {}
            response = self._read_record(payload.get("response")) or {}
            source_texts.update(self._items_text_map(prompt.get("items")))
            ai_translation_texts.update(self._items_text_map(response.get("items")))
        if not source_texts and not ai_translation_texts:
            return {}, {}, "ai_debug_archive_no_text"
        return source_texts, ai_translation_texts, None

    def _read_json_file(self, file: DocumentFileRecord) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.file_upload_service.read_file_content(file).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _items_text_map(self, value: Any) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_item in self._read_list(value):
            item = self._read_record(raw_item)
            if item is None:
                continue
            item_id = self._read_string(item.get("id"))
            text = self._read_string(item.get("text"))
            if item_id is not None and text is not None:
                result[item_id] = text
        return result

    def _build_translation_qa_segments(
        self,
        document_ir: DocumentIR,
        *,
        source_texts: dict[str, str],
        ai_translation_texts: dict[str, str],
    ) -> list[DocumentJobTranslationQaSegmentResponse]:
        segments: list[DocumentJobTranslationQaSegmentResponse] = []
        for block in sorted(document_ir.blocks, key=lambda item: item.order):
            if self._normalize_optional_text(block.text):
                item_id = f"{block.id}.text"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="text",
                        index=None,
                        final_text=block.text or "",
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
            for index, text in enumerate(block.list_items or []):
                if not self._normalize_optional_text(text):
                    continue
                item_id = f"{block.id}.list_items.{index:04d}"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="list_items",
                        index=index,
                        final_text=text,
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
            for index, text in enumerate(self._extract_html_text_nodes(block.html)):
                if not self._normalize_optional_text(text):
                    continue
                item_id = f"{block.id}.html.{index:04d}"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="html",
                        index=index,
                        final_text=text,
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
        return segments

    def _build_translation_qa_segment(
        self,
        *,
        item_id: str,
        block_id: str,
        page_index: int | None,
        order: int,
        block_type: str,
        field: str,
        index: int | None,
        final_text: str,
        source_texts: dict[str, str],
        ai_translation_texts: dict[str, str],
    ) -> DocumentJobTranslationQaSegmentResponse:
        source_text = source_texts.get(item_id)
        ai_translation_text = ai_translation_texts.get(item_id)
        return DocumentJobTranslationQaSegmentResponse(
            id=item_id,
            block_id=block_id,
            page_index=page_index,
            order=order,
            block_type=block_type,
            field=field,
            index=index,
            source_text=source_text,
            ai_translation_text=ai_translation_text,
            final_text=final_text,
            source_available=source_text is not None or ai_translation_text is not None,
        )

    def _extract_html_text_nodes(self, html: str | None) -> list[str]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        return [str(node).strip() for node in soup.find_all(string=True) if str(node).strip()]

    def _read_record(self, value: Any) -> dict[str, Any] | None:
        return value if isinstance(value, dict) else None

    def _read_list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _read_string(self, value: Any) -> str | None:
        return value if isinstance(value, str) else None

    def _read_int(self, value: Any) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    def _read_optional_int(self, value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _get_source_file_for_create(self, file_id: str, user: AuthenticatedUser) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(file_id)
        if source_file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"源文件不存在: {file_id}")
        if source_file.file_type != "source_pdf":
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "document_job 只能使用 source_pdf 文件创建。")
        if source_file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源文件尚未完成上传。")
        if source_file.job_id is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源文件已绑定其他任务。")
        if source_file.tenant_id != user.tenant_id or source_file.company_id != user.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限使用该源文件。")
        if user.role != "admin" and source_file.created_by != user.id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "operator 只能使用自己上传的源文件。")
        return source_file

    def _get_source_file_for_clone(self, job: DocumentJobRecord) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源任务的 source_pdf 文件不存在，不能重新发起。")
        if source_file.file_type != "source_pdf":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源任务文件不是 source_pdf，不能重新发起。")
        if source_file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源 PDF 尚不可用，不能重新发起。")
        if source_file.tenant_id != job.tenant_id or source_file.company_id != job.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "源 PDF 与任务租户不匹配。")
        if source_file.expires_at is not None and source_file.expires_at <= utc_now():
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源 PDF 已过期，不能重新发起。")
        return source_file

    def _get_completed_result_file(self, job: DocumentJobRecord, *,
            observed_result: DocumentFileRecord | None | object = _UNREAD_RESULT) -> DocumentFileRecord:
        self._ensure_job_not_deleted(job, reason_code="job_deleted")
        if job.status != "succeeded" or job.stage != "completed":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务尚未成功完成，生成 Word 不可下载。", reason_code="job_not_completed")
        if job.result_file_id is None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务尚未成功完成，生成 Word 不可下载。", reason_code="result_file_missing")
        file = self.file_repository.get_document_file(job.result_file_id) if observed_result is _UNREAD_RESULT else observed_result
        if file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"结果文件不存在: {job.result_file_id}", reason_code="result_file_missing")
        if ((file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.file_type != "generated_word"):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "结果文件与文档任务不匹配。", reason_code="result_file_mismatch")
        if file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "结果文件尚未完成上传。", reason_code="result_file_not_uploaded")
        return file

    def _get_downloadable_completed_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        file = self._get_completed_result_file(job)
        self._ensure_file_not_expired(file)
        return file

    def _list_files_for_job(self, job: DocumentJobRecord) -> list[DocumentFileRecord]:
        candidates = [
            file
            for file in self.file_repository.list_document_files()
            if file.tenant_id == job.tenant_id
            and file.company_id == job.company_id
            and file.file_type in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES
            and self._file_belongs_to_job(job, file)
        ]
        # 完整预览只观测一次；以刚验证的Record筛选列表快照，避免逐页重读全组。
        preview_files = verified_current_preview_files(job, self.file_repository, self.file_upload_service) if any(
            file.file_type in PREVIEW_FILE_TYPES for file in candidates
        ) else {}
        files = [file for file in candidates if (
            preview_files.get(file.id) == file if file.file_type in PREVIEW_FILE_TYPES
            else self._is_current_downloadable_job_file(job, file)
        )]
        return sorted(
            files,
            key=lambda file: (
                DOCUMENT_JOB_FILE_TYPE_ORDER.get(file.file_type, 100),
                file.created_at,
                file.id,
            ),
        )

    def _get_downloadable_task_file(self, job: DocumentJobRecord, *, file_id: str) -> DocumentFileRecord:
        self._ensure_job_not_deleted(job, reason_code="job_deleted")
        file = self.file_repository.get_document_file(file_id)
        if file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文件不存在: {file_id}")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if not self._file_belongs_to_job(job, file):
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if file.file_type not in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "该文件类型不支持从任务详情下载。")
        if not self._is_current_downloadable_job_file(job, file):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "该文件不属于当前任务重试轮次，不能从任务详情下载。", reason_code="file_not_current")
        if file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件尚未完成上传，不能下载。", reason_code="result_file_not_uploaded")
        self._ensure_file_not_expired(file)
        return file

    def _ensure_file_not_expired(self, file: DocumentFileRecord, *, as_of: datetime | None = None) -> None:
        if file.deletion_claim is not None:
            raise ApiError(409, "conflict", "文件已预留删除。", reason_code="file_deletion_reserved")
        if file.expires_at is not None and file.expires_at <= (as_of if as_of is not None else utc_now()) and not self.file_repository.is_document_file_protected(file.id):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件已过期，不能下载。", reason_code="file_expired")

    def _file_belongs_to_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        return file.job_id == job.id or file.id == job.source_file_id

    def _is_current_downloadable_job_file(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
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
        return self._file_matches_current_retry_count(job, file)

    def _file_matches_current_retry_count(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        retry_count = self._file_retry_count(file)
        if retry_count is None:
            return job.retry_count == 0
        return retry_count == job.retry_count

    @staticmethod
    def _file_retry_count(file: DocumentFileRecord) -> int | None:
        raw_value = (file.metadata or {}).get("retry_count")
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str) and raw_value.isdigit():
            return int(raw_value)
        return None

    def _ensure_delete_allowed(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> None:
        reason = self._delete_disabled_reason(job, user=user)
        if reason is not None:
            if user.role != "admin":
                raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", reason)
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", reason)

    def _ensure_job_not_deleted(self, job: DocumentJobRecord, *, reason_code: str | None = None) -> None:
        if job.deleted_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务已删除。", reason_code=reason_code)

    def _build_delete_plan(
        self,
        job: DocumentJobRecord,
        *,
        action_mode: str,
        files: list[DocumentJobDeletePlanFile] | None = None,
        physical_delete_executed: bool = False,
        metadata_mutated: bool = False,
        audit_events_written: bool = False,
        preview_hash: str | None = None,
    ) -> DocumentJobDeletePlan:
        plan_files = files if files is not None else self._build_delete_plan_files(job)
        return DocumentJobDeletePlan(
            job=job,
            action_mode=action_mode,
            confirmation_phrase=self._delete_confirmation_phrase(job),
            preview_hash=preview_hash or self._delete_preview_hash(job, plan_files),
            totals=self._delete_plan_totals(plan_files),
            files=plan_files,
            safety={
                "physical_delete_executed": physical_delete_executed,
                "metadata_mutated": metadata_mutated,
                "audit_events_written": audit_events_written,
                "s3_delete_executed": False,
                "deleted_job_metadata_retained": True,
            },
        )

    def _build_delete_plan_files(self, job: DocumentJobRecord) -> list[DocumentJobDeletePlanFile]:
        return [self._build_delete_plan_file(job, file) for file in self._list_files_for_job(job)]

    def _build_delete_plan_file(self, job: DocumentJobRecord, file: DocumentFileRecord) -> DocumentJobDeletePlanFile:
        keep_reason = self._delete_keep_reason(job, file)
        if keep_reason is not None:
            return DocumentJobDeletePlanFile(
                file_id=file.id,
                file_type=file.file_type,
                storage_provider=file.storage_provider,
                status_before=file.status,
                status_after=file.status,
                size_bytes=file.size_bytes,
                action="keep",
                outcome="kept",
                reason=keep_reason,
                s3_delete_contract=self._delete_s3_contract_summary(file),
            )
        return DocumentJobDeletePlanFile(
            file_id=file.id,
            file_type=file.file_type,
            storage_provider=file.storage_provider,
            status_before=file.status,
            status_after=file.status,
            size_bytes=file.size_bytes,
            action="delete",
            outcome="deletable",
            reason="任务删除将清理该文件。",
        )

    def _delete_keep_reason(self, job: DocumentJobRecord, file: DocumentFileRecord) -> str | None:
        if file.status == "deleted":
            return "文件 metadata 已是 deleted。"
        if self._file_is_shared_with_other_job(job, file):
            return "文件仍被其他任务引用，已保留。"
        if file.status == "pending_upload":
            return "文件仍处于 pending_upload，未执行物理删除。"
        if file.storage_provider not in {"local_file", "local_object"}:
            return f"暂不支持物理删除 storage_provider={file.storage_provider}。"
        if not file.object_key.strip():
            return "文件缺少 object_key，不能物理删除。"
        return None

    def _file_is_shared_with_other_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        for other_job in self.job_repository.list_document_jobs():
            if other_job.id == job.id or other_job.deleted_at is not None:
                continue
            if self._file_belongs_to_job(other_job, file):
                return True
        return False

    def _delete_plan_file_from_physical_item(
        self,
        item: Any,
        *,
        action: str,
    ) -> DocumentJobDeletePlanFile:
        s3_contract = item.s3_delete_contract.to_dict() if item.s3_delete_contract is not None else None
        return DocumentJobDeletePlanFile(
            file_id=item.file_id,
            file_type=item.file_type,
            storage_provider=item.storage_provider,
            status_before=item.status_before,
            status_after=item.status_after,
            size_bytes=item.size_bytes,
            action=action,
            outcome=item.outcome,
            reason=item.reason,
            deleted=item.deleted,
            metadata_updated=item.metadata_updated,
            s3_delete_contract=s3_contract,
        )

    def _delete_s3_contract_summary(self, file: DocumentFileRecord) -> dict[str, Any] | None:
        if file.storage_provider != "s3":
            return None
        return {
            "contract_version": "s3-delete-fake-v1",
            "adapter_mode": "fake",
            "target_exact": bool(file.bucket.strip() and file.object_key.strip()),
            "expected_outcome": "fake_skipped",
            "safety": {
                "real_s3_delete_executed": False,
                "fake_s3_delete_executed": True,
                "metadata_mutated": False,
                "audit_events_written": False,
                "requires_future_real_adapter": True,
            },
        }

    def _delete_plan_totals(self, files: list[DocumentJobDeletePlanFile]) -> dict[str, int]:
        return {
            "files": len(files),
            "delete": sum(1 for item in files if item.action == "delete"),
            "keep": sum(1 for item in files if item.action == "keep"),
            "deleted": sum(1 for item in files if item.deleted),
            "skipped": sum(1 for item in files if item.outcome.startswith("skipped_") or item.outcome == "kept"),
            "failed": sum(1 for item in files if item.outcome == "failed"),
            "metadata_updated": sum(1 for item in files if item.metadata_updated),
        }

    def _delete_preview_hash(self, job: DocumentJobRecord, files: list[DocumentJobDeletePlanFile]) -> str:
        payload = {
            "job_id": job.id,
            "updated_at": job.updated_at.isoformat(),
            "confirmation_phrase": self._delete_confirmation_phrase(job),
            "files": [item.to_response_dict() for item in files],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _delete_confirmation_phrase(self, job: DocumentJobRecord) -> str:
        return f"DELETE {job.id}"

    def _ensure_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> None:
        if self._is_visible(job, user):
            return
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限访问该文档任务。")

    def _is_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> bool:
        if job.tenant_id != user.tenant_id or job.company_id != user.company_id:
            return False
        if user.role == "admin":
            return True
        return job.created_by == user.id

    def _matches_document_job_query(self, job: DocumentJobRecord, q: str | None) -> bool:
        if q is None:
            return True
        needle = q.casefold()
        return any(needle in value.casefold() for value in self._document_job_search_values(job))

    def _matches_status_filter(
        self,
        job: DocumentJobRecord,
        *,
        status_filter: str | None,
        status_group: str | None,
    ) -> bool:
        if status_filter is not None:
            return job.status == status_filter
        if status_group is not None:
            return job.status in DOCUMENT_JOB_STATUS_GROUPS[status_group]
        return True

    def _matches_translation_qa_status(
        self,
        job: DocumentJobRecord,
        translation_qa_status: str | None,
    ) -> bool:
        """按任务级翻译 QA 状态筛选；direct 任务不参与 QA 工作台筛选。"""

        if translation_qa_status is None:
            return True
        if translation_qa_status == "all":
            return is_translation_document_job_mode(job.mode)
        return is_translation_document_job_mode(job.mode) and job.review_status == translation_qa_status

    def _count_translation_qa_statuses(self, jobs: list[DocumentJobRecord]) -> dict[str, int]:
        counts = Counter(job.review_status for job in jobs)
        return {qa_status: counts.get(qa_status, 0) for qa_status in get_args(DocumentJobTranslationQaStatus)}

    def _document_job_search_values(self, job: _DocumentJobSearchable) -> list[str]:
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

    def _matches_created_range(
        self,
        job: DocumentJobRecord,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> bool:
        if created_from is not None and job.created_at < created_from:
            return False
        if created_to is not None and job.created_at > created_to:
            return False
        return True

    def _document_job_sort_key(self, job: DocumentJobRecord, sort: str) -> tuple[datetime, str]:
        if sort.startswith("updated_at"):
            return job.updated_at, job.id
        return job.created_at, job.id

    def _available_action(
        self,
        disabled_reason: str | None,
        *,
        retryable: bool = False,
    ) -> DocumentJobAvailableActionResponse:
        return DocumentJobAvailableActionResponse(
            enabled=disabled_reason is None,
            disabled_reason=disabled_reason,
            retryable=retryable,
        )

    def _build_result_read_view(
        self, job: DocumentJobRecord, *, observed_result: DocumentFileRecord | None | object = _UNREAD_RESULT,
        as_of: datetime | None = None,
    ) -> tuple[DocumentJobRecord, DocumentJobAvailableActionResponse]:
        """同一主件观察拥有有效复核和下载判定，期间不再次读取主件。"""

        file = None
        try:
            file = self._get_completed_result_file(job, observed_result=observed_result)
            self._ensure_file_not_expired(file, as_of=as_of)
        except ApiError as exc:
            reason = exc.message
            if exc.reason_code == "job_not_completed":
                reason = "只有 succeeded 文档任务允许下载结果。"
            elif exc.reason_code == "result_file_missing" and job.result_file_id is None:
                reason = "任务结果文件尚未登记，不能下载。"
            return effective_review_job(job, file, now=as_of if as_of is not None else utc_now()), DocumentJobAvailableActionResponse(
                enabled=False, disabled_reason=reason, disabled_reason_code=exc.reason_code,
            )
        view = effective_review_job(job, file, now=as_of if as_of is not None else utc_now())
        policy = self._download_policy_for_view(view, file)
        return view, DocumentJobAvailableActionResponse(
            enabled=True, classification=policy.classification,
            warning_code=policy.warning_code, warning_message=policy.warning_message,
        )

    def _build_publish_action(self, job: DocumentJobRecord, *, user: AuthenticatedUser,
        download: DocumentJobAvailableActionResponse,
    ) -> tuple[DocumentJobAvailableActionResponse, list[dict[str, Any]]]:
        """核心资格保持原语义；未执行的实物/预览/快照组合检查不能冒充通过。"""
        reasons = []
        checks = []

        def check(code, passed, reason_code, message):
            checks.append({"code": code, "status": "passed" if passed else "blocked",
                "reason_code": None if passed else reason_code, "message": "检查通过。" if passed else message})
            if not passed:
                reasons.append(DocumentJobActionDisabledReasonResponse(code=reason_code, message=message))

        check("result_download", download.enabled, download.disabled_reason_code or "download_unavailable",
            download.disabled_reason or "结果不可下载。")
        check("admin_role", user.role == "admin", "admin_required", "只有 Admin 可以发布文档。")
        check("quality", job.quality_status in {"passed", "warning"}, "quality_status_" + job.quality_status,
            "质量阻塞，不能发布。" if job.quality_status == "blocked" else "尚无质量结论，不能发布。")
        review_messages = {"unreviewed": "文档尚未复核。", "needs_fix": "文档复核要求修正。", "blocked": "文档复核已阻断。"}
        check("review", job.review_status == "approved", "review_status_" + job.review_status,
            review_messages.get(job.review_status, "文档尚无有效批准。"))
        check("publication_state", job.delivery_status != "published", "already_published", "该结果已发布，不能重复发布。")
        eligible = not reasons
        check("publication_write", self.settings.document_publication_enabled, "publication_disabled", "文档发布写入当前已停用。")
        if self.settings.document_publication_enabled and eligible:
            check("job_state", job.archived_at is None and job.deleted_at is None,
                "publication_state_conflict", "归档或删除任务不能发布。")
        evidence_check = {"code": "publication_evidence", "status": "not_checked", "reason_code": None,
            "message": "尚未核验预览、实物完整性、执行快照及保留能力；提交时由后端完整核验。"}
        if not reasons:
            try:
                evidence = prepare_publication_evidence(job, file_repository=self.file_repository,
                    file_service=self.file_upload_service, job_repository=self.job_repository)
                if any(self.file_repository.get_document_file(item.id) != item for item in evidence.files):
                    raise ApiError(409, "conflict", "发布证据在读取期间发生变化。", reason_code="publication_source_changed")
                evidence_check.update(status="passed", message="预览、实物、执行快照及保留能力检查通过。")
            except PublicationConflict as error:
                evidence_check.update(status="blocked", reason_code=error.reason_code, message=str(error))
            except Exception as error:
                if not _is_preview_storage_error(error):
                    raise
                evidence_check.update(status="blocked", reason_code="publication_storage_unavailable", message="发布存储暂不可用。")
            if evidence_check["status"] == "blocked":
                reasons.append(DocumentJobActionDisabledReasonResponse(code=evidence_check["reason_code"], message=evidence_check["message"]))
        checks.append(evidence_check)
        return DocumentJobAvailableActionResponse(
            enabled=not reasons, eligible=eligible, disabled_reason=reasons[0].message if reasons else None,
            disabled_reason_code=reasons[0].code if reasons else None, disabled_reasons=reasons,
        ), checks

    def _retry_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许重试。"
        if job.status != "failed":
            return "只有 failed 文档任务允许重试。"
        if job.retry_count >= self.settings.p0_document_job_max_retries:
            return "文档任务重试次数已达上限。"
        if not self._is_retryable_failure(job):
            return f"该失败不可重试: {job.error_code or 'unknown'}"
        return None

    def _cancel_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许取消。"
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            return "只有 pending、queued、running 任务允许取消。"
        return None

    def _archive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "任务已归档。"
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            return "只有 succeeded、failed、canceled 终态任务允许归档。"
        return None

    def _unarchive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is None:
            return "任务未归档。"
        return None

    def _clone_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if not self._is_visible(job, user):
            return "无权限访问该文档任务。"
        try:
            self._get_source_file_for_clone(job)
        except ApiError as exc:
            return exc.message
        return None

    def _delete_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if user.role != "admin":
            return "只有 admin 可以删除文档任务。"
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.status not in DOCUMENT_JOB_DELETE_TERMINAL_STATUSES:
            return "只有终态任务允许删除；处理中任务请先取消。"
        if job.delivery_status == "published":
            return "已发布任务不能删除，仅允许更新归档元数据。"
        return None

    def _build_request_snapshot(
        self,
        source_file: DocumentFileRecord,
        *,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str,
        term_version_id: str | None,
        debug_full_text_enabled: bool,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        resource_snapshot: dict | None = None,
    ) -> dict:
        return {
            "source_file": {
                "id": source_file.id,
                "object_key": source_file.object_key,
                "original_filename": source_file.original_filename,
                "mime_type": source_file.mime_type,
                "size_bytes": source_file.size_bytes,
                "checksum_sha256": source_file.checksum_sha256,
            },
            "mode": mode,
            "translation_mode": translation_mode_for_document_job_mode(mode),
            "document_language": document_language,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_assets": {
                "term_rule_set_id": self._normalize_optional_text(term_rule_set_id),
                "term_rule_set_version": self._normalize_optional_text(term_rule_set_version),
                "translation_term_set_id": self._normalize_optional_text(translation_term_set_id),
                "translation_term_version": self._normalize_optional_text(translation_term_version),
            },
            "translation_profile": {
                "translation_profile_id": self._normalize_optional_text(translation_profile_id),
                "translation_profile_version": self._normalize_optional_text(translation_profile_version),
            },
            "resources": resource_snapshot,
            "debug_full_text_enabled": debug_full_text_enabled,
            "word_preview": self.settings.word_preview_policy().model_dump(mode="json"),
            "page_quality": self.settings.page_quality_policy().model_dump(mode="json"),
        }

    def _resolve_clone_config(
        self,
        source_job: DocumentJobRecord,
        source_file: DocumentFileRecord,
        *,
        new_job_id: str,
        config_strategy: str,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        debug_full_text: bool | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if config_strategy == "keep_source_snapshot":
            source_assets = self._read_snapshot_record(source_job.request_snapshot, "term_assets")
            source_profile = self._read_snapshot_record(source_job.request_snapshot, "translation_profile")
            resolved_debug = self._resolve_debug_full_text_enabled(
                source_job.mode,
                source_job.debug_full_text_enabled if debug_full_text is None else debug_full_text,
            )
            request_snapshot = self._build_request_snapshot(
                source_file,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=source_job.template_version_id,
                term_version_id=source_job.term_version_id,
                debug_full_text_enabled=resolved_debug,
                term_rule_set_id=self._read_snapshot_string(source_assets, "term_rule_set_id"),
                term_rule_set_version=self._read_snapshot_string(source_assets, "term_rule_set_version"),
                translation_term_set_id=self._read_snapshot_string(source_assets, "translation_term_set_id"),
                translation_term_version=self._read_snapshot_string(source_assets, "translation_term_version"),
                translation_profile_id=self._read_snapshot_string(source_profile, "translation_profile_id"),
                translation_profile_version=self._read_snapshot_string(source_profile, "translation_profile_version"),
                resource_snapshot=self._read_snapshot_record(source_job.request_snapshot, "resources"),
            )
            if "word_preview" in source_job.request_snapshot:
                request_snapshot["word_preview"] = source_job.request_snapshot["word_preview"]
            else:
                request_snapshot.pop("word_preview", None)
            if "page_quality" in source_job.request_snapshot:
                request_snapshot["page_quality"] = source_job.request_snapshot["page_quality"]
            else:
                request_snapshot.pop("page_quality", None)
            request_snapshot["clone"] = self._build_clone_snapshot(source_job, config_strategy, reason)
            return {
                "template_version_id": source_job.template_version_id,
                "term_version_id": source_job.term_version_id,
                "debug_full_text_enabled": resolved_debug,
                "request_snapshot": request_snapshot,
            }

        selected_template_version_id = template_version_id if config_strategy == "select_published_versions" else None
        selected_term_version_id = term_version_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_id = term_rule_set_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_version = term_rule_set_version if config_strategy == "select_published_versions" else None
        selected_translation_term_set_id = translation_term_set_id if config_strategy == "select_published_versions" else None
        selected_translation_term_version = translation_term_version if config_strategy == "select_published_versions" else None
        selected_translation_profile_id = translation_profile_id if config_strategy == "select_published_versions" else None
        selected_translation_profile_version = translation_profile_version if config_strategy == "select_published_versions" else None
        resolved_template_version_id = self._resolve_template_version_id(selected_template_version_id)
        resolved_term_version_id = self._resolve_term_version_id(
            source_job.mode,
            self._legacy_translation_term_version_id(
                source_job.mode,
                selected_term_version_id,
                selected_translation_term_version,
            ),
        )
        resolved_debug = self._resolve_debug_full_text_enabled(source_job.mode, bool(debug_full_text))
        request_snapshot = self._build_request_snapshot(
            source_file,
            mode=source_job.mode,
            document_language=document_language,
            template_version_id=resolved_template_version_id,
            term_version_id=resolved_term_version_id,
            debug_full_text_enabled=resolved_debug,
            term_rule_set_id=selected_term_rule_set_id,
            term_rule_set_version=selected_term_rule_set_version,
            translation_term_set_id=selected_translation_term_set_id,
            translation_term_version=selected_translation_term_version,
            translation_profile_id=selected_translation_profile_id,
            translation_profile_version=selected_translation_profile_version,
            resource_snapshot=self._build_resource_snapshot(
                job_id=new_job_id,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=resolved_template_version_id if self._normalize_optional_text(selected_template_version_id) else None,
                term_rule_set_id=selected_term_rule_set_id,
                term_rule_set_version=selected_term_rule_set_version,
                translation_term_set_id=selected_translation_term_set_id,
                translation_term_version=selected_translation_term_version,
                translation_profile_id=selected_translation_profile_id,
                translation_profile_version=selected_translation_profile_version,
            ),
        )
        request_snapshot["clone"] = self._build_clone_snapshot(source_job, config_strategy, reason)
        return {
            "template_version_id": resolved_template_version_id,
            "term_version_id": resolved_term_version_id,
            "debug_full_text_enabled": resolved_debug,
            "request_snapshot": request_snapshot,
        }

    def _build_clone_snapshot(self, source_job: DocumentJobRecord, config_strategy: str, reason: str | None) -> dict[str, Any]:
        return {
            "source_job_id": source_job.id,
            "config_strategy": config_strategy,
            "reason": self._normalize_optional_text(reason),
            "source_status": source_job.status,
            "source_stage": source_job.stage,
            "source_template_version_id": source_job.template_version_id,
            "source_term_version_id": source_job.term_version_id,
        }

    def _read_snapshot_record(self, snapshot: dict, key: str) -> dict[str, Any] | None:
        value = snapshot.get(key)
        return value if isinstance(value, dict) else None

    def _read_snapshot_string(self, snapshot: dict[str, Any] | None, key: str) -> str | None:
        if snapshot is None:
            return None
        value = snapshot.get(key)
        return value if isinstance(value, str) else None

    def _build_retry_request_snapshot(
        self,
        job: DocumentJobRecord,
        *,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict | None:
        has_selection = any(
            self._normalize_optional_text(value)
            for value in (term_rule_set_id, term_rule_set_version, translation_term_set_id, translation_term_version)
        )
        if not use_latest_term_assets and not has_selection:
            return None
        snapshot = dict(job.request_snapshot)
        resource_snapshot = self._build_resource_snapshot(
            job_id=job.id,
            mode=job.mode,
            document_language=job.document_language,
            template_version_id=None,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=None if use_latest_term_assets else term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=None if use_latest_term_assets else translation_term_version,
            translation_profile_id=None,
            translation_profile_version=None,
        )
        resource_snapshot = self._preserve_retry_template_and_profile(job.request_snapshot, resource_snapshot)
        snapshot["term_assets"] = {
            "use_latest_term_assets": use_latest_term_assets,
            "term_rule_set_id": self._normalize_optional_text(term_rule_set_id),
            "term_rule_set_version": self._normalize_optional_text(term_rule_set_version),
            "translation_term_set_id": self._normalize_optional_text(translation_term_set_id),
            "translation_term_version": self._normalize_optional_text(translation_term_version),
        }
        snapshot["resources"] = resource_snapshot
        return snapshot

    def _build_resource_snapshot(
        self,
        *,
        job_id: str,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        term_rule_department_id: str | None = None,
        allow_draft_template: bool = False,
    ) -> dict | None:
        if self.job_resource_snapshot_service is None:
            return None
        has_explicit_selection = any(
            self._normalize_optional_text(value)
            for value in (
                template_version_id,
                term_rule_set_id,
                term_rule_set_version,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        template_id, template_version = self._split_template_version_id(template_version_id)
        options = ConversionOptions(
            template_id=template_id,
            template_version=template_version,
            term_rule_set_id=self._normalize_optional_text(term_rule_set_id),
            term_rule_set_version=self._normalize_optional_text(term_rule_set_version),
            term_rule_department_id=self._normalize_optional_text(term_rule_department_id),
            translation_term_set_id=self._normalize_optional_text(translation_term_set_id),
            translation_term_version=self._normalize_optional_text(translation_term_version),
            translation_profile_id=self._normalize_optional_text(translation_profile_id),
            translation_profile_version=self._normalize_optional_text(translation_profile_version),
            translation_mode=translation_mode_for_document_job_mode(mode),
            document_language=document_language,
        )
        try:
            snapshot = self.job_resource_snapshot_service.build_snapshot(
                options=options,
                source_kind="source_pdf",
                job_id=job_id,
                allow_draft_template=allow_draft_template,
            )
        except JobResourceSnapshotError as exc:
            if not has_explicit_selection:
                return None
            raise ApiError(exc.status_code, exc.code, exc.message) from exc
        if snapshot is None:
            return None
        return snapshot.model_dump(mode="json")

    def _ensure_resource_selection_allowed(
        self,
        *,
        user: AuthenticatedUser,
        use_latest_term_assets: bool = False,
        template_version_id: str | None = None,
        term_version_id: str | None = None,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
    ) -> None:
        if user.role == "admin":
            return
        selected: list[str] = []
        for name, value in {
            "use_latest_term_assets": use_latest_term_assets,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_rule_set_id": term_rule_set_id,
            "term_rule_set_version": term_rule_set_version,
            "translation_term_set_id": translation_term_set_id,
            "translation_term_version": translation_term_version,
            "translation_profile_id": translation_profile_id,
            "translation_profile_version": translation_profile_version,
        }.items():
            if isinstance(value, bool):
                if value:
                    selected.append(name)
                continue
            if self._normalize_optional_text(value):
                selected.append(name)
        if selected:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                f"operator 不能选择任务资源版本: {', '.join(selected)}。",
            )

    def _split_template_version_id(self, template_version_id: str | None) -> tuple[str | None, str | None]:
        normalized = self._normalize_optional_text(template_version_id)
        if normalized is None:
            return None, None
        template_id, separator, version = normalized.partition("@")
        if not separator:
            return normalized, None
        return template_id or None, version or None

    def _preserve_retry_template_and_profile(self, request_snapshot: dict, resource_snapshot: dict | None) -> dict | None:
        if resource_snapshot is None:
            return None
        previous_resources = request_snapshot.get("resources")
        if not isinstance(previous_resources, dict):
            return resource_snapshot
        preserved = dict(resource_snapshot)
        if isinstance(previous_resources.get("template"), dict):
            preserved["template"] = previous_resources["template"]
        if isinstance(previous_resources.get("translation_profile"), dict):
            preserved["translation_profile"] = previous_resources["translation_profile"]
            for key in (
                "translation_prompt_id",
                "translation_prompt_content_hash",
            ):
                if key in previous_resources:
                    preserved[key] = previous_resources[key]
                else:
                    preserved.pop(key, None)
        return preserved

    def _snapshot_resource_id(self, request_snapshot: dict, key: str) -> str | None:
        resources = request_snapshot.get("resources")
        if not isinstance(resources, dict):
            return None
        resource = resources.get(key)
        if not isinstance(resource, dict):
            return None
        raw = resource.get("resource_id") or resource.get("set_id")
        return raw if isinstance(raw, str) else None

    def _snapshot_resource_version(self, request_snapshot: dict, key: str) -> str | None:
        resources = request_snapshot.get("resources")
        if not isinstance(resources, dict):
            return None
        resource = resources.get(key)
        if not isinstance(resource, dict):
            return None
        raw = resource.get("version")
        return raw if isinstance(raw, str) else None

    def _resolve_document_job_mode(
        self,
        *,
        mode: DocumentJobMode | None,
        translation_mode: TranslationMode | None,
    ) -> DocumentJobMode:
        if translation_mode is not None:
            try:
                translation_mode = normalize_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if mode is None and translation_mode is None:
            return "direct_pdf_to_word"
        if mode is None:
            try:
                return document_job_mode_for_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        try:
            resolved_translation_mode = translation_mode_for_document_job_mode(mode)
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if translation_mode is not None and translation_mode != resolved_translation_mode:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"translation_mode 与 mode 不一致: translation_mode={translation_mode} mode={mode}。",
            )
        return mode

    def _ensure_direct_translation_selection_absent(
        self,
        mode: DocumentJobMode,
        *,
        term_version_id: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        debug_full_text: bool = False,
    ) -> None:
        """只校验新写入意图；历史 direct 快照的惰性字段不参与资源选择。"""

        if is_translation_document_job_mode(mode):
            return
        has_translation_selection = any(
            self._normalize_optional_text(value)
            for value in (
                term_version_id,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        if has_translation_selection or debug_full_text:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "原文转换（direct）不能绑定翻译资源或开启翻译全文调试。",
            )

    def _ensure_document_language_allowed(self, mode: DocumentJobMode, document_language: str) -> None:
        spec = spec_for_document_job_mode(mode)
        if not spec.is_translation:
            return
        allowed = {"auto", spec.default_document_language}
        if document_language not in allowed:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                (
                    f"{spec.translation_mode} 只支持 "
                    f"document_language=auto 或 {spec.default_document_language}。"
                ),
            )

    def _legacy_translation_term_version_id(
        self,
        mode: DocumentJobMode,
        term_version_id: str | None,
        translation_term_version: str | None,
    ) -> str | None:
        if not is_translation_document_job_mode(mode):
            return term_version_id
        normalized_translation_term_version = self._normalize_optional_text(translation_term_version)
        if normalized_translation_term_version is None:
            return term_version_id
        if "@" in normalized_translation_term_version:
            return normalized_translation_term_version
        spec = spec_for_document_job_mode(mode)
        return f"{spec.language_pair}@{normalized_translation_term_version}"

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _resolve_template_version_id(self, template_version_id: str | None, *, allow_draft: bool = False) -> str:
        if self.template_read_service is None:
            return template_version_id or self.settings.default_template_id
        try:
            return self.template_read_service.resolve_template_version(
                template_version_id,
                allow_draft=allow_draft,
            ).template_version_id
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc

    def _resolve_term_version_id(self, mode: DocumentJobMode, term_version_id: str | None) -> str | None:
        """direct 在调用术语服务前返回，历史字段不能触发翻译资源加载。"""

        language_pair = spec_for_document_job_mode(mode).language_pair
        if language_pair is None:
            return None
        if self.term_version_service is None:
            return term_version_id
        try:
            snapshot = self.term_version_service.resolve_for_job(term_version_id, language_pair=language_pair)
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        return snapshot.term_version_id if snapshot is not None else None

    def _resolve_debug_full_text_enabled(self, mode: DocumentJobMode, debug_full_text: bool) -> bool:
        if not debug_full_text:
            return False
        if not is_translation_document_job_mode(mode):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "debug_full_text 仅支持翻译任务。")
        if not self.settings.translation_debug_archive_enabled:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "TRANSLATION_DEBUG_ARCHIVE_ENABLED 未开启，不能保存翻译全文调试归档。",
            )
        return True

    def _ensure_debug_full_text_allowed(self, user: AuthenticatedUser, debug_full_text: bool) -> None:
        if debug_full_text and user.role != "admin":
            raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "只有 admin 可以开启翻译全文调试归档。")
