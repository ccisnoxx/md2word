"""生成 Word 的结果身份认证与 receipt 之后的上传收尾。"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.execution_support import DocumentJobLifecycle, require_uploaded_file
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.render_placeholders import RenderPlaceholderSource
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.table_evidence import (
    has_evidence,
    verify_report,
    validate_candidate_binding,
    recheck_verified_report,
)
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_placeholder import (
    TablePlaceholderError,
    checksum as placeholder_checksum,
    decode_placeholders,
)
from app.services.renderer import image_evidence
from app.services.renderer.block_anchors import validate_block_anchor_evidence
from app.services.renderer.render_event_summary import build_renderer_event_summary
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import validate_persisted_render_evidence
from app.services.tables.evidence import TableEvidenceError


class WordResultFinalizer:
    """生成 Word 的结果身份：最终 IR/历史主件查找、主件与绑定 IR 的实物认证，以及 receipt 之后的上传收尾。"""

    def __init__(
        self,
        *,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        lifecycle: DocumentJobLifecycle,
        word_preview_service: DocumentJobPreviewService,
        placeholders: RenderPlaceholderSource,
    ) -> None:
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.lifecycle = lifecycle
        self.word_preview_service = word_preview_service
        self.placeholders = placeholders
        self.logger = logging.getLogger("business")

    def finish_selected_or_current(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        current = self.job_repository.get_document_job(job.id) or job
        timed_out = self.lifecycle.mark_timed_out_if_needed(current, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        if current.status == "running" and current.retry_count == job.retry_count and current.prepared_result is not None:
            return self.finish_prepared_result(current, trace_id=trace_id)
        return current

    def finish_prepared_result(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        """receipt 后只物化同一身份；两步之间中断可由任意重投继续。"""

        current = self.job_repository.get_document_job(job.id) or job
        if current.status != "running" or current.retry_count != job.retry_count:
            return current
        receipt = job.prepared_result
        if receipt is None:
            raise ValueError("任务没有选定结果凭据。")
        timed_out = self.lifecycle.mark_timed_out_if_needed(job, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        try:
            validate_candidate_binding(job, receipt.file)
            word_file = self.file_repository.materialize_prepared_result(receipt.file)
            ir_file, final_ir, _ = self.validate_result_file(word_file)
            verified_report = verify_report(job, word_file, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
            # 恢复只核对原 receipt 的实物，不重裁图、不重渲染或更换同代身份。
            proof = word_file.metadata.get("table_placeholder_rendering")
            placeholders = decode_placeholders(final_ir, require_bound=True)
            if placeholders or proof is not None:
                if final_ir.metadata.job_id != job.id or final_ir.metadata.source_file_id != job.source_file_id:
                    raise TablePlaceholderError("table_placeholder_integrity_failed")
                self.placeholders.verify_dependencies(job, final_ir)
                for file in (ir_file, word_file):
                    self.placeholders.ensure_file_current(job, file, "table_placeholder_integrity_failed")
            preview_job, preview_finished = self.word_preview_service.ensure_initial(current, trace_id=trace_id)
            if not preview_finished:
                return self.lifecycle.mark_timed_out_if_needed(preview_job, trace_id=trace_id) or preview_job
            if verified_report is not None:
                recheck_verified_report(verified_report, file_repository=self.file_repository,
                                        job_repository=self.job_repository)
            completed = self.job_repository.update_document_job_if_current(
                job.id, allowed_statuses={"running"}, allowed_stages={"uploading"},
                expected_retry_count=receipt.generation, expected_document_ir_file_id=receipt.document_ir_file_id,
                expected_prepared_result_file_id=word_file.id, status="succeeded", stage="completed",
                progress=100, result_file_id=word_file.id, completed_at=utc_now(), updated_at=utc_now(),
            )
        except Exception as exc:
            return self.lifecycle.mark_failed(job,
                failed_stage="quality_checking" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "uploading",
                error_code="render_failed" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "oss_failed",
                error_message=(failure_policy.worker_failure_message(exc) if isinstance(exc, (TablePlaceholderError, TableEvidenceError, DocumentIntegrityError)) or
                    "table_placeholder_rendering" not in receipt.file.metadata else "表格占位结果文件读取或完整性校验失败。"),
                trace_id=trace_id, expected_prepared_result_file_id=receipt.file.id)
        if completed is None:
            current = self.job_repository.get_document_job(job.id) or job
            return self.lifecycle.mark_timed_out_if_needed(current, trace_id=trace_id) or current
        self.lifecycle.record_event(completed, event_type="file_registered", stage="uploading", message="生成 Word 已保存。",
                           payload={"file_id": word_file.id, "file_type": word_file.file_type,
                                    **build_renderer_event_summary(word_file.metadata)}, trace_id=trace_id)
        self.lifecycle.record_event(completed, event_type="stage_succeeded", stage="completed", message="文档任务已完成。",
                           payload={"result_file_id": word_file.id, "template_version_id": completed.template_version_id},
                           trace_id=trace_id)
        return completed

    def validate_result_file(self, record: DocumentFileRecord) -> tuple[DocumentFileRecord, DocumentIR, bytes]:
        """先核实原件及绑定 IR 的实物，再由 renderer 按保存的版本认证内容。"""

        if (record.file_type != "generated_word" or record.status != "uploaded"
                or record.expires_at is not None and record.expires_at <= utc_now()
                or record.expires_at is None and any(key in record.metadata for key in (
                    "renderer_content_contract_version", "formula_source_coverage"))):
            raise ValueError("主 DOCX 的类型、状态或保留期无效。")
        content = self.file_service.read_file_content(record)
        if record.size_bytes != len(content) or record.checksum_sha256 != f"sha256:{hashlib.sha256(content).hexdigest()}":
            raise ValueError("主 DOCX 字节与 SHA-256 描述不一致。")
        ir_id = record.metadata.get("document_ir_file_id")
        if not isinstance(ir_id, str) or not ir_id:
            raise ValueError("主 DOCX 缺少原始 IR 绑定。")
        ir_file = require_uploaded_file(self.file_repository, ir_id)
        if ((ir_file.tenant_id, ir_file.company_id, ir_file.job_id)
                != (record.tenant_id, record.company_id, record.job_id) or ir_file.file_type != "document_ir"
                or ir_file.expires_at is not None and ir_file.expires_at <= utc_now()):
            raise ValueError("主 DOCX 的原始 IR 与文件归属不一致。")
        ir_bytes = self.file_service.read_file_content(ir_file)
        if ir_file.size_bytes != len(ir_bytes) or ir_file.checksum_sha256 != placeholder_checksum(ir_bytes):
            raise ValueError("主 DOCX 的原始 IR 字节与描述不一致。")
        ir = DocumentIR.model_validate_json(ir_bytes)
        validate_persisted_renderer_content(ir, content, record.metadata,
            expected_template_version_id=record.metadata.get("template_version_id"))
        self._validate_optional_block_anchors(ir, content, record.metadata)
        return ir_file, ir, content

    def _validate_optional_block_anchors(self, document_ir: DocumentIR, content: bytes, metadata: dict[str, Any]) -> None:
        """历史恢复只局部认证可选锚点；保留原 metadata，不重建或升级创建事实。"""
        if "block_anchor_evidence" not in metadata:
            return
        verified = validate_persisted_render_evidence(document_ir, content,
            render_plan=metadata.get("render_plan"), block_render_evidence=metadata.get("block_render_evidence"))
        anchors = None
        if verified is not None:
            plan, trace = verified
            anchors = validate_block_anchor_evidence(metadata["block_anchor_evidence"], plan=plan,
                block_evidence=trace, word_content=content)
        if anchors is None:
            self.logger.warning("[reason_code=anchor_missing] 历史主件的可选锚点证据不可用。")

    def get_document_ir_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        if job.document_ir_file_id is None:
            raise FileNotFoundError(f"任务缺少权威最终 DocumentIR 指针: {job.id}")
        record = require_uploaded_file(self.file_repository, job.document_ir_file_id)
        if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                or record.file_type != "document_ir"):
            raise ValueError("最终 DocumentIR 文件与任务归属不一致。")
        return record

    def get_existing_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord | None:
        if job.result_file_id:
            record = require_uploaded_file(self.file_repository, job.result_file_id)
            if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                    or record.file_type != "generated_word"
                    or (record.expires_at is not None and record.expires_at <= utc_now())):
                raise ValueError("任务指定的结果文件不属于该任务的可用主 DOCX。")
            if (any(key in record.metadata for key in ("renderer_content_contract_version", "formula_source_coverage",
                    "formula_report", "formula_summary"))
                    or image_evidence.IMAGE_EVIDENCE_KEYS.intersection(record.metadata)
                    or has_evidence(record.metadata)):
                self.validate_result_file(record)
            elif image_evidence.has_image_markers(self.file_service.read_file_content(record)):
                raise ValueError("主 DOCX 含图片布局标记但缺少报告。")
            # 显式历史指针原本允许无报告、无 IR 绑定；仅该已验收路径保留原门。
            if has_evidence(record.metadata):
                verify_report(job, record, file_repository=self.file_repository,
                              file_service=self.file_service, job_repository=self.job_repository)
            return record
        candidates = [
            file for file in self.file_repository.list_document_files()
            if (file.tenant_id, file.company_id, file.job_id) == (job.tenant_id, job.company_id, job.id)
            and file.file_type == "generated_word" and file.status == "uploaded"
            and "document_job_result_protocol" not in file.metadata
            and type(file.metadata.get("retry_count")) is int and file.metadata["retry_count"] == job.retry_count
            and job.document_ir_file_id is not None
            and file.metadata.get("document_ir_file_id") == job.document_ir_file_id
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ValueError("同代最终 IR 存在多份历史主件，不能猜测结果身份。")
        record = candidates[0]
        if record.expires_at is None or record.expires_at <= utc_now():
            raise ValueError("历史主件已过期或缺少保留期。")
        self.validate_result_file(record)
        if has_evidence(record.metadata):
            verify_report(job, record, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
        return record
