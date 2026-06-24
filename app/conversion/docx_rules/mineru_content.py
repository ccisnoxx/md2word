"""Shared MinerU content extraction helpers for runtime and DocumentIR paths."""

from __future__ import annotations

# File: app/conversion/docx_rules/mineru_content.py
# Purpose: Normalize MinerU text, captions, footnotes, HTML, and asset paths without renderer dependencies.

import re
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.text_semantics import normalize_formula_text


DETAILS_BLOCK_RE = re.compile(r"<details\b[^>]*>.*?</details>", re.IGNORECASE | re.DOTALL)
TOC_DOT_LEADER_LINE_RE = re.compile(r"\S.*(?:\.{2,}|·{2,}|…{2,})\s*\d+\s*$")
FOOTNOTE_START_RE = re.compile(
    r"^\s*(?:\(?\d+\)|\[\d+\]|\d+[.)、]|[a-z][.)])\s+",
    re.IGNORECASE,
)
FOOTNOTE_LABEL_RE = re.compile(r"^\s*(?:notes?|注|备注|说明)\s*[:：]", re.IGNORECASE)
INLINE_FORMULA_MARKUP_RE = re.compile(r"</?(?:sub|sup)>", re.IGNORECASE)


def clean_markdown_document(text: str) -> str:
    """Remove non-body details blocks while preserving useful markdown text."""

    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = DETAILS_BLOCK_RE.sub("", normalized)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def clean_text(text: str) -> str:
    cleaned = clean_markdown_document(str(text or ""))
    return " ".join(cleaned.replace("\n", " ").split()).strip()


def join_text_fragments(nodes: list[dict[str, Any]], *, clean: bool = True) -> str:
    parts: list[str] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type == "text":
            parts.append(str(node.get("content", "")))
        elif node_type in {"equation_inline", "inline_formula"} and isinstance(node.get("content"), str):
            parts.append(f" {normalize_formula_text(node['content'])} ")
        elif "content" in node and isinstance(node["content"], str):
            parts.append(node["content"])
    text = "".join(parts)
    return clean_text(text) if clean else text


def split_toc_like_lines(text: str) -> list[str]:
    lines = [clean_text(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 3:
        return []

    toc_like = sum(1 for line in lines if TOC_DOT_LEADER_LINE_RE.match(line))
    if toc_like / len(lines) < 0.7:
        return []
    return lines


def coerce_text_list(value: Any) -> list[str]:
    texts: list[str] = []
    if value is None:
        return texts

    if isinstance(value, str):
        text = clean_text(value)
        if text and not looks_like_asset_path(text) and not looks_like_html(text):
            texts.append(text)
        return texts

    if isinstance(value, list):
        for item in value:
            texts.extend(coerce_text_list(item))
        return texts

    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "text" and isinstance(value.get("content"), str):
            text = clean_text(value["content"])
            if text:
                texts.append(text)
            return texts
        if node_type in {"equation_inline", "inline_formula"} and isinstance(value.get("content"), str):
            text = clean_text(normalize_formula_text(value["content"]))
            if text:
                texts.append(text)
            return texts

        for key, child in value.items():
            if key in {"img_path", "image_path", "path", "type"}:
                continue
            texts.extend(coerce_text_list(child))
        return texts

    return texts


def collect_text_from_fields(payload: dict[str, Any], field_names: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    collected: list[str] = []
    for field_name in field_names:
        for value in find_values_by_key(payload, field_name):
            for text in coerce_text_list(value):
                if text and text not in seen:
                    seen.add(text)
                    collected.append(text)
    return collected


def merge_footnote_fragments(texts: list[str]) -> list[str]:
    """Merge MinerU rich-text footnote fragments without collapsing independent notes."""

    merged: list[str] = []
    current = ""
    current_has_marker = False

    for text in texts:
        fragment = str(text or "").strip()
        if not fragment:
            continue

        starts_new_note = is_footnote_start(fragment)
        if not current:
            current = fragment
            current_has_marker = starts_new_note
            continue

        if starts_new_note:
            merged.append(current)
            current = fragment
            current_has_marker = True
            continue

        if current_has_marker or should_join_footnote_fragment(current, fragment):
            current = append_footnote_fragment(current, fragment)
            continue

        merged.append(current)
        current = fragment
        current_has_marker = False

    if current:
        merged.append(current)
    return merged


def is_footnote_start(text: str) -> bool:
    return bool(FOOTNOTE_START_RE.match(text) or FOOTNOTE_LABEL_RE.match(text))


def should_join_footnote_fragment(previous: str, fragment: str) -> bool:
    stripped_previous = previous.rstrip()
    stripped_fragment = fragment.lstrip()
    if not stripped_previous or not stripped_fragment:
        return False
    if stripped_fragment[0] in ",.;:，。；：)]}）】":
        return True
    if stripped_previous[-1] in ",;:([{（【/":
        return True
    if INLINE_FORMULA_MARKUP_RE.search(stripped_fragment) and not stripped_previous.endswith((".", "。", ";", "；")):
        return True

    lower_previous = stripped_previous.lower()
    return lower_previous.endswith(
        (
            " of",
            " and",
            " or",
            " with",
            " from",
            " to",
            " is",
            " are",
            " by",
            "为",
            "是",
            "由",
            "和",
            "与",
            "的",
        )
    )


def append_footnote_fragment(previous: str, fragment: str) -> str:
    left = previous.rstrip()
    right = fragment.lstrip()
    if not left:
        return right
    if not right:
        return left
    if right[0] in ",.;:，。；：)]}）】":
        return f"{left}{right}"
    if left[-1] in "([{（【/":
        return f"{left}{right}"
    if is_cjk_char(left[-1]) or is_cjk_char(right[0]):
        return f"{left}{right}"
    return f"{left} {right}"


def is_cjk_char(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def find_values_by_key(node: Any, wanted_key: str) -> list[Any]:
    matches: list[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == wanted_key:
                matches.append(value)
            matches.extend(find_values_by_key(value, wanted_key))
    elif isinstance(node, list):
        for item in node:
            matches.extend(find_values_by_key(item, wanted_key))
    return matches


def extract_first_asset_path(node: Any) -> str | None:
    if isinstance(node, str):
        return node if looks_like_asset_path(node) else None

    if isinstance(node, list):
        for item in node:
            path = extract_first_asset_path(item)
            if path:
                return path
        return None

    if isinstance(node, dict):
        for key in ("img_path", "image_path", "path"):
            value = node.get(key)
            if isinstance(value, str) and looks_like_asset_path(value):
                return value
        for value in node.values():
            path = extract_first_asset_path(value)
            if path:
                return path
    return None


def looks_like_asset_path(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    if Path(lowered).suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}:
        return True
    return lowered.startswith("images/")


def looks_like_html(text: str) -> bool:
    lowered = clean_markdown_document(text).strip().lower()
    return lowered.startswith("<table") or lowered.startswith("<img")


def extract_first_html(node: Any) -> str | None:
    if isinstance(node, str):
        stripped = clean_markdown_document(node).strip()
        return stripped if looks_like_html(stripped) else None

    if isinstance(node, list):
        for item in node:
            html = extract_first_html(item)
            if html:
                return html
        return None

    if isinstance(node, dict):
        direct = node.get("html")
        if isinstance(direct, str):
            cleaned_direct = clean_markdown_document(direct).strip()
            if looks_like_html(cleaned_direct):
                return cleaned_direct
        for value in node.values():
            html = extract_first_html(value)
            if html:
                return html
    return None
