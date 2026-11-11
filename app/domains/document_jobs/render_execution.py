"""Word 渲染执行：渲染、页面降级、质量检查、上传收尾与表格占位符读取。"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded

from app.clients.mineru_client import MinerUError
from app.core.errors import ApiError
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.publication_provenance import capture_render_publication_provenance
from app.domains.document_jobs.table_evidence import (
    has_evidence,
    save_report,
    verify_report,
    validate_candidate_binding,
    recheck_verified_report,
)
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, TableReferenceProvenance
from app.services.document_ir.page_degradation import (
    PAGE_RASTER_SOURCE_PATH,
    degradation_closure,
    drop_degraded_table_groups,
    replace_degraded_pages,
)
from app.services.document_ir.table_placeholder import (
    PdfCropSource,
    TablePlaceholderError,
    checksum as placeholder_checksum,
    decode_placeholders,
)
from app.services.document_ir.table_reference_assets import TABLE_REFERENCE_ROLE, decode_table_references
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer, image_evidence
from app.services.renderer.block_anchors import validate_block_anchor_evidence
from app.services.renderer.render_evidence import (
    build_renderer_evidence,
    validate_persisted_renderer_content,
)
from app.services.renderer.render_evidence_validation import (
    ensure_renderer_integrity,
    validate_persisted_render_evidence,
)
from app.services.renderer.render_event_summary import build_renderer_event_summary
from app.services.renderer.layout_plan import build_layout_plan
from app.services.tables.evidence import TableEvidenceError

if TYPE_CHECKING:
    # execution.py 在运行时导入本模块；这里只为类型标注引用，避免循环导入。
    from app.domains.document_jobs.execution import DocumentJobExecutionService


class WordRenderExecution:
    """Word 渲染执行：由 DocumentJobExecutionService 构造并持有，负责渲染、页面降级、质量检查、上传收尾与表格占位符读取。

    任务级状态与事件仍由宿主收口。对宿主只允许调用 _record_event、_mark_failed、_mark_succeeded、
    _mark_timed_out_if_needed、_get_uploaded_file、_document_ir_layout_metadata，且必须在调用时经
    self._host 查找，不得在构造时捕获绑定方法，否则对宿主方法的替换（例如测试中的 patch.object）不会生效。
    settings、job_repository 等共用依赖只由宿主持有，同样在使用时经 self._host 读取，本类只保存专属依赖。
    """

    def __init__(
        self,
        host: DocumentJobExecutionService,
        *,
        template_read_service: Any,
        word_renderer: DocumentIRWordRenderer,
        word_preview_service: DocumentJobPreviewService,
    ) -> None:
        self._host = host
        self.template_read_service = template_read_service
        self.word_renderer = word_renderer
        self.word_preview_service = word_preview_service
        self.logger = logging.getLogger("business")

    def _render_and_save_word(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        attempt = job
        validating_legacy = False
        try:
            current = self._host.job_repository.get_document_job(job.id) or job
            if current.retry_count != job.retry_count or current.status != "running":
                return current
            if current.prepared_result is not None:
                return self._finish_prepared_result(current, trace_id=trace_id)
            # 明确历史指针优先保留；legacy 扫描必须唯一且可验证。
            if job.stage != "quality_checking":
                validating_legacy = True
                existing_result = self._get_existing_result_file(job)
                validating_legacy = False
                if existing_result is not None:
                    uploading = self._host.job_repository.update_document_job_if_current(
                        job.id, allowed_statuses={"running"}, allowed_stages={"rendering", "uploading"},
                        expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                        require_no_prepared_result=True, stage="uploading", updated_at=utc_now(),
                    )
                    if uploading is None:
                        return self._finish_selected_or_current(job, trace_id=trace_id)
                    if job.result_file_id is not None:
                        return self._host._mark_succeeded(uploading, trace_id=trace_id)
                    prepared = self._host.job_repository.prepare_document_job_result(
                        job.id, expected_retry_count=job.retry_count,
                        expected_document_ir_file_id=job.document_ir_file_id, candidate=existing_result,
                    )
                    if prepared is None:
                        return self._finish_selected_or_current(job, trace_id=trace_id)
                    return self._finish_prepared_result(prepared, trace_id=trace_id)
            attempt = job
            recovery_from = job.stage if job.stage in {"quality_checking", "uploading"} else None
            rendering = job
            if recovery_from is not None:
                rendering = self._host.job_repository.update_document_job_if_current(
                    job.id, allowed_statuses={"running"}, allowed_stages={recovery_from},
                    expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                    require_no_prepared_result=True, stage="rendering", updated_at=utc_now(),
                )
                if rendering is None:
                    return self._finish_selected_or_current(job, trace_id=trace_id)
            attempt = rendering
            self._host._record_event(
                rendering,
                event_type="stage_started",
                stage="rendering",
                message="内存中的 Word 内容已丢失，重新渲染并校验。" if recovery_from else "Word 渲染已开始。",
                payload={
                    "document_ir_file_id": rendering.document_ir_file_id,
                    "template_version_id": rendering.template_version_id,
                    **({"recovery_from": recovery_from} if recovery_from else {}),
                },
                trace_id=trace_id,
            )
            render_started_at = time.perf_counter()

            ir_file = self._get_document_ir_file(rendering)
            try:
                ir_bytes = self._host.file_service.read_file_content(ir_file)
                document_ir = DocumentIR.model_validate_json(ir_bytes)
            except ValueError:
                raise TablePlaceholderError("table_placeholder_integrity_failed") from None
            snapshot_resources = rendering.request_snapshot.get("resources")
            snapshot_template = snapshot_resources.get("template") if isinstance(snapshot_resources, dict) else None
            draft_was_authorized_at_creation = (
                isinstance(snapshot_template, dict)
                and snapshot_template.get("status") == "draft"
                and rendering.template_version_id
                == f"{snapshot_template.get('resource_id')}@{snapshot_template.get('version')}"
            )
            # 仅允许执行创建阶段已固化 draft 快照的验证任务，legacy 或不一致记录继续按 published 校验。
            template_selection = self.template_read_service.resolve_template_version(
                rendering.template_version_id,
                allow_draft=draft_was_authorized_at_creation,
            )
            def render(job: DocumentJobRecord, document: DocumentIR):
                return self.word_renderer.render_to_result(
                    document,
                    template_path=template_selection.template_path,
                    config_path=template_selection.layout_config_path,
                    image_loader=self._build_image_loader(job, document),
                    options=DocumentIRRenderOptions(
                        subscript_config_path=self._host.settings.subscript_config_path,
                        document_language=document.metadata.document_language,
                        template_version_id=template_selection.template_version_id,
                    ),
                )

            degradation_attempts = 0
            while True:
                try:
                    render_result = render(rendering, document_ir)
                    break
                except Exception as exc:
                    if degradation_attempts >= self._host.settings.render_degradation_max_attempts:
                        raise
                    degraded = self._degrade_render_failure_page(rendering, ir_file, document_ir, exc, trace_id=trace_id)
                    if degraded is None:
                        raise
                    if isinstance(degraded, DocumentJobRecord):
                        return self._finish_selected_or_current(degraded, trace_id=trace_id)
                    # 降级后的新 IR 已成为任务权威指针；后续失败基于它继续判断，不回到旧 IR。
                    rendering, ir_file, ir_bytes, document_ir = degraded
                    attempt = rendering
                    degradation_attempts += 1
            layout_plan = build_layout_plan(document_ir)
            word_content = render_result.content
            checking = self._host.job_repository.update_document_job_if_current(
                rendering.id,
                allowed_statuses={"running"},
                allowed_stages={"rendering"},
                expected_retry_count=rendering.retry_count,
                expected_document_ir_file_id=rendering.document_ir_file_id, require_no_prepared_result=True,
                status="running",
                stage="quality_checking",
                progress=max(rendering.progress, 80),
                template_version_id=template_selection.template_version_id,
                updated_at=utc_now(),
            )
            if checking is None:
                return self._finish_selected_or_current(rendering, trace_id=trace_id)
            attempt = checking
            self._host._record_event(
                checking,
                event_type="stage_succeeded",
                stage="rendering",
                message="Word 渲染已完成。",
                payload={
                    "document_ir_file_id": ir_file.id,
                    "template_version_id": template_selection.template_version_id,
                    "block_count": len(document_ir.blocks),
                },
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - render_started_at) * 1000),
            )
            self._host._record_event(
                checking, event_type="stage_started", stage="quality_checking",
                message="Word 文档质量检查已开始。", payload={"document_ir_file_id": ir_file.id}, trace_id=trace_id,
            )
            quality_started_at = time.perf_counter()
            try:
                renderer_metadata = build_renderer_evidence(
                    document_ir, word_content, layout_plan, render_result=render_result, formula_report=render_result.formula_report,
                    image_layout_report=render_result.image_layout_report,
                    renderer_content_contract_version=render_result.renderer_content_contract_version,
                    formula_source_coverage=render_result.formula_source_coverage,
                    expected_template_version_id=template_selection.template_version_id,
                    expected_generation_policy=image_evidence.IMAGE_GENERATION_POLICY,
                )
                ensure_renderer_integrity(renderer_metadata)
            except Exception as exc:
                failed = self._host._mark_failed(
                    checking, failed_stage="quality_checking", error_code="render_failed",
                    error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                    failure_evidence=failure_policy.worker_failure_evidence(exc),
                    duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
                )
                if failed.status == "running" and failed.retry_count == checking.retry_count and failed.prepared_result is not None:
                    return self._finish_prepared_result(failed, trace_id=trace_id)
                return failed
            uploading = self._host.job_repository.update_document_job_if_current(
                checking.id, allowed_statuses={"running"}, allowed_stages={"quality_checking"},
                expected_retry_count=checking.retry_count, expected_document_ir_file_id=checking.document_ir_file_id,
                require_no_prepared_result=True, stage="uploading",
                progress=max(checking.progress, 85), updated_at=utc_now(),
            )
            if uploading is None:
                return self._finish_selected_or_current(checking, trace_id=trace_id)
            attempt = uploading
            self._host._record_event(
                uploading, event_type="stage_succeeded", stage="quality_checking",
                message="Word 文档质量检查已通过。",
                payload={"document_ir_file_id": ir_file.id, **build_renderer_event_summary(renderer_metadata)},
                trace_id=trace_id, duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
            )
            self._host._record_event(
                uploading,
                event_type="stage_started",
                stage="uploading",
                message="生成 Word 上传登记已开始。",
                payload={"template_version_id": template_selection.template_version_id},
                trace_id=trace_id,
            )
            renderer_metadata, preparation = save_report(uploading, ir_file, ir_bytes, renderer_metadata, self._host.file_service)
            publication_provenance = capture_render_publication_provenance(uploading, ir_file, document_ir, render_result,
                renderer=self.word_renderer, snapshot_service=self._host.job_resource_snapshot_service, file_service=self._host.file_service)
            renderer_metadata["publication_provenance_file_id"] = publication_provenance.id
            word_file = self._host.file_service.register_result_candidate(
                tenant_id=uploading.tenant_id,
                company_id=uploading.company_id,
                job_id=uploading.id,
                created_by=uploading.created_by,
                filename=self._result_filename(uploading),
                content=word_content,
                expires_at=preparation.docx_expires_at,
                metadata={
                    "source_file_id": uploading.source_file_id,
                    "document_ir_file_id": ir_file.id,
                    "template_version_id": template_selection.template_version_id,
                    "template_id": template_selection.template_id,
                    "template_version": template_selection.version,
                    "block_count": len(document_ir.blocks),
                    "image_asset_file_ids": uploading.image_asset_file_ids,
                    "retry_count": uploading.retry_count,
                    **renderer_metadata,
                },
            )
            verify_report(uploading, word_file, file_repository=self._host.file_repository,
                          file_service=self._host.file_service, job_repository=self._host.job_repository)
            prepared = self._host.job_repository.prepare_document_job_result(
                uploading.id, expected_retry_count=uploading.retry_count,
                expected_document_ir_file_id=ir_file.id, candidate=word_file,
            )
            if prepared is None:
                return self._finish_selected_or_current(uploading, trace_id=trace_id)
            return self._finish_prepared_result(prepared, trace_id=trace_id)
        except Exception as exc:
            failed_stage, error_code, unexpected_log_stage = failure_policy.render_failure(
                exc, attempt.stage, validating_legacy=validating_legacy,
            )
            if unexpected_log_stage is not None:
                self.logger.exception("[trace_id=%s job_id=%s stage=%s status=unexpected_error]", trace_id, job.id, unexpected_log_stage)
            failed = self._host._mark_failed(attempt, failed_stage=failed_stage, error_code=error_code,
                                       error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                                       failure_evidence=failure_policy.worker_failure_evidence(exc))
            if failed.status == "running" and failed.retry_count == attempt.retry_count and failed.prepared_result is not None:
                return self._finish_prepared_result(failed, trace_id=trace_id)
            return failed

    def _degrade_render_failure_page(
        self, job: DocumentJobRecord, ir_file: DocumentFileRecord, document_ir: DocumentIR, error: Exception,
        *, trace_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord, bytes, DocumentIR] | DocumentJobRecord | None:
        """第三批 C3：带页定位的渲染失败把该页（及表格依赖页）降级为整页图像，另存新 IR 并条件切换任务指针。

        返回 None 表示不满足降级前提，调用方按原错误失败；返回任务记录表示指针切换落败（已被并发推进）。
        """
        context = failure_policy.worker_failure_evidence(error).get("failure_context")
        rasterizer = getattr(self._host.document_ir_service, "page_rasterizer", None)
        if (not isinstance(context, dict) or context.get("source_page_index") is None or rasterizer is None
                or is_translation_document_job_mode(job.mode)
                or isinstance(error, (ApiError, OSError, MinerUError, TablePlaceholderError, DocumentIntegrityError,
                                      SoftTimeLimitExceeded))):
            return None
        page_index = context["source_page_index"]
        already = {record.get("page_index") for record in document_ir.metadata.degraded_pages}
        degraded = degradation_closure(document_ir.metadata.logical_table_groups, {page_index})
        if (degraded is None or degraded & already
                or not self._host.document_ir_service.degradation_policy.allows(len(degraded | already), len(document_ir.pages))):
            return None
        try:
            source = self._load_placeholder_source(job)
            if source.file_id != job.source_file_id or placeholder_checksum(source.content) != source.checksum_sha256:
                return None
            rasters = {page: rasterizer.rasterize(source, page) for page in sorted(degraded)}
            candidate = document_ir.model_copy(deep=True)
            reason = {"reason_codes": ["render_failed"], "operation_kind": context.get("operation_kind"),
                      "render_reason_code": context.get("reason_code")}
            removed_ids, pending = replace_degraded_pages(
                candidate, rasters, {page_index: reason}, source_pdf_sha256=source.checksum_sha256,
                dpi=getattr(rasterizer, "DPI", None), trigger="render")
            drop_degraded_table_groups(candidate, removed_ids)
            candidate = DocumentIR.model_validate(candidate.model_dump(mode="python"))
        except (TablePlaceholderError, ValueError):
            # 栅格失败或替换后 IR 不再自洽（如保留组的续表诊断指向被删片段）：放弃降级。
            return None
        raster_file_ids: list[str] = []
        for item in pending:
            image_file = self._host.file_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="image_asset", filename=f"{item.asset_id}_page.png", mime_type="image/png",
                content=item.content, object_version=f"g{job.retry_count}_{uuid4().hex}",
                metadata={"source_file_id": job.source_file_id,
                          "mineru_raw_result_file_id": ir_file.metadata.get("mineru_raw_result_file_id"),
                          "source_path": PAGE_RASTER_SOURCE_PATH, "asset_id": item.asset_id, "block_id": item.block_id,
                          "retry_count": job.retry_count, "origin": "pdf_page_raster", "page_raster": item.page_raster},
            )
            raster_file_ids.append(image_file.id)
            asset = next(asset for asset in candidate.assets if asset.id == item.asset_id)
            asset.file_id, asset.object_key = image_file.id, image_file.object_key
            asset.mime_type, asset.checksum_sha256 = image_file.mime_type, image_file.checksum_sha256
        ir_content = candidate.model_dump_json(indent=2).encode("utf-8")
        new_ir_file = self._host.file_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename=ir_file.original_filename,
            object_version=f"g{job.retry_count}_{uuid4().hex}", mime_type="application/json", content=ir_content,
            metadata={**ir_file.metadata, **self._host._document_ir_layout_metadata(candidate),
                      "degraded_from_document_ir_file_id": ir_file.id},
        )
        switched = self._host.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={"running"}, allowed_stages={"rendering"},
            expected_retry_count=job.retry_count, expected_document_ir_file_id=ir_file.id,
            require_no_prepared_result=True, document_ir_file_id=new_ir_file.id,
            image_asset_file_ids=[*job.image_asset_file_ids, *raster_file_ids], updated_at=utc_now(),
        )
        if switched is None:
            return job
        self._host._record_event(
            switched, event_type="file_registered", stage="rendering",
            message=f"第 {', '.join(str(page + 1) for page in sorted(degraded))} 页渲染失败，已按原 PDF 页面图像降级并重新渲染。",
            payload={"file_id": new_ir_file.id, "file_type": "document_ir", "document_ir_file_id": new_ir_file.id,
                     "degraded_from_document_ir_file_id": ir_file.id, "degraded_page_indexes": sorted(degraded),
                     "image_asset_file_ids": raster_file_ids, "failure_context": context},
            trace_id=trace_id,
        )
        return switched, new_ir_file, ir_content, candidate

    def _finish_selected_or_current(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        current = self._host.job_repository.get_document_job(job.id) or job
        timed_out = self._host._mark_timed_out_if_needed(current, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        if current.status == "running" and current.retry_count == job.retry_count and current.prepared_result is not None:
            return self._finish_prepared_result(current, trace_id=trace_id)
        return current

    def _finish_prepared_result(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        """receipt 后只物化同一身份；两步之间中断可由任意重投继续。"""

        current = self._host.job_repository.get_document_job(job.id) or job
        if current.status != "running" or current.retry_count != job.retry_count:
            return current
        receipt = job.prepared_result
        if receipt is None:
            raise ValueError("任务没有选定结果凭据。")
        timed_out = self._host._mark_timed_out_if_needed(job, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        try:
            validate_candidate_binding(job, receipt.file)
            word_file = self._host.file_repository.materialize_prepared_result(receipt.file)
            ir_file, final_ir, _ = self._validate_render_result_file(word_file)
            verified_report = verify_report(job, word_file, file_repository=self._host.file_repository,
                          file_service=self._host.file_service, job_repository=self._host.job_repository)
            # 恢复只核对原 receipt 的实物，不重裁图、不重渲染或更换同代身份。
            proof = word_file.metadata.get("table_placeholder_rendering")
            placeholders = decode_placeholders(final_ir, require_bound=True)
            if placeholders or proof is not None:
                if final_ir.metadata.job_id != job.id or final_ir.metadata.source_file_id != job.source_file_id:
                    raise TablePlaceholderError("table_placeholder_integrity_failed")
                self._verify_placeholder_dependencies(job, final_ir)
                for file in (ir_file, word_file):
                    self._ensure_placeholder_file_current(job, file, "table_placeholder_integrity_failed")
            preview_job, preview_finished = self.word_preview_service.ensure_initial(current, trace_id=trace_id)
            if not preview_finished:
                return self._host._mark_timed_out_if_needed(preview_job, trace_id=trace_id) or preview_job
            if verified_report is not None:
                recheck_verified_report(verified_report, file_repository=self._host.file_repository,
                                        job_repository=self._host.job_repository)
            completed = self._host.job_repository.update_document_job_if_current(
                job.id, allowed_statuses={"running"}, allowed_stages={"uploading"},
                expected_retry_count=receipt.generation, expected_document_ir_file_id=receipt.document_ir_file_id,
                expected_prepared_result_file_id=word_file.id, status="succeeded", stage="completed",
                progress=100, result_file_id=word_file.id, completed_at=utc_now(), updated_at=utc_now(),
            )
        except Exception as exc:
            return self._host._mark_failed(job,
                failed_stage="quality_checking" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "uploading",
                error_code="render_failed" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "oss_failed",
                error_message=(failure_policy.worker_failure_message(exc) if isinstance(exc, (TablePlaceholderError, TableEvidenceError, DocumentIntegrityError)) or
                    "table_placeholder_rendering" not in receipt.file.metadata else "表格占位结果文件读取或完整性校验失败。"),
                trace_id=trace_id, expected_prepared_result_file_id=receipt.file.id)
        if completed is None:
            current = self._host.job_repository.get_document_job(job.id) or job
            return self._host._mark_timed_out_if_needed(current, trace_id=trace_id) or current
        self._host._record_event(completed, event_type="file_registered", stage="uploading", message="生成 Word 已保存。",
                           payload={"file_id": word_file.id, "file_type": word_file.file_type,
                                    **build_renderer_event_summary(word_file.metadata)}, trace_id=trace_id)
        self._host._record_event(completed, event_type="stage_succeeded", stage="completed", message="文档任务已完成。",
                           payload={"result_file_id": word_file.id, "template_version_id": completed.template_version_id},
                           trace_id=trace_id)
        return completed

    def _validate_render_result_file(self, record: DocumentFileRecord) -> tuple[DocumentFileRecord, DocumentIR, bytes]:
        """先核实原件及绑定 IR 的实物，再由 renderer 按保存的版本认证内容。"""

        if (record.file_type != "generated_word" or record.status != "uploaded"
                or record.expires_at is not None and record.expires_at <= utc_now()
                or record.expires_at is None and any(key in record.metadata for key in (
                    "renderer_content_contract_version", "formula_source_coverage"))):
            raise ValueError("主 DOCX 的类型、状态或保留期无效。")
        content = self._host.file_service.read_file_content(record)
        if record.size_bytes != len(content) or record.checksum_sha256 != f"sha256:{hashlib.sha256(content).hexdigest()}":
            raise ValueError("主 DOCX 字节与 SHA-256 描述不一致。")
        ir_id = record.metadata.get("document_ir_file_id")
        if not isinstance(ir_id, str) or not ir_id:
            raise ValueError("主 DOCX 缺少原始 IR 绑定。")
        ir_file = self._host._get_uploaded_file(ir_id)
        if ((ir_file.tenant_id, ir_file.company_id, ir_file.job_id)
                != (record.tenant_id, record.company_id, record.job_id) or ir_file.file_type != "document_ir"
                or ir_file.expires_at is not None and ir_file.expires_at <= utc_now()):
            raise ValueError("主 DOCX 的原始 IR 与文件归属不一致。")
        ir_bytes = self._host.file_service.read_file_content(ir_file)
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

    def _get_document_ir_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        if job.document_ir_file_id is None:
            raise FileNotFoundError(f"任务缺少权威最终 DocumentIR 指针: {job.id}")
        record = self._host._get_uploaded_file(job.document_ir_file_id)
        if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                or record.file_type != "document_ir"):
            raise ValueError("最终 DocumentIR 文件与任务归属不一致。")
        return record

    def _get_existing_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord | None:
        if job.result_file_id:
            record = self._host._get_uploaded_file(job.result_file_id)
            if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                    or record.file_type != "generated_word"
                    or (record.expires_at is not None and record.expires_at <= utc_now())):
                raise ValueError("任务指定的结果文件不属于该任务的可用主 DOCX。")
            if (any(key in record.metadata for key in ("renderer_content_contract_version", "formula_source_coverage",
                    "formula_report", "formula_summary"))
                    or image_evidence.IMAGE_EVIDENCE_KEYS.intersection(record.metadata)
                    or has_evidence(record.metadata)):
                self._validate_render_result_file(record)
            elif image_evidence.has_image_markers(self._host.file_service.read_file_content(record)):
                raise ValueError("主 DOCX 含图片布局标记但缺少报告。")
            # 显式历史指针原本允许无报告、无 IR 绑定；仅该已验收路径保留原门。
            if has_evidence(record.metadata):
                verify_report(job, record, file_repository=self._host.file_repository,
                              file_service=self._host.file_service, job_repository=self._host.job_repository)
            return record
        candidates = [
            file for file in self._host.file_repository.list_document_files()
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
        self._validate_render_result_file(record)
        if has_evidence(record.metadata):
            verify_report(job, record, file_repository=self._host.file_repository,
                          file_service=self._host.file_service, job_repository=self._host.job_repository)
        return record

    def _ensure_placeholder_attempt_current(self, job: DocumentJobRecord, error_code: str) -> None:
        """慢读两侧核对仍在执行的同代/最终 IR；质量摘要等无关并发更新不影响快照。"""
        current = self._host.job_repository.get_document_job(job.id)
        if (current is None or current.status != "running" or current.deleted_at is not None
                or current.archived_at is not None or current.retry_count != job.retry_count
                or current.document_ir_file_id != job.document_ir_file_id
                or (current.tenant_id, current.company_id, current.source_file_id, current.source_job_id) !=
                   (job.tenant_id, job.company_id, job.source_file_id, job.source_job_id)):
            raise TablePlaceholderError(error_code)

    def _ensure_placeholder_file_current(self, job: DocumentJobRecord, file: DocumentFileRecord, error_code: str) -> None:
        """与 IR-206 相同：按 ID 重取并比较完整描述，不把有 file_id 当作当前可读。"""
        if (self._host.file_repository.get_document_file(file.id) != file or file.status != "uploaded"
                or file.expires_at is not None and file.expires_at <= utc_now()):
            raise TablePlaceholderError(error_code)
        self._ensure_placeholder_attempt_current(job, error_code)

    def _read_current_placeholder_file(self, job: DocumentJobRecord, file: DocumentFileRecord,
                                       error_code: str = "table_placeholder_integrity_failed") -> bytes:
        """字节读取前后核验同一描述、生命周期、任务快照与实际 hash；错误不带存储定位。"""
        snapshot = file.model_copy(deep=True)
        self._ensure_placeholder_file_current(job, snapshot, error_code)
        try:
            content = self._host.file_service.read_file_content(snapshot)
        except Exception:
            raise TablePlaceholderError(error_code) from None
        self._ensure_placeholder_file_current(job, snapshot, error_code)
        if len(content) != snapshot.size_bytes or placeholder_checksum(content) != snapshot.checksum_sha256:
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return content

    def _get_placeholder_source_file(self, job: DocumentJobRecord,
                                      error_code: str = "table_placeholder_source_unavailable") -> DocumentFileRecord:
        """裁图或未完成 receipt 只认绑定源；clone 沿既有同源父链核验归属。"""
        file = self._host.file_repository.get_document_file(job.source_file_id)
        if (file is None or file.file_type != "source_pdf" or file.status != "uploaded"
                or (file.tenant_id, file.company_id) != (job.tenant_id, job.company_id)
                or file.expires_at is not None and file.expires_at <= utc_now()
                or not file.checksum_sha256):
            raise TablePlaceholderError(error_code)
        owner = job
        seen = set()
        while file.job_id != owner.id:
            if owner.id in seen or owner.source_job_id is None:
                raise TablePlaceholderError(error_code)
            seen.add(owner.id)
            owner = self._host.job_repository.get_document_job(owner.source_job_id)
            if (owner is None or owner.source_file_id != file.id
                    or (owner.tenant_id, owner.company_id) != (job.tenant_id, job.company_id)):
                raise TablePlaceholderError(error_code)
        return file

    def _load_placeholder_source(self, job: DocumentJobRecord) -> PdfCropSource:
        file = self._get_placeholder_source_file(job)
        content = self._read_current_placeholder_file(job, file, "table_placeholder_source_unavailable")
        return PdfCropSource(file.id, file.checksum_sha256, content)

    def _read_placeholder_asset(self, job: DocumentJobRecord, document: DocumentIR, asset: DocumentIRAsset, binding):
        """仅显式消费的占位图按当前 ID 读取；来源 attempt 可早于翻译 retry，不能硬套最新代。"""
        file = self._host.file_repository.get_document_file(asset.file_id)
        try:
            provenance = TableReferenceProvenance.model_validate(document.metadata.mineru_validation_input)
        except ValueError:
            raise TablePlaceholderError("table_placeholder_integrity_failed") from None
        expected = {"asset_id": asset.id, "source_file_id": job.source_file_id,
                    "fragment_id": binding.fragment_id, "retry_count": provenance.retry_count}
        if binding.source_kind == "mineru_reference":
            reference = next(item for item in decode_table_references(document, require_bound=True)
                             if item.fragment.fragment_id == binding.fragment_id)
            expected.update(asset_role=TABLE_REFERENCE_ROLE, block_id=reference.block_id,
                logical_group_id=reference.logical_group_id, source_path=asset.source_path,
                mineru_raw_result_file_id=provenance.mineru_raw_result_file_id)
        else:
            expected.update(asset_role="table_placeholder", source_pdf_sha256=binding.source_pdf_sha256)
        if (file is None or file.file_type != "image_asset" or file.mime_type != asset.mime_type
                or (file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.checksum_sha256 != asset.checksum_sha256 or file.object_key != asset.object_key
                or not provenance.retry_count <= job.retry_count
                or type(file.metadata.get("retry_count")) is not int
                or any(file.metadata.get(key) != value for key, value in expected.items())):
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return file, self._read_current_placeholder_file(job, file)

    def _verify_placeholder_dependencies(self, job: DocumentJobRecord, document: DocumentIR) -> None:
        """未完成 receipt 复核原绑定依赖；只读取原件，不重渲染、重裁图或替换身份。"""
        bindings = decode_placeholders(document, require_bound=True)
        if not bindings:
            return
        source = self._get_placeholder_source_file(job, "table_placeholder_integrity_failed")
        snapshots = [source]
        crop_hashes = {item.source_pdf_sha256 for item in bindings if item.source_kind == "source_pdf_crop"}
        if crop_hashes:
            self._read_current_placeholder_file(job, source)
            if crop_hashes != {source.checksum_sha256}:
                raise TablePlaceholderError("table_placeholder_integrity_failed")
        assets = {asset.id: asset for asset in document.assets}
        for binding in bindings:
            file, _ = self._read_placeholder_asset(job, document, assets[binding.asset_ref], binding)
            snapshots.append(file)
        # 后续图片慢读也可能使前面的源/图片失效；所有 I/O 完成后再次对账。
        for file in snapshots:
            self._ensure_placeholder_file_current(job, file, "table_placeholder_integrity_failed")

    def _build_image_loader(self, job: DocumentJobRecord, document_ir: DocumentIR) -> Callable[[DocumentIRAsset], bytes | None]:
        bindings = {item.asset_ref: item for item in decode_placeholders(document_ir, require_bound=True)}
        image_files = {
            file.id: file
            for file in self._host.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "image_asset" and file.status == "uploaded"
        }

        def load_image(asset: DocumentIRAsset) -> bytes | None:
            if asset.id in bindings:
                return self._read_placeholder_asset(job, document_ir, asset, bindings[asset.id])[1]
            if asset.id.startswith(("table-reference:", "table-placeholder:")):
                # 普通 QA 参考图不能借普通 image loader 绕过显式占位消费及其来源核验。
                raise TablePlaceholderError("table_placeholder_integrity_failed")
            if asset.file_id is None:
                return None
            record = image_files.get(asset.file_id)
            return self._host.file_service.read_file_content(record) if record is not None else None

        return load_image

    def _result_filename(self, job: DocumentJobRecord) -> str:
        source_file = self._host.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            return f"{job.id}.docx"
        source_stem = Path(source_file.original_filename).stem.strip() or job.id
        return f"{source_stem}.docx"
