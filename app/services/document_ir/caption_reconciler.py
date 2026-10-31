"""只读整理 MinerU 题注；严格修复与原文证据共享唯一的消费结果。"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    append_footnote_fragment, classify_mineru_block, clean_text, coerce_text_list, mineru_raw_text_preserving_lines,
)
from app.services.document_ir.artifact_validator import parse_valid_bbox
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.layout_signals import parse_page_index
from app.services.document_ir.table_annotations import (
    is_mixed_table_context_annotation, is_table_context_annotation,
)


RULE_VERSION = "caption-reconciliation/v1"
NUMBERED_CAPTION_RE = re.compile(
    r"^\s*(?P<label>图|表|Figure|Table)\s*(?P<number>[0-9]+)"
    r"(?![A-Za-z0-9]|[.．]\d|[-–—][A-Za-z0-9]|\s*[（(][A-Za-z0-9]|\s*[、,，/&]\s*\d)",
    re.IGNORECASE,
)
CAPTION_TOKEN_RE = re.compile(r"(?:图|表|\bFigure|\bTable)\s*[0-9]+", re.IGNORECASE)
CAPTION_LEAD_RE = re.compile(r"^\s*(?:图|表|Figure\b|Table\b)", re.IGNORECASE)
NUMBER_CONTINUATION_RE = re.compile(
    r"^\s*(?:[-–—~～至到、,，/&]|与|及|和|或|and\b|or\b|to\b|through\b)"
    r"\s*(?:(?:图|表|Figure|Table)\s*)?[0-9]", re.IGNORECASE,
)


@dataclass(frozen=True)
class CaptionFragment:
    """片段只引用原始字符串区间；不复制 donor 的原始 rich 值。"""

    donor_index: int
    group_pointer: str
    spans: tuple[tuple[str, int, int], ...]
    text: str


@dataclass
class _CaptionGroup:
    donor_index: int
    pointer: str
    runs: list[tuple[str, str, dict[str, Any] | None]]


@dataclass
class ReconciledCaption:
    captions: list[str] = field(default_factory=list)
    evidence: dict[str, Any] | None = None


def _source_type(block: dict[str, Any]) -> str:
    return str(block.get("type") or block.get("block_type") or "").strip().lower()


def _family(block: dict[str, Any]) -> str | None:
    effective_type = classify_mineru_block(block, _source_type(block))
    return "figure" if effective_type == "image" else "table" if effective_type == "table" else None


def _pointer(parent: str, key: str | int) -> str:
    return f"{parent}/{str(key).replace('~', '~0').replace('/', '~1')}"


def _caption_fields(block: dict[str, Any], keys: list[str], root: str) -> list[tuple[str, Any]]:
    """保留旧字段优先级，但不进入内部证据或重复扫描已选题注值。"""

    fields: list[tuple[str, Any]] = []
    for key in keys:
        def visit(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for child_key, child in value.items():
                    if child_key.startswith("_") or child_key in {"metadata", "caption_reconciliation"}:
                        continue
                    child_path = _pointer(path, child_key)
                    if child_key == key:
                        fields.append((child_path, child))
                    elif child_key not in keys:
                        visit(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, _pointer(path, index))
        visit(block, root)
    return fields


def _groups(value: Any, pointer: str, donor_index: int) -> list[_CaptionGroup]:
    if isinstance(value, str):
        return [_CaptionGroup(donor_index, pointer, [(pointer, value, None)])]
    if isinstance(value, list):
        if value and all(isinstance(node, dict) and isinstance(node.get("type"), str)
                         and isinstance(node.get("content"), str) for node in value):
            return [_CaptionGroup(donor_index, pointer, [
                (_pointer(_pointer(pointer, index), "content"), node["content"], node)
                for index, node in enumerate(value)
            ])]
        return [group for index, child in enumerate(value)
                for group in _groups(child, _pointer(pointer, index), donor_index)]
    if isinstance(value, dict):
        if isinstance(value.get("content"), str) and isinstance(value.get("type"), str):
            return [_CaptionGroup(donor_index, pointer, [(_pointer(pointer, "content"), value["content"], value)])]
        return [group for key, child in value.items() if key not in {"type", "path", "img_path", "image_path"}
                for group in _groups(child, _pointer(pointer, key), donor_index)]
    return []


def _render_spans(group: _CaptionGroup, spans: tuple[tuple[str, int, int], ...]) -> str:
    runs = {pointer: (text, node) for pointer, text, node in group.runs}
    rendered = ""
    for pointer, start, end in spans:
        text, node = runs[pointer]
        value = text[start:end] if node is None else {**node, "content": text[start:end]}
        for fragment in coerce_text_list(value):
            rendered = append_footnote_fragment(rendered, fragment)
    return clean_text(rendered)


def _fragment(group: _CaptionGroup, start: int, end: int) -> CaptionFragment:
    offset = 0
    spans: list[tuple[str, int, int]] = []
    for pointer, text, _node in group.runs:
        left, right = max(start - offset, 0), min(end - offset, len(text))
        if right > left:
            spans.append((pointer, left, right))
        offset += len(text)
    selected = tuple(spans)
    return CaptionFragment(group.donor_index, group.pointer, selected, _render_spans(group, selected))


def _number(text: str) -> tuple[str, int] | None:
    match = NUMBERED_CAPTION_RE.match(text)
    if match is None or len(match["number"]) > 18:
        return None
    # 范围及共享标签续号不是单一整数标题，不能只取首号自动绑定。
    if NUMBER_CONTINUATION_RE.match(text[match.end():]):
        return None
    return match["label"].lower(), int(match["number"])


def _split_group(group: _CaptionGroup, family: str) -> list[CaptionFragment]:
    """只有原串换行后的完整编号或独立条件行才是边界，节点边界无此含义。"""

    raw = "".join(text for _pointer, text, _node in group.runs)
    lines = list(re.finditer(r"[^\r\n]+(?:\r\n|\r|\n|$)", raw))
    first_line = lines[0].group() if lines else ""
    if not _number(first_line) and not (family == "table" and is_table_context_annotation(first_line)):
        return [_fragment(group, 0, len(raw))]
    if family == "table" and not any(_number(line.group()) for line in lines):
        return [_fragment(group, 0, len(raw))]
    boundaries = [0]
    for line in lines[1:]:
        offset = 0
        boundary_is_text = False
        for _pointer, text, node in group.runs:
            if offset <= line.start() < offset + len(text):
                boundary_is_text = node is None or node.get("type") == "text"
                break
            offset += len(text)
        if boundary_is_text and (_number(line.group()) or (family == "table" and is_table_context_annotation(line.group()))):
            boundaries.append(line.start())
    boundaries.append(len(raw))
    return [_fragment(group, start, end) for start, end in zip(boundaries, boundaries[1:]) if start < end]


def _validate_repair(groups: list[_CaptionGroup], assignments: list[list[CaptionFragment]],
                     visible_captions: list[list[str]]) -> None:
    """仅拟修复结果执行守恒门禁；原始重复或普通歧义不属于确定性损坏。"""

    expected = {(group.donor_index, group.pointer): group for group in groups}
    consumed: dict[tuple[int, str], list[CaptionFragment]] = {}
    damaged = visible_captions != [[fragment.text for fragment in fragments] for fragments in assignments]
    for fragments in assignments:
        for fragment in fragments:
            key = (fragment.donor_index, fragment.group_pointer)
            group = expected.get(key)
            if group is None:
                damaged = True
                continue
            consumed.setdefault(key, []).append(fragment)
            try:
                if fragment.text != _render_spans(group, fragment.spans) or not fragment.text:
                    damaged = True
            except (KeyError, TypeError, ValueError):
                damaged = True
    for key, group in expected.items():
        actual: dict[str, list[tuple[int, int]]] = {}
        for fragment in consumed.get(key, []):
            for pointer, start, end in fragment.spans:
                actual.setdefault(pointer, []).append((start, end))
        for pointer, text, _node in group.runs:
            cursor = 0
            for start, end in sorted(actual.pop(pointer, [])):
                if start != cursor or end <= start or end > len(text):
                    damaged = True
                cursor = end
            if cursor != len(text):
                damaged = True
        if actual:
            damaged = True
    if damaged:
        raise DocumentIntegrityError("CaptionReconciler", {
            "blocking_quality_flags": ["caption_reconciliation_integrity:fragment_conservation"],
            "source_locators": sorted({group.pointer for group in groups}),
        })


def _uncertain(result: ReconciledCaption, reasons: list[str]) -> None:
    if result.evidence is not None:
        result.evidence["status"] = "uncertain"
        result.evidence["reasons"] = list(dict.fromkeys([*result.evidence["reasons"], *reasons]))


def _consecutive(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_source, right_source = left.get("_mineru_source", {}), right.get("_mineru_source", {})
    left_index, right_index = left_source.get("source_index"), right_source.get("source_index")
    return (type(left_index) is int and type(right_index) is int and right_index == left_index + 1
            and isinstance(left_source.get("json_pointer"), str) and isinstance(right_source.get("json_pointer"), str))


def _binding(fragment: CaptionFragment, target: int, blocks: list[dict[str, Any]], rule_id: str) -> dict[str, Any]:
    parsed = _number(fragment.text)
    return {
        "source_locator": deepcopy(blocks[fragment.donor_index]["_mineru_source"]),
        "donor_index": fragment.donor_index, "target_index": target,
        "group_pointer": fragment.group_pointer,
        "source_spans": [{"json_pointer": pointer, "start": start, "end": end} for pointer, start, end in fragment.spans],
        "label": parsed[0] if parsed else None, "number": parsed[1] if parsed else None,
        "rule_id": rule_id,
        "reason": "strict_numbered_sequence" if rule_id == "strict_numbered_group/v1" else "explicit_annotation_boundary",
        "evidence_only": False,
    }


def _reconcile_group(indices: list[int], blocks: list[dict[str, Any]], groups_by_block: list[list[_CaptionGroup]],
                     results: list[ReconciledCaption]) -> None:
    family = _family(blocks[indices[0]])
    source_groups = [group for index in indices for group in groups_by_block[index]]
    pieces = [fragment for group in source_groups for fragment in _split_group(group, family or "") if fragment.text]
    if not pieces:
        return
    reasons: list[str] = []
    for piece in pieces:
        if len(CAPTION_TOKEN_RE.findall(piece.text)) > 1:
            reasons.append("split_boundary_uncertain")
        elif CAPTION_LEAD_RE.match(piece.text) and not _number(piece.text):
            reasons.append("unsupported_number")
        if family == "table" and is_mixed_table_context_annotation(piece.text):
            reasons.append("mixed_context_boundary_uncertain")
    # 真表题与条件已有可靠结构时可独立分类；条件仍属于原表，不能参与跨表分配。
    contexts = family == "table" and any(is_table_context_annotation(piece.text) for piece in pieces)
    if contexts:
        numbered = [number for piece in pieces if (number := _number(piece.text)) is not None]
        labels = {label for label, _number_value in numbered}
        if len(labels) > 1 or labels - {"表", "table"}:
            reasons.append("mixed_labels")
        if len(set(numbered)) != len(numbered):
            # renderer 会去重相同表题，不能把此类原串拆成会丢失可见次数的候选。
            reasons.append("duplicate_number")
        for index in indices:
            local_groups = groups_by_block[index]
            local_pieces = [piece for group in local_groups for piece in _split_group(group, "table") if piece.text]
            if any(len(_split_group(group, "table")) > 1 for group in local_groups) and not reasons:
                captions = [piece.text for piece in local_pieces]
                _validate_repair(local_groups, [local_pieces], [captions])
                results[index].captions = captions
                results[index].evidence["status"] = "rebound"
                results[index].evidence["bindings"] = [_binding(piece, index, blocks, "explicit_annotation_boundary/v1")
                                                       for piece in local_pieces]
        if len(indices) > 1 and any(not results[index].captions for index in indices):
            reasons.append("competing_subjects")
        for index in indices:
            if reasons:
                _uncertain(results[index], reasons)
        return
    if not reasons and not any(CAPTION_LEAD_RE.match(piece.text) or CAPTION_TOKEN_RE.search(piece.text) for piece in pieces):
        return
    already_one_to_one = all(len(results[index].captions) == 1 for index in indices) and len(pieces) == len(indices)
    if len(pieces) != len(indices):
        reasons.append("count_mismatch")
    parsed = [_number(piece.text) for piece in pieces]
    if any(item is None for item in parsed):
        # 普通非编号图注本身合法；仅在存在编号修复线索时记录组歧义。
        if not reasons and not any(CAPTION_TOKEN_RE.search(piece.text) for piece in pieces):
            return
        reasons.append("unclassified_annotation")
    else:
        labels = {item[0] for item in parsed}
        numbers = [item[1] for item in parsed]
        if len(labels) != 1 or any((label in {"表", "table"}) != (family == "table") for label in labels):
            reasons.append("mixed_labels")
        if len(set(numbers)) != len(numbers):
            reasons.append("duplicate_number")
        elif sorted(numbers) != list(range(min(numbers), min(numbers) + len(numbers))):
            reasons.append("non_contiguous_numbers")
    # 完整的一对象一题注保持原关联，编号逆序也不能触发重排。
    if already_one_to_one:
        for index in indices:
            if reasons:
                _uncertain(results[index], reasons)
        return
    if reasons or len(indices) < 2 or parse_page_index(blocks[indices[0]]) is None:
        if parse_page_index(blocks[indices[0]]) is None:
            reasons.append("missing_page")
        for index in indices:
            _uncertain(results[index], reasons)
        return
    ordered = sorted(pieces, key=lambda piece: _number(piece.text)[1])
    assignments = [[piece] for piece in ordered]
    captions_by_target = [[piece.text for piece in fragments] for fragments in assignments]
    _validate_repair(source_groups, assignments, captions_by_target)
    group_id = f"{RULE_VERSION}:{blocks[indices[0]]['_mineru_source']['json_pointer']}"
    for index, fragments, captions in zip(indices, assignments, captions_by_target, strict=True):
        results[index].captions = captions
        evidence = results[index].evidence
        evidence.update(status="rebound", group_id=group_id,
                        bindings=[_binding(piece, index, blocks, "strict_numbered_group/v1") for piece in fragments])
    results[indices[0]].evidence["members"] = indices


def _paragraph_evidence(blocks: list[dict[str, Any]], results: list[ReconciledCaption]) -> None:
    for index, block in enumerate(blocks):
        if _source_type(block) not in {"paragraph", "text", "para"} or _family(block) is not None:
            continue
        text = clean_text(mineru_raw_text_preserving_lines(block))
        tokens = list(CAPTION_TOKEN_RE.finditer(text))
        if not tokens:
            continue
        parsed = _number(text) or _number(tokens[0].group())
        if parsed is None:
            continue
        family = "table" if parsed[0] in {"表", "table"} else "figure"
        adjacent = [target for target in (index - 1, index + 1) if 0 <= target < len(blocks)
                    and _family(blocks[target]) == family]
        if not adjacent or all(results[target].captions for target in adjacent):
            continue
        reasons: list[str] = []
        if _number(text) is None:
            reasons.append("not_caption_title")
        if len(tokens) != 1:
            reasons.append("split_boundary_uncertain")
        if len(adjacent) != 1 or any(results[target].captions for target in adjacent):
            reasons.append("competing_subjects")
        for target in adjacent:
            page = parse_page_index(block)
            if page is None or page != parse_page_index(blocks[target]):
                reasons.append("cross_page")
            left, right = sorted((target, index))
            if not _consecutive(blocks[left], blocks[right]):
                reasons.append("non_contiguous_source")
            caption_box, target_box = parse_valid_bbox(block.get("bbox")), parse_valid_bbox(blocks[target].get("bbox"))
            if caption_box is None or target_box is None:
                reasons.append("missing_layout")
            elif (min(caption_box[2], target_box[2]) <= max(caption_box[0], target_box[0])
                  or (family == "figure" and caption_box[1] < target_box[3])
                  or (family == "table" and caption_box[3] > target_box[1])
                  or (family == "figure" and target > index) or (family == "table" and target < index)):
                reasons.append("layout_mismatch")
        for target in adjacent:
            evidence = results[target].evidence
            receipt = {"source_locator": deepcopy(block["_mineru_source"]), "donor_index": index,
                       "target_index": target, "label": parsed[0], "number": parsed[1],
                       "rule_id": "adjacent_paragraph/v1", "evidence_only": True}
            if reasons:
                receipt["reasons"] = list(dict.fromkeys(reasons))
                evidence.setdefault("candidates", []).append(receipt)
                _uncertain(results[target], reasons)
            else:
                receipt["reason"] = "unique_adjacent_layout"
                evidence["bindings"].append(receipt)
                evidence["status"] = "evidence_only"


def reconcile_captions(raw_blocks: list[dict[str, Any]]) -> list[ReconciledCaption]:
    """从已验证源块重建结果；不修改输入，也不追加前次运行的证据。"""

    results: list[ReconciledCaption] = []
    groups_by_block: list[list[_CaptionGroup]] = []
    for index, block in enumerate(raw_blocks):
        family = _family(block)
        groups: list[_CaptionGroup] = []
        result = ReconciledCaption()
        source = block.get("_mineru_source", {})
        keys = ([f"{_source_type(block)}_caption", "caption"]
                if _source_type(block) in {"table", "image", "chart", "figure"} else ["caption"])
        originals: list[dict[str, Any]] = []
        for pointer, value in _caption_fields(block, keys, source.get("json_pointer", "")):
            field_groups = _groups(value, pointer, index)
            if field_groups:
                originals.append({"json_pointer": pointer, "value": deepcopy(value),
                                  "groups": [group.pointer for group in field_groups]})
            groups.extend(group for group in field_groups if _fragment(group, 0, sum(len(run[1]) for run in group.runs)).text)
        result.captions = list(dict.fromkeys(
            _fragment(group, 0, sum(len(run[1]) for run in group.runs)).text for group in groups
        ))
        if family:
            result.evidence = {"rule_version": RULE_VERSION, "status": "unchanged", "originals": originals,
                               "bindings": [], "reasons": []}
        results.append(result)
        groups_by_block.append(groups)
    index = 0
    while index < len(raw_blocks):
        family = _family(raw_blocks[index])
        if family is None:
            index += 1
            continue
        end = index + 1
        while (end < len(raw_blocks) and _family(raw_blocks[end]) == family
               and parse_page_index(raw_blocks[index]) == parse_page_index(raw_blocks[end])
               and _consecutive(raw_blocks[end - 1], raw_blocks[end])):
            end += 1
        _reconcile_group(list(range(index, end)), raw_blocks, groups_by_block, results)
        if end < len(raw_blocks) and _family(raw_blocks[end]) == family:
            combined = [*range(index, end), end]
            counts = [sum(len(_split_group(group, family)) for group in groups_by_block[item]) for item in combined]
            if 0 in counts and any(count > 1 for count in counts):
                reason = "cross_page" if parse_page_index(raw_blocks[end - 1]) != parse_page_index(raw_blocks[end]) else "non_contiguous_source"
                for item in combined:
                    _uncertain(results[item], [reason])
        index = end
    _paragraph_evidence(raw_blocks, results)
    return results
