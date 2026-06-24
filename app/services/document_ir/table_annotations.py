from __future__ import annotations

"""Classify table-adjacent annotation text before it becomes Word styling."""

# File: app/services/document_ir/table_annotations.py
# Purpose: Keep true table captions separate from table condition/context text.

import re


EXPLICIT_TABLE_CAPTION_RE = re.compile(
    r"^\s*(?:"
    r"(?:table|figure|fig\.?|caption)\s+[\wIVXLCDM]+(?:[.\-:]\w+)*"
    r"|(?:表|图)\s*[\w一二三四五六七八九十百千.、:-]+"
    r"|(?:continued\s+table|续表)\b"
    r"|[A-Z]\.\d+(?:\.\d+)?\b"
    r")",
    re.IGNORECASE,
)
CONDITION_LEAD_RE = re.compile(r"^\s*(?:at|when|with|under|for)\b", re.IGNORECASE)
ASSIGNMENT_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_()*/+\-]*\s*=")
TERMINAL_SENTENCE_RE = re.compile(r"[.!?。！？]\s*$")


def split_table_annotation_texts(texts: list[str]) -> tuple[list[str], list[str]]:
    """Split MinerU table annotation strings into captions and context paragraphs."""

    captions: list[str] = []
    contexts: list[str] = []
    for text in texts:
        if is_table_context_annotation(text):
            contexts.append(text)
        else:
            captions.append(text)
    return captions, contexts


def is_table_context_annotation(text: str | None) -> bool:
    """Return True when a table annotation is really a condition/context sentence."""

    normalized = _normalize_text(text)
    if not normalized:
        return False
    lowered = normalized.lower()
    assignment_count = len(ASSIGNMENT_RE.findall(normalized))
    if "unless otherwise noted" in lowered:
        return True
    if CONDITION_LEAD_RE.match(normalized) and assignment_count >= 1:
        return True
    if assignment_count >= 2 and any(separator in normalized for separator in (",", ";", "，", "；")):
        return True
    if len(normalized) > 100 and assignment_count >= 1:
        return True
    return False


def is_table_caption_annotation(text: str | None) -> bool:
    """Return True for short title-like labels and explicit table captions."""

    normalized = _normalize_text(text)
    if not normalized or is_table_context_annotation(normalized):
        return False
    if EXPLICIT_TABLE_CAPTION_RE.match(normalized):
        return True
    if ASSIGNMENT_RE.search(normalized):
        return False
    if len(normalized) > 90:
        return False
    if TERMINAL_SENTENCE_RE.search(normalized):
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", normalized))


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())
