"""原始 MinerU 结构、字段与资产验证；不承担语义转换或发布判断。"""
from __future__ import annotations

import io
import hashlib
import json
import math
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.image.image import Image as WordImage
from pydantic import BaseModel, Field

from app.conversion.docx_rules.mineru_content import (
    classify_mineru_block, coerce_text_list, collect_text_from_fields, looks_like_asset_path,
    mineru_list_items, mineru_raw_text_preserving_lines, select_mineru_list_source, select_mineru_table_html,
    select_mineru_text_source,
)
from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.mineru_package import (
    DEFAULT_POLICY, MinerUPackageError, MinerUValidationPolicy, resolve_asset_path,
)


ALLOWED_RASTER_FORMATS = frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"})
SEMANTIC_TEXT_FIELDS = frozenset({"text", "latex", "math_content", "equation_content", "description", "alt"})
SEMANTIC_RUN_FIELDS = frozenset({"title_content", "paragraph_content", "page_header_content", "page_footer_content", "page_number_content", "item_content"})
ANNOTATION_FIELDS = frozenset({"caption", "footnote", "captions", "footnotes", "table_caption", "table_footnote",
                               "image_caption", "image_footnote", "chart_caption", "chart_footnote", "figure_caption", "figure_footnote"})
KNOWN_SOURCE_TYPES = frozenset({"text", "paragraph", "para", "title", "heading", "header", "footer", "page_header", "page_footer",
                               "page_number", "table", "table_placeholder", "image", "chart", "figure", "list", "index",
                               "equation", "formula", "interline_equation", "inline_equation", "equation_interline"})
REPORT_FIELD_NAMES = (SEMANTIC_TEXT_FIELDS | SEMANTIC_RUN_FIELDS | ANNOTATION_FIELDS | {
    "", "type", "block_type", "content", "content_list", "items", "list_items", "bbox", "page_idx", "page_index",
    "html", "table_html", "table_body", "image_source", "img_path", "image_path", "path",
})
UNICODE_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def _safe_field(field: str | None) -> str | None:
    if field is None:
        return None
    return "/".join(
        part if part in REPORT_FIELD_NAMES or part.isdecimal() else
        "unknown_" + hashlib.sha256(part.encode("utf-8")).hexdigest()[:12]
        for part in field.split("/")
    )[:240]


def _issue_order(issue: MinerUValidationIssue) -> tuple:
    return (tuple((0, int(part)) if part.isdecimal() else (1, part) for part in issue.json_pointer.split("/")),
            issue.code, issue.field or "")


class MinerUSourceLocator(BaseModel):
    json_pointer: str
    page_index: int | None = None
    source_index_in_page: int | None = None
    source_index: int | None = None
    source_type: str | None = None


class MinerUValidationIssue(MinerUSourceLocator):
    code: str
    severity: Literal["warning", "blocker"]
    stops_conversion: bool = False
    field: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


class MinerUTableCheck(MinerUSourceLocator):
    classification: Literal["html_present_and_parseable", "html_present_but_suspicious",
                            "html_missing_reference_present", "html_missing_reference_missing"]
    row_count: int = 0
    cell_count: int = 0
    reference_status: str
    reference_resolution: str | None = None
    parseable: bool = False


class MinerUValidationReport(BaseModel):
    """计数是聚合权威；超限报告必须明确未完成，不能用截断明细证明通过。"""

    schema_version: Literal["mineru-artifact-validation/v1"] = "mineru-artifact-validation/v1"
    validator_version: str = "mineru-artifact-validator/v3"
    policy_version: str = DEFAULT_POLICY.version
    package_sha256: str
    content_list_path: str | None = None
    content_list_sha256: str | None = None
    inventory: dict[str, Any] = Field(default_factory=dict)
    effective_inventory: dict[str, Any] = Field(default_factory=dict)
    normalization: dict[str, Any] = Field(default_factory=dict)
    warnings: list[MinerUValidationIssue] = Field(default_factory=list)
    blockers: list[MinerUValidationIssue] = Field(default_factory=list)
    issue_counts: dict[str, dict[str, int]] = Field(default_factory=lambda: {"warning": {}, "blocker": {}})
    warning_count: int = 0
    blocker_count: int = 0
    fatal_count: int = 0
    first_fatal: MinerUValidationIssue | None = None
    details_truncated: bool = False
    omitted_issue_count: int = 0
    table_checks: list[MinerUTableCheck] = Field(default_factory=list)
    table_check_count: int = 0
    omitted_table_check_count: int = 0
    complete: bool = True
    can_convert: bool = True

    def sort_details(self) -> None:
        """按原始位置和 code 稳定排序，不改变有界报告已保留的首个失败。"""
        self.warnings.sort(key=_issue_order)
        self.blockers.sort(key=_issue_order)
        if not self.details_truncated:
            self.first_fatal = next((issue for issue in self.blockers if issue.stops_conversion), None)


class MinerUArtifactValidationError(ValueError):
    """输入 fatal，调用方必须保留报告并停止转换。"""

    def __init__(self, report: MinerUValidationReport) -> None:
        report.sort_details()
        self.report = report
        code = report.first_fatal.code if report.first_fatal else "mineru_input_invalid"
        super().__init__(f"MinerU 产物验证失败：{code}。")


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    source_path: str
    mime_type: str
    content: bytes
    resolution: str


