from __future__ import annotations

# app/domains/document_jobs/use_cases/read_model.py: 任务读视图与可用动作（含禁用原因）的共享 owner；列表、详情与命令前置检查共用同一份规则。

from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.new_generation import NewGenerationConflict, new_generation_eligibility_reason
from app.domains.document_jobs.preview import _is_preview_storage_error
from app.domains.document_jobs.publication import PublicationConflict
from app.domains.document_jobs.publication_evidence import prepare_publication_evidence
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import effective_review_job
from app.domains.document_jobs.schemas import (
    DocumentJobActionDisabledReasonResponse,
    DocumentJobAvailableActionResponse,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import (
    DOCUMENT_JOB_DELETE_TERMINAL_STATUSES,
    DocumentJobDownloadPolicy,
    UNREAD_RESULT,
)
from app.domains.document_jobs.workflow import (
    ARCHIVABLE_DOCUMENT_JOB_STATUSES,
    CANCELABLE_DOCUMENT_JOB_STATUSES,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileReaderProtocol, DocumentFileRepositoryProtocol
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.resources.models import utc_now
from app.domains.translation.modes import (
    is_translation_document_job_mode,
    translation_mode_for_document_job_mode,
)
from app.services.auth.models import AuthenticatedUser


class DocumentJobReadModel:
    """任务读视图与可用动作（含禁用原因）的共享 owner；列表、详情与命令前置检查共用同一份规则。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        job_resource_snapshot_service: Any | None,
        file_upload_service: Any | None,
        access: DocumentJobAccess,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.file_upload_service = file_upload_service
        self.access = access

    def new_generation_source_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
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

    @staticmethod
    def new_generation_resource_snapshot(job: DocumentJobRecord) -> JobResourceSnapshot:
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
        observed_result: DocumentFileRecord | None | object = UNREAD_RESULT,
        as_of: datetime | None = None,
        check_publication_evidence: bool = True,
        observed_result_view: tuple[DocumentJobRecord, DocumentJobAvailableActionResponse] | None = None,
    ) -> tuple[DocumentJobRecord, dict[str, DocumentJobAvailableActionResponse]]:
        """保留公共二元组合同；列表可仅判断发布状态，其他调用默认核验证据。"""
        view, actions, _ = self.build_job_read_observation(job, user=user, observed_result=observed_result,
            as_of=as_of, check_publication_evidence=check_publication_evidence,
            observed_result_view=observed_result_view)
        return view, actions

    def build_job_read_observation(
        self, job: DocumentJobRecord, *, user: AuthenticatedUser,
        observed_result: DocumentFileRecord | None | object = UNREAD_RESULT,
        as_of: datetime | None = None,
        check_publication_evidence: bool = True,
        observed_result_view: tuple[DocumentJobRecord, DocumentJobAvailableActionResponse] | None = None,
    ):
        """同次来源及显式证据核验策略同时产出状态、动作及前置检查。"""


        # 异常列表复用本次分类的主件观察，避免分页后换件或到期使条目与统计分离。
        job, download = (observed_result_view if observed_result_view is not None else
            self.build_result_read_view(job, observed_result=observed_result, as_of=as_of))
        publish, checks = self.build_publish_action(job, user=user, download=download,
            check_publication_evidence=check_publication_evidence)
        actions = {
            "download": download,
            "retry": self.build_retry_action(job),
            "cancel": self.available_action(self.cancel_disabled_reason(job)),
            "archive": self.available_action(self.archive_disabled_reason(job)),
            "unarchive": self.available_action(self.unarchive_disabled_reason(job)),
            "clone": self.available_action(self.clone_disabled_reason(job, user=user)),
            "delete": self.available_action(self.delete_disabled_reason(job, user=user)),
            "publish": publish,
            "new_generation": self.build_new_generation_action(job, user=user),
        }
        if actions["publish"].enabled and job.delivery_status != "published":
            job = job.model_copy(update={"delivery_status": "ready_to_publish"})
        return job, actions, checks

    def build_incident_classification_view(
        self, job: DocumentJobRecord, *, file_reader: DocumentFileReaderProtocol | None = None,
    ) -> tuple[DocumentJobRecord, DocumentJobAvailableActionResponse, DocumentJobAvailableActionResponse]:
        """分类复用完整读视图的主件门控和重试判断，不构建无关动作。"""
        job, download = self.build_result_read_view(job, file_reader=file_reader)
        return job, self.build_retry_action(job), download

    def build_retry_action(self, job: DocumentJobRecord) -> DocumentJobAvailableActionResponse:
        reason = self.retry_disabled_reason(job)
        return self.available_action(reason, retryable=reason is None)

    def build_new_generation_action(self, job: DocumentJobRecord, *, user: AuthenticatedUser):
        """后端给出可执行资格；POST 仍独立认证实物并在接受锁内重核。"""
        reason = ("admin_required" if user.role != "admin" or {"admin_token", "jobs_token"}.intersection(user.token_scopes)
            else new_generation_eligibility_reason(job, max_retries=self.settings.p0_document_job_max_retries))
        if reason is None:
            try:
                self.new_generation_resource_snapshot(job)
            except ValueError:
                reason = "new_generation_resources_unavailable"
            if self.job_resource_snapshot_service is None:
                reason = "new_generation_resources_unavailable"
        if reason is None:
            try:
                self.new_generation_source_file(job)
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
        return self.download_policy_for_view(view, file)

    def download_policy_for_view(
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

    def is_retryable_failure(self, job: DocumentJobRecord) -> bool:
        if job.error_code in {"document_job_invalid_input"}:
            return False
        return True

    def available_action(
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

    def build_result_read_view(
        self, job: DocumentJobRecord, *, observed_result: DocumentFileRecord | None | object = UNREAD_RESULT,
        as_of: datetime | None = None,
        file_reader: DocumentFileReaderProtocol | None = None,
    ) -> tuple[DocumentJobRecord, DocumentJobAvailableActionResponse]:
        """同一主件观察拥有有效复核和下载判定，期间不再次读取主件。"""

        file = None
        try:
            file = self.access.get_completed_result_file(job, observed_result=observed_result, file_reader=file_reader)
            self.access.ensure_file_not_expired(file, as_of=as_of, file_reader=file_reader)
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
        policy = self.download_policy_for_view(view, file)
        return view, DocumentJobAvailableActionResponse(
            enabled=True, classification=policy.classification,
            warning_code=policy.warning_code, warning_message=policy.warning_message,
        )

    def build_publish_action(self, job: DocumentJobRecord, *, user: AuthenticatedUser,
        download: DocumentJobAvailableActionResponse,
        check_publication_evidence: bool = True,
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
        if not reasons and check_publication_evidence:
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

    def retry_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许重试。"
        if job.status != "failed":
            return "只有 failed 文档任务允许重试。"
        if job.retry_count >= self.settings.p0_document_job_max_retries:
            return "文档任务重试次数已达上限。"
        if not self.is_retryable_failure(job):
            return f"该失败不可重试: {job.error_code or 'unknown'}"
        return None

    def cancel_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许取消。"
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            return "只有 pending、queued、running 任务允许取消。"
        return None

    def archive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "任务已归档。"
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            return "只有 succeeded、failed、canceled 终态任务允许归档。"
        return None

    def unarchive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is None:
            return "任务未归档。"
        return None

    def clone_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if not self.access.is_visible(job, user):
            return "无权限访问该文档任务。"
        try:
            self.access.get_source_file_for_clone(job)
        except ApiError as exc:
            return exc.message
        return None

    def delete_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if user.role != "admin":
            return "只有 admin 可以删除文档任务。"
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.status not in DOCUMENT_JOB_DELETE_TERMINAL_STATUSES:
            return "只有终态任务允许删除；处理中任务请先取消。"
        if job.delivery_status == "published":
            return "已发布任务不能删除，仅允许更新归档元数据。"
        return None
