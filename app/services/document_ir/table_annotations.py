"""统一区分表题和表前条件，供 converter 与 renderer 共同消费。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.conversion.docx_rules.text_semantics import CAPTION_RE

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR, DocumentIRBlock


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
_CONTINUED = re.compile(r"[（(]\s*(?:continued|续表?)\s*[）)]|\bcontinued\b|(?<![\u3400-\u9fff])续表?(?![\u3400-\u9fff])", re.IGNORECASE)
_ANNOTATION_SOURCE_KEY = "table_annotation_source"
_ItemIndex = Annotated[int, Field(ge=0, strict=True)]


class TableAnnotationSource(BaseModel):
    """译前冻结的表前条件和跨片段注释位置，目标内容仍由批次负责。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    context_indices: list[_ItemIndex] = Field(default_factory=list)
    captions: dict[str, _ItemIndex] = Field(default_factory=dict)
    footnotes: dict[str, _ItemIndex] = Field(default_factory=dict)


def continuation_caption(text: str, primary: tuple[str, ...]) -> bool:
    """沿用 Word 续表判定，区分同一表的续题、条件及独立表题。"""
    if text in primary:
        return True
    if is_table_context_annotation(text):
        return False
    from app.services.document_ir.logical_table_group import is_compound_table_continuation

    if any(is_compound_table_continuation(caption, text) for caption in primary):
        return True
    match = CAPTION_RE.match(text)
    if match is None or match.group("label").lower() not in {"table", "表"}:
        return False
    tail = _CONTINUED.sub("", match.group("tail")).strip(" .．:：-–—")
    for caption in primary:
        first = CAPTION_RE.match(caption)
        if (first is not None and first.group("label").lower() in {"table", "表"}
                and int(first.group("number")) == int(match.group("number"))
                and (not tail or tail == first.group("tail").strip(" .．:：-–—"))):
            return True
    return False


def annotation_items(values: list[str], *, preserve_positions: bool) -> dict[int, str]:
    """投影有效原下标。历史渲染保留原有的同文归并。"""
    seen: set[str] = set()
    result = {}
    for index, value in enumerate(values):
        text = value.strip()
        if text and (preserve_positions or text not in seen):
            result[index] = text
            seen.add(text)
    return result


def table_placeholder_text(block: DocumentIRBlock, *, preserve_positions: bool) -> str | None:
    """占位表仍显示独立说明，已证实的题注派生值只从题注输出。"""
    if preserve_positions:
        return block.text if block.caption_text_alias_index is None else None
    return block.text if block.text not in block.captions else None


def _annotation_groups(document: DocumentIR) -> dict[str, tuple[DocumentIRBlock, DocumentIRBlock]]:
    blocks = {block.id: block for block in document.blocks if block.type == "table" and (block.html or "").strip()}
    groups = {}
    for group in document.metadata.logical_table_groups:
        members = [(fragment, block) for fragment in group.fragments if fragment.block_id is not None
                   and (block := blocks.get(fragment.block_id)) is not None]
        verified = {(relation.from_fragment_id, relation.to_fragment_id) for relation in group.continuation_relations
                    if relation.kind == "verified_continuation"}
        if len(members) > 1 and all((left[0].fragment_id, right[0].fragment_id) in verified
                                    for left, right in zip(members, members[1:])):
            owners = (members[0][1], members[-1][1])
            groups.update((block.id, owners) for _, block in members)
    return groups


def _match_annotation_indices(values: list[str], representatives: list[str], *, caption: bool) -> dict[str, int]:
    candidates = annotation_items(representatives, preserve_positions=True)
    result = {}
    for index, text in annotation_items(values, preserve_positions=True).items():
        exact = [key for key, value in candidates.items() if value == text]
        matches = exact or [key for key, value in candidates.items() if caption and continuation_caption(text, (value,))]
        if len(matches) == 1:
            result[str(index)] = matches[0]
    return result


def _table_annotation_source(
    block: DocumentIRBlock, owners: tuple[DocumentIRBlock, DocumentIRBlock] | None,
) -> TableAnnotationSource:
    contexts = [index for index, text in enumerate(block.captions) if is_table_context_annotation(text)]
    if owners is None:
        return TableAnnotationSource(context_indices=contexts)
    first, last = owners
    return TableAnnotationSource(
        context_indices=contexts,
        captions=_match_annotation_indices(block.captions, first.captions, caption=True) if block is not first else {},
        footnotes=_match_annotation_indices(block.footnotes, last.footnotes, caption=False) if block is not last else {},
    )


def freeze_table_annotation_sources(document: DocumentIR) -> None:
    """只从送译前的有效源表计算代表，避免按译文字面反推源身份。"""
    groups = _annotation_groups(document)
    for block in document.blocks:
        if block.type == "table":
            source = _table_annotation_source(block, groups.get(block.id))
            payload = source.model_dump(exclude_defaults=True)
            if payload:
                block.metadata[_ANNOTATION_SOURCE_KEY] = payload


def read_table_annotation_source(block: DocumentIRBlock) -> TableAnnotationSource:
    return TableAnnotationSource.model_validate(block.metadata.get(_ANNOTATION_SOURCE_KEY, {}))


def validate_table_annotation_sources(document: DocumentIR) -> None:
    if document.metadata.translation_item_scope is None:
        if any(_ANNOTATION_SOURCE_KEY in block.metadata for block in document.blocks):
            raise ValueError("表格注释来源需要绑定翻译范围。")
        return
    groups = _annotation_groups(document)
    for block in document.blocks:
        if block.type != "table":
            if _ANNOTATION_SOURCE_KEY in block.metadata:
                raise ValueError("表格注释来源仅适用于对应的翻译表格。")
            continue
        owners = groups.get(block.id)
        source = read_table_annotation_source(block)
        if not document.metadata.translation_items_applied:
            if source != _table_annotation_source(block, owners):
                raise ValueError("表格注释与翻译源位置不一致。")
            continue
        if (len(source.context_indices) != len(set(source.context_indices))
                or any(index >= len(block.captions) or not block.captions[index].strip() for index in source.context_indices)):
            raise ValueError("表格注释源条件位置无效。")
        for owner_index, field in enumerate(("captions", "footnotes")):
            mappings = getattr(source, field)
            if not mappings:
                continue
            owner = owners[owner_index] if owners else None
            if owner is None or owner is block:
                raise ValueError("表格注释源代表不在已验证的续表片段中。")
            values = {str(index) for index in annotation_items(getattr(block, field), preserve_positions=True)}
            representatives = annotation_items(getattr(owner, field), preserve_positions=True)
            if any(key not in values or index not in representatives for key, index in mappings.items()):
                raise ValueError("表格注释源代表位置无效。")


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
