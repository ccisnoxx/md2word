"""集中生成 DocumentIR 内容完整性证据并执行失败关闭。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.services.document_ir.source_item_ledger import (
    LIST_ITEM_COUNT_MISMATCH, LIST_ITEM_LEDGER_V1, source_item_ledger_evidence,
)


FILTERED_PAGE_FLAG_PREFIX = "final_promotional_page_filtered:"
VISUAL_SOURCE_TYPES = {"chart", "image", "figure"}
FORMULA_SOURCE_TYPES = {
    "equation",
    "formula",
    "interline_equation",
    "inline_equation",
    "equation_interline",
}


class DocumentIntegrityError(RuntimeError):
    """确定性内容丢失；调用方必须停止发布当前产物。"""

    def __init__(self, boundary: str, evidence: Mapping[str, Any]) -> None:
        self.boundary = boundary
        self.evidence = dict(evidence)
        flags = [str(flag) for flag in evidence.get("blocking_quality_flags", [])]
        summary = ", ".join(flags) if flags else "unknown_integrity_failure"
        count_keys = (
            "expected_source_block_count",
            "ir_main_block_count",
            "expected_layout_block_count",
            "layout_block_count",
            "expected_inline_shape_count",
            "inline_shape_count",
            "expected_table_count",
            "table_count",
            "expected_heading_count",
            "heading_count",
        )
        counts = ", ".join(
            f"{key}={evidence[key]}"
            for key in count_keys
            if evidence.get(key) is not None
        )
        details = f"（{counts}）" if counts else ""
        super().__init__(f"{boundary} 内容完整性校验失败：{summary}{details}")


def build_page_counts(document_ir: DocumentIR) -> dict[str, Any] | None:
    """按源 PDF 页统计（不是 Word 页）；旧 IR 没有页记录时返回 None，不猜页数。"""

    if not document_ir.pages:
        return None
    filtered = sum(flag.startswith(FILTERED_PAGE_FLAG_PREFIX) for flag in document_ir.quality_flags)
    page_indexes = {page.index for page in document_ir.pages}
    degraded = {record["page_index"] for record in document_ir.metadata.degraded_pages} & page_indexes
    return {
        "source_page_count": len(page_indexes) + filtered,
        "converted_page_count": len(page_indexes) - len(degraded),
        "degraded_page_count": len(degraded),
        "filtered_page_count": filtered,
        # 没有 MinerU 页面元数据时只知道有内容的页，空白页可能未计入，总页数只能当下限。
        "page_count_basis": ("mineru_layout" if any(page.metadata.get("page_size_source") for page in document_ir.pages)
                             else "content_blocks"),
    }


def build_source_integrity(document_ir: DocumentIR) -> dict[str, Any]:
    """使用 metadata inventory 与主 IR block 建立 source→IR 对账证据。"""

    expected_total = document_ir.metadata.source_block_count
    expected_types = dict(document_ir.metadata.source_type_counts)
    # 合成块（整页降级的提示与页面图像）不是源块；降级移除的源块按记录计入，保持源→IR 一一对账。
    main_blocks = [block for block in document_ir.blocks
                   if not block.metadata.get("source_block_id") and not block.metadata.get("synthetic")]
    actual_types = Counter(str(block.metadata.get("source_type") or "text") for block in main_blocks)
    degraded_count = 0
    for record in document_ir.metadata.degraded_pages:
        degraded_count += int(record.get("removed_source_block_count") or 0)
        actual_types.update({str(key): int(value) for key, value in (record.get("removed_source_type_counts") or {}).items()})
    accounted_count = len(main_blocks) + degraded_count
    # 渲染阶段降级没有验证报告问题，以此计数进入基础质量 blocker。
    render_degraded = sum(record.get("trigger") == "render" for record in document_ir.metadata.degraded_pages)
    # 降级页摘要由基础质量按受控模型校验后公开；此处只做投影，不含正文与指针。
    degraded_pages = [{"page_number": record["page_index"] + 1, "trigger": record.get("trigger"),
                       "reason_codes": list(record.get("reason_codes") or [])}
                      for record in document_ir.metadata.degraded_pages]
    page_counts = build_page_counts(document_ir)
    versioned_ledgers = source_item_ledger_evidence(document_ir)
    flags = list(versioned_ledgers.pop("blocking_quality_flags", []))

    # 旧 IR 没有 inventory，无法可靠重建 source 合同；仅正式 converter 产物执行对账。
    if expected_total is None and not expected_types:
        return {
            "expected_source_block_count": None,
            "ir_main_block_count": accounted_count,
            "degraded_source_block_count": degraded_count,
            "render_degraded_page_count": render_degraded,
            "degraded_pages": degraded_pages,
            "page_counts": page_counts,
            "source_block_count_delta": None,
            "expected_source_type_counts": {},
            "ir_source_type_counts": dict(sorted(actual_types.items())),
            "blocking_quality_flags": flags,
            **versioned_ledgers,
        }

    if expected_total is not None and expected_total != accounted_count:
        flags.append("source_ir_integrity:block_count_mismatch")
    if expected_types and expected_types != dict(actual_types):
        flags.append("source_ir_integrity:type_count_mismatch")

    from app.services.document_ir.table_placeholder import decode_placeholders
    from app.services.document_ir.table_figure import validate_table_figure_bindings
    represented = {item.owner_block_id for item in decode_placeholders(document_ir)}
    table_figures = validate_table_figure_bindings(document_ir)
    assets_by_id = {asset.id for asset in document_ir.assets}
    for block in main_blocks:
        source_type = str(block.metadata.get("source_type") or "text")
        if source_type in VISUAL_SOURCE_TYPES or block.id in table_figures:
            if block.type != "image":
                flags.append(f"source_ir_integrity:type_mismatch:{source_type}")
            elif not block.asset_ref or block.asset_ref not in assets_by_id:
                flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif source_type == "table" and (block.type != "table" or (
            not (block.html or "").strip() and block.id not in represented
        )):
            flags.append("source_ir_integrity:payload_missing:table")
        elif source_type in FORMULA_SOURCE_TYPES and (
            block.type != "formula" or not ((block.latex or block.text or "").strip())
        ):
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif source_type in {"title", "heading"} and (
            block.type != "heading" or not (block.text or "").strip()
        ):
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif source_type in {"list", "index"} and (
            block.type != "list" or not block.list_items
        ):
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")

    ledger_summary = (
        _legacy_list_item_ledger_summary(main_blocks)
        if document_ir.metadata.source_item_ledger_scope is None and not versioned_ledgers else None
    )
    if ledger_summary is not None and ledger_summary["mismatch_block_ids"]:
        flags.append(LIST_ITEM_COUNT_MISMATCH)

    unique_flags = list(dict.fromkeys(flags))
    evidence = {
        "expected_source_block_count": expected_total,
        "ir_main_block_count": accounted_count,
        "degraded_source_block_count": degraded_count,
        "render_degraded_page_count": render_degraded,
        "degraded_pages": degraded_pages,
        "page_counts": page_counts,
        "source_block_count_delta": None if expected_total is None else accounted_count - expected_total,
        "expected_source_type_counts": expected_types,
        "ir_source_type_counts": dict(sorted(actual_types.items())),
        "blocking_quality_flags": unique_flags,
        **versioned_ledgers,
    }
    if document_ir.metadata.table_structure_reviews:
        evidence["table_structure_reviews"] = [item.model_dump(mode="json")
                                                for item in document_ir.metadata.table_structure_reviews]
    # 历史 IR 无账本时不新增键，持久化证据重算后须与原存储结构逐字节一致。
    if ledger_summary is not None:
        evidence["list_item_ledger"] = ledger_summary
    return evidence


def _legacy_list_item_ledger_summary(main_blocks: list[DocumentIRBlock]) -> dict[str, Any] | None:
    """对账转换时冻结的列表项数；只输出块 ID 与计数，不含正文。

    有 v1 账本的旧件延用原计数规则和证据形状，无账本的旧件不新增证据。
    """

    list_blocks = [block for block in main_blocks if block.type == "list"]
    ledgers = {block.id: block.metadata.get("list_item_ledger") for block in list_blocks}
    if not any(isinstance(ledger, dict) for ledger in ledgers.values()):
        return None
    mismatched = []
    for block in list_blocks:
        ledger = ledgers[block.id]
        if (not isinstance(ledger, dict) or ledger.get("version") != LIST_ITEM_LEDGER_V1
                or type(ledger.get("item_count")) is not int or ledger["item_count"] != len(block.list_items or [])):
            mismatched.append(block.id)
    return {
        "version": LIST_ITEM_LEDGER_V1,
        "block_count": len(list_blocks),
        "item_count": sum(len(block.list_items or []) for block in list_blocks),
        "mismatch_block_ids": mismatched,
    }


def ensure_integrity(boundary: str, evidence: Mapping[str, Any]) -> None:
    """存在确定性阻断标记时抛错，禁止调用方继续发布。"""

    if evidence.get("blocking_quality_flags"):
        raise DocumentIntegrityError(boundary, evidence)


def is_visible_body_block(block: DocumentIRBlock) -> bool:
    """判断 block 是否应进入正文布局和最终 DOCX。"""

    role = block.layout.role if block.layout is not None else "body"
    if role != "body":
        return False
    if block.type in {"heading", "paragraph"}:
        return bool((block.text or "").strip())
    if block.type == "table":
        return True  # 空表也必须进入布局；合法占位或完整性失败由权威 decoder 判断。
    if block.type == "image":
        return bool(block.asset_ref or block.captions or block.footnotes or (block.text or "").strip())
    if block.type == "list":
        return bool(block.list_items or (block.text or "").strip())
    if block.type == "formula":
        return bool((block.latex or block.text or "").strip())
    return False
