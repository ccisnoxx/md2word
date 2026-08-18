from __future__ import annotations

# app/conversion/runtime/input_adapter_runtime.py
# MinerU 输入适配与块级文本规整。

import json
import re
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.conversion.docx_rules import mineru_content as _shared_mineru_content
from app.conversion.runtime.page_repair_runtime import (
    attach_table_continuations,
    backfill_middle_visual_metadata,
    bbox_distance,
    collect_placeholder_continuation_heights,
    find_best_visual_match,
    get_page_body_blocks,
    merge_middle_header_footer_blocks,
    merge_page_with_middle,
    repair_and_sort_pages,
)
from app.services.document_ir.layout_signals import find_final_source_page_index


_RUNTIME_MODULE: Any | None = None
DETAILS_BLOCK_RE = re.compile(r"<details\b[^>]*>.*?</details>", re.IGNORECASE | re.DOTALL)
TOC_DOT_LEADER_LINE_RE = re.compile(r"\S.*(?:\.{2,}|·{2,}|…{2,})\s*\d+\s*$")
FOOTNOTE_START_RE = re.compile(
    r"^\s*(?:\(?\d+\)|\[\d+\]|\d+[.)、]|[a-z][.)])\s+",
    re.IGNORECASE,
)
FOOTNOTE_LABEL_RE = re.compile(r"^\s*(?:notes?|注|备注|说明)\s*[:：]", re.IGNORECASE)
INLINE_FORMULA_MARKUP_RE = re.compile(r"</?(?:sub|sup)>", re.IGNORECASE)
is_empty_table_placeholder = _shared_mineru_content.is_empty_table_placeholder


def bind_runtime(module: Any) -> None:
    global _RUNTIME_MODULE
    _RUNTIME_MODULE = module


def _runtime_value(name: str, default: Any) -> Any:
    if _RUNTIME_MODULE is None:
        return default
    return getattr(_RUNTIME_MODULE, name, default)


class _NullLogger:
    def debug(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def info(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def warning(self, *_args: Any, **_kwargs: Any) -> None:
        return


def _logger() -> Any:
    return _runtime_value("logger", _NullLogger())


def _block_cls() -> Any:
    cls = _runtime_value("Block", None)
    if cls is None:
        raise RuntimeError("Block is not bound")
    return cls


def _page_data_cls() -> Any:
    cls = _runtime_value("PageData", None)
    if cls is None:
        raise RuntimeError("PageData is not bound")
    return cls


def _middle_page_cls() -> Any:
    cls = _runtime_value("MiddlePage", None)
    if cls is None:
        raise RuntimeError("MiddlePage is not bound")
    return cls


def _visual_types() -> set[str]:
    return _runtime_value("VISUAL_TYPES", set())


def _image_extensions() -> set[str]:
    return _runtime_value("IMAGE_EXTENSIONS", set())


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    symlink_mask = 0o120000

    for member in archive.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"zip 包含非法路径: {member.filename}")
        if ((member.external_attr >> 16) & 0o170000) == symlink_mask:
            raise ValueError(f"zip 包含不支持的符号链接条目: {member.filename}")

        target_path = (root / member.filename).resolve()
        if target_path != root and root not in target_path.parents:
            raise ValueError(f"zip 目标路径越界: {member.filename}")

        if member.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target_path.open("wb") as target:
            shutil.copyfileobj(source, target)


@contextmanager
def materialize_input(input_path: Path) -> Iterator[Path]:
    if input_path.is_dir():
        yield input_path
        return

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="mineru_docx_") as temp_dir:
            with zipfile.ZipFile(input_path) as zip_file:
                _safe_extract_zip(zip_file, Path(temp_dir))
            yield Path(temp_dir)
        return

    raise FileNotFoundError(f"不支持的输入路径: {input_path}")


