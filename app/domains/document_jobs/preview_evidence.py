"""当前 Word 预览证据的严格读取：主件、manifest 与全部输出 Artifact 的身份/字节认证，
以及页级质量与页面映射的同次解析。预览执行服务与只读 API、下载授权共用这里的唯一认证 owner。
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from app.core.errors import ApplicationError
from app.domains.document_jobs.preview_state import (
    PreviewArtifactObservation,
    current_preview_ids,
    page_quality_context_sha256,
)
from app.domains.files.models import DocumentFileRecord, WORD_PREVIEW_FILE_TYPES
from app.domains.files.result_registration import (
    ensure_result_descriptor_matches,
    file_lifecycle_unavailable,
    retained_file_expiry,
)
from app.domains.resources.models import utc_now
from app.services.document_ir.models import DocumentIR
from app.services.preview.models import PreviewFailure, PreviewPolicy, PreviewResult, sha256, validate_result
from app.services.preview.page_mapping import MappingBinding, read_page_mapping
from app.services.preview.page_quality import (
    PageQualityBinding,
    parse_page_quality_policy,
    policy_sha256,
    read_page_quality_run,
    page_quality_summary,
)
from app.services.renderer.block_anchors import validate_block_anchor_evidence
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import validate_persisted_render_evidence

PREVIEW_FILE_TYPES = WORD_PREVIEW_FILE_TYPES
_UNREAD_QUALITY_PLAN = object()


class PreviewStorageError(OSError):
    """新预览I/O的安全错误，不保留驱动消息、对象路径或客户内容。"""

    code = "preview_storage_failed"

    def __init__(self):
        super().__init__("Word 预览存储失败，请稍后重试。")


def is_preview_storage_error(error: Exception) -> bool:
    return (isinstance(error, (OSError, sqlite3.Error, BotoCoreError, ClientError))
            or type(error).__module__.startswith("pymysql."))


@contextmanager
def preview_storage_io():
    """只归一化已识别的存储异常；编程、业务权限和契约错误仍按原语义抛出。"""
    try:
        yield
    except Exception as error:
        if is_preview_storage_error(error):
            raise PreviewStorageError() from None
        raise


def artifact_descriptor(file):
    """预览 manifest 中引用单个 Artifact 的不可变描述符。"""
    return {"file_id": file.id, "sha256": file.checksum_sha256, "mime_type": file.mime_type,
            "size_bytes": file.size_bytes}


def frozen_page_policy(job):
    """旧快照缺字段保持缺失；配置只影响未来新任务。"""
    if "page_quality" not in job.request_snapshot:
        return None
    try:
        policy = parse_page_quality_policy(job.request_snapshot["page_quality"])
    except ValueError:
        raise ValueError("冻结页面质量策略无效或版本不受支持。") from None
    if policy.enabled:
        preview = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
        if ((policy.profile_id, policy.profile_sha256) != (preview.profile_id, preview.profile_sha256)
                or policy.render_budget_seconds + policy.observe_budget_seconds + policy.registration_budget_seconds
                > preview.timeout_seconds):
            raise ValueError("冻结页面策略与预览 profile 或 attempt 预算不一致。")
    return policy


def page_quality_binding(job, source, state, run, policy, *, pdf, page_count, mapping, authenticated_plan):
    # 可选 mapping 的坏内层 hash 不得破坏已认证 PDF/页面的下载资格。
    mapping_hash = mapping.get("mapping_sha256") if isinstance(mapping, dict) else None
    if not isinstance(mapping_hash, str) or re.fullmatch(r"[0-9a-f]{64}", mapping_hash) is None:
        mapping_hash = None
    return PageQualityBinding(source_generation=state.source_generation, result_file_id=source.id,
        docx_sha256=source.checksum_sha256, preview_run_id=run.run_id, attempt=run.attempt_count,
        preview_pdf_file_id=pdf.id, preview_pdf_sha256=pdf.checksum_sha256, page_count=page_count,
        profile_id=state.profile_id, profile_sha256=state.profile_sha256, policy_sha256=policy_sha256(policy),
        mapping_sha256=mapping_hash, actual_context_sha256=page_quality_context_sha256(job, authenticated_plan=authenticated_plan, require_authenticated=True))


def read_page_quality(job, run, records, body, file_repository, file_service, *, authenticated_plan=_UNREAD_QUALITY_PLAN):
    policy = frozen_page_policy(job)
    if policy is None or not policy.enabled or body["status"] != "succeeded":
        return None
    if read_page_quality_run(body.get("page_quality_run"), policy=policy) is None:
        return None
    if authenticated_plan is _UNREAD_QUALITY_PLAN:
        # 原件已通过外层身份与字节校验；实际校准上下文还须认证同次 renderer 证据。
        source_content = read_artifact(records[0], file_service)
        try:
            authenticated_plan, _, _ = mapping_source(job.prepared_result.file, source_content,
                                                       file_repository, file_service)
        except ValueError:
            # 严格新 key 不能把原 IR 字节或描述符完整性失败误当作缺报告。
            raise ValueError("当前页面质量上下文无法认证。") from None
    pdf = next(record for record in records if record.file_type == "word_preview_pdf")
    binding = page_quality_binding(job, job.prepared_result.file, job.word_preview_state, run, policy,
        pdf=pdf, page_count=body["page_count"], mapping=body.get("page_mapping"), authenticated_plan=authenticated_plan)
    return read_page_quality_run(body.get("page_quality_run"), binding=binding, policy=policy)


def page_quality_contribution(job, run, policy, report, manifest_file_id):
    state = job.word_preview_state
    return {"quality_status": report["quality_status"], "evaluation_state": report["evaluation_state"],
        "run_sha256": report["run_sha256"], "summary": page_quality_summary(report),
        "source_generation": state.source_generation, "source_result_file_id": state.source_result_file_id,
        "source_docx_sha256": state.source_docx_sha256, "profile_id": state.profile_id,
        "profile_sha256": state.profile_sha256, "run_id": run.run_id, "attempt": run.attempt_count,
        "policy_sha256": policy_sha256(policy), "manifest_file_id": manifest_file_id}


def mapping_source(source, content, file_repository, file_service, *, authentication_files=None):
    """只读取选定主件的原始 IR 与持久证据；存储/原件损坏不能借映射降级。"""
    metadata = source.metadata
    if metadata.get("render_trace_status") != "complete":
        return None, None, None
    ir_id = metadata.get("document_ir_file_id")
    if not isinstance(ir_id, str) or not ir_id:
        return None, None, None
    with preview_storage_io():
        ir_file = file_repository.get_document_file(ir_id)
    if (ir_file is None or ir_file.status != "uploaded" or ir_file.file_type != "document_ir"
            or file_lifecycle_unavailable(ir_file, file_repository, now=utc_now())
            or (ir_file.tenant_id, ir_file.company_id, ir_file.job_id)
            != (source.tenant_id, source.company_id, source.job_id)):
        # 原 IR 生命周期与 scope 不能成为历史主件的新可用性门，也不能扩展读取权限。
        return None, None, None
    try:
        ir_bytes = read_artifact(ir_file, file_service)
    except PreviewUnavailable:
        return None, None, None
    try:
        document_ir = DocumentIR.model_validate_json(ir_bytes)
    except (ValidationError, ValueError):
        raise ValueError("主件的原始 IR 数据无法认证。") from None
    validate_persisted_renderer_content(document_ir, content, metadata,
        expected_template_version_id=metadata.get("template_version_id"))
    verified = validate_persisted_render_evidence(document_ir, content,
        render_plan=metadata.get("render_plan"), block_render_evidence=metadata.get("block_render_evidence"))
    if verified is None:
        return None, None, None
    plan, trace = verified
    anchors = validate_block_anchor_evidence(metadata.get("block_anchor_evidence"), plan=plan,
        block_evidence=trace, word_content=content)
    if plan.schema_version == "render-plan/v2" and anchors is None:
        return None, None, None
    if authentication_files is not None:
        authentication_files[ir_file.id] = ir_file
    return plan, trace, anchors


def mapping_binding(source, state, run, *, pdf=None, page_count=None, plan=None):
    """文件及 run 身份都来自同次选定 receipt/已验证预览，不接受外部请求覆盖。"""
    source_id, ir_id = source.metadata.get("source_file_id"), source.metadata.get("document_ir_file_id")
    return MappingBinding(source_pdf_file_id=source_id if isinstance(source_id, str) else None,
        document_ir_file_id=ir_id if isinstance(ir_id, str) else None,
        input_ir_sha256=plan.input_ir_sha256 if plan is not None else None,
        plan_sha256=plan.plan_sha256 if plan is not None else None,
        source_generation=state.source_generation, result_file_id=source.id,
        docx_sha256=source.checksum_sha256, run_id=run.run_id, attempt=run.attempt_count,
        profile_sha256=state.profile_sha256, preview_pdf_file_id=pdf.id if pdf is not None else None,
        preview_pdf_sha256=pdf.checksum_sha256 if pdf is not None else None, page_count=page_count)


def current_page_mapping(job, file_repository, file_service):
    """内部只读视图；沿原完整预览认证后，独立解析可选 mapping，不修改 manifest。"""
    state = job.word_preview_state
    run = state.current_run
    records, body = artifact_evidence(job, run, file_repository, file_service)
    return _mapping_from_current_evidence(job, records, body, file_repository, file_service)


def _mapping_from_current_evidence(job, records, body, file_repository, file_service):
    """复用同次已认证的 manifest/预览集合，避免内容读取再次下载预览 PDF。"""
    state, run = job.word_preview_state, job.word_preview_state.current_run
    source = records[0]
    with preview_storage_io():
        content = file_service.read_file_content(source)
    selected_source = job.prepared_result.file
    plan, _, _ = mapping_source(selected_source, content, file_repository, file_service) if body["status"] == "succeeded" else (None, None, None)
    pdf = next((record for record in records if record.file_type == "word_preview_pdf"), None)
    binding = mapping_binding(selected_source, state, run, pdf=pdf, page_count=body.get("page_count"), plan=plan)
    return read_page_mapping(body.get("page_mapping"), binding=binding)


class PreviewUnavailable(Exception):
    """仅表示预览件已确定过期、删除或不存在，不能代表未知存储错误。"""


def read_artifact(file, file_service):
    try:
        content = file_service.read_file_content(file)
    except FileNotFoundError:
        raise PreviewUnavailable() from None
    except ClientError as exc:
        # S3只把明确的对象不存在分类为生命周期失效，超时/权限/连接错误继续传播。
        if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
            raise PreviewUnavailable() from None
        raise PreviewStorageError() from None
    except Exception as error:
        if is_preview_storage_error(error):
            raise PreviewStorageError() from None
        raise
    if len(content) != file.size_bytes or sha256(content) != file.checksum_sha256:
        raise ValueError("预览Artifact字节与描述符不一致。")
    return content


def artifact_evidence(job, run, file_repository, file_service, *, manifest_file_id=None, expected_status=None, expected_error_code=None):
    """一次完整读取manifest与所有必需输出；列表、重试和Token共用同一身份校验。"""
    from app.services.preview.models import PreviewPage

    state, receipt = job.word_preview_state, job.prepared_result
    policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
    now = utc_now()
    with preview_storage_io():
        source = file_repository.get_document_file(state.source_result_file_id)
    if (source is None or receipt is None or source.status != "uploaded" or source.expires_at is None
            or file_lifecycle_unavailable(source, file_repository, now=now) or source.file_type != "generated_word"
            or (source.tenant_id, source.company_id, source.job_id) != (job.tenant_id, job.company_id, job.id)
            or source.id != receipt.file.id or source.checksum_sha256 != state.source_docx_sha256
            or source.size_bytes != receipt.file.size_bytes or source.mime_type != receipt.file.mime_type
            or state.source_generation != job.retry_count or receipt.generation != job.retry_count
            or (state.profile_id, state.profile_sha256) != (policy.profile_id, policy.profile_sha256)):
        raise ValueError("预览主件身份或有效期无法确认。")
    ensure_result_descriptor_matches(source, receipt.file)
    # 主件缺失不能作为预览失效再生成的理由。
    with preview_storage_io():
        source_bytes = file_service.read_file_content(source)
    if len(source_bytes) != source.size_bytes or sha256(source_bytes) != state.source_docx_sha256:
        raise ValueError("预览主件字节与凭据不一致。")
    records = [source]

    def artifact(file_id, file_type, mime, descriptor=None):
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("预览Artifact描述符缺少文件身份。")
        with preview_storage_io():
            record = file_repository.get_document_file(file_id)
        if record is None:
            raise PreviewUnavailable()
        if (record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id):
            raise ValueError("预览Artifact归属与任务不一致。")
        if file_lifecycle_unavailable(record, file_repository, now=now):
            raise PreviewUnavailable()
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
            expected = artifact_descriptor(record)
            if not isinstance(descriptor, dict) or any(descriptor.get(key) != value for key, value in expected.items()):
                raise ValueError("预览manifest与Artifact描述符不一致。")
        content = read_artifact(record, file_service)
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


@dataclass(frozen=True)
class CurrentPreviewEvidence:
    """同次严格读取的私有结果；公共 API 必须再经显式白名单投影。"""
    observation: PreviewArtifactObservation
    manifest: dict | None
    page_quality_run: dict | None
    page_mapping: dict | None = None
    authentication_files: tuple[DocumentFileRecord, ...] = ()
    render_plan: object | None = None


def read_current_preview_evidence(job, file_repository, file_service, *, include_page_quality=False, include_mapping=False, include_render=False) -> CurrentPreviewEvidence:
    """复用原 Artifact/policy/context 认证，一次读取供预览与页级 API 使用。"""
    state = job.word_preview_state
    run = state.current_run
    quality_policy = frozen_page_policy(job) if include_page_quality else None
    quality_report = None
    mapping = None
    body = None
    authentication_files = {}
    authenticated_plan = None
    try:
        records, body = artifact_evidence(job, run, file_repository, file_service)
        if include_render:
            source = records[0]
            authenticated_plan, _, _ = mapping_source(source, read_artifact(source, file_service),
                file_repository, file_service, authentication_files=authentication_files)
        if include_mapping:
            mapping = _mapping_from_current_evidence(job, records, body, file_repository, file_service)
        if include_page_quality:
            quality_report = read_page_quality(job, run, records, body, file_repository, file_service)
        summary = job.quality_summary.get("checks_v1", {}).get("word_preview", {})
        expected = {"manifest_file_id": run.manifest_file_id, "run_id": run.run_id,
                    "profile_sha256": state.profile_sha256}
        if run.status == "succeeded":
            expected.update(pdf_file_id=body["pdf_file_id"], page_file_ids=body["page_file_ids"])
        if any(summary.get(key) != value for key, value in expected.items()):
            raise ValueError("当前预览质量摘要与manifest不一致。")
        available = True
        earliest = min((retained_file_expiry(record, file_repository) or datetime.max.replace(tzinfo=timezone.utc))
                       for record in records)
    except PreviewUnavailable:
        with preview_storage_io():
            source = file_repository.get_document_file(state.source_result_file_id)
        # _artifact_evidence先验证主件；此处期限只限定失效观测本身的使用窗口。
        records, available, earliest = (source,), False, source.expires_at
        body = None
    observation = PreviewArtifactObservation(source_generation=state.source_generation,
        source_result_file_id=state.source_result_file_id, source_docx_sha256=state.source_docx_sha256,
        profile_id=state.profile_id, profile_sha256=state.profile_sha256, revision=state.revision,
        current_request_key=state.current_request_key, run_id=run.run_id, attempt=run.attempt_count,
        manifest_file_id=run.manifest_file_id, files=records, earliest_expires_at=earliest, available=available,
        page_quality_policy_sha256=policy_sha256(quality_policy) if quality_policy is not None and quality_policy.enabled else None,
        page_quality_run_sha256=quality_report["run_sha256"] if quality_report is not None else None,
        page_quality_reusable=(quality_report is not None and quality_report["evaluation_state"] == "complete")
        if include_page_quality else None)
    return CurrentPreviewEvidence(observation, body, quality_report, mapping, tuple(authentication_files.values()), authenticated_plan)


def observe_current_preview(job, file_repository, file_service, *, check_page_quality=False) -> PreviewArtifactObservation:
    """保留原预览状态机的观察接口，认证事实与新读取入口共用同一 owner。"""
    return read_current_preview_evidence(job, file_repository, file_service,
        include_page_quality=check_page_quality).observation


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
    except (OSError, ValueError, PreviewFailure, PreviewUnavailable):
        return {}


def preview_download_ttl(job, record, file_repository, file_service, *, expires_seconds: int) -> int:
    """签发时以完整当前预览的最早期限截断，直连URL仍不承诺即时撤销。"""
    observation = observe_current_preview(job, file_repository, file_service)
    if (not observation.available or record.id not in current_preview_ids(job) or record not in observation.files):
        raise ApplicationError("conflict", "当前预览引用已失效。")
    with preview_storage_io():
        ttl = min(file_service.preview_download_ttl(record, expires_seconds=expires_seconds),
                  int((observation.earliest_expires_at - utc_now()).total_seconds()))
    if ttl <= 0:
        raise ApplicationError("conflict", "当前预览引用已过期。")
    return ttl
