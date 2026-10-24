"""通用非可见书签的同次创建证明与最终 OOXML 关系认证。"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pydantic import Field

from app.services.renderer.block_evidence import (
    BlockRenderEvidence, BlockRenderRecord, LocalTarget, PackageIndex, PART_RE,
)
from app.services.renderer.render_plan import RenderContract, RenderPlan, Sha256, content_hash

BLOCK_ANCHOR_VERSION = "block-anchor-evidence/v1"
MAX_ANCHOR_BYTES = 8 * 1024 * 1024
MAX_ANCHOR_ENTRIES = 100000
# B1 兼容构建仅停止新写入；已有证明和图片报告的 reader 必须保留。
BLOCK_ANCHOR_GENERATION_POLICY = "enabled/v1"
ANCHOR_NAME_RE = re.compile(r"md2w_blk_[0-9a-f]{30}\Z")


class AnchorLocator(RenderContract):
    part: str
    child_path: list[int] = Field(min_length=1)


class AnchorTarget(AnchorLocator):
    role: str
    item_index: int | None


class BlockAnchorEntry(RenderContract):
    block_id: str
    anchor_ref: str
    bookmark_name: str
    start: AnchorLocator
    end: AnchorLocator
    target: AnchorTarget


class BlockAnchorEvidence(RenderContract):
    schema_version: Literal["block-anchor-evidence/v1"] = BLOCK_ANCHOR_VERSION
    input_ir_sha256: Sha256
    plan_sha256: Sha256
    docx_sha256: Sha256
    entries: list[BlockAnchorEntry]
    evidence_sha256: Sha256


@dataclass(frozen=True, slots=True)
class _BlockAnchorOwnership:
    """只由创建节点引用冻结；持久化 reader 不生成此对象。"""

    input_ir_sha256: str
    plan_sha256: str
    docx_sha256: str
    entries: tuple[tuple, ...]


@dataclass(slots=True)
class _LocalBlockAnchor:
    block_id: str
    anchor_ref: str
    bookmark_name: str
    target: LocalTarget
    start: Any
    end: Any


def block_bookmark_name(anchor_ref: str) -> str:
    """短名只用于包内定位，完整逻辑身份仍由 trace 和证明保存。"""
    return "md2w_blk_" + anchor_ref.removeprefix("render-block:")[:30]


def bookmark_inventory(document: Any) -> tuple[set[str], set[int]]:
    names, ids = set(), set()
    for part in document.part.package.parts:
        if PART_RE.fullmatch(str(part.partname).lstrip("/")) and hasattr(part, "element"):
            for node in part.element.iter():
                if node.tag in {qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
                    value = node.get(qn("w:id"), "")
                    if value.isdecimal():
                        ids.add(int(value))
                    if node.tag == qn("w:bookmarkStart"):
                        names.add(node.get(qn("w:name"), ""))
    return names, ids


def _placement(target: LocalTarget) -> tuple[Any, Any | None]:
    node = target.element
    if node.tag == qn("w:tbl"):
        return next(node.iter(qn("w:p"))), None
    if node.tag == qn("w:p"):
        return node, None
    paragraph = next(node.iterancestors(qn("w:p")))
    run = next(node.iterancestors(qn("w:r")))
    if run.getparent() is not paragraph:
        raise ValueError("block_anchor:target_mismatch")
    return paragraph, run


def materialize_block_anchors(document: Any, records: dict[str, BlockRenderRecord],
                              targets: dict[str, list[LocalTarget]],
                              reserved: tuple[set[str], set[int]]) -> tuple[list[_LocalBlockAnchor], dict[str, int]]:
    """只处理实际输出引用；同名冲突保留模板，失败时撤回本次半对。"""
    if BLOCK_ANCHOR_GENERATION_POLICY != "enabled/v1":
        return [], {"created": 0, "generation_disabled": 1}
    names, ids = bookmark_inventory(document)
    names.update(reserved[0])
    ids.update(reserved[1])
    next_id = max(ids, default=-1) + 1
    candidates = {block_id: block_bookmark_name(record.anchor_ref)
                  for block_id, record in records.items() if targets[block_id]}
    name_counts: dict[str, int] = {}
    for name in candidates.values():
        name_counts[name] = name_counts.get(name, 0) + 1
    created, counts = [], {"created": 0, "name_conflict": 0, "target_unavailable": 0}
    for block_id, name in candidates.items():
        if name in names or name_counts[name] != 1:
            counts["name_conflict"] += 1
            continue
        own_targets = targets[block_id]
        target = own_targets[0]
        if any(item.role == "table" for item in own_targets):
            target = next((item for item in own_targets if item.role in {"caption", "context"}), target)
        start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
        start.set(qn("w:name"), name)
        start.set(qn("w:id"), str(next_id))
        end.set(qn("w:id"), str(next_id))
        try:
            paragraph, run = _placement(target)
            if run is not None:
                run.addprevious(start)
                run.addnext(end)
            else:
                properties = paragraph.find(qn("w:pPr"))
                paragraph.insert(1 if properties is not None else 0, start)
                paragraph.append(end)
        except (ValueError, StopIteration):
            for marker in (start, end):
                if marker.getparent() is not None:
                    marker.getparent().remove(marker)
            counts["target_unavailable"] += 1
            continue
        created.append(_LocalBlockAnchor(block_id, records[block_id].anchor_ref, name, target, start, end))
        names.add(name)
        next_id += 1
    counts["created"] = len(created)
    return created, counts


def _bounded_json(value: Any) -> bool:
    """逐片计量，拒绝超限证明而不先创建一个无限制编码字符串。"""
    pending, minimum = [value], 0
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            minimum += len(item)
            if minimum > MAX_ANCHOR_BYTES:
                return False
        elif isinstance(item, dict):
            pending.extend(item)
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    size = 0
    for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > MAX_ANCHOR_BYTES:
            return False
    return True


def _entry_identity(entry: BlockAnchorEntry) -> tuple:
    return (entry.block_id, entry.anchor_ref, entry.bookmark_name,
            entry.start.part, tuple(entry.start.child_path), entry.end.part, tuple(entry.end.child_path),
            entry.target.part, tuple(entry.target.child_path), entry.target.role, entry.target.item_index)


def freeze_block_anchors(created: list[_LocalBlockAnchor], live_paths: dict,
                         plan: RenderPlan, docx_sha256: str) -> tuple[BlockAnchorEvidence | None, _BlockAnchorOwnership | None]:
    """最终保存后从真实创建引用取路径，不从书签名字反推成功事实。"""
    if len(created) > MAX_ANCHOR_ENTRIES:
        return None, None
    entries, size = [], 0
    for local in created:
        def locate(node):
            part, path = live_paths[local.target.part, node]
            return {"part": part, "child_path": list(path)}
        entry = BlockAnchorEntry(block_id=local.block_id, anchor_ref=local.anchor_ref, bookmark_name=local.bookmark_name,
            start=AnchorLocator(**locate(local.start)), end=AnchorLocator(**locate(local.end)),
            target=AnchorTarget(**locate(local.target.element), role=local.target.role, item_index=local.target.item_index))
        if not _bounded_json(entry.model_dump(mode="json")):
            return None, None
        size += len(entry.model_dump_json().encode("utf-8")) + 1
        if size > MAX_ANCHOR_BYTES:
            return None, None
        entries.append(entry)
    body = {"schema_version": BLOCK_ANCHOR_VERSION, "input_ir_sha256": plan.input_ir_sha256,
            "plan_sha256": plan.plan_sha256, "docx_sha256": docx_sha256,
            "entries": [entry.model_dump(mode="json") for entry in entries]}
    body["evidence_sha256"] = content_hash(body)
    if not _bounded_json(body):
        return None, None
    evidence = BlockAnchorEvidence.model_validate(body)
    ownership = _BlockAnchorOwnership(plan.input_ir_sha256, plan.plan_sha256, docx_sha256,
                                     tuple(_entry_identity(entry) for entry in entries))
    return evidence, ownership


def _plain_marker(node: Any, *, start: bool) -> bool:
    expected = {qn("w:id"), qn("w:name")} if start else {qn("w:id")}
    return (set(node.attrib) == expected and len(node) == 0
            and not (node.text or "").strip() and not (node.tail or "").strip())


def _paragraph_projection(root: Any, paragraph: Any) -> list[Any]:
    """RND-503 兼容投影只忽略合法成对新 marker，不忽略 run 或内容。"""
    children = list(paragraph)
    generic = [node for node in children if node.tag == qn("w:bookmarkStart")
               and ANCHOR_NAME_RE.fullmatch(node.get(qn("w:name"), ""))]
    ignored = set()
    for start in generic:
        identity = start.get(qn("w:id"))
        starts = [node for node in root.iter(qn("w:bookmarkStart")) if node.get(qn("w:id")) == identity]
        ends = [node for node in root.iter(qn("w:bookmarkEnd")) if node.get(qn("w:id")) == identity]
        names = [node for node in root.iter(qn("w:bookmarkStart")) if node.get(qn("w:name")) == start.get(qn("w:name"))]
        if (identity is None or not identity.isdecimal() or len(starts) != 1 or len(ends) != 1
                or len(names) != 1 or ends[0] not in children or children.index(start) >= children.index(ends[0])
                or not _plain_marker(start, start=True) or not _plain_marker(ends[0], start=False)):
            raise ValueError("通用书签配对无效")
        ignored.update((start, ends[0]))
    return [node for node in children if node.tag != qn("w:pPr") and node not in ignored]


def validate_block_anchor_evidence(value: Any, *, plan: RenderPlan, block_evidence: BlockRenderEvidence,
                                   word_content: bytes, ownership: _BlockAnchorOwnership | None = None) -> BlockAnchorEvidence | None:
    """可选证明失败仅返回不可用；调用方须先认证原主件及内容报告。"""
    if value is None:
        return None
    try:
        raw = value.model_dump(mode="json") if isinstance(value, BlockAnchorEvidence) else value
        if (not isinstance(raw, dict) or raw.get("schema_version") != BLOCK_ANCHOR_VERSION
                or not isinstance(raw.get("entries"), list) or len(raw["entries"]) > MAX_ANCHOR_ENTRIES
                or not _bounded_json(raw)):
            return None
        proof = BlockAnchorEvidence.model_validate(raw)
        if (proof.input_ir_sha256 != plan.input_ir_sha256 or proof.plan_sha256 != plan.plan_sha256
                or proof.docx_sha256 != hashlib.sha256(word_content).hexdigest()
                or proof.docx_sha256 != block_evidence.docx_sha256
                or proof.evidence_sha256 != content_hash(proof.model_dump(mode="json", exclude={"evidence_sha256"}))):
            return None
        if ownership is not None and (not isinstance(ownership, _BlockAnchorOwnership) or (ownership.input_ir_sha256, ownership.plan_sha256, ownership.docx_sha256)
                != (proof.input_ir_sha256, proof.plan_sha256, proof.docx_sha256)
                or ownership.entries != tuple(_entry_identity(entry) for entry in proof.entries)):
            return None
        index = PackageIndex(word_content)
        records = {record.block_id: record for record in block_evidence.block_render_map}
        starts, ends, names = {}, {}, {}
        for root in index.roots.values():
            for node in root.iter():
                if node.tag == qn("w:bookmarkStart"):
                    starts.setdefault(node.get(qn("w:id")), []).append(node)
                    names.setdefault(node.get(qn("w:name")), []).append(node)
                elif node.tag == qn("w:bookmarkEnd"):
                    ends.setdefault(node.get(qn("w:id")), []).append(node)
        seen = set()
        for entry in proof.entries:
            record = records.get(entry.block_id)
            if (entry.block_id in seen or record is None or record.disposition != "rendered"
                    or entry.anchor_ref != record.anchor_ref or entry.bookmark_name != block_bookmark_name(entry.anchor_ref)
                    or not ANCHOR_NAME_RE.fullmatch(entry.bookmark_name)):
                return None
            seen.add(entry.block_id)
            if not any((target.part, target.child_path, target.role, target.item_index)
                       == (entry.target.part, entry.target.child_path, entry.target.role, entry.target.item_index)
                       for target in record.targets if target.role != "toc_representative"):
                return None
            locators = (entry.start, entry.end, entry.target)
            if (len({locator.part for locator in locators}) != 1
                    or any(any(type(i) is not int or i < 0 for i in locator.child_path) for locator in locators)):
                return None
            start, end, target = [index.nodes[locator.part, tuple(locator.child_path)] for locator in locators]
            identity = start.get(qn("w:id"))
            if (start.tag != qn("w:bookmarkStart") or end.tag != qn("w:bookmarkEnd")
                    or start.get(qn("w:name")) != entry.bookmark_name or identity is None or not identity.isdecimal()
                    or end.get(qn("w:id")) != identity or starts.get(identity) != [start]
                    or ends.get(identity) != [end] or names.get(entry.bookmark_name) != [start]
                    or not _plain_marker(start, start=True) or not _plain_marker(end, start=False)):
                return None
            paragraph = start.getparent()
            if paragraph is not end.getparent() or paragraph.tag != qn("w:p"):
                return None
            children = list(paragraph)
            if children.index(start) >= children.index(end):
                return None
            if target.tag == qn("w:drawing"):
                run = next(target.iterancestors(qn("w:r")), None)
                if (run is None or run.getparent() is not paragraph
                        or children[children.index(start) + 1:children.index(end)] != [run]):
                    return None
            elif target.tag == qn("w:tbl"):
                if next(target.iter(qn("w:p")), None) is not paragraph:
                    return None
            elif target is not paragraph:
                return None
        return proof
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, UnicodeError, RecursionError):
        return None