def load_pages(package_root: Path) -> tuple[list[Any], Path]:
    load_content_pages_fn = _runtime_value("load_content_pages", load_content_pages)
    load_middle_pages_fn = _runtime_value("load_middle_pages", load_middle_pages)
    repair_and_sort_pages_fn = _runtime_value("repair_and_sort_pages", repair_and_sort_pages)
    attach_table_continuations_fn = _runtime_value("attach_table_continuations", attach_table_continuations)

    pages, source_path = load_content_pages_fn(package_root)
    middle_pages = load_middle_pages_fn(package_root)
    _logger().info("loaded content pages={} source={}", len(pages), source_path)
    if middle_pages:
        _logger().info("loaded middle pages={}", len(middle_pages))

    merged_pages = repair_and_sort_pages_fn(pages, middle_pages)
    attach_table_continuations_fn(merged_pages)
    return merged_pages, source_path


def load_content_pages(package_root: Path) -> tuple[list[Any], Path]:
    find_first_file_fn = _runtime_value("find_first_file", find_first_file)
    build_v2_pages_fn = _runtime_value("build_v2_pages", build_v2_pages)
    build_legacy_pages_fn = _runtime_value("build_legacy_pages", build_legacy_pages)
    build_missing_content_list_message_fn = _runtime_value(
        "build_missing_content_list_message",
        build_missing_content_list_message,
    )

    v2_path = find_first_file_fn(
        package_root,
        exact_names=("content_list_v2.json",),
        suffixes=("_content_list_v2.json",),
    )
    if v2_path:
        raw_pages = json.loads(v2_path.read_text(encoding="utf-8"))
        promotional_page_index = _find_final_promotional_v2_page(raw_pages, package_root)
        if promotional_page_index is not None:
            raw_pages = [page for page_index, page in enumerate(raw_pages) if page_index != promotional_page_index]
        return build_v2_pages_fn(raw_pages, package_root), v2_path

    legacy_path = find_first_file_fn(
        package_root,
        exact_names=("content_list.json",),
        suffixes=("_content_list.json",),
    )
    if legacy_path:
        raw_items = json.loads(legacy_path.read_text(encoding="utf-8"))
        promotional_page_index = _shared_mineru_content.find_final_promotional_page(
            raw_items,
            final_page_index=find_final_source_page_index(raw_items, package_root),
        )
        if promotional_page_index is not None:
            raw_items = [item for item in raw_items if _raw_page_index(item) != promotional_page_index]
        return build_legacy_pages_fn(raw_items, package_root), legacy_path

    raise FileNotFoundError(build_missing_content_list_message_fn(package_root))


def _find_final_promotional_v2_page(raw_pages: list[Any], package_root: Path) -> int | None:
    raw_blocks: list[dict[str, Any]] = []
    for page_index, page in enumerate(raw_pages):
        if not isinstance(page, list):
            continue
        for item in page:
            if not isinstance(item, dict):
                continue
            copied = dict(item)
            copied.setdefault("page_idx", page_index)
            raw_blocks.append(copied)
    return _shared_mineru_content.find_final_promotional_page(
        raw_blocks,
        final_page_index=find_final_source_page_index(raw_blocks, package_root),
    )


def _raw_page_index(raw_block: dict[str, Any]) -> int | None:
    raw_page_index = raw_block.get("page_idx", raw_block.get("page_index"))
    try:
        return int(raw_page_index)
    except (TypeError, ValueError):
        return None


def build_v2_pages(raw_pages: list[Any], package_root: Path) -> list[Any]:
    parse_v2_block_fn = _runtime_value("parse_v2_block", parse_v2_block)
    page_data_cls = _page_data_cls()
    pages: list[Any] = []
    for page_idx, raw_page in enumerate(raw_pages):
        blocks = [
            block
            for block_idx, item in enumerate(raw_page)
            if (block := parse_v2_block_fn(item, package_root, page_idx=page_idx, block_idx=block_idx))
        ]
        pages.append(page_data_cls(page_idx=page_idx, blocks=sorted(blocks, key=lambda block: (block.y1, block.x1))))
    return pages


def build_legacy_pages(raw_items: list[dict[str, Any]], package_root: Path) -> list[Any]:
    parse_legacy_block_fn = _runtime_value("parse_legacy_block", parse_legacy_block)
    page_data_cls = _page_data_cls()
    page_map: dict[int, list[Any]] = {}
    for item in raw_items:
        page_idx = int(item.get("page_idx", 0))
        block = parse_legacy_block_fn(item, package_root, page_idx=page_idx, block_idx=len(page_map.get(page_idx, [])))
        if not block:
            continue
        page_map.setdefault(page_idx, []).append(block)

    return [
        page_data_cls(page_idx=page_idx, blocks=sorted(page_map[page_idx], key=lambda block: (block.y1, block.x1)))
        for page_idx in sorted(page_map)
    ]


