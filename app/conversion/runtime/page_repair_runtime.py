from __future__ import annotations

from typing import Any


_RUNTIME_MODULE: Any | None = None


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


def _logger() -> Any:
    return _runtime_value("logger", _NullLogger())


def _visual_types() -> set[str]:
    return _runtime_value("VISUAL_TYPES", set())


def repair_and_sort_pages(
    pages: list[Any],
    middle_pages: dict[int, Any],
) -> list[Any]:
    merge_page_with_middle_fn = _runtime_value("merge_page_with_middle", merge_page_with_middle)
    repaired_pages: list[Any] = []
    for page in pages:
        middle_page = middle_pages.get(page.page_idx)
        if middle_page:
            merge_page_with_middle_fn(page, middle_page)
        page.blocks.sort(key=lambda block: (block.y1, block.x1))
        _logger().debug("page={} blocks={} page_size={}", page.page_idx, len(page.blocks), page.page_size)
        repaired_pages.append(page)
    return repaired_pages


def attach_table_continuations(pages: list[Any]) -> None:
    get_page_body_blocks_fn = _runtime_value("get_page_body_blocks", get_page_body_blocks)
    collect_placeholder_continuation_heights_fn = _runtime_value(
        "collect_placeholder_continuation_heights",
        collect_placeholder_continuation_heights,
    )

    page_idx = 0
    while page_idx < len(pages):
        page = pages[page_idx]
        body_blocks = get_page_body_blocks_fn(page)
        real_tables = [block for block in body_blocks if block.type == "table" and block.html]
        if not real_tables:
            page_idx += 1
            continue

        target_table = real_tables[-1]
        follow_idx, continuation_heights = collect_placeholder_continuation_heights_fn(pages, page_idx + 1)
        target_table.continuation_heights.extend(continuation_heights)

        page.blocks = [block for block in page.blocks if block.type != "table_placeholder"]
        page_idx = follow_idx


def get_page_body_blocks(page: Any) -> list[Any]:
    return [
        block for block in page.blocks
        if block.type not in {"page_header", "page_footer", "page_number"}
    ]


def collect_placeholder_continuation_heights(
    pages: list[Any],
    start_idx: int,
) -> tuple[int, list[float]]:
    get_page_body_blocks_fn = _runtime_value("get_page_body_blocks", get_page_body_blocks)
    follow_idx = start_idx
    continuation_heights: list[float] = []

    while follow_idx < len(pages):
        follow_page = pages[follow_idx]
        follow_body_blocks = get_page_body_blocks_fn(follow_page)
        if not follow_body_blocks:
            break
        if all(block.type == "table_placeholder" for block in follow_body_blocks):
            continuation_heights.extend(block.height for block in follow_body_blocks)
            follow_page.blocks = [
                block for block in follow_page.blocks
                if block.type != "table_placeholder"
            ]
            follow_idx += 1
            continue
        break

    return follow_idx, continuation_heights


def merge_page_with_middle(page: Any, middle_page: Any) -> None:
    merge_middle_header_footer_blocks_fn = _runtime_value(
        "merge_middle_header_footer_blocks",
        merge_middle_header_footer_blocks,
    )
    backfill_middle_visual_metadata_fn = _runtime_value(
        "backfill_middle_visual_metadata",
        backfill_middle_visual_metadata,
    )
    page.page_size = middle_page.page_size or page.page_size
    merge_middle_header_footer_blocks_fn(page, middle_page)
    backfill_middle_visual_metadata_fn(page, middle_page)


def merge_middle_header_footer_blocks(page: Any, middle_page: Any) -> None:
    existing_header_types = {
        block.type
        for block in page.blocks
        if block.type in {"page_header", "page_footer", "page_number"}
    }
    for extra_block in middle_page.discarded_blocks:
        if extra_block.type not in existing_header_types:
            page.blocks.append(extra_block)
            existing_header_types.add(extra_block.type)


def backfill_middle_visual_metadata(page: Any, middle_page: Any) -> None:
    find_best_visual_match_fn = _runtime_value("find_best_visual_match", find_best_visual_match)
    for block in page.blocks:
        if block.type not in _visual_types():
            continue
        if block.image_path and block.image_path.exists():
            continue
        matched = find_best_visual_match_fn(block, middle_page.visual_blocks)
        if not matched:
            continue
        if not block.image_path:
            block.image_path = matched.image_path
        if not block.captions:
            block.captions = matched.captions[:]
        if not block.footnotes:
            block.footnotes = matched.footnotes[:]
        if not block.text:
            block.text = matched.text


def find_best_visual_match(target: Any, candidates: list[Any]) -> Any | None:
    bbox_distance_fn = _runtime_value("bbox_distance", bbox_distance)
    same_type = [
        candidate
        for candidate in candidates
        if candidate.type == target.type and candidate.image_path
    ]
    if not same_type:
        return None

    best_score: float | None = None
    best_candidate: Any | None = None
    for candidate in same_type:
        score = bbox_distance_fn(target.bbox, candidate.bbox)
        if best_score is None or score < best_score:
            best_score = score
            best_candidate = candidate

    if best_score is not None and best_score < 200:
        return best_candidate
    return None


def bbox_distance(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    return sum(abs(lv - rv) for lv, rv in zip(left, right))
