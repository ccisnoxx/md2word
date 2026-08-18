"""供兼容运行时与 DocumentIR 路径复用的 MinerU 内容抽取规则。"""

from __future__ import annotations

# 文件：app/conversion/docx_rules/mineru_content.py
# 用途：在不依赖渲染器的前提下归一化 MinerU 文本、题注、表注、HTML 和资产路径。

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
NUMBERED_HEADING_RE = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百千万零〇0-9]+\s*[章节篇部]|"
    r"(?:chapter|section|part)\s+\d+|\d+(?:[.．]\d+)*[、.．\s]+\S)",
    re.IGNORECASE,
)
NUMBERED_CAPTION_RE = re.compile(r"^\s*(?:图|表|figure|table)\s*\d+", re.IGNORECASE)
PROMOTIONAL_BODY_TEXT_LIMIT = 160
PAGE_DECORATION_TYPES = {"header", "footer", "page_header", "page_footer", "page_number"}
FORMULA_TYPES = {
    "equation",
    "formula",
    "interline_equation",
    "inline_equation",
    "equation_inline",
    "equation_interline",
    "inline_formula",
}


def clean_markdown_document(text: str) -> str:
    """删除非正文 details 块，同时保留有效 Markdown 文本。"""

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


def find_final_promotional_page(
    raw_blocks: list[dict[str, Any]],
    *,
    final_page_index: int | None = None,
) -> int | None:
    """只在证据完整且无实质内容时识别最后物理页的推广封底。"""

    resolved_final_index = final_page_index
    if resolved_final_index is None:
        page_indices = [page_index for block in raw_blocks if (page_index := _raw_page_index(block)) is not None]
        resolved_final_index = max(page_indices, default=None)
    if resolved_final_index is None:
        return None

    page_blocks = [block for block in raw_blocks if _raw_page_index(block) == resolved_final_index]
    body_blocks = [block for block in page_blocks if _source_type(block) not in PAGE_DECORATION_TYPES]
    if not body_blocks or not _has_promotional_cta(_body_text(body_blocks)):
        return None
    if not any(
        _source_type(block) in {"image", "figure"} and extract_first_asset_path(block)
        for block in body_blocks
    ):
        return None
    if _has_substantive_structure(body_blocks):
        return None
    return resolved_final_index


def _has_promotional_cta(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text).lower()
    scan = any(token in normalized for token in ("扫码", "扫描", "扫一扫"))
    action = any(token in normalized for token in ("进入", "打开", "关注"))
    return any(
        (
            "微信" in normalized and scan and action,
            "小程序" in normalized and any(token in normalized for token in ("进入", "打开", "扫码")),
            "长按" in normalized and "识别" in normalized and "二维码" in normalized,
            "扫一扫" in normalized and any(token in normalized for token in ("进入", "打开")),
        )
    )


def _has_substantive_structure(blocks: list[dict[str, Any]]) -> bool:
    if len(re.sub(r"\s+", "", _body_text(blocks))) > PROMOTIONAL_BODY_TEXT_LIMIT:
        return True

    for block in blocks:
        source_type = _source_type(block)
        nested_types = {str(value).strip().lower() for value in find_values_by_key(block, "type")}
        if source_type == "table" and extract_first_html(block):
            return True
        if source_type in FORMULA_TYPES or nested_types & FORMULA_TYPES:
            return True
        if source_type in {"list", "index"}:
            return True

        texts = coerce_text_list(block)
        if (source_type in {"title", "heading"} or block.get("text_level") is not None) and any(
            NUMBERED_HEADING_RE.match(text) for text in texts
        ):
            return True
        captions = collect_text_from_fields(
            block,
            ("caption", "captions", "image_caption", "figure_caption", "table_caption", "chart_caption"),
        )
        if any(NUMBERED_CAPTION_RE.match(caption) for caption in captions):
            return True
    return False


def _body_text(blocks: list[dict[str, Any]]) -> str:
    return " ".join(text for block in blocks for text in coerce_text_list(block))


def _source_type(block: dict[str, Any]) -> str:
    return str(block.get("type") or block.get("block_type") or "").strip().lower()


def _raw_page_index(block: dict[str, Any]) -> int | None:
    raw_page_index = block.get("page_idx", block.get("page_index"))
    try:
        return int(raw_page_index)
    except (TypeError, ValueError):
        return None


def merge_footnote_fragments(texts: list[str]) -> list[str]:
    """合并 MinerU 富文本脚注片段，同时保留相互独立的脚注。"""

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


def is_empty_table_placeholder(
    *,
    block_type: str,
    raw_asset_path: str | None,
    image_path: Path | None,
    captions: list[str],
    html: str | None,
    text_candidates: list[str],
    bbox: tuple[float, float, float, float],
) -> bool:
    """识别 MinerU 用空表资产表示的续表占位块。"""

    if block_type != "table" or html or captions or text_candidates:
        return False

    raw = (raw_asset_path or "").strip().lower()
    if raw_asset_path is not None and not raw:
        return True
    if raw in {"images", "images/", "./images", "./images/"}:
        return True

    return image_path is not None and bbox[0] <= 130 and bbox[1] <= 100 and bbox[2] >= 860 and bbox[3] >= 880
