"""正式任务与本地转换共用的渲染完整性证据构建，以及持久化主件的证据重建比对。"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from app.conversion.docx_rules.formula import content_math_spans, formula_block_span, sha256_text
from app.conversion.docx_rules.table_expansion import expanded_table_rows, requires_table_expansion
from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.integrity import build_source_integrity, is_visible_body_block
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.caption_reconciler import RULE_VERSION as CAPTION_RULE_VERSION
from app.services.renderer.docx_quality import (
    DOCX_QUALITY_VERSION,
    LITERAL_IDENTIFIER_RE,
    analyze_docx_quality_bytes,
    build_docx_quality_flags,
    validate_formula_report,
    verify_docx_formula_report,
)
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan, image_annotations
from app.services.renderer.image_evidence import verify_image_report
from app.services.renderer.render_evidence_validation import (
    ensure_renderer_integrity,
    render_contract_failure,
    validate_persisted_render_evidence,
    validate_render_result,
)


if TYPE_CHECKING:
    from app.services.renderer.block_anchors import BlockAnchorEvidence
    from app.services.renderer.block_evidence import BlockRenderEvidence, WordRenderResult
    from app.services.renderer.render_plan import RenderPlan

# 历史主件须逐项核对原aggregate合同，不能把新增trace或来源字段强加给旧件。
LEGACY_RENDERER_EVIDENCE_KEYS = frozenset({
    'schema_version',
    'renderer_mode',
    'layout_page_count',
    'layout_region_count',
    'layout_block_count',
    'expected_layout_block_count',
    'layout_block_count_delta',
    'layout_missing_block_ids',
    'layout_duplicate_block_ids',
    'layout_quality_flags',
    'source_integrity',
    'docx_quality',
    'quality_flags',
    'expected_inline_shape_count',
    'inline_shape_count',
    'inline_shape_count_delta',
    'expected_table_count',
    'table_count',
    'table_count_delta',
    'expected_heading_count',
    'heading_count',
    'heading_count_delta',
    'blocking_quality_flags',
})
_UNSET = object()


def build_renderer_metadata(document_ir: DocumentIR, layout_plan: LayoutPlan | None = None) -> dict[str, Any]:
    """构造产物和事件共用的布局证据，输入质量与执行完整性分开。"""

    resolved_layout_plan = layout_plan or build_layout_plan(document_ir)
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    layout_block_ids = [
        block.id for page in resolved_layout_plan.pages for region in page.regions for block in region.blocks
    ]
    expected_block_ids = [block.id for block in body_blocks]
    metadata = {
        "schema_version": document_ir.schema_version,
        "renderer_mode": resolved_layout_plan.mode,
        "layout_page_count": len(resolved_layout_plan.pages),
        "layout_region_count": sum(len(page.regions) for page in resolved_layout_plan.pages),
        "layout_block_count": sum(
            len(region.blocks) for page in resolved_layout_plan.pages for region in page.regions
        ),
        "expected_layout_block_count": len(expected_block_ids),
        "layout_block_count_delta": len(layout_block_ids) - len(expected_block_ids),
        "layout_missing_block_ids": sorted(set(expected_block_ids) - set(layout_block_ids)),
        "layout_duplicate_block_ids": sorted(
            block_id for block_id, count in Counter(layout_block_ids).items() if count > 1
        ),
        "layout_quality_flags": document_ir.quality_flags,
        "source_integrity": build_source_integrity(document_ir),
        "mineru_validation": (document_ir.metadata.mineru_validation.model_dump(mode="json")
                              if document_ir.metadata.mineru_validation is not None else None),
        "mineru_validation_input": document_ir.metadata.mineru_validation_input,
    }
    caption_blocks = [block for block in document_ir.blocks if not block.metadata.get("source_block_id")
                      and isinstance(block.metadata.get("caption_reconciliation"), dict)]
    if caption_blocks:
        statuses: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        binding_count = candidate_count = 0
        examples: list[dict[str, Any]] = []
        relation_examples: list[dict[str, Any]] = []
        for block in caption_blocks:
            caption = block.metadata["caption_reconciliation"]
            statuses[caption["status"]] += 1
            reasons.update(caption.get("reasons", []))
            binding_count += len(caption.get("bindings", []))
            candidate_count += len(caption.get("candidates", []))
            for kind in ("bindings", "candidates"):
                for receipt in caption.get(kind, []):
                    if len(relation_examples) < 40:
                        relation_examples.append({
                            "kind": kind, "donor_block_id": receipt["donor_block_id"],
                            "target_block_id": receipt["target_block_id"], "source_locator": receipt["source_locator"],
                            "rule_id": receipt["rule_id"], "evidence_only": receipt["evidence_only"],
                            "reasons": receipt.get("reasons", [receipt["reason"]] if "reason" in receipt else []),
                        })
            if len(examples) < 40:
                examples.append({
                    "block_id": block.id, "source_locator": block.metadata.get("mineru_source"),
                    "status": caption["status"], "reasons": caption.get("reasons", []),
                })
        # 摘要不复制 originals、rich runs 或可见文本；完整关系仍由 IR 主源块持有。
        metadata["caption_reconciliation"] = {
            "rule_version": CAPTION_RULE_VERSION, "block_count": len(caption_blocks),
            "status_counts": dict(sorted(statuses.items())), "reason_counts": dict(sorted(reasons.items())),
            "binding_count": binding_count, "candidate_count": candidate_count,
            "examples": examples, "omitted_example_count": len(caption_blocks) - len(examples),
            "relation_examples": relation_examples,
            "omitted_relation_count": binding_count + candidate_count - len(relation_examples),
        }
    return metadata



def build_renderer_aggregate_evidence(
    document_ir: DocumentIR,
    word_content: bytes,
    layout_plan: LayoutPlan | None = None,
    *,
    formula_report: dict[str, Any] | None = None,
    image_layout_report: dict[str, Any] | None = None,
    expected_template_version_id: str | None = None,
    expected_generation_policy: str | None = None,
    _table_plan=None,
    _formula_sources: list[dict[str, Any]] | None = None,
    _placeholder_count: int = 0,
    _v2_content: bool = False,
    _legacy_ir_identity: bool = False,
    _placeholder_ownership=None,
) -> dict[str, Any]:
    """生成 DOCX 证据；新报告严格核验，历史无报告保持原字段。"""

    evidence = build_renderer_metadata(document_ir, layout_plan)
    if image_layout_report is not None:
        from app.services.renderer.logical_table_plan import table_unit_contracts
        evidence["image_layout_summary"] = verify_image_report(document_ir, word_content, image_layout_report,
            expected_template_version_id=expected_template_version_id, expected_generation_policy=expected_generation_policy,
            _legacy_ir_identity=_legacy_ir_identity,
            _table_contracts=table_unit_contracts(document_ir, _table_plan) if _v2_content else None,
            _table_primary_block_ids={document_ir.blocks[unit.anchor_block_index].id
                for unit in _table_plan.units if unit.is_group_primary} if _v2_content else None,
            _placeholder_ownership=_placeholder_ownership)
        evidence["image_layout_report"] = image_layout_report
    literal_identifiers: set[str] = set()
    if formula_report is not None:
        summary = validate_formula_report(formula_report)
        reconstructed_sources = formula_source_inventory(document_ir, _literal_identifiers=literal_identifiers)
        expected_sources = reconstructed_sources if _formula_sources is None else _formula_sources
        recorded_sources = [entry["source"] for entry in formula_report["entries"]]
        if Counter(_binding_key(value) for value in expected_sources) != Counter(_binding_key(value) for value in recorded_sources):
            raise ValueError("公式报告与源 DocumentIR 不匹配")
        verify_docx_formula_report(word_content, formula_report)
        evidence["formula_report"] = formula_report
        evidence["formula_summary"] = summary
    annotation_anchors = frozenset(annotation["anchor"] for span in image_layout_report["spans"]
        for image in span["images"] for annotation in image["annotations"]) if image_layout_report is not None else frozenset()
    docx_quality = analyze_docx_quality_bytes(word_content, formula_report=formula_report,
        _verified_literal_identifiers=frozenset(literal_identifiers),
        _verified_image_annotation_anchors=annotation_anchors)
    if docx_quality:
        docx_quality["analysis_version"] = DOCX_QUALITY_VERSION
    evidence["docx_quality"] = docx_quality
    evidence["quality_flags"] = build_docx_quality_flags(docx_quality)
    if formula_report is not None and evidence["formula_summary"]["fallback_count"]:
        evidence["quality_flags"].append("formula_text_fallback")
    if image_layout_report is not None and evidence["image_layout_summary"]["uncertain_span_count"]:
        evidence["quality_flags"].append("image_group_uncertain")
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    expected_inline_shapes = sum(1 for block in body_blocks if block.type == "image") + _placeholder_count
    expected_tables = (sum(1 for block in body_blocks if block.type == "table")
                       if _table_plan is None else len(_table_plan.units))
    expected_headings = sum(1 for block in body_blocks if block.type == "heading")
    actual_inline_shapes = int(docx_quality.get("inline_shape_count") or 0)
    actual_tables = int(docx_quality.get("table_count") or 0)
    actual_headings = int(docx_quality.get("heading_paragraphs") or 0)
    evidence.update(
        {
            "expected_inline_shape_count": expected_inline_shapes,
            "inline_shape_count": actual_inline_shapes,
            "inline_shape_count_delta": actual_inline_shapes - expected_inline_shapes,
            "expected_table_count": expected_tables,
            "table_count": actual_tables,
            "table_count_delta": actual_tables - expected_tables,
            "expected_heading_count": expected_headings,
            "heading_count": actual_headings,
            "heading_count_delta": actual_headings - expected_headings,
        }
    )
    flags = list(evidence["source_integrity"]["blocking_quality_flags"])
    if evidence["layout_missing_block_ids"]:
        flags.append("ir_layout_integrity:missing_blocks")
    if evidence["layout_duplicate_block_ids"]:
        flags.append("ir_layout_integrity:duplicate_blocks")
    asset_ids = {asset.id for asset in document_ir.assets}
    if any(block.type == "image" and (not block.asset_ref or block.asset_ref not in asset_ids) for block in body_blocks):
        flags.append("ir_docx_integrity:image_asset_missing")
    if actual_inline_shapes != expected_inline_shapes:
        flags.append("ir_docx_integrity:inline_shape_count_mismatch")
    if image_layout_report is not None:
        layout_count = evidence["image_layout_summary"]["accepted_group_count"]
        content_count = actual_tables - layout_count
        evidence.update({"expected_layout_table_count": layout_count, "layout_table_count": layout_count,
                         "layout_table_count_delta": 0, "expected_content_table_count": expected_tables,
                         "content_table_count": content_count, "content_table_count_delta": content_count - expected_tables,
                         "expected_total_table_count": expected_tables + layout_count,
                         "total_table_count": actual_tables, "total_table_count_delta": actual_tables - expected_tables - layout_count})
        if content_count != expected_tables:
            flags.append("ir_docx_integrity:table_count_mismatch")
    elif actual_tables != expected_tables:
        flags.append("ir_docx_integrity:table_count_mismatch")
    if document_ir.schema_version == "document-ir/v2" and actual_headings != expected_headings:
        flags.append("ir_docx_integrity:heading_count_mismatch")
    evidence["blocking_quality_flags"] = list(dict.fromkeys(flags))
    return evidence


def _binding_key(binding: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(binding[key] for key in ("block_id", "field", "start", "end", "boundary", "source_sha256"))


def formula_source_inventory(document_ir: DocumentIR, *, _literal_identifiers: set[str] | None = None) -> list[dict[str, Any]]:
    """从权威 IR 重建公式源绑定；字面标识符只采集共享数学边界之外的整词。"""
    sources: list[dict[str, Any]] = []

    def add(block_id: str, field: str, text: str, *, formula: bool = False) -> None:
        spans = (formula_block_span(text),) if formula else content_math_spans(text)
        sources.extend({"block_id": block_id, "field": field, "start": span.start, "end": span.end, "boundary": span.boundary, "source_sha256": sha256_text(span.source)} for span in spans)
        if _literal_identifiers is not None:
            _literal_identifiers.update(match.group(0) for match in LITERAL_IDENTIFIER_RE.finditer(text)
                if not any(match.start() < span.end and span.start < match.end() for span in spans))

    for block in document_ir.blocks:
        if not is_visible_body_block(block):
            continue
        if block.type == "formula":
            add(block.id, "latex" if block.latex else "text", block.latex or block.text or "", formula=True)
        elif block.type == "table":
            table = parse_html_table(block.html)
            if table:
                if requires_table_expansion(table, block.html):
                    for row in expanded_table_rows(table):
                        for occurrence in row:
                            if occurrence is not None:
                                add(block.id, f"html/{occurrence.source_row}/{occurrence.source_column}", occurrence.cell.html or occurrence.cell.text)
                else:
                    for row_index, row in enumerate(table.rows):
                        for col_index, cell in enumerate(row):
                            add(block.id, f"html/{row_index}/{col_index}", cell.html or cell.text)
            else:
                add(block.id, "text", block.text or "")
        elif block.type == "list":
            for index, text in enumerate(block.list_items or []):
                add(block.id, f"list_items/{index}", text)
        elif block.type != "image":
            add(block.id, "text", block.text or "")
        if block.type == "image":
            annotations = image_annotations(block)
            for field, text in annotations:
                add(block.id, field, text)
            if not annotations:
                add(block.id, "text", block.text or "")
        elif block.type == "table":
            seen: set[tuple[str, str]] = set()
            values = [(f"captions/{index}", text) for index, text in enumerate(block.captions)]
            values.extend((f"footnotes/{index}", text) for index, text in enumerate(block.footnotes))
            for field, text in values:
                # 表题与表注分别去重；图片库存与 writer 共用上面的唯一注释遍历。
                key = (field.split("/")[0], text.strip())
                if text.strip() and key not in seen:
                    seen.add(key)
                    add(block.id, field, text.strip())
    return sources


def build_renderer_evidence(document_ir: DocumentIR, word_content: bytes, layout_plan: LayoutPlan | None = None,
                            *, render_result: WordRenderResult | None = None, formula_report: dict[str, Any] | None = None,
                            image_layout_report: dict[str, Any] | None = None,
                            expected_template_version_id: str | None = None,
                            expected_generation_policy: str | None = None,
                            render_plan: RenderPlan | dict[str, Any] | None = None,
                            block_render_evidence: BlockRenderEvidence | dict[str, Any] | None = None,
                            block_anchor_evidence: BlockAnchorEvidence | dict[str, Any] | None = None,
                            renderer_content_contract_version: Any = _UNSET,
                            formula_source_coverage: Any = _UNSET) -> dict[str, Any]:
    """原内容认证保持严格；恢复时只消费已存 trace，可选锚点失败局部降级。"""
    if render_result is not None:
        if formula_report is not None and formula_report != render_result.formula_report or image_layout_report is not None and image_layout_report != render_result.image_layout_report:
            raise render_contract_failure(ValueError("ir_render_evidence:binding_mismatch"))
        formula_report, image_layout_report = render_result.formula_report, render_result.image_layout_report
        if (renderer_content_contract_version is not _UNSET
                and renderer_content_contract_version != render_result.renderer_content_contract_version
                or formula_source_coverage is not _UNSET and formula_source_coverage != render_result.formula_source_coverage):
            raise render_contract_failure(ValueError("ir_render_evidence:binding_mismatch"))
        renderer_content_contract_version = render_result.renderer_content_contract_version
        formula_source_coverage = render_result.formula_source_coverage
    from app.services.renderer.content_contract import CONTENT_VERSION, build_v2_content_evidence, content_failure
    v2 = renderer_content_contract_version is not _UNSET
    if v2:
        if renderer_content_contract_version != CONTENT_VERSION or formula_source_coverage is _UNSET:
            raise content_failure()
        evidence = build_v2_content_evidence(document_ir, word_content, layout_plan, coverage=formula_source_coverage,
            formula_report=formula_report, image_report=image_layout_report,
            expected_template_version_id=expected_template_version_id, expected_generation_policy=expected_generation_policy)
    else:
        if formula_source_coverage is not _UNSET:
            raise content_failure()
        evidence = build_renderer_aggregate_evidence(document_ir, word_content, layout_plan,
            formula_report=formula_report, image_layout_report=image_layout_report,
            expected_template_version_id=expected_template_version_id, expected_generation_policy=expected_generation_policy)
    if render_result is not None:
        if v2 and (render_result.plan.schema_version != "render-plan/v2"
                   or render_result.block_evidence.schema_version != "block-render-evidence/v2"):
            raise content_failure()
        validate_render_result(document_ir, word_content, render_result)
        plan, trace = render_result.plan, render_result.block_evidence
        block_anchor_evidence = render_result.block_anchor_evidence
    else:
        restored = validate_persisted_render_evidence(document_ir, word_content,
            render_plan=render_plan, block_render_evidence=block_render_evidence) if render_plan is not None and block_render_evidence is not None else None
        plan, trace = restored if restored is not None else (None, None)
        if plan is not None and (plan.schema_version == "render-plan/v2") != v2:
            plan, trace = None, None
    if plan is None:
        evidence["render_trace_status"] = "unavailable"
    else:
        evidence.update(render_trace_status="complete", render_plan=plan.model_dump(mode="json"),
            block_render_evidence=trace.model_dump(mode="json"))
        from app.services.renderer.block_anchors import validate_block_anchor_evidence
        # 新件缺运行期创建事实时不可借名字或持久化 reader 追认；历史件只读原证明。
        ownership = render_result._anchor_ownership if render_result is not None else None
        anchors = validate_block_anchor_evidence(block_anchor_evidence, plan=plan, block_evidence=trace,
            word_content=word_content, ownership=ownership) if render_result is None or ownership is not None else None
        if anchors is not None:
            evidence["block_anchor_evidence"] = anchors.model_dump(mode="json")
        elif v2 and render_result is not None:
            raise content_failure("ir_render_evidence:target_mismatch")
        if render_result is not None:
            evidence["block_anchor_summary"] = {"schema_version": "block-anchor-evidence/v2" if v2 else "block-anchor-evidence/v1",
                **{key: count for key, count in render_result.block_anchor_counts.items()
                   if key in {"created", "name_conflict", "target_unavailable", "limit_exceeded", "generation_disabled"}
                   and type(count) is int and count >= 0}}
    return evidence


def validate_persisted_renderer_content(document_ir: DocumentIR, word_content: bytes, metadata: dict[str, Any], *,
                                        expected_template_version_id: str | None = None) -> dict[str, Any]:
    """共同文件门之后按显式 mandatory 字段分派；可选导航不参与主件内容比较。"""
    from copy import deepcopy
    from app.services.renderer.content_contract import CONTENT_VERSION, content_failure
    from app.services.renderer import image_evidence
    v2 = "renderer_content_contract_version" in metadata
    if not v2 and "formula_source_coverage" in metadata:
        raise content_failure()
    if v2:
        if metadata["renderer_content_contract_version"] != CONTENT_VERSION:
            raise content_failure()
        actual = build_renderer_evidence(document_ir, word_content,
            renderer_content_contract_version=metadata["renderer_content_contract_version"],
            formula_source_coverage=metadata.get("formula_source_coverage"),
            formula_report=metadata.get("formula_report"), image_layout_report=metadata.get("image_layout_report"),
            expected_template_version_id=expected_template_version_id,
            render_plan=metadata.get("render_plan"), block_render_evidence=metadata.get("block_render_evidence"),
            block_anchor_evidence=metadata.get("block_anchor_evidence"))
        _restore_legacy_docx_quality(actual, word_content, metadata)
        ensure_renderer_integrity(actual)
        optional = {"render_trace_status", "render_plan", "block_render_evidence", "block_anchor_evidence", "block_anchor_summary"}
        if any(key not in metadata or metadata[key] != value for key, value in actual.items() if key not in optional):
            raise content_failure("ir_render_evidence:binding_mismatch")
        return actual
    if image_evidence.has_image_markers(word_content) and not isinstance(metadata.get("image_layout_report"), dict):
        raise ValueError("主 DOCX 含图片布局标记但缺少报告。")
    for key in ("formula_report", "image_layout_report"):
        if key in metadata and not isinstance(metadata[key], dict):
            raise ValueError("主 DOCX 的既有内容报告无效。")
    table_plan = None
    placeholders = []
    table_contract = any(key in metadata for key in ("table_rendering", "table_placeholder_rendering", "table_evidence", "table_placeholder_count"))
    if table_contract:
        from app.services.renderer.logical_table_plan import build_logical_table_render_plan
        from app.services.document_ir.table_placeholder import decode_placeholders
        table_plan = build_logical_table_render_plan(document_ir, build_layout_plan(document_ir))
        placeholders = decode_placeholders(document_ir)
    actual = build_renderer_aggregate_evidence(document_ir, word_content,
        formula_report=metadata.get("formula_report"), image_layout_report=metadata.get("image_layout_report"),
        expected_template_version_id=expected_template_version_id, _table_plan=table_plan,
        _placeholder_count=len(placeholders), _legacy_ir_identity=True)
    if table_contract:
        from app.services.renderer.table_content_evidence import _table_rendering_evidence, _build_table_evidence
        from app.services.renderer.table_placeholder_evidence import build_placeholder_evidence
        actual["table_placeholder_count"] = len(placeholders)
        if table_plan is not None:
            actual["table_rendering"], flags = _table_rendering_evidence(document_ir, word_content, table_plan,
                actual["docx_quality"]["table_observations"])
            actual["blocking_quality_flags"] = list(dict.fromkeys([*actual["blocking_quality_flags"], *flags]))
        proof = build_placeholder_evidence(document_ir, word_content)
        if proof is not None:
            actual["table_placeholder_rendering"] = proof
        if "table_evidence" in metadata and not actual["blocking_quality_flags"]:
            actual["table_evidence"] = _build_table_evidence(document_ir, word_content, actual).model_dump(mode="json", warnings=False)
    _restore_legacy_docx_quality(actual, word_content, metadata)
    ensure_renderer_integrity(actual)
    comparable = deepcopy(actual)
    if isinstance(metadata.get("docx_quality"), dict) and "table_observations" not in metadata["docx_quality"]:
        comparable["docx_quality"].pop("table_observations", None)
    keys = LEGACY_RENDERER_EVIDENCE_KEYS | {key for key in comparable if key in metadata}
    if any(key not in metadata or metadata[key] != comparable[key] for key in keys):
        raise ValueError("主 DOCX 的既有质量证据与实际字节不一致。")
    return actual


def _restore_legacy_docx_quality(actual: dict[str, Any], word_content: bytes, metadata: dict[str, Any]) -> None:
    """旧件按原扫描逐值重算，不能因诊断升级拒绝恢复或直接信任存储值。"""
    stored_quality = metadata.get("docx_quality")
    if not isinstance(stored_quality, dict) or "analysis_version" in stored_quality:
        return
    current_flags = set(build_docx_quality_flags(actual["docx_quality"]))
    legacy_quality = analyze_docx_quality_bytes(word_content, formula_report=metadata.get("formula_report"))
    actual["docx_quality"] = legacy_quality
    actual["quality_flags"] = [*build_docx_quality_flags(legacy_quality),
        *(flag for flag in actual["quality_flags"] if flag not in current_flags)]
