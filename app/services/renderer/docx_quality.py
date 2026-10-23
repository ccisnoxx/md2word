from __future__ import annotations

# app/services/renderer/docx_quality.py: 提取生成 DOCX 的轻量 OOXML 质量证据。

import re
import zipfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.conversion.docx_rules.formula import (
    FORMULA_OUTPUT_VERSION,
    FORMULA_REASONS,
    FORMULA_REPORT_VERSION,
    canonical_sha256,
    output_sha256,
)
from app.conversion.docx_rules.text_semantics import looks_like_heading_text, parse_toc_entry_text


EDITABLE_TEXT_MIN_CHARS = 20
DOCX_XML_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
LATEX_RESIDUE_RE = re.compile(
    r"(\$[^$]{1,160}\$|\\[A-Za-z]+\b|[_^]\{?\\?[A-Za-z0-9()+\-/]+\}?)"
)
MANUAL_LIST_MARKER_RE = re.compile(r"^\s*(?:[•■*]|[-–—])\s+")
WIDE_TABLE_MIN_COLUMNS = 6


def analyze_docx_quality_bytes(content: bytes | None, *, formula_report: dict[str, Any] | None = None) -> dict[str, Any]:
    """从 DOCX bytes 中提取可编辑性和 Word 标准结构证据。"""

    if not content:
        return {}
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            return _analyze_docx_package(package, formula_report=formula_report)
    except zipfile.BadZipFile:
        return {}


def analyze_docx_quality_file(path: Path | None) -> dict[str, Any]:
    """从 DOCX 文件中提取可编辑性和 Word 标准结构证据。"""

    if path is None or not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        with zipfile.ZipFile(path) as package:
            return _analyze_docx_package(package)
    except zipfile.BadZipFile:
        return {}


def build_docx_quality_flags(quality: Mapping[str, Any] | None) -> list[str]:
    """把 DOCX 机器证据转为人工复核用风险标记。"""

    if not quality:
        return ["docx_quality_unavailable"]

    flags: list[str] = []
    if quality.get("analysis_error"):
        flags.append("docx_analysis_error")
    if quality.get("editable_content_available") is False:
        flags.append("docx_no_editable_content")
    if quality.get("image_only_suspected") is True:
        flags.append("docx_image_only_suspected")

    latex_residue_count = _int_value(quality.get("latex_residue_count"))
    if latex_residue_count > 0:
        flags.append(f"docx_latex_residue:{latex_residue_count}")

    manual_list_marker_count = _int_value(quality.get("manual_list_marker_paragraphs"))
    if manual_list_marker_count > 0:
        flags.append(f"docx_manual_list_markers:{manual_list_marker_count}")

    plain_toc_entry_count = _int_value(quality.get("plain_toc_entry_paragraphs"))
    if plain_toc_entry_count > 0 and _int_value(quality.get("toc_tab_leader_paragraphs")) == 0:
        flags.append(f"docx_plain_toc_entries:{plain_toc_entry_count}")

    unstyled_heading_count = _int_value(quality.get("heading_like_unstyled_paragraphs"))
    if unstyled_heading_count > 0:
        flags.append(f"docx_unstyled_heading_candidates:{unstyled_heading_count}")

    return flags


