"""列表与注释来源账本的写入、认证和翻译位置投影。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.conversion.docx_rules.formula import canonical_sha256, sha256_text

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR, DocumentIRBlock


LIST_ITEM_LEDGER_V1 = "list-item-ledger/v1"
LIST_ITEM_LEDGER_V2 = "list-item-ledger/v2"
ANNOTATION_LEDGER_VERSION = "annotation-ledger/v1"
LIST_ITEM_COUNT_MISMATCH = "source_ir_integrity:list_item_count_mismatch"
LIST_ITEM_LEDGER_MISMATCH = "source_ir_integrity:list_item_ledger_mismatch"
ANNOTATION_LEDGER_MISMATCH = "source_ir_integrity:annotation_ledger_mismatch"
LEDGER_RECOVERED = "source_ir_integrity:ledger_recovered"

AnnotationField = Literal["captions", "footnotes"]
LedgerPosition = tuple[str, str, int]
_ANNOTATION_FIELDS: tuple[AnnotationField, ...] = ("captions", "footnotes")
_SHA256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
_Index = Annotated[int, Field(ge=0)]
_NonemptyString = Annotated[str, Field(min_length=1)]
_LIST_TARGET_KEYS = {"target_sha256", "target_sha256s"}
_LIST_ITEM_KEYS = {"source_index", "source_sha256", "empty"}
_LIST_SINGLE_KEYS = {"output_index", "normalized_sha256"}
_LIST_EXPANDED_KEYS = {"output_start", "output_end", "normalized_sha256s"}


class _LedgerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class _ListItem(_LedgerPayload):
    source_index: _Index
    source_sha256: _SHA256
    empty: bool
    output_index: _Index | None = None
    normalized_sha256: _SHA256 | None = None
    output_start: _Index | None = None
    output_end: _Index | None = None
    normalized_sha256s: list[_SHA256] | None = None
    target_sha256: _SHA256 | None = None
    target_sha256s: list[_SHA256] | None = None


class _ListLedger(_LedgerPayload):
    version: Literal["list-item-ledger/v2"]
    selected_field: _NonemptyString
    mode: Literal["v2_items", "legacy_items", "selected_text", "content"]
    source_item_count: _Index
    empty_item_count: _Index
    item_count: _Index
    items: list[_ListItem]
    sequence_sha256: _SHA256


class _AnnotationItem(_LedgerPayload):
    block_id: _NonemptyString
    field: AnnotationField
    source_index: _Index
    source_sha256: _SHA256
    target_index: _Index
    target_sha256: _SHA256


class _AnnotationLedger(_LedgerPayload):
    version: Literal["annotation-ledger/v1"]
    items: Annotated[list[_AnnotationItem], Field(min_length=1)]


def _text_hash(value: str) -> str:
    return "sha256:" + sha256_text(value)


def _list_sequence_hash(ledger: Mapping[str, Any]) -> str:
    # 回填只增加目标摘要，源字段与输出区间仍绑定同一序列。
    source = {key: value for key, value in ledger.items() if key not in {"items", "sequence_sha256"}}
    source["items"] = [
        {key: value for key, value in item.items() if key not in _LIST_TARGET_KEYS}
        for item in ledger["items"]
    ]
    return "sha256:" + canonical_sha256(source)


def build_list_item_ledger(
    selected_field: str, mode: str, source_items: Sequence[tuple[Any, Sequence[str]]],
) -> dict[str, Any]:
    """从转换器冻结的源项及输出投影写入账本，原始正文仅用于计算摘要。"""
    items: list[dict[str, Any]] = []
    cursor = 0
    for source_index, (source_value, outputs) in enumerate(source_items):
        item = {
            "source_index": source_index,
            "source_sha256": "sha256:" + canonical_sha256(source_value),
            "empty": not outputs,
        }
        if len(outputs) > 1:
            item.update(output_start=cursor, output_end=cursor + len(outputs),
                        normalized_sha256s=[_text_hash(value) for value in outputs])
        else:
            item.update(output_index=cursor if outputs else None,
                        normalized_sha256=_text_hash(outputs[0]) if outputs else None)
        cursor += len(outputs)
        items.append(item)
    ledger = {
        "version": LIST_ITEM_LEDGER_V2, "selected_field": selected_field, "mode": mode,
        "source_item_count": len(items), "empty_item_count": sum(item["empty"] for item in items),
        "item_count": cursor, "items": items,
    }
    return {**ledger, "sequence_sha256": _list_sequence_hash(ledger)}


def build_annotation_ledger(sources: Iterable[tuple[str, AnnotationField, int, str]]) -> dict[str, Any]:
    """保留独立的源位置，按目标块内各字段的顺序建立映射。"""
    indices: Counter[AnnotationField] = Counter()
    items = []
    for source_block_id, field, source_index, source_text in sources:
        source_sha256 = _text_hash(source_text)
        items.append({
            "block_id": source_block_id, "field": field, "source_index": source_index,
            "source_sha256": source_sha256, "target_index": indices[field], "target_sha256": source_sha256,
        })
        indices[field] += 1
    return {"version": ANNOTATION_LEDGER_VERSION, "items": items}


def _list_ledger_failure(block: DocumentIRBlock, raw: Any, *, translated: bool) -> str | None:
    try:
        ledger = _ListLedger.model_validate(raw)
    except ValidationError:
        return LIST_ITEM_LEDGER_MISMATCH
    texts = block.list_items or []
    if len(texts) != ledger.item_count:
        return LIST_ITEM_COUNT_MISMATCH
    if (ledger.source_item_count != len(ledger.items)
            or ledger.empty_item_count != sum(item.empty for item in ledger.items)
            or ledger.sequence_sha256 != _list_sequence_hash(raw)):
        return LIST_ITEM_LEDGER_MISMATCH

    cursor = 0
    for source_index, item in enumerate(ledger.items):
        if item.source_index != source_index:
            return LIST_ITEM_LEDGER_MISMATCH
        keys = item.model_fields_set - _LIST_ITEM_KEYS
        if item.empty:
            if keys != _LIST_SINGLE_KEYS or item.output_index is not None or item.normalized_sha256 is not None:
                return LIST_ITEM_LEDGER_MISMATCH
            continue
        if item.output_index is not None:
            expected_keys = _LIST_SINGLE_KEYS | ({"target_sha256"} if translated else set())
            if keys != expected_keys or item.output_index != cursor or item.normalized_sha256 is None:
                return LIST_ITEM_LEDGER_MISMATCH
            digests = [item.target_sha256 if translated else item.normalized_sha256]
        else:
            expected_keys = _LIST_EXPANDED_KEYS | ({"target_sha256s"} if translated else set())
            if (keys != expected_keys or item.output_start != cursor or item.output_end is None
                    or item.output_end < cursor + 2 or item.normalized_sha256s is None
                    or len(item.normalized_sha256s) != item.output_end - cursor):
                return LIST_ITEM_LEDGER_MISMATCH
            digests = item.target_sha256s if translated else item.normalized_sha256s
            if digests is None or len(digests) != len(item.normalized_sha256s):
                return LIST_ITEM_LEDGER_MISMATCH
        actual_texts = texts[cursor:cursor + len(digests)]
        if (not all(value.strip() for value in actual_texts)
                or digests != [_text_hash(value) for value in actual_texts]):
            return LIST_ITEM_LEDGER_MISMATCH
        cursor += len(digests)
    return None if cursor == len(texts) else LIST_ITEM_LEDGER_MISMATCH


def _verified_annotation_sources(
    block: DocumentIRBlock, raw: Any, *, translated: bool, main_ids: set[str],
) -> set[tuple[str, AnnotationField, int]] | None:
    try:
        ledger = _AnnotationLedger.model_validate(raw)
    except ValidationError:
        return None
    next_index: Counter[AnnotationField] = Counter()
    sources: set[tuple[str, AnnotationField, int]] = set()
    for item in ledger.items:
        source = (item.block_id, item.field, item.source_index)
        texts = getattr(block, item.field)
        if (item.block_id not in main_ids or source in sources
                or item.target_index != next_index[item.field] or item.target_index >= len(texts)
                or not texts[item.target_index].strip()
                or _text_hash(texts[item.target_index]) != item.target_sha256
                or (not translated and item.target_sha256 != item.source_sha256)):
            return None
        sources.add(source)
        next_index[item.field] += 1
    if any(next_index[field] != len(getattr(block, field)) for field in _ANNOTATION_FIELDS):
        return None
    return sources


def source_item_ledger_evidence(document: DocumentIR) -> dict[str, Any]:
    """独立核对可变 IR 的当前内容，仅输出版本、计数和不一致块。"""
    scope = document.metadata.source_item_ledger_scope
    if scope is None:
        # 历史件允许 v1 列表账本及完全无账本。不能把坏的新件降级成历史路径。
        list_drift, annotation_drift = [], []
        for block in document.blocks:
            if "list_item_ledger" in block.metadata:
                raw = block.metadata["list_item_ledger"]
                if not isinstance(raw, dict) or raw.get("version") != LIST_ITEM_LEDGER_V1:
                    list_drift.append(block.id)
            if "annotation_ledger" in block.metadata:
                annotation_drift.append(block.id)
        if not list_drift and not annotation_drift:
            return {}
        return {
            "blocking_quality_flags": [
                *([LIST_ITEM_LEDGER_MISMATCH] if list_drift else []),
                *([ANNOTATION_LEDGER_MISMATCH] if annotation_drift else []),
            ],
            "mismatch_block_ids": list(dict.fromkeys([*list_drift, *annotation_drift])),
        }

    translated = document.metadata.translation_items_applied is True
    main_blocks = [block for block in document.blocks
                   if not block.metadata.get("source_block_id") and not block.metadata.get("synthetic")]
    main_ids = {block.id for block in main_blocks}
    annotation_ids = set(scope.annotation_block_ids)
    annotations = []
    list_drift, annotation_drift = [], []
    seen_block_ids: set[str] = set()
    list_count = list_items = annotation_count = 0
    flags: list[str] = []
    used_sources: set[tuple[str, AnnotationField, int]] = set()
    for block in document.blocks:
        if block.id in seen_block_ids:
            annotation_drift.append(block.id)
        seen_block_ids.add(block.id)
        is_main = not block.metadata.get("source_block_id") and not block.metadata.get("synthetic")
        list_payload = block.metadata.get("list_item_ledger")
        if is_main and block.type == "list":
            list_count += 1
            list_items += len(block.list_items or [])
            failure = _list_ledger_failure(block, list_payload, translated=translated)
            if failure is not None:
                flags.append(failure)
                list_drift.append(block.id)
        elif "list_item_ledger" in block.metadata or block.list_items:
            flags.append(LIST_ITEM_LEDGER_MISMATCH)
            list_drift.append(block.id)
        annotation_count += len(block.captions) + len(block.footnotes)
        has_annotations = bool(block.captions or block.footnotes or "annotation_ledger" in block.metadata)
        if is_main and (has_annotations or block.id in annotation_ids):
            annotations.append(block.id)
            sources = _verified_annotation_sources(
                block, block.metadata.get("annotation_ledger"), translated=translated, main_ids=main_ids,
            )
            if sources is None or used_sources & sources or block.id not in annotation_ids:
                annotation_drift.append(block.id)
            else:
                used_sources.update(sources)
        elif has_annotations:
            annotation_drift.append(block.id)
    if tuple(annotations) != scope.annotation_block_ids:
        annotation_drift.extend(annotations)
        annotation_drift.extend(scope.annotation_block_ids)
    if annotation_drift:
        flags.append(ANNOTATION_LEDGER_MISMATCH)
    list_drift = list(dict.fromkeys(list_drift))
    annotation_drift = list(dict.fromkeys(annotation_drift))
    return {
        "blocking_quality_flags": list(dict.fromkeys(flags)),
        "list_item_ledger": {
            "version": LIST_ITEM_LEDGER_V2, "block_count": list_count, "item_count": list_items,
            "mismatch_block_ids": list_drift,
        },
        "annotation_ledger": {
            "version": ANNOTATION_LEDGER_VERSION, "block_count": len(annotations), "item_count": annotation_count,
            "mismatch_block_ids": annotation_drift,
        },
    }


def validate_source_item_ledgers(document: DocumentIR) -> None:
    """载入新件时，在依赖题注正文的校验前完成来源认证。"""
    from app.services.document_ir.integrity import ensure_integrity

    ensure_integrity("DocumentIR 来源账本", source_item_ledger_evidence(document))


def ledger_positions(document: DocumentIR) -> tuple[LedgerPosition, ...]:
    """按翻译抽取顺序投影已认证账本的位置，不使用当前正文推导预期覆盖。"""
    if document.metadata.source_item_ledger_scope is None:
        return ()
    positions: list[LedgerPosition] = []
    for block in sorted(document.blocks, key=lambda item: item.order):
        if (ledger := block.metadata.get("list_item_ledger")) is not None:
            positions.extend((block.id, "list_items", index) for index in range(ledger["item_count"]))
        if (ledger := block.metadata.get("annotation_ledger")) is not None:
            counts = Counter(item["field"] for item in ledger["items"])
            for field in _ANNOTATION_FIELDS:
                positions.extend((block.id, field, index) for index in range(counts[field]))
    return tuple(positions)


def apply_target_digests(document: DocumentIR, replacements_by_position: Mapping[LedgerPosition, str]) -> None:
    """将已认证的翻译结果摘要绑定到冻结输出位置。"""
    from app.services.document_ir.integrity import ensure_integrity

    if document.metadata.source_item_ledger_scope is None:
        return
    positions = set(ledger_positions(document))
    missing_or_invalid = {position for position in positions
                          if not replacements_by_position.get(position, "").strip()}
    mismatches = missing_or_invalid | (replacements_by_position.keys() - positions)
    if mismatches:
        ensure_integrity("DocumentIR 来源账本", {
            "blocking_quality_flags": list(dict.fromkeys(
                LIST_ITEM_LEDGER_MISMATCH if field == "list_items" else ANNOTATION_LEDGER_MISMATCH
                for _, field, _ in sorted(mismatches)
            )),
        })
    for block in document.blocks:
        if (ledger := block.metadata.get("list_item_ledger")) is not None:
            for item in ledger["items"]:
                if item["empty"]:
                    continue
                if "output_index" in item:
                    item["target_sha256"] = _text_hash(replacements_by_position[
                        block.id, "list_items", item["output_index"]
                    ])
                else:
                    item["target_sha256s"] = [
                        _text_hash(replacements_by_position[block.id, "list_items", index])
                        for index in range(item["output_start"], item["output_end"])
                    ]
        if (ledger := block.metadata.get("annotation_ledger")) is not None:
            for item in ledger["items"]:
                item["target_sha256"] = _text_hash(replacements_by_position[
                    block.id, item["field"], item["target_index"]
                ])


def validate_ledger_source_identity(source: DocumentIR, target: DocumentIR) -> None:
    """已认证译后件的冻结来源必须与已绑定源件一致。"""
    from app.services.document_ir.integrity import ensure_integrity

    if source.metadata.source_item_ledger_scope is None and target.metadata.source_item_ledger_scope is None:
        return

    def frozen_identity(document: DocumentIR) -> tuple[
        dict[str, str], dict[str, list[dict[str, Any]]], dict[str, tuple[Any, Any]],
    ]:
        lists, annotations, bindings = {}, {}, {}
        if document.metadata.source_item_ledger_scope is not None:
            for block in document.blocks:
                if (ledger := block.metadata.get("list_item_ledger")) is not None:
                    lists[block.id] = ledger["sequence_sha256"]
                if (ledger := block.metadata.get("annotation_ledger")) is not None:
                    annotations[block.id] = [
                        {key: value for key, value in item.items() if key != "target_sha256"}
                        for item in ledger["items"]
                    ]
                if "caption_text_alias_index" in block.metadata or "table_annotation_source" in block.metadata:
                    bindings[block.id] = (
                        block.caption_text_alias_index, block.metadata.get("table_annotation_source"),
                    )
        return lists, annotations, bindings

    source_lists, source_annotations, source_bindings = frozen_identity(source)
    target_lists, target_annotations, target_bindings = frozen_identity(target)
    flags = []
    if source_lists != target_lists:
        flags.append(LIST_ITEM_LEDGER_MISMATCH)
    if (source.metadata.source_item_ledger_scope != target.metadata.source_item_ledger_scope
            or source_annotations != target_annotations
            or source_bindings != target_bindings
            or source.metadata.translation_items_applied is not None
            or target.metadata.translation_items_applied is not True):
        flags.append(ANNOTATION_LEDGER_MISMATCH)
    ensure_integrity("DocumentIR 翻译来源绑定", {"blocking_quality_flags": flags})
