"""渲染证据到事件、异常和接口摘要的安全投影。

只输出白名单内的计数、版本和受控诊断码；自由 block/fragment 身份与异常正文留在私有证据中。
"""

from __future__ import annotations

import re
from typing import Any

from app.domains.resources.integrity import RENDER_RESOURCE_ERROR_CODES
from app.services.renderer.logical_table_plan import (
    TABLE_RENDERING_VERSION, QUALITY_BLOCKERS, QUALITY_WARNINGS, SAFE_COUNT_KEYS,
)
from app.services.renderer.template_conformance import TEMPLATE_CONFORMANCE_FLAGS, build_template_conformance_summary


RENDER_EVIDENCE_CODES = frozenset({
    "ir_render_evidence:binding_mismatch", "ir_render_evidence:block_coverage_mismatch",
    "ir_render_evidence:target_mismatch", "ir_render_evidence:invalid_contract",
})


CONTROLLED_SOURCE_TYPES = frozenset({"text", "paragraph", "para", "title", "heading", "header", "footer", "page_header", "page_footer", "page_number", "table", "table_placeholder", "image", "chart", "figure", "list", "index", "equation", "formula", "interline_equation", "inline_equation", "equation_interline", "unsupported", "invalid", "unknown"})
FIXED_FLAGS = frozenset({"formula_text_fallback", "image_group_uncertain", "caption_binding_uncertain", "docx_quality_unavailable", "docx_analysis_error", "docx_no_editable_content", "docx_image_only_suspected", "middle_json_missing", "empty_content_list",
    "source_ir_integrity:block_count_mismatch", "source_ir_integrity:type_count_mismatch", "ir_layout_integrity:missing_blocks", "ir_layout_integrity:duplicate_blocks", "ir_docx_integrity:image_asset_missing", "ir_docx_integrity:inline_shape_count_mismatch", "ir_docx_integrity:table_count_mismatch", "ir_docx_integrity:heading_count_mismatch",
    "ir_docx_integrity:table_anchor_mismatch", "ir_docx_integrity:table_row_count_mismatch", "ir_docx_integrity:table_header_mismatch",
    "ir_docx_integrity:table_geometry_mismatch", "ir_docx_integrity:table_fragment_anchor_mismatch",
    "ir_docx_integrity:table_fragment_map_mismatch", "table_placeholder_integrity_failed", "table_noneditable_placeholder"
}) | RENDER_EVIDENCE_CODES | QUALITY_BLOCKERS | QUALITY_WARNINGS | RENDER_RESOURCE_ERROR_CODES | TEMPLATE_CONFORMANCE_FLAGS
COUNT_FLAG_RE = re.compile(r"(?:docx_latex_residue|docx_manual_list_markers|docx_plain_toc_entries|docx_unstyled_heading_candidates|final_promotional_page_filtered):[0-9]+\Z")


def controlled_quality_flags(value: Any) -> list[str]:
    """只返回已定义的诊断码；自由 block/fragment 身份留在私有证据。"""
    if not isinstance(value, list):
        return []
    result = []
    for flag in value:
        if not isinstance(flag, str):
            continue
        parts = flag.split(":")
        if (flag in FIXED_FLAGS or COUNT_FLAG_RE.fullmatch(flag)
                or len(parts) == 3 and parts[0] == "source_ir_integrity" and parts[1] in {"type_mismatch", "payload_missing"} and parts[2] in CONTROLLED_SOURCE_TYPES):
            result.append(flag)
        elif parts[0] in {"table_continuation_uncertain", "layout_bbox_missing", "table_continuation", "layout_two_column_candidate", "layout_wide_table", "layout_table_context_binding", "layout_caption_binding", "layout_footnote_binding", "unsupported_block_type"}:
            result.append(parts[0])
    return list(dict.fromkeys(result))


