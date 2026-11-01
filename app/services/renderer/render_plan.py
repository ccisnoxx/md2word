"""渲染前确定的 JSON 计划与正式 writer 共用的纯策略。"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.services.document_ir.models import DocumentIR
from app.services.renderer.layout_plan import LayoutPlan, LayoutRegion, build_image_plan, image_annotations, split_two_col_blocks
from app.services.renderer.semantic_text import (
    infer_heading_level, is_list_item_text, is_toc_title_text, looks_like_heading_text, parse_toc_entry_text,
)
from app.services.renderer.template_config import TemplateConfigPackage

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

POLICY_VERSION = "word-renderer-policy/v1"


def canonical_bytes(value: Any) -> bytes:
    """内容身份不含运行时路径、时间或对象身份。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def legacy_document_ir_payload(document_ir: DocumentIR, *, mode="json") -> dict:
    """历史输入未声明的 TAB 默认扩展不进入原 v1 身份；显式存在的字段仍保留。"""
    value = document_ir.model_dump(mode=mode)
    for field, default in (("table_references_version", None), ("table_placeholders_version", None),
                           ("table_placeholders", [])):
        if field not in document_ir.metadata.model_fields_set and value["metadata"].get(field) == default:
            value["metadata"].pop(field, None)
    return value


def document_ir_hash(document_ir: DocumentIR, *, legacy: bool = False) -> str:
    """有限 IR 沿用原身份；历史非有限值以带类型的无损表示隔离，不写回 IR。"""
    value = legacy_document_ir_payload(document_ir, mode="python") if legacy else document_ir.model_dump(mode="python")
    def has_nonfinite(item):
        if isinstance(item, float):
            return not math.isfinite(item)
        if isinstance(item, dict):
            return any(has_nonfinite(child) for child in item.values())
        return isinstance(item, (list, tuple)) and any(has_nonfinite(child) for child in item)
    if not has_nonfinite(value):
        return content_hash(legacy_document_ir_payload(document_ir) if legacy else document_ir.model_dump(mode="json"))
    def typed(item):
        if isinstance(item, dict):
            return ["object", [[key, typed(child)] for key, child in sorted(item.items())]]
        if isinstance(item, (list, tuple)):
            return ["array", [typed(child) for child in item]]
        if isinstance(item, float):
            if math.isnan(item):
                return ["nonfinite", "nan"]
            if math.isinf(item):
                return ["nonfinite", "positive_infinity" if item > 0 else "negative_infinity"]
            return ["float", item]
        if item is None:
            return ["null"]
        if isinstance(item, bool):
            return ["boolean", item]
        return ["integer" if isinstance(item, int) else "string", item]
    return content_hash(["document-ir-nonfinite/v1", typed(value)])


class RenderContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def _json_contract(self):
        canonical_bytes(self.model_dump(mode="json"))
        return self


class ResourceIdentity(RenderContract):
    template_sha256: Sha256 | None
    effective_config_sha256: Sha256
    symbol_rules_sha256: Sha256 | None
    logo_sha256: Sha256 | None
    document_language: str


class TextPolicy(RenderContract):
    mode: Literal["paragraph", "heading", "bullet", "toc_title", "toc", "coalesced", "table_context", "formula"]
    style_group: str
    heading_level: int | None = None
    representative_block_id: str | None = None
    representative_item_index: int | None = None


class RenderDecision(RenderContract):
    decision_id: str
    block_id: str
    block_type: Literal["heading", "paragraph", "list", "formula", "table", "image"]
    order: int
    role: Literal["body", "page_header", "page_footer", "page_number"]
    source_page_index: int | None
    section_id: str | None = None
    region_id: str | None = None
    mode: Literal["native_text", "native_table", "table_expanded", "table_fallback", "native_image", "image_pair", "decoration", "unassigned"] = "unassigned"
    text_policies: list[TextPolicy] = Field(default_factory=list)
    style_group: str = "inherit"
    named_style: str | None = None
    page_break_before: bool = False
    keep_with_next: bool = False
    table_strategy: Literal["standard", "expanded", "fallback"] | None = None
    image_strategy: Literal["bbox_relative", "paired_tabs"] | None = None
    formula_strategy: Literal["omml_subset_or_text"] | None = None
    table_policy: dict[str, JsonValue] = Field(default_factory=dict)
    image_policy: dict[str, JsonValue] = Field(default_factory=dict)
    annotation_styles: list[str] = Field(default_factory=list)
    anchor_ref: str
    reason_codes: list[Literal["legacy_sequence", "layout_region", "image_pair", "decoration_joined", "semantic_page_break", "unassigned_layout"]] = Field(default_factory=list)


