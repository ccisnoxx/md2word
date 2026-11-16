from __future__ import annotations

# app/domains/document_jobs/use_cases/review_writer.py: 质量评审记录提交；质量评审与翻译 QA 共用。

import hashlib
from typing import Any
from uuid import uuid4


from app.core.errors import ApplicationError
from app.domains.document_jobs.delivery_state import translation_qa_projection
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import is_preview_storage_error
from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import (
    ReviewBinding,
    ReviewExpectedSource,
    ReviewIssueType,
    ReviewStatus,
    ReviewSubmission,
    ReviewSubmissionConflict,
    observed_review_source,
    receipt_identity,
    receipt_matches_file,
    table_semantics_approval_conflict,
)
from app.domains.document_jobs.table_evidence import recheck_verified_report, verify_report
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.common import ReviewCommit
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.result_registration import review_source_descriptor
from app.domains.resources.models import utc_now
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.auth.models import AuthenticatedUser
from app.services.renderer.render_event_summary import is_valid_table_rendering_evidence
from app.services.tables.evidence import TableEvidenceError


class DocumentReviewWriter:
    """质量评审记录提交；质量评审与翻译 QA 共用。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
        events: DocumentJobEventWriter,
        access: DocumentJobAccess,
    ) -> None:
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service
        self.events = events
        self.access = access

    def submit_document_review(
        self, job: DocumentJobRecord, *, user: AuthenticatedUser, review_status: ReviewStatus,
        issue_type: ReviewIssueType | None, note: str | None, trace_id: str | None,
        expected_source: ReviewExpectedSource | None = None,
        acknowledged_table_semantics_report_sha256: str | None = None,
    ) -> ReviewCommit:
        def conflict(message, reason):
            return ApplicationError("conflict", message,
                reason_code=reason if expected_source is not None else None)

        if job.deleted_at is not None or job.delivery_status == "published":
            raise conflict("已删除或已发布任务不能修改复核。", "review_state_conflict")
        result_file, actual_hash = None, None
        if expected_source is not None:
            result_file = self.access.review_api_file(job, conflict_reason="review_result_integrity_conflict")
            if observed_review_source(job, result_file) != expected_source:
                raise conflict("复核来源已变化，请重新读取。", "review_source_changed")
        if review_status == "approved":
            if effective_quality_status(job) == "blocked":
                raise conflict("质量阻断的任务不能批准复核。", "review_quality_blocked")
            try:
                if expected_source is None:
                    result_file = self.access.get_downloadable_completed_result_file(job)
                else:
                    result_file = self.access.get_completed_result_file(job, observed_result=result_file)
                    self.access.ensure_file_not_expired(result_file)
            except ApplicationError as exc:
                if expected_source is not None:
                    reason = ("review_result_integrity_conflict" if exc.reason_code == "result_file_mismatch"
                        else "review_result_unavailable")
                    raise conflict("当前主 DOCX 不可用，不能批准复核。", reason) from None
                if exc.code != "not_found":
                    raise
                raise ApplicationError("conflict", "当前主 DOCX 未登记，不能批准复核。") from exc
            if "table_rendering" in result_file.metadata:
                rendering = result_file.metadata["table_rendering"]
                if (
                    self.access.file_retry_count(result_file) != job.retry_count
                    or not is_valid_table_rendering_evidence(rendering)
                    or rendering.get("quality_status") not in ("passed", "warning")
                    or rendering["blocking_quality_flags"]
                ):
                    reason = ("review_result_integrity_conflict" if self.access.file_retry_count(result_file) != job.retry_count
                        or not is_valid_table_rendering_evidence(rendering) else "review_quality_blocked")
                    raise conflict("表格质量受阻或渲染证据无效，不能批准。", reason)
            if expected_source is not None and self.file_upload_service is None:
                raise ApplicationError("service_unavailable", "复核文件存储暂不可用。", reason_code="quality_storage_unavailable")
            self.access.ensure_file_reader_available()
            try:
                content = self.file_upload_service.read_file_content(result_file)
            except FileNotFoundError as exc:
                raise conflict("当前主 DOCX 不可用，不能批准复核。", "review_result_unavailable") from exc
            except Exception as exc:
                from app.domains.document_jobs.preview_evidence import is_preview_storage_error
                if expected_source is not None and is_preview_storage_error(exc):
                    raise ApplicationError("service_unavailable", "复核文件存储暂不可用。", reason_code="quality_storage_unavailable") from None
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
            latest = self.access.review_api_file(job, conflict_reason="review_result_integrity_conflict")
            if (observed_review_source(job, latest) != expected_source or
                    latest is not None and review_source_descriptor(latest) != review_source_descriptor(result_file)):
                raise conflict("复核来源已变化，请重新读取。", "review_source_changed")
        now = utc_now()
        binding = ReviewBinding(generation=job.retry_count, result_file_id=job.result_file_id,
            binding_state="verified" if actual_hash else ("no_result" if job.result_file_id is None else "unverified_result"),
            result_sha256=actual_hash, file_review_source_revision=result_file.review_source_revision if result_file else None,
            descriptor=review_source_descriptor(result_file) if result_file else None, receipt_sha256=receipt_identity(job),
            acknowledged_table_semantics_report_sha256=acknowledged_table_semantics_report_sha256)
        if review_status == "approved":
            reason = table_semantics_approval_conflict(job, binding)
            if reason is not None:
                messages = {
                    "table_semantics_confirmation_required": "请对照源 PDF 核对当前报告的疑似数值列归属后，再明确确认。",
                    "table_semantics_confirmation_stale": "数值列归属确认与当前报告不一致，请刷新后核对。",
                    "table_semantics_evidence_invalid": "当前表格证据无效，不能批准复核。",
                }
                raise conflict(messages[reason], reason)
            if acknowledged_table_semantics_report_sha256 is not None:
                try:
                    verified = verify_report(job, result_file, file_repository=self.file_repository,
                        file_service=self.file_upload_service, job_repository=self.job_repository)
                    if verified is None or verified.envelope.report.report_sha256 != acknowledged_table_semantics_report_sha256:
                        raise TableEvidenceError("table_evidence_integrity")
                    recheck_verified_report(verified, file_repository=self.file_repository, job_repository=self.job_repository)
                except (TableEvidenceError, FileNotFoundError):
                    raise conflict("当前表格证据无法验证，请刷新后核对。", "table_semantics_evidence_invalid") from None
                except RuntimeError:
                    raise ApplicationError("service_unavailable", "表格证据存储暂不可用。",
                        reason_code="quality_storage_unavailable") from None
        submission = ReviewSubmission(record_id=f"review_{uuid4().hex}", status=review_status, issue_type=issue_type,
            note=self.access.normalize_optional_text(note), reviewed_by=user.id, reviewed_at=now, reviewer_role=user.role,
            binding=binding, expected_source=expected_source)
        try:
            updated = self.job_repository.update_document_job_review_if_current(job.id, submission=submission)
        except ReviewSubmissionConflict as exc:
            raise conflict("复核提交条件已变化，请重新读取。", exc.reason_code) from None
        if updated is None:
            raise conflict("任务代数、当前主件或复核条件已变化，请刷新后重试。", "review_source_changed")
        effective = self.access.effective_job(updated)
        self.events.record_event(updated, event_type="translation_qa_updated", stage=updated.stage, level="info",
            message="文档复核状态已更新。", payload={
                "observed_review_status": job.review_status, "record_status": submission.status,
                "review_status": effective.review_status, "status": effective.review_status,
                "issue_type": translation_qa_projection(updated)["translation_qa_issue_type"] if is_translation_document_job_mode(job.mode) else issue_type,
                "reviewed_by": user.id, "generation": updated.retry_count, "result_file_id": updated.result_file_id,
                "checksum_sha256": actual_hash, "note_length": len(submission.note or ""),
                "review_record_id": updated.current_review_record_id, "review_sequence": updated.review_sequence,
            }, trace_id=trace_id)
        return ReviewCommit(effective, updated.current_review_record_id, updated.review_sequence)