NUMERIC_KEYS = frozenset("degraded_source_block_count render_degraded_page_count expected_layout_table_count layout_table_count layout_table_count_delta expected_content_table_count content_table_count content_table_count_delta expected_total_table_count total_table_count total_table_count_delta layout_missing_block_count layout_duplicate_block_count page_count block_count layout_page_count layout_region_count layout_block_count expected_layout_block_count layout_block_count_delta expected_inline_shape_count inline_shape_count inline_shape_count_delta expected_table_count table_count table_count_delta expected_heading_count heading_count heading_count_delta expected_source_block_count ir_main_block_count source_block_count_delta paragraph_count wide_table_count media_count heading_paragraphs heading_like_paragraphs heading_like_unstyled_paragraphs numbering_paragraphs manual_list_marker_paragraphs toc_tab_leader_paragraphs plain_toc_entry_paragraphs keep_next_paragraphs table_header_rows table_no_split_rows shaded_table_cells table_cell_zero_spacing_paragraphs landscape_sections latex_residue_count text_chars".split())
BOOLEAN_KEYS = frozenset({"editable_text_available", "editable_content_available", "image_only_suspected"})


def _safe_counts(value):
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if key in NUMERIC_KEYS and (type(item) is int or item is None)
        or key in BOOLEAN_KEYS and type(item) is bool}


def _type_counts(value):
    result = {}
    for key, count in value.items() if isinstance(value, dict) else []:
        if type(count) is int and count >= 0:
            label = key if key in CONTROLLED_SOURCE_TYPES else "unknown"
            result[label] = result.get(label, 0) + count
    return result


FAILURE_OPERATION_KINDS = frozenset({"section", "configure_page", "decoration", "block", "image_pair", "column_break",
                                     "logical_table", "table_prepare", "layout_plan", "table_plan", "render_plan", "table_placeholder"})
FAILURE_REASON_CODES = frozenset({
    "table_render_input", "table_render_geometry", "table_render_failed", "table_build_limit", "table_html_encoding",
    "table_html_unsupported_structure", "table_placeholder_crop_failed", "table_placeholder_geometry_invalid",
    "table_placeholder_integrity_failed", "table_placeholder_source_unavailable",
    "ValueError", "KeyError", "TypeError", "IndexError", "AttributeError", "UnicodeError", "OSError",
    "ZeroDivisionError", "OverflowError", "RuntimeError",
})
FAILURE_ID_RE = re.compile(r"[A-Za-z0-9:_-]{1,120}")


def _safe_failure_context(value: Any) -> dict[str, Any] | None:
    """失败操作定位逐字段白名单；原因码只接受固定错误码、受控质量标记或异常类型名，不收异常正文。"""
    if not isinstance(value, dict) or value.get("operation_kind") not in FAILURE_OPERATION_KINDS:
        return None
    reason = value.get("reason_code")
    if not isinstance(reason, str) or not (reason in FAILURE_REASON_CODES or controlled_quality_flags([reason])):
        return None
    block_ids = value.get("block_ids")
    if not isinstance(block_ids, list) or len(block_ids) > 20 or not all(
            isinstance(item, str) and FAILURE_ID_RE.fullmatch(item) for item in block_ids):
        return None
    result: dict[str, Any] = {"operation_kind": value["operation_kind"], "reason_code": reason, "block_ids": list(block_ids)}
    for key in ("operation_index", "source_page_index", "source_page_count"):
        item = value.get(key)
        result[key] = item if type(item) is int and item >= 0 else None
    basis = value.get("page_count_basis")
    result["page_count_basis"] = basis if basis in {"mineru_layout", "content_blocks"} else None
    for key in ("section_id", "unit_id"):
        item = value.get(key)
        result[key] = item if isinstance(item, str) and FAILURE_ID_RE.fullmatch(item) else None
    return result


