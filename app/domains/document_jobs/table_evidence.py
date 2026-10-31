"""表格报告的应用绑定、受控实物读取与候选保留期，不拥有任务状态机。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import ValidationError, field_validator, model_validator

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import ensure_result_descriptor_matches, retained_file_expiry
from app.domains.resources.models import utc_now
from app.services.document_ir.models import DocumentIR
from app.services.renderer.evidence import validate_persisted_renderer_content
from app.services.tables.evidence import (
    Checksum, EvidenceModel, SafeId, TableEvidenceError, TableEvidenceReport,
    read_table_evidence, table_evidence_summary, VERSION,
)
from app.services.tables.models import NonNegativeInt, canonical_json_bytes, canonical_sha256
import hashlib


class EvidencePreparation(EvidenceModel):
    t0: datetime
    word_retention_days: NonNegativeInt
    report_retention_days: NonNegativeInt
    docx_expires_at: datetime
    report_expires_at: datetime

    @field_validator("t0", "docx_expires_at", "report_expires_at", mode="before")
    @classmethod
    def _json_datetime(cls, value, info):
        # 父级安全 wrap 使用 Python handler；只恢复 JSON 合同中的 ISO 时间表达。
        if info.mode == "json" and isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _deadlines(self):
        if (self.t0.tzinfo is None or self.docx_expires_at != self.t0 + timedelta(days=self.word_retention_days)
                or self.report_expires_at != max(self.docx_expires_at, self.t0 + timedelta(days=self.report_retention_days))):
            raise TableEvidenceError("table_evidence_integrity")
        return self


class ReportEnvelope(EvidenceModel):
    schema_version: Literal["table-evidence-artifact/v1"]
    job_id: SafeId
    generation: NonNegativeInt
    source_file_id: SafeId
    ir_file_id: SafeId
    ir_file_sha256: Checksum
    report: TableEvidenceReport


class ReportDescriptor(EvidenceModel):
    schema_version: Literal["table-evidence/v1"]
    report_file_id: SafeId
    object_version: SafeId
    checksum_sha256: Checksum
    size_bytes: NonNegativeInt
    report_sha256: str
    generation: NonNegativeInt
    ir_file_id: SafeId
    ir_file_sha256: Checksum
    preparation: EvidencePreparation


class TableEvidenceView(EvidenceModel):
    job_id: SafeId
    generation: NonNegativeInt
    ir_file_id: SafeId | None
    result_file_id: SafeId | None
    evidence_status: Literal["available", "legacy_unavailable", "not_ready"]
    report_file_id: SafeId | None = None
    report_sha256: str | None = None
    summary: dict
    tables: list


def _read_model(model, value):
    try:
        return model.model_validate_json(value if isinstance(value, bytes) else canonical_json_bytes(value))
    except (ValueError, TypeError, ValidationError):
        raise TableEvidenceError("table_evidence_integrity") from None


def has_evidence(metadata: dict) -> bool:
    return any(key in metadata for key in ("table_evidence", "table_evidence_report", "table_evidence_summary", "table_evidence_preparation"))


def ensure_selected_result_descriptor(job: DocumentJobRecord, result: DocumentFileRecord) -> None:
    """receipt 存在时先按原文件 owner 的不可变合同对账，不能删声明降级旧协议。"""
    receipt = job.prepared_result
    if receipt is None:
        return
    if receipt.generation != job.retry_count or receipt.document_ir_file_id != job.document_ir_file_id:
        raise TableEvidenceError("table_evidence_integrity")
    try:
        # 复用原 owner 的严格描述比较；到期/删除仍留给实际物化，保留旧失败映射。
        ensure_result_descriptor_matches(result, receipt.file)
    except (ValueError, TypeError):
        raise TableEvidenceError("table_evidence_integrity") from None


def validate_candidate_binding(job, candidate):
    """锁内纯校验声明闭合；实物校验由应用在 prepare/完成前锁外执行。"""
    ensure_selected_result_descriptor(job, candidate)
    if not has_evidence(candidate.metadata):
        return None
    report = read_table_evidence(candidate.metadata.get("table_evidence"))
    descriptor = _read_model(ReportDescriptor, candidate.metadata.get("table_evidence_report"))
    summary = {**table_evidence_summary(report), "report_file_id": descriptor.report_file_id,
               "generation": descriptor.generation, "ir_file_sha256": descriptor.ir_file_sha256}
    if (descriptor.report_sha256 != report.report_sha256 or descriptor.generation != job.retry_count
            or descriptor.ir_file_id != job.document_ir_file_id
            or "sha256:" + report.docx_sha256 != candidate.checksum_sha256
            or candidate.metadata.get("table_evidence_summary") != summary
            or candidate.expires_at != descriptor.preparation.docx_expires_at):
        raise TableEvidenceError("table_evidence_integrity")
    return descriptor, report, summary


def save_report(job, ir_file, ir_bytes, metadata, file_service):
    """一次捕获政策及 t0，先保存独立报告；不修改 DOCX 字节或延长原件政策。"""
    report = read_table_evidence(metadata["table_evidence"])
    # 两类政策只解析一次，登记服务显式使用冻结绝对期限。
    t0 = utc_now()
    word_days = file_service.retention_days_resolver("generated_word")
    report_days = file_service.retention_days_resolver("quality_report")
    preparation = EvidencePreparation(t0=t0, word_retention_days=word_days, report_retention_days=report_days,
        docx_expires_at=t0 + timedelta(days=word_days), report_expires_at=t0 + timedelta(days=max(word_days, report_days)))
    if (len(ir_bytes) != ir_file.size_bytes or checksum(ir_bytes) != ir_file.checksum_sha256
            or report.ir_model_sha256 != canonical_sha256(DocumentIR.model_validate_json(ir_bytes).model_dump(mode="json"))):
        raise TableEvidenceError("table_evidence_integrity")
    envelope = ReportEnvelope(schema_version="table-evidence-artifact/v1", job_id=job.id,
        generation=job.retry_count, source_file_id=job.source_file_id, ir_file_id=ir_file.id,
        ir_file_sha256=checksum(ir_bytes), report=report)
    version = "table-evidence-" + uuid4().hex
    record = file_service.register_generated_content(tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
        created_by=job.created_by, file_type="quality_report", filename="table-evidence.json", mime_type="application/json",
        content=canonical_json_bytes(envelope.model_dump(mode="json", warnings=False)), expires_at=preparation.report_expires_at,
        object_version=version, metadata={"asset_role": "table_evidence", "object_version": version,
            "schema_version": VERSION, "generation": job.retry_count, "source_file_id": job.source_file_id,
            "ir_file_id": ir_file.id, "ir_file_sha256": checksum(ir_bytes), "report_sha256": report.report_sha256})
    descriptor = ReportDescriptor(schema_version=VERSION, report_file_id=record.id, object_version=version,
        checksum_sha256=record.checksum_sha256, size_bytes=record.size_bytes, report_sha256=report.report_sha256,
        generation=job.retry_count, ir_file_id=ir_file.id, ir_file_sha256=checksum(ir_bytes), preparation=preparation)
    return {**metadata, "table_evidence_report": descriptor.model_dump(mode="json"),
            "table_evidence_summary": {**table_evidence_summary(report), "report_file_id": record.id,
                "generation": job.retry_count, "ir_file_sha256": checksum(ir_bytes)}}, preparation


def checksum(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class VerifiedTableEvidence:
    """已核实物的应用快照，只用于本次调用收尾，不序列化或作为授权凭证。"""
    envelope: ReportEnvelope
    summary: dict
    job: DocumentJobRecord
    files: tuple[DocumentFileRecord, ...]


def table_evidence_snapshot_values(job: DocumentJobRecord) -> tuple:
    """即时重核原有的比较字段；id 仅用于仓储寻址，删除状态独立判断。"""
    return (job.archived_at, job.tenant_id, job.company_id, job.created_by, job.source_file_id,
        job.retry_count, job.document_ir_file_id, job.result_file_id, job.prepared_result, job.status)


def _ensure_current_snapshot(job, files, *, file_repository, job_repository):
    if not job_repository.is_document_job_table_evidence_snapshot_current(job):
        raise TableEvidenceError("table_evidence_integrity")
    for file in files:
        if (file_repository.get_document_file(file.id) != file or file.expires_at is None
                or (retained_file_expiry(file, file_repository) is not None and retained_file_expiry(file, file_repository) <= utc_now())
                or file.deletion_claim is not None or file.status not in {"uploaded", "pending_upload"}):
            raise TableEvidenceError("table_evidence_integrity")


def recheck_verified_report(verified: VerifiedTableEvidence, *, file_repository, job_repository) -> None:
    """全部后续外部 I/O 完成后、完成 CAS 前重核同一实物快照；不重新读取报告字节。"""
    _ensure_current_snapshot(verified.job, verified.files, file_repository=file_repository, job_repository=job_repository)


def verify_report(job, result, *, file_repository, file_service, job_repository):
    """读取同一报告/IR/DOCX并重建事实，两侧核对描述及当前任务；无 I/O 进入锁。"""
    binding = validate_candidate_binding(job, result)
    if binding is None:
        return None
    descriptor, core, summary = binding
    snapshot = job.model_copy(deep=True)
    files = []
    def current():
        _ensure_current_snapshot(snapshot, files, file_repository=file_repository, job_repository=job_repository)
    def load(file_id, *, pending=False):
        file = file_repository.get_document_file(file_id)
        if file is None:
            raise FileNotFoundError("表格报告依赖文件不存在。")
        if ((file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.status != "uploaded" and not (pending and file.status == "pending_upload")):
            raise TableEvidenceError("table_evidence_integrity")
        files.append(file.model_copy(deep=True))
        current()
        try:
            data = file_service.read_file_content(file)
        except FileNotFoundError:
            raise FileNotFoundError("表格报告依赖内容不存在。") from None
        except Exception as error:
            response = getattr(error, "response", None)
            details = response.get("Error") if isinstance(response, dict) else None
            if isinstance(details, dict) and details.get("Code") in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError("表格报告依赖内容不存在。") from None
            raise RuntimeError("表格报告存储暂不可用。") from None
        current()
        if len(data) != file.size_bytes or checksum(data) != file.checksum_sha256:
            raise TableEvidenceError("table_evidence_integrity")
        return file, data
    current()
    report_file, report_bytes = load(descriptor.report_file_id)
    if (report_file.file_type != "quality_report" or report_file.mime_type != "application/json"
            or report_file.metadata != {"asset_role": "table_evidence", "object_version": descriptor.object_version,
                "schema_version": VERSION, "generation": job.retry_count, "source_file_id": job.source_file_id,
                "ir_file_id": job.document_ir_file_id, "ir_file_sha256": descriptor.ir_file_sha256,
                "report_sha256": core.report_sha256}
            or report_file.size_bytes != descriptor.size_bytes or report_file.checksum_sha256 != descriptor.checksum_sha256
            or report_file.expires_at != descriptor.preparation.report_expires_at
            or report_file.expires_at < result.expires_at):
        raise TableEvidenceError("table_evidence_integrity")
    envelope = _read_model(ReportEnvelope, report_bytes)
    if (envelope.job_id != job.id or envelope.generation != job.retry_count or envelope.source_file_id != job.source_file_id
            or envelope.ir_file_id != job.document_ir_file_id or envelope.ir_file_sha256 != descriptor.ir_file_sha256
            or envelope.report != core):
        raise TableEvidenceError("table_evidence_integrity")
    ir_file, ir_bytes = load(job.document_ir_file_id)
    result_file, result_bytes = load(result.id, pending=True)
    if (ir_file.file_type != "document_ir" or ir_file.checksum_sha256 != descriptor.ir_file_sha256
            or result_file.file_type != "generated_word"):
        raise TableEvidenceError("table_evidence_integrity")
    try:
        ensure_result_descriptor_matches(result_file, result)
    except (ValueError, TypeError):
        raise TableEvidenceError("table_evidence_integrity") from None
    try:
        document = DocumentIR.model_validate_json(ir_bytes)
        if document.metadata.job_id != job.id or document.metadata.source_file_id != job.source_file_id:
            raise TableEvidenceError("table_evidence_integrity")
        actual = validate_persisted_renderer_content(document, result_bytes, result.metadata,
            expected_template_version_id=result.metadata.get("template_version_id"))
        if actual.get("table_evidence") != core.model_dump(mode="json", warnings=False):
            raise TableEvidenceError("table_evidence_integrity")
    except (ValueError, TypeError, KeyError):
        raise TableEvidenceError("table_evidence_integrity") from None
    current()
    return VerifiedTableEvidence(envelope, summary, snapshot, tuple(files))
