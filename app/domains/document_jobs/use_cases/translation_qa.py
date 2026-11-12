from __future__ import annotations

# app/domains/document_jobs/use_cases/translation_qa.py: 用例：翻译 QA 读取与更新。

import json
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup
from fastapi import status

from app.core.errors import ApiError
from app.domains.document_jobs.delivery_state import translation_qa_projection
from app.domains.document_jobs.models import (
    DocumentJobRecord,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.schemas.translation import (
    DocumentJobTranslationQaAiCallResponse,
    DocumentJobTranslationQaArtifactsResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaSegmentResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaSummaryResponse,
    DocumentJobTranslationQaTermTraceResponse,
)
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.document_jobs.use_cases.review_writer import DocumentReviewWriter
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.auth.models import AuthenticatedUser
from app.services.document_ir.models import DocumentIR


class DocumentJobTranslationQa:
    """用例：翻译 QA 读取与更新。"""

    def __init__(
        self,
        *,
        file_repository: DocumentFileRepositoryProtocol,
        file_upload_service: Any | None,
        access: DocumentJobAccess,
        review_writer: DocumentReviewWriter,
    ) -> None:
        self.file_repository = file_repository
        self.file_upload_service = file_upload_service
        self.access = access
        self.review_writer = review_writer

    def get_translation_qa(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        limit: int,
    ) -> DocumentJobTranslationQaResponse:
        """读取翻译 QA 证据摘要；只消费已有 artifact，不触发任何任务执行。"""

        job = self.access.get_job(job_id, user=user)
        qa = self._build_translation_qa_state(job)
        if not is_translation_document_job_mode(job.mode):
            return self._build_unavailable_translation_qa(job, qa, reason="unsupported_mode")
        self.access.ensure_file_reader_available()

        files = self.access.list_files_for_job(job)
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
        job = self.access.get_authorized_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "翻译 QA 仅支持翻译任务。")
        return self.review_writer.submit_document_review(job, user=user, review_status=qa_status,
                                            issue_type=issue_type, note=note, trace_id=trace_id).job

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
            if self.access.normalize_optional_text(block.text):
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
                if not self.access.normalize_optional_text(text):
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
                if not self.access.normalize_optional_text(text):
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