def build_renderer_event_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """完整字段白名单；新增私有 metadata 默认不会进入事件/异常。"""
    summary = _safe_counts(evidence)
    if evidence.get("renderer_content_contract_version") == "renderer-content/v2":
        summary["renderer_content_contract_version"] = "renderer-content/v2"
    if evidence.get("schema_version") in {"document-ir/v1", "document-ir/v2"}:
        summary["schema_version"] = evidence["schema_version"]
    if evidence.get("renderer_mode") in {"layout_v2", "legacy_v1_fallback"}:
        summary["renderer_mode"] = evidence["renderer_mode"]
    for key in ("quality_flags", "layout_quality_flags", "blocking_quality_flags"):
        if key in evidence:
            value = evidence[key]
            flags = controlled_quality_flags(value)
            summary[key] = flags
            previous = evidence.get(key + "_unknown_count")
            summary[key + "_unknown_count"] = previous if type(previous) is int and previous >= 0 else (sum(isinstance(item, str) and not controlled_quality_flags([item]) for item in value) if isinstance(value, list) else 0)
    for key in ("layout_missing_block_ids", "layout_duplicate_block_ids"):
        if isinstance(evidence.get(key), list):
            summary[key.removesuffix("_ids") + "_count"] = len(evidence[key])
    for key in ("source_integrity", "docx_quality"):
        value = evidence.get(key)
        if isinstance(value, dict):
            projected = _safe_counts(value)
            if key == "source_integrity":
                projected["blocking_quality_flags"] = controlled_quality_flags(value.get("blocking_quality_flags"))
                for field in ("expected_source_type_counts", "ir_source_type_counts"):
                    projected[field] = _type_counts(value.get(field))
            elif value.get("analysis_error"):
                projected["analysis_error"] = "document_xml_parse_error"
            summary[key] = projected
    conformance = build_template_conformance_summary(evidence.get("template_conformance"))
    if conformance is not None:
        summary["template_conformance"] = conformance
    if "mineru_validation" in evidence:
        summary["mineru_validation"] = _safe_mineru_report(evidence["mineru_validation"])
    if "failure_context" in evidence:
        context = _safe_failure_context(evidence["failure_context"])
        if context is not None:
            summary["failure_context"] = context
    if "mineru_validation_input" in evidence:
        value = evidence["mineru_validation_input"]
        summary["mineru_validation_input"] = _safe_validation_input(value)
    if evidence.get("render_trace_status") in {"complete", "unavailable"}:
        summary["render_trace_status"] = evidence["render_trace_status"]
    for key in ("input_ir_sha256", "plan_sha256", "docx_sha256"):
        value = evidence.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            summary[key] = value
    for key, versions in (("render_plan_schema_version", {"render-plan/v1", "render-plan/v2"}),
                          ("block_render_evidence_schema_version", {"block-render-evidence/v1", "block-render-evidence/v2"})):
        if evidence.get(key) in versions | {"unavailable"}:
            summary[key] = evidence[key]
    counts = evidence.get("render_trace_counts")
    if isinstance(counts, dict):
        summary["render_trace_counts"] = {k: v for k, v in counts.items() if k in {"rendered", "coalesced", "suppressed", "superseded", "not_emitted", "block_count", "target_count"} and type(v) is int and v >= 0}
    plan, trace = evidence.get("render_plan"), evidence.get("block_render_evidence")
    if isinstance(plan, dict) and isinstance(trace, dict):
        for key in ("input_ir_sha256", "plan_sha256", "docx_sha256"):
            value = trace.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                summary[key] = value
        summary["render_plan_schema_version"] = plan["schema_version"] if plan.get("schema_version") in {"render-plan/v1", "render-plan/v2"} else "unavailable"
        summary["block_render_evidence_schema_version"] = trace["schema_version"] if trace.get("schema_version") in {"block-render-evidence/v1", "block-render-evidence/v2"} else "unavailable"
        counts = trace.get("counts")
        if isinstance(counts, dict):
            summary["render_trace_counts"] = {k: v for k, v in counts.items() if k in {"rendered", "coalesced", "suppressed", "superseded", "not_emitted", "block_count", "target_count"} and type(v) is int and v >= 0}
    anchor_summary = evidence.get("block_anchor_summary")
    if isinstance(anchor_summary, dict) and anchor_summary.get("schema_version") in {"block-anchor-evidence/v1", "block-anchor-evidence/v2"}:
        summary["block_anchor_summary"] = {"schema_version": anchor_summary["schema_version"],
            **{key: count for key, count in anchor_summary.items()
               if key in {"created", "name_conflict", "target_unavailable", "limit_exceeded", "generation_disabled"}
               and type(count) is int and count >= 0}}
    from app.conversion.docx_rules.formula import FORMULA_REASONS
    report_fields = (
        ("formula_summary", "formula-summary/v1", {"formula_count", "omml_count", "semantic_count", "fallback_count"}, FORMULA_REASONS),
        ("image_layout_summary", "image-layout/v1", {"accepted_group_count", "single_image_count", "uncertain_span_count", "omitted_example_count"},
         {"geometry_unavailable", "geometry_invalid", "page_or_section_boundary", "source_order_conflict", "row_alignment_insufficient",
          "horizontal_overlap", "gap_too_large", "competing_row_membership", "caption_binding_uncertain", "external_caption_binding", "asset_unavailable", "image_size_unfit"}),
    )
    for key, version, numeric_fields, reasons in report_fields:
        value = evidence.get(key)
        if not isinstance(value, dict) or value.get("schema_version") != version:
            continue
        safe = {"schema_version": version, **{name: item for name, item in value.items()
            if name in numeric_fields and type(item) is int and item >= 0}}
        digest = value.get("report_sha256")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            safe["report_sha256"] = digest
        counts = value.get("reason_counts")
        if isinstance(counts, dict):
            safe["reason_counts"] = {reason: count for reason, count in counts.items()
                if reason in reasons and type(count) is int and count >= 0}
        if key == "formula_summary":
            safe["warning_codes"] = controlled_quality_flags(value.get("warning_codes"))
        summary[key] = safe
    native = evidence.get("table_rendering")
    if isinstance(native, dict) and native.get("version") == TABLE_RENDERING_VERSION:
        status = native.get("quality_status")
        summary["table_rendering"] = {"version": TABLE_RENDERING_VERSION,
            "quality_status": status if isinstance(status, str) and status in {"passed", "warning", "blocked"} else None,
            "blocking_quality_flags": controlled_quality_flags(native.get("blocking_quality_flags")),
            "warning_flags": controlled_quality_flags(native.get("warning_flags")),
            **{key: native[key] for key in SAFE_COUNT_KEYS if type(native.get(key)) is int and native[key] >= 0}}
    proof = evidence.get("table_placeholder_rendering")
    if isinstance(proof, dict) and proof.get("version") == "table-placeholder-rendering/v1":
        summary["table_placeholder_rendering"] = {"version": "table-placeholder-rendering/v1",
            "count": proof.get("count") if type(proof.get("count")) is int and proof["count"] >= 0 else None,
            "issue_codes": controlled_quality_flags(proof.get("issue_codes"))}
    table_report = evidence.get("table_evidence")
    if isinstance(table_report, dict) and table_report.get("schema_version") == "table-evidence/v1":
        from app.services.tables.evidence import ISSUE_CODES
        counts = table_report.get("counts")
        count_source = counts if isinstance(counts, dict) else table_report
        issues = table_report.get("issue_codes")
        if not isinstance(issues, list):
            tables = table_report.get("tables")
            issues = []
            for table in tables if isinstance(tables, list) else []:
                flags = table.get("flags") if isinstance(table, dict) else None
                if isinstance(flags, list):
                    issues.extend(flag.get("code") for flag in flags if isinstance(flag, dict))
        summary["table_evidence"] = {"schema_version": "table-evidence/v1",
            **{key: table_report[key] for key, allowed in (("coverage", {"complete", "unavailable"}),
               ("status", {"pending", "passed", "warning", "blocked"}))
               if isinstance(table_report.get(key), str) and table_report[key] in allowed},
            **{key: value for key, value in count_source.items() if key in {"table_count", "fragment_count", "native_count",
                "placeholder_count", "blocker_count", "warning_count"} and type(value) is int and value >= 0},
            "issue_codes": list(dict.fromkeys(code for code in issues if isinstance(code, str) and code in ISSUE_CODES))}
    return summary


