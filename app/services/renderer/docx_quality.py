from __future__ import annotations

# app/services/renderer/docx_quality.py: 提取生成 DOCX 的轻量 OOXML 质量证据。

import hashlib
import posixpath
import re
import zipfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.conversion.docx_rules.text_semantics import looks_like_heading_text, parse_toc_entry_text


EDITABLE_TEXT_MIN_CHARS = 20
DOCX_XML_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
PACKAGE_REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
LATEX_RESIDUE_RE = re.compile(
    r"(\$[^$]{1,160}\$|\\(?:[A-Za-z]+\b|[,;!>])|[_^]\{?\\?[A-Za-z0-9()+\-/]+\}?)"
)
MANUAL_LIST_MARKER_RE = re.compile(r"^\s*(?:[•■*]|[-–—])\s+")
WIDE_TABLE_MIN_COLUMNS = 6
PAIRED_VISUAL_TABLE_DESCRIPTION = "md2word:paired_visual_row"
VISUAL_TABLE_COMPOSITE_PREFIX = "md2word:visual_table_composite:"


def analyze_docx_quality_bytes(content: bytes | None) -> dict[str, Any]:
    """从 DOCX bytes 中提取可编辑性和 Word 标准结构证据。"""

    quality, _content_evidence = analyze_docx_evidence_bytes(content)
    return quality


