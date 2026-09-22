"""在 MinerU schema 映射与 Word 布局之间统一裁决块语义和去向。"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.conversion.docx_rules.text_semantics import (
    is_toc_title_text,
    parse_decimal_list_marker,
    parse_toc_entry_text,
    resolve_source_heading_level,
    split_document_identity,
)
from app.services.document_ir.models import DocumentIRBlockRole, DocumentIRBlockType


CAPTION_TITLE_RE = re.compile(r"^\s*(?:图|表|figure|table)\s*[A-Z]?\d+\b", re.IGNORECASE)
REVISION_RANGE_RE = re.compile(
    r"(?:\brevision\b.*\b(?:to|through)\b.*\brevision\b|修订(?:版)?\s*.+?(?:到|至).+?修订(?:版)?)",
    re.IGNORECASE,
)
LOCAL_LABEL_RE = re.compile(r"^\s*(?:notes?|注意|注|说明)\s*[:：]?(?:\s*\(continued\))?\s*$", re.IGNORECASE)
DATE_MARKER_RE = re.compile(
    r"^(?:\d{1,4}[-/.](?:[A-Za-z]{3,9}|\d{1,2})[-/.]\d{1,4}|"
    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})$",
    re.IGNORECASE,
)
URL_MARKER_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
DECORATION_SOURCE_TYPES = {"header", "page_header", "footer", "page_footer", "page_number"}
MarginLineKey = tuple[str, str, tuple[str, int]]


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    """converter 已机械解析、等待文档级语义裁决的源块。"""

    source_index: int
    source_type: str
    block_type: DocumentIRBlockType
    text: str
    page_index: int | None
    bbox: tuple[float, float, float, float] | None
    page_width: float | None
    page_height: float | None
    heading_level: int | None = None
    list_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticDecision:
    """一个源块的唯一最终语义和布局去向。"""

    block_type: DocumentIRBlockType
    role: DocumentIRBlockRole
    reason: str
    annotation_role: str | None = None
    quality_flags: tuple[str, ...] = ()
    insert_toc_anchor: bool = False
    heading_level: int | None = None


def normalize_semantics(candidates: list[SemanticCandidate]) -> dict[int, SemanticDecision]:
    """按竞争角色优先、源 title 非对称保留的规则返回确定性裁决。"""

    subject_pages = _structured_subject_pages(candidates)
    recurring_lines, recurring_lines_outside_subject = _recurring_margin_lines(
        candidates,
        subject_pages=subject_pages,
    )
    subject_header_indices = _subject_header_indices(
        candidates,
        subject_pages=subject_pages,
        recurring_lines_outside_subject=recurring_lines_outside_subject,
    )
    aligned_decoration_indices = _aligned_margin_group_indices(
        candidates,
        subject_header_indices=subject_header_indices,
    )
    pages_with_regular_content = {
        candidate.page_index
        for candidate in candidates
        if candidate.source_type not in DECORATION_SOURCE_TYPES
        and bool(candidate.text or candidate.block_type in {"table", "image", "formula"})
    }
    decisions = {
        candidate.source_index: _base_decision(
            candidate,
            page_has_regular_content=candidate.page_index in pages_with_regular_content,
            recurring_lines=recurring_lines,
            subject_header_indices=subject_header_indices,
            aligned_decoration_indices=aligned_decoration_indices,
        )
        for candidate in candidates
    }
    _mark_decimal_list_runs(candidates, decisions)
    _mark_toc_regions(candidates, decisions)
    _mark_document_identity(candidates, decisions)
    return decisions


def _base_decision(
    candidate: SemanticCandidate,
    *,
    page_has_regular_content: bool,
    recurring_lines: set[MarginLineKey],
    subject_header_indices: set[int],
    aligned_decoration_indices: set[int],
) -> SemanticDecision:
    source_type = candidate.source_type
    text = candidate.text.strip()
    if (
        source_type in {"", "text", "paragraph", "para", "title", "heading", "page_footnote"}
        and candidate.block_type in {"heading", "paragraph"}
        and not text
    ):
        return SemanticDecision(candidate.block_type, "filtered", "empty_text_block_filtered")
    if source_type in DECORATION_SOURCE_TYPES:
        return _decoration_decision(
            candidate,
            page_has_regular_content=page_has_regular_content,
            recurring_lines=recurring_lines,
            is_subject_header=candidate.source_index in subject_header_indices,
            is_aligned_decoration=candidate.source_index in aligned_decoration_indices,
        )
    if source_type == "page_footnote":
        return SemanticDecision("paragraph", "body", "page_footnote_preserved_as_page_note", "page_note")
    if source_type in {"title", "heading"}:
        if CAPTION_TITLE_RE.match(text):
            return SemanticDecision("paragraph", "body", "title_demoted_by_caption_role", "standalone_caption")
        if REVISION_RANGE_RE.search(text):
            return SemanticDecision("paragraph", "body", "title_demoted_by_revision_group", "group_label")
        if LOCAL_LABEL_RE.match(text):
            return SemanticDecision("paragraph", "body", "title_demoted_by_local_group_label", "group_label")
        return SemanticDecision(
            "heading",
            "body",
            "source_title_preserved",
            heading_level=resolve_source_heading_level(text, candidate.heading_level),
        )
    return SemanticDecision(candidate.block_type, "body", f"source_type_mapped:{source_type or 'text'}")


def _mark_document_identity(
    candidates: list[SemanticCandidate],
    decisions: dict[int, SemanticDecision],
) -> None:
    """仅把首物理页唯一的顶部宽幅产品标题裁决为首页文档身份。"""

    first_page_index = min(
        (candidate.page_index for candidate in candidates if candidate.page_index is not None),
        default=None,
    )
    if first_page_index is None:
        return
    matches = [
        candidate
        for candidate in candidates
        if candidate.page_index == first_page_index
        and candidate.source_type in {"title", "heading"}
        and decisions[candidate.source_index].reason == "source_title_preserved"
        and _is_top_wide_title(candidate)
        and split_document_identity(candidate.text) is not None
    ]
    if len(matches) != 1:
        return
    candidate = matches[0]
    decisions[candidate.source_index] = SemanticDecision(
        "paragraph",
        "body",
        "first_page_document_identity",
        "document_identity",
    )


def _is_top_wide_title(candidate: SemanticCandidate) -> bool:
    if (
        candidate.bbox is None
        or candidate.page_width is None
        or candidate.page_height is None
        or candidate.page_width <= 0
        or candidate.page_height <= 0
    ):
        return False
    left, _top, right, bottom = candidate.bbox
    return right - left >= candidate.page_width * 0.5 and bottom <= candidate.page_height * 0.2


def _decoration_decision(
    candidate: SemanticCandidate,
    *,
    page_has_regular_content: bool,
    recurring_lines: set[MarginLineKey],
    is_subject_header: bool,
    is_aligned_decoration: bool,
) -> SemanticDecision:
    text = candidate.text.strip()
    if text and len(text) > 200:
        return SemanticDecision(
            "paragraph",
            "body",
            "decoration_candidate_promoted_to_body",
            quality_flags=(f"semantic_decoration_promoted:{candidate.source_index}",),
        )
    if _is_margin_decoration(candidate):
        role = _decoration_role(candidate)
        if is_subject_header:
            return SemanticDecision(
                "paragraph",
                "body",
                "decoration_candidate_promoted_by_page_subject",
                quality_flags=(f"semantic_decoration_promoted:{candidate.source_index}",),
            )
        if _has_recurring_margin_lines(candidate, recurring_lines):
            return SemanticDecision("paragraph", role, "repeated_margin_decoration")
        if text and candidate.page_index is not None and not page_has_regular_content and candidate.source_type != "page_number":
            return SemanticDecision(
                "paragraph",
                "body",
                "decoration_candidate_promoted_to_body",
                quality_flags=(f"semantic_decoration_promoted:{candidate.source_index}",),
            )
        if is_aligned_decoration:
            return SemanticDecision("paragraph", role, "aligned_margin_decoration_group")
        if _is_structured_margin_marker(candidate) and (
            candidate.source_type == "page_number"
            or candidate.source_type in {"header", "page_header"}
            or candidate.bbox is not None
            and candidate.page_height is not None
            and candidate.bbox[1] >= candidate.page_height * 0.75
        ):
            return SemanticDecision("paragraph", role, "structured_margin_marker")
        return SemanticDecision(
            "paragraph",
            "body",
            "ambiguous_margin_decoration_preserved_as_body",
            quality_flags=(f"semantic_decoration_ambiguous:{candidate.source_index}",),
        )
    if text and candidate.page_index is not None and not page_has_regular_content:
        return SemanticDecision(
            "paragraph",
            "body",
            "decoration_candidate_promoted_to_body",
            quality_flags=(f"semantic_decoration_promoted:{candidate.source_index}",),
        )
    return SemanticDecision(
        "paragraph",
        "body",
        "ambiguous_decoration_preserved_as_body",
        quality_flags=(f"semantic_decoration_ambiguous:{candidate.source_index}",),
    )


def _is_margin_decoration(candidate: SemanticCandidate) -> bool:
    if candidate.bbox is None or candidate.page_height is None or candidate.page_height <= 0:
        return False
    _left, top, _right, bottom = candidate.bbox
    if candidate.source_type in {"header", "page_header"}:
        return bottom <= candidate.page_height * 0.12
    # MinerU 的 bbox 与 layout.page_size 可能采用不同的纵向缩放比例。
    # 0.70～0.75 区间只允许跨页重复行或明确页码作为装饰，孤立正文仍保留。
    return top >= candidate.page_height * 0.70


def _structured_subject_pages(candidates: list[SemanticCandidate]) -> set[int]:
    """识别由大图或表格主导、边缘标签可能属于页面主体的页面。"""

    candidates_by_page: dict[int, list[SemanticCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.page_index is not None:
            candidates_by_page[candidate.page_index].append(candidate)

    subject_pages: set[int] = set()
    for page_index, page_candidates in candidates_by_page.items():
        page_width = next((item.page_width for item in page_candidates if item.page_width and item.page_width > 0), None)
        page_height = next((item.page_height for item in page_candidates if item.page_height and item.page_height > 0), None)
        if page_width is None or page_height is None:
            continue
        page_area = page_width * page_height
        area_ratios = [
            max(0.0, item.bbox[2] - item.bbox[0]) * max(0.0, item.bbox[3] - item.bbox[1]) / page_area
            for item in page_candidates
            if item.block_type in {"image", "table"} and item.bbox is not None
        ]
        if not area_ratios:
            continue
        ordinary_count = sum(
            item.source_type not in DECORATION_SOURCE_TYPES and item.block_type not in {"image", "table"}
            for item in page_candidates
        )
        if max(area_ratios) >= 0.18 or sum(area_ratios) >= 0.25 or (max(area_ratios) >= 0.1 and ordinary_count <= 4):
            subject_pages.add(page_index)
    return subject_pages


def _recurring_margin_lines(
    candidates: list[SemanticCandidate],
    *,
    subject_pages: set[int],
) -> tuple[set[MarginLineKey], set[MarginLineKey]]:
    """按跨页覆盖率和稳定边缘位置提取真实重复 decoration 行。"""

    document_pages = {candidate.page_index for candidate in candidates if candidate.page_index is not None}
    if not document_pages:
        return set(), set()
    observations: dict[tuple[str, str], list[tuple[int, tuple[str, int]]]] = defaultdict(list)
    for candidate in candidates:
        if candidate.page_index is None or not candidate.page_width or not _is_margin_decoration(candidate):
            continue
        for line in _line_signatures(candidate.text):
            observations[(_decoration_family(candidate.source_type), line)].append(
                (candidate.page_index, _margin_position_bucket(candidate))
            )

    recurring: set[MarginLineKey] = set()
    recurring_outside_subject: set[MarginLineKey] = set()
    for key, values in observations.items():
        pages = {page_index for page_index, _position in values}
        position_pages: dict[tuple[str, int], set[int]] = defaultdict(set)
        for page_index, position in values:
            position_pages[position].add(page_index)
        stable_positions = sorted(position_pages.items(), key=lambda item: -len(item[1]))[:2]
        stable_pages = set().union(*(group for _position, group in stable_positions))
        if (
            len(pages) < 2
            or (len(pages) / len(document_pages) < 0.2 and len(pages) < 6)
            or len(stable_pages) / len(pages) < 0.8
        ):
            continue
        for position, stable_position_pages in stable_positions:
            if len(stable_position_pages) < (1 if len(pages) == 2 else 2):
                continue
            positioned_key = (*key, position)
            recurring.add(positioned_key)
            if stable_position_pages - subject_pages:
                recurring_outside_subject.add(positioned_key)
    return recurring, recurring_outside_subject


def _subject_header_indices(
    candidates: list[SemanticCandidate],
    *,
    subject_pages: set[int],
    recurring_lines_outside_subject: set[MarginLineKey],
) -> set[int]:
    """逐块绑定技术标签与同页大图/表格主体，不提升同页稳定品牌装饰。"""

    candidates_by_page: dict[int, list[SemanticCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.page_index is not None and candidate.page_index in subject_pages:
            candidates_by_page[candidate.page_index].append(candidate)

    result: set[int] = set()
    for page_candidates in candidates_by_page.values():
        structured_tops = [
            item.bbox[1]
            for item in page_candidates
            if item.block_type in {"image", "table"} and item.bbox is not None
        ]
        if not structured_tops:
            continue
        subject_top = min(structured_tops)
        for candidate in page_candidates:
            if candidate.source_type not in {"header", "page_header"} or candidate.bbox is None:
                continue
            if _has_recurring_margin_lines(candidate, recurring_lines_outside_subject):
                continue
            if _is_structured_margin_marker(candidate):
                continue
            if not _signature(candidate.text):
                continue
            if candidate.bbox[3] <= subject_top and subject_top - candidate.bbox[3] <= (candidate.page_height or 0) * 0.25:
                result.add(candidate.source_index)
    return result


def _aligned_margin_group_indices(
    candidates: list[SemanticCandidate],
    *,
    subject_header_indices: set[int],
) -> set[int]:
    """识别同页横向连续的短顶带导航/装饰组。"""

    headers_by_page: dict[int, list[SemanticCandidate]] = defaultdict(list)
    for candidate in candidates:
        if (
            candidate.page_index is not None
            and candidate.source_type in {"header", "page_header"}
            and candidate.source_index not in subject_header_indices
            and _is_margin_decoration(candidate)
            and candidate.bbox is not None
            and candidate.page_width
            and candidate.page_height
            and len(_signature(candidate.text)) <= 80
        ):
            headers_by_page[candidate.page_index].append(candidate)

    result: set[int] = set()
    for page_headers in headers_by_page.values():
        for anchor in page_headers:
            assert anchor.bbox is not None and anchor.page_width and anchor.page_height
            row = [
                item
                for item in page_headers
                if item.bbox is not None
                and abs(item.bbox[1] - anchor.bbox[1]) <= anchor.page_height * 0.01
                and abs(item.bbox[3] - anchor.bbox[3]) <= anchor.page_height * 0.01
            ]
            if len(row) < 3:
                continue
            span = max(item.bbox[2] for item in row if item.bbox) - min(item.bbox[0] for item in row if item.bbox)
            if span >= anchor.page_width * 0.4:
                result.update(item.source_index for item in row)
    return result


def _has_recurring_margin_lines(candidate: SemanticCandidate, recurring_lines: set[MarginLineKey]) -> bool:
    lines = _line_signatures(candidate.text)
    family = _decoration_family(candidate.source_type)
    if not lines or candidate.bbox is None or not candidate.page_width or not candidate.page_height:
        return False
    position = _margin_position_bucket(candidate)
    return all((family, line, position) in recurring_lines for line in lines)


def _line_signatures(text: str) -> tuple[str, ...]:
    return tuple(signature for line in text.splitlines() if (signature := _signature(line)))


def _decoration_family(source_type: str) -> str:
    if source_type in {"header", "page_header"}:
        return "header"
    if source_type == "page_number":
        return "page_number"
    return "footer"


def _decoration_role(candidate: SemanticCandidate) -> DocumentIRBlockRole:
    if candidate.source_type in {"header", "page_header"}:
        return "page_header"
    if candidate.source_type == "page_number":
        return "page_number"
    return "page_footer"


def _margin_position_bucket(candidate: SemanticCandidate) -> tuple[str, int]:
    assert candidate.bbox is not None and candidate.page_width and candidate.page_height
    center_x = (candidate.bbox[0] + candidate.bbox[2]) / 2 / candidate.page_width
    horizontal = "left" if center_x < 0.35 else "right" if center_x > 0.65 else "center"
    center_y = (candidate.bbox[1] + candidate.bbox[3]) / 2 / candidate.page_height
    return horizontal, round(center_y * 10)


def _is_structured_margin_marker(candidate: SemanticCandidate) -> bool:
    text = _signature(candidate.text)
    if not text:
        return True
    compact = "".join(character for character in text if character.isalnum())
    if len(compact) <= 1:
        return True
    if candidate.source_type == "page_number" and len(text) <= 32:
        return True
    if candidate.source_type in {"footer", "page_footer"} and "\n" not in candidate.text and len(text) <= 64:
        return True
    return DATE_MARKER_RE.fullmatch(text) is not None or URL_MARKER_RE.fullmatch(text) is not None


def _mark_toc_regions(
    candidates: list[SemanticCandidate],
    decisions: dict[int, SemanticDecision],
) -> None:
    for position, candidate in enumerate(candidates):
        if candidate.source_type not in {"title", "heading"} or not is_toc_title_text(candidate.text):
            continue
        toc_positions: list[int] = []
        entry_count = 0
        parsed_entry_count = 0
        for following in candidates[position + 1 :]:
            if following.page_index != candidate.page_index:
                break
            values = following.list_items or tuple(line.strip() for line in following.text.splitlines() if line.strip())
            if not values:
                break
            parsed_count = sum(parse_toc_entry_text(value) is not None for value in values)
            if parsed_count == 0 or parsed_count / len(values) < 0.6:
                break
            toc_positions.append(following.source_index)
            entry_count += len(values)
            parsed_entry_count += parsed_count
        if entry_count < 3 or parsed_entry_count / entry_count < 0.6:
            continue
        decisions[candidate.source_index] = SemanticDecision(
            "paragraph",
            "body",
            "toc_title_and_anchor",
            "toc_title",
            insert_toc_anchor=True,
        )
        for source_index in toc_positions:
            original = decisions[source_index]
            decisions[source_index] = SemanticDecision(
                original.block_type,
                "toc_source",
                "explicit_toc_region_source",
            )


def _mark_decimal_list_runs(
    candidates: list[SemanticCandidate],
    decisions: dict[int, SemanticDecision],
) -> None:
    """仅把同页、源顺序相邻且序号严格连续的至少两项裁决为列表。"""

    position = 0
    while position < len(candidates):
        first = candidates[position]
        first_item = _decimal_list_candidate(first)
        if first_item is None or first.page_index is None:
            position += 1
            continue

        end = position + 1
        previous_number = first_item[0]
        while end < len(candidates):
            current = candidates[end]
            current_item = _decimal_list_candidate(current)
            if (
                current.page_index != first.page_index
                or current_item is None
                or current_item[0] != previous_number + 1
            ):
                break
            previous_number = current_item[0]
            end += 1

        if end - position >= 2:
            for candidate in candidates[position:end]:
                decisions[candidate.source_index] = SemanticDecision(
                    "list",
                    "body",
                    "sequential_decimal_list",
                )
            position = end
            continue
        position += 1


def _decimal_list_candidate(candidate: SemanticCandidate) -> tuple[int, str] | None:
    if candidate.source_type not in {"", "text", "paragraph", "para", "title", "heading"}:
        return None
    if candidate.block_type not in {"heading", "paragraph"}:
        return None
    return parse_decimal_list_marker(candidate.text)


def _signature(text: str) -> str:
    return " ".join(text.lower().split())