class RenderSection(RenderContract):
    section_id: str
    source_page_indices: list[int]
    orientation: Literal["portrait", "landscape", "inherit"]
    columns: Literal[1, 2, "inherit"]
    paper_policy: Literal["inherit_or_configured", "configured_or_a4"]
    start_kind: Literal["initial", "new_page", "continuous"]
    page_setup: dict[str, JsonValue]
    header_policy: Literal["linked_replace", "inherit"]
    footer_policy: Literal["linked_replace", "custom", "inherit"]


class RenderOperation(RenderContract):
    kind: Literal["section", "configure_page", "decoration", "block", "image_pair", "column_break"]
    section_id: str
    block_ids: list[str] = Field(default_factory=list)
    source_page_index: int | None = None
    page_width: float | None = None
    landscape: bool = False
    start_kind: Literal["initial", "new_page", "continuous"] = "initial"
    columns: int = 1
    decoration_kind: Literal["header", "footer"] | None = None
    decoration_policy: Literal["replace", "disabled", "custom"] | None = None
    keep_with_next: bool = False


class RenderPlan(RenderContract):
    schema_version: Literal["render-plan/v1"] = "render-plan/v1"
    renderer_policy_version: Literal["word-renderer-policy/v1"] = POLICY_VERSION
    input_ir_sha256: Sha256
    resource_identity: ResourceIdentity
    layout_mode: Literal["legacy_v1_fallback", "layout_v2"]
    styles: dict[str, dict[str, JsonValue]]
    sections: list[RenderSection]
    decisions: list[RenderDecision]
    operations: list[RenderOperation]
    plan_sha256: Sha256

    @model_validator(mode="after")
    def _identity(self):
        if self.plan_sha256 != content_hash(self.model_dump(mode="json", exclude={"plan_sha256"})):
            raise ValueError("渲染计划身份不一致。")
        return self


class TableFragmentPlan(RenderContract):
    fragment_id: str
    block_id: str | None
    render_owner_block_id: str
    render_input_sha256: Sha256 | None
    render_fragment_id: str | None
    status: Literal["rendered", "header_only", "empty", "missing"]
    source_rows: list[int]
    retained_source_rows: list[int]
    output_rows: list[int]
    removed_header_rows: list[int] | None
    shared_header_rows: list[int] | None
    content_scope_id: str | None
    repeated_header_ref: str | None

    @model_validator(mode="after")
    def _ranges(self):
        for interval in (self.source_rows, self.retained_source_rows, self.output_rows,
                         self.removed_header_rows, self.shared_header_rows):
            if interval is not None and (len(interval) != 2 or not 0 <= interval[0] <= interval[1]):
                raise ValueError("ir_render_evidence:target_mismatch")
        if (self.source_rows[0] != 0 or self.retained_source_rows[1] != self.source_rows[1]
                or self.output_rows[1] - self.output_rows[0] != self.retained_source_rows[1] - self.retained_source_rows[0]
                or self.shared_header_rows != self.removed_header_rows
                or self.removed_header_rows != ([0, self.retained_source_rows[0]] if self.retained_source_rows[0] else None)):
            raise ValueError("ir_render_evidence:target_mismatch")
        return self


class TableAnnotationPlan(RenderContract):
    block_id: str
    field: Literal["captions", "footnotes"]
    item_index: int
    role: Literal["caption", "context", "note"]
    disposition: Literal["rendered", "coalesced"]
    representative_block_id: str | None = None
    representative_field: Literal["captions", "footnotes"] | None = None
    representative_item_index: int | None = None
    reason: Literal["table_annotation_coalesced"] | None = None


class TableUnitPlan(RenderContract):
    unit_id: str
    logical_group_id: str
    anchor_block_id: str
    member_block_ids: list[str]
    fragments: list[TableFragmentPlan]
    annotations: list[TableAnnotationPlan]


class RenderOperationV2(RenderOperation):
    kind: Literal["section", "configure_page", "decoration", "block", "image_pair", "column_break", "logical_table"]
    unit_id: str | None = None