def load_middle_pages(package_root: Path) -> dict[int, Any]:
    find_first_file_fn = _runtime_value("find_first_file", find_first_file)
    parse_page_size_fn = _runtime_value("parse_page_size", parse_page_size)
    parse_middle_discarded_block_fn = _runtime_value("parse_middle_discarded_block", parse_middle_discarded_block)
    collect_middle_visual_blocks_fn = _runtime_value("collect_middle_visual_blocks", collect_middle_visual_blocks)
    middle_page_cls = _middle_page_cls()

    page_info_path = find_first_file_fn(
        package_root,
        exact_names=("middle.json",),
        suffixes=("_middle.json",),
    )
    if not page_info_path:
        page_info_path = find_first_file_fn(
            package_root,
            exact_names=("layout.json",),
            suffixes=("_layout.json",),
        )
    if not page_info_path:
        return {}

    raw_middle = json.loads(page_info_path.read_text(encoding="utf-8"))
    pdf_info = raw_middle.get("pdf_info", []) if isinstance(raw_middle, dict) else []
    middle_pages: dict[int, Any] = {}

    for page_idx, page_info in enumerate(pdf_info):
        current_idx = int(page_info.get("page_idx", page_idx))
        page_size = parse_page_size_fn(page_info.get("page_size"))
        discarded_blocks = [
            block
            for raw_block in page_info.get("discarded_blocks", [])
            if (block := parse_middle_discarded_block_fn(raw_block))
        ]
        visual_blocks = collect_middle_visual_blocks_fn(page_info, package_root)
        middle_pages[current_idx] = middle_page_cls(
            page_idx=current_idx,
            page_size=page_size,
            discarded_blocks=discarded_blocks,
            visual_blocks=visual_blocks,
        )

    return middle_pages


def parse_v2_block(item: dict[str, Any], package_root: Path, *, page_idx: int, block_idx: int) -> Any | None:
    parse_bbox_fn = _runtime_value("parse_bbox", parse_bbox)
    parse_v2_text_block_fn = _runtime_value("parse_v2_text_block", parse_v2_text_block)
    parse_v2_page_decoration_block_fn = _runtime_value("parse_v2_page_decoration_block", parse_v2_page_decoration_block)
    parse_visual_block_fn = _runtime_value("parse_visual_block", parse_visual_block)
    coerce_text_list_fn = _runtime_value("coerce_text_list", coerce_text_list)
    block_cls = _block_cls()

    block_type = str(item.get("type", "")).strip()
    bbox = parse_bbox_fn(item.get("bbox"))
    content = item.get("content", {})

    text_block = parse_v2_text_block_fn(block_type, bbox, content, page_idx=page_idx, block_idx=block_idx)
    if text_block is not None:
        return text_block

    page_decoration_block = parse_v2_page_decoration_block_fn(block_type, bbox, content, page_idx=page_idx, block_idx=block_idx)
    if page_decoration_block is not None:
        return page_decoration_block

    if block_type in _visual_types():
        return parse_visual_block_fn(block_type, bbox, content, package_root, page_idx=page_idx, block_idx=block_idx)

    if block_type == "equation":
        text = " ".join(coerce_text_list_fn(content.get("equation_content")))
        return block_cls(type="paragraph", bbox=bbox, text=text, page_idx=page_idx, block_idx=block_idx)

    return None


