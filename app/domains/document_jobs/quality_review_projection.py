"""授权观察的有限公开投影与游标；不访问仓储、不读取对象、不改变任务状态。"""
from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
import json
import re
from typing import Annotated, Any, Literal, get_args

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from app.domains.document_jobs.base_quality import Reason as BaseReason, project_base_quality
from app.domains.document_jobs.review import receipt_identity
from app.domains.document_jobs.schemas import (
    DocumentQualityBlockCandidateResponse, DocumentQualityCellShapeResponse,
    DocumentQualityCountsResponse, DocumentQualityCoverageResponse, DocumentQualityFragmentResponse,
    DocumentQualityGridResponse, DocumentQualityNativeTableResponse, DocumentQualityPageFlagResponse,
    DocumentQualityPageItemResponse, DocumentQualityPageReportResponse, DocumentQualityPageRuleResponse,
    DocumentQualityPlaceholderResponse, DocumentQualityProducerResponse, DocumentQualityProducersResponse,
    DocumentQualityRowShapeResponse, DocumentQualitySourceResponse, DocumentQualitySourceSpanResponse,
    DocumentQualitySummaryResponse, DocumentQualityTableFlagResponse, DocumentQualityTableItemResponse,
    DocumentQualityTableReferenceResponse, DocumentQualityTableReportResponse, DocumentPreviewPageResponse,
    DocumentPreviewRunResponse, DocumentReviewBindingResponse, DocumentReviewHistoryItemResponse,
    DocumentReviewQualityResponse, DocumentReviewResponse, QualityCount, QualityHash, QualityId,
    QualityMetric, QualityReviewModel,
)
from app.services.preview.models import PreviewErrorCode
from app.services.preview.page_quality import QualityFlag, Reason, RULES
from app.services.renderer.evidence import controlled_quality_flags
from app.services.tables.evidence import ISSUE_CODES


MAX_CURSOR_LENGTH = 2048
_VERSION = re.compile(r"[a-z][a-z0-9-]*/v[0-9]+\Z")
_PAGE_REASONS = frozenset(get_args(Reason))
_PREVIEW_ERRORS = frozenset(get_args(PreviewErrorCode))
_REASONS = _PAGE_REASONS | _PREVIEW_ERRORS | frozenset(get_args(BaseReason)) | {
    "source_groups_unavailable", "rendering_evidence_unavailable", "reference_evidence_unavailable",
    "preview_artifact_unavailable", "legacy_evidence_missing", "not_ready", "disabled",
}
_PAGE_FLAGS = frozenset(get_args(QualityFlag.model_fields["code"].annotation))
_METRICS_BY_RULE = {
    "clipping": {"native_outside_area_pt2", "foreground_union_area_pt2", "outside_area_ratio", "outside_object_count", "max_outside_distance_pt", "edge_ink_ratio"},
    "overflow": {"outside_body_area_ratio", "clearance_pt", "excluded_object_count"},
    "blank": {"ink_area_ratio", "foreground_object_count", "char_count"},
    "overlap": {"positive_pair_count", "max_intersection_min_area_ratio"},
    "density": {"body_ink_ratio", "native_foreground_body_area_ratio", "char_density", "group_median", "median_absolute_deviation"},
}