class RenderPlanV2(RenderPlan):
    schema_version: Literal["render-plan/v2"] = "render-plan/v2"
    renderer_policy_version: Literal["word-renderer-policy/v2"] = "word-renderer-policy/v2"
    operations: list[RenderOperationV2]
    table_units: list[TableUnitPlan]


def read_render_plan(value: Any) -> RenderPlan | RenderPlanV2:
    """只按显式版本解析；旧 hash 域和模型字段不接纳新语义。"""
    raw = value.model_dump(mode="json") if isinstance(value, (RenderPlan, RenderPlanV2)) else value
    if not isinstance(raw, dict):
        raise ValueError("ir_render_evidence:invalid_contract")
    model = {"render-plan/v1": RenderPlan, "render-plan/v2": RenderPlanV2}.get(raw.get("schema_version"))
    if model is None:
        raise ValueError("ir_render_evidence:invalid_contract")
    return model.model_validate(raw)


def select_text_policy(text: str, *, list_item: bool = False, allow_heading_inference: bool = True) -> TextPolicy:
    """保留原自动文字分派优先级，writer 只执行这里选定的策略。"""
    if is_toc_title_text(text):
        return TextPolicy(mode="toc_title", style_group="toc_title")
    parsed = parse_toc_entry_text(text)
    if parsed is not None:
        level = max(1, min(infer_heading_level(parsed[0]) or 1, 3))
        return TextPolicy(mode="toc", style_group=f"toc_level{level}", heading_level=level)
    if list_item or is_list_item_text(text):
        return TextPolicy(mode="bullet", style_group="normal")
    if allow_heading_inference and looks_like_heading_text(text):
        level = max(1, min(infer_heading_level(text) or 1, 3))
        return TextPolicy(mode="heading", style_group=f"heading{level}", heading_level=level)
    return TextPolicy(mode="paragraph", style_group="normal")


def semantic_page_break_block_id(page) -> str | None:
    block = next((block for region in page.regions for block in region.blocks), None)
    if block is not None and (block.type == "heading" or block.type == "table" and block.captions
            or block.type == "paragraph" and block.metadata.get("annotation_role") == "table_context"):
        return block.id
    return None


