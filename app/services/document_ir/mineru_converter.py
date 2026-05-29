from __future__ import annotations

# app/services/document_ir/mineru_converter.py: 将 MinerU 原始结果包转换为 DocumentIR v1。

import json
import mimetypes
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.document_ir_models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockType,
    DocumentIRMetadata,
)


@dataclass(frozen=True, slots=True)
class MinerUImageAsset:
    """从 MinerU 包中抽取出的图片资产。"""

    asset_id: str
    block_id: str
    source_path: str
    mime_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class MinerUToDocumentIRResult:
    document: DocumentIR
    image_assets: list[MinerUImageAsset]


class MinerUToDocumentIRService:
    """P0 MinerU -> DocumentIR v1 转换器，优先保留块顺序和资产引用。"""

    def convert_zip(
        self,
        zip_path: Path,
        *,
        job_id: str,
        source_file_id: str,
        document_language: str,
    ) -> MinerUToDocumentIRResult:
        """读取 MinerU 结果 zip，生成 DocumentIR v1 和待登记图片资产。"""

        with tempfile.TemporaryDirectory(prefix="document_ir_mineru_") as temp_dir:
            package_root = Path(temp_dir)
            self._extract_zip(zip_path, package_root)
            content_list_path = self._find_content_list(package_root)
            raw_blocks = self._load_content_blocks(content_list_path)
            return self._convert_blocks(
                raw_blocks,
                package_root=package_root,
                job_id=job_id,
                source_file_id=source_file_id,
                document_language=document_language,
            )

    def _extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
                    raise ValueError(f"MinerU 结果包包含非法路径: {member.filename}")
                archive.extract(member, target_dir)

    def _find_content_list(self, package_root: Path) -> Path:
        candidates = []
        for path in package_root.rglob("*.json"):
            name = path.name
            if name in {"content_list_v2.json", "content_list.json"}:
                candidates.append(path)
            elif name.endswith("_content_list_v2.json") or name.endswith("_content_list.json"):
                candidates.append(path)
        if not candidates:
            raise FileNotFoundError("MinerU 结果包缺少 content_list_v2.json 或 content_list.json。")
        return sorted(candidates, key=lambda item: (len(item.parts), item.as_posix()))[0]

    def _load_content_blocks(self, content_list_path: Path) -> list[dict[str, Any]]:
        payload = json.loads(content_list_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            blocks = payload
        elif isinstance(payload, dict) and isinstance(payload.get("content_list"), list):
            blocks = payload["content_list"]
        else:
            raise ValueError("MinerU content_list 不是数组，也不包含 content_list 数组。")
        return [block for block in blocks if isinstance(block, dict)]

    def _convert_blocks(
        self,
        raw_blocks: list[dict[str, Any]],
        *,
        package_root: Path,
        job_id: str,
        source_file_id: str,
        document_language: str,
    ) -> MinerUToDocumentIRResult:
        blocks: list[DocumentIRBlock] = []
        image_assets: list[MinerUImageAsset] = []
        ir_assets: list[DocumentIRAsset] = []
        quality_flags: list[str] = []
        unsupported_types: set[str] = set()

        for index, raw_block in enumerate(raw_blocks):
            block_id = f"block_{index + 1:04d}"
            source_type = str(raw_block.get("type") or raw_block.get("block_type") or "text").strip().lower()
            block_type = self._map_block_type(raw_block, source_type)
            if block_type == "paragraph" and source_type not in {"", "text", "paragraph", "para"}:
                unsupported_types.add(source_type)
            metadata = self._metadata_from_raw(raw_block, source_type)
            asset_ref = None
            if block_type == "image":
                image_path = self._resolve_image_path(raw_block, package_root)
                if image_path is None:
                    quality_flags.append(f"missing_image_asset:{block_id}")
                else:
                    asset_id = f"asset_{block_id}"
                    asset_ref = asset_id
                    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
                    source_path = image_path.relative_to(package_root.resolve()).as_posix()
                    image_assets.append(
                        MinerUImageAsset(
                            asset_id=asset_id,
                            block_id=block_id,
                            source_path=source_path,
                            mime_type=mime_type,
                            content=image_path.read_bytes(),
                        )
                    )
                    ir_assets.append(DocumentIRAsset(id=asset_id, kind="image", source_path=source_path))
            blocks.append(
                DocumentIRBlock(
                    id=block_id,
                    type=block_type,
                    order=index,
                    page_index=self._page_index(raw_block),
                    text=self._text_for_block(raw_block, block_type),
                    level=self._heading_level(raw_block) if block_type == "heading" else None,
                    html=self._table_html(raw_block) if block_type == "table" else None,
                    latex=self._formula_text(raw_block) if block_type == "formula" else None,
                    list_items=self._list_items(raw_block) if block_type == "list" else None,
                    asset_ref=asset_ref,
                    metadata=metadata,
                )
            )

        if not blocks:
            quality_flags.append("empty_content_list")
        for source_type in sorted(unsupported_types):
            quality_flags.append(f"unsupported_block_type:{source_type}")

        document = DocumentIR(
            metadata=DocumentIRMetadata(
                job_id=job_id,
                source_file_id=source_file_id,
                document_language=document_language,
            ),
            blocks=blocks,
            assets=ir_assets,
            quality_flags=quality_flags,
        )
        return MinerUToDocumentIRResult(document=document, image_assets=image_assets)

    def _map_block_type(self, raw_block: dict[str, Any], source_type: str) -> DocumentIRBlockType:
        if source_type in {"title", "heading"} or raw_block.get("text_level") is not None:
            return "heading"
        if source_type in {"table"} or raw_block.get("table_body") or raw_block.get("table_html"):
            return "table"
        if source_type in {"image", "figure"} or raw_block.get("img_path") or raw_block.get("image_path"):
            return "image"
        if source_type in {"equation", "formula", "interline_equation", "inline_equation"}:
            return "formula"
        if source_type in {"list"} or isinstance(raw_block.get("items"), list):
            return "list"
        return "paragraph"

    def _metadata_from_raw(self, raw_block: dict[str, Any], source_type: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {"source_type": source_type}
        for key in ("bbox", "page_idx", "page_index", "text_level"):
            if key in raw_block:
                metadata[key] = raw_block[key]
        return metadata

    def _page_index(self, raw_block: dict[str, Any]) -> int | None:
        raw_page = raw_block.get("page_idx", raw_block.get("page_index"))
        if isinstance(raw_page, int):
            return raw_page
        try:
            return int(raw_page)
        except (TypeError, ValueError):
            return None

    def _heading_level(self, raw_block: dict[str, Any]) -> int:
        raw_level = raw_block.get("text_level", raw_block.get("level", 1))
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            level = 1
        return min(max(level, 1), 6)

    def _text_for_block(self, raw_block: dict[str, Any], block_type: str) -> str | None:
        if block_type == "table":
            return self._string_or_none(raw_block.get("table_caption")) or self._string_or_none(raw_block.get("caption"))
        if block_type == "formula":
            return self._formula_text(raw_block)
        if block_type == "list":
            items = self._list_items(raw_block)
            return "\n".join(items) if items else self._string_or_none(raw_block.get("text"))
        return (
            self._string_or_none(raw_block.get("text"))
            or self._string_or_none(raw_block.get("content"))
            or self._string_or_none(raw_block.get("caption"))
        )

    def _table_html(self, raw_block: dict[str, Any]) -> str | None:
        return (
            self._string_or_none(raw_block.get("table_body"))
            or self._string_or_none(raw_block.get("table_html"))
            or self._string_or_none(raw_block.get("html"))
        )

    def _formula_text(self, raw_block: dict[str, Any]) -> str | None:
        return (
            self._string_or_none(raw_block.get("latex"))
            or self._string_or_none(raw_block.get("text"))
            or self._string_or_none(raw_block.get("content"))
        )

    def _list_items(self, raw_block: dict[str, Any]) -> list[str] | None:
        raw_items = raw_block.get("items")
        if not isinstance(raw_items, list):
            return None
        items = [str(item).strip() for item in raw_items if str(item).strip()]
        return items or None

    def _resolve_image_path(self, raw_block: dict[str, Any], package_root: Path) -> Path | None:
        raw_path = (
            self._string_or_none(raw_block.get("img_path"))
            or self._string_or_none(raw_block.get("image_path"))
            or self._string_or_none(raw_block.get("path"))
        )
        if not raw_path:
            return None
        normalized = raw_path.strip().lstrip("./")
        direct = (package_root / normalized).resolve()
        root = package_root.resolve()
        if direct.exists() and direct.is_file() and (direct == root or root in direct.parents):
            return direct
        matches = sorted(package_root.rglob(Path(normalized).name))
        for match in matches:
            resolved_match = match.resolve()
            if resolved_match.is_file() and (resolved_match == root or root in resolved_match.parents):
                return resolved_match
        return None

    def _string_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
