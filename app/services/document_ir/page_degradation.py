"""第三批整页降级的 IR 替换：验证阶段（converter）与渲染阶段（Worker）共用同一实现。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock, DocumentIRBlockLayout

PAGE_RASTER_SOURCE_PATH = "derived/pdf-page-raster.png"
DEGRADED_PAGE_NOTICE = "第 {page} 页因{reasons}无法转换，已按原 PDF 页面图像保留，本页不可编辑。"
# 提示写入交付文档，只用中文；机器原因码留在 metadata.degraded_pages。键须覆盖全部可降级原因，缺失时显式报错。
DEGRADED_REASON_LABELS = {
    "missing_image_asset": "图片缺失",
    "invalid_image_asset": "图片损坏或格式不受支持",
    "invalid_table_html": "表格结构无法解析",
    "render_failed": "排版渲染失败",
}
DEPENDENT_PAGE_REASON = "所属跨页表格的其他页面失败"
# 整页图像为提示和分节段落预留的高度（3 cm）。随 IR 持久化：存档校验按 IR 重算尺寸，调整此值不影响已生成结果。
NOTICE_RESERVE_EMU = 1_080_000


@dataclass(frozen=True, slots=True)
class PageDegradationPolicy:
    """验证与渲染阶段共用的数量门槛：防止大部分页失败的文档被当作正常结果。"""
    max_page_ratio: float = 0.5
    allow_single_page: bool = False

    def allows(self, degraded_count: int, page_count: int) -> bool:
        # 单页文档降级即 100%，比例上限没有意义，只看开关。
        if page_count == 1:
            return self.allow_single_page
        return degraded_count <= page_count * self.max_page_ratio


@dataclass(frozen=True, slots=True)
class PageRaster:
    page_index: int
    asset_id: str
    block_id: str
    content: bytes
    page_raster: dict[str, Any]


def degradation_closure(groups, candidate_pages: set[int]) -> set[int] | None:
    """跨越降级页的逻辑表格组整体纳入；组含合并回执或无页码片段时返回 None（放弃降级）。"""
    degraded = set(candidate_pages)
    changed = True
    while changed:
        changed = False
        for group in groups:
            group_pages = {fragment.source_span.page_index for fragment in group.fragments}
            if not group_pages & degraded:
                continue
            if None in group_pages or any(fragment.block_id is None for fragment in group.fragments):
                return None
            if not group_pages <= degraded:
                degraded |= group_pages
                changed = True
    return degraded


def replace_degraded_pages(document: DocumentIR, rasters: dict[int, bytes], reasons: dict[int, dict[str, Any]], *,
                           source_pdf_sha256: str, dpi: int | None,
                           trigger: Literal["validation", "render"]) -> tuple[set[str], list[PageRaster]]:
    """降级页全部块替换为提示段落 + 整页图像块，追加 `metadata.degraded_pages`；返回被移除块 ID 与待登记图像。

    `reasons[page]` 提供 `reason_codes`、`issue_pointers` 及可选的附加记录字段；依赖闭包带入的页没有自身原因。
    """
    degraded = set(rasters)
    removed = [block for block in document.blocks if block.page_index in degraded]
    removed_ids = {block.id for block in removed}
    blocks: list[DocumentIRBlock] = []
    records: list[dict[str, Any]] = []
    pending: list[PageRaster] = []
    for block in document.blocks:
        if block.page_index not in degraded:
            blocks.append(block)
            continue
        page_index = block.page_index
        if any(record["page_index"] == page_index for record in records):
            continue
        main_removed = [item for item in removed if item.page_index == page_index and not item.metadata.get("source_block_id")]
        entry = reasons.get(page_index, {})
        reason_codes = sorted(set(entry.get("reason_codes", [])))
        asset_id = f"asset_degraded_page_{page_index + 1:04d}"
        image_block_id = f"degraded_page_{page_index + 1:04d}_image"
        layout = DocumentIRBlockLayout(page_index=page_index, role="body")
        synthetic = {"synthetic": "degraded_page", "degraded_page_index": page_index, "exclusive_page": True}
        reason_text = "、".join(DEGRADED_REASON_LABELS[code] for code in reason_codes) or DEPENDENT_PAGE_REASON
        blocks.append(DocumentIRBlock(
            id=f"degraded_page_{page_index + 1:04d}_notice", type="paragraph", order=block.order,
            page_index=page_index, layout=layout,
            text=DEGRADED_PAGE_NOTICE.format(page=page_index + 1, reasons=reason_text),
            metadata={**synthetic, "source_type": "degraded_page_notice"}))
        blocks.append(DocumentIRBlock(
            id=image_block_id, type="image", order=block.order, page_index=page_index, layout=layout,
            asset_ref=asset_id, metadata={**synthetic, "source_type": "degraded_page_image",
                                          "notice_reserve_emu": NOTICE_RESERVE_EMU}))
        document.assets.append(DocumentIRAsset(id=asset_id, kind="image", source_path=PAGE_RASTER_SOURCE_PATH))
        pending.append(PageRaster(page_index, asset_id, image_block_id, rasters[page_index],
                                  {"page_index": page_index, "source_pdf_sha256": source_pdf_sha256, "dpi": dpi}))
        records.append({
            **{key: value for key, value in entry.items() if key not in {"reason_codes", "issue_pointers"}},
            "page_index": page_index, "trigger": trigger, "reason_codes": reason_codes,
            "issue_pointers": sorted(entry.get("issue_pointers", [])), "page_image_asset_id": asset_id,
            "source_pdf_sha256": source_pdf_sha256,
            "removed_source_block_count": len(main_removed),
            "removed_source_type_counts": dict(sorted(Counter(
                str(item.metadata.get("source_type") or "text") for item in main_removed).items())),
            "removed_source_pointers": [item.metadata["mineru_source"]["json_pointer"] for item in main_removed
                                        if isinstance(item.metadata.get("mineru_source"), dict)],
        })
    # 表格参考图只由块 metadata 引用（渲染阶段降级时已挂接）；一并移除，不留无主资产。
    removed_assets = {block.asset_ref for block in removed if block.asset_ref}
    removed_assets |= {ref for block in removed for ref in block.metadata.get("reference_asset_refs", [])}
    document.blocks = blocks
    document.assets = [asset for asset in document.assets if asset.id not in removed_assets]
    document.quality_flags = [flag for flag in document.quality_flags
                              if not any(flag.endswith(":" + block_id) for block_id in removed_ids)]
    document.metadata.degraded_pages = sorted([*document.metadata.degraded_pages, *records],
                                              key=lambda record: record["page_index"])
    return removed_ids, pending


def drop_degraded_table_groups(document: DocumentIR, removed_ids: set[str]) -> None:
    """渲染阶段降级：IR 已挂接表格组、参考图与占位绑定，移除只属于被删表格块的部分。

    闭包保证被删组的片段全部位于降级页；残留引用（如保留组的不确定续表诊断指向被删片段）由调用方重新校验 IR 时拒绝。
    """
    from app.services.document_ir.logical_table_group import _counts

    metadata = document.metadata
    dropped = [group for group in metadata.logical_table_groups
               if any(fragment.block_id in removed_ids for fragment in group.fragments)]
    if not dropped:
        return
    fragment_ids = {fragment.fragment_id for group in dropped for fragment in group.fragments}
    metadata.logical_table_groups = [group for group in metadata.logical_table_groups if group not in dropped]
    metadata.logical_table_group_counts = _counts(metadata.logical_table_groups)
    removed_bindings = [item for item in metadata.table_placeholders if item.fragment_id in fragment_ids]
    metadata.table_placeholders = [item for item in metadata.table_placeholders if item.fragment_id not in fragment_ids]
    if not metadata.table_placeholders:
        # 占位 decoder 要求有版本就必须有待绑定片段；全部移除后回到“无占位”状态。
        metadata.table_placeholders_version = None
    dropped_assets = {item.asset_ref for item in removed_bindings}
    document.assets = [asset for asset in document.assets if asset.id not in dropped_assets]
    document.quality_flags = [flag for flag in document.quality_flags
                              if not any(flag.endswith(":" + fragment_id) for fragment_id in fragment_ids)]
