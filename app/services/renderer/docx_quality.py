from __future__ import annotations

# app/services/renderer/docx_quality.py: 提取生成 DOCX 的轻量 OOXML 质量证据。

import re
import zipfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.conversion.docx_rules.text_semantics import parse_toc_entry_text


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
NUMBERED_HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+){0,5})\s+\S")
HEADING_NUMBER_RE = re.compile(
    r"^(?:\d+[.、]|\d+\.\d+|附录[A-Z\d.\-]+|appendix\s+[A-Z\d.\-]+)",
    re.IGNORECASE,
)
ENGLISH_HEADING_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9/&()\-]*")
ENGLISH_HEADING_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
}
WIDE_TABLE_MIN_COLUMNS = 6


def analyze_docx_quality_bytes(content: bytes | None) -> dict[str, Any]:
    """从 DOCX bytes 中提取可编辑性和 Word 标准结构证据。"""

    if not content:
        return {}
    try:
        with zipfile.ZipFile(BytesIO(content)) as package:
            return _analyze_docx_package(package)
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
    ]
    semantic_body_paragraph_texts = [_paragraph_text(paragraph) for paragraph in semantic_body_paragraphs]
    joined_text = "\n".join(text for text in paragraph_texts if text)
    latex_matches = _unique_latex_residue(joined_text)
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
        "heading_like_paragraphs": sum(1 for text in semantic_body_paragraph_texts if _looks_like_heading_text(text)),
        "heading_like_unstyled_paragraphs": sum(
            1
            for paragraph, text in zip(semantic_body_paragraphs, semantic_body_paragraph_texts, strict=True)
            if _looks_like_heading_text(text) and not _paragraph_has_heading_style(paragraph, heading_style_ids)
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


def _looks_like_heading_text(text: str) -> bool:
    cleaned = " ".join((text or "").replace("\n", " ").split()).strip()
    cleaned = re.sub(r"(?:[.\s·。…]{2,}|\s+)\d+\s*$", "", cleaned)
    if len(cleaned) > 80 or not cleaned or cleaned[-1:] in ".!?;:":
        return False
    if MANUAL_LIST_MARKER_RE.match(cleaned) or _looks_like_plain_toc_entry(text):
        return False
    if re.search(r"[$\\{}=<>/√±°µμθψΩ]", cleaned):
        return False
    if re.match(r"^(?:table|figure)\b", cleaned, re.IGNORECASE):
        return False
    if re.match(r"^\d+\.[A-Z]", cleaned):
        return False
    if NUMBERED_HEADING_RE.match(cleaned) or HEADING_NUMBER_RE.match(cleaned):
        return True
    return _looks_like_english_heading_text(cleaned)


def _looks_like_english_heading_text(text: str) -> bool:
    stripped = text.strip()
    tokens = ENGLISH_HEADING_TOKEN_RE.findall(stripped)
    if not 1 <= len(tokens) <= 8:
        return False
    if len(tokens) == 1 and not tokens[0].isupper():
        return False

    significant_chars = sum(1 for char in stripped if char.isalpha() or char.isdigit())
    token_chars = sum(len(token) for token in tokens)
    if token_chars < significant_chars * 0.7:
        return False

    acceptable = 0
    for token in tokens:
        lowered = token.lower()
        if lowered in ENGLISH_HEADING_STOPWORDS or token.isupper() or token[0].isupper():
            acceptable += 1
    return acceptable >= max(len(tokens) - 1, 1)


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
