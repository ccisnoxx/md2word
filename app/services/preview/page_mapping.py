"""同一已认证主件的页导航派生合同；多页结果只表达低置信起点估计。"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.services.renderer.block_evidence import BlockRenderEvidence, SourceProjection
from app.services.renderer.render_plan import RenderPlan, Sha256

SCHEMA_VERSION = "pdf-ir-word-page-map/v1"
ALGORITHM_VERSION = "source-order-nearest/v1"
MAX_MAPPING_BYTES = 8 * 1024 * 1024
MAX_MAPPING_ENTRIES = 100000
NonNegative = Annotated[int, Field(ge=0)]
REASONS = frozenset({"legacy_evidence_missing", "anchor_missing", "source_unavailable", "no_target",
    "preview_unavailable", "unsupported_version", "invalid_mapping", "limit_exceeded", "unexpected_error",
    "estimated_start"})


class MappingContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MappingBinding(MappingContract):
    source_pdf_file_id: str | None = None
    document_ir_file_id: str | None = None
    input_ir_sha256: Sha256 | None = None
    plan_sha256: Sha256 | None = None
    source_generation: NonNegative
    result_file_id: str = Field(min_length=1)
    docx_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    attempt: Annotated[int, Field(ge=1)]
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    preview_pdf_file_id: str | None = None
    preview_pdf_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    page_count: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def complete_preview(self):
        values = (self.preview_pdf_file_id, self.preview_pdf_sha256, self.page_count)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("页映射的预览身份必须同时存在。")
        return self


class MappingLocation(MappingContract):
    kind: Literal["single_page", "estimated_start", "unavailable"]
    preview_page_index: NonNegative | None
    page_range: None = None
    confidence: Literal["high", "low", "none"]
    reason_code: Literal["single_page", "source_page_ratio", "source_page_rank_degenerate", "nearest_output",
                         "output_order_ratio", "no_target"]
    nearest_block_id: str | None = None

    @model_validator(mode="after")
    def shape(self):
        expected = {"single_page": "high", "estimated_start": "low", "unavailable": "none"}[self.kind]
        if (self.confidence != expected or (self.preview_page_index is None) != (self.kind == "unavailable")
                or (self.kind == "single_page" and (self.preview_page_index != 0 or self.reason_code != "single_page"))
                or (self.kind == "unavailable" and self.reason_code != "no_target")
                or (self.reason_code == "nearest_output") != (self.nearest_block_id is not None)):
            raise ValueError("页映射位置的证据等级不一致。")
        return self


class MappingFallback(MappingContract):
    page_index: NonNegative
    nearest_block_id: str
    method: Literal["source_page_nearest", "representative"]
    confidence: Literal["low"] = "low"


class MappingSource(MappingContract):
    provenance_status: Literal["verified_ir205", "legacy_layout", "unavailable"]
    source_spans: list[dict[str, Any]]
    logical_group_id: str | None
    fragment_ids: list[str]
    layout_page_index: NonNegative | None
    bbox: list[float | None] | None


class MappingEntry(MappingContract):
    block_id: str
    anchor_ref: str
    bookmark_name: str | None
    anchor_reason_code: Literal["anchor_missing"] | None
    disposition: Literal["rendered", "coalesced", "suppressed", "superseded", "not_emitted"]
    representative_block_id: str | None
    source: MappingSource
    location: MappingLocation
    fallback: MappingFallback | None

    @model_validator(mode="after")
    def anchor_shape(self):
        missing = self.location.kind != "unavailable" and self.bookmark_name is None
        if (self.anchor_reason_code == "anchor_missing") != missing:
            raise ValueError("页映射锚点证据不一致。")
        return self


class PageMapping(MappingContract):
    schema_version: Literal["pdf-ir-word-page-map/v1"] = SCHEMA_VERSION
    algorithm_version: Literal["source-order-nearest/v1"] = ALGORITHM_VERSION
    status: Literal["available", "degraded", "unavailable"]
    reason_code: str | None
    binding: MappingBinding
    entries: list[MappingEntry]
    counts: dict[str, NonNegative | None]
    mapping_sha256: Sha256

    @model_validator(mode="after")
    def semantics(self):
        if self.reason_code is not None and self.reason_code not in REASONS:
            raise ValueError("页映射原因码无效。")
        if set(self.counts) != {"total", "located", "high", "low", "anchor_available"}:
            raise ValueError("页映射计数字段无效。")
        ids = [entry.block_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("页映射块身份重复。")
        pages = self.binding.page_count
        for entry in self.entries:
            for page in (entry.location.preview_page_index, entry.fallback.page_index if entry.fallback else None):
                if page is not None and (pages is None or page >= pages):
                    raise ValueError("页映射页索引越界。")
            if entry.disposition not in {"rendered", "coalesced"} and entry.location.kind != "unavailable":
                raise ValueError("无输出块不能声明正文命中。")
            if entry.location.kind == "single_page" and pages != 1:
                raise ValueError("单页证明不能用于多页预览。")
            if entry.fallback is not None and entry.location.kind != "unavailable":
                raise ValueError("正文定位不能冒充导航回退。")
        if self.entries:
            if self.counts != _counts([entry.model_dump(mode="json") for entry in self.entries]):
                raise ValueError("页映射计数不一致。")
        elif any(self.counts.get(key) != 0 for key in ("located", "high", "low", "anchor_available")):
            raise ValueError("空页映射不能声明覆盖。")
        if self.status != "unavailable" and (not self.counts.get("located")
                or self.binding.input_ir_sha256 is None or self.binding.plan_sha256 is None or pages is None
                or self.binding.source_pdf_file_id is None or self.binding.document_ir_file_id is None):
            raise ValueError("可用页映射缺少完整证据。")
        if self.status == "unavailable" and (self.reason_code is None or self.counts["located"] != 0
                or self.entries and (self.reason_code != "no_target" or any(entry.fallback is not None for entry in self.entries))):
            raise ValueError("不可用页映射不能声明定位或回退成功。")
        if self.status == "degraded" and self.reason_code not in {"anchor_missing", "estimated_start"}:
            raise ValueError("降级页映射必须说明估计或缺锚原因。")
        if self.status == "available" and (self.reason_code is not None or any(
                entry.location.kind != "single_page" or entry.bookmark_name is None
                for entry in self.entries if entry.location.kind != "unavailable")):
            raise ValueError("页映射不能提升估计或缺锚结果。")
        return self


class _MappingLimit(ValueError):
    """局部预算耗尽，不能输出已截断的完整映射。"""


def _canonical_size_hash(value: Any, *, budget: int = MAX_MAPPING_BYTES) -> tuple[int, str]:
    """逐编码片段累计；不先构造可能无界的完整 JSON 字符串。"""
    total, digest = 0, hashlib.sha256()
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode("utf-8")
        total += len(encoded)
        if total > budget:
            raise _MappingLimit("页映射超出固定容量预算。")
        digest.update(encoded)
    return total, digest.hexdigest()


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    # 为自身 hash 字段预留固定空间，整个最终对象仍须满足 8 MiB。
    _, digest = _canonical_size_hash(body, budget=MAX_MAPPING_BYTES - 84)
    return {**body, "mapping_sha256": digest}


def _counts(entries):
    return {"total": len(entries), "located": sum(e["location"]["preview_page_index"] is not None for e in entries),
        "high": sum(e["location"]["confidence"] == "high" for e in entries),
        "low": sum(e["location"]["confidence"] == "low" for e in entries),
        "anchor_available": sum(e["bookmark_name"] is not None for e in entries)}


def unavailable_mapping(binding: MappingBinding, reason: str, *, total: int | None = None):
    """只保留可证明身份；缺 trace 时块数未知，不从 DOCX 反推。"""
    return _seal({"schema_version": SCHEMA_VERSION, "algorithm_version": ALGORITHM_VERSION,
        "status": "unavailable", "reason_code": reason, "binding": binding.model_dump(mode="json"),
        "entries": [], "counts": {"total": total, "located": 0, "high": 0, "low": 0, "anchor_available": 0}})


def _ratio(rank: int, count: int, pages: int) -> int:
    if count <= 1:
        return 0
    quotient, remainder = divmod(rank * (pages - 1), count - 1)
    return quotient + (2 * remainder > count - 1)


def _source_page(source: SourceProjection) -> int | None:
    if source.status == "verified_ir205":
        pages = [span["page_index"] for span in source.source_spans
                 if type(span.get("page_index")) is int and span["page_index"] >= 0]
        if pages:
            return min(pages)
    return source.page_index if source.status in {"verified_ir205", "legacy_layout"} else None


def _location(page=None, reason="no_target", nearest=None):
    return {"kind": "unavailable" if page is None else "single_page" if reason == "single_page" else "estimated_start",
        "preview_page_index": page, "page_range": None,
        "confidence": "none" if page is None else "high" if reason == "single_page" else "low",
        "reason_code": reason, "nearest_block_id": nearest}


def build_page_mapping(*, binding: MappingBinding, plan: RenderPlan | None,
                       block_evidence: BlockRenderEvidence | None, block_anchor_evidence=None):
    """只接收原 owner 已认证的计划/trace/可选证明，不搜索或猜测书签。"""
    if binding.page_count is None:
        return unavailable_mapping(binding, "preview_unavailable")
    if plan is None or block_evidence is None or binding.source_pdf_file_id is None or binding.document_ir_file_id is None:
        return unavailable_mapping(binding, "legacy_evidence_missing")
    total = len(block_evidence.block_render_map)
    if total > MAX_MAPPING_ENTRIES:
        return unavailable_mapping(binding, "limit_exceeded", total=total)
    if ((plan.input_ir_sha256, plan.plan_sha256, block_evidence.docx_sha256)
            != (binding.input_ir_sha256, binding.plan_sha256, binding.docx_sha256.removeprefix("sha256:"))
            or (block_evidence.input_ir_sha256, block_evidence.plan_sha256)
            != (plan.input_ir_sha256, plan.plan_sha256) or not block_evidence.complete
            or any(record.provenance.page_index is not None and record.provenance.page_index < 0
                   for record in block_evidence.block_render_map)):
        return unavailable_mapping(binding, "invalid_mapping", total=total)
    try:
        return _build(binding, plan, block_evidence, block_anchor_evidence)
    except _MappingLimit:
        return unavailable_mapping(binding, "limit_exceeded", total=total)


def _build(binding, plan, trace, proof):
    records = {record.block_id: record for record in trace.block_render_map}
    operation_order = {block_id: order for order, operation in reversed(list(enumerate(plan.operations)))
                       for block_id in operation.block_ids}
    positions = {record.block_id: min(tuple(target.child_path) for target in record.targets
                 if target.part == "word/document.xml" and target.role not in {"header", "footer", "toc_representative"})
                 for record in records.values() if record.disposition == "rendered" and any(
                     target.part == "word/document.xml" and target.role not in {"header", "footer", "toc_representative"}
                     for target in record.targets)}
    owners = sorted(positions, key=lambda key: (positions[key], operation_order.get(key, len(operation_order))))
    order = {block_id: index for index, block_id in enumerate(owners)}
    representatives = {}
    for record in records.values():
        owner, visited = record.block_id, set()
        while records[owner].disposition == "coalesced":
            if owner in visited or records[owner].representative_block_id not in records:
                return unavailable_mapping(binding, "invalid_mapping", total=len(records))
            visited.add(owner)
            owner = records[owner].representative_block_id
        representatives[record.block_id] = owner
    source_pages = sorted({page for section in plan.sections for page in section.source_page_indices if page >= 0}) if plan.layout_mode != "legacy_v1_fallback" else []
    ranks = {page: index for index, page in enumerate(source_pages)}
    own_ranks = {key: ranks.get(_source_page(record.provenance)) for key, record in records.items()}
    locations, pages = {}, binding.page_count
    direct = [key for key in owners if own_ranks[key] is not None]
    for key in owners:
        if pages == 1:
            locations[key] = _location(0, "single_page")
        elif len(source_pages) <= 1:
            locations[key] = _location(_ratio(order[key], len(owners), pages), "source_page_rank_degenerate")
        elif own_ranks[key] is not None:
            locations[key] = _location(_ratio(own_ranks[key], len(source_pages), pages), "source_page_ratio")
        elif direct:
            nearest = min(direct, key=lambda candidate: (abs(order[candidate] - order[key]), order[candidate]))
            locations[key] = _location(_ratio(own_ranks[nearest], len(source_pages), pages), "nearest_output", nearest)
        else:
            locations[key] = _location(_ratio(order[key], len(owners), pages), "output_order_ratio")
    anchors = {entry.block_id: entry.bookmark_name for entry in proof.entries} if proof is not None else {}
    # 非正文保留在实际 operation 顺序，正文及归并块使用最终 document.xml owner 顺序。
    sorted_records = sorted(records.values(), key=lambda record: (
        (0, order[representatives[record.block_id]]) if representatives[record.block_id] in order
        else (1, operation_order.get(record.block_id, len(operation_order)))))
    entries, used = [], 0
    for record in sorted_records:
        representative = representatives[record.block_id]
        actual = record.block_id in positions or record.disposition == "coalesced" and representative in positions
        location = locations[representative] if actual else _location()
        bookmark = anchors.get(representative) if actual else anchors.get(record.block_id)
        fallback = None
        if not actual and owners:
            nearest, method = None, "source_page_nearest"
            if own_ranks[record.block_id] is not None and direct:
                nearest = min(direct, key=lambda key: (abs(own_ranks[key] - own_ranks[record.block_id]), order[key]))
            elif record.representative_block_id in locations:
                nearest, method = record.representative_block_id, "representative"
            if nearest is not None:
                fallback = {"page_index": locations[nearest]["preview_page_index"], "nearest_block_id": nearest,
                            "method": method, "confidence": "low"}
        source = record.provenance
        entry = {"block_id": record.block_id, "anchor_ref": record.anchor_ref, "bookmark_name": bookmark,
            "anchor_reason_code": "anchor_missing" if actual and bookmark is None else None,
            "disposition": record.disposition, "representative_block_id": record.representative_block_id,
            "source": {"provenance_status": source.status, "source_spans": source.source_spans,
                       "logical_group_id": source.logical_group_id, "fragment_ids": source.fragment_ids,
                       "layout_page_index": source.page_index, "bbox": source.bbox},
            "location": location, "fallback": fallback}
        size, _ = _canonical_size_hash(entry, budget=MAX_MAPPING_BYTES - used)
        used += size + 1
        entries.append(entry)
    counts = _counts(entries)
    status = "unavailable" if not owners else "degraded" if pages > 1 or any(
        e["anchor_reason_code"] for e in entries) else "available"
    reason = "no_target" if not owners else "anchor_missing" if any(e["anchor_reason_code"] for e in entries) else "estimated_start" if pages > 1 else None
    return _seal({"schema_version": SCHEMA_VERSION, "algorithm_version": ALGORITHM_VERSION,
        "status": status, "reason_code": reason, "binding": binding.model_dump(mode="json"),
        "entries": entries, "counts": counts})


def read_page_mapping(value: Any, *, binding: MappingBinding) -> dict[str, Any]:
    """原 manifest/权限/hash 已通过后使用；只降级内层 mapping，不写回历史字节。"""
    if value is None:
        return unavailable_mapping(binding, "legacy_evidence_missing")
    if isinstance(value, dict) and (value.get("schema_version") != SCHEMA_VERSION
            or value.get("algorithm_version") != ALGORITHM_VERSION):
        return unavailable_mapping(binding, "unsupported_version")
    try:
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            return unavailable_mapping(binding, "invalid_mapping")
        if len(value["entries"]) > MAX_MAPPING_ENTRIES:
            raise _MappingLimit()
        _canonical_size_hash(value)
        parsed = PageMapping.model_validate(value)
        unhashed = {key: item for key, item in value.items() if key != "mapping_sha256"}
        _, digest = _canonical_size_hash(unhashed)
        if parsed.binding != binding or parsed.mapping_sha256 != digest:
            return unavailable_mapping(binding, "invalid_mapping")
        return parsed.model_dump(mode="json")
    except _MappingLimit:
        return unavailable_mapping(binding, "limit_exceeded")
    except (ValidationError, ValueError, TypeError, RecursionError):
        return unavailable_mapping(binding, "invalid_mapping")


def mapping_summary(mapping):
    """日志只允许固定状态、版本、原因和数字计数。"""
    return {**{key: mapping[key] for key in ("schema_version", "algorithm_version", "status", "reason_code")},
            "counts": {key: mapping["counts"][key] for key in ("total", "located", "high", "low", "anchor_available")}}
