"""列表静态事实与 file 查询；最终有效复核由当前文件和请求时刻决定。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Protocol, get_args

from app.domains.document_jobs.list_query_facts import (
    datetime_query_key, equality_key, receipt_file_key, table_evidence_snapshot_key,
)
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationQaStatus
from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.document_jobs.review import effective_review_job, receipt_identity
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import review_source_descriptor
from app.domains.resources.models import utc_now
from app.domains.translation.modes import TRANSLATION_MODE_SPECS

TRANSLATION_LIST_MODES = tuple(spec.document_job_mode for spec in TRANSLATION_MODE_SPECS.values() if spec.is_translation)
DOCUMENT_JOB_LIST_SORTS = {
    "created_at_asc": ("created", False), "created_at_desc": ("created", True),
    "updated_at_asc": ("updated", False), "updated_at_desc": ("updated", True),
}


class DocumentJobSearchable(Protocol):
    id: str
    source_file_id: str
    request_snapshot: dict[str, Any]
    error_code: str | None
    error_message: str | None


def document_job_search_values(job: DocumentJobSearchable) -> list[str]:
    source = job.request_snapshot.get("source_file")
    filename = source.get("original_filename") if isinstance(source, dict) else None
    return [value for value in (job.id, job.source_file_id,
            filename if isinstance(filename, str) else None, job.error_code, job.error_message) if value]


@dataclass(frozen=True)
class DocumentJobListQuery:
    tenant_id: str
    company_id: str
    created_by: str | None = None
    page: int = 1
    page_size: int = 20
    statuses: tuple[str, ...] | None = None
    translation_qa_status: str | None = None
    q: str | None = None
    sort: str = "created_at_desc"
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    as_of: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class DocumentJobListResult:
    items: list[DocumentJobRecord]
    total: int
    summary: dict[str, int]
    filtered_summary: dict[str, int]
    translation_qa_summary: dict[str, int]
    observed_results: dict[str, DocumentFileRecord | None] = field(default_factory=dict)


class DocumentJobListProjectionUnavailable(Exception):
    """查询所需派生事实尚未就绪；GET 不修复或全量回退。"""


class DocumentJobListProjectionUnstable(ValueError):
    """raw 缺少参与比较的动态默认时间，不能冻结回填时刻。"""


def _put_key(projection: dict, name: str, value: tuple[str, bool]) -> None:
    projection[name], comparable = value
    projection[name + "_comparable"] = int(comparable)


def _error_code(error: Exception) -> str:
    return {ValueError: "value", TypeError: "type", OverflowError: "overflow"}[type(error)]


def raise_projection_rule_error(code: str) -> None:
    kind = {"value": ValueError, "type": TypeError, "overflow": OverflowError}[code]
    raise kind("列表读视图的复核事实无法按原规则比较。")


def document_job_list_projection(job: DocumentJobRecord) -> dict[str, Any]:
    projection = {name: getattr(job, name) for name in (
        "id", "tenant_id", "company_id", "created_by", "status", "mode", "review_status", "stage", "delivery_status")}
    projection.update(version=2, deleted=int(job.deleted_at is not None), archived=int(job.archived_at is not None),
        search=[value.casefold() for value in document_job_search_values(job)],
        result_present=int(job.result_file_id is not None), result_id=job.result_file_id or "",
        quality_error="", binding_error="", review_path="unbound", binding_revision="",
        binding_checksum="", descriptor_key="", descriptor_key_comparable=1,
        receipt_present=int(job.prepared_result is not None), receipt_expiry_present=0,
        receipt_expiry_us=0, receipt_expiry_kind="", receipt_key="", receipt_key_comparable=1)
    for name in ("created", "updated"):
        projection[name + "_us"], projection[name + "_kind"] = datetime_query_key(getattr(job, name + "_at"))
    try:
        projection["effective_quality"] = effective_quality_status(job)
    except (ValueError, TypeError) as error:
        # 现有质量 owner 的数据错误在 V 域读取时出现；写投影不提前扩大失败分支。
        projection["effective_quality"] = job.quality_status
        projection["quality_error"] = _error_code(error)
    binding = job.current_review_binding
    if binding is not None and job.current_review_record_id is not None:
        if binding.generation != job.retry_count or binding.result_file_id != job.result_file_id:
            projection["review_path"] = "invalid"
        else:
            try:
                identity_matches = binding.receipt_sha256 == receipt_identity(job)
            except (ValueError, TypeError, OverflowError) as error:
                projection["binding_error"] = _error_code(error)
                identity_matches = False
            projection["review_path"] = ("invalid" if not identity_matches else
                                         "verified" if binding.binding_state == "verified" else "unbound")
        if projection["review_path"] == "verified":
            projection["binding_revision"] = equality_key(binding.file_review_source_revision)[0]
            projection["binding_checksum"] = binding.result_sha256
            _put_key(projection, "descriptor_key", equality_key(binding.descriptor))
    if job.prepared_result is not None:
        file = job.prepared_result.file
        _put_key(projection, "receipt_key", receipt_file_key(file))
        projection["receipt_expiry_present"] = int(file.expires_at is not None)
        if file.expires_at is not None:
            projection["receipt_expiry_us"], projection["receipt_expiry_kind"] = datetime_query_key(file.expires_at)
    _put_key(projection, "table_snapshot_key", table_evidence_snapshot_key(job))
    return projection


def document_file_review_projection(file: DocumentFileRecord) -> dict[str, Any]:
    projection = {name: getattr(file, name) for name in ("id", "tenant_id", "company_id", "file_type")}
    projection.update(version=1, job_present=int(file.job_id is not None), job_id=file.job_id or "")
    if file.file_type != "generated_word":
        return projection
    projection.update(status=file.status, deletion_claim=int(file.deletion_claim is not None),
        revision=equality_key(file.review_source_revision)[0], checksum_present=int(file.checksum_sha256 is not None),
        checksum=file.checksum_sha256 or "", expiry_present=int(file.expires_at is not None),
        expiry_us=0, expiry_kind="", descriptor_error="", descriptor_key="", descriptor_key_comparable=1)
    if file.expires_at is not None:
        projection["expiry_us"], projection["expiry_kind"] = datetime_query_key(file.expires_at)
    try:
        _put_key(projection, "descriptor_key", equality_key(review_source_descriptor(file)))
    except (ValueError, TypeError, OverflowError) as error:
        # 如边界日期转 UTC 溢出，只在原 descriptor 比较前缀实际可达时拒绝。
        projection["descriptor_error"] = _error_code(error)
    _put_key(projection, "receipt_key", receipt_file_key(file))
    return projection


def _raw_model(payload: str | dict, model):
    raw = json.loads(payload) if isinstance(payload, str) else payload
    # 非对象等模型错误仍交给原模型，不把它转换为缺键默认值。
    if isinstance(raw, dict):
        if model is DocumentJobRecord:
            receipt = raw.get("prepared_result")
            file = receipt.get("file") if isinstance(receipt, dict) else None
            if not {"created_at", "updated_at"} <= raw.keys() or (
                isinstance(file, dict) and not {"created_at", "updated_at"} <= file.keys()
            ):
                raise DocumentJobListProjectionUnstable("missing_time_key")
        elif raw.get("file_type") == "generated_word" and "created_at" not in raw:
            raise DocumentJobListProjectionUnstable("missing_time_key")
    return model.model_validate_json(payload) if isinstance(payload, str) else model.model_validate(raw)


def document_job_list_projection_from_raw(payload: str | dict) -> dict[str, Any]:
    return document_job_list_projection(_raw_model(payload, DocumentJobRecord))


def document_file_review_projection_from_raw(payload: str | dict) -> dict[str, Any]:
    return document_file_review_projection(_raw_model(payload, DocumentFileRecord))


def dump_document_job_list_projection(job: DocumentJobRecord) -> str:
    return json.dumps(document_job_list_projection(job), ensure_ascii=False)


def query_document_job_records(jobs: list[DocumentJobRecord], query: DocumentJobListQuery, *, file_repository) -> DocumentJobListResult:
    """file 后端只观察一次当前主件；页内服务复用观察，不新增跨全表锁。"""
    visible = [job for job in jobs if job.tenant_id == query.tenant_id and job.company_id == query.company_id
               and (query.created_by is None or job.created_by == query.created_by)
               and job.deleted_at is None and (query.include_archived or job.archived_at is None)]
    observations = {}
    views = []
    for job in visible:
        candidate = None
        observed = None
        if job.status == "succeeded" and job.stage == "completed" and job.result_file_id is not None:
            candidate = file_repository.get_document_file(job.result_file_id)
            if candidate is not None and (candidate.tenant_id, candidate.company_id, candidate.job_id,
                    candidate.file_type, candidate.status) == (job.tenant_id, job.company_id, job.id, "generated_word", "uploaded"):
                observed = candidate
                # 删除预留的 ApiError 先发生；其他 ApiError 不影响复核观察，只有比较类型错误会传播。
                if candidate.deletion_claim is None and candidate.expires_at is not None:
                    candidate.expires_at <= query.as_of
        observations[job.id] = candidate
        views.append(effective_review_job(job, observed, now=query.as_of))
    base = []
    for job in views:
        if query.statuses is not None and job.status not in query.statuses:
            continue
        if query.q is not None and not any(query.q in value.casefold() for value in document_job_search_values(job)):
            continue
        if query.created_from is not None and job.created_at < query.created_from:
            continue
        if query.created_to is not None and job.created_at > query.created_to:
            continue
        base.append(job)
    qa_counts = Counter(job.review_status for job in base if job.mode in TRANSLATION_LIST_MODES)
    filtered = [job for job in base if query.translation_qa_status is None or (
        job.mode in TRANSLATION_LIST_MODES and (query.translation_qa_status == "all"
                                              or job.review_status == query.translation_qa_status))]
    column, descending = DOCUMENT_JOB_LIST_SORTS[query.sort]
    filtered.sort(key=lambda job: (getattr(job, column + "_at"), job.id), reverse=descending)
    start = (query.page - 1) * query.page_size
    page = filtered[start:start + query.page_size]
    raw = {job.id: job for job in visible}
    return DocumentJobListResult([raw[job.id] for job in page], len(filtered),
        dict(Counter(job.status for job in visible)), dict(Counter(job.status for job in filtered)),
        {key: qa_counts.get(key, 0) for key in get_args(DocumentJobTranslationQaStatus)},
        {job.id: observations[job.id] for job in page})
