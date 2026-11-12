"""渲染证据的发布前完整性门与 RenderPlan/块级 trace 认证。"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from app.services.document_ir.integrity import DocumentIntegrityError, is_visible_body_block
from app.services.document_ir.models import DocumentIR
from app.services.renderer.layout_plan import image_annotations
from app.services.renderer.render_event_summary import (
    RENDER_EVIDENCE_CODES,
    build_renderer_event_summary,
    is_valid_table_rendering_evidence,
)


if TYPE_CHECKING:
    from app.services.renderer.block_evidence import BlockRenderEvidence, WordRenderResult, _RenderOwnership
    from app.services.renderer.render_plan import RenderPlan


def ensure_renderer_integrity(evidence: dict[str, Any]) -> None:
    """阻止包含确定性 IR→DOCX 内容丢失的产物进入发布边界。"""

    if "table_rendering" in evidence and not is_valid_table_rendering_evidence(evidence["table_rendering"]):
        evidence = {**evidence, "blocking_quality_flags": [*evidence.get("blocking_quality_flags", []),
                    "ir_docx_integrity:table_fragment_map_mismatch"]}
    if "table_placeholder_count" in evidence:
        from app.services.renderer.table_placeholder_evidence import valid_placeholder_evidence
        count = evidence["table_placeholder_count"]
        proof = evidence.get("table_placeholder_rendering")
        if (type(count) is not int or count < 0 or count and proof is None
                or proof is not None and (not valid_placeholder_evidence(proof) or proof["count"] != count)):
            evidence = {**evidence, "blocking_quality_flags": [*evidence.get("blocking_quality_flags", []),
                        "table_placeholder_integrity_failed"]}
    if "table_evidence" in evidence:
        from app.services.tables.evidence import read_table_evidence, TableEvidenceError
        report = read_table_evidence(evidence["table_evidence"])
        observations = evidence.get("docx_quality", {}).get("table_observations")
        if not isinstance(observations, list) or any(output.actual.table_index >= len(observations)
                or output.actual.model_dump(mode="json") != observations[output.actual.table_index]
                for table in report.tables for output in table.outputs):
            raise TableEvidenceError("table_evidence_integrity")
    if evidence.get("blocking_quality_flags"):
        raise DocumentIntegrityError("DocumentIR→DOCX", build_renderer_event_summary(evidence))


def render_contract_failure(error: Exception) -> DocumentIntegrityError:
    """只公开固定机器码，不把 ValidationError/源身份写入异常载体。"""
    code = str(error) if str(error) in RENDER_EVIDENCE_CODES else "ir_render_evidence:invalid_contract"
    return DocumentIntegrityError("DocumentIR→DOCX", {"blocking_quality_flags": [code]})


def validate_render_result(document_ir: DocumentIR, word_content: bytes, render_result: WordRenderResult) -> None:
    """同次结果必须保有真实运行期归属，缺失时不能降级到历史读者。"""
    if word_content != render_result.content:
        raise render_contract_failure(ValueError("ir_render_evidence:binding_mismatch"))
    _validate_render_evidence(document_ir, word_content, render_result.plan, render_result.block_evidence,
        ownership=render_result._ownership, require_ownership=True)


def _validate_persisted_image_targets(index, records, blocks, image_ids) -> None:
    """原图片报告通过后，用其稳定 marker 容器核对逐图 target。"""
    from docx.oxml.ns import qn
    from app.services.renderer.image_evidence import image_anchor
    root = index.roots["word/document.xml"]
    markers = {}
    for node in root.iter(qn("w:bookmarkStart")):
        markers.setdefault(node.get(qn("w:name")), []).append(node)
    for block_id in image_ids:
        record = records[block_id]
        expected = [(image_anchor(block_id), None)] + [(image_anchor(block_id, field), i)
            for i, (field, _) in enumerate(image_annotations(blocks[block_id]))]
        if len(record.targets) != len(expected):
            raise ValueError("ir_render_evidence:target_mismatch")
        for target, (name, item_index) in zip(record.targets, expected, strict=True):
            starts = markers.get(name, [])
            if len(starts) != 1 or starts[0].getparent().tag != qn("w:p"):
                raise ValueError("ir_render_evidence:target_mismatch")
            paragraph = starts[0].getparent()
            if target.role == "image":
                drawings = list(paragraph.iter(qn("w:drawing")))
                if len(drawings) != 1:
                    raise ValueError("ir_render_evidence:target_mismatch")
                node = drawings[0]
            else:
                node = paragraph
            if (target.part, tuple(target.child_path), target.item_index) != (*index.paths[node], item_index):
                raise ValueError("ir_render_evidence:target_mismatch")


def validate_persisted_render_evidence(document_ir: DocumentIR, word_content: bytes, *,
                                       render_plan: RenderPlan | dict[str, Any] | None,
                                       block_render_evidence: BlockRenderEvidence | dict[str, Any] | None,
                                       ) -> tuple[RenderPlan, BlockRenderEvidence] | None:
    """消费历史可选 trace；坏 trace 不改变原主件恢复/下载合同。"""
    try:
        return _validate_render_evidence(document_ir, word_content, render_plan, block_render_evidence)
    except DocumentIntegrityError:
        return None


def _validate_render_evidence(document_ir: DocumentIR, word_content: bytes,
                              plan_value: RenderPlan | dict[str, Any] | None,
                              trace_value: BlockRenderEvidence | dict[str, Any] | None,
                              *, ownership: _RenderOwnership | None = None,
                              require_ownership: bool = False) -> tuple[RenderPlan, BlockRenderEvidence]:
    """共用最终包认证；持久化证明不重建同次运行期归属。"""
    from docx.oxml.ns import qn
    from app.services.renderer.block_evidence import (
        BlockRenderEvidence, PackageIndex, _RenderOwnership, provenance_for, toc_representative_target,
    )
    from app.services.renderer.render_plan import (
        RenderPlan, TOC_FORMULA_POLICY_VERSION, content_hash, document_ir_hash, read_render_plan,
    )
    from app.services.renderer.block_evidence import read_block_render_evidence, resolve_table_scope
    from app.services.renderer.text_renderer import TOC_FIELD_INSTRUCTION
    try:
        plan = read_render_plan(plan_value)
        trace = read_block_render_evidence(trace_value)
        v2 = plan.schema_version == "render-plan/v2"
        toc_formula_policy = plan.renderer_policy_version == TOC_FORMULA_POLICY_VERSION
        if (trace.schema_version == "block-render-evidence/v2") != v2:
            raise ValueError("ir_render_evidence:invalid_contract")
        if (trace.docx_sha256 != hashlib.sha256(word_content).hexdigest()
                or plan.input_ir_sha256 != document_ir_hash(document_ir, legacy=not v2)
                or trace.input_ir_sha256 != plan.input_ir_sha256 or trace.resource_identity != plan.resource_identity
                or trace.plan_sha256 != plan.plan_sha256 or not trace.complete):
            raise ValueError("ir_render_evidence:binding_mismatch")
        if require_ownership and (not isinstance(ownership, _RenderOwnership)
                or (ownership.input_ir_sha256, ownership.resource_identity_sha256, ownership.plan_sha256, ownership.docx_sha256)
                != (plan.input_ir_sha256, content_hash(plan.resource_identity.model_dump(mode="json")), plan.plan_sha256, trace.docx_sha256)):
            raise ValueError("ir_render_evidence:target_mismatch")
        ids = [block.id for block in document_ir.blocks]
        record_ids = [record.block_id for record in trace.block_render_map]
        decision_ids = [decision.block_id for decision in plan.decisions]
        if len(ids) != len(set(ids)) or ids != record_ids or ids != decision_ids:
            raise ValueError("ir_render_evidence:block_coverage_mismatch")
        index = PackageIndex(word_content)
        table_members = set()
        if v2:
            from app.services.renderer.content_contract import validate_v2_table_trace
            table_members = validate_v2_table_trace(document_ir, plan, trace, index, ownership,
                require_ownership=require_ownership)
        if len(index.sections) != len(plan.sections):
            raise ValueError("ir_render_evidence:target_mismatch")
        for planned, actual in zip(plan.sections, index.sections, strict=True):
            if planned.orientation != "inherit" and planned.orientation != actual["orientation"] or planned.columns != "inherit" and planned.columns != actual["columns"]:
                raise ValueError("ir_render_evidence:target_mismatch")
        provenance = provenance_for(document_ir)
        records = {record.block_id: record for record in trace.block_render_map}
        decisions = {decision.block_id: decision for decision in plan.decisions}
        blocks = {block.id: block for block in document_ir.blocks}
        owners = {}
        decoration_ops = {block_id: operation for operation in plan.operations if operation.kind == "decoration" for block_id in operation.block_ids}
        for record in trace.block_render_map:
            decision, block = decisions[record.block_id], blocks[record.block_id]
            if record.content_visible != is_visible_body_block(block):
                raise ValueError("ir_render_evidence:binding_mismatch")
            # collector 按 item 顺序记录最后一个归并代表；混合列表仍拥有独立正文目标。
            representative = next((policy.representative_block_id for policy in reversed(decision.text_policies)
                if policy.mode == "coalesced"), None)
            if record.block_id not in table_members and record.representative_block_id != representative:
                raise ValueError("ir_render_evidence:target_mismatch")
            own_targets = [target for target in record.targets if target.role != "toc_representative"]
            if decision.mode == "native_text":
                role = "list_item" if block.type == "list" else "formula" if block.type == "formula" else "body"
                expected = []
                for i, policy in enumerate(decision.text_policies):
                    if policy.mode == "toc_formula_first":
                        expected.append((i, "toc_field"))
                    if policy.mode != "coalesced":
                        expected.append((i, role))
                if [(target.item_index, target.role) for target in own_targets] != expected or any(target.element_kind != "paragraph" for target in own_targets):
                    raise ValueError("ir_render_evidence:target_mismatch")
                if any(own_targets[i].child_path >= own_targets[i + 1].child_path
                       for i, (_, role) in enumerate(expected) if role == "toc_field"):
                    raise ValueError("ir_render_evidence:target_mismatch")
                coalesced = [i for i, policy in enumerate(decision.text_policies) if policy.mode == "coalesced"]
                if [target.item_index for target in record.targets if target.role == "toc_representative"] != coalesced:
                    raise ValueError("ir_render_evidence:target_mismatch")
                if decision.text_policies and record.disposition != ("rendered" if expected else "coalesced"):
                    raise ValueError("ir_render_evidence:target_mismatch")
                if block.type == "list":
                    expected_items = [(i, "coalesced" if policy.mode == "coalesced" else "rendered",
                        policy.representative_block_id, policy.representative_item_index) for i, policy in enumerate(decision.text_policies)]
                    if [(item.item_index, item.disposition, item.representative_block_id, item.representative_item_index) for item in record.items] != expected_items:
                        raise ValueError("ir_render_evidence:target_mismatch")
            elif decision.table_strategy is not None and record.block_id not in table_members:
                caption_count = len(dict.fromkeys(text.strip() for text in block.captions if text.strip()))
                note_count = len(dict.fromkeys(text.strip() for text in block.footnotes if text.strip()))
                roles = ["context" if style == "normal" else "caption" for style in decision.annotation_styles[:caption_count]]
                roles += ["body" if decision.table_strategy == "fallback" else "table"] + ["note"] * note_count
                if v2:
                    from app.services.document_ir.table_placeholder import decode_placeholders
                    placeholders = [item for item in decode_placeholders(document_ir) if item.owner_block_id == block.id]
                    if placeholders:
                        roles = roles[:caption_count] + (["body"] if block.text and block.text not in block.captions else [])
                        roles += ["image_fallback"] * len(placeholders) + ["note"] * note_count
                if [target.role for target in own_targets] != roles:
                    raise ValueError("ir_render_evidence:target_mismatch")
                if any(target.element_kind != ("table" if target.role == "table" else "paragraph") for target in own_targets):
                    raise ValueError("ir_render_evidence:target_mismatch")
            elif decision.image_strategy is not None:
                if not own_targets or own_targets[0].role not in {"image", "image_fallback"}:
                    raise ValueError("ir_render_evidence:target_mismatch")
                if own_targets[0].role == "image" and own_targets[0].element_kind != "drawing":
                    raise ValueError("ir_render_evidence:target_mismatch")
                if any(target.role != "caption" for target in own_targets[1:]):
                    raise ValueError("ir_render_evidence:target_mismatch")
                if decision.image_strategy == "bbox_relative":
                    expected_count = len(decision.annotation_styles)
                    if len(own_targets) != expected_count + 1 or any(target.element_kind != "paragraph" for target in own_targets[1:]):
                        raise ValueError("ir_render_evidence:target_mismatch")
                elif decision.annotation_styles and len(own_targets) <= 1:
                    raise ValueError("ir_render_evidence:target_mismatch")
            if (record.decision_id, record.anchor_ref, record.provenance) != (decision.decision_id, decision.anchor_ref, provenance[block.id]):
                raise ValueError("ir_render_evidence:binding_mismatch")
            if record.disposition in {"rendered", "coalesced"} and not record.targets and record.block_id not in table_members:
                raise ValueError("ir_render_evidence:target_mismatch")
            if record.disposition in {"suppressed", "superseded", "not_emitted"} and record.targets:
                raise ValueError("ir_render_evidence:target_mismatch")
            if record.disposition == "not_emitted" and not (decision.mode == "unassigned" or block.type == "list" and not block.list_items):
                raise ValueError("ir_render_evidence:target_mismatch")
            if record.disposition == "not_emitted" and is_visible_body_block(block):
                raise ValueError("ir_render_evidence:target_mismatch")
            if record.disposition == "suppressed":
                operation = decoration_ops.get(block.id)
                expected = "custom_footer" if operation and operation.decoration_policy == "custom" else "decoration_disabled"
                if operation is None or operation.decoration_policy == "replace" or record.reason_code != expected:
                    raise ValueError("ir_render_evidence:target_mismatch")
            if record.disposition == "superseded":
                operation = decoration_ops.get(block.id)
                current, seen = record, set()
                while current.disposition == "superseded":
                    if current.block_id in seen or current.replacement_block_id not in records:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    seen.add(current.block_id)
                    current = records[current.replacement_block_id]
                if operation is None or operation.decoration_policy != "replace" or current.disposition != "rendered":
                    raise ValueError("ir_render_evidence:target_mismatch")
                section_index = int(operation.section_id.split("_")[1])
                if not any(t.role == operation.decoration_kind and section_index in t.actual["referenced_section_indices"] for t in current.targets):
                    raise ValueError("ir_render_evidence:target_mismatch")
            if block.type == "list" and len(record.items) != len(block.list_items or []):
                raise ValueError("ir_render_evidence:target_mismatch")
            for target in record.targets:
                if any(type(value) is not int or value < 0 for value in target.child_path):
                    raise ValueError("ir_render_evidence:target_mismatch")
                if v2 and target.element_kind == "table_rows":
                    from app.services.renderer.content_contract import project_table_scope
                    scope = resolve_table_scope(trace, target.content_scope_id)
                    if scope.block_id != block.id or (scope.part, scope.table_child_path) != (target.part, target.child_path):
                        raise ValueError("ir_render_evidence:target_mismatch")
                    actual, bookmarks = project_table_scope(index, scope)
                    kind = "table_rows"
                else:
                    if v2 and target.content_scope_id is not None:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    kind, actual, bookmarks = index.project(target.part, tuple(target.child_path))
                if (kind, actual, bookmarks) != (target.element_kind, target.actual, target.bookmark_names):
                    raise ValueError("ir_render_evidence:target_mismatch")
                if target.role == "toc_representative":
                    item = target.item_index
                    if item is None or item >= len(decision.text_policies):
                        raise ValueError("ir_render_evidence:target_mismatch")
                    policy = decision.text_policies[item]
                    representative = records.get(policy.representative_block_id)
                    if policy.mode != "coalesced" or representative is None:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    if toc_formula_policy and (policy.representative_item_index is None or
                            decisions[representative.block_id].text_policies[policy.representative_item_index].mode
                            not in {"toc", "toc_formula_first"}):
                        raise ValueError("ir_render_evidence:target_mismatch")
                    shared = toc_representative_target(representative.targets, policy.representative_item_index)
                    if (shared.part, shared.child_path) != (target.part, target.child_path):
                        raise ValueError("ir_render_evidence:target_mismatch")
                    continue
                if (toc_formula_policy and decision.mode == "native_text" and
                        (target.role == "toc_field" or decision.text_policies[target.item_index].mode == "toc")):
                    node = index.nodes[target.part, tuple(target.child_path)]
                    if ([leaf.text for leaf in node.iter(qn("w:instrText"))] != [TOC_FIELD_INSTRUCTION]
                            or [leaf.get(qn("w:fldCharType")) for leaf in node.iter(qn("w:fldChar"))]
                            != ["begin", "separate", "end"]):
                        raise ValueError("ir_render_evidence:target_mismatch")
                section = int(decision.section_id.split("_")[1]) if decision.section_id is not None else None
                if section not in actual["referenced_section_indices"]:
                    raise ValueError("ir_render_evidence:target_mismatch")
                if decision.mode == "decoration":
                    op = decoration_ops[block.id]
                    group = "decoration:" + content_hash([op.decoration_kind, op.block_ids])
                    if target.role != op.decoration_kind or target.sharing_group != group or target.participant_order != op.block_ids.index(block.id):
                        raise ValueError("ir_render_evidence:target_mismatch")
                elif target.sharing_group is not None or target.part != "word/document.xml":
                    raise ValueError("ir_render_evidence:target_mismatch")
                locator = (target.part, tuple(target.child_path), target.content_scope_id if v2 else None)
                other = owners.get(locator)
                if other is not None and not (target.sharing_group is not None and other == target.sharing_group):
                    raise ValueError("ir_render_evidence:target_mismatch")
                owners[locator] = target.sharing_group or block.id
            names = list(dict.fromkeys(name for t in record.targets for name in t.bookmark_names))
            if record.bookmark_name != (names[0] if names else None):
                raise ValueError("ir_render_evidence:target_mismatch")
        # 每图/每条注释只拥有其真实 cell 或正文对象，不能以表计数或全局 OMML 集合替代归属。
        image_ids = [block_id for operation in plan.operations if operation.kind == "block"
            for block_id in operation.block_ids if blocks[block_id].type == "image"]
        if require_ownership:
            if image_ids != [image.block_id for image in ownership.images]:
                raise ValueError("ir_render_evidence:target_mismatch")
            for image in ownership.images:
                actual = [(tuple(target.child_path), target.element_kind, target.role, target.item_index)
                    for target in records[image.block_id].targets]
                if image.part != "word/document.xml" or any(target.part != image.part for target in records[image.block_id].targets) or tuple(actual) != image.targets:
                    raise ValueError("ir_render_evidence:target_mismatch")
        else:
            # 恢复沿 RND-503 已认证的原图/注释 marker 核对位置，不声称重新获得创建事实。
            _validate_persisted_image_targets(index, records, blocks, image_ids)
        # 实际输出顺序与计划一致，交换两个合法段落 locator 也不能通过。
        previous = None
        for operation in plan.operations:
            if v2 and operation.kind == "logical_table":
                own = [tuple(target.child_path) for block_id in operation.block_ids
                       for target in records[block_id].targets]
                if own:
                    if previous is not None and min(own) <= previous:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    previous = max(own)
                continue
            if operation.kind not in {"block", "image_pair"}:
                continue
            for block_id in operation.block_ids:
                own = [tuple(t.child_path) for t in records[block_id].targets if t.role != "toc_representative"]
                if own:
                    position = min(own)
                    if previous is not None and position <= previous:
                        raise ValueError("ir_render_evidence:target_mismatch")
                    previous = max(own) if v2 else position
        counts = {state: sum(r.disposition == state for r in records.values()) for state in ("rendered", "coalesced", "suppressed", "superseded", "not_emitted")}
        counts.update(block_count=len(records), target_count=sum(len(r.targets) for r in records.values()))
        if trace.counts != counts:
            raise ValueError("ir_render_evidence:block_coverage_mismatch")
        return plan, trace
    except DocumentIntegrityError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, UnicodeError) as exc:
        raise render_contract_failure(exc) from None