def _build_render_plan_v1(document_ir: DocumentIR, *, layout_plan: LayoutPlan, effective_config: TemplateConfigPackage,
                      resource_identity: ResourceIdentity, table_strategies: dict[str, str] | None = None,
                      table_models: dict[str, Any] | None = None) -> RenderPlan:
    """在 Word 对象创建前冻结顺序、分节与策略；不修改源 IR。"""
    ids = [block.id for block in document_ir.blocks]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("ir_render_evidence:block_coverage_mismatch")
    config = effective_config
    if table_strategies is None:
        from app.services.renderer.table_renderer import prepare_table_input
        prepared = {block.id: prepare_table_input(block, effective_config) for block in document_ir.blocks if block.type == "table"}
        table_strategies = {key: value[1] for key, value in prepared.items()}
        table_models = {key: value[0] for key, value in prepared.items()}
    blocks_by_id = {block.id: block for block in document_ir.blocks}
    decisions = {block.id: RenderDecision(
        decision_id="render-decision:" + content_hash(["render-decision/v1", block.id]),
        block_id=block.id, block_type=block.type, order=block.order,
        role=block.layout.role if block.layout else "body",
        source_page_index=block.layout.page_index if block.layout and block.layout.page_index is not None else block.page_index,
        anchor_ref="render-block:" + content_hash(["render-block/v1", block.id]),
    ) for block in document_ir.blocks}
    sections, operations = [], []
    from app.services.renderer.image_evidence import IMAGE_GENERATION_POLICY, source_image_position
    spans = {block_id: span for span in build_image_plan(document_ir) for block_id in span.block_ids}
    source_blocks = sorted(document_ir.blocks, key=lambda block: block.order)
    consumed_images = set()
    legacy = layout_plan.mode == "legacy_v1_fallback"

    def section(page, *, columns=1, start="initial", landscape=False):
        section_id = f"section_{len(sections)}"
        sections.append(RenderSection(section_id=section_id, source_page_indices=[page.index],
            orientation="inherit" if legacy else "landscape" if landscape else "portrait", columns=columns if start == "continuous" else "inherit",
            paper_policy="inherit_or_configured" if legacy else "configured_or_a4",
            start_kind=start, page_setup=config.page_setup.model_dump(mode="json"),
            header_policy="linked_replace" if config.header.enabled else "inherit",
            footer_policy="custom" if config.footer.enabled and (config.footer.left_text or config.footer.right_text)
                else "linked_replace" if config.footer.enabled else "inherit"))
        operations.append(RenderOperation(kind="section", section_id=section_id, start_kind=start, columns=columns))
        return section_id

    current = None
    previous_landscape = False
    for page_index, page in enumerate(layout_plan.pages):
        landscape = page.width is not None and page.height is not None and page.width > page.height
        if current is None or not legacy and landscape != previous_landscape:
            current = section(page, start="initial" if current is None else "new_page", landscape=landscape)
        elif page.index not in sections[-1].source_page_indices:
            sections[-1].source_page_indices.append(page.index)
        if not legacy:
            operations.append(RenderOperation(kind="configure_page", section_id=current,
                source_page_index=page.index, landscape=landscape))
            for kind, blocks, enabled, custom in (
                ("header", page.header_blocks, config.header.enabled, False),
                ("footer", page.footer_blocks + page.page_number_blocks, config.footer.enabled,
                 bool(config.footer.left_text or config.footer.right_text)),
            ):
                if blocks:
                    operations.append(RenderOperation(kind="decoration", section_id=current, block_ids=[b.id for b in blocks],
                        decoration_kind=kind, decoration_policy="disabled" if not enabled else "custom" if custom else "replace"))
                    for block in blocks:
                        decisions[block.id].mode = "decoration"
                        decisions[block.id].section_id = current
                        decisions[block.id].style_group = kind
                        decisions[block.id].reason_codes = ["decoration_joined"]
        break_id = semantic_page_break_block_id(page) if not legacy and page_index > 0 and landscape == previous_landscape else None
        # 复用 RND-503 的实际调度：仅抽出确认组或与原生栏读序冲突的 span。
        regions = list(enumerate(page.regions))
        if not legacy:
            body_ids = {block.id for region in page.regions for block in region.blocks}
            source_images = [block.id for block in source_blocks if block.id in body_ids and block.type == "image"]
            native_images = []
            for region in page.regions:
                left, right = split_two_col_blocks(region.blocks) if region.kind == "two_col" else (region.blocks, [])
                native_images.extend(block.id for block in [*left, *right] if block.type == "image")
            source_positions = {block_id: index for index, block_id in enumerate(source_images)}
            positions = [source_positions[block_id] for block_id in native_images]
            suffix_min = [len(positions)] * (len(positions) + 1)
            for index in range(len(positions) - 1, -1, -1):
                suffix_min[index] = min(positions[index], suffix_min[index + 1])
            overlay_spans, prefix_max = set(), -1
            for index, block_id in enumerate(native_images):
                span = spans[block_id]
                if (positions[index] < prefix_max or positions[index] > suffix_min[index + 1]
                        or span.mode == "group" and IMAGE_GENERATION_POLICY == "grouped/v1"):
                    overlay_spans.add(span.id)
                prefix_max = max(prefix_max, positions[index])
            overlay_ids = {block_id for block_id in source_images if spans[block_id].id in overlay_spans}
            if overlay_ids:
                regions, pending = [], set()
                def flush_pending():
                    for region_index, region in enumerate(page.regions):
                        blocks = [block for block in region.blocks if block.id in pending]
                        if blocks:
                            regions.append((region_index, LayoutRegion(region.kind, blocks)))
                    pending.clear()
                for block in source_blocks:
                    if block.id not in body_ids:
                        continue
                    if block.id in overlay_ids:
                        flush_pending()
                        regions.append((-1, LayoutRegion("one_col", [block])))
                    else:
                        pending.add(block.id)
                flush_pending()
        for region_index, region in regions:
            if region.kind == "two_col":
                current = section(page, columns=2, start="continuous", landscape=landscape)
                left, right = split_two_col_blocks(region.blocks)
                ordered = [*left, None, *right]
            else:
                ordered = region.blocks
            for block in region.blocks:
                if block.type == "image" and block.id in consumed_images:
                    continue
                decision = decisions[block.id]
                decision.section_id, decision.region_id = current, f"page_{page.index}_region_{region_index}"
                decision.page_break_before = block.id == break_id
                decision.keep_with_next = block.type == "heading" or block.metadata.get("annotation_role") == "table_context"
                decision.reason_codes = ["legacy_sequence" if legacy else "layout_region"]
                if decision.page_break_before:
                    decision.reason_codes.append("semantic_page_break")
                if block.type == "table":
                    strategy = table_strategies[block.id]
                    decision.table_strategy = strategy
                    decision.mode = {"standard": "native_table", "expanded": "table_expanded", "fallback": "table_fallback"}[strategy]
                    decision.style_group, decision.named_style = "table_content", config.table_style.style_name
                    from app.services.renderer.table_renderer import table_annotation_style, table_config_for_columns
                    captions = list(dict.fromkeys(text.strip() for text in block.captions if text.strip()))
                    decision.annotation_styles = [table_annotation_style(text) for text in captions]
                    decision.annotation_styles.extend("table_note" for text in dict.fromkeys(text.strip() for text in block.footnotes if text.strip()))
                    model = (table_models or {}).get(block.id)
                    if model is not None:
                        decision.table_policy = {"row_count": len(model.rows), "column_count": model.max_columns,
                            "content_style": table_config_for_columns(config, model.max_columns).table_content.model_dump(mode="json"),
                            "width_strategy": "five_column_weighted" if model.max_columns == 5 else "equal_or_minimum",
                            "repeat_first_row": True, "cant_split_rows": True}
                elif block.type == "image":
                    decision.mode, decision.image_strategy = "native_image", "bbox_relative"
                    decision.style_group = "caption"
                    decision.annotation_styles = ["caption"] * len(image_annotations(block))
                    decision.image_policy = {"width_strategy": "bbox_relative_with_column_cap", "source_page_width": page.width,
                        "bbox": source_image_position(block)["bbox"], "annotation_count": len(decision.annotation_styles),
                        "generation_policy": IMAGE_GENERATION_POLICY, "span_id": spans[block.id].id, "planned_mode": spans[block.id].mode}
                else:
                    decision.mode = "native_text"
            for block in ordered:
                if block is not None and block.type == "image":
                    if block.id in consumed_images:
                        continue
                    span = spans[block.id]
                    block_ids = list(span.block_ids) if span.mode == "group" and IMAGE_GENERATION_POLICY == "grouped/v1" else [block.id]
                    for block_id in block_ids:
                        decision = decisions[block_id]
                        decision.section_id, decision.region_id = current, f"page_{page.index}_region_{region_index}"
                    consumed_images.update(block_ids)
                else:
                    block_ids = [] if block is None else [block.id]
                operations.append(RenderOperation(kind="column_break" if block is None else "block", section_id=current,
                    block_ids=block_ids, page_width=page.width))
            if region.kind == "two_col":
                current = section(page, start="continuous", landscape=landscape)
        previous_landscape = landscape
    for operation in operations:
        if operation.kind == "block" and len(operation.block_ids) > 1:
            first = decisions[operation.block_ids[0]]
            for block_id in operation.block_ids[1:]:
                block = blocks_by_id[block_id]
                decision = decisions[block_id]
                decision.mode, decision.image_strategy, decision.style_group = "native_image", "bbox_relative", "caption"
                decision.annotation_styles = ["caption"] * len(image_annotations(block))
                decision.image_policy = {**first.image_policy, "bbox": source_image_position(block)["bbox"],
                    "annotation_count": len(decision.annotation_styles)}
                decision.reason_codes = list(first.reason_codes)
    representative = None
    for operation in operations:
        if operation.kind != "block":
            continue
        block = blocks_by_id[operation.block_ids[0]]
        decision = decisions[block.id]
        if block.type == "heading":
            level = max(1, min(block.level or 1, 3))
            policies = [TextPolicy(mode="heading", style_group=f"heading{level}", heading_level=level)]
        elif block.type == "formula":
            policies = [TextPolicy(mode="formula", style_group="normal")]
            decision.formula_strategy = "omml_subset_or_text"
        elif block.type in {"paragraph", "list"}:
            texts = block.list_items or [] if block.type == "list" else [block.text or ""]
            policies = [select_text_policy(text, list_item=block.type == "list", allow_heading_inference=document_ir.schema_version == "document-ir/v1") for text in texts]
            # table_context 原实现先占用 TOC 槽位，再采用 context 样式；保持该顺序。
            for index, policy in enumerate(policies):
                if policy.mode == "toc":
                    if representative is not None:
                        policy.mode = "coalesced"
                        policy.representative_block_id, policy.representative_item_index = representative
                    else:
                        representative = (block.id, index)
                if block.type == "paragraph" and block.metadata.get("annotation_role") == "table_context" and policy.mode != "coalesced":
                    policy.mode, policy.style_group = "table_context", "normal"
        else:
            policies = []
        decision.text_policies = policies
        if policies:
            decision.style_group = policies[0].style_group
            style = getattr(config, decision.style_group)
            decision.named_style = config.heading_word_style_name_for_level(policies[0].heading_level) if policies[0].mode == "heading" else style.word_style_name
    for decision in decisions.values():
        if decision.mode == "unassigned":
            decision.reason_codes = ["unassigned_layout"]
    styles = {name: getattr(config, name).model_dump(mode="json") for name in (
        "normal", "heading1", "heading2", "heading3", "toc_title", "toc_level1", "toc_level2", "toc_level3",
        "table_content", "table_style", "table_note", "caption", "long_table_caption")}
    value = dict(input_ir_sha256=document_ir_hash(document_ir), resource_identity=resource_identity.model_dump(mode="json"),
        layout_mode=layout_plan.mode, styles=styles, sections=[s.model_dump(mode="json") for s in sections],
        decisions=[d.model_dump(mode="json") for d in decisions.values()], operations=[o.model_dump(mode="json") for o in operations],
        schema_version="render-plan/v1", renderer_policy_version=POLICY_VERSION)
    return RenderPlan.model_validate({**value, "plan_sha256": content_hash(value)})


