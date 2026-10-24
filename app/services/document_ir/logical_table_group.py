"""逻辑表格的来源投影、保守关联和持久化一致性唯一 owner。"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    classify_mineru_block, collect_text_from_fields, extract_first_html,
)
from app.conversion.runtime.table_html_parser import HtmlTable, parse_html_table
from app.services.document_ir.layout_signals import parse_bbox, role_for_source_type
from app.services.document_ir.models import (
    ContinuationRelation, DocumentIR, LogicalTableGroup, RepeatedHeaderHint,
    SourceSpan, TableContinuationDiagnostic, TableFragment,
)


VERSION = "logical-table-groups/v1"
VERIFIED_RULE = "adjacent_table_continuation/v1"
EMPTY_RULE = "mineru_empty_table_continuation/v1"
TABLE_NUMBER = re.compile(r"^\s*(?:table|表)\s*([0-9]+)", re.IGNORECASE)
TABLE_LABEL = re.compile(r"(?<![A-Za-z])(?:table|表)\s*[0-9]+", re.IGNORECASE)
COMPOSITE_SUFFIX = re.compile(
    r"^(?:[.．]\s*[0-9]|[-–—]\s*[A-Za-z0-9]|[（(](?!\s*(?:continued|续)\s*[）)])\s*[A-Za-z0-9]+\s*[）)])",
    re.IGNORECASE,
)
CONTINUED = re.compile(r"\bcontinued\b|(?<![\u3400-\u9fff])续(?:表)?(?![\u3400-\u9fff])", re.IGNORECASE)


def _fail(reason: str) -> None:
    raise ValueError(f"逻辑表格来源合同无效：{reason}。")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _fragment_id(checksum: str, pointer: str) -> str:
    return "table-fragment:" + _digest(["table-fragment/v1", checksum, pointer])


def _group_id(first_fragment_id: str) -> str:
    return "logical-table:" + _digest([VERSION, first_fragment_id])


def _resolve(payload: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        _fail("source_pointer")
    try:
        for token in pointer.split("/")[1:]:
            token = token.replace("~1", "/").replace("~0", "~")
            payload = payload[int(token)] if isinstance(payload, list) else payload[token]
    except (KeyError, IndexError, TypeError, ValueError):
        _fail("source_pointer")
    return payload


def _source_view(raw: dict[str, Any], span: SourceSpan) -> dict[str, Any]:
    """还原消费者的可信覆盖视图；原始同名字段仍完整保存在 raw_fragment。"""
    view = {**raw, "_mineru_source": span.model_dump(exclude={"bbox"})}
    if span.page_index is not None:
        view["page_idx"] = span.page_index
    return view


def _children(node: Any, pointer: str):
    """保持共享 HTML 选择器的 direct html 优先和 JSON 插入顺序。"""
    if isinstance(node, dict):
        direct_html = isinstance(node.get("html"), str) and extract_first_html(node["html"])
        keys = (["html"] + [key for key in node if key != "html"]) if direct_html else node.keys()
        for key in keys:
            yield node[key], pointer + "/" + key.replace("~", "~0").replace("/", "~1")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield value, f"{pointer}/{index}"


def _html_pointer(raw: dict[str, Any], span: SourceSpan) -> str | None:
    # 只定位共享消费函数认可的原字符串，不复制其清理结果或另造 HTML parser。
    raw = _source_view(raw, span)
    roots = [(raw[key], "/" + key) for key in ("table_body", "table_html", "html", "content") if key in raw]
    roots.append((raw, ""))
    for root, pointer in roots:
        pending = [(root, pointer)]
        while pending:
            node, location = pending.pop()
            if isinstance(node, str) and extract_first_html(node):
                return location
            pending.extend(reversed(list(_children(node, location))))
    # 消费者不返回空 HTML；账本仍区分字段缺失与逐字空白。
    pending = [(raw, "")]
    while pending:
        node, pointer = pending.pop()
        if isinstance(node, dict):
            for key in ("table_body", "table_html", "html"):
                if isinstance(node.get(key), str):
                    return pointer + "/" + key
        pending.extend(reversed(list(_children(node, pointer))))
    return None


@dataclass(frozen=True)
class _TableSource:
    span: SourceSpan
    raw: dict[str, Any]


@dataclass(frozen=True)
class TableSourceLedger:
    """仅在单次转换内持有的原始表集合与正文数组位置。"""

    checksum: str
    tables: tuple[_TableSource, ...]
    body_order: tuple[tuple[str, int | None], ...]


def capture_table_sources(payload: Any, validated_blocks: list[dict[str, Any]], *, checksum: str) -> TableSourceLedger:
    """凭 validator 覆盖生成的 locator 取回原 JSON，保留输入自带的内部同名字段。"""
    tables: list[_TableSource] = []
    body_order: list[tuple[str, int | None]] = []
    for block in validated_blocks:
        locator = block["_mineru_source"]
        pointer = locator["json_pointer"]
        source_type = str(block.get("type") or block.get("block_type") or "").strip().lower()
        if role_for_source_type(source_type) == "body":
            body_order.append((pointer, locator["page_index"]))
        if classify_mineru_block(block, source_type) != "table" and source_type != "table_placeholder":
            continue
        raw = _resolve(payload, pointer)
        if not isinstance(raw, dict):
            _fail("source_not_object")
        tables.append(_TableSource(SourceSpan(**locator, bbox=parse_bbox(raw.get("bbox"))), copy.deepcopy(raw)))
    pointers = [source.span.json_pointer for source in tables]
    if len(set(pointers)) != len(pointers):
        _fail("duplicate_source")
    return TableSourceLedger(checksum, tuple(tables), tuple(body_order))


@dataclass(frozen=True)
class _TableShape:
    table: HtmlTable | None
    columns: int | None
    header_rows: int
    signature: str | None


def _shape(html: str | None) -> _TableShape:
    table = parse_html_table(html)
    if table is None:
        return _TableShape(None, None, 0, None)
    widths = {sum(cell.colspan for cell in row) for row in table.rows}
    reliable = len(widths) == 1 and all(cell.rowspan == 1 for row in table.rows for cell in row)
    columns = next(iter(widths)) if reliable else None
    header_rows = 0
    for row in table.rows:
        if not any(cell.is_header for cell in row):
            break
        header_rows += 1
    headers = [[{"text": " ".join(cell.text.split()), "rowspan": cell.rowspan,
                 "colspan": cell.colspan, "is_header": cell.is_header} for cell in row]
               for row in table.rows[:header_rows]]
    signature = _digest({"rows": headers, "columns": columns}) if headers else None
    return _TableShape(table, columns, header_rows, signature)


def _ordinal(text: str) -> tuple[int, int] | None:
    text = text.strip()
    if re.fullmatch(r"[0-9]+", text):
        return 10, int(text)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", text):
        return 16, int(text, 16)
    return None


def _consecutive(left: _TableShape, right: _TableShape) -> bool:
    if left.table is None or right.table is None:
        return False
    if len(left.table.rows) <= left.header_rows or len(right.table.rows) <= right.header_rows:
        return False
    previous = left.table.rows[-1][0]
    following = right.table.rows[right.header_rows][0]
    if previous.colspan != 1 or following.colspan != 1:
        return False
    start, end = _ordinal(previous.text), _ordinal(following.text)
    return start is not None and end is not None and start[0] == end[0] and start[1] + 1 == end[1]


def _caption(raw: dict[str, Any]) -> tuple[set[str], bool, bool, bool]:
    captions = collect_text_from_fields(raw, ("table_caption", "caption", "captions"))
    numbers: set[str] = set()
    continuation = False
    ordinary = False
    ambiguous = False
    for caption in captions:
        match = TABLE_NUMBER.match(caption)
        tail = caption[match.end():] if match else ""
        if match and (len(TABLE_LABEL.findall(caption)) != 1 or
                      (tail and re.match(r"[A-Za-z0-9]", tail[0])) or
                      COMPOSITE_SUFFIX.match(tail.lstrip())):
            ambiguous = True
            continue
        if match:
            numbers.add(match.group(1).lstrip("0") or "0")
        if match and CONTINUED.search(caption):
            continuation = True
        else:
            ordinary = True
    return numbers, continuation, ordinary, ambiguous or len(numbers) > 1


def _continuation(left: TableFragment, right: TableFragment, document: DocumentIR,
                  body_order: tuple[tuple[str, int | None], ...]) -> tuple[bool, str | None, str | None]:
    """明确独立证据优先；其余候选只在全部保守条件成立时归组。"""
    left_view = _source_view(left.raw_fragment, left.source_span)
    right_view = _source_view(right.raw_fragment, right.source_span)
    left_numbers, _left_continued, _left_ordinary, left_ambiguous = _caption(left_view)
    right_numbers, continued, ordinary, right_ambiguous = _caption(right_view)
    if left_ambiguous or right_ambiguous:
        return False, "insufficient_evidence", None
    if ordinary or (left_numbers and right_numbers and left_numbers != right_numbers):
        return False, None, None
    if collect_text_from_fields(left_view, ("table_footnote", "footnote", "footnotes")):
        return False, None, None
    lp, rp = left.source_span.page_index, right.source_span.page_index
    if lp is not None and rp == lp:
        return False, None, None
    if lp is None or rp is None or rp != lp + 1:
        return False, "page_not_adjacent", None
    left_page = [pointer for pointer, page in body_order if page == lp]
    right_page = [pointer for pointer, page in body_order if page == rp]
    if left_page[-1:] != [left.source_span.json_pointer] or right_page[:1] != [right.source_span.json_pointer]:
        return False, "page_body_boundary", None
    pages = {page.index: page for page in document.pages}
    before, after = pages.get(lp), pages.get(rp)
    lb, rb = left.source_span.bbox, right.source_span.bbox
    if (before is None or after is None or lb is None or rb is None or
            not before.metadata.get("page_size_source") or not after.metadata.get("page_size_source") or
            not before.width or not before.height or not after.width or not after.height):
        return False, "missing_geometry", None
    if (lb[3] < .75 * before.height or rb[1] > .25 * after.height or
            any(abs(lb[index] / before.width - rb[index] / after.width) > .05 + 1e-12 for index in (0, 2))):
        return False, "geometry_mismatch", None
    previous, following = _shape(left.raw_html), _shape(right.raw_html)
    if previous.signature and following.signature and previous.signature != following.signature:
        return False, "header_mismatch", None
    if previous.columns is None or following.columns is None:
        return False, "unreliable_columns", None
    if previous.columns != following.columns:
        return False, "column_mismatch", None
    if len(left_numbers) == len(right_numbers) == 1 and left_numbers == right_numbers and continued:
        return True, None, "same_table_number_continued"
    if previous.signature and previous.signature == following.signature and _consecutive(previous, following):
        return True, None, "matching_header_consecutive_ordinal"
    return False, "insufficient_evidence", None


def attach_logical_table_groups(document: DocumentIR, ledger: TableSourceLedger) -> None:
    """替换同版本派生字段，保持 blocks、有效源清单和可渲染 HTML 不变。"""
    by_pointer = {block.metadata["mineru_source"]["json_pointer"]: block for block in document.blocks
                  if block.type == "table"}
    report = document.metadata.mineru_validation
    if report is None or report.content_list_sha256 != ledger.checksum:
        _fail("content_checksum")
    receipts = report.normalization.get("merged_table_placeholders", [])
    merged = {receipt["json_pointer"]: receipt for receipt in receipts}
    if len(merged) != len(receipts):
        _fail("duplicate_receipt")
    filtered_receipts = report.normalization.get("filtered_blocks", [])
    filtered = {receipt["json_pointer"]: receipt for receipt in filtered_receipts}
    if len(filtered) != len(filtered_receipts):
        _fail("duplicate_filtered_receipt")
    retained_sources = []
    for source in ledger.tables:
        pointer = source.span.json_pointer
        receipt = filtered.get(pointer)
        if receipt is None:
            retained_sources.append(source)
            continue
        # 账本在封底过滤前捕获，只认可同一 validator 的精确来源回执，不为被删来源猜 owner。
        if (receipt != {**source.span.model_dump(exclude={"bbox"}),
                        "rule_id": "final_promotional_page/v1", "reason": "final_promotional_page"}
                or source.span.page_index != report.normalization.get("filtered_promotional_page_index")
                or pointer in by_pointer or pointer in merged):
            _fail("filtered_receipt")
    source_pointers = {source.span.json_pointer for source in retained_sources}
    if source_pointers != set(by_pointer) | set(merged) or set(by_pointer) & set(merged):
        _fail("source_inventory")
    fragments: dict[str, TableFragment] = {}
    for source in retained_sources:
        pointer = source.span.json_pointer
        block = by_pointer.get(pointer)
        receipt = merged.get(pointer)
        owner = block if block else by_pointer.get(receipt["target"]["json_pointer"])
        if owner is None:
            _fail("render_owner")
        fragment = TableFragment(
            fragment_id=_fragment_id(ledger.checksum, pointer), source_span=source.span,
            block_id=block.id if block else None, render_owner_block_id=owner.id,
            raw_fragment=source.raw, raw_html_pointer=_html_pointer(source.raw, source.span), html_state="missing",
            normalization_rule_id=receipt["rule_id"] if receipt else None,
            normalization_reason=receipt["reason"] if receipt else None,
        )
        html = fragment.raw_html
        fragment.html_state = "missing" if html is None else "present" if html.strip() else "empty"
        fragment.raw_html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest() if html is not None else None
        fragment.header_signature = _shape(html).signature
        fragments[pointer] = fragment
    groups: list[LogicalTableGroup] = []
    group_by_pointer: dict[str, LogicalTableGroup] = {}
    body_predecessor = {ledger.body_order[index][0]: ledger.body_order[index - 1][0]
                        for index in range(1, len(ledger.body_order))}
    for pointer, fragment in fragments.items():
        diagnostic = None
        if pointer in merged:
            previous_pointer = merged[pointer]["target"]["json_pointer"]
            group = group_by_pointer.get(previous_pointer)
            if group is None:
                _fail("normalization_order")
            previous = fragments[previous_pointer]
            relation = ContinuationRelation(from_fragment_id=previous.fragment_id, to_fragment_id=fragment.fragment_id,
                                            kind="normalized_empty_placeholder", rule_id=EMPTY_RULE,
                                            evidence_codes=["normalization_receipt"])
        else:
            previous_pointer = body_predecessor.get(pointer)
            previous = fragments.get(previous_pointer)
            verified, reason, evidence = (False, None, None)
            if previous is not None and previous.block_id is not None:
                verified, reason, evidence = _continuation(previous, fragment, document, ledger.body_order)
            if verified:
                group = group_by_pointer[previous_pointer]
                relation = ContinuationRelation(from_fragment_id=previous.fragment_id, to_fragment_id=fragment.fragment_id,
                                                kind="verified_continuation", rule_id=VERIFIED_RULE,
                                                evidence_codes=["adjacent_page_geometry", evidence])
                shape = _shape(fragment.raw_html)
                if shape.signature and shape.signature == previous.header_signature:
                    fragment.repeated_header_hint = RepeatedHeaderHint(row_count=shape.header_rows, signature=shape.signature)
            else:
                group = LogicalTableGroup(logical_group_id=_group_id(fragment.fragment_id), fragments=[])
                groups.append(group)
                relation = None
                if reason:
                    diagnostic = TableContinuationDiagnostic(from_fragment_id=previous.fragment_id,
                                                              to_fragment_id=fragment.fragment_id, reason=reason)
        group.fragments.append(fragment)
        if relation:
            group.continuation_relations.append(relation)
        if diagnostic:
            group.diagnostics.append(diagnostic)
        group_by_pointer[pointer] = group
    document.metadata.logical_table_groups_version = VERSION
    document.metadata.logical_table_groups = groups
    document.metadata.logical_table_group_counts = _counts(groups)
    document.quality_flags = [flag for flag in document.quality_flags if not flag.startswith("table_continuation_uncertain:")]
    for group in groups:
        for diagnostic in group.diagnostics:
            document.quality_flags.append(f"table_continuation_uncertain:{diagnostic.to_fragment_id}")
        for fragment in group.fragments:
            if fragment.block_id:
                block = by_pointer[fragment.source_span.json_pointer]
                block.metadata.update(logical_group_id=group.logical_group_id, table_fragment_id=fragment.fragment_id,
                                      source_spans=[item.source_span.model_dump(mode="json") for item in group.fragments
                                                    if item.render_owner_block_id == block.id])
    validate_logical_table_groups(document)


def _counts(groups: list[LogicalTableGroup]) -> dict[str, int]:
    return {"group_count": len(groups), "fragment_count": sum(len(group.fragments) for group in groups),
            "normalized_empty_fragment_count": sum(fragment.block_id is None for group in groups for fragment in group.fragments),
            "uncertain_count": sum(len(group.diagnostics) for group in groups)}


def validate_logical_table_groups(document: DocumentIR) -> None:
    """构建与 JSON 重读共用结构对账；不从译文重新推导来源事实。"""
    metadata = document.metadata
    groups = metadata.logical_table_groups
    if metadata.logical_table_groups_version is None:
        if (groups or metadata.logical_table_group_counts or any(
                any(key in block.metadata for key in ("logical_group_id", "table_fragment_id"))
                for block in document.blocks)):
            _fail("missing_version")
        return
    report = metadata.mineru_validation
    if report is None or not report.content_list_sha256:
        _fail("content_checksum")
    blocks = {block.id: block for block in document.blocks if block.type == "table"}
    if len(blocks) != sum(block.type == "table" for block in document.blocks):
        _fail("duplicate_block")
    fragments = [fragment for group in groups for fragment in group.fragments]
    pointers = [fragment.source_span.json_pointer for fragment in fragments]
    identities = [fragment.fragment_id for fragment in fragments]
    if len(set(pointers)) != len(pointers) or len(set(identities)) != len(identities):
        _fail("duplicate_source")
    indices = [fragment.source_span.source_index for fragment in fragments]
    if len(set(indices)) != len(indices):
        _fail("duplicate_source_index")
    if len({group.logical_group_id for group in groups}) != len(groups):
        _fail("duplicate_group")
    receipts = report.normalization.get("merged_table_placeholders", [])
    merged = {receipt["json_pointer"]: receipt for receipt in receipts}
    if len(merged) != len(receipts) or set(merged) != {fragment.source_span.json_pointer for fragment in fragments if fragment.block_id is None}:
        _fail("normalization_inventory")
    if Counter(fragment.block_id for fragment in fragments if fragment.block_id) != Counter(blocks.keys()):
        _fail("block_inventory")
    # 用不参与翻译的源定位还原正文顺序，重读时不相信关系中自报的正证据。
    body_sources = [block.metadata["mineru_source"] for block in document.blocks
                    if not block.metadata.get("source_block_id") and
                    (block.layout is None or block.layout.role == "body")]
    body_sources.extend(fragment.source_span.model_dump(exclude={"bbox"})
                        for fragment in fragments if fragment.block_id is None)
    body_sources.sort(key=lambda source: source["source_index"])
    body_order = tuple((source["json_pointer"], source["page_index"]) for source in body_sources)
    predecessor = {body_order[index][0]: body_order[index - 1][0] for index in range(1, len(body_order))}
    all_ids = set(identities)
    for group in groups:
        if not group.fragments or group.logical_group_id != _group_id(group.fragments[0].fragment_id):
            _fail("group_identity")
        # 空片只能通过 receipt 归到已有渲染 owner，不能独立成为无 incoming 的组首。
        if group.fragments[0].block_id is None:
            _fail("normalization_group")
        ordered = [fragment.source_span.source_index for fragment in group.fragments]
        if ordered != sorted(ordered):
            _fail("fragment_order")
        order = {fragment.fragment_id: index for index, fragment in enumerate(group.fragments)}
        incoming: Counter[str] = Counter()
        for relation in group.continuation_relations:
            if (relation.from_fragment_id not in order or relation.to_fragment_id not in order or
                    order[relation.from_fragment_id] >= order[relation.to_fragment_id]):
                _fail("relation_order")
            incoming[relation.to_fragment_id] += 1
            target = group.fragments[order[relation.to_fragment_id]]
            source = group.fragments[order[relation.from_fragment_id]]
            if relation.kind == "normalized_empty_placeholder":
                if (target.block_id is not None or source.block_id != target.render_owner_block_id or
                        relation.rule_id != EMPTY_RULE or relation.evidence_codes != ["normalization_receipt"]):
                    _fail("normalization_relation")
            else:
                verified, _reason, evidence = _continuation(source, target, document, body_order)
                if (target.block_id is None or source.block_id is None or relation.rule_id != VERIFIED_RULE or
                        order[target.fragment_id] != order[source.fragment_id] + 1 or
                        predecessor.get(target.source_span.json_pointer) != source.source_span.json_pointer or
                        not verified or relation.evidence_codes != ["adjacent_page_geometry", evidence]):
                    _fail("verified_relation")
        if incoming != Counter(fragment.fragment_id for fragment in group.fragments[1:]):
            _fail("relation_inventory")
        for diagnostic in group.diagnostics:
            if diagnostic.from_fragment_id not in all_ids or diagnostic.to_fragment_id not in order:
                _fail("diagnostic_reference")
        for fragment in group.fragments:
            span = fragment.source_span
            if fragment.fragment_id != _fragment_id(report.content_list_sha256, span.json_pointer):
                _fail("fragment_identity")
            if fragment.raw_html_pointer != _html_pointer(fragment.raw_fragment, span):
                _fail("raw_html_pointer")
            html = fragment.raw_html
            state = "missing" if html is None else "present" if html.strip() else "empty"
            checksum = hashlib.sha256(html.encode("utf-8")).hexdigest() if html is not None else None
            shape = _shape(html)
            if (fragment.html_state != state or fragment.raw_html_sha256 != checksum or
                    fragment.header_signature != shape.signature or span.bbox != parse_bbox(fragment.raw_fragment.get("bbox"))):
                _fail("raw_projection")
            if fragment.repeated_header_hint is not None:
                hint = fragment.repeated_header_hint
                previous = next((item for item in group.continuation_relations
                                 if item.to_fragment_id == fragment.fragment_id and item.kind == "verified_continuation"), None)
                if (hint.signature != shape.signature or hint.row_count != shape.header_rows or previous is None or
                        group.fragments[order[previous.from_fragment_id]].header_signature != shape.signature):
                    _fail("repeated_header_hint")
            owner = blocks.get(fragment.render_owner_block_id)
            if owner is None:
                _fail("render_owner")
            if fragment.block_id:
                if fragment.block_id != owner.id or owner.metadata.get("mineru_source") != span.model_dump(exclude={"bbox"}):
                    _fail("block_source")
                expected = [item.source_span.model_dump(mode="json") for item in group.fragments if item.render_owner_block_id == owner.id]
                if (owner.metadata.get("logical_group_id") != group.logical_group_id or
                        owner.metadata.get("table_fragment_id") != fragment.fragment_id or owner.metadata.get("source_spans") != expected):
                    _fail("block_spans")
                if fragment.normalization_rule_id is not None or fragment.normalization_reason is not None:
                    _fail("unexpected_normalization")
            else:
                receipt = merged[span.json_pointer]
                if (receipt.get("rule_id") != EMPTY_RULE or fragment.normalization_rule_id != EMPTY_RULE or
                        fragment.normalization_reason != receipt.get("reason") or
                        receipt.get("target") != owner.metadata.get("mineru_source") or
                        {key: receipt.get(key) for key in span.model_dump(exclude={"bbox"})} != span.model_dump(exclude={"bbox"})):
                    _fail("normalization_receipt")
    if metadata.logical_table_group_counts != _counts(groups):
        _fail("group_counts")