def _field(value: Any, name: str, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _fields(value: Any, names: Sequence[str]) -> dict:
    return {name: _field(value, name) for name in names}


def _counts(value: Any) -> DocumentQualityCountsResponse:
    return DocumentQualityCountsResponse(**{name: item for name in DocumentQualityCountsResponse.model_fields
        if type(item := _field(value, name)) is int and item >= 0})


def _version(value):
    return value if isinstance(value, str) and len(value) <= 100 and _VERSION.fullmatch(value) else None


def _reason(value):
    return value if isinstance(value, str) and value in _REASONS else None


def _flags(values, *, table=False):
    safe, unknown = [], 0
    for value in values if isinstance(values, (tuple, list)) else ():
        accepted = isinstance(value, str) and (value in ISSUE_CODES if table else bool(controlled_quality_flags([value])))
        if accepted:
            safe.extend([value] if table else controlled_quality_flags([value]))
        else:
            unknown += 1
    return list(dict.fromkeys(safe)), unknown


def project_source(job, file) -> DocumentQualitySourceResponse:
    return DocumentQualitySourceResponse(generation=job.retry_count, ir_file_id=job.document_ir_file_id,
        result_file_id=job.result_file_id, result_sha256=file.checksum_sha256 if file else None,
        file_review_source_revision=file.review_source_revision if file else None, receipt_sha256=receipt_identity(job))


def project_quality_summary(summary: Mapping, *, generation: int | None = None) -> tuple[DocumentQualitySummaryResponse, DocumentQualityProducersResponse]:
    flags, unknown_flags = {}, 0
    for name in ("quality_flags", "layout_quality_flags", "blocking_quality_flags"):
        flags[name], count = _flags(summary.get(name))
        unknown_flags += count
    rows = []
    known = {"formula", "table_evidence", "table_placeholder"}
    unknown_producers = len(set(summary) - known - set(flags) - {"checks_v1", "unknown_flag_count"})
    checks = summary.get("checks_v1", {})
    producer_values = [(name, summary[name]) for name in ("formula", "table_evidence", "table_placeholder") if name in summary]
    if isinstance(checks, Mapping):
        for name, value in checks.items():
            if name in {"word_preview", "word_page_quality", "document_base", "__unattributed__"}:
                producer_values.append(("unattributed" if name == "__unattributed__" else name,
                    project_base_quality(value, generation=generation) if name == "document_base" else value))
            else:
                unknown_producers += 1
    for producer, value in producer_values:
        if not isinstance(value, Mapping):
            unknown_producers += 1
            continue
        nested = value.get("summary")
        details = nested if isinstance(nested, Mapping) else value
        table = producer in {"table_evidence", "table_placeholder"}
        safe_flags, unknown = _flags(details.get("issue_codes") if table else details.get("warning_codes"), table=table)
        if producer == "document_base":
            safe_flags = list(details.get("warning_codes", []))
            unknown = details.get("counts", {}).get("unknown_flag_count", 0)
        status = value.get("quality_status", value.get("status"))
        coverage = details.get("coverage")
        available = value.get("availability")
        report_hash = details.get("report_sha256")
        rows.append(DocumentQualityProducerResponse(producer=producer,
            schema_version=_version(details.get("schema_version", details.get("version"))),
            quality_status=status if status in ("pending", "passed", "warning", "blocked") else None,
            evaluation_state=value.get("evaluation_state") if value.get("evaluation_state") in ("complete", "incomplete") else None,
            availability=available if available in ("available", "legacy_unavailable", "not_ready", "disabled", "unavailable") else None,
            coverage=coverage if coverage in ("complete", "unavailable") else None,
            report_sha256=report_hash if isinstance(report_hash, str) and re.fullmatch(r"[0-9a-f]{64}", report_hash) else None,
            reason_code=_reason(details.get("reason_code", details.get("reason"))), counts=_counts(details.get("counts", details)),
            flags=safe_flags, unknown_flag_count=unknown))
    return DocumentQualitySummaryResponse(**flags, unknown_flag_count=unknown_flags), DocumentQualityProducersResponse(
        items=rows, unknown_producer_count=unknown_producers)


def _source_span(value, *, table=False):
    box = _field(value, "bbox")
    return DocumentQualitySourceSpanResponse(source_page_index=_field(value, "page_index"),
        bbox=tuple(box) if box is not None else None,
        **(_fields(value, ("fragment_id", "html_state", "row_start", "row_count", "columns")) if table else {}))


def project_table_item(table) -> DocumentQualityTableItemResponse:
    validation, grid = _field(table, "validation"), _field(table, "source_grid")
    cells = _field(validation, "cells")
    outputs = []
    for output in _field(table, "outputs"):
        actual = _field(output, "actual")
        rows = [DocumentQualityRowShapeResponse(header=_field(row, "header"), cant_split=_field(row, "cant_split"),
            cells=[DocumentQualityCellShapeResponse(**_fields(cell, ("grid_span", "vertical_merge")))
                   for cell in _field(row, "cells")]) for row in _field(actual, "rows")]
        outputs.append(DocumentQualityNativeTableResponse(**_fields(output, ("output_table_key", "anchor_block_id")),
            table_index=_field(actual, "table_index"), grid_columns=_field(actual, "grid_columns"), rows=rows,
            fragments=[DocumentQualityFragmentResponse(**_fields(fragment, ("fragment_id", "block_id", "render_owner_block_id",
                "source_rows", "retained_source_rows", "output_rows", "removed_header_rows", "shared_header_rows", "status")))
                for fragment in _field(output, "fragments")]))
    flags, unknown = [], 0
    for flag in _field(table, "flags"):
        if (_field(flag, "producer") in ("table_validator", "table_rendering", "table_reference", "table_placeholder")
                and isinstance(_field(flag, "code"), str) and _field(flag, "code") in ISSUE_CODES):
            flags.append(DocumentQualityTableFlagResponse(**_fields(flag, ("producer", "code", "severity", "fragment_id"))))
        else:
            unknown += 1
    return DocumentQualityTableItemResponse(**_fields(table, ("table_id", "logical_group_id", "member_block_ids", "anchor_block_id", "render_state", "status")),
        source_spans=[_source_span(fragment, table=True) for fragment in _field(validation, "fragments")],
        source_grid=DocumentQualityGridResponse(**_fields(grid, ("rows", "columns", "header_rows")),
            rowspan_count=sum(_field(cell, "rowspan") > 1 for cell in cells), colspan_count=sum(_field(cell, "colspan") > 1 for cell in cells)),
        references=[DocumentQualityTableReferenceResponse(**_fields(reference, ("fragment_id", "source_status", "asset_id", "file_id", "mime_type", "registered")))
                    for reference in _field(table, "references")], outputs=outputs,
        placeholders=[DocumentQualityPlaceholderResponse(**_fields(item, ("placeholder_id", "fragment_id", "owner_block_id", "asset_ref", "source_kind", "issue_code")))
                      for item in _field(table, "placeholders")], flags=flags, unknown_flag_count=unknown)


def project_table_report(view) -> DocumentQualityTableReportResponse:
    summary = _field(view, "summary")
    return DocumentQualityTableReportResponse(schema_version=_field(summary, "schema_version"),
        report_file_id=_field(view, "report_file_id"), report_sha256=_field(view, "report_sha256"),
        coverage=_field(summary, "coverage"), status=_field(summary, "status"), counts=_counts(summary))


def _manual_checks(values):
    return [value for value in values if isinstance(value, str) and (value in _PAGE_REASONS or any(
        value == rule + ":" + reason for rule in RULES for reason in _PAGE_REASONS))]


def project_page_item(page) -> DocumentQualityPageItemResponse:
    rules = {}
    for name in RULES:
        rule = _field(_field(page, "rules"), name)
        metrics, units = _field(rule, "metrics"), _field(rule, "units")
        allowed = _METRICS_BY_RULE[name]
        rules[name] = DocumentQualityPageRuleResponse(rule_version=_field(rule, "rule_version"), checked=_field(rule, "checked"),
            reason_code=_reason(_field(rule, "reason_code")), metrics={key: value for key, value in metrics.items() if key in allowed},
            units={key: value for key, value in units.items() if key in allowed})
    flags, unknown = [], 0
    for flag in _field(page, "flags"):
        if not isinstance(_field(flag, "code"), str) or _field(flag, "code") not in _PAGE_FLAGS:
            unknown += 1
            continue
        flags.append(DocumentQualityPageFlagResponse(**_fields(flag, ("code", "severity", "rule_version", "preview_page_index", "evidence_kind", "manual_check_required")),
            metric_refs=[value for value in _field(flag, "metric_refs") if any(value == rule + "." + metric
                for rule in RULES for metric in _METRICS_BY_RULE[rule])]))
    candidates = []
    for candidate in _field(page, "block_candidates"):
        candidates.append(DocumentQualityBlockCandidateResponse(**_fields(candidate, ("block_id", "association", "confidence", "source_page_indices")),
            source_spans=[_source_span(span) for span in _field(candidate, "source_spans")]))
    return DocumentQualityPageItemResponse(preview_page_index=_field(page, "preview_page_index"), rules=rules,
        flags=flags, unknown_flag_count=unknown, manual_checks=_manual_checks(_field(page, "manual_checks")), block_candidates=candidates)


def project_page_report(run, *, revision: int, manifest_file_id: str) -> DocumentQualityPageReportResponse:
    binding = _field(run, "binding")
    return DocumentQualityPageReportResponse(**_fields(run, ("schema_version", "analyzer_version", "id", "run_sha256", "evaluation_state", "quality_status")),
        generation=_field(binding, "source_generation"), preview_run_id=_field(binding, "preview_run_id"),
        revision=revision, attempt=_field(binding, "attempt"), manifest_file_id=manifest_file_id,
        **_fields(binding, ("profile_id", "profile_sha256", "page_count")), reason_code=_reason(_field(run, "reason_code")),
        manual_checks=_manual_checks(_field(run, "manual_checks")), counts=_counts(_field(run, "counts")),
        coverage={name: DocumentQualityCoverageResponse(**_fields(_field(_field(run, "coverage"), name), ("checked", "not_checked"))) for name in RULES})


def project_preview_page(descriptor: Mapping) -> DocumentPreviewPageResponse:
    return DocumentPreviewPageResponse(**_fields(descriptor, ("file_id", "page_index", "width", "height")))


def project_preview_run(state, run) -> DocumentPreviewRunResponse:
    return DocumentPreviewRunResponse(**_fields(run, ("run_id", "status", "started_at", "completed_at")),
        revision=state.revision, attempt=run.attempt_count, profile_id=state.profile_id, profile_sha256=state.profile_sha256,
        error_code=run.error_code if run.error_code in _PREVIEW_ERRORS else None)


def _review_quality(value):
    stored = _field(value, "producers")
    names = {"formula", "table_evidence", "table_placeholder"}
    checks = {name: item for name, item in stored.items() if name in {"word_preview", "word_page_quality", "__unattributed__"}}
    summary, producers = project_quality_summary({**_field(value, "flags"),
        **{name: item for name, item in stored.items() if name in names}, "checks_v1": checks})
    producers.unknown_producer_count += len(set(stored) - names - set(checks))
    summary.unknown_flag_count += _field(value, "unknown_flag_count")
    return DocumentReviewQualityResponse(quality_status=_field(value, "quality_status"), summary_sha256=_field(value, "summary_sha256"),
                                        summary=summary, producers=producers)


def _review_binding(value):
    return DocumentReviewBindingResponse(**_fields(value, ("generation", "result_file_id", "binding_state", "result_sha256", "file_review_source_revision", "receipt_sha256")))


def project_review(record, *, effective_status, validity_reason) -> DocumentReviewResponse:
    return DocumentReviewResponse(status=effective_status, current_record_id=_field(record, "id"), sequence=_field(record, "sequence"),
        **_fields(record, ("issue_type", "note", "reviewed_by", "reviewed_at")), validity_reason=validity_reason,
        binding=_review_binding(record.binding) if record else None, quality=_review_quality(record.quality) if record else None)


def project_review_history_item(record) -> DocumentReviewHistoryItemResponse:
    return DocumentReviewHistoryItemResponse(**_fields(record, ("id", "sequence", "issue_type", "note", "reviewed_by", "reviewed_at", "origin", "legacy_observed_status")),
        record_status=record.status, binding=_review_binding(record.binding), quality=_review_quality(record.quality))


class InvalidReviewCursor(ValueError):
    """只由有界游标解析抛出，服务按类型映射400，不沿用任意输入文本。"""
    def __init__(self):
        super().__init__("复核分页游标无效。")


class _Cursor(QualityReviewModel):
    version: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    job_id: QualityId


class TableCursor(_Cursor):
    kind: Literal["tables"] = "tables"
    generation: QualityCount
    ir_file_id: QualityId
    result_file_id: QualityId
    report_sha256: QualityHash
    next_index: QualityCount


class PageCursor(_Cursor):
    kind: Literal["pages"] = "pages"
    generation: QualityCount
    result_file_id: QualityId
    run_id: QualityId
    revision: QualityCount
    attempt: Annotated[int, Field(strict=True, ge=1)]
    manifest_file_id: QualityId
    run_sha256: QualityHash
    next_index: QualityCount


class PreviewCursor(_Cursor):
    kind: Literal["preview"] = "preview"
    generation: QualityCount
    result_file_id: QualityId
    run_id: QualityId
    revision: QualityCount
    attempt: Annotated[int, Field(strict=True, ge=1)]
    manifest_file_id: QualityId
    next_index: QualityCount


class HistoryCursor(_Cursor):
    kind: Literal["history"] = "history"
    after_sequence: QualityCount
    through_sequence: QualityCount

    @model_validator(mode="after")
    def _window(self):
        if self.after_sequence > self.through_sequence:
            raise ValueError("历史游标窗口无效。")
        return self


class ReviewBlocksCursor(_Cursor):
    kind: Literal["review_blocks"] = "review_blocks"
    snapshot_id: QualityHash
    filter_sha256: QualityHash
    next_index: Annotated[int, Field(strict=True, gt=0)]


class ReviewBlockContentCursor(_Cursor):
    kind: Literal["review_block_content"] = "review_block_content"
    snapshot_id: QualityHash
    block_id: QualityId
    next_index: Annotated[int, Field(strict=True, gt=0)]


Cursor = Annotated[TableCursor | PageCursor | PreviewCursor | HistoryCursor | ReviewBlocksCursor | ReviewBlockContentCursor, Field(discriminator="kind")]
_CURSOR = TypeAdapter(Cursor)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InvalidReviewCursor()
        value[key] = item
    return value


def _reject_constant(_value):
    raise InvalidReviewCursor()


def decode_cursor(value: str, kind: str, job_id: str):
    try:
        if not isinstance(value, str) or not 0 < len(value) <= MAX_CURSOR_LENGTH or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise InvalidReviewCursor()
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if not isinstance(data, dict) or "version" not in data:
            raise InvalidReviewCursor()
        cursor = _CURSOR.validate_python(data, strict=True)
        if cursor.kind != kind or cursor.job_id != job_id:
            raise InvalidReviewCursor()
        return cursor
    except (ValueError, TypeError, ValidationError, UnicodeError, RecursionError):
        raise InvalidReviewCursor() from None


def encode_cursor(cursor: Cursor) -> str:
    data = json.dumps(cursor.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    value = base64.urlsafe_b64encode(data).decode().rstrip("=")
    if len(value) > MAX_CURSOR_LENGTH:
        raise InvalidReviewCursor()
    return value


def paginate_history(records: Sequence, *, after_sequence: int, through_sequence: int, limit: int):
    """输入是 adapter 的 limit+1 窗口；追加记录不移动首屏高水位。"""
    sequences = [record.sequence for record in records]
    if sequences != sorted(set(sequences)) or any(sequence <= after_sequence for sequence in sequences):
        raise ValueError("复核历史读取顺序无效。")
    window = [record for record in records if record.sequence <= through_sequence]
    items = window[:limit]
    return items, items[-1].sequence if len(window) > limit else None
