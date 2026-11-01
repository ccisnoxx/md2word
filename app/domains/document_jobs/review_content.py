"""QA-603 专用授权内容读取；只消费现有产物，私有观察不进入 DTO。"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import html
import json
import math
import re

from bs4 import BeautifulSoup
from app.core.errors import ApiError
from app.domains.document_jobs.preview import (
    _is_preview_storage_error, _PreviewUnavailable, _read_artifact,
    read_current_preview_evidence,
)
from app.domains.document_jobs.quality_review_projection import (
    ReviewBlocksCursor, ReviewBlockContentCursor, encode_cursor, project_source, project_table_item,
)
from app.domains.document_jobs.review import digest
from app.domains.document_jobs.schemas import (
    DocumentReviewComponentResponse as Component,
    DocumentReviewContentSnapshotResponse as Snapshot,
    DocumentReviewSourceSpanResponse as Span,
    DocumentReviewLocationResponse as Location,
    DocumentReviewBlockItemResponse as Block,
    DocumentReviewBlockFlagResponse as Flag,
    DocumentReviewBlocksResponse, DocumentReviewBlockDetailResponse,
    DocumentReviewContentPartResponse as Part,
    DocumentReviewTermResponse as Term,
    DocumentReviewBatchResponse as Batch,
    DocumentReviewTokenCountsResponse as TokenCounts,
)
from app.domains.document_jobs.workflow import reduce_translation_generation
from app.domains.resources.models import utc_now
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.integrity import items_sha256
from app.domains.translation.models import TranslationTextItem
from app.domains.translation.modes import is_translation_document_job_mode, spec_for_document_job_mode
from app.services.document_ir.layout_signals import pdf_point_bbox
from app.services.document_ir.models import DocumentIR
from app.services.preview.models import PreviewPolicy
from app.services.preview.page_mapping import PageMapping
from app.services.renderer.evidence import controlled_quality_flags

MAX_IR_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 100000
MAX_LOG_BYTES = 8 * 1024 * 1024
MAX_LOG_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
TEXT_CHARS = 4096
HTML_SUMMARY_CHARS = 2048


class _ContentLimit(Exception):
    """固定阅读预算耗尽，不能返回看似完整的部分证据。"""


def _conflict(reason="quality_evidence_conflict"):
    return ApiError(409, "conflict", "审核内容来源无法确认，请刷新后核对。", reason_code=reason)


def _changed():
    return _conflict("quality_source_changed")


@contextmanager
def _storage():
    """仅归一化已知存储故障；程序错误仍交安全路由记录。"""
    try:
        yield
    except Exception as exc:
        if _is_preview_storage_error(exc):
            raise ApiError(503, "service_unavailable", "审核内容存储暂不可用。",
                           reason_code="quality_storage_unavailable") from None
        raise


def _job_identity(job):
    return digest(job.model_dump(mode="json", include={
        "id", "tenant_id", "company_id", "created_by", "retry_count", "source_file_id",
        "source_document_ir_file_id", "document_ir_file_id", "result_file_id", "prepared_result",
        "word_preview_state", "request_snapshot", "mode", "status", "stage", "deleted_at",
    }))


def _batch_identity(job, batches):
    # 覆盖所有当前代记录，未被本页采用的重试/split 同样影响下一次证据资格。
    fields = {"id", "job_id", "generation", "job_retry_count", "source_document_ir_file_id",
              "root_batch_id", "parent_batch_id", "item_ids", "item_count", "status", "attempt_count",
              "result_file_id", "ai_call_log_file_ids", "language_pair", "term_version_id",
              "term_snapshot_hash", "retryable", "max_attempts", "provider_call_budget"}
    return digest({"job": _job_identity(job), "batches": [
        batch.model_dump(mode="json", include=fields) for batch in sorted(batches, key=lambda value: value.id)]})


@dataclass
class _Read:
    service: object
    user: object
    job: object
    result: object
    batches: list = field(default_factory=list)
    batch_identity: str | None = None
    observed: dict = field(default_factory=dict)
    live_files: list = field(default_factory=list)
    source_ir: DocumentIR | None = None
    final_ir: DocumentIR | None = None
    basis: DocumentIR | None = None
    mapping: object | None = None
    tables: list = field(default_factory=list)
    references: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    batch_evidence: list = field(default_factory=list)
    source_units: dict = field(default_factory=dict)
    target_units: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)
    snapshot: Snapshot | None = None
    limited: bool = False
    mapping_by_id: dict = field(default_factory=dict)
    pages_by_index: dict = field(default_factory=dict)
    fragments_by_block: dict = field(default_factory=dict)
    tables_by_block: dict = field(default_factory=dict)

    def observe(self, file_id):
        if file_id not in self.observed:
            with _storage():
                self.observed[file_id] = self.service.file_repository.get_document_file(file_id)
        return self.observed[file_id]

    def read_ir(self, file_id, *, required=False):
        if file_id is None:
            return None
        record = self.observe(file_id)
        if record is None:
            if required:
                raise ApiError(404, "not_found", "当前文档内容不存在。", reason_code="review_content_missing")
            return None
        if (record.tenant_id, record.company_id, record.job_id) != (
                self.job.tenant_id, self.job.company_id, self.job.id):
            raise ApiError(403, "forbidden", "文档内容与任务归属不匹配。", reason_code="review_access_denied")
        if record.file_type != "document_ir" or record.mime_type != "application/json":
            raise _conflict()
        if record.status != "uploaded" or record.expires_at is not None and record.expires_at <= utc_now():
            if required:
                raise _conflict("review_content_unavailable")
            return None
        generation = record.metadata.get("retry_count")
        if generation is not None and (type(generation) is not int or not 0 <= generation <= self.job.retry_count):
            raise _conflict()
        if record.metadata.get("source_file_id", self.job.source_file_id) != self.job.source_file_id:
            raise _conflict()
        if record.size_bytes > MAX_IR_BYTES:
            raise _ContentLimit()
        raw = self.read_bytes(record, required=required)
        if raw is None:
            return None
        if len(raw) > MAX_IR_BYTES:
            raise _ContentLimit()
        try:
            document = DocumentIR.model_validate_json(raw)
        except (ValueError, TypeError):
            raise _conflict() from None
        if (document.metadata.job_id, document.metadata.source_file_id) != (self.job.id, self.job.source_file_id):
            raise _conflict()
        if len(document.blocks) > MAX_BLOCKS:
            raise _ContentLimit()
        ids = [block.id for block in document.blocks]
        if len(ids) != len(set(ids)) or any(block.order < 0 for block in document.blocks):
            raise _conflict()
        return document

    def read_bytes(self, record, *, required=False):
        if self.service.file_upload_service is None:
            raise ApiError(503, "service_unavailable", "审核内容存储暂不可用。", reason_code="quality_storage_unavailable")
        try:
            with _storage():
                raw = _read_artifact(record, self.service.file_upload_service)
        except _PreviewUnavailable:
            if required:
                raise ApiError(404, "not_found", "当前文档内容不存在。", reason_code="review_content_missing") from None
            return None
        except ValueError:
            raise _conflict() from None
        self.live_files.append(record)
        return raw

    def finish(self):
        with _storage():
            current = self.service._review_api_job(self.job.id, self.user)
            if _job_identity(current) != _job_identity(self.job):
                raise _changed()
            self.service._finish_review_read(self.job, self.result, self.user, preview=True)
            for file_id, record in self.observed.items():
                if self.service.file_repository.get_document_file(file_id) != record:
                    raise _changed()
            if any(record.expires_at is not None and record.expires_at <= utc_now() for record in self.live_files):
                raise _changed()
            if self.batch_identity is not None:
                current_job, batches = self.service.get_translation_batch_snapshot(self.job.id, user=self.user)
                if _batch_identity(current_job, batches) != self.batch_identity:
                    raise _changed()


def _component(availability, reason=None):
    return Component(availability=availability, reason_code=reason)


def _preview(read):
    policy = read.job.request_snapshot.get("word_preview")
    if policy is None or PreviewPolicy.model_validate(policy).backend == "disabled":
        return _component("disabled", "disabled"), _component("unavailable", "preview_unavailable")
    from app.domains.document_jobs.preview_state import _confirmed
    state = read.job.word_preview_state
    if state is None or not _confirmed(state.current_run):
        return _component("not_ready", "not_ready"), _component("unavailable", "preview_unavailable")
    if read.service.file_upload_service is None:
        raise ApiError(503, "service_unavailable", "审核内容存储暂不可用。", reason_code="quality_storage_unavailable")
    try:
        with _storage():
            evidence = read_current_preview_evidence(read.job, read.service.file_repository,
                read.service.file_upload_service, include_mapping=True)
    except ValueError:
        raise _conflict() from None
    for record in evidence.observation.files:
        read.observed[record.id] = record
        read.live_files.append(record)
    if not evidence.observation.available or state.current_run.status != "succeeded":
        return _component("unavailable", "preview_artifact_unavailable"), _component("unavailable", "preview_unavailable")
    read.mapping = PageMapping.model_validate(evidence.page_mapping) if evidence.page_mapping is not None else None
    return _component("available"), _component(
        "available" if read.mapping and read.mapping.status != "unavailable" else "unavailable",
        read.mapping.reason_code if read.mapping else "legacy_evidence_missing")


def _units(document):
    if document is None:
        return {}
    targets, items = DocumentIRTranslationService.extract_translation_items(document)
    return {target.item_id: (target, item.text) for target, item in zip(targets, items)}


def _translation(read):
    if not is_translation_document_job_mode(read.job.mode):
        return _component("not_applicable")
    if read.source_ir is None:
        return _component("unavailable", "source_content_unavailable")
    read.source_units = _units(read.source_ir)
    read.target_units = _units(read.final_ir)
    if read.final_ir is not None:
        # 稳定 target 归属和索引必须一致；不按文本、相似位置或重新拆句配对。
        if set(read.source_units) != set(read.target_units) or any(
                read.source_units[key][0] != read.target_units[key][0] for key in read.source_units):
            raise _conflict()
    source_record = read.observe(read.job.source_document_ir_file_id)
    role = source_record.metadata.get("translation") if source_record else None
    if role is not None and (not isinstance(role, dict) or role.get("role") != "source" or role.get("applied") is not False):
        raise _conflict()
    if read.job.status not in {"succeeded", "failed", "canceled"}:
        # 原运行中 tree owner 要求权威 source/config 计划；GET 不加载资源重建。
        return _component("unavailable", "translation_binding_unavailable")
    summary = reduce_translation_generation(job_id=read.job.id, job_status=read.job.status,
        job_stage=read.job.stage, generation=read.job.retry_count, expected_plans=(), batches=read.batches)
    leaves = {row.batch_id for row in summary.rows if row.is_effective_leaf}
    final_file = read.observe(read.job.document_ir_file_id) if read.job.document_ir_file_id else None
    if final_file is not None and final_file.metadata.get("retry_count", read.job.retry_count) < read.job.retry_count:
        # 权威指针允许复用旧代 IR；它不证明本代翻译日志的资格。
        return _component("unavailable", "translation_binding_unavailable")
    metadata = final_file.metadata.get("translation") if final_file is not None else None
    if not isinstance(metadata, dict) or metadata.get("applied") is not True:
        return _component("unavailable", "translation_binding_unavailable")
    if (metadata.get("source_document_ir_file_id") != read.job.source_document_ir_file_id
            or set(metadata.get("batch_ids", [])) != {batch.id for batch in read.batches if batch.status == "succeeded" and batch.id in leaves}
            or set(metadata.get("ai_call_log_file_ids", [])) != {
                log_id for batch in read.batches if batch.status == "succeeded" and batch.id in leaves
                for log_id in batch.ai_call_log_file_ids}):
        raise _conflict()
    source_file = read.observe(read.job.source_document_ir_file_id)
    covered, total_log_bytes = set(), 0
    for batch in read.batches:
        if batch.id not in leaves or batch.status not in {"succeeded", "failed"}:
            continue
        if (batch.job_id != read.job.id or batch.generation != read.job.retry_count
                or batch.job_retry_count != read.job.retry_count
                or batch.source_document_ir_file_id != source_file.id
                or batch.language_pair != spec_for_document_job_mode(read.job.mode).language_pair
                or len(batch.item_ids) != len(set(batch.item_ids))
                or batch.item_count != len(batch.item_ids)
                or not set(batch.item_ids) <= read.source_units.keys()):
            raise _conflict()
        for log_id in batch.ai_call_log_file_ids:
            record = read.observe(log_id)
            if record is None or record.status in {"deleted", "expired"} or (
                    record.expires_at is not None and record.expires_at <= utc_now()):
                continue
            if (record.tenant_id, record.company_id, record.job_id) != (
                    read.job.tenant_id, read.job.company_id, read.job.id):
                raise ApiError(403, "forbidden", "翻译证据与任务归属不匹配。", reason_code="review_access_denied")
            if record.file_type != "ai_call_log" or record.mime_type != "application/json" or record.status != "uploaded":
                raise _conflict()
            if type(record.metadata.get("attempt")) is not int:
                raise _conflict()
            if record.metadata.get("attempt") < batch.attempt_count:
                # 领取新 attempt 后记录里仍保留旧日志；不把历史成功当当前证据。
                continue
            if record.metadata.get("attempt") > batch.attempt_count:
                raise _conflict()
            if any(record.metadata.get(key) != value for key, value in {
                    "batch_id": batch.id, "retry_count": read.job.retry_count}.items()):
                raise _conflict()
            total_log_bytes += record.size_bytes
            if record.size_bytes > MAX_LOG_BYTES or total_log_bytes > MAX_LOG_TOTAL_BYTES:
                raise _ContentLimit()
            raw = read.read_bytes(record)
            if raw is None:
                continue
            if len(raw) > MAX_LOG_BYTES:
                raise _ContentLimit()
            try:
                payload = json.loads(raw)
                _log_evidence(read, batch, record, payload, source_file)
            except (ValueError, TypeError, KeyError, AttributeError):
                raise _conflict() from None
            if any(entry[0] == batch.id for entry in read.batch_evidence):
                covered.update(batch.item_ids)
    return _component("available" if covered == set(read.source_units) and read.batch_evidence else "unavailable",
                      None if covered == set(read.source_units) and read.batch_evidence else "translation_evidence_incomplete")


def _log_evidence(read, batch, record, payload, source_file):
    if (payload.get("schema_version") != "ai-call-log/v1" or payload.get("job_id") != read.job.id
            or payload.get("batch", {}).get("batch_id") != batch.id
            or payload.get("batch", {}).get("attempt") != batch.attempt_count
            or payload.get("batch", {}).get("parent_batch_id") != batch.parent_batch_id
            or payload.get("language_pair") != batch.language_pair
            or payload.get("term_version_id") != batch.term_version_id
            or payload.get("term_snapshot_hash") != batch.term_snapshot_hash):
        raise _conflict()
    integrity = payload.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("binding") is None:
        return
    binding = integrity["binding"]
    expected = {"job_id": read.job.id, "batch_id": batch.id, "root_batch_id": batch.root_batch_id,
        "parent_batch_id": batch.parent_batch_id, "attempt": batch.attempt_count, "generation": read.job.retry_count,
        "source_document_ir_file_id": source_file.id, "source_document_ir_sha256": source_file.checksum_sha256,
        "term_snapshot_hash": batch.term_snapshot_hash}
    resources = read.job.request_snapshot.get("resources")
    resources = resources if isinstance(resources, dict) else {}
    profile = resources.get("translation_profile")
    expected["profile_snapshot_hash"] = profile.get("snapshot_hash") if isinstance(profile, dict) else None
    expected["prompt_content_hash"] = resources.get("translation_prompt_content_hash")
    if any(type(binding.get(key)) is not type(value) or binding.get(key) != value for key, value in expected.items()):
        raise _conflict()
    items = payload.get("request", {}).get("redacted_items", [])
    if [item.get("id") for item in items] != batch.item_ids:
        raise _conflict()
    # redacted request 指向编码后的文本；只用已有 source 摘要核原文，不重跑 Codec 冒充历史验证。
    source_items = tuple(TranslationTextItem(id=item_id, text=read.source_units[item_id][1]) for item_id in batch.item_ids)
    if integrity.get("source_sha256") != items_sha256(source_items):
        raise _conflict()
    if read.final_ir is not None and integrity.get("status") == "passed" and payload.get("status") == "succeeded":
        blocks = {block.id: block for block in read.final_ir.blocks}
        html_nodes = {}
        target_items = []
        for item_id in batch.item_ids:
            target = read.target_units[item_id][0]
            block = blocks[target.block_id]
            # 提取器的文本用于展示会 strip；持久 hash 必须沿原 field/index 取实际回填值。
            if target.field == "text":
                text = block.text
            elif target.field == "list_items":
                text = block.list_items[target.index]
            else:
                if block.id not in html_nodes:
                    html_nodes[block.id] = [str(node) for node in BeautifulSoup(block.html, "html.parser").find_all(string=True) if str(node).strip()]
                text = html_nodes[block.id][target.index]
            target_items.append(TranslationTextItem(id=item_id, text=text))
        if integrity.get("restored_sha256") != items_sha256(tuple(target_items)):
            raise _conflict()
    status = payload.get("status")
    if status not in {"succeeded", "failed"} or record.metadata.get("status") != status:
        raise _conflict()
    values = {name: integrity[name] for name in (
        "schema_version", "validator_version", "codec_version", "instruction_version", "instruction_sha256",
        "expected_item_count", "actual_item_count", "checked_item_count",
        "failed_item_count", "source_sha256", "restored_sha256") if name in integrity}
    values["integrity_status"] = integrity.get("status")
    # 错误码必须来自已有 Validator 受控集合，不回传 Provider 异常消息。
    from app.domains.translation.integrity import _MESSAGES
    values["error_code"] = integrity.get("error_code") if integrity.get("error_code") in _MESSAGES else None
    for name in ("expected_token_counts", "actual_token_counts"):
        values[name] = TokenCounts.model_validate(integrity[name]) if integrity.get(name) is not None else None
    provider = payload.get("provider", {})
    backend = provider.get("backend")
    model = provider.get("model")
    if model is not None and (not isinstance(model, str) or "://" in model or model.startswith("/") or len(model) > 200):
        model = None
    safe = Batch(batch_id=batch.id, attempt=batch.attempt_count, status=status,
        provider_backend=backend if backend in {"fake", "openai_compatible"} else None,
        provider_model=model, **values)
    read.batch_evidence.append((batch.id, set(batch.item_ids), safe))
    for trace in payload.get("glossary_trace", []):
        unit_id = trace.get("segment_id")
        if unit_id not in batch.item_ids or trace.get("batch_id") != batch.id:
            raise _conflict()
        read.terms.append(Term(unit_id=unit_id, batch_id=batch.id,
            source_term=trace["source_term"], target_term=trace["target_term"],
            version=trace.get("translation_term_version")))


def _load(service, job_id, user):
    with _storage():
        job = service._review_api_job(job_id, user)
        service._ensure_job_not_deleted(job, reason_code="job_deleted")
        result = service._review_api_file(job)
    read = _Read(service, user, job, result)
    if is_translation_document_job_mode(job.mode):
        with _storage():
            snapshot_job, read.batches = service.get_translation_batch_snapshot(job.id, user=user)
        if _job_identity(snapshot_job) != _job_identity(job):
            raise _changed()
        read.batch_identity = _batch_identity(snapshot_job, read.batches)
    read.observe(job.source_file_id)
    source_pdf = read.observed[job.source_file_id]
    if source_pdf is not None and ((source_pdf.tenant_id, source_pdf.company_id) != (job.tenant_id, job.company_id)
            or not service._file_belongs_to_job(job, source_pdf) or source_pdf.file_type != "source_pdf"):
        raise ApiError(403, "forbidden", "源 PDF 与任务归属不匹配。", reason_code="review_access_denied")
    basis_id = job.document_ir_file_id or job.source_document_ir_file_id
    try:
        read.basis = read.read_ir(basis_id, required=True)
        if is_translation_document_job_mode(job.mode):
            read.final_ir = read.basis if job.document_ir_file_id else None
            read.source_ir = (read.basis if basis_id == job.source_document_ir_file_id
                              else read.read_ir(job.source_document_ir_file_id))
        else:
            read.source_ir = read.basis
        read.components["source_content"] = _component("available" if read.source_ir else "unavailable", None if read.source_ir else "source_content_unavailable")
        read.components["target_content"] = _component("available" if read.final_ir else "not_applicable" if not is_translation_document_job_mode(job.mode) else "not_ready")
        read.components["translation"] = _translation(read)
        read.components["preview"], read.components["mapping"] = _preview(read)
        if read.basis is not None and any(block.type == "table" for block in read.basis.blocks):
            with _storage():
                evidence = service.get_table_evidence(job.id, user=user, generation=job.retry_count,
                    ir_file_id=job.document_ir_file_id, result_file_id=job.result_file_id)
                reference_snapshot = service._table_reference_snapshot(job, read.observe(basis_id), read.basis)
                references = service._list_table_references_snapshot(reference_snapshot, user=user)
            if evidence.report_file_id:
                read.observe(evidence.report_file_id)
            read.tables = [project_table_item(table) for table in evidence.tables]
            read.references = references.items
            for reference in read.references:
                if reference.file_id:
                    read.observe(reference.file_id)
            read.components["tables"] = _component("available" if evidence.evidence_status == "available" else "unavailable", None if evidence.evidence_status == "available" else "legacy_evidence_missing")
        else:
            read.components["tables"] = _component("not_applicable")
    except _ContentLimit:
        read.limited = True
        read.basis = None
        read.terms, read.batch_evidence, read.tables, read.references = [], [], [], []
        read.components = {key: _component("unavailable", "review_content_limit_exceeded") for key in (
            "source_content", "target_content", "translation", "preview", "mapping", "tables")}
        if not is_translation_document_job_mode(job.mode):
            read.components["translation"] = _component("not_applicable")
    state = job.word_preview_state
    run = state.current_run if state else None
    private_identity = {"job": _job_identity(job), "batch": read.batch_identity,
        "files": {key: value.model_dump(mode="json") if value else None for key, value in read.observed.items()},
        "mapping": read.mapping.mapping_sha256 if read.mapping else None,
        "tables": [table.model_dump(mode="json") for table in read.tables],
        "components": {key: value.model_dump() for key, value in read.components.items()}}
    read.snapshot = Snapshot(snapshot_id=digest(private_identity).removeprefix("sha256:"), source_pdf_file_id=job.source_file_id,
        source_ir_file_id=job.source_document_ir_file_id if is_translation_document_job_mode(job.mode) else basis_id,
        final_ir_file_id=job.document_ir_file_id if is_translation_document_job_mode(job.mode) else None,
        preview_run_id=run.run_id if run else None, preview_revision=state.revision if state else None,
        preview_attempt=run.attempt_count if run else None,
        basis="none" if not basis_id else "final" if job.document_ir_file_id else "source", **read.components)
    # 在同次不可变观察上建索引，列表不逐块重复扫描整份 mapping/fragment 集合。
    read.mapping_by_id = {entry.block_id: entry for entry in read.mapping.entries} if read.mapping else {}
    if read.basis is not None:
        read.pages_by_index = {page.index: page for page in read.basis.pages}
        for group in read.basis.metadata.logical_table_groups:
            for fragment in group.fragments:
                for block_id in {fragment.block_id, fragment.render_owner_block_id} - {None}:
                    read.fragments_by_block.setdefault(block_id, []).append(fragment)
    for table in read.tables:
        for block_id in table.member_block_ids:
            read.tables_by_block.setdefault(block_id, []).append(table)
    return read


def _spans(read, block, entry):
    spans = []
    if entry is not None:
        spans = [(span.get("page_index"), span.get("bbox"), span.get("fragment_id")) for span in entry.source.source_spans]
    if not spans:
        spans = [(fragment.source_span.page_index, fragment.source_span.bbox, fragment.fragment_id)
                 for fragment in read.fragments_by_block.get(block.id, ())]
    if not spans:
        spans = [(block.layout.page_index if block.layout else block.page_index, block.layout.bbox if block.layout else None, None)]
    result = []
    for page_index, bbox, fragment_id in spans:
        page = read.pages_by_index.get(page_index)
        raw_size = page.metadata.get("pdf_page_size") if page else None
        valid_bbox = (isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(
            type(value) in {int, float} and math.isfinite(value) for value in bbox)
            and 0 <= bbox[0] < bbox[2] and 0 <= bbox[1] < bbox[3])
        # 只有能换算为 PDF 点（归一化页或旧的点坐标页）且落在 PDF 页内时才视为已核实；返回值统一为 PDF 点。
        points = pdf_point_bbox(bbox, page) if valid_bbox else None
        verified = bool(points is not None and isinstance(raw_size, list) and len(raw_size) == 2
            and all(type(value) in {int, float} and math.isfinite(value) and value > 0 for value in raw_size)
            and points[2] <= raw_size[0] and points[3] <= raw_size[1])
        result.append(Span(source_page_index=page_index if type(page_index) is int and page_index >= 0 else None,
            bbox=points if verified else tuple(float(value) for value in bbox) if valid_bbox else None,
            page_width=raw_size[0] if verified else None, page_height=raw_size[1] if verified else None,
            coordinate_verified=verified, reason_code=None if verified else "coordinate_space_unverified", fragment_id=fragment_id))
    return result


def _block(read, block):
    entry = read.mapping_by_id.get(block.id)
    if entry is None:
        location = Location(kind="unavailable", preview_page_index=None, confidence="none",
            reason_code=read.components["mapping"].reason_code or "source_unavailable")
    else:
        location = Location(kind=entry.location.kind, preview_page_index=entry.location.preview_page_index,
            confidence=entry.location.confidence, reason_code=entry.location.reason_code,
            bookmark_label=entry.bookmark_name, disposition=entry.disposition,
            representative_block_id=entry.representative_block_id,
            fallback_page_index=entry.fallback.page_index if entry.fallback else None,
            fallback_block_id=entry.fallback.nearest_block_id if entry.fallback else None,
            provenance_status=entry.source.provenance_status)
    tables = read.tables_by_block.get(block.id, ())
    flags = [Flag(code=flag.code, severity=flag.severity, table_id=table.table_id) for table in tables for flag in table.flags]
    flags.extend(Flag(code=code, severity="warning") for code in controlled_quality_flags(block.metadata.get("quality_flags")))
    reconciliation = block.metadata.get("caption_reconciliation")
    # 题注裁决只在主源块展示，不复制私有原文证据，也不写回正式质量状态。
    if not block.metadata.get("source_block_id") and isinstance(reconciliation, dict):
        if reconciliation.get("status") == "uncertain":
            flags.append(Flag(code="caption_binding_uncertain", severity="warning"))
        elif reconciliation.get("status") == "rebound":
            flags.append(Flag(code="caption_reassociated", severity="info"))
    flags = list({(flag.code, flag.severity, flag.table_id): flag for flag in flags}.values())
    # source_type 仅公开解析器已有受控类型，不透传任意 metadata 文本。
    source_type = block.metadata.get("source_type")
    safe_types = {"text", "title", "paragraph", "table", "image", "equation", "formula", "list", "header", "footer", "page_header", "page_footer", "page_number"}
    text = block.text or " ".join(block.list_items or []) or block.latex or " ".join(block.captions)
    return Block(block_id=block.id, order=block.order, block_type=block.type,
        source_type=source_type if source_type in safe_types else None, excerpt=text[:240],
        source_spans=_spans(read, block, entry), location=location, flags=flags, table_ids=[table.table_id for table in tables])


def _text_parts(kind, side, field_name, text, *, unit_id=None, index=None, fragment_id=None):
    for offset in range(0, len(text), TEXT_CHARS):
        yield Part(kind=kind, side=side, field=field_name, index=index, unit_id=unit_id,
            fragment_id=fragment_id, offset=offset, text=text[offset:offset + TEXT_CHARS], total_chars=len(text))


def _parts(read, block):
    for side, document in (("source", read.source_ir), ("target", read.final_ir)):
        if document is None:
            continue
        current = next((item for item in document.blocks if item.id == block.id), None)
        if current is None:
            continue
        if current.text:
            unit = f"{block.id}.text"
            yield from _text_parts("text", side, "text", current.text, unit_id=unit if unit in read.source_units else None)
        for index, text in enumerate(current.list_items or []):
            unit = f"{block.id}.list_items.{index:04d}"
            yield from _text_parts("list_item", side, "list_items", text, index=index, unit_id=unit if unit in read.source_units else None)
        for field_name, kind in (("captions", "caption"), ("footnotes", "footnote")):
            for index, text in enumerate(getattr(current, field_name)):
                yield from _text_parts(kind, side, field_name, text, index=index)
        if current.latex:
            yield from _text_parts("latex", side, "latex", current.latex)
        if current.html:
            units = read.source_units if side == "source" else read.target_units
            table_units = [(target, text) for target, text in units.values() if target.block_id == block.id and target.field == "html"]
            if table_units:
                for target, text in table_units:
                    yield from _text_parts("table_text", side, "html", text, index=target.index, unit_id=target.item_id)
            else:
                text = BeautifulSoup(current.html, "html.parser").get_text(" ", strip=True)
                yield from _text_parts("table_text", side, "html", text)
    # raw HTML 只消费原始来源账本；目标 normalized HTML 从不冒充 source raw。
    document = read.source_ir or read.basis
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            if fragment.block_id != block.id and fragment.render_owner_block_id != block.id:
                continue
            raw = fragment.raw_html
            summary = html.escape(raw[:HTML_SUMMARY_CHARS])[:HTML_SUMMARY_CHARS] if raw is not None else None
            yield Part(kind="html_summary", side="source", field="raw_html", fragment_id=fragment.fragment_id,
                text=summary, total_chars=len(raw) if raw is not None else 0,
                truncated=raw is not None and (len(raw) > HTML_SUMMARY_CHARS or len(html.escape(raw[:HTML_SUMMARY_CHARS])) > HTML_SUMMARY_CHARS),
                html_state=fragment.html_state, sha256=hashlib.sha256(raw.encode()).hexdigest() if raw is not None else None)
    for term in read.terms:
        if read.source_units[term.unit_id][0].block_id == block.id:
            yield Part(kind="term", side="shared", field="glossary_trace", unit_id=term.unit_id, term=term)
    for batch_id, item_ids, evidence in read.batch_evidence:
        if any(read.source_units[item_id][0].block_id == block.id for item_id in item_ids):
            yield Part(kind="batch", side="shared", field="integrity", batch=evidence)
    for table in read.tables:
        if block.id in table.member_block_ids:
            yield Part(kind="table", side="shared", field="table", table=table)
    for reference in read.references:
        if reference.block_id == block.id:
            yield Part(kind="reference", side="shared", field="reference", reference=reference)


def _page(items, start, limit, *, reserve=65536):
    """按实际 JSON 字节控制页预算；超大结构不截断后冒充完整。"""
    if reserve > MAX_RESPONSE_BYTES:
        raise _ContentLimit()
    result, size, next_index, count = [], reserve, None, 0
    for index, item in enumerate(items):
        count = index + 1
        if index < start:
            continue
        length = len(item.model_dump_json().encode())
        if length + reserve > MAX_RESPONSE_BYTES:
            raise _ContentLimit()
        if len(result) >= limit or size + length > MAX_RESPONSE_BYTES:
            next_index = index
            break
        result.append(item)
        size += length
    if start and start >= count:
        raise ApiError(400, "invalid_request", "分页游标位置无效。", reason_code="invalid_review_cursor")
    return result, next_index


def list_blocks(service, job_id, *, user, limit=50, cursor=None, source_page_index=None,
                block_type=None, problem="all", severity="all"):
    with _storage():
        service._review_api_job(job_id, user)
    parsed = service._review_cursor(cursor, "review_blocks", job_id, limit)
    if (source_page_index is not None and (type(source_page_index) is not int or source_page_index < 0)
            or block_type not in {None, "heading", "paragraph", "table", "image", "list", "formula"}
            or problem not in {"all", "flagged"} or severity not in {"all", "blocker", "warning", "info"}):
        raise ApiError(422, "validation_error", "审核筛选条件无效。")
    filters = digest(dict(source_page_index=source_page_index, block_type=block_type, problem=problem, severity=severity)).removeprefix("sha256:")
    if parsed and parsed.filter_sha256 != filters:
        raise ApiError(400, "invalid_request", "分页筛选条件已变化。", reason_code="invalid_review_cursor")
    read = _load(service, job_id, user)
    if parsed and parsed.snapshot_id != read.snapshot.snapshot_id:
        raise _changed()
    rows = [_block(read, block) for block in sorted(read.basis.blocks, key=lambda item: (item.order, item.id))] if read.basis else []
    rows = [row for row in rows if (source_page_index is None or any(span.source_page_index == source_page_index for span in row.source_spans))
        and (block_type is None or row.block_type == block_type)
        and (problem == "all" or row.flags) and (severity == "all" or any(flag.severity == severity for flag in row.flags))]
    try:
        items, next_index = _page(iter(rows), parsed.next_index if parsed else 0, limit)
    except _ContentLimit:
        items, next_index, read.limited = [], None, True
    response = DocumentReviewBlocksResponse(job_id=job_id, source=project_source(read.job, read.result), content_snapshot=read.snapshot,
        availability="unavailable" if read.limited else "available" if read.basis else "not_ready",
        reason_code="review_content_limit_exceeded" if read.limited else None,
        total=len(rows), items=items, next_cursor=encode_cursor(ReviewBlocksCursor(job_id=job_id,
            snapshot_id=read.snapshot.snapshot_id, filter_sha256=filters, next_index=next_index)) if next_index is not None else None)
    read.finish()
    return response


def get_block(service, job_id, block_id, *, user, snapshot_id, limit=20, cursor=None):
    with _storage():
        service._review_api_job(job_id, user)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ApiError(422, "validation_error", "内容分页数量必须为 1 到 50 的整数。")
    parsed = service._review_cursor(cursor, "review_block_content", job_id, limit)
    if parsed and (parsed.block_id != block_id or parsed.snapshot_id != snapshot_id):
        raise ApiError(400, "invalid_request", "内容分页游标不匹配。", reason_code="invalid_review_cursor")
    if not isinstance(snapshot_id, str) or re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is None:
        raise ApiError(422, "validation_error", "内容快照标识无效。")
    read = _load(service, job_id, user)
    if snapshot_id != read.snapshot.snapshot_id:
        raise _changed()
    if read.limited:
        raise ApiError(409, "conflict", "审核内容超出固定阅读预算。", reason_code="review_content_limit_exceeded")
    block = next((block for block in read.basis.blocks if block.id == block_id), None) if read.basis else None
    if block is None:
        raise ApiError(404, "not_found", "当前文档中不存在该内容块。", reason_code="review_block_not_found")
    projected = _block(read, block)
    try:
        items, next_index = _page(_parts(read, block), parsed.next_index if parsed else 0, limit,
            reserve=len(projected.model_dump_json().encode()) + 16384)
    except _ContentLimit:
        raise ApiError(409, "conflict", "该内容块超出固定阅读预算。", reason_code="review_content_limit_exceeded") from None
    response = DocumentReviewBlockDetailResponse(job_id=job_id, source=project_source(read.job, read.result),
        content_snapshot=read.snapshot, block=projected, items=items, next_cursor=encode_cursor(ReviewBlockContentCursor(
            job_id=job_id, snapshot_id=snapshot_id, block_id=block_id, next_index=next_index)) if next_index is not None else None)
    read.finish()
    return response
