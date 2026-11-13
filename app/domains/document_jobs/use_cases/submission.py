from __future__ import annotations

# app/domains/document_jobs/use_cases/submission.py: 用例：创建、克隆、重试任务及重试 Word 预览。

from datetime import timedelta
from typing import Any
from uuid import uuid4


from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.document_jobs.base_quality import fresh_quality_summary
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.domains.document_jobs.models import DocumentJobMode, DocumentJobRecord
from app.domains.document_jobs.preview_state import PreviewRetryResult
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.dispatcher import DocumentJobDispatcher
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.document_jobs.use_cases.request_snapshot import DocumentJobRequestSnapshots
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.domains.translation.modes import TranslationMode, translation_mode_for_document_job_mode
from app.services.auth.models import AuthenticatedUser


class DocumentJobSubmission:
    """用例：创建、克隆、重试任务及重试 Word 预览。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        task_queue: DocumentJobTaskQueueProtocol | None,
        word_preview_service: Any | None,
        events: DocumentJobEventWriter,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
        dispatcher: DocumentJobDispatcher,
        request_snapshot: DocumentJobRequestSnapshots,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.word_preview_service = word_preview_service
        self.events = events
        self.access = access
        self.read_model = read_model
        self.dispatcher = dispatcher
        self.request_snapshot = request_snapshot

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
        mode = self.request_snapshot.resolve_document_job_mode(mode=mode, translation_mode=translation_mode)
        self.request_snapshot.ensure_document_language_allowed(mode, document_language)
        self.request_snapshot.ensure_debug_full_text_allowed(user, debug_full_text)
        self.request_snapshot.ensure_direct_translation_selection_absent(
            mode,
            term_version_id=term_version_id,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=debug_full_text,
        )
        normalized_template_version_id = self.request_snapshot.resolve_template_version_id(
            template_version_id,
            allow_draft=user.role == "admin",
        )
        normalized_term_version_id = self.request_snapshot.resolve_term_version_id(
            mode,
            self.request_snapshot.legacy_translation_term_version_id(mode, term_version_id, translation_term_version),
        )
        debug_full_text_enabled = self.request_snapshot.resolve_debug_full_text_enabled(mode, debug_full_text)
        now = utc_now()
        job_id = f"docjob_{uuid4().hex[:12]}"
        request_snapshot = self.request_snapshot.build_request_snapshot(
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
            resource_snapshot=self.request_snapshot.build_resource_snapshot(
                job_id=job_id,
                mode=mode,
                document_language=document_language,
                template_version_id=normalized_template_version_id,
                template_selection_explicit=bool(self.access.normalize_optional_text(template_version_id)),
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
        self.events.record_event(
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
        return self.dispatcher.enqueue_created_job(job, trace_id=trace_id)

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

        job = self.access.get_authorized_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        self.request_snapshot.ensure_resource_selection_allowed(
            user=user,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if job.archived_at is not None:
            raise ApplicationError("conflict", "已归档文档任务不允许重试。")
        self._ensure_retry_allowed(job)
        self.request_snapshot.ensure_direct_translation_selection_absent(
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
            raise ApplicationError("conflict", "任务状态或重试代数已变化，无法重试。")
        self.events.record_event(
            retried,
            event_type="retry_requested",
            stage=retried.stage,
            level="info",
            message="文档任务已请求重试。",
            payload={
                "retry_count": retry_count,
                "reason": self.access.normalize_optional_text(reason),
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
            failed = self.dispatcher.mark_enqueue_failed(retried, str(exc), trace_id=trace_id)
            raise ApplicationError(
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or retried

    def retry_word_preview(self, job_id: str, *, user: AuthenticatedUser, reason: str, request_id: str,
                           trace_id: str | None = None) -> PreviewRetryResult:
        """内部应用入口；沿用 owner/Admin 范围，不增加 HTTP 重试路由。"""
        job = self.access.get_job(job_id, user=user)
        if self.word_preview_service is None:
            raise ApplicationError("service_unavailable", "Word 预览应用服务未配置。")
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

        source_job = self.access.get_authorized_job(job_id, user=user)
        self.access.ensure_job_not_deleted(source_job)
        source_file = self.access.get_source_file_for_clone(source_job)
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
            self.access.normalize_optional_text(value) for value in explicit_values.values()
        ):
            raise ApplicationError("invalid_request", "只有 select_published_versions 支持显式资源版本。")
        if config_strategy == "select_published_versions":
            self.request_snapshot.ensure_resource_selection_allowed(user=user, **explicit_values)
        elif config_strategy not in {"keep_source_snapshot", "use_current_defaults"}:
            raise ApplicationError("invalid_request", "config_strategy 非法。")
        requested_debug_full_text = bool(debug_full_text)
        inherited_debug_full_text = (
            config_strategy == "keep_source_snapshot"
            and debug_full_text is None
            and source_job.debug_full_text_enabled
        )
        self.request_snapshot.ensure_debug_full_text_allowed(user, requested_debug_full_text or inherited_debug_full_text)
        self.request_snapshot.ensure_direct_translation_selection_absent(
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
        self.request_snapshot.ensure_document_language_allowed(source_job.mode, normalized_document_language)
        clone_config = self.request_snapshot.resolve_clone_config(
            source_job,
            source_file,
            user=user,
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
        self.events.record_event(
            cloned,
            event_type="job_cloned",
            stage="uploaded",
            level="info",
            message="文档任务已重新发起为新任务。",
            payload={
                "source_job_id": source_job.id,
                "source_file_id": source_file.id,
                "config_strategy": config_strategy,
                "reason": self.access.normalize_optional_text(reason),
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return cloned
        return self.dispatcher.enqueue_created_job(cloned, trace_id=trace_id)

    def _ensure_retry_allowed(self, job: DocumentJobRecord) -> None:
        reason = self.read_model.retry_disabled_reason(job)
        if reason is not None:
            raise ApplicationError("conflict", reason)

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
        next_request_snapshot = self.request_snapshot.build_retry_request_snapshot(
            job,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if next_request_snapshot is not None:
            patch["request_snapshot"] = next_request_snapshot
            next_template_version_id = next_request_snapshot["template_version_id"]
            if next_template_version_id != job.template_version_id:
                patch["template_version_id"] = next_template_version_id
            selected_term_version = self.request_snapshot.legacy_translation_term_version_id(
                job.mode,
                None if use_latest_term_assets else job.term_version_id,
                None if use_latest_term_assets else translation_term_version,
            )
            patch["term_version_id"] = self.request_snapshot.resolve_term_version_id(job.mode, selected_term_version)
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

    def _get_source_file_for_create(self, file_id: str, user: AuthenticatedUser) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(file_id)
        if source_file is None:
            raise ApplicationError("not_found", f"源文件不存在: {file_id}")
        if source_file.file_type != "source_pdf":
            raise ApplicationError("invalid_request", "document_job 只能使用 source_pdf 文件创建。")
        if source_file.status != "uploaded":
            raise ApplicationError("conflict", "源文件尚未完成上传。")
        if source_file.job_id is not None:
            raise ApplicationError("conflict", "源文件已绑定其他任务。")
        if source_file.tenant_id != user.tenant_id or source_file.company_id != user.company_id:
            raise ApplicationError("forbidden", "无权限使用该源文件。")
        if user.role != "admin" and source_file.created_by != user.id:
            raise ApplicationError("forbidden", "operator 只能使用自己上传的源文件。")
        return source_file
