"""核对同一 MinerU 包的表格预处理、清空及行覆盖证据。"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from itertools import takewhile
from typing import TYPE_CHECKING, Any, NamedTuple

from app.conversion.docx_rules.mineru_content import collect_text_from_fields
from app.services.document_ir.artifact_validator import parse_valid_bbox
from app.services.document_ir.layout_signals import NORMALIZED_BBOX_SPACE, _parse_page_size
from app.services.document_ir.logical_table_group import (
    COMPOUND_CONTINUED, COMPOSITE_SUFFIX, TABLE_LABEL, is_compound_table_continuation, source_table_body_order,
)
from app.services.document_ir.models import DocumentIR, TableFragment, UpstreamTableCoverage
from app.services.tables.html_normalizer import TableBuildError, normalize_table_fragment
from app.services.tables.models import CellRun, TableSourceFragment, canonical_sha256

if TYPE_CHECKING:
    from app.services.document_ir.artifact_validator import MinerUValidationReport


_SINGLE_TABLE_CAPTION = re.compile(r"^\s*(?:table|表)\s*([0-9]+)(?=$|[\s.．:：(（])(.*)$", re.IGNORECASE)
_TEX_SUBSCRIPT = r"[A-Za-z][A-Za-z0-9]*_\{[A-Za-z0-9]+\}"


class _Rows(NamedTuple):
    keys: tuple[str, ...]
    columns: int
    header_rows: int


def _sha(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _source_sha(fragment: TableFragment) -> str:
    return canonical_sha256([fragment.source_span.model_dump(mode="json"), fragment.raw_fragment])


def _standalone_subscript(runs: tuple[CellRun, ...]) -> str | None:
    """只接受独立 LaTeX 下标 Token 的定界符差异，逐字保留符号和下标。"""
    if any(run.type not in {"text", "formula"} or run.bold or run.italic for run in runs):
        return None
    meaningful = [run for run in runs if run.source.strip()]
    if len(meaningful) != 1:
        return None
    run = meaningful[0]
    pattern = r"\$(" + _TEX_SUBSCRIPT + r")\$" if run.type == "formula" else "(" + _TEX_SUBSCRIPT + ")"
    match = re.fullmatch(pattern, run.source.strip())
    return match.group(1) if match else None


def _rows(fragment: TableFragment, html: str) -> _Rows | None:
    try:
        parsed = normalize_table_fragment(TableSourceFragment(
            fragment_id=fragment.fragment_id, source_span=fragment.source_span, html_state="present",
            raw_html=html, raw_html_sha256=_sha(html),
        ))
    except (TableBuildError, UnicodeEncodeError):
        return None
    if not parsed.rows or any(issue.code != "table_html_canonicalized" for issue in parsed.diagnostics):
        return None
    widths = {sum(cell.colspan for cell in row.cells) for row in parsed.rows}
    # 行覆盖只处理可逐行比较的网格。跨行合并需要证明边界占位，暂按未证明处理。
    if len(widths) != 1 or 0 in widths or any(cell.rowspan != 1 for row in parsed.rows for cell in row.cells):
        return None
    keys = []
    for row in parsed.rows:
        cells = []
        for cell in row.cells:
            token = _standalone_subscript(cell.runs)
            runs = [["latex_subscript", token]] if token else [
                [run.type, run.source, run.bold, run.italic] for run in cell.runs
            ]
            cells.append([cell.colspan, cell.is_header, runs])
        keys.append(canonical_sha256(cells))
    headers = sum(1 for _ in takewhile(lambda row: all(cell.is_header for cell in row.cells), parsed.rows))
    return _Rows(tuple(keys), next(iter(widths)), headers)


def _verified_header_count(primary: TableFragment, rows: _Rows, content_list_sha256: str) -> int:
    review = primary.header_review
    if rows.header_rows or review is None:
        return rows.header_rows
    review.verify_fragment(primary, content_list_sha256)
    return review.header_row_count


def _child(block: dict[str, Any], kind: str) -> dict[str, Any] | None:
    children = block.get("blocks")
    if not isinstance(children, list):
        return None
    matches = [child for child in children if isinstance(child, dict) and child.get("type") == kind]
    return matches[0] if len(matches) == 1 else None


def _spans(block: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    lines = block.get("lines") if block is not None else None
    if not isinstance(lines, list):
        return None
    result = []
    for line in lines:
        spans = line.get("spans") if isinstance(line, dict) else None
        if not isinstance(spans, list) or any(not isinstance(span, dict) for span in spans):
            return None
        result.extend(spans)
    return result


def _layout_html(block: dict[str, Any]) -> str | None:
    spans = _spans(_child(block, "table_body"))
    if spans and len(spans) == 1 and spans[0].get("type") == "table":
        html = spans[0].get("html")
        return html if isinstance(html, str) and html.strip() else None
    return None


def _layout_text(block: dict[str, Any] | None) -> str | None:
    spans = _spans(block)
    if spans and all(span.get("type") == "text" and isinstance(span.get("content"), str) for span in spans):
        return " ".join(" ".join(span["content"] for span in spans).split())
    return None


def _layout_footnotes(block: dict[str, Any]) -> list[str] | None:
    notes = []
    for child in block["blocks"]:
        if isinstance(child, dict) and child.get("type") == "table_footnote":
            text = _layout_text(child)
            if not text:
                return None
            notes.append(text)
    return notes


def _explicit_continuation(primary: str, covered: str) -> bool:
    if is_compound_table_continuation(primary, covered):
        return True
    left, right = _SINGLE_TABLE_CAPTION.fullmatch(primary), _SINGLE_TABLE_CAPTION.fullmatch(covered)
    if (left is None or right is None or left[1] != right[1]
            or any(len(TABLE_LABEL.findall(text)) != 1 for text in (primary, covered))
            or any(COMPOSITE_SUFFIX.match(match[2].lstrip()) for match in (left, right))):
        return False
    marker = COMPOUND_CONTINUED.search(right[2])
    return (marker is not None and COMPOUND_CONTINUED.search(left[2]) is None
            and right[2][:marker.start()].strip(" .．:：") == left[2].strip(" .．:："))


def _match_table(page: dict[str, Any], size: tuple[float, float], fragment: TableFragment, stage: str
                 ) -> tuple[dict[str, Any], tuple, str] | None:
    blocks = page.get(stage)
    if not isinstance(blocks, list):
        return None
    matches = []
    for ordinal, block in enumerate(blocks):
        if (not isinstance(block, dict) or block.get("type") != "table"
                or (bbox := parse_valid_bbox(block.get("bbox"))) is None):
            continue
        projected = tuple(value * 1000 / size[index % 2] for index, value in enumerate(bbox))
        if all(math.isfinite(value) and 0 <= value <= 1000 for value in projected):
            if tuple(int(value) for value in projected) == fragment.source_span.bbox:
                matches.append((block, (block.get("index"), bbox), f"/pdf_info/{page['page_idx']}/{stage}/{ordinal}"))
    if len(matches) != 1:
        return None
    match = matches[0]
    index, bbox = match[1]
    body = _child(match[0], "table_body")
    if (type(index) is not int or body is None or type(body.get("index")) is not int
            or body["index"] != index or parse_valid_bbox(body.get("bbox")) != bbox):
        return None
    return match


def _is_empty_table_candidate(fragment: TableFragment) -> bool:
    return (fragment.block_id is None and fragment.html_state == "empty"
            and fragment.normalization_reason == "strict_empty_table_placeholder")


def count_upstream_coverage_candidates(fragments: list[TableFragment]) -> Counter[tuple[str, int | None]]:
    """同一主片和次页有多个空片时，保留占位供后续校核。"""
    return Counter((fragment.render_owner_block_id, fragment.source_span.page_index)
                   for fragment in fragments if _is_empty_table_candidate(fragment))


def _eligible_pair(primary: TableFragment, covered: TableFragment) -> bool:
    lp, rp = primary.source_span.page_index, covered.source_span.page_index
    return (primary.block_id is not None and primary.block_id == covered.render_owner_block_id
            and primary.html_state == "present" and _is_empty_table_candidate(covered)
            and lp is not None and rp == lp + 1)


def _prove_pair(primary: TableFragment, covered: TableFragment, *, layout_pages: dict[int, dict[str, Any]],
                page_frames: dict[int, tuple[float, float]], report: MinerUValidationReport,
                layout_sha256: str) -> UpstreamTableCoverage | None:
    matches = []
    for fragment in (primary, covered):
        page_index = fragment.source_span.page_index
        page, frame = layout_pages.get(page_index), page_frames.get(page_index)
        if page is None or frame is None or _parse_page_size(page.get("page_size")) != frame:
            return None
        before = _match_table(page, frame, fragment, "preproc_blocks")
        after = _match_table(page, frame, fragment, "para_blocks")
        if before is None or after is None or before[1] != after[1]:
            return None
        matches.append((before, after))

    ((left, _, left_pointer), (merged, _, merged_pointer)), (
        (right, _, right_pointer), (empty, _, empty_pointer),
    ) = matches
    primary_caption = _layout_text(_child(left, "table_caption"))
    continuation_caption = _layout_text(_child(right, "table_caption"))
    source_captions = collect_text_from_fields(primary.raw_fragment, ("table_caption",))
    if (not primary_caption or not continuation_caption or _layout_text(_child(merged, "table_caption")) != primary_caption
            or source_captions != [primary_caption]
            or not _explicit_continuation(primary_caption, continuation_caption)
            or (empty_body := _child(empty, "table_body")) is None or empty_body.get("lines") != []
            or empty_body.get("lines_deleted") is not True):
        return None
    notes = _layout_footnotes(right)
    if notes is None:
        return None
    if notes:
        layout_notes = _layout_footnotes(merged)
        source_notes = collect_text_from_fields(primary.raw_fragment, ("table_footnote",))
        if (layout_notes is None or not Counter(notes) <= Counter(layout_notes)
                or not Counter(notes) <= Counter(source_notes)):
            return None
    left_html, right_html, merged_html = _layout_html(left), _layout_html(right), _layout_html(merged)
    if left_html is None or right_html is None or merged_html is None:
        return None
    left_rows, right_rows, merged_rows, raw_rows = (
        _rows(primary, left_html), _rows(covered, right_html), _rows(primary, merged_html),
        _rows(primary, primary.raw_html),
    )
    if (left_rows is None or right_rows is None or merged_rows is None or raw_rows is None
            or merged_rows != raw_rows or left_rows.columns != right_rows.columns or left_rows.columns != merged_rows.columns):
        return None
    left_keys, right_keys, merged_keys = left_rows.keys, right_rows.keys, merged_rows.keys
    # 完整前段和主表总行数唯一确定复用前缀长度，剩余后段必须逐行落在主表连续尾部。
    repeat = len(left_keys) + len(right_keys) - len(merged_keys)
    if (not 0 <= repeat <= len(left_keys) or repeat >= len(right_keys)
            or left_keys[:repeat] != right_keys[:repeat] or left_keys + right_keys[repeat:] != merged_keys):
        return None
    # 前缀相等也可能是两条独立数据，只有已确认的整个表头允许复用。
    if repeat and repeat != _verified_header_count(primary, raw_rows, report.content_list_sha256):
        return None
    return UpstreamTableCoverage(
        package_sha256=report.package_sha256, content_list_sha256=report.content_list_sha256,
        layout_sha256=layout_sha256, primary_fragment_id=primary.fragment_id, covered_fragment_id=covered.fragment_id,
        primary_source_sha256=_source_sha(primary), covered_source_sha256=_source_sha(covered),
        primary_before_pointer=left_pointer, covered_before_pointer=right_pointer,
        primary_after_pointer=merged_pointer, covered_after_pointer=empty_pointer,
        primary_before_html_sha256=_sha(left_html), covered_before_html_sha256=_sha(right_html),
        primary_after_html_sha256=_sha(merged_html),
        primary_before_rows_sha256=canonical_sha256(left_keys), covered_before_rows_sha256=canonical_sha256(right_keys),
        repeated_prefix_rows=repeat, row_start=len(left_keys), row_end=len(merged_keys),
    )


def attach_upstream_table_coverage(document: DocumentIR, payload: Any, layout_sha256: str) -> None:
    """在已完成源归组的 IR 上采用可从本次原包复核的覆盖证据。"""
    report = document.metadata.mineru_validation
    pdf_info = payload.get("pdf_info") if isinstance(payload, dict) else None
    if report is None or not report.content_list_sha256 or not isinstance(pdf_info, list):
        return
    indices = Counter(page["page_idx"] for page in pdf_info
                      if isinstance(page, dict) and type(page.get("page_idx")) is int)
    layout_pages = {index: page for index, page in enumerate(pdf_info)
                    if isinstance(page, dict) and type(page.get("page_idx")) is int
                    and page["page_idx"] == index and indices[index] == 1}
    page_frames = {page.index: frame for page in document.pages
                   if page.metadata.get("bbox_coordinate_space") == NORMALIZED_BBOX_SPACE
                   and (frame := _parse_page_size(page.metadata.get("pdf_page_size"))) is not None}
    body_order = source_table_body_order(document)
    predecessor = {current[0]: previous[0] for previous, current in zip(body_order, body_order[1:])}
    for group in document.metadata.logical_table_groups:
        by_id = {fragment.fragment_id: fragment for fragment in group.fragments}
        candidates = count_upstream_coverage_candidates(group.fragments)
        for relation in group.continuation_relations:
            primary, covered = by_id[relation.from_fragment_id], by_id[relation.to_fragment_id]
            if (relation.kind == "normalized_empty_placeholder" and _eligible_pair(primary, covered)
                    and predecessor.get(covered.source_span.json_pointer) == primary.source_span.json_pointer
                    and candidates[covered.render_owner_block_id, covered.source_span.page_index] == 1):
                covered.upstream_coverage = _prove_pair(
                    primary, covered, layout_pages=layout_pages, page_frames=page_frames,
                    report=report, layout_sha256=layout_sha256,
                )


def validate_upstream_table_coverage(primary: TableFragment, covered: TableFragment,
                                     report: MinerUValidationReport) -> None:
    """在 IR 边界补充核对原始包绑定。"""
    proof = validate_upstream_coverage_rows(primary, covered, report.content_list_sha256)
    if proof.package_sha256 != report.package_sha256:
        raise ValueError("逻辑表格来源合同无效：upstream_coverage_package。")


def validate_upstream_coverage_rows(primary: TableFragment, covered: TableFragment,
                                    source_content_sha256: str) -> UpstreamTableCoverage:
    """将来源身份和两段规范化行指纹与主片重新对账。"""
    proof = UpstreamTableCoverage.model_validate(covered.upstream_coverage)
    if (
        not _eligible_pair(primary, covered) or proof.content_list_sha256 != source_content_sha256
        or (proof.primary_fragment_id, proof.covered_fragment_id) != (primary.fragment_id, covered.fragment_id)
        or (proof.primary_source_sha256, proof.covered_source_sha256) != (_source_sha(primary), _source_sha(covered))
        or not proof.primary_before_pointer.startswith(f"/pdf_info/{primary.source_span.page_index}/preproc_blocks/")
        or not proof.covered_before_pointer.startswith(f"/pdf_info/{covered.source_span.page_index}/preproc_blocks/")
        or not proof.primary_after_pointer.startswith(f"/pdf_info/{primary.source_span.page_index}/para_blocks/")
        or not proof.covered_after_pointer.startswith(f"/pdf_info/{covered.source_span.page_index}/para_blocks/")
        or not 0 <= proof.repeated_prefix_rows <= proof.row_start < proof.row_end
    ):
        raise ValueError("逻辑表格来源合同无效：upstream_coverage_binding。")
    rows = _rows(primary, primary.raw_html)
    if (
        rows is None or proof.row_end != len(rows.keys)
        or (proof.repeated_prefix_rows and
            proof.repeated_prefix_rows != _verified_header_count(primary, rows, source_content_sha256))
        or proof.primary_before_rows_sha256 != canonical_sha256(rows.keys[:proof.row_start])
        or proof.covered_before_rows_sha256 != canonical_sha256(
            rows.keys[:proof.repeated_prefix_rows] + rows.keys[proof.row_start:proof.row_end]
        )
    ):
        raise ValueError("逻辑表格来源合同无效：upstream_coverage_rows。")
    return proof
