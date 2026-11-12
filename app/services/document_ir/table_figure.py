"""依据同块图题和已验证图像，记录 MinerU 错分表格的来源。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.conversion.docx_rules.mineru_content import (
    NUMBERED_HEADING_RE, clean_text, collect_text_from_fields, find_values_by_key,
)

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR


TABLE_FIGURE_FIELD = "mineru_table_figure"
FIGURE_SECTION_ROLE = "figure_section_heading"
_CAPTION_KEY = "table_caption"
_FIGURE_LABEL = r"(?<![A-Za-z])(?:figure\b|fig\.?\s|图)\s*[0-9]+"
_FIGURE_TITLE = re.compile(
    rf"^\s*{_FIGURE_LABEL}(?:[.\-–—][0-9]+)*[.．:：、]\s*[^\W\d_].*$",
    re.IGNORECASE,
)
_FIGURE_REFERENCE = re.compile(_FIGURE_LABEL, re.IGNORECASE)
_TABLE_REFERENCE = re.compile(r"(?<![A-Za-z])(?:table\b|表)\s*[0-9]+", re.IGNORECASE)
_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_BlockPointer = Annotated[str, Field(pattern=r"^/(?:content_list/)?[0-9]+(?:/[0-9]+)?$")]


class TableFigureBinding(BaseModel):
    """保留源位置、图题所在 run 和正文图片字节的只读来源。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    rule_id: Literal["mineru_table_as_figure/v1"] = "mineru_table_as_figure/v1"
    source_pointer: _BlockPointer
    content_list_sha256: _Sha256
    caption_index: int = Field(ge=0)
    caption_source_sha256: _Sha256
    asset_sha256: _Sha256


def split_table_figure_caption(value: Any) -> tuple[list[str], str] | None:
    """只接受独立图题及其前方的编号章节。混合引用、多个图题和普通正文留在表格路径。"""
    if not isinstance(value, list) or not value:
        return None
    texts = []
    for run in value:
        if (not isinstance(run, dict) or run.get("type") != "text" or not isinstance(run.get("content"), str)
                or not run["content"].strip() or "\n" in run["content"] or "\r" in run["content"]):
            return None
        texts.append(clean_text(run["content"]))
    caption = texts[-1]
    if (not _FIGURE_TITLE.fullmatch(caption) or len(_FIGURE_REFERENCE.findall(caption)) != 1
            or any(_TABLE_REFERENCE.search(text) for text in texts)
            or any(not NUMBERED_HEADING_RE.match(text) or _FIGURE_REFERENCE.search(text) for text in texts[:-1])):
        return None
    return texts[:-1], caption


def select_table_figure(block: dict[str, Any]) -> str | None:
    """返回唯一可核实的显式图片路径，仅从结构化 v2 块取证。"""
    content = block.get("content")
    if (not isinstance(content, dict) or not isinstance(content.get("html"), str)
            or block.get("table_body") or block.get("table_html")):
        return None
    if (len(find_values_by_key(block, _CAPTION_KEY)) != 1
            or split_table_figure_caption(content.get(_CAPTION_KEY)) is None):
        return None
    if collect_text_from_fields(block, ("caption", "captions", "image_caption", "figure_caption", "chart_caption",
                                      "title_content", "paragraph_content", "text", "description", "alt")):
        return None
    source = content.get("image_source")
    path = source.get("path") if isinstance(source, dict) else None
    return path if isinstance(path, str) and path.strip() else None


def caption_source_sha256(value: Any) -> str:
    """用原始 run 的稳定 JSON 表示校验题注证据。"""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_table_figure_bindings(document: DocumentIR) -> set[str]:
    """重读时核对来源、图题和输出资产。译文保留来源账本并独立核验自身内容。"""
    figures = [block for block in document.blocks if TABLE_FIGURE_FIELD in block.metadata]
    report = document.metadata.mineru_validation
    assets = {asset.id: asset for asset in document.assets}
    sections: dict[str, list] = {}
    for block in document.blocks:
        if block.metadata.get("annotation_role") == FIGURE_SECTION_ROLE:
            sections.setdefault(block.metadata.get("source_block_id"), []).append(block)
    if not figures and not sections:
        return set()
    if report is None or not (report.content_list_path or "").endswith("content_list_v2.json"):
        raise ValueError("MinerU 图表来源绑定无效。")
    checked_sources = {check.json_pointer: check for check in report.table_checks}
    if len(checked_sources) != len(report.table_checks):
        raise ValueError("MinerU 图表来源绑定无效。")
    pointers = set()
    for block in figures:
        proof = TableFigureBinding.model_validate(block.metadata[TABLE_FIGURE_FIELD])
        locator = block.metadata.get("mineru_source")
        check = checked_sources.get(proof.source_pointer)
        evidence = block.metadata.get("caption_reconciliation")
        originals = evidence.get("originals") if isinstance(evidence, dict) else None
        asset = assets.get(block.asset_ref)
        if (report.content_list_sha256 != proof.content_list_sha256 or proof.source_pointer in pointers
                or check is None or check.source_type != "table" or not check.parseable or check.reference_status != "valid"
                or not isinstance(locator, dict) or any(locator.get(key) != getattr(check, key)
                    for key in ("json_pointer", "source_type", "source_index", "source_index_in_page", "page_index"))
                or block.metadata.get("source_type") != "table"
                or locator.get("page_index") != block.page_index or block.type != "image" or block.html is not None
                or asset is None or asset.kind != "image" or asset.checksum_sha256 != f"sha256:{proof.asset_sha256}"
                or not isinstance(originals, list) or len(originals) != 1 or not isinstance(originals[0], dict)
                or originals[0].get("json_pointer") != f"{proof.source_pointer}/content/{_CAPTION_KEY}"):
            raise ValueError("MinerU 图表来源绑定无效。")
        split = split_table_figure_caption(originals[0].get("value"))
        headings = sections.pop(block.id, [])
        if (split is None or caption_source_sha256(originals[0]["value"]) != proof.caption_source_sha256
                or len(split[0]) != proof.caption_index or len(headings) != proof.caption_index
                or block.captions != [split[1]]
                or any(heading.type != "heading" or heading.page_index != block.page_index or not (heading.text or "").strip()
                       for heading in headings)):
            raise ValueError("MinerU 图表题注绑定无效。")
        pointers.add(proof.source_pointer)
    if sections:
        raise ValueError("MinerU 图表章节缺少来源。")
    return {block.id for block in figures}