def parse_v2_text_block(
    block_type: str,
    bbox: tuple[float, float, float, float],
    content: dict[str, Any],
    *,
    page_idx: int,
    block_idx: int,
) -> Any | None:
    join_text_fragments_fn = _runtime_value("join_text_fragments", join_text_fragments)
    split_toc_like_lines_fn = _runtime_value("split_toc_like_lines", split_toc_like_lines)
    block_cls = _block_cls()

    if block_type == "title":
        return block_cls(
            type="title",
            bbox=bbox,
            text=join_text_fragments_fn(content.get("title_content", [])),
            level=int(content.get("level", 1) or 1),
            page_idx=page_idx,
            block_idx=block_idx,
        )

    if block_type == "paragraph":
        raw_text = join_text_fragments_fn(content.get("paragraph_content", []), clean=False)
        toc_items = split_toc_like_lines_fn(raw_text)
        if toc_items:
            return block_cls(
                type="list",
                bbox=bbox,
                items=toc_items,
                page_idx=page_idx,
                block_idx=block_idx,
            )
        return block_cls(
            type="paragraph",
            bbox=bbox,
            text=join_text_fragments_fn(content.get("paragraph_content", [])),
            page_idx=page_idx,
            block_idx=block_idx,
        )

    if block_type in {"list", "index"}:
        items = [
            join_text_fragments_fn(list_item.get("item_content", []))
            for list_item in content.get("list_items", [])
        ]
        return block_cls(
            type="list",
            bbox=bbox,
            items=[value for value in items if value],
            page_idx=page_idx,
            block_idx=block_idx,
        )

    return None


def parse_v2_page_decoration_block(
    block_type: str,
    bbox: tuple[float, float, float, float],
    content: dict[str, Any],
    *,
    page_idx: int,
    block_idx: int,
) -> Any | None:
    join_text_fragments_fn = _runtime_value("join_text_fragments", join_text_fragments)
    block_cls = _block_cls()

    field_name_map = {
        "page_header": "page_header_content",
        "page_footer": "page_footer_content",
        "page_number": "page_number_content",
    }
    field_name = field_name_map.get(block_type)
    if field_name is None:
        return None

    return block_cls(
        type=block_type,
        bbox=bbox,
        text=join_text_fragments_fn(content.get(field_name, [])),
        page_idx=page_idx,
        block_idx=block_idx,
    )


def parse_legacy_block(item: dict[str, Any], package_root: Path, *, page_idx: int, block_idx: int) -> Any | None:
    parse_bbox_fn = _runtime_value("parse_bbox", parse_bbox)
    clean_text_fn = _runtime_value("clean_text", clean_text)
    parse_visual_block_fn = _runtime_value("parse_visual_block", parse_visual_block)
    block_cls = _block_cls()

    block_type = str(item.get("type", "")).strip()
    bbox = parse_bbox_fn(item.get("bbox"))

    if block_type == "text":
        text = clean_text_fn(str(item.get("text", "")))
        if not text:
            return None
        level = int(item.get("text_level", 0) or 0)
        normalized_type = "title" if level > 0 else "paragraph"
        return block_cls(type=normalized_type, bbox=bbox, text=text, level=max(level, 1), page_idx=page_idx, block_idx=block_idx)

    if block_type == "list":
        items = [clean_text_fn(str(value)) for value in item.get("list_items", [])]
        return block_cls(type="list", bbox=bbox, items=[value for value in items if value], page_idx=page_idx, block_idx=block_idx)

    if block_type == "header":
        return block_cls(type="page_header", bbox=bbox, text=clean_text_fn(str(item.get("text", ""))), page_idx=page_idx, block_idx=block_idx)

    if block_type == "footer":
        return block_cls(type="page_footer", bbox=bbox, text=clean_text_fn(str(item.get("text", ""))), page_idx=page_idx, block_idx=block_idx)

    if block_type == "page_number":
        return block_cls(type="page_number", bbox=bbox, text=clean_text_fn(str(item.get("text", ""))), page_idx=page_idx, block_idx=block_idx)

    if block_type in _visual_types():
        return parse_visual_block_fn(block_type, bbox, item, package_root, page_idx=page_idx, block_idx=block_idx)

    return None