def build_render_plan(document_ir: DocumentIR, *, layout_plan: LayoutPlan, effective_config: TemplateConfigPackage,
                      resource_identity: ResourceIdentity, table_strategies: dict[str, str] | None = None,
                      table_models: dict[str, Any] | None = None, logical_table_plan=None) -> RenderPlanV2:
    """保留原普通调度，以唯一 unit 替换表操作；全部源 decision 保持一条。"""
    from dataclasses import replace
    from app.services.renderer.logical_table_plan import build_content_table_plan, table_unit_contracts
    tables = logical_table_plan or build_content_table_plan(document_ir, layout_plan)
    output_layout = replace(layout_plan, pages=tables.output_pages(layout_plan))
    original = _build_render_plan_v1(document_ir, layout_plan=output_layout, effective_config=effective_config,
        resource_identity=resource_identity, table_strategies=table_strategies, table_models=table_models)
    units = table_unit_contracts(document_ir, tables)
    anchors = {unit.anchor_block_id: unit for unit in units}
    decisions = {decision.block_id: decision for decision in original.decisions}
    sections = {section.section_id: section for section in original.sections}
    source_rank = {page.index: rank for rank, page in enumerate(layout_plan.pages)}
    operations = []
    for operation in original.operations:
        value = operation.model_dump(mode="json")
        unit = anchors.get(operation.block_ids[0]) if operation.kind == "block" else None
        if unit is not None:
            value.update(kind="logical_table", unit_id=unit.unit_id, block_ids=unit.member_block_ids)
            first = decisions[unit.anchor_block_id]
            for block_id in unit.member_block_ids:
                decision = decisions[block_id]
                decision.mode, decision.table_strategy = "native_table", "standard"
                decision.section_id, decision.region_id = first.section_id, first.region_id
            section = sections[first.section_id]
            native = next(value for value in tables.units if value.key == unit.unit_id)
            pages = {fragment.source.source_span.page_index for fragment in native.fragments
                     if fragment.source.source_span.page_index is not None}
            section.source_page_indices = sorted(set(section.source_page_indices) | pages,
                key=lambda page: (source_rank.get(page, len(source_rank)), page))
        operations.append(RenderOperationV2.model_validate(value))
    value = original.model_dump(mode="json", exclude={"plan_sha256"})
    value.update(schema_version="render-plan/v2", renderer_policy_version="word-renderer-policy/v2",
        sections=[section.model_dump(mode="json") for section in sections.values()],
        decisions=[decision.model_dump(mode="json") for decision in decisions.values()],
        operations=[operation.model_dump(mode="json") for operation in operations],
        table_units=[unit.model_dump(mode="json") for unit in units])
    return RenderPlanV2.model_validate({**value, "plan_sha256": content_hash(value)})
