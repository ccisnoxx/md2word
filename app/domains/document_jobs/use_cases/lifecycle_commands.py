from __future__ import annotations

# app/domains/document_jobs/use_cases/lifecycle_commands.py: 用例：归档、取消归档、删除预览与删除、取消任务。

import hashlib
import json
from typing import Any


from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import is_preview_storage_error
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import (
    DEFAULT_DOCUMENT_JOB_DELETE_REASON,
    DocumentJobDeletePlan,
    DocumentJobDeletePlanFile,
    SYSTEM_LOGGER,
)
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.document_jobs.workflow import (
    ARCHIVABLE_DOCUMENT_JOB_STATUSES,
    CANCELABLE_DOCUMENT_JOB_STATUSES,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


class DocumentJobLifecycleCommands:
    """用例：归档、取消归档、删除预览与删除、取消任务。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_upload_service: Any | None,
        events: DocumentJobEventWriter,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
    ) -> None:
        self.job_repository = job_repository
        self.file_upload_service = file_upload_service
        self.events = events
        self.access = access
        self.read_model = read_model

    def archive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """归档终态 document_job，仅隐藏列表记录，不删除文件或事件。"""

        job = self.access.get_authorized_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        if job.archived_at is not None:
            return self.access.effective_job(job)
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            raise ApplicationError("conflict", "只有 succeeded、failed、canceled 终态任务允许归档。")
        now = utc_now()
        archived = self.job_repository.update_document_job_lifecycle_if_current(job.id,
            expected_retry_count=job.retry_count, action="archive", actor_id=user.id, occurred_at=now)
        if archived is None:
            raise ApplicationError("conflict", "任务代次或终态已变化，不能归档旧来源。")
        self.events.record_event(
            archived,
            event_type="job_archived",
            stage=archived.stage,
            level="info",
            message="文档任务已归档并从默认列表隐藏。",
            payload={"archived_by": user.id, "status": archived.status},
            trace_id=trace_id,
        )
        return self.access.effective_job(archived)

    def unarchive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """恢复误归档 document_job；只更新归档元数据，不触碰文件或状态。"""

        job = self.access.get_authorized_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        if job.archived_at is None:
            return self.access.effective_job(job)
        now = utc_now()
        restored = self.job_repository.update_document_job(
            job.id,
            archived_at=None,
            archived_by=None,
            updated_at=now,
        )
        self.events.record_event(
            restored,
            event_type="job_unarchived",
            stage=restored.stage,
            level="info",
            message="文档任务已取消归档并恢复到默认列表。",
            payload={"restored_by": user.id, "status": restored.status},
            trace_id=trace_id,
        )
        return self.access.effective_job(restored)

    def preview_delete_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> DocumentJobDeletePlan:
        """构建 Admin-only 任务删除计划；不修改任务、文件、事件或审计。"""

        job = self.access.get_authorized_job(job_id, user=user)
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

        job = self.access.get_authorized_job(job_id, user=user)
        self._ensure_delete_allowed(job, user=user)
        normalized_reason = self.access.normalize_optional_text(reason) or DEFAULT_DOCUMENT_JOB_DELETE_REASON
        if confirmation is not None:
            expected_confirmation = self._delete_confirmation_phrase(job)
            if confirmation != expected_confirmation:
                raise ApplicationError(
                    "invalid_request",
                    f"confirmation 必须为 {expected_confirmation}。",
                )
        preview = self._build_delete_plan(job, action_mode="delete_preview")
        if preview.preview_hash != preview_hash:
            raise ApplicationError("conflict", "删除预览已过期，请重新预览后再执行。")

        delete_file_ids = [item.file_id for item in preview.files if item.action == "delete"]
        if delete_file_ids and self.file_upload_service is None:
            raise ApplicationError("service_unavailable", "文件清理服务不可用，无法删除任务文件。")
        # deleted_at 是持久生命周期预留；确认赢得本代后，才允许取得文件删除 claim。
        now = utc_now()
        try:
            deleted = self.job_repository.update_document_job_lifecycle_if_current(job.id,
                expected_retry_count=job.retry_count, action="delete", actor_id=user.id, occurred_at=now,
                delete_reason=normalized_reason)
        except Exception as error:
            if not is_preview_storage_error(error):
                raise
            raise ApplicationError("service_unavailable", "任务删除预留暂不可确认，请先核对原任务状态。",
                reason_code="document_job_deletion_unknown") from None
        if deleted is None:
            raise ApplicationError("conflict", "任务代次、发布或删除状态已变化，未执行文件删除。")
        executed_files = preview.files
        if delete_file_ids:
            try:
                physical_delete = self.file_upload_service.execute_document_job_physical_delete(delete_file_ids)
            except Exception as error:
                SYSTEM_LOGGER.error("任务删除预留已提交，文件清理结果未确认 job_id=%s generation=%s trace_id=%s exception_type=%s",
                    deleted.id, deleted.retry_count, trace_id, type(error).__name__)
                raise
            physical_items = {item.file_id: item for item in physical_delete.items}
            executed_files = [
                self._delete_plan_file_from_physical_item(physical_items[item.file_id], action="delete")
                if item.file_id in physical_items
                else item
                for item in preview.files
            ]

        self.events.record_event(
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
            self.access.effective_job(deleted),
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

        job = self.access.get_authorized_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        if job.archived_at is not None:
            raise ApplicationError("conflict", "已归档文档任务不允许取消。")
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            raise ApplicationError("conflict", "只有 pending、queued、running 任务允许取消。")
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
            raise ApplicationError(
                "conflict",
                f"任务状态已变化，无法取消: status={latest.status} stage={latest.stage}",
            )
        self.events.record_event(
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

    def _ensure_delete_allowed(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> None:
        reason = self.read_model.delete_disabled_reason(job, user=user)
        if reason is not None:
            if user.role != "admin":
                raise ApplicationError("forbidden", reason)
            raise ApplicationError("conflict", reason)

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
        return [self._build_delete_plan_file(job, file) for file in self.access.list_files_for_job(job)]

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
            if self.access.file_belongs_to_job(other_job, file):
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
