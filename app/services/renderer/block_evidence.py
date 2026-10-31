"""单次输出点收集与最终包结构定位；临时 Word 引用不进入持久化合同。"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from lxml import etree
from docx.oxml.ns import qn
from pydantic import Field, JsonValue, model_validator

from app.services.document_ir.models import DocumentIR
from app.services.renderer.render_plan import RenderContract, RenderPlan, ResourceIdentity, Sha256, content_hash

if TYPE_CHECKING:
    from app.services.renderer.block_anchors import BlockAnchorEvidence, _BlockAnchorOwnership

Disposition = Literal["rendered", "coalesced", "suppressed", "superseded", "not_emitted"]
Reason = Literal["native_object", "empty_content", "empty_list", "toc_coalesced", "decoration_joined", "decoration_disabled", "custom_footer", "decoration_replaced", "unassigned_layout"]


class SourceProjection(RenderContract):
    status: Literal["verified_ir205", "legacy_layout", "unavailable"]
    logical_group_id: str | None = None
    fragment_ids: list[str] = Field(default_factory=list)
    source_spans: list[dict[str, JsonValue]] = Field(default_factory=list)
    page_index: int | None = None
    bbox: list[float | None] | None = None


class WordTarget(RenderContract):
    part: str
    child_path: list[int]
    element_kind: Literal["paragraph", "table", "drawing", "run", "bookmark", "math"]
    role: Literal["body", "list_item", "formula", "caption", "context", "table", "note", "image", "image_fallback", "header", "footer", "toc_representative"]
    item_index: int | None = None
    actual: dict[str, JsonValue]
    bookmark_names: list[str] = Field(default_factory=list)
    sharing_group: str | None = None
    participant_order: int | None = None


class ItemEvidence(RenderContract):
    item_index: int
    disposition: Literal["rendered", "coalesced"]
    representative_block_id: str | None = None
    representative_item_index: int | None = None


class BlockRenderRecord(RenderContract):
    block_id: str
    decision_id: str
    anchor_ref: str
    provenance: SourceProjection
    disposition: Disposition
    reason_code: Reason
    content_visible: bool
    representative_block_id: str | None = None
    replacement_block_id: str | None = None
    items: list[ItemEvidence] = Field(default_factory=list)
    targets: list[WordTarget] = Field(default_factory=list)
    bookmark_name: str | None = None
    word_page: None = None


class BlockRenderEvidence(RenderContract):
    schema_version: Literal["block-render-evidence/v1"] = "block-render-evidence/v1"
    input_ir_sha256: Sha256
    resource_identity: ResourceIdentity
    plan_sha256: Sha256
    docx_sha256: Sha256
    complete: bool
    block_render_map: list[BlockRenderRecord]
    counts: dict[str, int]


class TableRowsScope(RenderContract):
    scope_id: str
    unit_id: str
    block_id: str
    part: str
    table_child_path: list[int]
    output_rows: list[int]
    row_child_paths: list[list[int]]
    first_paragraph_child_path: list[int]

    @model_validator(mode="after")
    def _row_range(self):
        if (len(self.output_rows) != 2 or not 0 <= self.output_rows[0] < self.output_rows[1]
                or len(self.row_child_paths) != self.output_rows[1] - self.output_rows[0]):
            raise ValueError("ir_render_evidence:target_mismatch")
        return self


class WordTargetV2(WordTarget):
    element_kind: Literal["paragraph", "table", "drawing", "run", "bookmark", "math", "table_rows"]
    content_scope_id: str | None = None


class BlockRenderRecordV2(BlockRenderRecord):
    reason_code: Literal["native_object", "empty_content", "empty_list", "toc_coalesced", "decoration_joined",
        "decoration_disabled", "custom_footer", "decoration_replaced", "unassigned_layout", "table_fragment_rows",
        "table_header_coalesced", "table_annotation_coalesced", "table_fragment_missing"]
    targets: list[WordTargetV2] = Field(default_factory=list)


class TableUnitEvidence(RenderContract):
    unit_id: str
    table_target: WordTarget


class BlockRenderEvidenceV2(BlockRenderEvidence):
    schema_version: Literal["block-render-evidence/v2"] = "block-render-evidence/v2"
    block_render_map: list[BlockRenderRecordV2]
    content_scopes: list[TableRowsScope]
    table_units: list[TableUnitEvidence]


def read_block_render_evidence(value: Any) -> BlockRenderEvidence | BlockRenderEvidenceV2:
    """版本和容量在持久化边界一次认证，未知版本不能伪装 v1。"""
    raw = value.model_dump(mode="json") if isinstance(value, (BlockRenderEvidence, BlockRenderEvidenceV2)) else value
    if not isinstance(raw, dict):
        raise ValueError("ir_render_evidence:invalid_contract")
    model = {"block-render-evidence/v1": BlockRenderEvidence,
             "block-render-evidence/v2": BlockRenderEvidenceV2}.get(raw.get("schema_version"))
    if model is None:
        raise ValueError("ir_render_evidence:invalid_contract")
    if model is BlockRenderEvidenceV2:
        from app.services.renderer.content_contract import validate_scope_budget
        validate_scope_budget(raw.get("content_scopes"))
    return model.model_validate(raw)


def resolve_table_scope(trace: BlockRenderEvidenceV2, content_scope_id: str) -> TableRowsScope:
    """导航只查询已认证 trace，不在此重建或认可待验归属。"""
    matches = [scope for scope in trace.content_scopes if scope.scope_id == content_scope_id]
    if len(matches) != 1:
        raise ValueError("ir_render_evidence:target_mismatch")
    return matches[0]


@dataclass(frozen=True, slots=True)
class _ImageOwnership:
    """RND-503 每图及其独立注释的同次写入位置，不从待验 trace 反推。"""

    block_id: str
    part: str
    targets: tuple[tuple[tuple[int, ...], str, str, int | None], ...]


@dataclass(frozen=True, slots=True)
class _TableOwnership:
    """本次 writer 捕获的表、行、注释事实；不能由序列化 trace 生成。"""
    unit_id: str
    part: str
    table_child_path: tuple[int, ...]
    scopes: tuple[tuple[str, str, tuple[tuple[int, ...], ...], tuple[int, ...]], ...]
    annotations: tuple[tuple[str, str, int, tuple[int, ...]], ...]


@dataclass(frozen=True, slots=True)
class _RenderOwnership:
    """collector 冻结的内部事实，禁止从 metadata/待验证 trace 重建。"""

    input_ir_sha256: str
    resource_identity_sha256: str
    plan_sha256: str
    docx_sha256: str
    images: tuple[_ImageOwnership, ...]
    tables: tuple[_TableOwnership, ...] = ()


@dataclass(frozen=True, slots=True)
class WordRenderResult:
    content: bytes
    plan: RenderPlan
    block_evidence: BlockRenderEvidence
    renderer_content_contract_version: str
    formula_source_coverage: dict[str, Any]
    _ownership: _RenderOwnership | None = field(default=None, repr=False)
    formula_report: dict[str, Any] | None = None
    image_layout_report: dict[str, Any] | None = None
    block_anchor_evidence: BlockAnchorEvidence | None = None
    _anchor_ownership: _BlockAnchorOwnership | None = field(default=None, repr=False)
    block_anchor_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class LocalTarget:
    """仅在本次 Document 生命周期内保留实际输出节点。"""
    element: Any
    part: Any
    role: str
    item_index: int | None = None
    sharing_group: str | None = None
    participant_order: int | None = None
    content_scope_id: str | None = None
    scope_table: Any | None = None
    scope_rows: tuple[Any, ...] = ()


def paragraph_target(paragraph, role="body", item_index=None):
    return LocalTarget(paragraph._p, paragraph.part, role, item_index)


KINDS = {qn("w:p"): "paragraph", qn("w:tbl"): "table", qn("w:drawing"): "drawing", qn("w:r"): "run", qn("w:bookmarkStart"): "bookmark", qn("m:oMath"): "math"}
PART_RE = re.compile(r"word/(?:document|header[0-9]+|footer[0-9]+)\.xml\Z")


def _walk(root):
    pending = [(root, ())]
    while pending:
        node, path = pending.pop()
        yield path, node
        pending.extend((child, (*path, index)) for index, child in reversed(list(enumerate(node))))


class PackageIndex:
    """一次解析包内可定位部件，section 引用从最终关系解析。"""
    def __init__(self, content: bytes):
        self.nodes, self.paths, self.roots = {}, {}, {}
        self.sections = []
        self.section_by_node = {}
        self.references = {}
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            for name in package.namelist():
                if PART_RE.fullmatch(name):
                    root = etree.fromstring(package.read(name))
                    self.roots[name] = root
                    for path, node in _walk(root):
                        self.nodes[name, path] = node
                        self.paths[node] = (name, path)
            relations = etree.fromstring(package.read("word/_rels/document.xml.rels"))
            targets = {r.get("Id"): r.get("Target") for r in relations}
        root = self.roots["word/document.xml"]
        sects = list(root.iter(qn("w:sectPr")))
        inherited = {}
        for index, sect in enumerate(sects):
            def attrs(tag):
                node = sect.find(qn(tag))
                return {etree.QName(k).localname: v for k, v in node.attrib.items()} if node is not None else {}
            size, margins, cols = attrs("w:pgSz"), attrs("w:pgMar"), attrs("w:cols")
            self.sections.append({"section_index": index, "orientation": size.get("orient", "portrait"),
                "columns": int(cols.get("num", "1")), "page_width_twips": int(size["w"]) if "w" in size else None,
                "page_height_twips": int(size["h"]) if "h" in size else None,
                "page_width_emu": int(size["w"]) * 635 if "w" in size else None,
                "page_height_emu": int(size["h"]) * 635 if "h" in size else None,
                "column_space_twips": int(cols["space"]) if "space" in cols else None,
                "margins_twips": {k: int(v) for k, v in margins.items()}})
            for kind in ("header", "footer"):
                for reference in sect.findall(qn(f"w:{kind}Reference")):
                    target = targets.get(reference.get(qn("r:id")))
                    if target:
                        name = target.lstrip("/") if target.startswith("/") else "word/" + target
                        if PART_RE.fullmatch(name):
                            inherited[kind, reference.get(qn("w:type"))] = name
                for (ref_kind, _), name in inherited.items():
                    if ref_kind == kind:
                        self.references.setdefault(name, set()).add(index)
        body = root.find(qn("w:body"))
        section_index, pending = 0, []
        for child in body:
            pending.append(child)
            ending = child.tag == qn("w:sectPr") or child.find("./" + qn("w:pPr") + "/" + qn("w:sectPr")) is not None
            if ending:
                for item in pending:
                    for descendant in item.iter():
                        self.section_by_node[descendant] = section_index
                pending.clear()
                section_index += 1

    def project(self, part: str, path: tuple[int, ...]) -> tuple[str, dict, list[str]]:
        node = self.nodes.get((part, path))
        if node is None or node.tag not in KINDS:
            raise ValueError("ir_render_evidence:target_mismatch")
        paragraph = node if node.tag == qn("w:p") else next((x for x in node.iterancestors() if x.tag == qn("w:p")), None)
        section_indices = sorted(self.references.get(part, ())) if part != "word/document.xml" else [self.section_by_node[node]]
        style = paragraph.find("./" + qn("w:pPr") + "/" + qn("w:pStyle")) if paragraph is not None else None
        if node.tag == qn("w:tbl"):
            style = node.find("./" + qn("w:tblPr") + "/" + qn("w:tblStyle"))
        dimensions = []
        for extent in node.iter(qn("wp:extent")):
            dimensions.append({"width_emu": int(extent.get("cx")), "height_emu": int(extent.get("cy"))})
        actual = {"referenced_section_indices": section_indices, "sections": [self.sections[x] for x in section_indices],
            "style_id": style.get(qn("w:val")) if style is not None else "inherit",
            "dimensions": dimensions, "math_object_count": len(list(node.iter(qn("m:oMath")))), "xml_sha256": hashlib.sha256(etree.tostring(node)).hexdigest()}
        if node.tag == qn("w:tbl"):
            width = node.find("./" + qn("w:tblPr") + "/" + qn("w:tblW"))
            actual["table_dimensions"] = {"rows": len(node.findall(qn("w:tr"))),
                "grid_columns": len(node.findall("./" + qn("w:tblGrid") + "/" + qn("w:gridCol"))),
                "width_twips": int(width.get(qn("w:w"))) if width is not None and width.get(qn("w:type")) == "dxa" else None}
        if paragraph is not None:
            actual["direct_formatting"] = [
                {"tag": etree.QName(child).localname,
                 "attributes": {etree.QName(k).localname: v for k, v in child.attrib.items()}}
                for properties in paragraph.findall(qn("w:pPr")) for child in properties
                if child.tag in {qn("w:spacing"), qn("w:ind"), qn("w:jc"), qn("w:keepNext"), qn("w:pageBreakBefore")}]
            formatting = [
                {"tag": etree.QName(child).localname,
                 "attributes": {etree.QName(k).localname: v for k, v in child.attrib.items()}}
                for properties in node.iter(qn("w:rPr")) for child in properties
                if child.tag in {qn("w:rFonts"), qn("w:sz"), qn("w:b"), qn("w:i"), qn("w:color")}]
            # 实际格式按有限变体计数，避免把每个表格单元格的重复样式再存一份。
            variants = {}
            for value in formatting:
                identity = content_hash(value)
                if identity not in variants:
                    variants[identity] = {**value, "count": 0}
                variants[identity]["count"] += 1
            actual["run_formatting"] = list(variants.values())
            actual["page_break_before"] = paragraph.find("./" + qn("w:pPr") + "/" + qn("w:pageBreakBefore")) is not None
            actual["keep_with_next"] = paragraph.find("./" + qn("w:pPr") + "/" + qn("w:keepNext")) is not None
        bookmarks = [x.get(qn("w:name")) for x in node.iter(qn("w:bookmarkStart"))]
        return KINDS[node.tag], actual, bookmarks


def provenance_for(document_ir: DocumentIR):
    from app.services.renderer.image_evidence import source_image_position
    result = {}
    for block in document_ir.blocks:
        layout = block.layout
        result[block.id] = SourceProjection(status="legacy_layout" if layout else "unavailable",
            page_index=layout.page_index if layout and layout.page_index is not None else block.page_index,
            bbox=source_image_position(block)["bbox"])
    if document_ir.metadata.logical_table_groups_version is not None:
        from app.services.document_ir.logical_table_group import validate_logical_table_groups
        validate_logical_table_groups(document_ir)
        for group in document_ir.metadata.logical_table_groups:
            for fragment in group.fragments:
                owner = fragment.render_owner_block_id
                if owner not in result:
                    raise ValueError("ir_render_evidence:block_coverage_mismatch")
                source = result[owner]
                source.status, source.logical_group_id = "verified_ir205", group.logical_group_id
                source.fragment_ids.append(fragment.fragment_id)
                # 自由 metadata.source_spans 不进入 verified 投影。
                source.source_spans.append(fragment.source_span.model_dump(mode="json"))
    return result


class RenderCollector:
    """当前调用独占；真实段落清空时撤销同一物理元素的旧贡献。"""
    def __init__(self, document_ir: DocumentIR, plan: RenderPlan):
        from app.services.document_ir.integrity import is_visible_body_block
        provenance = provenance_for(document_ir)
        visible = {b.id: is_visible_body_block(b) for b in document_ir.blocks}
        self.v2 = plan.schema_version == "render-plan/v2"
        record_model = BlockRenderRecordV2 if self.v2 else BlockRenderRecord
        self.records = {d.block_id: record_model(block_id=d.block_id, decision_id=d.decision_id,
            anchor_ref=d.anchor_ref, provenance=provenance[d.block_id], disposition="not_emitted",
            reason_code="unassigned_layout", content_visible=visible[d.block_id]) for d in plan.decisions}
        self.targets = {key: [] for key in self.records}
        self.decoration_owners = {}
        self.representatives = {}
        self.images: list[tuple[str, tuple[LocalTarget, ...]]] = []
        self.tables = []
        self.created_anchors = []
        self.block_anchor_counts = {}

    def add(self, block_id, targets):
        self.targets[block_id].extend(targets)
        record = self.records[block_id]
        record.disposition = "rendered"
        record.reason_code = "native_object" if record.content_visible else "empty_content"

    def replace_decoration(self, blocks, paragraph, kind):
        key = (paragraph.part, paragraph._p)
        old = self.decoration_owners.get(key, [])
        for block_id in old:
            self.targets[block_id] = []
            record = self.records[block_id]
            record.disposition, record.reason_code = "superseded", "decoration_replaced"
            record.replacement_block_id = blocks[0]
        group = "decoration:" + content_hash([kind, blocks])
        for index, block_id in enumerate(blocks):
            target = paragraph_target(paragraph, kind)
            target.sharing_group, target.participant_order = group, index
            self.add(block_id, [target])
            self.records[block_id].reason_code = "decoration_joined"
        self.decoration_owners[key] = blocks

    def freeze(self, document, content: bytes, plan: RenderPlan) -> tuple[BlockRenderEvidence, _RenderOwnership, BlockAnchorEvidence | None, _BlockAnchorOwnership | None]:
        index = PackageIndex(content)
        live_paths = {}
        for part in document.part.package.parts:
            name = str(part.partname).lstrip("/")
            if PART_RE.fullmatch(name) and hasattr(part, "element"):
                for path, node in _walk(part.element):
                    live_paths[part, node] = (name, path)
        # 独立边界由真实逐图 writer 捕获，完整 paragraph 自然涵盖其所有 OMML。
        images = []
        for block_id, targets in self.images:
            locations = [live_paths[target.part, target.element] for target in targets]
            part = locations[0][0]
            if any(name != part for name, _ in locations):
                raise ValueError("ir_render_evidence:target_mismatch")
            frozen = tuple((path, index.project(part, path)[0], target.role, target.item_index)
                for target, (_, path) in zip(targets, locations, strict=True))
            images.append(_ImageOwnership(block_id, part, frozen))
        scopes, table_units, tables = [], [], []
        for unit_id, table, part, local_scopes, annotations in self.tables:
            name, table_path = live_paths[part, table]
            kind, actual, bookmarks = index.project(name, table_path)
            table_units.append(TableUnitEvidence(unit_id=unit_id,
                table_target=WordTarget(part=name, child_path=list(table_path), element_kind=kind,
                    role="table", actual=actual, bookmark_names=bookmarks)))
            frozen_scopes = []
            direct_rows = table.findall(qn("w:tr"))
            for block_id, target in local_scopes:
                row_paths = [live_paths[part, row][1] for row in target.scope_rows]
                positions = [direct_rows.index(row) for row in target.scope_rows]
                if positions != list(range(positions[0], positions[-1] + 1)):
                    raise ValueError("ir_render_evidence:target_mismatch")
                first_path = live_paths[part, target.element][1]
                scopes.append(TableRowsScope(scope_id=target.content_scope_id, unit_id=unit_id, block_id=block_id,
                    part=name, table_child_path=list(table_path), output_rows=[positions[0], positions[-1] + 1],
                    row_child_paths=[list(path) for path in row_paths], first_paragraph_child_path=list(first_path)))
                frozen_scopes.append((target.content_scope_id, block_id, tuple(row_paths), first_path))
            frozen_annotations = tuple((block_id, field_name, item, live_paths[target.part, target.element][1])
                for block_id, field_name, item, target in annotations)
            tables.append(_TableOwnership(unit_id, name, table_path, tuple(frozen_scopes), frozen_annotations))
        docx_sha256 = hashlib.sha256(content).hexdigest()
        ownership = _RenderOwnership(plan.input_ir_sha256, content_hash(plan.resource_identity.model_dump(mode="json")),
            plan.plan_sha256, docx_sha256, tuple(images), tuple(tables))
        for block_id, targets in self.targets.items():
            for target in targets:
                if target.content_scope_id is not None:
                    from app.services.renderer.content_contract import project_table_scope
                    scope = next(scope for scope in scopes if scope.scope_id == target.content_scope_id)
                    actual, bookmarks = project_table_scope(index, scope)
                    self.records[block_id].targets.append(WordTargetV2(part=scope.part,
                        child_path=scope.table_child_path, element_kind="table_rows", role="table",
                        actual=actual, bookmark_names=bookmarks, content_scope_id=scope.scope_id))
                    continue
                locator = live_paths.get((target.part, target.element))
                if locator is None:
                    raise ValueError("ir_render_evidence:target_mismatch")
                name, path = locator
                kind, actual, bookmarks = index.project(name, path)
                target_model = WordTargetV2 if self.v2 else WordTarget
                self.records[block_id].targets.append(target_model(part=name, child_path=list(path), element_kind=kind,
                    role=target.role, item_index=target.item_index, actual=actual, bookmark_names=bookmarks,
                    sharing_group=target.sharing_group, participant_order=target.participant_order))
        # TOC 合并引用真实代表，不按文字或 block ID 猜 OOXML 位置。
        for block_id, representative, item_index, representative_item_index in self.representatives.values():
            record = self.records[block_id]
            targets = [t for t in self.records[representative].targets if t.item_index == representative_item_index and t.role != "toc_representative"]
            if not targets:
                raise ValueError("ir_render_evidence:target_mismatch")
            record.targets.extend(t.model_copy(update={"role": "toc_representative", "item_index": item_index}) for t in targets)
            record.representative_block_id = representative
            if not self.targets[block_id]:
                record.disposition, record.reason_code = "coalesced", "toc_coalesced"
        decisions = {decision.block_id: decision for decision in plan.decisions}
        for record in self.records.values():
            if decisions[record.block_id].text_policies:
                record.targets.sort(key=lambda target: target.item_index if target.item_index is not None else -1)
            names = list(dict.fromkeys(name for t in record.targets for name in t.bookmark_names))
            record.bookmark_name = names[0] if names else None
        counts = {state: sum(r.disposition == state for r in self.records.values()) for state in ("rendered", "coalesced", "suppressed", "superseded", "not_emitted")}
        counts.update(block_count=len(self.records), target_count=sum(len(r.targets) for r in self.records.values()))
        evidence_model = BlockRenderEvidenceV2 if self.v2 else BlockRenderEvidence
        extra = {"content_scopes": scopes, "table_units": table_units} if self.v2 else {}
        evidence = evidence_model(input_ir_sha256=plan.input_ir_sha256, resource_identity=plan.resource_identity,
            plan_sha256=plan.plan_sha256, docx_sha256=docx_sha256, complete=True,
            block_render_map=list(self.records.values()), counts=counts, **extra)
        if self.v2:
            from app.services.renderer.content_contract import validate_scope_budget
            validate_scope_budget([scope.model_dump(mode="json") for scope in scopes])
        from app.services.renderer.block_anchors import freeze_block_anchors
        anchors, anchor_ownership = (None, None) if self.block_anchor_counts.get("generation_disabled") else freeze_block_anchors(self.created_anchors, live_paths, plan, docx_sha256)
        if anchors is None and not self.block_anchor_counts.get("generation_disabled"):
            self.block_anchor_counts["limit_exceeded"] = 1
        return evidence, ownership, anchors, anchor_ownership