@dataclass(slots=True)
class _ImageInspection:
    """单次验证中按规范文件复用栅格探测；Word 能力另行缓存，不能替代参考图能力。"""

    content: bytes = b""
    mime_type: str | None = None
    error_code: str | None = None
    error_reason: str | None = None
    word_supported: bool | None = None


@dataclass(frozen=True, slots=True)
class MinerUValidatedContent:
    blocks: list[dict[str, Any]]
    report: MinerUValidationReport


def bbox_invalid_reason(value: Any) -> str | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return "wrong_length_or_type"
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return "non_numeric"
    try:
        if not all(math.isfinite(item) for item in value):
            return "non_finite"
    except OverflowError:
        return "non_finite"
    if value[2] <= value[0] or value[3] <= value[1]:
        return "non_positive_area"
    return None


def parse_valid_bbox(value: Any) -> tuple[float, float, float, float] | None:
    return tuple(float(item) for item in value) if bbox_invalid_reason(value) is None else None


class _HTMLSignals(HTMLParser):
    """仅检查基本标记/原始 span，不构建另一套表格或访问外部资源。"""

    def __init__(self) -> None:
        super().__init__()
        self.reasons: set[str] = set()
        self.table_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.table_depth += 1
            if self.table_depth > 1:
                self.reasons.add("nested_table")
        if tag not in {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "col", "colgroup",
                       "p", "br", "b", "strong", "i", "em", "u", "span", "sub", "sup"}:
            self.reasons.add("unsupported_tag")
        for name, value in attrs:
            if name in {"rowspan", "colspan"} and (value is None or len(value) > 9 or not re.fullmatch(r"[0-9]+", value) or int(value) < 1):
                self.reasons.add("invalid_span")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self.table_depth -= 1


