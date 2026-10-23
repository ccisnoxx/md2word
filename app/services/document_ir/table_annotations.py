"""统一区分表题和表前条件，供 converter 与 renderer 共同消费。"""

from __future__ import annotations

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
# 这里只保护显式编号标题的身份；完整编号是否允许重绑定仍由 reconciler 判定。
NUMBERED_ANNOTATION_LEAD_RE = re.compile(
    r"^\s*(?:(?:table|figure|fig\.?|caption)\s*(?:[0-9]|[IVXLCDM]+(?=\s|[.:\-]|$)|[A-Za-z]\.[0-9])"
    r"|(?:表|图)\s*[0-9一二三四五六七八九十百千])", re.IGNORECASE,
)


def split_table_annotation_texts(texts: list[str]) -> tuple[list[str], list[str]]:
    """按已确定的逻辑组区分表题和条件，不猜测句内边界。"""

    captions: list[str] = []
    contexts: list[str] = []
    for text in texts:
        if is_table_context_annotation(text):
            contexts.append(text)
        else:
            captions.append(text)
    return captions, contexts


def is_table_context_annotation(text: str | None) -> bool:
    """识别纯条件；显式表题与条件混合时保留完整源 annotation。"""

    normalized = _normalize_text(text)
    if not normalized or NUMBERED_ANNOTATION_LEAD_RE.match(normalized):
        return False
    return _has_context_signals(normalized)


def is_mixed_table_context_annotation(text: str | None) -> bool:
    """显式表题中的条件信号需要可靠结构边界，不能整串降为 context。"""

    normalized = _normalize_text(text)
    return bool(NUMBERED_ANNOTATION_LEAD_RE.match(normalized) and _has_context_signals(normalized))


def _has_context_signals(normalized: str) -> bool:
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
    """供样式选择识别短标题；此宽松判断不构成自动重绑定证据。"""

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