def collect_visual_block_metadata(
    payload: dict[str, Any],
    package_root: Path,
    *,
    caption_fields: tuple[str, ...],
    footnote_fields: tuple[str, ...],
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    extract_first_asset_path_fn = _runtime_value("extract_first_asset_path", extract_first_asset_path)
    parse_bbox_fn = _runtime_value("parse_bbox", parse_bbox)
    resolve_asset_path_fn = _runtime_value("resolve_asset_path", resolve_asset_path)
    collect_text_from_fields_fn = _runtime_value("collect_text_from_fields", collect_text_from_fields)
    merge_footnote_fragments_fn = _runtime_value("merge_footnote_fragments", merge_footnote_fragments)
    extract_first_html_fn = _runtime_value("extract_first_html", extract_first_html)

    footnotes = collect_text_from_fields_fn(payload, footnote_fields)
    raw_asset_path = extract_first_asset_path_fn(payload)
    return {
        "bbox": bbox if bbox is not None else parse_bbox_fn(payload.get("bbox")),
        "raw_asset_path": raw_asset_path,
        "image_path": resolve_asset_path_fn(package_root, raw_asset_path),
        "captions": collect_text_from_fields_fn(payload, caption_fields),
        "footnotes": merge_footnote_fragments_fn(footnotes),
        "html": extract_first_html_fn(payload),
    }


def parse_visual_block(
    block_type: str,
    bbox: tuple[float, float, float, float],
    payload: dict[str, Any],
    package_root: Path,
    *,
    page_idx: int | None = None,
    block_idx: int | None = None,
) -> Any:
    collect_visual_block_metadata_fn = _runtime_value("collect_visual_block_metadata", collect_visual_block_metadata)
    normalize_visual_key_fn = _runtime_value("normalize_visual_key", normalize_visual_key)
    collect_text_from_fields_fn = _runtime_value("collect_text_from_fields", collect_text_from_fields)
    is_empty_table_placeholder_fn = _runtime_value("is_empty_table_placeholder", is_empty_table_placeholder)
    block_cls = _block_cls()

    metadata = collect_visual_block_metadata_fn(
        payload,
        package_root,
        caption_fields=(
            f"{normalize_visual_key_fn(block_type)}_caption",
            "caption",
            "captions",
            "image_caption",
            "table_caption",
            "chart_caption",
        ),
        footnote_fields=(
            f"{normalize_visual_key_fn(block_type)}_footnote",
            "footnote",
            "footnotes",
            "image_footnote",
            "table_footnote",
            "chart_footnote",
        ),
        bbox=bbox,
    )
    text_candidates = collect_text_from_fields_fn(
        payload,
        ("equation_content", "math_content", "latex", "alt", "description"),
    )

    if is_empty_table_placeholder_fn(
        block_type=block_type,
        raw_asset_path=metadata["raw_asset_path"],
        image_path=metadata["image_path"],
        captions=metadata["captions"],
        html=metadata["html"],
        text_candidates=text_candidates,
        bbox=bbox,
    ):
        _logger().debug(
            "skip empty table placeholder page={} block={} bbox={} raw_asset_path={}",
            page_idx,
            block_idx,
            bbox,
            metadata["raw_asset_path"],
        )
        return block_cls(
            type="table_placeholder",
            bbox=bbox,
            image_path=metadata["image_path"],
            page_idx=page_idx,
            block_idx=block_idx,
        )

    block = block_cls(
        type=block_type,
        bbox=bbox,
        text=" ".join(text_candidates).strip(),
        image_path=metadata["image_path"],
        captions=metadata["captions"],
        footnotes=metadata["footnotes"],
        html=metadata["html"],
        page_idx=page_idx,
        block_idx=block_idx,
    )
    _logger().debug(
        "visual block type={} page={} block={} bbox={} image_path={} has_html={} caption={}",
        block_type,
        page_idx,
        block_idx,
        bbox,
        metadata["image_path"],
        bool(block.html),
        metadata["captions"][0] if metadata["captions"] else "N/A",
    )
    return block


def normalize_visual_key(block_type: str) -> str:
    if block_type == "equation_interline":
        return "equation"
    return block_type


def parse_middle_discarded_block(raw_block: dict[str, Any]) -> Any | None:
    parse_bbox_fn = _runtime_value("parse_bbox", parse_bbox)
    extract_middle_block_text_fn = _runtime_value("extract_middle_block_text", extract_middle_block_text)
    block_cls = _block_cls()

    block_type = str(raw_block.get("type", "")).strip()
    bbox = parse_bbox_fn(raw_block.get("bbox"))
    text = extract_middle_block_text_fn(raw_block)
    if block_type == "header":
        return block_cls(type="page_header", bbox=bbox, text=text)
    if block_type == "footer":
        return block_cls(type="page_footer", bbox=bbox, text=text)
    if block_type == "page_number":
        return block_cls(type="page_number", bbox=bbox, text=text)
    return None


def collect_middle_visual_blocks(page_info: dict[str, Any], package_root: Path) -> list[Any]:
    collect_visual_block_metadata_fn = _runtime_value("collect_visual_block_metadata", collect_visual_block_metadata)
    extract_middle_block_text_fn = _runtime_value("extract_middle_block_text", extract_middle_block_text)
    block_cls = _block_cls()
    candidates: list[Any] = []
    seen: set[tuple[Any, ...]] = set()

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if not isinstance(node, dict):
            return

        node_type = str(node.get("type", "")).strip()
        if node_type in _visual_types():
            metadata = collect_visual_block_metadata_fn(
                node,
                package_root,
                caption_fields=(
                    "image_caption",
                    "table_caption",
                    "chart_caption",
                    "caption",
                    "captions",
                ),
                footnote_fields=(
                    "image_footnote",
                    "table_footnote",
                    "chart_footnote",
                    "footnote",
                    "footnotes",
                ),
            )
            text = extract_middle_block_text_fn(node)
            bbox = metadata["bbox"]
            key = (
                node_type,
                round(bbox[0], 2),
                round(bbox[1], 2),
                round(bbox[2], 2),
                round(bbox[3], 2),
                str(metadata["image_path"] or ""),
            )
            if key not in seen:
                seen.add(key)
                candidates.append(
                    block_cls(
                        type=node_type,
                        bbox=bbox,
                        text=text,
                        image_path=metadata["image_path"],
                        captions=metadata["captions"],
                        footnotes=metadata["footnotes"],
                        html=metadata["html"],
                    )
                )

        for child in node.values():
            visit(child)

    for key in ("para_blocks", "preproc_blocks", "discarded_blocks", "images", "tables", "interline_equations"):
        visit(page_info.get(key, []))

    return candidates


def parse_bbox(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(float(item) for item in value)
    return (0.0, 0.0, 0.0, 0.0)


def parse_page_size(value: Any) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return None


def join_text_fragments(nodes: list[dict[str, Any]], *, clean: bool = True) -> str:
    clean_text_fn = _runtime_value("clean_text", clean_text)
    normalize_formula_text_fn = _runtime_value("normalize_formula_text", lambda text: text)
    parts: list[str] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type == "text":
            parts.append(str(node.get("content", "")))
        elif node_type == "equation_inline" and isinstance(node.get("content"), str):
            parts.append(f" {normalize_formula_text_fn(node['content'])} ")
        elif "content" in node and isinstance(node["content"], str):
            parts.append(node["content"])
    text = "".join(parts)
    return clean_text_fn(text) if clean else text


def split_toc_like_lines(text: str) -> list[str]:
    clean_text_fn = _runtime_value("clean_text", clean_text)
    lines = [clean_text_fn(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 3:
        return []

    toc_like = sum(1 for line in lines if TOC_DOT_LEADER_LINE_RE.match(line))
    if toc_like / len(lines) < 0.7:
        return []
    return lines


def coerce_text_list(value: Any) -> list[str]:
    clean_text_fn = _runtime_value("clean_text", clean_text)
    normalize_formula_text_fn = _runtime_value("normalize_formula_text", lambda text: text)
    looks_like_asset_path_fn = _runtime_value("looks_like_asset_path", looks_like_asset_path)
    looks_like_html_fn = _runtime_value("looks_like_html", looks_like_html)
    texts: list[str] = []

    if value is None:
        return texts

    if isinstance(value, str):
        text = clean_text_fn(value)
        if text and not looks_like_asset_path_fn(text) and not looks_like_html_fn(text):
            texts.append(text)
        return texts

    if isinstance(value, list):
        for item in value:
            texts.extend(coerce_text_list(item))
        return texts

    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "text" and isinstance(value.get("content"), str):
            text = clean_text_fn(value["content"])
            if text:
                texts.append(text)
            return texts
        if node_type in {"equation_inline", "inline_formula"} and isinstance(value.get("content"), str):
            text = clean_text_fn(normalize_formula_text_fn(value["content"]))
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
    find_values_by_key_fn = _runtime_value("find_values_by_key", find_values_by_key)
    coerce_text_list_fn = _runtime_value("coerce_text_list", coerce_text_list)
    seen: set[str] = set()
    collected: list[str] = []
    for field_name in field_names:
        for value in find_values_by_key_fn(payload, field_name):
            for text in coerce_text_list_fn(value):
                if text and text not in seen:
                    seen.add(text)
                    collected.append(text)
    return collected


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
    looks_like_asset_path_fn = _runtime_value("looks_like_asset_path", looks_like_asset_path)
    if isinstance(node, str):
        return node if looks_like_asset_path_fn(node) else None

    if isinstance(node, list):
        for item in node:
            path = extract_first_asset_path(item)
            if path:
                return path
        return None

    if isinstance(node, dict):
        for key in ("img_path", "image_path", "path"):
            value = node.get(key)
            if isinstance(value, str) and looks_like_asset_path_fn(value):
                return value
        for value in node.values():
            path = extract_first_asset_path(value)
            if path:
                return path
    return None


def resolve_asset_path(package_root: Path, raw_path: str | None) -> Path | None:
    normalize_asset_path_fn = _runtime_value("normalize_asset_path", normalize_asset_path)
    if not raw_path:
        return None

    candidate = Path(raw_path)
    if candidate.is_absolute() and candidate.exists():
        return normalize_asset_path_fn(candidate)

    direct = (package_root / candidate).resolve()
    if direct.exists():
        return normalize_asset_path_fn(direct)

    by_name = sorted(package_root.rglob(candidate.name), key=lambda path: (len(path.parts), str(path)))
    for path in by_name:
        normalized = normalize_asset_path_fn(path)
        if normalized is not None:
            return normalized
    return None


def normalize_asset_path(path: Path) -> Path | None:
    if path.is_file():
        return path if path.suffix.lower() in _image_extensions() else None

    if path.is_dir():
        images = sorted(
            [child for child in path.iterdir() if child.is_file() and child.suffix.lower() in _image_extensions()],
            key=lambda child: child.name,
        )
        return images[0] if images else None

    return None


def looks_like_asset_path(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    if Path(lowered).suffix in _image_extensions():
        return True
    return lowered.startswith("images/")


def looks_like_html(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith("<table") or lowered.startswith("<img")


def extract_first_html(node: Any) -> str | None:
    looks_like_html_fn = _runtime_value("looks_like_html", looks_like_html)
    clean_markdown_document_fn = _runtime_value("clean_markdown_document", clean_markdown_document)
    if isinstance(node, str):
        stripped = clean_markdown_document_fn(node).strip()
        return stripped if looks_like_html_fn(stripped) else None

    if isinstance(node, list):
        for item in node:
            html = extract_first_html(item)
            if html:
                return html
        return None

    if isinstance(node, dict):
        direct = node.get("html")
        if isinstance(direct, str):
            cleaned_direct = clean_markdown_document_fn(direct).strip()
            if looks_like_html_fn(cleaned_direct):
                return cleaned_direct
        for value in node.values():
            html = extract_first_html(value)
            if html:
                return html
    return None


def extract_middle_block_text(node: dict[str, Any]) -> str:
    clean_text_fn = _runtime_value("clean_text", clean_text)
    fragments: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, list):
            for item in current:
                walk(item)
            return

        if not isinstance(current, dict):
            return

        node_type = current.get("type")
        if node_type == "text" and isinstance(current.get("content"), str):
            text = clean_text_fn(current["content"])
            if text:
                fragments.append(text)
            return

        for key, value in current.items():
            if key in {"img_path", "image_path", "path"}:
                continue
            walk(value)

    walk(node)
    return " ".join(fragments).strip()


def clean_markdown_document(text: str) -> str:
    """删除不应进入正文的 details 块，同时尽量保留 Markdown 结构。"""
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = DETAILS_BLOCK_RE.sub("", normalized)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def clean_text(text: str) -> str:
    """删除 details 整块后再压缩空白，供结构化文本片段复用。"""
    without_details = clean_markdown_document(text)
    return " ".join(without_details.replace("\n", " ").split())


def find_first_file(package_root: Path, exact_names: tuple[str, ...], suffixes: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []

    for name in exact_names:
        candidates.extend(package_root.rglob(name))

    for suffix in suffixes:
        candidates.extend(package_root.rglob(f"*{suffix}"))

    unique_candidates = sorted(set(candidates), key=lambda path: (len(path.parts), str(path)))
    return unique_candidates[0] if unique_candidates else None


def build_missing_content_list_message(package_root: Path) -> str:
    looks_like_project_root_fn = _runtime_value("looks_like_project_root", looks_like_project_root)
    find_nearby_content_directories_fn = _runtime_value(
        "find_nearby_content_directories",
        find_nearby_content_directories,
    )

    lines = [
        f"在 {package_root} 下没有找到 content_list_v2.json、*_content_list_v2.json、content_list.json 或 *_content_list.json。",
        "当前代码已经支持带前缀的 MinerU 文件名，不需要手工改成精确的 content_list_v2.json。",
    ]

    if looks_like_project_root_fn(package_root):
        lines.append("当前 input_path 看起来是后端项目根目录，不是 MinerU 输出目录。")

    nearby_dirs = find_nearby_content_directories_fn(package_root)
    if nearby_dirs:
        lines.append("附近发现了可用的 MinerU 输出目录，请把 input_path 指向下面这些目录之一：")
        lines.extend(f"- {candidate}" for candidate in nearby_dirs)

    lines.append("请把 input_path 指向 MinerU 输出目录，或通过 FastAPI jobs 接口上传 MinerU 输出 zip。")
    return "\n".join(lines)


def looks_like_project_root(package_root: Path) -> bool:
    return (package_root / "app" / "main.py").exists() and (package_root / "app" / "conversion").is_dir()


def find_nearby_content_directories(package_root: Path, limit: int = 5) -> list[Path]:
    has_content_list_payload_fn = _runtime_value("has_content_list_payload", has_content_list_payload)
    search_roots: list[Path] = []
    if package_root.exists():
        search_roots.append(package_root)
    parent = package_root.parent
    if parent.exists() and parent != package_root:
        search_roots.append(parent)

    matches: list[Path] = []
    seen: set[Path] = set()
    for root in search_roots:
        for child in sorted(root.iterdir(), key=lambda path: path.name):
            if len(matches) >= limit:
                return matches
            if not child.is_dir() or child == package_root or child in seen:
                continue
            seen.add(child)
            if has_content_list_payload_fn(child):
                matches.append(child)
    return matches


def has_content_list_payload(path: Path) -> bool:
    find_first_file_fn = _runtime_value("find_first_file", find_first_file)
    return find_first_file_fn(
        path,
        exact_names=("content_list_v2.json", "content_list.json"),
        suffixes=("_content_list_v2.json", "_content_list.json"),
    ) is not None


def is_supported_input_path(path: Path) -> bool:
    has_content_list_payload_fn = _runtime_value("has_content_list_payload", has_content_list_payload)
    if path.is_dir():
        return has_content_list_payload_fn(path)
    return path.is_file() and path.suffix.lower() == ".zip"


clean_markdown_document = _shared_mineru_content.clean_markdown_document
clean_text = _shared_mineru_content.clean_text
join_text_fragments = _shared_mineru_content.join_text_fragments
split_toc_like_lines = _shared_mineru_content.split_toc_like_lines
coerce_text_list = _shared_mineru_content.coerce_text_list
collect_text_from_fields = _shared_mineru_content.collect_text_from_fields
merge_footnote_fragments = _shared_mineru_content.merge_footnote_fragments
is_footnote_start = _shared_mineru_content.is_footnote_start
should_join_footnote_fragment = _shared_mineru_content.should_join_footnote_fragment
append_footnote_fragment = _shared_mineru_content.append_footnote_fragment
is_cjk_char = _shared_mineru_content.is_cjk_char
find_values_by_key = _shared_mineru_content.find_values_by_key
extract_first_asset_path = _shared_mineru_content.extract_first_asset_path
looks_like_asset_path = _shared_mineru_content.looks_like_asset_path
looks_like_html = _shared_mineru_content.looks_like_html
extract_first_html = _shared_mineru_content.extract_first_html