def _analyze_docx_package(package: zipfile.ZipFile, *, formula_report: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        document_xml = package.read("word/document.xml")
    except KeyError:
        return {}

    media_count = len([name for name in package.namelist() if name.startswith("word/media/")])
    heading_style_ids = _heading_style_ids(package)
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        return {"analysis_error": f"document_xml_parse_error:{exc.__class__.__name__}"}

    paragraphs = root.findall(".//w:p", DOCX_XML_NS)
    tables = root.findall(".//w:tbl", DOCX_XML_NS)
    table_cell_paragraphs = [paragraph for table in tables for paragraph in table.findall(".//w:tc/w:p", DOCX_XML_NS)]
    table_cell_paragraph_ids = {id(paragraph) for paragraph in table_cell_paragraphs}
    paragraph_texts = [_paragraph_text(paragraph) for paragraph in paragraphs]
    body_paragraphs = [paragraph for paragraph in paragraphs if id(paragraph) not in table_cell_paragraph_ids]
    body_paragraph_texts = [_paragraph_text(paragraph) for paragraph in body_paragraphs]
    semantic_body_paragraphs = [
        paragraph
        for paragraph in body_paragraphs
        if paragraph.find("./w:pPr/w:numPr", DOCX_XML_NS) is None
        and not _paragraph_has_dot_tab_leader(paragraph)
    ]
    semantic_body_paragraph_texts = [_paragraph_text(paragraph) for paragraph in semantic_body_paragraphs]
    joined_text = "\n".join(text for text in paragraph_texts if text)
    residue_text = joined_text
    if formula_report is not None:
        validate_formula_report(formula_report)
        ranges = _formula_ranges(root, formula_report)
        excluded = {id(node) for entry, nodes in ranges if entry["mode"] == "text_fallback" for node in nodes for node in node.iter()}
        residue_text = "\n".join("".join(node.text or "" for node in paragraph.iter() if node.tag in {_w_attr("t"), f"{{{DOCX_XML_NS['m']}}}t"} and id(node) not in excluded) for paragraph in paragraphs)
    latex_matches = _unique_latex_residue(residue_text)
    text_chars = len(joined_text)
    table_count = len(tables)
    table_shapes = [_table_shape(table) for table in tables]
    wide_table_count = sum(1 for table in tables if _table_column_count(table) >= WIDE_TABLE_MIN_COLUMNS)
    inline_shape_count = len(root.findall(".//wp:inline", DOCX_XML_NS))
    editable_text_available = text_chars >= EDITABLE_TEXT_MIN_CHARS
    editable_content_available = editable_text_available or table_count > 0
    heading_paragraphs = sum(1 for paragraph in paragraphs if _paragraph_has_heading_style(paragraph, heading_style_ids))
    toc_tab_leader_paragraphs = sum(1 for paragraph in paragraphs if _paragraph_has_dot_tab_leader(paragraph))
    return {
        "paragraph_count": len(paragraphs),
        "table_count": table_count,
        "table_shapes": table_shapes,
        "wide_table_count": wide_table_count,
        "media_count": media_count,
        "inline_shape_count": inline_shape_count,
        "heading_paragraphs": heading_paragraphs,
        "heading_like_paragraphs": sum(1 for text in semantic_body_paragraph_texts if looks_like_heading_text(text)),
        "heading_like_unstyled_paragraphs": sum(
            1
            for paragraph, text in zip(semantic_body_paragraphs, semantic_body_paragraph_texts, strict=True)
            if looks_like_heading_text(text) and not _paragraph_has_heading_style(paragraph, heading_style_ids)
        ),
        "numbering_paragraphs": sum(1 for paragraph in paragraphs if paragraph.find("./w:pPr/w:numPr", DOCX_XML_NS) is not None),
        "manual_list_marker_paragraphs": sum(1 for text in body_paragraph_texts if MANUAL_LIST_MARKER_RE.match(text)),
        "toc_tab_leader_paragraphs": toc_tab_leader_paragraphs,
        "plain_toc_entry_paragraphs": sum(
            1
            for paragraph, text in zip(body_paragraphs, body_paragraph_texts, strict=True)
            if _looks_like_plain_toc_entry(text) and not _paragraph_has_dot_tab_leader(paragraph)
        ),
        "keep_next_paragraphs": sum(1 for paragraph in paragraphs if paragraph.find("./w:pPr/w:keepNext", DOCX_XML_NS) is not None),
        "table_header_rows": sum(1 for table in tables for row in table.findall("./w:tr", DOCX_XML_NS) if _row_has_table_header(row)),
        "table_no_split_rows": sum(1 for table in tables for row in table.findall("./w:tr", DOCX_XML_NS) if _row_has_cant_split(row)),
        "shaded_table_cells": sum(1 for table in tables for cell in table.findall(".//w:tc", DOCX_XML_NS) if _cell_has_fill(cell)),
        "table_cell_zero_spacing_paragraphs": sum(1 for paragraph in table_cell_paragraphs if _paragraph_has_zero_spacing(paragraph)),
        "landscape_sections": sum(1 for section in root.findall(".//w:sectPr", DOCX_XML_NS) if _section_is_landscape(section)),
        "latex_residue_count": len(latex_matches),
        "latex_residue_examples": latex_matches[:8],
        "text_chars": text_chars,
        "editable_text_available": editable_text_available,
        "editable_content_available": editable_content_available,
        "image_only_suspected": media_count > 0 and not editable_content_available,
    }


def _heading_style_ids(package: zipfile.ZipFile) -> set[str]:
    try:
        styles_xml = package.read("word/styles.xml")
    except KeyError:
        return set()
    try:
        styles_root = ElementTree.fromstring(styles_xml)
    except ElementTree.ParseError:
        return set()

    style_ids: set[str] = set()
    for style in styles_root.findall("./w:style", DOCX_XML_NS):
        style_id = style.get(_w_attr("styleId")) or ""
        name = style.find("./w:name", DOCX_XML_NS)
        style_name = (name.get(_w_attr("val")) if name is not None else "") or ""
        if style_id.lower().startswith("heading") or style_name.lower().startswith("heading"):
            style_ids.add(style_id)
    return style_ids


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    text_tags = {f"{{{DOCX_XML_NS['w']}}}t", f"{{{DOCX_XML_NS['m']}}}t"}
    return "".join(element.text or "" for element in paragraph.iter() if element.tag in text_tags).strip()


def _paragraph_style(paragraph: ElementTree.Element) -> str:
    style = paragraph.find("./w:pPr/w:pStyle", DOCX_XML_NS)
    if style is None:
        return ""
    return style.get(f"{{{DOCX_XML_NS['w']}}}val") or ""


def _paragraph_has_heading_style(paragraph: ElementTree.Element, heading_style_ids: set[str]) -> bool:
    style = _paragraph_style(paragraph)
    return bool(style and (style.lower().startswith("heading") or style in heading_style_ids))


def _w_attr(name: str) -> str:
    return f"{{{DOCX_XML_NS['w']}}}{name}"


def _paragraph_has_dot_tab_leader(paragraph: ElementTree.Element) -> bool:
    for tab in paragraph.findall("./w:pPr/w:tabs/w:tab", DOCX_XML_NS):
        leader = (tab.get(_w_attr("leader")) or "").lower()
        if leader in {"dot", "dots"}:
            return True
    return False


def _paragraph_has_zero_spacing(paragraph: ElementTree.Element) -> bool:
    spacing = paragraph.find("./w:pPr/w:spacing", DOCX_XML_NS)
    return spacing is not None and spacing.get(_w_attr("before")) == "0" and spacing.get(_w_attr("after")) == "0"


def _row_has_table_header(row: ElementTree.Element) -> bool:
    return row.find("./w:trPr/w:tblHeader", DOCX_XML_NS) is not None


def _row_has_cant_split(row: ElementTree.Element) -> bool:
    return row.find("./w:trPr/w:cantSplit", DOCX_XML_NS) is not None


def _cell_has_fill(cell: ElementTree.Element) -> bool:
    shading = cell.find("./w:tcPr/w:shd", DOCX_XML_NS)
    if shading is None:
        return False
    fill = (shading.get(_w_attr("fill")) or "").strip().lower()
    return bool(fill and fill != "auto")


def _section_is_landscape(section: ElementTree.Element) -> bool:
    page_size = section.find("./w:pgSz", DOCX_XML_NS)
    if page_size is None:
        return False
    return (page_size.get(_w_attr("orient")) or "").lower() == "landscape"


def _table_shape(table: ElementTree.Element) -> str:
    rows = table.findall("./w:tr", DOCX_XML_NS)
    return f"{len(rows)}x{_table_column_count(table)}"


def _table_column_count(table: ElementTree.Element) -> int:
    rows = table.findall("./w:tr", DOCX_XML_NS)
    max_columns = 0
    for row in rows:
        max_columns = max(max_columns, len(row.findall("./w:tc", DOCX_XML_NS)))
    return max_columns


def _looks_like_plain_toc_entry(text: str) -> bool:
    return parse_toc_entry_text(text) is not None


def _unique_latex_residue(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in LATEX_RESIDUE_RE.finditer(text):
        value = match.group(0).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def validate_formula_report(report: object) -> dict[str, Any]:
    """严格校验持久化报告并派生安全摘要；此函数不进行文件 I/O。"""
    if not isinstance(report, dict) or set(report) != {"schema_version", "entries"} or report.get("schema_version") != FORMULA_REPORT_VERSION:
        raise ValueError("公式报告版本或结构无效")
    entries = report.get("entries")
    if not isinstance(entries, list):
        raise ValueError("公式报告条目无效")
    counts = {"omml": 0, "semantic_runs": 0, "text_fallback": 0}
    reasons: dict[str, int] = {}
    entry_keys = {"occurrence", "source", "anchor", "mode", "reason", "output_projection_version", "expected_output_sha256"}
    source_keys = {"block_id", "field", "start", "end", "boundary", "source_sha256"}
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or set(entry) != entry_keys:
            raise ValueError("公式报告条目结构无效")
        if type(entry["occurrence"]) is not int or entry["occurrence"] != index or entry["anchor"] != f"md2w_formula_{index:06d}":
            raise ValueError("公式报告锚点或次序无效")
        mode = entry["mode"]
        if not isinstance(mode, str) or mode not in counts or entry["output_projection_version"] != FORMULA_OUTPUT_VERSION:
            raise ValueError("公式报告输出模式无效")
        reason = entry["reason"]
        if (mode == "text_fallback" and (not isinstance(reason, str) or reason not in FORMULA_REASONS)) or (mode != "text_fallback" and reason is not None):
            raise ValueError("公式报告降级原因无效")
        source = entry["source"]
        if not isinstance(source, dict) or set(source) != source_keys:
            raise ValueError("公式报告源绑定无效")
        if not isinstance(source["block_id"], str) or not source["block_id"] or not isinstance(source["field"], str) or not re.fullmatch(r"(?:text|latex|html/\d+/\d+|list_items/\d+|captions/\d+|footnotes/\d+|metadata/caption)", source["field"]):
            raise ValueError("公式报告源位置无效")
        if type(source["start"]) is not int or type(source["end"]) is not int or not 0 <= source["start"] < source["end"]:
            raise ValueError("公式报告源范围无效")
        if not isinstance(source["boundary"], str) or source["boundary"] not in {"block", "dollar", "display_dollar", "paren", "bracket", "eq", "bare_command", "semantic", "semantic_script"}:
            raise ValueError("公式报告数学边界无效")
        for value in (source["source_sha256"], entry["expected_output_sha256"]):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("公式报告内容绑定无效")
        counts[mode] += 1
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "schema_version": "formula-summary/v1",
        "formula_count": len(entries),
        "omml_count": counts["omml"],
        "semantic_count": counts["semantic_runs"],
        "fallback_count": counts["text_fallback"],
        "warning_codes": ["formula_text_fallback"] if counts["text_fallback"] else [],
        "reason_counts": dict(sorted(reasons.items())),
        "report_sha256": canonical_sha256(report),
    }


def _formula_ranges(root: ElementTree.Element, report: dict[str, Any]) -> list[tuple[dict[str, Any], list[ElementTree.Element]]]:
    entries = {entry["anchor"]: entry for entry in report["entries"]}
    found: set[str] = set()
    ranges: list[tuple[dict[str, Any], list[ElementTree.Element]]] = []
    all_starts = root.findall(".//w:bookmarkStart", DOCX_XML_NS)
    all_ends = root.findall(".//w:bookmarkEnd", DOCX_XML_NS)
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child.tag != _w_attr("bookmarkStart"):
                continue
            anchor = child.get(_w_attr("name")) or ""
            if not anchor.startswith("md2w_formula_"):
                continue
            if anchor not in entries or anchor in found:
                raise ValueError("DOCX 公式锚点缺失、重复或未登记")
            found.add(anchor)
            bookmark_id = child.get(_w_attr("id"))
            if sum(node.get(_w_attr("id")) == bookmark_id for node in all_starts) != 1 or sum(node.get(_w_attr("id")) == bookmark_id for node in all_ends) != 1:
                raise ValueError("DOCX 公式锚点身份无效")
            end = next((end_index for end_index in range(index + 1, len(children)) if children[end_index].tag == _w_attr("bookmarkEnd") and children[end_index].get(_w_attr("id")) == bookmark_id), None)
            if end is None:
                raise ValueError("DOCX 公式锚点范围未闭合")
            nodes = children[index + 1:end]
            entry = entries[anchor]
            math_count = sum(node.tag == f"{{{DOCX_XML_NS['m']}}}oMath" for node in nodes)
            if not nodes or (entry["mode"] == "omml" and (math_count != 1 or len(nodes) != 1)) or (entry["mode"] != "omml" and (math_count or any(node.tag != _w_attr("r") for node in nodes))):
                raise ValueError("DOCX 公式实际输出模式不匹配")
            if output_sha256(nodes) != entry["expected_output_sha256"]:
                raise ValueError("DOCX 公式实际输出与预期绑定不匹配")
            ranges.append((entry, nodes))
    if found != set(entries):
        raise ValueError("DOCX 公式锚点缺失")
    covered_math = {id(node) for _entry, nodes in ranges for element in nodes for node in element.iter() if node.tag == f"{{{DOCX_XML_NS['m']}}}oMath"}
    if covered_math != {id(node) for node in root.findall(".//m:oMath", DOCX_XML_NS)}:
        raise ValueError("DOCX 包含未登记的数学对象")
    return ranges


def verify_docx_formula_report(content: bytes, report: dict[str, Any]) -> None:
    """从最终 DOCX 锚点范围重建投影，拒绝改值、错位、截断和漏提示。"""
    validate_formula_report(report)
    with zipfile.ZipFile(BytesIO(content)) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    _formula_ranges(root, report)