# INPUT-006 的安全输出合同；不接受 schema 内自由字典中的任意机器字符串。
REPORT_CODES = frozenset({
    "mineru_package_invalid", "mineru_package_limit_exceeded", "mineru_path_invalid", "mineru_content_list_missing",
    "mineru_json_invalid", "mineru_content_empty", "mineru_page_invalid", "mineru_page_missing", "mineru_page_empty",
    "mineru_page_gap", "mineru_block_invalid", "mineru_block_payload_invalid", "unsupported_block_type",
    "legacy_page_index_coerced", "mineru_page_order_nonmonotonic", "mineru_bbox_missing", "mineru_bbox_invalid",
    "report_limit_exceeded", "mineru_margin_payload_empty", "mineru_merged_paragraph_empty", "missing_image_asset", "invalid_image_asset",
    "missing_table_reference", "invalid_table_reference", "empty_table_html", "invalid_table_html", "suspicious_table_html",
    "image_asset_normalized", "image_asset_pdf_fallback",
})
REPORT_REASONS = frozenset({
    "absolute_or_traversal", "actual_expanded_bytes", "ambiguous_asset_reference", "conflicting_index",
    "contentful_table_placeholder", "duplicate_normalized_path", "encrypted_entry", "entry_count",
    "expected_asset_path_string", "expected_list", "expected_runs", "expected_string", "expected_type_string",
    "file_directory_conflict", "image_bytes", "invalid", "invalid_block", "invalid_content_node", "invalid_content_type",
    "invalid_index", "invalid_page", "invalid_path_syntax", "invalid_span", "invalid_text_node", "invalid_type",
    "isolated_unicode_surrogate", "issue_details", "json_bytes", "missing", "missing_content_list", "missing_index",
    "missing_or_invalid_type", "missing_readable_formula", "missing_readable_payload", "missing_readable_table_payload",
    "mixed_or_invalid_page", "nested_table", "no_blocks", "no_consumable_rows", "non_finite", "non_numeric",
    "non_positive_area", "not_allowed_raster_format", "not_object", "outside_package_root", "outside_selected_list_payload",
    "outside_selected_rich_payload", "report_bytes", "single_file_bytes", "special_zip_entry", "symlink", "total_bytes",
    "type_too_long", "unaccounted_normalization", "unreadable_archive", "unreadable_json", "unreadable_or_unsupported_image",
    "unsupported_tag", "unsupported_top_level", "wrong_length_or_type", "final_promotional_page",
    "explicit_table_placeholder", "strict_empty_table_placeholder", "word_incompatible_raster", "merged_paragraph_residue",
})
REPORT_DETAIL_VALUES = {
    "code": REPORT_CODES,
    "severity": {"warning", "blocker"},
    "classification": {"html_present_and_parseable", "html_present_but_suspicious", "html_missing_reference_present", "html_missing_reference_missing"},
    "reference_status": {"valid", "missing", "invalid", "unsafe"},
    "reference_resolution": {"package_root", "content_list_directory"},
    "rule_id": {"final_promotional_page/v1", "mineru_empty_table_continuation/v1"},
    "reason": REPORT_REASONS,
}
REPORT_VERSIONS = {
    "schema_version": {"mineru-artifact-validation/v1"},
    "validator_version": {"mineru-artifact-validator/v1", "mineru-artifact-validator/v2", "mineru-artifact-validator/v3", "mineru-artifact-validator/v4"},
    "policy_version": {"mineru-input-policy/v1", "mineru-input-policy/v2"},
}
REPORT_NUMERIC_KEYS = frozenset("page_index source_index_in_page source_index row_count cell_count warning_count blocker_count fatal_count omitted_issue_count table_check_count omitted_table_check_count raw_page_count raw_block_count valid_block_count invalid_block_count invalid_page_count image_check_count table_reference_check_count omitted_type_count block_count filtered_promotional_page_index filtered_block_count merged_table_placeholder_count omitted_merged_table_placeholder_count omitted_filtered_block_count previous_page_index index_gap width height".split())
REPORT_BOOLEAN_KEYS = frozenset({"complete", "can_convert", "details_truncated", "stops_conversion", "parseable", "readable_payload"})
REPORT_LOCATOR_KEYS = frozenset({"json_pointer", "page_index", "source_index_in_page", "source_index", "source_type"})