def analyze_docx_evidence_bytes(content: bytes | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """一次解析 DOCX，并把可持久化质量指标与内部内容证据分开返回。"""

    if not content:
        return {}, {}
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            analyzed = _analyze_docx_package(package)
    except zipfile.BadZipFile:
        return {}, {}
    content_evidence = analyzed.pop("_content_evidence", {})
    return analyzed, content_evidence


def analyze_docx_quality_file(path: Path | None) -> dict[str, Any]:
    """从 DOCX 文件中提取可编辑性和 Word 标准结构证据。"""

    if path is None or not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        with zipfile.ZipFile(path) as package:
            analyzed = _analyze_docx_package(package)
    except zipfile.BadZipFile:
        return {}
    analyzed.pop("_content_evidence", None)
    return analyzed


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


def _analyze_docx_package(package: zipfile.ZipFile) -> dict[str, Any]:
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
    toc_field_paragraph_ids = {id(paragraph) for paragraph in paragraphs if _toc_field_count(paragraph)}
    tables = root.findall(".//w:tbl", DOCX_XML_NS)
    layout_tables = [table for table in tables if _is_layout_table(table)]
    semantic_tables = [table for table in tables if not _is_layout_table(table)]
    visual_table_composite_ids = [
        description.removeprefix(VISUAL_TABLE_COMPOSITE_PREFIX)
        for table in layout_tables
        if (description := _table_description(table)).startswith(VISUAL_TABLE_COMPOSITE_PREFIX)
    ]
    table_cell_paragraphs = [paragraph for table in tables for paragraph in table.findall(".//w:tc/w:p", DOCX_XML_NS)]
    semantic_table_cell_paragraphs = [
        paragraph for table in semantic_tables for paragraph in table.findall(".//w:tc/w:p", DOCX_XML_NS)
    ]
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
    word_text_tag = f"{{{DOCX_XML_NS['w']}}}t"
    latex_matches = _unique_latex_residue(
        "\n".join(
            "".join(element.text or "" for element in paragraph.iter(word_text_tag))
            for paragraph in paragraphs
        )
    )
    text_chars = len(joined_text)
    table_count = len(semantic_tables)
    table_shapes = [_table_shape(table) for table in semantic_tables]
    wide_table_count = sum(1 for table in semantic_tables if _table_column_count(table) >= WIDE_TABLE_MIN_COLUMNS)
    inline_shape_count = len(root.findall(".//wp:inline", DOCX_XML_NS))
    editable_text_available = text_chars >= EDITABLE_TEXT_MIN_CHARS
    editable_content_available = editable_text_available or table_count > 0
    heading_paragraphs = sum(1 for paragraph in paragraphs if _paragraph_has_heading_style(paragraph, heading_style_ids))
    toc_tab_leader_paragraphs = sum(1 for paragraph in paragraphs if _paragraph_has_dot_tab_leader(paragraph))
    toc_cache_texts = _toc_cache_texts(paragraphs)
    image_asset_evidence = _image_asset_evidence(root, package)
    return {
        "paragraph_count": len(paragraphs),
        "table_count": table_count,
        "layout_table_count": len(layout_tables),
        "paired_visual_table_count": sum(1 for table in layout_tables if _is_paired_visual_table(table)),
        "visual_table_composite_count": len(visual_table_composite_ids),
        "table_shapes": table_shapes,
        "wide_table_count": wide_table_count,
        "media_count": media_count,
        "inline_shape_count": inline_shape_count,
        "image_asset_marker_count": len(image_asset_evidence),
        "heading_paragraphs": heading_paragraphs,
        "toc_field_count": len(toc_cache_texts),
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
        "table_header_rows": sum(
            1 for table in semantic_tables for row in table.findall("./w:tr", DOCX_XML_NS) if _row_has_table_header(row)
        ),
        "table_no_split_rows": sum(
            1 for table in semantic_tables for row in table.findall("./w:tr", DOCX_XML_NS) if _row_has_cant_split(row)
        ),
        "shaded_table_cells": sum(
            1 for table in semantic_tables for cell in table.findall(".//w:tc", DOCX_XML_NS) if _cell_has_fill(cell)
        ),
        "table_cell_zero_spacing_paragraphs": sum(
            1 for paragraph in semantic_table_cell_paragraphs if _paragraph_has_zero_spacing(paragraph)
        ),
        "landscape_sections": sum(1 for section in root.findall(".//w:sectPr", DOCX_XML_NS) if _section_is_landscape(section)),
        "latex_residue_count": len(latex_matches),
        "latex_residue_examples": latex_matches[:8],
        "text_chars": text_chars,
        "editable_text_available": editable_text_available,
        "editable_content_available": editable_content_available,
        "image_only_suspected": media_count > 0 and not editable_content_available,
        "_content_evidence": {
            "paragraph_texts": [text for text in paragraph_texts if text],
            "non_toc_paragraph_texts": [
                _paragraph_text(paragraph)
                for paragraph in paragraphs
                if id(paragraph) not in toc_field_paragraph_ids and _paragraph_text(paragraph)
            ],
            "body_paragraph_texts": [text for text in body_paragraph_texts if text],
            "non_toc_body_paragraph_texts": [
                _paragraph_text(paragraph)
                for paragraph in body_paragraphs
                if id(paragraph) not in toc_field_paragraph_ids and _paragraph_text(paragraph)
            ],
            "heading_paragraph_texts": [
                _paragraph_text(paragraph)
                for paragraph in paragraphs
                if _paragraph_has_heading_style(paragraph, heading_style_ids) and _paragraph_text(paragraph)
            ],
            "numbering_paragraph_texts": [
                _paragraph_text(paragraph)
                for paragraph in paragraphs
                if paragraph.find("./w:pPr/w:numPr", DOCX_XML_NS) is not None and _paragraph_text(paragraph)
            ],
            "semantic_table_cell_texts": [
                _paragraph_text(paragraph)
                for paragraph in semantic_table_cell_paragraphs
                if _paragraph_text(paragraph)
            ],
            "toc_cache_texts": toc_cache_texts,
            "image_asset_evidence": image_asset_evidence,
            "visual_table_composite_ids": visual_table_composite_ids,
        },
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


def _toc_cache_texts(paragraphs: list[ElementTree.Element]) -> list[str]:
    """提取 document.xml 中 TOC complex field 的当前可见缓存。"""

    values: list[str] = []
    for paragraph in paragraphs:
        values.extend([_paragraph_text(paragraph)] * _toc_field_count(paragraph))
    return values


def _toc_field_count(paragraph: ElementTree.Element) -> int:
    instruction = "".join(
        element.text or ""
        for element in paragraph.findall(".//w:instrText", DOCX_XML_NS)
    )
    return len(re.findall(r"(?:^|\s)TOC(?:\s|$)", instruction))


def _image_asset_evidence(root: ElementTree.Element, package: zipfile.ZipFile) -> list[dict[str, Any]]:
    """按 drawing marker、裁剪区域、relationship 和 checksum 还原图片身份。"""

    targets = _document_relationship_targets(package)
    evidence: list[dict[str, Any]] = []
    for inline in root.findall(".//wp:inline", DOCX_XML_NS):
        properties = inline.find("./wp:docPr", DOCX_XML_NS)
        description = properties.get("descr") if properties is not None else None
        if not description or not description.startswith("md2word:asset:"):
            continue
        asset_id = description.removeprefix("md2word:asset:")
        blip = inline.find(".//a:blip", DOCX_XML_NS)
        relationship_id = blip.get(f"{{{DOCX_XML_NS['r']}}}embed") if blip is not None else None
        media_path = _word_relationship_target(targets.get(relationship_id or ""))
        checksum = None
        if media_path is not None:
            try:
                checksum = f"sha256:{hashlib.sha256(package.read(media_path)).hexdigest()}"
            except KeyError:
                media_path = None
        evidence.append(
            {
                "asset_id": asset_id,
                "relationship_id": relationship_id,
                "media_path": media_path,
                "checksum_sha256": checksum,
                "crop_offsets": _drawing_crop_offsets(inline),
            }
        )
    return evidence


def _drawing_crop_offsets(inline: ElementTree.Element) -> list[int] | str | None:
    src_rect = inline.find(".//a:srcRect", DOCX_XML_NS)
    if src_rect is None:
        return None
    try:
        offsets = [int(src_rect.get(name) or "0") for name in ("l", "t", "r", "b")]
    except ValueError:
        return "invalid"
    if any(value < 0 or value > 100000 for value in offsets):
        return "invalid"
    return offsets


def _document_relationship_targets(package: zipfile.ZipFile) -> dict[str, str]:
    try:
        relationships = ElementTree.fromstring(package.read("word/_rels/document.xml.rels"))
    except (KeyError, ElementTree.ParseError):
        return {}
    return {
        str(item.get("Id")): str(item.get("Target"))
        for item in relationships.findall("./pr:Relationship", PACKAGE_REL_NS)
        if item.get("Id") and item.get("Target") and item.get("TargetMode") != "External"
    }


def _word_relationship_target(target: str | None) -> str | None:
    if not target:
        return None
    path = target.lstrip("/") if target.startswith("/") else posixpath.join("word", target)
    normalized = posixpath.normpath(path)
    return normalized if normalized.startswith("word/media/") else None


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


def _is_paired_visual_table(table: ElementTree.Element) -> bool:
    return _table_description(table) == PAIRED_VISUAL_TABLE_DESCRIPTION


def _is_layout_table(table: ElementTree.Element) -> bool:
    description = _table_description(table)
    return description == PAIRED_VISUAL_TABLE_DESCRIPTION or description.startswith(VISUAL_TABLE_COMPOSITE_PREFIX)


def _table_description(table: ElementTree.Element) -> str:
    description = table.find("./w:tblPr/w:tblDescription", DOCX_XML_NS)
    return (description.get(_w_attr("val")) if description is not None else "") or ""


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
