"""集中生成 DocumentIR 内容完整性证据并执行失败关闭。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.services.document_ir.models import DocumentIR, DocumentIRBlock


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


def build_source_integrity(document_ir: DocumentIR) -> dict[str, Any]:
    """使用 metadata inventory 与主 IR block 建立 source→IR 对账证据。"""

    expected_total = document_ir.metadata.source_block_count
    expected_types = dict(document_ir.metadata.source_type_counts)
    main_blocks = [block for block in document_ir.blocks if not block.metadata.get("source_block_id")]
    actual_types = Counter(str(block.metadata.get("source_type") or "text") for block in main_blocks)
    flags: list[str] = []

    # 旧 IR 没有 inventory，无法可靠重建 source 合同；仅正式 converter 产物执行对账。
    if expected_total is None and not expected_types:
        return {
            "expected_source_block_count": None,
            "ir_main_block_count": len(main_blocks),
            "source_block_count_delta": None,
            "expected_source_type_counts": {},
            "ir_source_type_counts": dict(sorted(actual_types.items())),
            "blocking_quality_flags": [],
        }

    if expected_total is not None and expected_total != len(main_blocks):
        flags.append("source_ir_integrity:block_count_mismatch")
    if expected_types and expected_types != dict(actual_types):
        flags.append("source_ir_integrity:type_count_mismatch")

    from app.services.document_ir.table_placeholder import decode_placeholders
    represented = {item.owner_block_id for item in decode_placeholders(document_ir)}
    assets_by_id = {asset.id for asset in document_ir.assets}
    for block in main_blocks:
        source_type = str(block.metadata.get("source_type") or "text")
        if source_type in VISUAL_SOURCE_TYPES:
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

    unique_flags = list(dict.fromkeys(flags))
    return {
        "expected_source_block_count": expected_total,
        "ir_main_block_count": len(main_blocks),
        "source_block_count_delta": None if expected_total is None else len(main_blocks) - expected_total,
        "expected_source_type_counts": expected_types,
        "ir_source_type_counts": dict(sorted(actual_types.items())),
        "blocking_quality_flags": unique_flags,
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
