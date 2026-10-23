"""选定主 DOCX 后的预览编排；不重新运行解析、翻译或 renderer。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import json
import logging
import sqlite3
import time
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.domains.document_jobs.preview_state import (
    PreviewArtifactObservation, PreviewClaimRequest, PreviewRetryResult, current_preview_ids,
)
from app.domains.resources.models import utc_now
from app.domains.files.models import DocumentFileRecord, WORD_PREVIEW_FILE_TYPES
from app.services.preview.models import PreviewFailure, PreviewPolicy, PreviewResult, sha256, validate_docx, validate_result
from app.services.preview.provider import WordPreviewProvider
from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider

PREVIEW_FILE_TYPES = WORD_PREVIEW_FILE_TYPES


class _PreviewStorageError(OSError):
    """新预览I/O的安全错误，不保留驱动消息、对象路径或客户内容。"""

    code = "preview_storage_failed"

    def __init__(self):
        super().__init__("Word 预览存储失败，请稍后重试。")


def _is_preview_storage_error(error: Exception) -> bool:
    return (isinstance(error, (OSError, sqlite3.Error, BotoCoreError, ClientError))
            or type(error).__module__.startswith("pymysql."))


@contextmanager
def _preview_storage_io():
    """只归一化已识别的存储异常；编程、业务权限和契约错误仍按原语义抛出。"""
    try:
        yield
    except Exception as error:
        if _is_preview_storage_error(error):
            raise _PreviewStorageError() from None
        raise


class DocumentJobPreviewService:
    """仓储负责原子身份与预算，文件服务负责追加对象；本服务只编排锁外 I/O。"""

    def __init__(self, settings, job_repository, event_repository, file_repository, file_service,
                 provider: WordPreviewProvider | None = None, audit_service=None):
        self.settings, self.job_repository, self.event_repository = settings, job_repository, event_repository
        self.file_repository, self.file_service = file_repository, file_service
        self.provider = provider or SandboxWordPreviewProvider(
            backend=settings.word_preview_backend, launcher=settings.word_preview_launcher,
            profile_path=settings.word_preview_profile_path, profile_id=settings.word_preview_profile_id,
            profile_sha256=settings.word_preview_profile_sha256)
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
            raise ApiError(400, "invalid_request", "预览重试必须提供 1..1000 字的原因。")
        try:
            key = str(UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ApiError(400, "invalid_request", "预览重试 request ID 必须是 UUID。") from None
        if (job.status != "succeeded" or job.stage != "completed" or job.prepared_result is None
                or job.result_file_id != job.prepared_result.file.id or job.deleted_at is not None
                or job.archived_at is not None or job.delivery_status == "published"
                or "word_preview" not in job.request_snapshot):
            raise ApiError(409, "conflict", "当前任务或主件不支持预览单独重试。")
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
            raise ApiError(409, "conflict", str(exc)) from None

    def _source(self, job: DocumentJobRecord):
        receipt = job.prepared_result
        if receipt is None:
            raise ValueError("预览缺少当前主件凭据。")
        with _preview_storage_io():
            file = self.file_repository.get_document_file(receipt.file.id)
        if (file is None or file != receipt.file.model_copy(update={"etag": file.etag, "updated_at": file.updated_at})
                or file.status != "uploaded" or file.expires_at is None or file.expires_at <= utc_now()):
            raise ValueError("预览主件 metadata 与选定凭据不一致或已失效。")
        with _preview_storage_io():
            content = self.file_service.read_file_content(file)
        if len(content) != receipt.file.size_bytes or sha256(content) != receipt.file.checksum_sha256:
            raise ValueError("选定主 DOCX 字节与凭据不一致。")
        return file, content

    def _run(self, job, *, request_key, requested_by, reason, independent, resume, trace_id, actor=None):
        policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
        file, docx = self._source(job)
        fingerprint = sha256(json.dumps({"tenant": job.tenant_id, "company": job.company_id, "job": job.id,
            "generation": job.retry_count, "result": file.id, "sha256": file.checksum_sha256,
            "profile": policy.profile_sha256, "action": "retry" if independent else "initial",
            "actor": requested_by, "reason_sha256": sha256(reason.encode())}, sort_keys=True).encode())
        request = PreviewClaimRequest(generation=job.retry_count, result_file_id=file.id, docx_sha256=file.checksum_sha256,
            policy=policy, request_key=request_key, request_fingerprint=fingerprint, requested_by=requested_by,
            reason_sha256=sha256(reason.encode()), independent=independent, resume=resume)
        while True:
            # 使用最新记录建立观测；job锁内仍须比较revision/current，禁止复用陈旧成功。
            with _preview_storage_io():
                latest = self.job_repository.get_document_job(job.id) or job
            observation = None
            if latest.word_preview_state is not None:
                selected = latest.word_preview_state.current_run
                if selected.manifest_file_id is not None and selected.status in {"succeeded", "failed", "unavailable"}:
                    observation = observe_current_preview(latest, self.file_repository, self.file_service)
            with _preview_storage_io():
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
                    with _preview_storage_io():
                        self.audit_service.record(actor=ActorContext(actor_id=actor.id, actor_role=actor.role, source="jwt"),
                            action="document_job.word_preview_retry", target_type="document_job", target_id=job.id,
                            trace_id=trace_id or "word_preview", details={"run_id": run.run_id, "generation": job.retry_count})
            self._event(current, "preview_started", trace_id=trace_id)
            started = time.monotonic()
            output, error = None, None
            try:
                if claim.disposition == "finalizing":
                    raise PreviewFailure("preview_timeout")
                if policy.backend == "disabled":
                    raise PreviewFailure("preview_disabled")
                validate_docx(docx, policy)
                remaining = max(0.001, (run.run_deadline_at - utc_now()).total_seconds())
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
            # Provider结束后再次CAS；任何PDF/page/失败manifest写入之前都必须已进入登记。
            with _preview_storage_io():
                registering = self.job_repository.begin_document_job_preview_registration(
                    job.id, request=request, revision=state.revision, lease_token=claim.lease_token,
                    attempt=run.attempt_count)
            if registering is None:
                with _preview_storage_io():
                    return self.job_repository.get_document_job(job.id) or current, False, run
            current = registering
            state, run = current.word_preview_state, current.word_preview_state.current_run
            evidence, descriptors = {}, {}
            if output is not None and error is None:
                # 任一对象或 metadata 不可确认均显式传播，不能降级为可成功收尾的预览失败。
                pdf = self._register(current, file, "word_preview_pdf", "preview.pdf", output.pdf, "application/pdf")
                pages = [self._register(current, file, "word_preview_page", f"page-{page.page_index:06d}.png",
                                        page.content, "image/png") for page in output.pages]
                descriptors = {"pdf": self._descriptor(pdf), "pages": [
                    {**self._descriptor(file), "page_index": page.page_index, "width": page.width, "height": page.height}
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
            # manifest 或 CAS 持久化失败显式传播，执行收尾不能伪成功。
            manifest_file = self._register(current, file, "word_preview_manifest", "manifest.json",
                                          json.dumps(manifest, ensure_ascii=False).encode(), "application/json")
            # uploaded响应与实际字节一致才允许确认；响应丢失仍保留registering而非猜测完成。
            _artifact_evidence(current, run, self.file_repository, self.file_service,
                               manifest_file_id=manifest_file.id, expected_status=status,
                               expected_error_code=error.code if error else None)
            with _preview_storage_io():
                finished = self.job_repository.finish_document_job_preview(job.id, request=request, revision=state.revision,
                    lease_token=claim.lease_token, status=status, manifest_file_id=manifest_file.id,
                    error_code=error.code if error else None, retryable=error.retryable if error else False, evidence=evidence)
            if finished is None:
                with _preview_storage_io():
                    return self.job_repository.get_document_job(job.id) or current, False, run
            self._event(finished, "preview_succeeded" if error is None else "preview_failed", trace_id=trace_id,
                        duration_ms=int((time.monotonic() - started) * 1000))
            if not finished.word_preview_state.current_run.retryable:
                if not observe_current_preview(finished, self.file_repository, self.file_service).available:
                    raise PreviewFailure("preview_storage_failed")
                return finished, True, finished.word_preview_state.current_run
            request = request.model_copy(update={"resume": True})

    def _register(self, job, source, file_type, suffix, content, mime):
        state, run = job.word_preview_state, job.word_preview_state.current_run
        with _preview_storage_io():
            expires = min(source.expires_at, utc_now() + timedelta(days=self.file_service.retention_days_resolver(file_type)))
            return self.file_service.register_generated_content(tenant_id=job.tenant_id, company_id=job.company_id,
                job_id=job.id, created_by=job.created_by, file_type=file_type,
                filename=f"g{job.retry_count}-{source.id}-{run.run_id}-a{run.attempt_count}-{suffix}", mime_type=mime,
                content=content, expires_at=expires, metadata={"retry_count": job.retry_count,
                    "source_result_file_id": source.id, "source_docx_sha256": source.checksum_sha256,
                    "profile_sha256": state.profile_sha256, "run_id": run.run_id, "attempt": run.attempt_count})

    @staticmethod
    def _descriptor(file):
        return {"file_id": file.id, "sha256": file.checksum_sha256, "mime_type": file.mime_type,
                "size_bytes": file.size_bytes}

    def _event(self, job, event_type, *, trace_id, duration_ms=None):
        state, run = job.word_preview_state, job.word_preview_state.current_run
        summary = job.quality_summary.get("checks_v1", {}).get("word_preview", {})
        event = DocumentJobEventRecord(id="event_" + uuid4().hex[:12], tenant_id=job.tenant_id,
            company_id=job.company_id, job_id=job.id, created_by=job.created_by, stage=job.stage,
            event_type=event_type, message="Word 预览状态已记录。", trace_id=trace_id, duration_ms=duration_ms,
            payload={"generation": state.source_generation, "source_result_file_id": state.source_result_file_id,
                     "source_docx_sha256": state.source_docx_sha256, "profile_sha256": state.profile_sha256,
                     "run_id": run.run_id, "attempt": run.attempt_count, "status": run.status,
                     "error_code": run.error_code, "manifest_file_id": run.manifest_file_id,
                     **{key: summary[key] for key in ("provider_id", "provider_version", "page_count") if key in summary}})
        try:
            self.event_repository.append_document_job_event(job.id, event)
        except Exception:
            # 状态提交后事件失败不能触发重渲染；保留现有无 outbox 的诊断边界。
            self.logger.error("[job_id=%s stage=%s] 预览事件追加失败，已提交状态保持有效。", job.id, job.stage)


class _PreviewUnavailable(Exception):
    """仅表示预览件已确定过期、删除或不存在，不能代表未知存储错误。"""


def _read_artifact(file, file_service):
    try:
        content = file_service.read_file_content(file)
    except FileNotFoundError:
        raise _PreviewUnavailable() from None
    except ClientError as exc:
        # S3只把明确的对象不存在分类为生命周期失效，超时/权限/连接错误继续传播。
        if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
            raise _PreviewUnavailable() from None
        raise _PreviewStorageError() from None
    except Exception as error:
        if _is_preview_storage_error(error):
            raise _PreviewStorageError() from None
        raise
    if len(content) != file.size_bytes or sha256(content) != file.checksum_sha256:
        raise ValueError("预览Artifact字节与描述符不一致。")
    return content


def _artifact_evidence(job, run, file_repository, file_service, *, manifest_file_id=None, expected_status=None, expected_error_code=None):
    """一次完整读取manifest与所有必需输出；列表、重试和Token共用同一身份校验。"""
    from app.services.preview.models import PreviewPage

    state, receipt = job.word_preview_state, job.prepared_result
    policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
    now = utc_now()
    with _preview_storage_io():
        source = file_repository.get_document_file(state.source_result_file_id)
    if (source is None or receipt is None or source.status != "uploaded" or source.expires_at is None
            or source.expires_at <= now or source.file_type != "generated_word"
            or (source.tenant_id, source.company_id, source.job_id) != (job.tenant_id, job.company_id, job.id)
            or source.id != receipt.file.id or source.checksum_sha256 != state.source_docx_sha256
            or source.size_bytes != receipt.file.size_bytes or source.mime_type != receipt.file.mime_type
            or state.source_generation != job.retry_count or receipt.generation != job.retry_count
            or (state.profile_id, state.profile_sha256) != (policy.profile_id, policy.profile_sha256)):
        raise ValueError("预览主件身份或有效期无法确认。")
    # 主件缺失不能作为预览失效再生成的理由。
    with _preview_storage_io():
        source_bytes = file_service.read_file_content(source)
    if len(source_bytes) != source.size_bytes or sha256(source_bytes) != state.source_docx_sha256:
        raise ValueError("预览主件字节与凭据不一致。")
    records = [source]

    def artifact(file_id, file_type, mime, descriptor=None):
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("预览Artifact描述符缺少文件身份。")
        with _preview_storage_io():
            record = file_repository.get_document_file(file_id)
        if record is None:
            raise _PreviewUnavailable()
        if (record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id):
            raise ValueError("预览Artifact归属与任务不一致。")
        if record.status in {"expired", "deleted"} or (record.expires_at is not None and record.expires_at <= now):
            raise _PreviewUnavailable()
        if (record.status != "uploaded" or record.expires_at is None
                or record.file_type != file_type or record.mime_type != mime):
            raise ValueError("预览Artifact状态、类型或保留期不一致。")
        expected_metadata = {"retry_count": state.source_generation, "source_result_file_id": source.id,
            "source_docx_sha256": state.source_docx_sha256, "profile_sha256": state.profile_sha256,
            "run_id": run.run_id, "attempt": run.attempt_count, "word_preview_artifact_protocol": 1}
        if any(record.metadata.get(key) != value or (type(value) is int and type(record.metadata.get(key)) is not int)
               for key, value in expected_metadata.items()):
            raise ValueError("预览Artifact来源或attempt不一致。")
        if descriptor is not None:
            expected = DocumentJobPreviewService._descriptor(record)
            if not isinstance(descriptor, dict) or any(descriptor.get(key) != value for key, value in expected.items()):
                raise ValueError("预览manifest与Artifact描述符不一致。")
        content = _read_artifact(record, file_service)
        records.append(record)
        return record, content

    manifest, raw = artifact(manifest_file_id or run.manifest_file_id, "word_preview_manifest", "application/json")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("预览manifest不是有效JSON。") from None
    identity = {"schema_version": "word-preview/v1", "source_generation": state.source_generation,
        "source_result_file_id": source.id, "source_docx_sha256": state.source_docx_sha256,
        "profile_id": state.profile_id, "profile_sha256": state.profile_sha256,
        "run_id": run.run_id, "attempt": run.attempt_count, "status": expected_status or run.status}
    if not isinstance(body, dict) or any(body.get(key) != value for key, value in identity.items()):
        raise ValueError("预览manifest来源、run或attempt不一致。")
    if body.get("error_code") != (expected_error_code if expected_status is not None else run.error_code):
        raise ValueError("预览manifest错误码与当前attempt不一致。")
    if body["status"] == "succeeded":
        pdf_desc, pages_desc = body.get("pdf"), body.get("pages")
        if body.get("error_code") is not None or not isinstance(pdf_desc, dict) or not isinstance(pages_desc, list):
            raise ValueError("成功预览manifest的输出描述无效。")
        pdf, pdf_bytes = artifact(pdf_desc.get("file_id"), "word_preview_pdf", "application/pdf", pdf_desc)
        pages = []
        if len(pages_desc) > policy.max_pages:
            raise ValueError("预览manifest页数超出预算。")
        for descriptor in pages_desc:
            if not isinstance(descriptor, dict):
                raise ValueError("预览页面描述符无效。")
            page, content = artifact(descriptor.get("file_id"), "word_preview_page", "image/png", descriptor)
            try:
                pages.append(PreviewPage(page_index=descriptor.get("page_index"), content=content,
                                         width=descriptor.get("width"), height=descriptor.get("height")))
            except ValidationError:
                raise ValueError("预览页面描述符无效。") from None
        try:
            output = PreviewResult(pdf=pdf_bytes, page_count=body.get("page_count"), pages=tuple(pages),
                provider_id=body.get("provider_id"), provider_version=body.get("provider_version"), profile_sha256=state.profile_sha256)
            validate_result(output, policy)
        except (ValidationError, PreviewFailure):
            raise ValueError("预览manifest的输出或预算校验失败。") from None
        if body.get("pdf_file_id") != pdf.id or body.get("page_file_ids") != [item["file_id"] for item in pages_desc]:
            raise ValueError("预览manifest输出引用不一致。")
        if len({record.id for record in records}) != len(records):
            raise ValueError("预览Artifact不能重复引用同一物理身份。")
    elif (body["status"] not in {"failed", "unavailable"} or body.get("error_code") is None
          or any(body.get(key) for key in ("pdf", "pages", "page_count", "pdf_file_id", "page_file_ids"))):
        raise ValueError("失败预览manifest不能包含成功输出。")
    return tuple(records), body


def observe_current_preview(job, file_repository, file_service) -> PreviewArtifactObservation:
    """生成内部观测；未知存储和完整性错误显式失败，只有确定生命周期失效可恢复。"""
    state = job.word_preview_state
    run = state.current_run
    try:
        records, body = _artifact_evidence(job, run, file_repository, file_service)
        summary = job.quality_summary.get("checks_v1", {}).get("word_preview", {})
        expected = {"manifest_file_id": run.manifest_file_id, "run_id": run.run_id,
                    "profile_sha256": state.profile_sha256}
        if run.status == "succeeded":
            expected.update(pdf_file_id=body["pdf_file_id"], page_file_ids=body["page_file_ids"])
        if any(summary.get(key) != value for key, value in expected.items()):
            raise ValueError("当前预览质量摘要与manifest不一致。")
        available = True
        earliest = min(record.expires_at for record in records)
    except _PreviewUnavailable:
        with _preview_storage_io():
            source = file_repository.get_document_file(state.source_result_file_id)
        # _artifact_evidence先验证主件；此处期限只限定失效观测本身的使用窗口。
        records, available, earliest = (source,), False, source.expires_at
    return PreviewArtifactObservation(source_generation=state.source_generation,
        source_result_file_id=state.source_result_file_id, source_docx_sha256=state.source_docx_sha256,
        profile_id=state.profile_id, profile_sha256=state.profile_sha256, revision=state.revision,
        current_request_key=state.current_request_key, run_id=run.run_id, attempt=run.attempt_count,
        manifest_file_id=run.manifest_file_id, files=records, earliest_expires_at=earliest, available=available)


def verified_current_preview_files(job, file_repository, file_service) -> dict[str, DocumentFileRecord]:
    """一次观测产生本次调用可见的完整预览集合；列表和单件授权不共享缓存。"""
    current_ids = current_preview_ids(job)
    if not current_ids or file_service is None:
        return {}
    try:
        observation = observe_current_preview(job, file_repository, file_service)
        if not observation.available or observation.earliest_expires_at <= utc_now():
            return {}
        return {record.id: record for record in observation.files if record.id in current_ids}
    except (OSError, ValueError, PreviewFailure, _PreviewUnavailable):
        return {}


def preview_download_ttl(job, record, file_repository, file_service, *, expires_seconds: int) -> int:
    """签发时以完整当前预览的最早期限截断，直连URL仍不承诺即时撤销。"""
    observation = observe_current_preview(job, file_repository, file_service)
    if (not observation.available or record.id not in current_preview_ids(job) or record not in observation.files):
        raise ApiError(409, "conflict", "当前预览引用已失效。")
    with _preview_storage_io():
        ttl = min(file_service.preview_download_ttl(record, expires_seconds=expires_seconds),
                  int((observation.earliest_expires_at - utc_now()).total_seconds()))
    if ttl <= 0:
        raise ApiError(409, "conflict", "当前预览引用已过期。")
    return ttl