def _safe_validation_input(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("mineru_raw_result_file_id", "mineru_raw_result_sha256", "retry_count"):
        item = value.get(key)
        if key == "retry_count" and type(item) is int and item >= 0:
            result[key] = item
        elif key.endswith("file_id") and isinstance(item, str) and re.fullmatch(r"file_[a-zA-Z0-9_-]{1,80}", item):
            result[key] = item
        elif key.endswith("sha256") and isinstance(item, str) and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", item):
            result[key] = item
    return result


def _report_locator(value):
    from app.services.document_ir.artifact_validator import REPORT_FIELD_NAMES
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in REPORT_LOCATOR_KEYS:
        item = value.get(key)
        if key in REPORT_NUMERIC_KEYS and (item is None or type(item) is int and item >= 0):
            result[key] = item
        elif key == "source_type" and (item is None or isinstance(item, str) and item in CONTROLLED_SOURCE_TYPES):
            result[key] = item
        elif key == "json_pointer" and isinstance(item, str) and re.fullmatch(r"(?:/(?:content_list|[0-9]+))*", item):
            result[key] = item
    field = value.get("field")
    if field is None:
        if "field" in value:
            result["field"] = None
    elif isinstance(field, str) and all(part in REPORT_FIELD_NAMES or part.isdecimal() or re.fullmatch(r"unknown_[0-9a-f]{12}", part) for part in field.split("/")):
        result["field"] = field
    return result


def _report_counts(value):
    return {key: count for key, count in value.items() if key in REPORT_CODES and type(count) is int and count >= 0} if isinstance(value, dict) else {}


def _report_detail(value):
    if not isinstance(value, dict):
        return {}
    result = _report_locator(value)
    for key in ("code", "severity", "classification", "reference_status", "reference_resolution", "rule_id", "reason"):
        item = value.get(key)
        if item is None and key in value or isinstance(item, str) and item in REPORT_DETAIL_VALUES[key]:
            result[key] = item
    for key in REPORT_NUMERIC_KEYS | REPORT_BOOLEAN_KEYS:
        item = value.get(key)
        if key in value and (key in REPORT_NUMERIC_KEYS and (type(item) is int or item is None) or key in REPORT_BOOLEAN_KEYS and type(item) is bool):
            result[key] = item
    facts = value.get("facts")
    if isinstance(facts, dict):
        safe = {}
        for key, item in facts.items():
            if key in REPORT_NUMERIC_KEYS and type(item) is int or key in REPORT_BOOLEAN_KEYS and type(item) is bool:
                safe[key] = item
            elif key == "reason" and isinstance(item, str) and item in REPORT_REASONS:
                safe[key] = item
            elif key == "actual_type" and isinstance(item, str) and item in {"str", "dict", "list", "int", "float", "bool", "NoneType"}:
                safe[key] = item
            elif key == "reasons" and isinstance(item, list):
                safe[key] = [reason for reason in item if isinstance(reason, str) and reason in REPORT_REASONS]
        result["facts"] = safe
    if isinstance(value.get("target"), dict):
        result["target"] = _report_locator(value["target"])
    return result


def _safe_mineru_report(value):
    """报告 schema 内自由字典仍按 INPUT-006 实际字段/有限值逐层投影。"""
    from app.services.document_ir.artifact_validator import MinerUValidationReport
    from app.services.document_ir.mineru_package import validate_relative_path
    from pydantic import ValidationError
    if value is None:
        return None
    try:
        report = MinerUValidationReport.model_validate(value).model_dump(mode="json")
    except (ValidationError, ValueError, TypeError):
        return None
    result = {}
    for key in ("schema_version", "validator_version", "policy_version"):
        if isinstance(report[key], str) and report[key] in REPORT_VERSIONS[key]:
            result[key] = report[key]
    for key in ("package_sha256", "content_list_sha256"):
        item = report[key]
        if item is None or re.fullmatch(r"[0-9a-f]{64}", item):
            result[key] = item
    # 这是 INPUT-006 明确允许的包内路径，不接受服务器绝对路径或 object key。
    item = report["content_list_path"]
    if item is None:
        result["content_list_path"] = None
    else:
        try:
            validate_relative_path(item)
            result["content_list_path"] = item
        except ValueError:
            pass
    for key in REPORT_NUMERIC_KEYS | REPORT_BOOLEAN_KEYS:
        if key in report:
            result[key] = report[key]
    for key in ("warnings", "blockers", "table_checks"):
        result[key] = [_report_detail(item) for item in report[key]]
    result["first_fatal"] = _report_detail(report["first_fatal"]) if report["first_fatal"] is not None else None
    result["issue_counts"] = {severity: _report_counts(report["issue_counts"].get(severity)) for severity in ("warning", "blocker")}
    for key in ("inventory", "effective_inventory"):
        value = report[key]
        safe = {k: v for k, v in value.items() if k in REPORT_NUMERIC_KEYS and type(v) is int}
        if isinstance(value.get("input_shape"), str) and value["input_shape"] in {"flat", "nested", "wrapper_flat", "wrapper_nested"}:
            safe["input_shape"] = value["input_shape"]
        if "type_counts" in value:
            safe["type_counts"] = _type_counts(value["type_counts"])
        result[key] = safe
    value = report["normalization"]
    safe = {k: v for k, v in value.items() if k in REPORT_NUMERIC_KEYS and (type(v) is int or v is None)}
    for key in ("filtered_blocks", "merged_table_placeholders"):
        if isinstance(value.get(key), list):
            safe[key] = [_report_detail(item) for item in value[key]]
    if isinstance(value.get("resolved_issue_counts"), dict):
        safe["resolved_issue_counts"] = {"blocker": _report_counts(value["resolved_issue_counts"].get("blocker"))}
    result["normalization"] = safe
    return result


def is_valid_table_rendering_evidence(value: Any) -> bool:
    """完整证据在登记前再次核对覆盖，防止中途丢 map 被根 flag 空列表掩盖。"""
    if not isinstance(value, dict) or value.get("version") != TABLE_RENDERING_VERSION:
        return False
    if not isinstance(value.get("quality_status"), str) or value["quality_status"] not in {"passed", "warning", "blocked"}:
        return False
    blockers, warnings = value.get("blocking_quality_flags"), value.get("warning_flags")
    if (not isinstance(blockers, list) or any(not isinstance(flag, str) or flag not in QUALITY_BLOCKERS for flag in blockers) or
            not isinstance(warnings, list) or any(not isinstance(flag, str) or flag not in QUALITY_WARNINGS for flag in warnings)):
        return False
    if value["quality_status"] != ("blocked" if blockers else "warning" if warnings else "passed"):
        return False
    if any(type(value.get(key)) is not int or value[key] < 0 for key in SAFE_COUNT_KEYS):
        return False
    tables = value.get("tables")
    if not isinstance(tables, list) or len(tables) != value["output_table_count"]:
        return False
    fragments = []
    local_blockers: set[str] = set()
    local_warnings: set[str] = set()
    for table in tables:
        if not isinstance(table, dict) or not isinstance(table.get("fragments"), list):
            return False
        table_blockers, table_warnings = table.get("blocking_quality_flags"), table.get("warning_flags")
        if (
            not isinstance(table_blockers, list)
            or any(not isinstance(flag, str) or flag not in QUALITY_BLOCKERS for flag in table_blockers)
            or not isinstance(table_warnings, list)
            or any(not isinstance(flag, str) or flag not in QUALITY_WARNINGS for flag in table_warnings)
            or table.get("group_status") != ("blocked" if table_blockers else "warning" if table_warnings else "passed")
        ):
            return False
        local_blockers.update(table_blockers)
        local_warnings.update(table_warnings)
        if (type(table.get("expected_rows")) is not int or table["expected_rows"] <= 0 or
                table.get("actual_rows") != table["expected_rows"] or
                table.get("actual_header_rows") != table.get("expected_header_rows")):
            return False
        cursor = 0
        has_missing_fragment = False
        owners = {}
        covered_ranges = []
        for fragment in table["fragments"]:
            if not isinstance(fragment, dict) or not isinstance(fragment.get("fragment_id"), str):
                return False
            status = fragment.get("status")
            if not isinstance(status, str) or status not in {"rendered", "header_only", "empty", "missing"}:
                return False
            interval = fragment.get("output_rows")
            if (not isinstance(interval, list) or len(interval) != 2 or
                    any(type(number) is not int or number < 0 for number in interval) or
                    fragment.get("actual_output_rows") != interval):
                return False
            if status in {"empty", "missing"}:
                if interval != [0, 0] or fragment.get("block_id") is not None or fragment.get("bookmark") is not None:
                    return False
                covered = fragment.get("upstream_covered_rows")
                if fragment.get("html_state") != status:
                    return False
                if covered is None:
                    if fragment.get("reason") != "table_fragment_missing":
                        return False
                    has_missing_fragment = True
                else:
                    owner = fragment.get("render_owner_block_id")
                    if (status != "empty" or fragment.get("reason") is not None or not isinstance(owner, str)
                            or not isinstance(covered, list) or len(covered) != 2
                            or any(type(row) is not int for row in covered) or not 0 <= covered[0] < covered[1]):
                        return False
                    covered_ranges.append((owner, covered))
            else:
                if ("upstream_covered_rows" in fragment or interval[0] != cursor or interval[1] < interval[0]
                        or (status == "rendered" and interval[1] == cursor)):
                    return False
                if isinstance(fragment.get("block_id"), str):
                    owners[fragment["block_id"]] = interval
                cursor = interval[1]
            fragments.append(fragment)
        if (cursor != table["expected_rows"] or any(owner not in owners
                or not owners[owner][0] <= rows[0] < rows[1] == owners[owner][1] for owner, rows in covered_ranges)):
            return False
        if has_missing_fragment != ("table_fragment_missing" in table_blockers):
            return False
    if len(fragments) != value["fragment_count"]:
        return False
    if set(blockers) != local_blockers or set(warnings) != local_warnings:
        return False
    ids = [fragment["fragment_id"] for fragment in fragments]
    return (len(set(ids)) == len(ids) and
            type(value.get("placeholder_table_block_count", 0)) is int and value.get("placeholder_table_block_count", 0) >= 0 and
            sum(fragment.get("block_id") is not None for fragment in fragments) + value.get("placeholder_table_block_count", 0) == value["source_table_block_count"] and
            value["source_table_block_count"] - value["consumed_block_count"] - value.get("placeholder_table_block_count", 0) == value["output_table_count"] and
            sum(fragment.get("status") == "empty" for fragment in fragments) == value["empty_fragment_count"] and
            sum(fragment.get("status") == "missing" for fragment in fragments) == value["missing_fragment_count"])
