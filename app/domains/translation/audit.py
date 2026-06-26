from __future__ import annotations

# app/domains/translation/audit.py: 保存翻译 AI 调用的元数据审计记录和可选全文调试归档。

import hashlib
import json
from datetime import timedelta
from collections.abc import Callable
from uuid import uuid4

from app.core.config import Settings
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.resources.models import utc_now
from app.domains.translation.provider_config import EffectiveAiProviderConfig
from app.domains.translation.models import (
    TermVersionSnapshot,
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTermMatchTraceRecord,
    TranslationTextItem,
)
from app.domains.translation.provider import TranslationProviderResponseError
from app.domains.files import FileUploadService


class TranslationCallAuditRecorder:
    """记录单次翻译 provider 调用；默认审计文件不包含 prompt 和 response 原文。"""

    def __init__(
        self,
        *,
        settings: Settings,
        file_service: FileUploadService,
        job: DocumentJobRecord,
        term_version: TermVersionSnapshot | None,
        trace_id: str | None,
        save_full_text: bool,
        config_resolver: Callable[[], EffectiveAiProviderConfig] | None = None,
    ) -> None:
        self.settings = settings
        self.file_service = file_service
        self.job = job
        self.term_version = term_version
        self.trace_id = trace_id
        self.save_full_text = save_full_text
        self.config_resolver = config_resolver
        self.call_id: str | None = None
        self.call_log_file_id: str | None = None
        self.call_log_file_ids: list[str] = []
        self.debug_archive_file_id: str | None = None
        self.debug_archive_file_ids: list[str] = []

    def record_success(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult,
        *,
        duration_ms: int,
    ) -> None:
        """保存成功调用的 metadata-only 审计记录，并按任务开关保存全文归档。"""

        call_id = self._new_call_id()
        self._write_call_log(
            call_id=call_id,
            request=request,
            result=result,
            status="succeeded",
            duration_ms=duration_ms,
            error=None,
        )
        self._write_debug_archive(call_id=call_id, request=request, result=result, error=None)

    def record_failure(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        *,
        error: Exception,
        duration_ms: int,
    ) -> None:
        """保存失败调用的 metadata-only 审计记录，必要时保留全文现场。"""

        error_payload = {
            "type": error.__class__.__name__,
            "message": self._redact_error_message(str(error)),
        }
        if isinstance(error, TranslationProviderResponseError):
            error_payload.update(
                {
                    "finish_reason": error.finish_reason,
                    "usage": error.usage,
                    "response_id": error.response_id,
                    "content_length": error.content_length,
                    "content_sha256": error.content_sha256,
                    "suspected_truncation": error.suspected_truncation,
                }
            )
        call_id = self._new_call_id()
        self._write_call_log(
            call_id=call_id,
            request=request,
            result=result,
            status="failed",
            duration_ms=duration_ms,
            error=error_payload,
        )
        self._write_debug_archive(call_id=call_id, request=request, result=result, error=error_payload)

    def _new_call_id(self) -> str:
        call_id = f"aicall_{uuid4().hex[:12]}"
        self.call_id = call_id
        return call_id

    def _write_call_log(
        self,
        *,
        call_id: str,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        status: str,
        duration_ms: int,
        error: dict | None,
    ) -> None:
        provider = self._provider_summary()
        payload = {
            "schema_version": "ai-call-log/v1",
            "call_id": call_id,
            "job_id": self.job.id,
            "trace_id": self.trace_id,
            "status": status,
            "provider": provider,
            "language_pair": request.language_pair,
            "source_language": request.source_language,
            "target_language": request.target_language,
            "term_version_id": self.term_version.term_version_id if self.term_version is not None else None,
            "term_snapshot_hash": self.term_version.snapshot_hash if self.term_version is not None else None,
            "term_count": len(request.terms),
            "glossary_trace": self._term_trace_summary(request.term_traces),
            "batch": self._batch_summary(request),
            "request": {
                "item_count": len(request.items),
                "char_count": sum(len(item.text) for item in request.items),
                "sha256": self._hash_json(self._full_request_payload(request)),
                "redacted_items": self._redacted_items_summary(request.items),
            },
            "response": self._response_summary(result),
            "error": error,
            "duration_ms": duration_ms,
            "created_at": utc_now().isoformat(),
        }
        record = self.file_service.register_generated_content(
            tenant_id=self.job.tenant_id,
            company_id=self.job.company_id,
            job_id=self.job.id,
            created_by=self.job.created_by,
            file_type="ai_call_log",
            filename=f"{call_id}.json",
            mime_type="application/json",
            content=self._json_bytes(payload),
            metadata={
                "call_id": call_id,
                "status": status,
                "provider_backend": provider["backend"],
                "language_pair": request.language_pair,
                "batch_id": request.batch_id,
                "attempt": request.attempt,
                "item_count": len(request.items),
                "term_version_id": self.term_version.term_version_id if self.term_version is not None else None,
                "retry_count": self.job.retry_count,
            },
        )
        self.call_log_file_id = record.id
        self.call_log_file_ids.append(record.id)

    def _write_debug_archive(
        self,
        *,
        call_id: str,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        error: dict | None,
    ) -> None:
        if not self.save_full_text:
            return
        provider = self._provider_summary()
        payload = {
            "schema_version": "translation-debug-archive/v1",
            "call_id": call_id,
            "job_id": self.job.id,
            "trace_id": self.trace_id,
            "provider": provider,
            "prompt": self._full_request_payload(request),
            "response": self._full_response_payload(result),
            "error": error,
            "created_at": utc_now().isoformat(),
        }
        expires_at = utc_now() + timedelta(days=max(1, self.settings.translation_debug_archive_retention_days))
        record = self.file_service.register_generated_content(
            tenant_id=self.job.tenant_id,
            company_id=self.job.company_id,
            job_id=self.job.id,
            created_by=self.job.created_by,
            file_type="ai_debug_archive",
            filename=f"{call_id}_debug.json",
            mime_type="application/json",
            content=self._json_bytes(payload),
            metadata={
                "call_id": call_id,
                "provider_backend": provider["backend"],
                "language_pair": request.language_pair,
                "batch_id": request.batch_id,
                "attempt": request.attempt,
                "contains_full_text": True,
                "retention_days": max(1, self.settings.translation_debug_archive_retention_days),
                "retry_count": self.job.retry_count,
            },
            expires_at=expires_at,
        )
        self.debug_archive_file_id = record.id
        self.debug_archive_file_ids.append(record.id)

    def _response_summary(self, result: TranslationProviderResult | None) -> dict | None:
        if result is None:
            return None
        return {
            "item_count": len(result.items),
            "char_count": sum(len(item.text) for item in result.items),
            "sha256": self._hash_json(self._full_response_payload(result)),
            "redacted_items": self._redacted_items_summary(result.items),
            "finish_reason": result.finish_reason,
            "usage": result.usage,
            "response_id": result.response_id,
            "provider_trace_id": result.provider_trace_id,
            "content_length": result.content_length,
            "content_sha256": result.content_sha256,
        }

    def _batch_summary(self, request: TranslationProviderRequest) -> dict | None:
        if request.batch_id is None:
            return None
        return {
            "batch_id": request.batch_id,
            "attempt": request.attempt,
            "split_level": request.split_level,
            "parent_batch_id": request.parent_batch_id,
            "page_start": request.page_start,
            "page_end": request.page_end,
            "item_count": len(request.items),
            "char_count": sum(len(item.text) for item in request.items),
        }

    def _full_request_payload(self, request: TranslationProviderRequest) -> dict:
        return {
            "language_pair": request.language_pair,
            "source_language": request.source_language,
            "target_language": request.target_language,
            "terms": [
                {
                    "language_pair": term.language_pair,
                    "source_term": term.source_term,
                    "target_term": term.target_term,
                    "version": term.version,
                }
                for term in request.terms
            ],
            "items": [{"id": item.id, "text": item.text} for item in request.items],
        }

    def _full_response_payload(self, result: TranslationProviderResult | None) -> dict | None:
        if result is None:
            return None
        return {"items": [{"id": item.id, "text": item.text} for item in result.items]}

    def _provider_summary(self) -> dict[str, str | None]:
        if self.config_resolver is not None:
            config = self.config_resolver()
            return {"backend": config.backend, "model": config.model if config.backend == "openai_compatible" else None}
        return {
            "backend": self.settings.translation_provider_backend,
            "model": self.settings.openai_model if self.settings.translation_provider_backend == "openai_compatible" else None,
        }

    def _term_trace_summary(self, traces: tuple[TranslationTermMatchTraceRecord, ...]) -> list[dict]:
        return [
            {
                "segment_id": trace.segment_id,
                "batch_id": trace.batch_id,
                "translation_term_set_id": trace.translation_term_set_id,
                "translation_term_version": trace.translation_term_version,
                "source_term": trace.source_term,
                "target_term": trace.target_term,
                "match_start": trace.match_start,
                "match_end": trace.match_end,
                "context": self._redacted_context_summary(trace.context_snippet),
                "injected_to_glossary": trace.injected_to_glossary,
                "provider_trace_id": trace.provider_trace_id,
            }
            for trace in traces
        ]

    def _redacted_context_summary(self, context_snippet: str | None) -> dict | None:
        if context_snippet is None:
            return None
        return {
            "char_count": len(context_snippet),
            "sha256": self._hash_text(context_snippet),
        }

    def _redacted_items_summary(self, items: tuple[TranslationTextItem, ...]) -> list[dict]:
        return [
            {
                "id": item.id,
                "char_count": len(item.text),
                "line_count": item.text.count("\n") + 1,
                "sha256": self._hash_text(item.text),
                "has_non_ascii": any(ord(char) > 127 for char in item.text),
            }
            for item in items
        ]

    def _hash_json(self, payload: dict | None) -> str | None:
        if payload is None:
            return None
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def _hash_text(self, text: str) -> str:
        return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

    def _json_bytes(self, payload: dict) -> bytes:
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    def _redact_error_message(self, message: str) -> str:
        normalized = " ".join(message.split())
        if len(normalized) <= 500:
            return normalized
        return normalized[:497] + "..."


class TranslationAuditService:
    """为 document_jobs 构建翻译调用审计 recorder。"""

    def __init__(
        self,
        settings: Settings,
        file_service: FileUploadService,
        config_resolver: Callable[[], EffectiveAiProviderConfig] | None = None,
    ) -> None:
        self.settings = settings
        self.file_service = file_service
        self.config_resolver = config_resolver

    def build_recorder(
        self,
        *,
        job: DocumentJobRecord,
        term_version: TermVersionSnapshot | None,
        trace_id: str | None,
        save_full_text: bool,
    ) -> TranslationCallAuditRecorder:
        return TranslationCallAuditRecorder(
            settings=self.settings,
            file_service=self.file_service,
            job=job,
            term_version=term_version,
            trace_id=trace_id,
            save_full_text=save_full_text,
            config_resolver=self.config_resolver,
        )