class MinerUArtifactValidator:
    """验证原始数组，再生成唯一用于转换的安全内存视图。"""

    def __init__(self, report: MinerUValidationReport, *, policy: MinerUValidationPolicy = DEFAULT_POLICY) -> None:
        self.report = report
        self.policy = policy
        self._seen: set[tuple[str, str, str | None]] = set()
        self._image_cache: dict[Path, _ImageInspection] = {}
        self._contentful_table_sources: set[str] = set()
        self.check_report_limits()

    def add_issue(self, code: str, locator: MinerUSourceLocator | None = None, *,
                  severity: Literal["warning", "blocker"] = "blocker", stops_conversion: bool = True,
                  field: str | None = None, facts: dict[str, Any] | None = None) -> None:
        locator = locator or MinerUSourceLocator(json_pointer="")
        key = (code, locator.json_pointer, field)
        if key in self._seen:
            return
        self._seen.add(key)
        issue = MinerUValidationIssue(**locator.model_dump(), code=code, severity=severity,
                                     stops_conversion=stops_conversion, field=_safe_field(field), facts=facts or {})
        counts = self.report.issue_counts[severity]
        counts[code] = counts.get(code, 0) + 1
        if severity == "warning":
            self.report.warning_count += 1
            details = self.report.warnings
        else:
            self.report.blocker_count += 1
            details = self.report.blockers
        details.append(issue)
        if stops_conversion:
            self.report.fatal_count += 1
            self.report.can_convert = False
            if self.report.first_fatal is None:
                self.report.first_fatal = issue
        self.check_report_limits()

    def _report_bytes(self) -> int:
        return len(json.dumps(self.report.model_dump(mode="json"), ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def check_report_limits(self) -> None:
        """所有报告写入边界共用此检查；问题总条数与完整 UTF-8 JSON 分别受限。"""
        if len(self.report.warnings) + len(self.report.blockers) >= self.policy.max_issue_details:
            self._stop_for_report_limit("issue_details")
        if self._report_bytes() >= self.policy.max_report_bytes:
            self._stop_for_report_limit("report_bytes")

    def _stop_for_report_limit(self, reason: str) -> None:
        """保留已发现计数，压缩失败定位以容纳超限原因，然后立即停止本次验证。"""
        report = self.report
        limit_issue = MinerUValidationIssue(json_pointer="", code="report_limit_exceeded", severity="blocker",
                                           stops_conversion=True, facts={"reason": reason})
        report.complete = False
        report.can_convert = False
        report.fatal_count += 1
        report.blocker_count += 1
        report.issue_counts["blocker"][limit_issue.code] = 1
        report.first_fatal = report.first_fatal or limit_issue
        report.blockers.append(limit_issue)
        report.details_truncated = True

        def remove_issue_detail() -> bool:
            if report.warnings:
                report.warnings.pop()
            elif len(report.blockers) > 1:
                report.blockers.pop(-2)
            else:
                return False
            report.omitted_issue_count += 1
            return True

        while len(report.warnings) + len(report.blockers) > self.policy.max_issue_details:
            if not remove_issue_detail():
                report.blockers.clear()
                report.omitted_issue_count += 1
                break
        while self._report_bytes() >= self.policy.max_report_bytes and remove_issue_detail():
            pass
        while self._report_bytes() >= self.policy.max_report_bytes and report.table_checks:
            report.table_checks.pop()
            report.omitted_table_check_count += 1
        merged = report.normalization.get("merged_table_placeholders", [])
        while self._report_bytes() >= self.policy.max_report_bytes and merged:
            merged.pop()
            report.normalization["omitted_merged_table_placeholder_count"] = (
                report.normalization.get("omitted_merged_table_placeholder_count", 0) + 1
            )
        filtered = report.normalization.get("filtered_blocks", [])
        while self._report_bytes() >= self.policy.max_report_bytes and filtered:
            filtered.pop()
            report.normalization["omitted_filtered_block_count"] = report.normalization.get("omitted_filtered_block_count", 0) + 1
        # 大量未知类型标签和超长包内定位属于明细；总体块数与 issue 计数仍保留。
        for inventory in (report.inventory, report.effective_inventory):
            types = inventory.get("type_counts", {})
            while self._report_bytes() >= self.policy.max_report_bytes and types:
                types.popitem()
                inventory["omitted_type_count"] = inventory.get("omitted_type_count", 0) + 1
        if self._report_bytes() >= self.policy.max_report_bytes:
            report.content_list_path = None
        if self._report_bytes() >= self.policy.max_report_bytes and "filtered_promotional_page_index" in report.normalization:
            report.normalization["filtered_promotional_page_index"] = None
        if self._report_bytes() >= self.policy.max_report_bytes and report.first_fatal is not limit_issue:
            report.first_fatal = MinerUValidationIssue(json_pointer="", code=report.first_fatal.code,
                                                       severity="blocker", stops_conversion=True)
        raise MinerUArtifactValidationError(report)

    def record_normalization(self, blocks_before_merge: list[dict[str, Any]], effective_blocks: list[dict[str, Any]],
                             *, filtered_page_index: int | None, filtered_block_count: int,
                             merge_evidence: list[dict[str, Any]] | None = None,
                             filtered_sources: list[dict[str, Any]] | None = None) -> None:
        """只对账既有归一化的实际结果，不在报告层重新判定空表或执行合并。"""
        retained = {block["_mineru_source"]["json_pointer"] for block in effective_blocks}
        merged = merge_evidence or []
        removed = {block["_mineru_source"]["json_pointer"] for block in blocks_before_merge} - retained
        if removed != {receipt["json_pointer"] for receipt in merged}:
            self.add_issue("mineru_block_invalid", facts={"reason": "unaccounted_normalization"})
            raise MinerUArtifactValidationError(self.report)
        # 坏 HTML 保留既有 invalid_table_html 分类，由完成门提升为 fatal。
        invalid_html_sources = {issue.json_pointer for issue in self.report.blockers if issue.code == "invalid_table_html"}
        contentful_removed = (removed & self._contentful_table_sources) - invalid_html_sources
        for block in blocks_before_merge:
            if block["_mineru_source"]["json_pointer"] in contentful_removed:
                # 只检查归并 owner 真正删除的节点，不复制其候选判据，也不改旧完整性失败。
                self._payload_issue(MinerUSourceLocator.model_validate(block["_mineru_source"]),
                                    "content", "contentful_table_placeholder")
        resolved_pointers = {locator["json_pointer"] for locator in merged} - contentful_removed
        resolved = Counter(issue.code for issue in self.report.blockers
                           if issue.code == "empty_table_html" and issue.json_pointer in resolved_pointers)
        self.report.effective_inventory = {
            "block_count": len(effective_blocks),
            "type_counts": dict(sorted(Counter(block["_mineru_source"]["source_type"] for block in effective_blocks).items())),
        }
        self.report.normalization = {
            "filtered_promotional_page_index": filtered_page_index,
            "filtered_block_count": filtered_block_count,
            "filtered_blocks": filtered_sources or [],
            "merged_table_placeholder_count": len(merged),
            "merged_table_placeholders": merged,
            "resolved_issue_counts": {"blocker": dict(sorted(resolved.items()))},
        }
        self.check_report_limits()
        if not self.report.can_convert:
            raise MinerUArtifactValidationError(self.report)

    def complete_validation(self, effective_blocks: list[dict[str, Any]], *, package_root: Path,
                            content_list_path: Path) -> None:
        """既有归一化完成后验证保留对象；原始安全问题始终在此前阻断。"""
        filtered = {source["json_pointer"] for source in self.report.normalization.get("filtered_blocks", [])}
        for issue in self.report.blockers:
            # 旧空表判据只读取可识别 HTML；非空坏 HTML 不能借合并回执获得空表豁免。
            if issue.code == "invalid_table_html" and issue.json_pointer not in filtered and not issue.stops_conversion:
                issue.stops_conversion = True
                self.report.fatal_count += 1
                self.report.can_convert = False
                self.report.first_fatal = self.report.first_fatal or issue
        for block in effective_blocks:
            locator = MinerUSourceLocator.model_validate(block["_mineru_source"])
            if classify_mineru_block(block, locator.source_type or "") == "image":
                asset, _status = self._validate_asset(block, locator, package_root, content_list_path.parent, required=True)
                block["_mineru_validated_asset"] = asset
        self.check_report_limits()
        if not self.report.can_convert:
            raise MinerUArtifactValidationError(self.report)
        self.report.sort_details()

    def add_package_error(self, error: MinerUPackageError, *, field: str | None = None) -> None:
        self.add_issue(error.code, field=field, facts=error.facts)

    def validate(self, payload: Any, *, package_root: Path, content_list_path: Path) -> MinerUValidatedContent:
        # JSON 解码已把合法 surrogate pair 合成字符；残留码位不能进入正文或 UTF-8 报告。
        pending = [payload]
        while pending:
            node = pending.pop()
            if isinstance(node, str):
                if UNICODE_SURROGATE_RE.search(node):
                    self.add_issue("mineru_json_invalid", facts={"reason": "isolated_unicode_surrogate"})
                    raise MinerUArtifactValidationError(self.report)
            elif isinstance(node, dict):
                pending.extend(node)
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        prefix = ""
        if isinstance(payload, dict):
            prefix = "/content_list"
            payload = payload.get("content_list")
        if not isinstance(payload, list):
            self.add_issue("mineru_json_invalid", facts={"reason": "unsupported_top_level"})
            raise MinerUArtifactValidationError(self.report)
        nested = any(isinstance(item, list) for item in payload)
        inventory = self.report.inventory
        inventory.update(input_shape=("wrapper_" if prefix else "") + ("nested" if nested else "flat"),
                         raw_page_count=len(payload) if nested else 0, raw_block_count=0,
                         valid_block_count=0, invalid_block_count=0, invalid_page_count=0,
                         type_counts={}, image_check_count=0, table_reference_check_count=0)
        normalized: list[dict[str, Any]] = []
        type_counts = inventory["type_counts"]
        flat_offsets: Counter[int] = Counter()
        flat_pages: set[int] = set()
        previous_page = None
        for outer_index, item in enumerate(payload):
            outer_pointer = f"{prefix}/{outer_index}"
            if nested and not isinstance(item, list):
                inventory["invalid_page_count"] += 1
                self.add_issue("mineru_page_invalid", MinerUSourceLocator(json_pointer=outer_pointer),
                               facts={"reason": "mixed_or_invalid_page", "actual_type": type(item).__name__})
                continue
            if nested and not item:
                self.add_issue("mineru_page_empty", MinerUSourceLocator(json_pointer=outer_pointer, page_index=outer_index),
                               severity="warning", stops_conversion=False, facts={"reason": "no_blocks"})
            for local_index, block in enumerate(item if nested else [item]):
                source_index = inventory["raw_block_count"]
                inventory["raw_block_count"] += 1
                pointer = f"{outer_pointer}/{local_index}" if nested else outer_pointer
                locator = MinerUSourceLocator(json_pointer=pointer, source_index=source_index,
                                              page_index=outer_index if nested else None,
                                              source_index_in_page=local_index if nested else None)
                if not isinstance(block, dict):
                    inventory["invalid_block_count"] += 1
                    self.add_issue("mineru_block_invalid", locator, facts={"reason": "not_object"})
                    continue
                before = self.report.fatal_count
                source_type = block.get("type", block.get("block_type"))
                if not isinstance(source_type, str) or not source_type.strip():
                    self.add_issue("mineru_block_invalid", locator, field="type", facts={"reason": "missing_or_invalid_type"})
                    source_type = ""
                else:
                    source_type = source_type.strip().lower()
                    # 不保存未知的任意长 type 原文；计数和定位只用有限标签。
                    if len(source_type) > 80:
                        self.add_issue("mineru_block_invalid", locator, field="type", facts={"reason": "type_too_long"})
                        source_type = "invalid"
                locator.source_type = source_type if source_type in KNOWN_SOURCE_TYPES else "unsupported" if source_type else "invalid"
                type_counts[locator.source_type] = type_counts.get(locator.source_type, 0) + 1
                explicit_pages = []
                explicit_page_invalid = False
                for key in ("page_idx", "page_index"):
                    if key in block:
                        value = block[key]
                        page = self._page_index(value)
                        if page is None:
                            explicit_page_invalid = True
                            self.add_issue("mineru_page_invalid", locator, field=key, facts={"reason": "invalid_index"})
                        else:
                            explicit_pages.append(page)
                            if isinstance(value, str):
                                self.add_issue("legacy_page_index_coerced", locator, severity="warning", stops_conversion=False,
                                               field=key, facts={"page_index": page})
                if len(set(explicit_pages)) > 1 or (nested and any(page != outer_index for page in explicit_pages)):
                    explicit_page_invalid = True
                    self.add_issue("mineru_page_invalid", locator, field="page_idx", facts={"reason": "conflicting_index"})
                if not nested:
                    if not explicit_pages and not any(key in block for key in ("page_idx", "page_index")):
                        self.add_issue("mineru_page_missing", locator, severity="warning", stops_conversion=False,
                                       field="page_idx", facts={"reason": "missing_index"})
                    elif explicit_pages:
                        locator.page_index = explicit_pages[0]
                        locator.source_index_in_page = flat_offsets[locator.page_index]
                        flat_offsets[locator.page_index] += 1
                        flat_pages.add(locator.page_index)
                        inventory["raw_page_count"] = len(flat_pages)
                        if not explicit_page_invalid:
                            if previous_page is not None and locator.page_index < previous_page:
                                self.add_issue("mineru_page_order_nonmonotonic", locator, severity="warning", stops_conversion=False)
                            elif previous_page is not None and locator.page_index > previous_page + 1:
                                self.add_issue("mineru_page_gap", locator, severity="warning", stops_conversion=False,
                                               facts={"previous_page_index": previous_page,
                                                      "index_gap": locator.page_index - previous_page - 1})
                            previous_page = locator.page_index
                copied = dict(block)
                if locator.page_index is not None:
                    copied["page_idx"] = locator.page_index
                copied["_mineru_source"] = locator.model_dump()
                if "bbox" not in block:
                    self.add_issue("mineru_bbox_missing", locator, severity="warning", stops_conversion=False, field="bbox")
                    copied.pop("bbox", None)
                elif reason := bbox_invalid_reason(block["bbox"]):
                    self.add_issue("mineru_bbox_invalid", locator, field="bbox", facts={"reason": reason})
                self._validate_type_nodes(block, locator)
                effective_type = classify_mineru_block(block, source_type)
                self._validate_fields(block, source_type, effective_type, locator)
                self._validate_asset_paths(block, locator, package_root, content_list_path.parent)
                if effective_type == "image":
                    inventory["image_check_count"] += 1
                if effective_type == "table":
                    inventory["table_reference_check_count"] += 1
                    asset, status = self._validate_asset(block, locator, package_root, content_list_path.parent, required=False)
                    self._validate_table(block, locator, status, asset)
                if self.report.fatal_count == before:
                    inventory["valid_block_count"] += 1
                else:
                    inventory["invalid_block_count"] += 1
                normalized.append(copied)
                self.check_report_limits()
        if not nested:
            inventory["raw_page_count"] = len(flat_pages)
        inventory["type_counts"] = dict(sorted(type_counts.items()))
        self.check_report_limits()
        if not inventory["raw_block_count"]:
            self.add_issue("mineru_content_empty", facts={"reason": "no_blocks"})
        if not self.report.can_convert:
            raise MinerUArtifactValidationError(self.report)
        return MinerUValidatedContent(blocks=normalized, report=self.report)

    @staticmethod
    def _page_index(value: Any) -> int | None:
        if type(value) is int and value >= 0:
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) and len(value) <= 18:
            return int(value)
        return None

    def _validate_type_nodes(self, block: dict[str, Any], locator: MinerUSourceLocator) -> None:
        """共享分类/正文 helper 前拒绝其不支持的不可哈希 type，保留结构化定位。"""
        pending = [(block, locator.json_pointer)]
        while pending:
            node, pointer = pending.pop()
            if isinstance(node, dict):
                if isinstance(node.get("type"), (dict, list)):
                    self._payload_issue(locator, f"{pointer}/type", "expected_type_string")
                    raise MinerUArtifactValidationError(self.report)
                pending.extend((value, f"{pointer}/{key}") for key, value in node.items())
            elif isinstance(node, list):
                pending.extend((value, f"{pointer}/{index}") for index, value in enumerate(node))

    def _validate_fields(self, block: dict[str, Any], source_type: str, effective_type: str, locator: MinerUSourceLocator) -> None:
        text_keys = SEMANTIC_TEXT_FIELDS
        run_keys = SEMANTIC_RUN_FIELDS
        annotation_keys = ANNOTATION_FIELDS
        fatal_count_before = self.report.fatal_count
        readable = False
        contentful_placeholder = False
        invalid_placeholder_html_field: str | None = None
        readable_fields: list[str] = []
        content = block.get("content")
        list_selection = select_mineru_list_source(block) if effective_type == "list" else None
        v2_list_selected = list_selection is not None and list_selection[1] == "v2_items"
        def visit(node: Any, pointer: str, key: str | None = None, *, raw_html: bool = False,
                  content_array: bool = False) -> None:
            nonlocal readable, contentful_placeholder, invalid_placeholder_html_field
            raw_html = raw_html or key in {"html", "table_html", "table_body"}
            if (isinstance(node, dict) and pointer != locator.json_pointer
                    and node.get("type") in ("text", "equation_inline", "inline_formula")
                    and not isinstance(node.get("content"), str)):
                # 已知 typed run 的必需字段必须先验类型，不能把畸形值当作空占位符。
                self._payload_issue(locator, f"{pointer}/content", "expected_string")
            if (source_type == "table_placeholder" and key in {"html", "table_html", "table_body"}
                    and not isinstance(node, str)):
                invalid_placeholder_html_field = invalid_placeholder_html_field or pointer
            if source_type == "table_placeholder" or effective_type == "table":
                if raw_html and isinstance(node, str) and node.strip():
                    contentful_placeholder = True
                elif (key == "content" or content_array) and isinstance(node, str) and coerce_text_list(node):
                    contentful_placeholder = True
                elif (isinstance(node, dict) and node.get("type") in ("text", "equation_inline", "inline_formula")
                      and coerce_text_list(node)):
                    contentful_placeholder = True
            if key in text_keys:
                if not isinstance(node, str):
                    self._payload_issue(locator, pointer, "expected_string")
                else:
                    if node.strip():
                        readable = True
                        readable_fields.append(pointer)
                return
            if key in run_keys:
                if not isinstance(node, list):
                    self._payload_issue(locator, pointer, "expected_runs")
                else:
                    self._validate_text_tree(node, locator, pointer, require_runs=True)
                    if coerce_text_list(node):
                        readable = True
                        readable_fields.append(pointer)
                return
            if key in annotation_keys:
                self._validate_text_tree(node, locator, pointer)
                return
            if key in {"items", "list_items"}:
                if not isinstance(node, list):
                    self._payload_issue(locator, pointer, "expected_list")
                else:
                    for index, item in enumerate(node):
                        if v2_list_selected and pointer == f"{locator.json_pointer}/content/list_items":
                            child_pointer = f"{pointer}/{index}/item_content"
                            if not isinstance(item, dict) or not isinstance(item.get("item_content"), list):
                                self._payload_issue(locator, child_pointer, "expected_runs")
                            else:
                                self._validate_text_tree(item["item_content"], locator, child_pointer, require_runs=True)
                            if isinstance(item, dict):
                                self._reject_unconsumed_fields(item, {"item_content"}, locator,
                                                               f"{pointer}/{index}", "outside_selected_list_payload")
                        else:
                            # legacy 消费整个 item 的 coerce 选择，不能仅验证 item_content 旁支。
                            self._validate_text_tree(item, locator, f"{pointer}/{index}")
                    readable |= bool(coerce_text_list(node))
                return
            if isinstance(node, dict):
                for child_key, child in node.items():
                    visit(child, f"{pointer}/{child_key}", child_key, raw_html=raw_html)
            elif isinstance(node, list):
                for index, child in enumerate(node):
                    # content 数组保留正文语义；字典仍仅按已知字段识别，不扫描结构 metadata。
                    visit(child, f"{pointer}/{index}", raw_html=raw_html,
                          content_array=content_array or key == "content")
        visit(block, locator.json_pointer)
        content = block.get("content")
        if "content" in block:
            if isinstance(content, str):
                readable |= bool(coerce_text_list(content))
            elif isinstance(content, list):
                # legacy content 列表既可含 runs，也可含 HTML/资产容器。
                for index, item in enumerate(content):
                    if isinstance(item, str) or isinstance(item, dict) and "type" in item:
                        self._validate_text_tree(item, locator, f"{locator.json_pointer}/content/{index}")
                        readable |= bool(coerce_text_list(item))
                    elif not isinstance(item, dict):
                        self._payload_issue(locator, f"{locator.json_pointer}/content/{index}", "invalid_content_node")
            elif not isinstance(content, dict):
                self._payload_issue(locator, "content", "invalid_content_type")
        if effective_type == "formula" and isinstance(content, dict) and any(
            key in content for key in ("math_content", "math_type", "image_source")
        ):
            math_content = content.get("math_content")
            if not isinstance(math_content, str) or not math_content.strip():
                self._payload_issue(locator, "content/math_content", "missing_readable_formula")
        selected = select_mineru_text_source(block)
        consumes_selected_text = effective_type in {"paragraph", "heading"} or (
            list_selection is not None and list_selection[1] == "selected_text"
        )
        if consumes_selected_text and selected is not None:
            selected_field, _selected_value, mode = selected
            selected_pointer = f"{locator.json_pointer}/{selected_field}"
            if mode in {"runs", "string"}:
                for field in readable_fields:
                    if field != selected_pointer and not field.startswith(selected_pointer + "/"):
                        self._payload_issue(locator, field, "outside_selected_rich_payload")
        if list_selection is not None and list_selection[1] in {"legacy_items", "v2_items"}:
            selected_pointer = f"{locator.json_pointer}/{list_selection[0]}"
            for field in readable_fields:
                if field != selected_pointer and not field.startswith(selected_pointer + "/"):
                    self._payload_issue(locator, field, "outside_selected_list_payload")
        candidate_values = [block.get("text"), content, block.get("caption")]
        if effective_type == "formula":
            candidate_values.extend(block.get(key) for key in ("latex", "math_content", "equation_content"))
        if effective_type == "list":
            candidate_values.extend(block.get(key) for key in ("items", "list_items"))
        if effective_type in {"paragraph", "heading"}:
            retained_readable = (readable and bool(mineru_raw_text_preserving_lines(block).strip())) or bool(
                coerce_text_list(block.get("caption"))
            )
        elif list_selection is not None:
            retained_readable = (self.report.fatal_count == fatal_count_before and readable and bool(mineru_list_items(block)))
        else:
            retained_readable = effective_type in {"table", "image"} or (readable and any(
                coerce_text_list(value) for value in candidate_values
            ))
        if source_type not in KNOWN_SOURCE_TYPES:
            self.add_issue("unsupported_block_type", locator, severity="warning" if retained_readable else "blocker",
                           stops_conversion=not retained_readable, facts={"readable_payload": retained_readable})
        elif effective_type not in {"table", "image"} and source_type != "table_placeholder" and not retained_readable:
            margin_field = {"page_header": "page_header_content", "page_footer": "page_footer_content",
                            "page_number": "page_number_content"}.get(source_type)
            if margin_field is not None and isinstance(content, dict) and content.get(margin_field) == []:
                # MinerU 正式样本包含合法空边缘 runs；保留节点与定位，空正文仍需失败关闭。
                self.add_issue("mineru_margin_payload_empty", locator, severity="warning", stops_conversion=False,
                               field=margin_field)
            else:
                self._payload_issue(locator, "content", "missing_readable_payload")
        has_placeholder_content = (
            contentful_placeholder or readable or select_mineru_table_html(block)
            or collect_text_from_fields(block, tuple(annotation_keys))
        )
        if effective_type == "table" and has_placeholder_content:
            self._contentful_table_sources.add(locator.json_pointer)
        if source_type == "table_placeholder" and has_placeholder_content:
            # 既有显式占位符只表达续页高度，不能利用该标签静默删除技术内容。
            self._payload_issue(locator, "content", "contentful_table_placeholder")
        elif source_type == "table_placeholder" and invalid_placeholder_html_field is not None:
            self._payload_issue(locator, invalid_placeholder_html_field, "expected_string")

    def _payload_issue(self, locator: MinerUSourceLocator, field: str, reason: str) -> None:
        self.add_issue("mineru_block_payload_invalid", locator, field=field, facts={"reason": reason})

    def _reject_unconsumed_fields(self, node: dict[str, Any], consumed: set[str], locator: MinerUSourceLocator,
                                  pointer: str, reason: str) -> None:
        """检查已知语义旁支；未知结构 metadata 不凭空当作正文或一律拒绝。"""
        for key, value in node.items():
            if key in consumed:
                continue
            field = f"{pointer}/{key}"
            if key in SEMANTIC_TEXT_FIELDS:
                if not isinstance(value, str):
                    self._payload_issue(locator, field, "expected_string")
                elif value.strip():
                    self._payload_issue(locator, field, reason)
            elif key in SEMANTIC_RUN_FIELDS or key in {"items", "list_items"}:
                if not isinstance(value, list):
                    self._payload_issue(locator, field, "expected_runs" if key in SEMANTIC_RUN_FIELDS else "expected_list")
                elif value:
                    self._payload_issue(locator, field, reason)
            elif key == "content":
                if not isinstance(value, (str, list, dict)):
                    self._payload_issue(locator, field, "invalid_content_type")
                elif coerce_text_list(value):
                    self._payload_issue(locator, field, reason)

    def _validate_text_tree(self, node: Any, locator: MinerUSourceLocator, pointer: str, *, require_runs: bool = False) -> None:
        if isinstance(node, str) and not require_runs:
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                if require_runs and not isinstance(child, dict):
                    self._payload_issue(locator, f"{pointer}/{index}", "invalid_text_node")
                else:
                    self._validate_text_tree(child, locator, f"{pointer}/{index}", require_runs=require_runs)
            return
        if isinstance(node, dict):
            if isinstance(node.get("type"), str) and node.get("type") and isinstance(node.get("content"), str):
                if require_runs or node["type"] in {"text", "equation_inline", "inline_formula"}:
                    # typed runs 只消费 content；非空正文旁支不能在验证后被静默丢弃。
                    self._reject_unconsumed_fields(node, {"content"}, locator, pointer, "outside_selected_rich_payload")
                return
            if not require_runs and any(key in node for key in SEMANTIC_TEXT_FIELDS | SEMANTIC_RUN_FIELDS | {"content", "items", "list_items"}):
                for key, value in node.items():
                    field = f"{pointer}/{key}"
                    if key in SEMANTIC_TEXT_FIELDS:
                        if not isinstance(value, str):
                            self._payload_issue(locator, field, "expected_string")
                    elif key in SEMANTIC_RUN_FIELDS:
                        if not isinstance(value, list):
                            self._payload_issue(locator, field, "expected_runs")
                        else:
                            self._validate_text_tree(value, locator, field, require_runs=True)
                    elif key in {"content", "items", "list_items"}:
                        self._validate_text_tree(value, locator, field)
                return
        self._payload_issue(locator, pointer, "invalid_text_node")

    @staticmethod
    def _asset_paths(block: dict[str, Any], locator: MinerUSourceLocator, *, include_all_strings: bool = False) -> list[tuple[str, Any]]:
        """具名路径保持优先；只在资产载体收集 legacy 引用，不把正文当路径扫描。"""
        paths: list[tuple[str, Any]] = []
        legacy_paths: list[tuple[str, Any]] = []
        other_asset_strings: list[tuple[str, Any]] = []
        legacy_content_allowed = classify_mineru_block(block, locator.source_type or "") in {"image", "table"}
        def collect(node: Any, pointer: str, *, asset_strings: bool = False, legacy_content: bool = False) -> None:
            if isinstance(node, dict):
                # 与既有抽取规则一致，直接 typed path 优先于嵌套引用，不依赖字典字段排列。
                for key in ("img_path", "image_path", "path"):
                    if key in node:
                        paths.append((f"{pointer}/{key}", node[key]))
                for key, value in node.items():
                    if key not in {"img_path", "image_path", "path"}:
                        collect(value, f"{pointer}/{key}",
                                asset_strings=(asset_strings and key != "type") or key == "image_source",
                                legacy_content=key == "content" and (legacy_content or
                                    pointer == locator.json_pointer and legacy_content_allowed))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    collect(value, f"{pointer}/{index}", asset_strings=asset_strings, legacy_content=legacy_content)
            elif isinstance(node, str) and (asset_strings or legacy_content):
                if looks_like_asset_path(node):
                    legacy_paths.append((pointer, node))
                elif asset_strings:
                    other_asset_strings.append((pointer, node))
        collect(block, locator.json_pointer)
        # legacy 原先只选择首个图片形态字符串；其他显式引用仅验安全，不能变成新资产消费协议。
        return paths + legacy_paths + (other_asset_strings if include_all_strings else [])

    def _validate_asset_paths(self, block: dict[str, Any], locator: MinerUSourceLocator,
                              root: Path, content_dir: Path) -> None:
        """所有原始引用先过路径安全门，包括可选公式引用和将被过滤的块。"""
        for pointer, raw in self._asset_paths(block, locator, include_all_strings=True):
            if raw == "" or raw is None:
                continue
            if not isinstance(raw, str):
                self._payload_issue(locator, pointer, "expected_asset_path_string")
                continue
            try:
                resolve_asset_path(raw, root, content_dir)
            except MinerUPackageError as error:
                self.add_issue(error.code, locator, field=pointer, facts=error.facts)

    def _validate_asset(self, block: dict[str, Any], locator: MinerUSourceLocator, root: Path, content_dir: Path, *, required: bool) -> tuple[ValidatedImage | None, str]:
        paths = self._asset_paths(block, locator)
        selected = None
        selected_resolution = "missing"
        invalid = False
        first_reference = True
        for pointer, raw in paths:
            if raw == "" or raw is None:
                continue
            if not isinstance(raw, str):
                invalid = True
                if required:
                    self._payload_issue(locator, pointer, "expected_asset_path_string")
                first_reference = False
                continue
            try:
                path, resolution = resolve_asset_path(raw, root, content_dir)
            except MinerUPackageError as error:
                self.add_issue(error.code, locator, field=pointer, facts=error.facts)
                return None, "unsafe"
            if first_reference:
                if path is None:
                    invalid |= resolution != "missing"
                else:
                    selected = path
                    selected_resolution = resolution
                first_reference = False
        code = "invalid_image_asset" if required else "invalid_table_reference"
        missing_code = "missing_image_asset" if required else "missing_table_reference"
        if selected is None:
            status = "invalid" if invalid else "missing"
            self.add_issue(code if invalid else missing_code, locator, severity="blocker" if required else "warning",
                           stops_conversion=required, field="image_source", facts={"reason": status})
            return None, status
        inspection = self._image_cache.get(selected)
        if inspection is None:
            inspection = _ImageInspection()
            try:
                if selected.stat().st_size > self.policy.max_file_bytes:
                    raise MinerUPackageError("mineru_package_limit_exceeded", "image_bytes")
                content = selected.read_bytes()
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(content)) as image:
                        image_format = image.format
                        # EPS 等插件的 load 可启动辅助程序；必须在 verify/load 前限制为纯栅格格式。
                        if image_format not in ALLOWED_RASTER_FORMATS:
                            inspection.error_reason = "not_allowed_raster_format"
                        else:
                            dimensions = image.size
                            image.verify()
                    if inspection.error_reason is None:
                        with Image.open(io.BytesIO(content)) as image:
                            image.load()
                        if min(dimensions) <= 0:
                            raise ValueError("图片尺寸无效。")
                        mime = Image.MIME.get(image_format)
                        if mime is None:
                            raise ValueError("图片格式不可识别。")
                        inspection.content = content
                        inspection.mime_type = mime
            except MinerUPackageError as error:
                inspection.error_code = error.code
                inspection.error_reason = error.facts["reason"]
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError,
                    Image.DecompressionBombWarning):
                inspection.error_reason = "unreadable_or_unsupported_image"
            self._image_cache[selected] = inspection
        if inspection.error_reason is not None:
            self.add_issue(inspection.error_code or code, locator,
                           severity="blocker" if required or inspection.error_code else "warning",
                           stops_conversion=required or inspection.error_code is not None, field="image_source",
                           facts={"reason": inspection.error_reason})
            return None, "unsafe" if inspection.error_code else "invalid"
        if required:
            if inspection.word_supported is None:
                try:
                    image = WordImage.from_blob(inspection.content)
                    native_dimensions = image.scaled_dimensions()
                    if min(native_dimensions) <= 0:
                        raise ValueError("Word 图片尺寸无效。")
                    image.scaled_dimensions(width=native_dimensions[0])
                    inspection.word_supported = True
                except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError, OSError,
                        ValueError, SyntaxError, ZeroDivisionError, OverflowError):
                    inspection.word_supported = False
            if not inspection.word_supported:
                self.add_issue(code, locator, field="image_source", facts={"reason": "unreadable_or_unsupported_image"})
                return None, "invalid"
        return ValidatedImage(selected.relative_to(root.resolve()).as_posix(), inspection.mime_type,
                              inspection.content, selected_resolution), "valid"

    def _validate_table(self, block: dict[str, Any], locator: MinerUSourceLocator, reference_status: str, reference_image: ValidatedImage | None) -> None:
        html = select_mineru_table_html(block)
        explicit_values: list[Any] = []
        def collect(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in {"html", "table_body", "table_html"}:
                        explicit_values.append(value)
                    else:
                        collect(value)
            elif isinstance(node, list):
                for child in node:
                    collect(child)
        collect(block)
        nonempty = html or next((value for value in explicit_values if isinstance(value, str) and value.strip()), None)
        invalid_type = any(not isinstance(value, str) for value in explicit_values)
        parsed = parse_html_table(html)
        row_count = len(parsed.rows) if parsed else 0
        cell_count = sum(len(row) for row in parsed.rows) if parsed else 0
        signals = _HTMLSignals()
        if nonempty:
            signals.feed(nonempty)
            signals.close()
        if invalid_type or nonempty and not parsed:
            self.add_issue("invalid_table_html", locator, stops_conversion=False, field="html",
                           facts={"parseable": False, "reason": "invalid_type" if invalid_type else "no_consumable_rows"})
        elif not nonempty:
            self.add_issue("empty_table_html", locator, stops_conversion=False, field="html", facts={"parseable": False})
        if html is None and locator.source_type != "table":
            # legacy 推断表格没有 type=table 的源清单门禁，不能生成不可见的空 payload。
            self._payload_issue(locator, "html", "missing_readable_table_payload")
        if parsed and signals.reasons:
            self.add_issue("suspicious_table_html", locator, severity="warning", stops_conversion=False,
                           field="html", facts={"parseable": True, "reasons": sorted(signals.reasons)})
        classification = ("html_present_but_suspicious" if nonempty and (not parsed or signals.reasons or invalid_type) else
                          "html_present_and_parseable" if parsed else
                          "html_missing_reference_present" if reference_image is not None else "html_missing_reference_missing")
        self.report.table_check_count += 1
        self.report.table_checks.append(MinerUTableCheck(**locator.model_dump(), classification=classification,
            row_count=row_count, cell_count=cell_count, reference_status=reference_status,
            reference_resolution=reference_image.resolution if reference_image is not None else None, parseable=parsed is not None))
        self.check_report_limits()
