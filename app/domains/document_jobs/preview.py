"""选定主 DOCX 后的预览编排；不重新运行解析、翻译或 renderer。

证据读取与存储异常归一化在 preview_evidence.py；本模块只负责领取、生成、登记与状态提交。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from uuid import UUID, uuid4

from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.domains.document_jobs.preview_evidence import (
    preview_storage_io,
    artifact_descriptor,
    frozen_page_policy,
    page_quality_binding,
    read_page_quality,
    page_quality_contribution,
    mapping_source,
    mapping_binding,
    artifact_evidence,
    observe_current_preview,
)
from app.domains.document_jobs.preview_state import (
    PreviewClaimRequest,
    PreviewRetryResult,
    page_quality_context_sha256,
)
from app.domains.files.result_registration import ensure_result_descriptor_matches
from app.domains.resources.models import utc_now
from app.services.preview.models import (
    PreviewFailure,
    PreviewPolicy,
    PreviewResult,
    sha256,
    validate_docx,
    validate_result,
)
from app.services.preview.page_mapping import build_page_mapping, unavailable_mapping
from app.services.preview.page_quality import policy_sha256, build_page_quality_run
from app.services.preview.provider import WordPreviewProvider
from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider


class DocumentJobPreviewService:
    """仓储负责原子身份与预算，文件服务负责追加对象；本服务只编排锁外 I/O。"""

    def __init__(self, settings, job_repository, event_repository, file_repository, file_service,
                 provider: WordPreviewProvider | None = None, audit_service=None, observer=None):
        self.settings, self.job_repository, self.event_repository = settings, job_repository, event_repository
        self.file_repository, self.file_service = file_repository, file_service
        self.provider = provider or SandboxWordPreviewProvider(
            backend=settings.word_preview_backend, launcher=settings.word_preview_launcher,
            profile_path=settings.word_preview_profile_path, profile_id=settings.word_preview_profile_id,
            profile_sha256=settings.word_preview_profile_sha256)
        self.observer = observer
        self.audit_service = audit_service
        self.logger = logging.getLogger("business")

    def ensure_initial(self, job: DocumentJobRecord, *, trace_id: str | None = None) -> tuple[DocumentJobRecord, bool]:
        # 缺快照的历史任务不自动回填或运行。
        if "word_preview" not in job.request_snapshot:
            return job, True
        current, completed, _ = self._run(job, request_key="initial", requested_by=job.created_by, reason="initial",
                         independent=False, resume=True, trace_id=trace_id)
        return current, completed

    def retry(self, job: DocumentJobRecord, *, user, reason: str, request_id: str,
              trace_id: str | None = None) -> PreviewRetryResult:
        reason = reason.strip()
        if not reason or len(reason) > 1000:
            raise ApplicationError("invalid_request", "预览重试必须提供 1..1000 字的原因。")
        try:
            key = str(UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ApplicationError("invalid_request", "预览重试 request ID 必须是 UUID。") from None
        if (job.status != "succeeded" or job.stage != "completed" or job.prepared_result is None
                or job.result_file_id != job.prepared_result.file.id or job.deleted_at is not None
                or job.archived_at is not None or job.delivery_status == "published"
                or "word_preview" not in job.request_snapshot):
            raise ApplicationError("conflict", "当前任务或主件不支持预览单独重试。")
        try:
            result, _, run = self._run(job, request_key=key, requested_by=user.id, reason=reason,
                                  independent=True, resume=False, trace_id=trace_id, actor=user)
            available = False
            state = result.word_preview_state
            if run is not None and run.status == "succeeded" and state is not None and state.current_run.run_id == run.run_id:
                observation = observe_current_preview(result, self.file_repository, self.file_service)
                available = observation.available
            return PreviewRetryResult(job=result, run=run, available=available)
        except ValueError as exc:
            raise ApplicationError("conflict", str(exc)) from None

    def _source(self, job: DocumentJobRecord):
        receipt = job.prepared_result
        if receipt is None:
            raise ValueError("预览缺少当前主件凭据。")
        with preview_storage_io():
            file = self.file_repository.get_document_file(receipt.file.id)
        if (file is None or file.status != "uploaded" or file.expires_at is None or file.expires_at <= utc_now()):
            raise ValueError("预览主件 metadata 与选定凭据不一致或已失效。")
        ensure_result_descriptor_matches(file, receipt.file)
        with preview_storage_io():
            content = self.file_service.read_file_content(file)
        if len(content) != receipt.file.size_bytes or sha256(content) != receipt.file.checksum_sha256:
            raise ValueError("选定主 DOCX 字节与凭据不一致。")
        return file, content

    def _run(self, job, *, request_key, requested_by, reason, independent, resume, trace_id, actor=None):
        policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
        page_policy = frozen_page_policy(job)
        page_hash = policy_sha256(page_policy) if page_policy is not None and page_policy.enabled else None
        actual_context = page_quality_context_sha256(job) if page_hash is not None else None
        file, docx = self._source(job)
        fingerprint = sha256(json.dumps({"tenant": job.tenant_id, "company": job.company_id, "job": job.id,
            "generation": job.retry_count, "result": file.id, "sha256": file.checksum_sha256,
            "profile": policy.profile_sha256, "action": "retry" if independent else "initial",
            **({"page_quality_policy_sha256": page_hash, "page_quality_context_sha256": actual_context} if page_hash is not None else {}),
            "actor": requested_by, "reason_sha256": sha256(reason.encode())}, sort_keys=True).encode())
        request = PreviewClaimRequest(generation=job.retry_count, result_file_id=file.id, docx_sha256=file.checksum_sha256,
            policy=policy, page_quality_policy_sha256=page_hash, page_quality_context_sha256=actual_context, request_key=request_key, request_fingerprint=fingerprint, requested_by=requested_by,
            reason_sha256=sha256(reason.encode()), independent=independent, resume=resume)
        while True:
            # 历史key交由锁内核验指纹和完成证据；当前key或新key才提前观测最新current。
            with preview_storage_io():
                latest = self.job_repository.get_document_job(job.id) or job
            observation = None
            state = latest.word_preview_state
            if state is not None and (request_key == state.current_request_key or request_key not in state.runs_by_request_key):
                selected = state.current_run
                if selected.manifest_file_id is not None and selected.status in {"succeeded", "failed", "unavailable"}:
                    observation = observe_current_preview(latest, self.file_repository, self.file_service,
                        check_page_quality=page_hash is not None and request_key not in state.runs_by_request_key)
            with preview_storage_io():
                claim = self.job_repository.claim_document_job_preview(job.id, request=request, observation=observation)
            if claim.disposition == "stale":
                if independent:
                    raise ValueError("预览来源、配置或任务状态已改变。")
                return claim.job, False, claim.run
            if claim.disposition == "busy":
                return claim.job, False, claim.run
            if claim.disposition == "storage_failed":
                raise PreviewFailure("preview_storage_failed")
            if claim.disposition not in {"claimed", "finalizing"}:
                # 主执行只接受当前attempt已留证的终态，文件仓储仍在锁外复查。
                if not independent and claim.run is not None:
                    confirmed = observe_current_preview(claim.job, self.file_repository, self.file_service)
                    if not confirmed.available:
                        raise PreviewFailure("preview_storage_failed")
                return claim.job, True, claim.run
            current = claim.job
            state, run = current.word_preview_state, current.word_preview_state.current_run
            if independent and run.attempt_count == 1:
                self._event(current, "preview_retry_requested", trace_id=trace_id)
                if self.audit_service is not None and actor is not None:
                    from app.domains.audit.models import ActorContext
                    with preview_storage_io():
                        self.audit_service.record(actor=ActorContext(actor_id=actor.id, actor_role=actor.role, source="jwt"),
                            action="document_job.word_preview_retry", target_type="document_job", target_id=job.id,
                            trace_id=trace_id or "word_preview", details={"run_id": run.run_id, "generation": job.retry_count})
            self._event(current, "preview_started", trace_id=trace_id)
            started = time.monotonic()
            output, error = None, None
            observed, observation_reason = None, None
            attempt_deadline = min(run.run_deadline_at, run.lease_expires_at,
                                   current.updated_at + timedelta(seconds=policy.timeout_seconds))
            try:
                if claim.disposition == "finalizing":
                    raise PreviewFailure("preview_timeout")
                if policy.backend == "disabled":
                    raise PreviewFailure("preview_disabled")
                validate_docx(docx, policy)
                remaining = max(0.001, (run.run_deadline_at - utc_now()).total_seconds())
                if page_hash is not None:
                    remaining = min(page_policy.render_budget_seconds,
                        (attempt_deadline - utc_now()).total_seconds()
                        - page_policy.observe_budget_seconds - page_policy.registration_budget_seconds)
                if remaining <= 0:
                    raise PreviewFailure("preview_timeout")
                call_policy = policy.model_copy(update={"timeout_seconds": min(policy.timeout_seconds, remaining),
                                                        "deadline_seconds": remaining})
                output = self.provider.render(docx, policy=call_policy)
                if not isinstance(output, PreviewResult):
                    raise PreviewFailure("preview_output_invalid")
                validate_result(output, policy)
            except PreviewFailure as exc:
                error = exc
            except Exception:
                error = PreviewFailure("preview_unexpected_error")
                self.logger.error("[job_id=%s stage=%s error_code=preview_unexpected_error] 预览 Provider 发生未分类异常。", job.id, job.stage)
            if output is not None and error is None and page_hash is not None:
                observed, observation_reason = self._observe_page_quality(output, page_policy, policy, attempt_deadline, job_id=job.id)
            # Provider结束后再次CAS；任何PDF/page/失败manifest写入之前都必须已进入登记。
            with preview_storage_io():
                registering = self.job_repository.begin_document_job_preview_registration(
                    job.id, request=request, revision=state.revision, lease_token=claim.lease_token,
                    attempt=run.attempt_count)
            if registering is None:
                with preview_storage_io():
                    return self.job_repository.get_document_job(job.id) or current, False, run
            current = registering
            state, run = current.word_preview_state, current.word_preview_state.current_run
            evidence, descriptors = {}, {}
            if output is not None and error is None:
                # 任一对象或 metadata 不可确认均显式传播，不能降级为可成功收尾的预览失败。
                pdf = self._register(current, file, "word_preview_pdf", "preview.pdf", output.pdf, "application/pdf", **({"deadline": attempt_deadline} if page_hash else {}))
                pages = [self._register(current, file, "word_preview_page", f"page-{page.page_index:06d}.png",
                                        page.content, "image/png", **({"deadline": attempt_deadline} if page_hash else {})) for page in output.pages]
                descriptors = {"pdf": artifact_descriptor(pdf), "pages": [
                    {**artifact_descriptor(file), "page_index": page.page_index, "width": page.width, "height": page.height}
                    for file, page in zip(pages, output.pages, strict=True)]}
                evidence = {"provider_id": output.provider_id, "provider_version": output.provider_version,
                            "page_count": output.page_count, "pdf_file_id": pdf.id, "page_file_ids": [page.id for page in pages]}
            status = "succeeded" if error is None else ("unavailable" if error.code in {
                "preview_disabled", "preview_provider_unavailable", "preview_profile_unavailable", "preview_sandbox_unavailable"} else "failed")
            manifest = {"schema_version": "word-preview/v1", "source_generation": state.source_generation,
                "source_result_file_id": state.source_result_file_id, "source_docx_sha256": state.source_docx_sha256,
                "profile_id": state.profile_id, "profile_sha256": state.profile_sha256, "run_id": run.run_id,
                "attempt": run.attempt_count, "status": status, "error_code": error.code if error else None,
                "created_at": utc_now().isoformat(), **evidence, **descriptors}
            if status == "succeeded":
                plan, trace, anchors = mapping_source(file, docx, self.file_repository, self.file_service)
                binding = mapping_binding(file, state, run, pdf=pdf, page_count=output.page_count, plan=plan)
                try:
                    manifest["page_mapping"] = build_page_mapping(binding=binding, plan=plan,
                        block_evidence=trace, block_anchor_evidence=anchors)
                except Exception:
                    # 只有纯 mapper 隔离未预期错误；上面的原件读取/认证与下面登记仍显式失败。
                    manifest["page_mapping"] = unavailable_mapping(binding, "unexpected_error")
                    self.logger.error("[job_id=%s trace_id=%s reason_code=unexpected_error] 页映射推断失败。", job.id, trace_id)
                if page_hash is not None:
                    quality_binding = page_quality_binding(current, file, state, run, page_policy, pdf=pdf,
                        page_count=output.page_count, mapping=manifest.get("page_mapping"), authenticated_plan=plan)
                    try:
                        manifest["page_quality_run"] = build_page_quality_run(binding=quality_binding,
                            policy=page_policy, observation=observed, mapping=manifest.get("page_mapping"),
                            created_at=run.started_at.isoformat(), reason_code=observation_reason)
                    except Exception:
                        # 规则异常只降级页面 coverage；原件认证及存储错误仍在此边界外显式失败。
                        manifest["page_quality_run"] = build_page_quality_run(binding=quality_binding,
                            policy=page_policy, created_at=run.started_at.isoformat(), reason_code="unexpected_error")
                        self.logger.error("[job_id=%s reason_code=page_quality_unexpected_error] 页面质量计算失败。", job.id)
            # manifest 或 CAS 持久化失败显式传播，执行收尾不能伪成功。
            manifest_file = self._register(current, file, "word_preview_manifest", "manifest.json",
                                          json.dumps(manifest, ensure_ascii=False).encode(), "application/json",
                                          **({"deadline": attempt_deadline} if page_hash else {}))
            # uploaded响应与实际字节一致才允许确认；响应丢失仍保留registering而非猜测完成。
            verified_records, verified_body = artifact_evidence(current, run, self.file_repository, self.file_service,
                               manifest_file_id=manifest_file.id, expected_status=status,
                               expected_error_code=error.code if error else None)
            page_contribution = None
            if page_hash is not None and status == "succeeded":
                checked = read_page_quality(current, run, verified_records, verified_body,
                    self.file_repository, self.file_service, authenticated_plan=plan)
                if checked is None:
                    raise ValueError("新登记的页面质量报告无法认证。")
                page_contribution = page_quality_contribution(current, run, page_policy, checked, manifest_file.id)
            if page_hash is not None and utc_now() >= attempt_deadline:
                raise PreviewFailure("preview_timeout")
            with preview_storage_io():
                finished = self.job_repository.finish_document_job_preview(job.id, request=request, revision=state.revision,
                    lease_token=claim.lease_token, status=status, manifest_file_id=manifest_file.id,
                    error_code=error.code if error else None, retryable=error.retryable if error else False, evidence=evidence,
                    page_quality_contribution=page_contribution)
            if finished is None:
                with preview_storage_io():
                    return self.job_repository.get_document_job(job.id) or current, False, run
            self._event(finished, "preview_succeeded" if error is None else "preview_failed", trace_id=trace_id,
                        duration_ms=int((time.monotonic() - started) * 1000))
            if not finished.word_preview_state.current_run.retryable:
                if not observe_current_preview(finished, self.file_repository, self.file_service).available:
                    raise PreviewFailure("preview_storage_failed")
                return finished, True, finished.word_preview_state.current_run
            request = request.model_copy(update={"resume": True})

    def _observe_page_quality(self, output, page_policy, preview_policy, attempt_deadline, *, job_id=None):
        """观察与 render 共用原 attempt 时限，并为对象登记保留冻结窗口。"""
        if not self.settings.page_quality_observation_enabled:
            return None, "observer_unavailable"
        observer = self.observer if self.observer is not None else self.provider
        if not hasattr(observer, "observe"):
            return None, "observer_unavailable"
        remaining = min(page_policy.observe_budget_seconds,
                        (attempt_deadline - utc_now()).total_seconds() - page_policy.registration_budget_seconds)
        if remaining <= 0:
            return None, "resource_exceeded"
        started = time.monotonic()
        try:
            batch = observer.observe(output.pdf, pages=output.pages, page_count=output.page_count,
                                     policy=page_policy, preview_policy=preview_policy, budget_seconds=remaining)
            if time.monotonic() - started > remaining:
                return None, "observer_timeout"
            return batch, None
        except Exception:
            self.logger.error("[job_id=%s reason_code=page_quality_invalid_observation] 页面 observer 返回失败。", job_id)
            return None, "invalid_observation"

    def _register(self, job, source, file_type, suffix, content, mime, *, deadline=None):
        state, run = job.word_preview_state, job.word_preview_state.current_run
        if deadline is not None and utc_now() >= deadline:
            raise PreviewFailure("preview_timeout")
        with preview_storage_io():
            expires = min(source.expires_at, utc_now() + timedelta(days=self.file_service.retention_days_resolver(file_type)))
            return self.file_service.register_generated_content(tenant_id=job.tenant_id, company_id=job.company_id,
                job_id=job.id, created_by=job.created_by, file_type=file_type,
                filename=f"g{job.retry_count}-{source.id}-{run.run_id}-a{run.attempt_count}-{suffix}", mime_type=mime,
                content=content, expires_at=expires, metadata={"retry_count": job.retry_count,
                    "source_result_file_id": source.id, "source_docx_sha256": source.checksum_sha256,
                    "profile_sha256": state.profile_sha256, "run_id": run.run_id, "attempt": run.attempt_count})

    def _event(self, job, event_type, *, trace_id, duration_ms=None):
        state, run = job.word_preview_state, job.word_preview_state.current_run
        summary = job.quality_summary.get("checks_v1", {}).get("word_preview", {})
        page_summary = job.quality_summary.get("checks_v1", {}).get("word_page_quality", {}).get("summary")
        page_event = {"page_quality": {key: page_summary[key] for key in (
            "schema_version", "evaluation_state", "quality_status", "reason_code", "counts") if key in page_summary}
        } if isinstance(page_summary, dict) else {}
        event = DocumentJobEventRecord(id="event_" + uuid4().hex[:12], tenant_id=job.tenant_id,
            company_id=job.company_id, job_id=job.id, created_by=job.created_by, stage=job.stage,
            event_type=event_type, message="Word 预览状态已记录。", trace_id=trace_id, duration_ms=duration_ms,
            payload={"generation": state.source_generation, "source_result_file_id": state.source_result_file_id,
                     "source_docx_sha256": state.source_docx_sha256, "profile_sha256": state.profile_sha256,
                     "run_id": run.run_id, "attempt": run.attempt_count, "status": run.status,
                     "error_code": run.error_code, "manifest_file_id": run.manifest_file_id,
                     **{key: summary[key] for key in ("provider_id", "provider_version", "page_count") if key in summary},
                     **page_event})
        try:
            self.event_repository.append_document_job_event(job.id, event)
        except Exception:
            # 状态提交后事件失败不能触发重渲染；保留现有无 outbox 的诊断边界。
            self.logger.error("[job_id=%s stage=%s] 预览事件追加失败，已提交状态保持有效。", job.id, job.stage)
