"""Word 渲染执行：渲染编排、页面降级与质量检查；占位图来源与结果收尾见 render_placeholders / render_result。"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded

from app.clients.mineru_client import MinerUError
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.execution_support import DocumentJobLifecycle, document_ir_layout_metadata
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.publication_provenance import capture_render_publication_provenance
from app.domains.document_jobs.render_placeholders import RenderPlaceholderSource
from app.domains.document_jobs.render_result import WordResultFinalizer
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.table_evidence import save_report, verify_report
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.resource_snapshots import (
    JobResourceSnapshotError, JobResourceSnapshotService, MaterializedRenderResources,
)
from app.domains.resources.models import utc_now
from app.domains.templates.read_service import TemplateVersionSelection
from app.domains.translation.modes import is_translation_document_job_mode
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.page_degradation import (
    PAGE_RASTER_SOURCE_PATH,
    degradation_closure,
    drop_degraded_table_groups,
    replace_degraded_pages,
)
from app.services.document_ir.table_placeholder import TablePlaceholderError, checksum as placeholder_checksum
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer, image_evidence
from app.services.renderer.layout_plan import build_layout_plan
from app.services.renderer.render_event_summary import build_renderer_event_summary
from app.services.renderer.render_evidence import build_renderer_evidence
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.renderer.resource_identity import RenderResourceInputs


class WordRenderExecution:
    """Word 渲染执行：由 DocumentJobExecutionService 构造并持有，负责渲染编排与页面降级。

    任务级状态推进与事件记录统一经注入的 DocumentJobLifecycle 完成；settings、job_repository 等共用依赖
    与宿主引用同一对象，在构造时显式注入。

    占位图来源核验由 ``placeholders``（RenderPlaceholderSource）负责；结果身份认证与上传收尾由
    ``results``（WordResultFinalizer）负责。宿主只调用 render_and_save_word 与 placeholders.load_source。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        document_ir_service: MinerUToDocumentIRService,
        job_resource_snapshot_service: JobResourceSnapshotService | None,
        lifecycle: DocumentJobLifecycle,
        template_read_service: Any,
        word_renderer: DocumentIRWordRenderer,
        word_preview_service: DocumentJobPreviewService,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.document_ir_service = document_ir_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.lifecycle = lifecycle
        self.template_read_service = template_read_service
        self.word_renderer = word_renderer
        self.logger = logging.getLogger("business")
        self.placeholders = RenderPlaceholderSource(
            job_repository=job_repository, file_repository=file_repository, file_service=file_service)
        self.results = WordResultFinalizer(
            job_repository=job_repository, file_repository=file_repository, file_service=file_service,
            lifecycle=lifecycle, word_preview_service=word_preview_service, placeholders=self.placeholders)

    def _resolve_render_resources(
        self, job: DocumentJobRecord,
    ) -> tuple[TemplateVersionSelection, MaterializedRenderResources | None]:
        raw = job.request_snapshot.get("resources")
        if raw is None:
            return self.template_read_service.resolve_template_version(job.template_version_id), None
        if not isinstance(raw, dict):
            raise JobResourceSnapshotError("任务资源快照格式非法。", category="conflict")
        service = self.job_resource_snapshot_service
        if service is None:
            raise JobResourceSnapshotError(
                "当前 Worker 无法认证任务资源快照。", category="service_unavailable", code="resource_snapshot_unavailable",
            )
        try:
            # 渲染只需要模板和格式规则；direct 的历史惰性翻译字段不参与。
            snapshot = JobResourceSnapshot.model_validate({
                key: raw[key] for key in ("template", "term_rule_set", "term_rule_department_id") if key in raw
            })
        except ValueError:
            raise JobResourceSnapshotError("任务资源快照格式非法。", category="conflict") from None
        template = snapshot.template
        if template is None:
            raise JobResourceSnapshotError(
                "任务资源快照缺少模板版本。", category="conflict", code="resource_snapshot_missing_template",
            )
        if (
            not template.version.isdecimal() or job.template_version_id != f"{template.resource_id}@{template.version}"
        ):
            raise JobResourceSnapshotError(
                "任务模板版本与绑定资源不一致。", category="conflict", code="resource_snapshot_template_version_mismatch",
            )
        version = int(template.version)
        try:
            self.template_read_service.resolve_template_render_state(template.resource_id, version)
        except (ValueError, FileNotFoundError):
            raise JobResourceSnapshotError(
                "任务绑定的模板版本未启用。", category="conflict", code="resource_snapshot_invalid_status",
            ) from None
        resources = service.materialize_render_resources(snapshot, build_job_paths(self.settings.data_path, job.id))
        return TemplateVersionSelection(
            template_id=template.resource_id,
            version=version,
            template_version_id=job.template_version_id,
            template_path=resources.template_path,
            layout_config_path=resources.layout_config_path,
            render_policy={},
        ), resources

    def render_and_save_word(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        attempt = job
        validating_legacy = False
        try:
            current = self.job_repository.get_document_job(job.id) or job
            if current.retry_count != job.retry_count or current.status != "running":
                return current
            if current.prepared_result is not None:
                return self.results.finish_prepared_result(current, trace_id=trace_id)
            # 明确历史指针优先保留；legacy 扫描必须唯一且可验证。
            if job.stage != "quality_checking":
                validating_legacy = True
                existing_result = self.results.get_existing_result_file(job)
                validating_legacy = False
                if existing_result is not None:
                    uploading = self.job_repository.update_document_job_if_current(
                        job.id, allowed_statuses={"running"}, allowed_stages={"rendering", "uploading"},
                        expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                        require_no_prepared_result=True, stage="uploading", updated_at=utc_now(),
                    )
                    if uploading is None:
                        return self.results.finish_selected_or_current(job, trace_id=trace_id)
                    if job.result_file_id is not None:
                        return self.lifecycle.mark_succeeded(uploading, trace_id=trace_id)
                    prepared = self.job_repository.prepare_document_job_result(
                        job.id, expected_retry_count=job.retry_count,
                        expected_document_ir_file_id=job.document_ir_file_id, candidate=existing_result,
                    )
                    if prepared is None:
                        return self.results.finish_selected_or_current(job, trace_id=trace_id)
                    return self.results.finish_prepared_result(prepared, trace_id=trace_id)
            attempt = job
            recovery_from = job.stage if job.stage in {"quality_checking", "uploading"} else None
            rendering = job
            if recovery_from is not None:
                rendering = self.job_repository.update_document_job_if_current(
                    job.id, allowed_statuses={"running"}, allowed_stages={recovery_from},
                    expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                    require_no_prepared_result=True, stage="rendering", updated_at=utc_now(),
                )
                if rendering is None:
                    return self.results.finish_selected_or_current(job, trace_id=trace_id)
            attempt = rendering
            self.lifecycle.record_event(
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

            ir_file = self.results.get_document_ir_file(rendering)
            try:
                ir_bytes = self.file_service.read_file_content(ir_file)
                document_ir = DocumentIR.model_validate_json(ir_bytes)
            except ValueError:
                raise TablePlaceholderError("table_placeholder_integrity_failed") from None
            template_selection, render_resources = self._resolve_render_resources(rendering)
            verified_inputs = (
                RenderResourceInputs(
                    template_docx=render_resources.template_content,
                    template_config=render_resources.layout_config_content,
                    symbol_rules=render_resources.subscript_content,
                )
                if render_resources is not None else None
            )

            def render(job: DocumentJobRecord, document: DocumentIR):
                return self.word_renderer.render_to_result(
                    document,
                    template_path=template_selection.template_path,
                    config_path=template_selection.layout_config_path,
                    image_loader=self.placeholders.build_image_loader(job, document),
                    options=DocumentIRRenderOptions(
                        subscript_config_path=(
                            render_resources.subscript_config_path
                            if render_resources is not None else self.settings.subscript_config_path
                        ),
                        document_language=document.metadata.document_language,
                        template_version_id=template_selection.template_version_id,
                        resource_inputs=verified_inputs,
                        layout_asset_dir=render_resources.layout_asset_dir if render_resources is not None else None,
                    ),
                )

            degradation_attempts = 0
            while True:
                try:
                    render_result = render(rendering, document_ir)
                    break
                except Exception as exc:
                    if degradation_attempts >= self.settings.render_degradation_max_attempts:
                        raise
                    degraded = self._degrade_render_failure_page(rendering, ir_file, document_ir, exc, trace_id=trace_id)
                    if degraded is None:
                        raise
                    if isinstance(degraded, DocumentJobRecord):
                        return self.results.finish_selected_or_current(degraded, trace_id=trace_id)
                    # 降级后的新 IR 已成为任务权威指针；后续失败基于它继续判断，不回到旧 IR。
                    rendering, ir_file, ir_bytes, document_ir = degraded
                    attempt = rendering
                    degradation_attempts += 1
            if verified_inputs is not None and (
                render_result.resource_inputs is None
                or replace(render_result.resource_inputs, logo=None) != verified_inputs
            ):
                raise JobResourceSnapshotError("渲染未使用本次认证的任务资源。", category="conflict")
            layout_plan = build_layout_plan(document_ir)
            word_content = render_result.content
            checking = self.job_repository.update_document_job_if_current(
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
                return self.results.finish_selected_or_current(rendering, trace_id=trace_id)
            attempt = checking
            self.lifecycle.record_event(
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
            self.lifecycle.record_event(
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
                failed = self.lifecycle.mark_failed(
                    checking, failed_stage="quality_checking", error_code="render_failed",
                    error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                    failure_evidence=failure_policy.worker_failure_evidence(exc),
                    duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
                )
                if failed.status == "running" and failed.retry_count == checking.retry_count and failed.prepared_result is not None:
                    return self.results.finish_prepared_result(failed, trace_id=trace_id)
                return failed
            uploading = self.job_repository.update_document_job_if_current(
                checking.id, allowed_statuses={"running"}, allowed_stages={"quality_checking"},
                expected_retry_count=checking.retry_count, expected_document_ir_file_id=checking.document_ir_file_id,
                require_no_prepared_result=True, stage="uploading",
                progress=max(checking.progress, 85), updated_at=utc_now(),
            )
            if uploading is None:
                return self.results.finish_selected_or_current(checking, trace_id=trace_id)
            attempt = uploading
            self.lifecycle.record_event(
                uploading, event_type="stage_succeeded", stage="quality_checking",
                message="Word 文档质量检查已通过。",
                payload={"document_ir_file_id": ir_file.id, **build_renderer_event_summary(renderer_metadata)},
                trace_id=trace_id, duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
            )
            self.lifecycle.record_event(
                uploading,
                event_type="stage_started",
                stage="uploading",
                message="生成 Word 上传登记已开始。",
                payload={"template_version_id": template_selection.template_version_id},
                trace_id=trace_id,
            )
            renderer_metadata, preparation = save_report(uploading, ir_file, ir_bytes, renderer_metadata, self.file_service)
            publication_provenance = capture_render_publication_provenance(
                uploading, ir_file, render_result,
                resources_publishable=render_resources is not None and render_resources.publishable,
                file_service=self.file_service,
            )
            renderer_metadata["publication_provenance_file_id"] = publication_provenance.id
            word_file = self.file_service.register_result_candidate(
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
            verify_report(uploading, word_file, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
            prepared = self.job_repository.prepare_document_job_result(
                uploading.id, expected_retry_count=uploading.retry_count,
                expected_document_ir_file_id=ir_file.id, candidate=word_file,
            )
            if prepared is None:
                return self.results.finish_selected_or_current(uploading, trace_id=trace_id)
            return self.results.finish_prepared_result(prepared, trace_id=trace_id)
        except Exception as exc:
            failed_stage, error_code, unexpected_log_stage = failure_policy.render_failure(
                exc, attempt.stage, validating_legacy=validating_legacy,
            )
            if unexpected_log_stage is not None:
                self.logger.exception("[trace_id=%s job_id=%s stage=%s status=unexpected_error]", trace_id, job.id, unexpected_log_stage)
            failed = self.lifecycle.mark_failed(attempt, failed_stage=failed_stage, error_code=error_code,
                                       error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                                       failure_evidence=failure_policy.worker_failure_evidence(exc))
            if failed.status == "running" and failed.retry_count == attempt.retry_count and failed.prepared_result is not None:
                return self.results.finish_prepared_result(failed, trace_id=trace_id)
            return failed

    def _degrade_render_failure_page(
        self, job: DocumentJobRecord, ir_file: DocumentFileRecord, document_ir: DocumentIR, error: Exception,
        *, trace_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord, bytes, DocumentIR] | DocumentJobRecord | None:
        """第三批 C3：带页定位的渲染失败把该页（及表格依赖页）降级为整页图像，另存新 IR 并条件切换任务指针。

        返回 None 表示不满足降级前提，调用方按原错误失败；返回任务记录表示指针切换落败（已被并发推进）。
        """
        context = failure_policy.worker_failure_evidence(error).get("failure_context")
        rasterizer = getattr(self.document_ir_service, "page_rasterizer", None)
        if (not isinstance(context, dict) or context.get("source_page_index") is None or rasterizer is None
                or is_translation_document_job_mode(job.mode)
                or isinstance(error, (ApplicationError, OSError, MinerUError, TablePlaceholderError, DocumentIntegrityError,
                                      SoftTimeLimitExceeded))):
            return None
        page_index = context["source_page_index"]
        already = {record.get("page_index") for record in document_ir.metadata.degraded_pages}
        degraded = degradation_closure(document_ir.metadata.logical_table_groups, {page_index})
        if (degraded is None or degraded & already
                or not self.document_ir_service.degradation_policy.allows(len(degraded | already), len(document_ir.pages))):
            return None
        try:
            source = self.placeholders.load_source(job)
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
            image_file = self.file_service.register_generated_content(
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
        new_ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename=ir_file.original_filename,
            object_version=f"g{job.retry_count}_{uuid4().hex}", mime_type="application/json", content=ir_content,
            metadata={**ir_file.metadata, **document_ir_layout_metadata(candidate),
                      "degraded_from_document_ir_file_id": ir_file.id},
        )
        switched = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={"running"}, allowed_stages={"rendering"},
            expected_retry_count=job.retry_count, expected_document_ir_file_id=ir_file.id,
            require_no_prepared_result=True, document_ir_file_id=new_ir_file.id,
            image_asset_file_ids=[*job.image_asset_file_ids, *raster_file_ids], updated_at=utc_now(),
        )
        if switched is None:
            return job
        self.lifecycle.record_event(
            switched, event_type="file_registered", stage="rendering",
            message=f"第 {', '.join(str(page + 1) for page in sorted(degraded))} 页渲染失败，已按原 PDF 页面图像降级并重新渲染。",
            payload={"file_id": new_ir_file.id, "file_type": "document_ir", "document_ir_file_id": new_ir_file.id,
                     "degraded_from_document_ir_file_id": ir_file.id, "degraded_page_indexes": sorted(degraded),
                     "image_asset_file_ids": raster_file_ids, "failure_context": context},
            trace_id=trace_id,
        )
        return switched, new_ir_file, ir_content, candidate

    def _result_filename(self, job: DocumentJobRecord) -> str:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            return f"{job.id}.docx"
        source_stem = Path(source_file.original_filename).stem.strip() or job.id
        return f"{source_stem}.docx"
