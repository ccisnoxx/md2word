"""表格 QA 引用的构建、typed 读取和一致性唯一 owner，不执行存储或重新分组。"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.services.document_ir.artifact_validator import ValidatedTableReference
from app.services.document_ir.models import (
    DocumentIR, DocumentIRAsset, TableFragment, TableReferenceEnvelope, TableReferenceFragment,
)


VERSION = "table-reference/v1"
TABLE_REFERENCE_ROLE = "table_reference"
RASTER_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
                     "image/bmp": "bmp", "image/tiff": "tiff", "image/webp": "webp"}
INLINE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
CHECKSUM_RE = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class TableReferenceAsset:
    """单次转换中待登记的 QA 字节及其既有片段归属，不属于渲染图片集合。"""

    asset_id: str
    block_id: str
    fragment_id: str
    logical_group_id: str
    source_path: str
    mime_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class DecodedTableReference:
    """从唯一 envelope 对接已验证来源账本，调用者无需再解析任意 metadata。"""

    block_id: str
    logical_group_id: str
    fragment: TableFragment
    detail: TableReferenceFragment
    asset: DocumentIRAsset | None


def _fail(reason: str) -> None:
    raise ValueError(f"表格参考资产合同无效：{reason}。")


def _asset_id(checksum: str, fragment_id: str) -> str:
    canonical = json.dumps([VERSION, checksum, fragment_id], ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "table-reference:" + hashlib.sha256(canonical).hexdigest()


def attach_table_references(document: DocumentIR, references: dict[str, ValidatedTableReference]) -> list[TableReferenceAsset]:
    """按已验收 fragment→render owner 关联原始结果，同输入重复调用替换派生字段。"""
    checksum = document.metadata.mineru_validation.content_list_sha256
    blocks = {block.id: block for block in document.blocks if block.type == "table"}
    assets: list[TableReferenceAsset] = []
    envelopes: dict[str, list[TableReferenceFragment]] = {block_id: [] for block_id in blocks}
    document.assets = [asset for asset in document.assets if not asset.id.startswith("table-reference:")]
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            reference = references.get(fragment.source_span.json_pointer)
            if reference is None:
                _fail("missing_source_check")
            asset_ref = None
            if reference.source_status == "valid":
                image = reference.image
                if image is None:
                    _fail("missing_validated_image")
                asset_ref = _asset_id(checksum, fragment.fragment_id)
                assets.append(TableReferenceAsset(asset_ref, fragment.render_owner_block_id, fragment.fragment_id,
                                                 group.logical_group_id, image.source_path, image.mime_type, image.content))
                document.assets.append(DocumentIRAsset(
                    id=asset_ref, kind="image", source_path=image.source_path, mime_type=image.mime_type,
                    checksum_sha256="sha256:" + hashlib.sha256(image.content).hexdigest()))
            envelopes[fragment.render_owner_block_id].append(TableReferenceFragment(
                fragment_id=fragment.fragment_id, source_status=reference.source_status, asset_ref=asset_ref))
    document.metadata.table_references_version = VERSION
    for block_id, details in envelopes.items():
        envelope = TableReferenceEnvelope(schema_version=VERSION, asset_role=TABLE_REFERENCE_ROLE, fragments=details)
        blocks[block_id].metadata.update(table_reference=envelope.model_dump(mode="json"),
                                        reference_asset_refs=list(dict.fromkeys(item.asset_ref for item in details
                                                                              if item.asset_ref is not None)))
    decode_table_references(document)
    return assets


def decode_table_references(document: DocumentIR, *, require_bound: bool = False) -> list[DecodedTableReference]:
    """模型、Worker 与审核 API 共用的严格 decoder；旧 IR 缺字段不推造历史引用。"""
    blocks = {block.id: block for block in document.blocks}
    has_fields = any("table_reference" in block.metadata or "reference_asset_refs" in block.metadata
                     for block in document.blocks)
    if document.metadata.table_references_version is None:
        if has_fields or any(asset.id.startswith("table-reference:") for asset in document.assets):
            _fail("missing_version")
        return []
    if (document.schema_version != "document-ir/v2" or
            document.metadata.logical_table_groups_version != "logical-table-groups/v1"):
        _fail("missing_logical_sources")
    assets = {asset.id: asset for asset in document.assets}
    if len(assets) != len(document.assets):
        _fail("duplicate_asset")
    expected: dict[str, list[tuple[str, TableFragment]]] = {
        block.id: [] for block in document.blocks if block.type == "table"}
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            expected[fragment.render_owner_block_id].append((group.logical_group_id, fragment))
    decoded: list[DecodedTableReference] = []
    seen: set[str] = set()
    checksum = document.metadata.mineru_validation.content_list_sha256
    for block_id, block in blocks.items():
        if block_id not in expected:
            if "table_reference" in block.metadata or "reference_asset_refs" in block.metadata:
                _fail("unexpected_owner")
            continue
        envelope = TableReferenceEnvelope.model_validate(block.metadata.get("table_reference"))
        if [item.fragment_id for item in envelope.fragments] != [fragment.fragment_id for _, fragment in expected[block_id]]:
            _fail("fragment_inventory")
        navigation: list[str] = []
        for detail, (group_id, fragment) in zip(envelope.fragments, expected[block_id], strict=True):
            asset = None
            if detail.source_status == "valid":
                asset = assets.get(detail.asset_ref)
                if asset is None or detail.asset_ref != _asset_id(checksum, fragment.fragment_id):
                    _fail("asset_identity")
                if asset.id in seen:
                    _fail("duplicate_reference")
                if (asset.kind != "image" or not asset.source_path or asset.mime_type not in RASTER_EXTENSIONS or
                        not isinstance(asset.checksum_sha256, str) or CHECKSUM_RE.fullmatch(asset.checksum_sha256) is None):
                    _fail("asset_integrity")
                if require_bound and not asset.file_id:
                    _fail("unbound_file")
                seen.add(asset.id)
                navigation.append(asset.id)
            elif detail.asset_ref is not None:
                _fail("unexpected_asset")
            decoded.append(DecodedTableReference(block_id, group_id, fragment, detail, asset))
        if block.metadata.get("reference_asset_refs") != navigation:
            _fail("navigation_index")
    if {asset.id for asset in document.assets if asset.id.startswith("table-reference:")} != seen:
        _fail("orphan_asset")
    return decoded
