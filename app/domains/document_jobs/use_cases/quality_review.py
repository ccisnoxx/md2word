from __future__ import annotations

# app/domains/document_jobs/use_cases/quality_review.py: 用例：质量/评审/预览读取与评审提交、表格证据。

from typing import Any

from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.review import (
    ReviewExpectedSource,
    ReviewIssueType,
    ReviewRecord,
    ReviewStatus,
    digest,
    review_validity,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.queries import DocumentJobQueries
from app.domains.document_jobs.use_cases.read_model import DocumentJobReadModel
from app.domains.document_jobs.use_cases.review_writer import DocumentReviewWriter
from app.domains.document_jobs.use_cases.table_references import DocumentJobTableReferences
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.result_registration import file_lifecycle_unavailable
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser


class DocumentJobQualityReview:
    """用例：质量/评审/预览读取与评审提交、表格证据。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
        access: DocumentJobAccess,
        read_model: DocumentJobReadModel,
        review_writer: DocumentReviewWriter,
        queries: DocumentJobQueries,
        table_references: DocumentJobTableReferences,
    ) -> None:
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service
        self.access = access
        self.read_model = read_model
        self.review_writer = review_writer
        # 仅供复核内容 reader（review_content）复用同一快照：翻译批次快照与已认证 IR 的表格参考投影。
        self.queries = queries
        self.table_references = table_references

    def review_api_job(self, job_id, user):
        """只在新接口的授权入口附固定原因，不改变旧端点错误。"""
        try:
            return self.access.get_authorized_job(job_id, user=user)
        except ApplicationError as exc:
            reason = {"forbidden": "review_access_denied", "role_forbidden": "review_access_denied",
                      "not_found": "document_job_not_found"}.get(exc.code)
            if reason is None:
                raise
            raise ApplicationError(exc.code, exc.message, reason_code=reason) from None

    @staticmethod
    def _review_read_identity(job, *, preview=False):
        fields = {"tenant_id", "company_id", "created_by", "source_file_id", "retry_count", "document_ir_file_id",
            "result_file_id", "prepared_result", "status", "stage", "quality_status", "quality_summary",
            "review_status", "delivery_status", "current_review_record_id", "current_review_binding", "review_sequence",
            "deleted_at", "archived_at", "template_version_id", "mode", "document_language"}
        if preview:
            fields.update({"word_preview_state", "request_snapshot"})
        return digest(job.model_dump(mode="json", include=fields))

    def finish_review_read(self, job, file, user, *, preview=False, artifacts=()):
        """全部相关 I/O 后复核同次来源；不重试，也不把读投影写回仓储。"""
        current = self.review_api_job(job.id, user)
        if (self._review_read_identity(current, preview=preview) != self._review_read_identity(job, preview=preview)
                or self.access.review_api_file(current) != file):
            raise ApplicationError("conflict", "质量来源已变化，请重新读取。", reason_code="quality_source_changed")
        for artifact in artifacts:
            if (self.file_repository.get_document_file(artifact.id) != artifact
                    or artifact.expires_at is None or file_lifecycle_unavailable(artifact, self.file_repository, now=utc_now())):
                raise ApplicationError("conflict", "质量产物来源已变化，请重新读取。", reason_code="quality_source_changed")

    def _current_review_record(self, job):
        if job.current_review_record_id is None:
            return None
        records = self.job_repository.list_document_job_reviews(job.id, after_sequence=job.review_sequence - 1, limit=1)
        if (len(records) != 1 or records[0].id != job.current_review_record_id
                or records[0].sequence != job.review_sequence):
            raise ValueError("当前复核指针与正式历史不一致。")
        return records[0]

    @staticmethod
    def review_cursor(cursor, kind, job_id, limit):
        from app.domains.document_jobs.quality_review_projection import decode_cursor, InvalidReviewCursor
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApplicationError("validation_error", "分页数量必须为 1 到 100 的整数。")
        try:
            return decode_cursor(cursor, kind=kind, job_id=job_id) if cursor is not None else None
        except InvalidReviewCursor:
            raise ApplicationError("invalid_request", "分页游标无效。", reason_code="invalid_review_cursor") from None

    @staticmethod
    def _review_cursor_binding(parsed, expected):
        if parsed is not None and any(getattr(parsed, key) != value for key, value in expected.items()):
            raise ApplicationError("conflict", "质量分页来源已变化，请重新读取。", reason_code="quality_source_changed")

    def get_document_quality(self, job_id, *, user):
        from app.domains.document_jobs.quality_review_projection import project_source, project_quality_summary, project_review
        from app.domains.document_jobs.views.quality_review import DocumentQualityResponse
        job = self.review_api_job(job_id, user)
        file = self.access.review_api_file(job)
        view, actions = self.read_model.build_job_read_view(job, user=user, observed_result=file)
        summary, producers = project_quality_summary(job.quality_summary, generation=job.retry_count)
        review = project_review(self._current_review_record(job), effective_status=view.review_status,
            validity_reason=review_validity(job, file, now=utc_now()))
        response = DocumentQualityResponse(job_id=job.id, source=project_source(job, file),
            states={"execution_status": view.status, "quality_status": view.quality_status,
                "review_status": view.review_status, "delivery_status": view.delivery_status},
            summary=summary, producers=producers, review=review, available_actions=actions)
        self.finish_review_read(job, file, user)
        return response

    def get_document_review(self, job_id, *, user):
        from app.domains.document_jobs.quality_review_projection import project_source, project_review
        from app.domains.document_jobs.views.quality_review import DocumentCurrentReviewResponse
        job = self.review_api_job(job_id, user)
        file = self.access.review_api_file(job)
        view, actions = self.read_model.build_job_read_view(job, user=user, observed_result=file)
        response = DocumentCurrentReviewResponse(job_id=job.id, source=project_source(job, file),
            review=project_review(self._current_review_record(job), effective_status=view.review_status,
                validity_reason=review_validity(job, file, now=utc_now())), available_actions=actions)
        self.finish_review_read(job, file, user)
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
        from app.domains.document_jobs.views.quality_review import DocumentReviewHistoryResponse
        job = self.review_api_job(job_id, user)
        parsed = self.review_cursor(cursor, "history", job.id, limit)
        after, through = (parsed.after_sequence, parsed.through_sequence) if parsed else (0, job.review_sequence)
        if not 0 <= after <= through <= job.review_sequence:
            raise ApplicationError("invalid_request", "复核历史游标窗口无效。", reason_code="invalid_review_cursor")
        records = self.job_repository.list_document_job_reviews(job.id, after_sequence=after, limit=limit + 1)
        items, next_after = paginate_history(records, after_sequence=after, through_sequence=through, limit=limit)
        self.review_api_job(job.id, user)
        return DocumentReviewHistoryResponse(job_id=job.id, through_sequence=through,
            items=[project_review_history_item(record) for record in items], next_cursor=encode_cursor(
                HistoryCursor(job_id=job.id, after_sequence=next_after, through_sequence=through)) if next_after is not None else None)

    def get_document_quality_tables(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            TableCursor, encode_cursor, project_source, project_table_item, project_table_report,
        )
        from app.domains.document_jobs.views.quality_review import DocumentQualityTablesResponse
        job = self.review_api_job(job_id, user)
        parsed = self.review_cursor(cursor, "tables", job.id, limit)
        file = self.access.review_api_file(job)
        self._review_cursor_binding(parsed, dict(generation=job.retry_count,
            ir_file_id=job.document_ir_file_id, result_file_id=job.result_file_id))
        evidence = self.get_table_evidence(job.id, user=user, generation=job.retry_count,
            ir_file_id=job.document_ir_file_id, result_file_id=job.result_file_id)
        binding = dict(generation=job.retry_count, ir_file_id=job.document_ir_file_id,
            result_file_id=job.result_file_id, report_sha256=evidence.report_sha256)
        self._review_cursor_binding(parsed, binding)
        start = parsed.next_index if parsed else 0
        if start > len(evidence.tables):
            raise ApplicationError("invalid_request", "表格分页游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentQualityTablesResponse(job_id=job.id, source=project_source(job, file),
            availability=evidence.evidence_status, reason_code=None,
            report=project_table_report(evidence) if evidence.evidence_status == "available" else None,
            items=[project_table_item(table) for table in evidence.tables[start:end]], next_cursor=encode_cursor(
                TableCursor(job_id=job.id, **binding, next_index=end)) if end < len(evidence.tables) else None)
        self.finish_review_read(job, file, user)
        return response

    def _read_api_preview(self, job, *, include_page_quality=False):
        from app.domains.document_jobs.preview_evidence import read_current_preview_evidence, PreviewStorageError, frozen_page_policy
        from app.domains.document_jobs.preview_state import _confirmed
        from app.services.preview.models import PreviewPolicy
        try:
            if include_page_quality:
                quality_policy = frozen_page_policy(job)
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
                raise PreviewStorageError()
            evidence = read_current_preview_evidence(job, self.file_repository, self.file_upload_service,
                include_page_quality=include_page_quality)
        except PreviewStorageError:
            raise ApplicationError("service_unavailable", "质量产物存储暂不可用。", reason_code="quality_storage_unavailable") from None
        except ValueError:
            raise ApplicationError("conflict", "预览质量证据无法认证。", reason_code="quality_evidence_conflict") from None
        if not evidence.observation.available or state.current_run.status != "succeeded":
            return "unavailable", evidence
        if include_page_quality and evidence.page_quality_run is None:
            return "not_ready", evidence
        return "available", evidence

    def get_document_preview(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            PreviewCursor, encode_cursor, project_source, project_preview_run, project_preview_page,
        )
        from app.domains.document_jobs.views.quality_review import DocumentPreviewResponse
        job = self.review_api_job(job_id, user)
        parsed = self.review_cursor(cursor, "preview", job.id, limit)
        file = self.access.review_api_file(job)
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
            raise ApplicationError("invalid_request", "预览分页游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentPreviewResponse(job_id=job.id, source=project_source(job, file),
            status=run.status if run else (availability if availability in {"disabled", "not_ready"} else "unavailable"), availability=availability,
            reason_code="preview_artifact_unavailable" if availability == "unavailable" else None,
            run=project_preview_run(state, run) if run else None, pdf_file_id=body["pdf_file_id"] if body else None,
            page_count=body["page_count"] if body else None, items=[project_preview_page(page) for page in pages[start:end]],
            next_cursor=encode_cursor(PreviewCursor(job_id=job.id, **binding, next_index=end)) if end < len(pages) else None)
        artifacts = evidence.observation.files if evidence and evidence.observation.available else ()
        self.finish_review_read(job, file, user, preview=True, artifacts=artifacts)
        return response

    def get_document_quality_pages(self, job_id, *, user, limit=50, cursor=None):
        from app.domains.document_jobs.quality_review_projection import (
            PageCursor, encode_cursor, project_source, project_page_report, project_page_item,
        )
        from app.domains.document_jobs.views.quality_review import DocumentQualityPagesResponse
        job = self.review_api_job(job_id, user)
        parsed = self.review_cursor(cursor, "pages", job.id, limit)
        file = self.access.review_api_file(job)
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
            raise ApplicationError("invalid_request", "页面质量游标无效。", reason_code="invalid_review_cursor")
        end = start + limit
        response = DocumentQualityPagesResponse(job_id=job.id, source=project_source(job, file),
            availability=availability, reason_code="preview_artifact_unavailable" if availability == "unavailable" else None,
            report=project_page_report(report, revision=state.revision, manifest_file_id=run.manifest_file_id) if report else None,
            items=[project_page_item(page) for page in pages[start:end]], next_cursor=encode_cursor(
                PageCursor(job_id=job.id, **binding, next_index=end)) if end < len(pages) else None)
        artifacts = evidence.observation.files if evidence and evidence.observation.available else ()
        self.finish_review_read(job, file, user, preview=True, artifacts=artifacts)
        return response

    def submit_document_review_with_source(self, job_id, *, user, review_status, expected_source,
            issue_type=None, note=None, trace_id=None):
        from app.domains.document_jobs.views.quality_review import DocumentReviewUpdateResponse
        expected = ReviewExpectedSource.model_validate(expected_source)
        committed = self.review_writer.submit_document_review(self.review_api_job(job_id, user), user=user,
            review_status=review_status, issue_type=issue_type, note=note, trace_id=trace_id, expected_source=expected)
        try:
            current = self.get_document_review(job_id, user=user)
        except ApplicationError as exc:
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
            raise ApplicationError("unauthorized", "表格证据查询需要认证。")
        from app.services.tables.evidence import TableEvidenceError
        job = self.access.get_job(job_id, user=user)
        self.access.ensure_job_not_deleted(job)
        if (type(generation) is not int or generation != job.retry_count or ir_file_id != job.document_ir_file_id
                or result_file_id != job.result_file_id):
            raise ApplicationError("conflict", "表格证据所属任务快照已变化，请刷新。", reason_code="quality_source_changed")
        base = dict(job_id=job.id, generation=job.retry_count, ir_file_id=ir_file_id, result_file_id=result_file_id)
        if result_file_id is None:
            return TableEvidenceView(**base, evidence_status="not_ready", summary={"status": "pending"}, tables=[])
        result = self.access.get_completed_result_file(job)
        try:
            ensure_selected_result_descriptor(job, result)
        except TableEvidenceError:
            raise ApplicationError("conflict", "当前主件与选定表格证据凭据冲突，请刷新。", reason_code="quality_evidence_conflict") from None
        if not has_evidence(result.metadata):
            return TableEvidenceView(**base, evidence_status="legacy_unavailable", summary={"status": "pending"}, tables=[])
        if self.file_upload_service is None:
            raise ApplicationError("service_unavailable", "表格证据存储暂不可用。", reason_code="quality_storage_unavailable")
        try:
            verified = verify_report(job, result, file_repository=self.file_repository,
                file_service=self.file_upload_service, job_repository=self.job_repository)
        except FileNotFoundError:
            raise ApplicationError("not_found", "表格证据文件或内容不存在。", reason_code="quality_artifact_missing") from None
        except TableEvidenceError:
            raise ApplicationError("conflict", "表格证据绑定或当前快照无效，请刷新。", reason_code="quality_evidence_conflict") from None
        except RuntimeError:
            raise ApplicationError("service_unavailable", "表格证据存储暂不可用。", reason_code="quality_storage_unavailable") from None
        current = self.access.get_job(job_id, user=user)
        self.access.ensure_job_not_deleted(current)
        if (current.retry_count, current.document_ir_file_id, current.result_file_id) != (generation, ir_file_id, result_file_id):
            raise ApplicationError("conflict", "表格证据所属任务快照已变化，请刷新。", reason_code="quality_source_changed")
        try:
            recheck_verified_report(verified, file_repository=self.file_repository, job_repository=self.job_repository)
        except TableEvidenceError:
            raise ApplicationError("conflict", "表格证据绑定或当前快照无效，请刷新。", reason_code="quality_evidence_conflict") from None
        envelope, summary = verified.envelope, verified.summary
        tables = envelope.report.tables
        if table_id is not None:
            tables = [table for table in tables if table.table_id == table_id]
            if not tables:
                raise ApplicationError("not_found", "当前报告未引用该表格。")
        return TableEvidenceView(**base, evidence_status="available", report_file_id=summary["report_file_id"],
            report_sha256=envelope.report.report_sha256, summary=summary,
            tables=[table.model_dump(mode="json", warnings=False) for table in tables])

    def submit_document_review(
        self, job_id: str, *, user: AuthenticatedUser, review_status: ReviewStatus,
        issue_type: ReviewIssueType | None = None, note: str | None = None, trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """两模式共用的受权内部入口；不读取翻译诊断或触发生产者。"""
        return self.review_writer.submit_document_review(self.access.get_authorized_job(job_id, user=user), user=user,
            review_status=review_status, issue_type=issue_type, note=note, trace_id=trace_id).job

    def list_document_reviews(
        self, job_id: str, *, user: AuthenticatedUser, after_sequence: int = 0, limit: int = 100,
    ) -> list[ReviewRecord]:
        """先鉴权任务，再按 job 和有界序号读取历史；不提供裸记录 ID 查询。"""
        job = self.access.get_authorized_job(job_id, user=user)
        return self.job_repository.list_document_job_reviews(job.id, after_sequence=after_sequence, limit=limit)
