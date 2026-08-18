from __future__ import annotations

# app/services/document_ir/mineru_converter.py: 将 MinerU 原始结果包转换为 DocumentIR v2。

import mimetypes
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    clean_markdown_document,
    clean_text,
    coerce_text_list,
    collect_text_from_fields,
    extract_first_asset_path,
    extract_first_html,
    find_final_promotional_page,
    join_text_fragments,
    merge_footnote_fragments,
    split_toc_like_lines,
)
from app.services.document_ir.layout_signals import (
    build_block_layout,
    build_block_layout_metadata,
    build_pages,
    find_final_source_page_index,
    merge_table_placeholder_continuations,
    parse_page_index,
    role_for_source_type,
)
from app.services.document_ir.mineru_package import extract_zip, find_content_list, load_content_blocks
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockType,
    DocumentIRMetadata,
)
from app.services.document_ir.table_annotations import split_table_annotation_texts


NUMBERED_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?P<label>图|Figure)\s*(?P<number>\d+)(?![A-Za-z0-9]|[.．]\d|[-–—][A-Za-z0-9])",
    re.IGNORECASE,
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
    """P0 MinerU -> DocumentIR v2 转换器，优先保留块顺序和资产引用。"""

    def convert_zip(
        self,
        zip_path: Path,
        *,
        job_id: str,
        source_file_id: str,
        document_language: str,
    ) -> MinerUToDocumentIRResult:
        """读取 MinerU 结果 zip，生成 DocumentIR v2 和待登记图片资产。"""

        with tempfile.TemporaryDirectory(prefix="document_ir_mineru_") as temp_dir:
            package_root = Path(temp_dir)
            extract_zip(zip_path, package_root)
            content_list_path = find_content_list(package_root)
            raw_blocks = load_content_blocks(content_list_path)
            return self._convert_blocks(
                raw_blocks,
                package_root=package_root,
                job_id=job_id,
                source_file_id=source_file_id,
                document_language=document_language,
            )

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
        filtered_page_index = find_final_promotional_page(
            raw_blocks,
            final_page_index=find_final_source_page_index(raw_blocks, package_root),
        )
        if filtered_page_index is not None:
            raw_blocks = [block for block in raw_blocks if parse_page_index(block) != filtered_page_index]
            quality_flags.append(f"final_promotional_page_filtered:{filtered_page_index}")
        raw_blocks = self._reassociate_numbered_image_captions(raw_blocks)
        raw_blocks = merge_table_placeholder_continuations(raw_blocks)
        pages = build_pages(
            raw_blocks,
            package_root,
            quality_flags,
            excluded_page_indices={filtered_page_index} if filtered_page_index is not None else None,
        )
        page_width_by_index = {page.index: page.width for page in pages}

        for index, raw_block in enumerate(raw_blocks):
            block_id = f"block_{index + 1:04d}"
            source_type = str(raw_block.get("type") or raw_block.get("block_type") or "text").strip().lower()
            block_type = self._map_block_type(raw_block, source_type)
            block_role = role_for_source_type(source_type)
            if block_type == "paragraph" and block_role == "body" and source_type not in {"", "text", "paragraph", "para"}:
                unsupported_types.add(source_type)
            page_index = parse_page_index(raw_block)
            page_width = page_width_by_index.get(page_index)
            layout = build_block_layout(
                raw_block,
                source_type=source_type,
                source_index=index,
                quality_flags=quality_flags,
                block_id=block_id,
                page_width=page_width,
            )
            metadata = self._metadata_from_raw(raw_block, source_type)
            metadata.update(build_block_layout_metadata(layout, page_width=page_width))
            captions = self._captions(raw_block, source_type)
            table_contexts: list[str] = []
            if block_type == "table" and captions:
                captions, table_contexts = split_table_annotation_texts(captions)
            footnotes = self._footnotes(raw_block, source_type)
            if table_contexts:
                quality_flags.append(f"layout_table_context_binding:{block_id}")
            if captions:
                quality_flags.append(f"layout_caption_binding:{block_id}")
            if footnotes:
                quality_flags.append(f"layout_footnote_binding:{block_id}")
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
            for context_index, context_text in enumerate(table_contexts):
                context_metadata = dict(metadata)
                context_metadata.update(
                    {
                        "source_type": "table_caption_context",
                        "annotation_role": "table_context",
                        "source_block_id": block_id,
                    }
                )
                blocks.append(
                    DocumentIRBlock(
                        id=f"{block_id}_context_{context_index + 1:04d}",
                        type="paragraph",
                        order=index,
                        page_index=page_index,
                        text=context_text,
                        layout=layout,
                        metadata=context_metadata,
                    )
                )
            blocks.append(
                DocumentIRBlock(
                    id=block_id,
                    type=block_type,
                    order=index,
                    page_index=page_index,
                    text=self._text_for_block(raw_block, block_type, captions=captions),
                    level=self._heading_level(raw_block) if block_type == "heading" else None,
                    html=self._table_html(raw_block) if block_type == "table" else None,
                    latex=self._formula_text(raw_block) if block_type == "formula" else None,
                    list_items=self._list_items(raw_block) if block_type == "list" else None,
                    asset_ref=asset_ref,
                    layout=layout,
                    captions=captions,
                    footnotes=footnotes,
                    metadata=metadata,
                )
            )

        if not blocks:
            quality_flags.append("empty_content_list")
        for source_type in sorted(unsupported_types):
            quality_flags.append(f"unsupported_block_type:{source_type}")

        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id=job_id,
                source_file_id=source_file_id,
                document_language=document_language,
            ),
            pages=pages,
            blocks=blocks,
            assets=ir_assets,
            quality_flags=quality_flags,
        )
        return MinerUToDocumentIRResult(document=document, image_assets=image_assets)

    def _map_block_type(self, raw_block: dict[str, Any], source_type: str) -> DocumentIRBlockType:
        if source_type in {"header", "footer", "page_header", "page_footer", "page_number"}:
            return "paragraph"
        if source_type in {"title", "heading"} or raw_block.get("text_level") is not None:
            return "heading"
        if source_type in {"table"} or raw_block.get("table_body") or raw_block.get("table_html"):
            return "table"
        if source_type in {"image", "figure"} or raw_block.get("img_path") or raw_block.get("image_path"):
            return "image"
        if source_type in {"equation", "formula", "interline_equation", "inline_equation", "equation_interline"}:
            return "formula"
        if source_type in {"list", "index"} or isinstance(raw_block.get("items"), list):
            return "list"
        if split_toc_like_lines(self._raw_text_preserving_lines(raw_block)):
            return "list"
        return "paragraph"

    def _reassociate_numbered_image_captions(
        self,
        raw_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """在严格可判定时修复同页连续图片组的 MinerU 图注错配。"""

        normalized: list[dict[str, Any]] = []
        index = 0
        while index < len(raw_blocks):
            first = raw_blocks[index]
            page_index = parse_page_index(first)
            if page_index is None or not self._is_image_source_block(first):
                normalized.append(first)
                index += 1
                continue

            end = index + 1
            while (
                end < len(raw_blocks)
                and parse_page_index(raw_blocks[end]) == page_index
                and self._is_image_source_block(raw_blocks[end])
            ):
                end += 1
            normalized.extend(self._reassociate_image_group(raw_blocks[index:end]))
            index = end
        return normalized

    def _reassociate_image_group(self, group: list[dict[str, Any]]) -> list[dict[str, Any]]:
        captions_by_block = [self._captions(block, self._source_type(block)) for block in group]
        if not any(len(captions) != 1 for captions in captions_by_block):
            return group

        parsed_captions: list[tuple[str, int, str]] = []
        for caption in (caption for captions in captions_by_block for caption in captions):
            match = NUMBERED_FIGURE_CAPTION_RE.match(caption)
            if match is None:
                return group
            parsed_captions.append((match.group("label").lower(), int(match.group("number")), caption))

        if len(parsed_captions) != len(group):
            return group
        labels = {label for label, _number, _caption in parsed_captions}
        numbers = [number for _label, number, _caption in parsed_captions]
        if len(labels) != 1 or len(set(numbers)) != len(numbers):
            return group
        ordered = sorted(parsed_captions, key=lambda item: item[1])
        if [number for _label, number, _caption in ordered] != list(range(ordered[0][1], ordered[0][1] + len(group))):
            return group

        reassociated: list[dict[str, Any]] = []
        for block, (_label, _number, caption) in zip(group, ordered, strict=True):
            copied = dict(block)
            source_type = self._source_type(copied)
            copied.pop("caption", None)
            copied[f"{source_type}_caption"] = [caption]
            reassociated.append(copied)
        return reassociated

    def _is_image_source_block(self, raw_block: dict[str, Any]) -> bool:
        return self._source_type(raw_block) in {"chart", "image", "figure"}

    def _source_type(self, raw_block: dict[str, Any]) -> str:
        return str(raw_block.get("type") or raw_block.get("block_type") or "").strip().lower()

    def _metadata_from_raw(self, raw_block: dict[str, Any], source_type: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {"source_type": source_type}
        for key in ("bbox", "page_idx", "page_index", "text_level"):
            if key in raw_block:
                metadata[key] = raw_block[key]
        return metadata

    def _heading_level(self, raw_block: dict[str, Any]) -> int:
        raw_level = raw_block.get("text_level", raw_block.get("level", 1))
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            level = 1
        return min(max(level, 1), 6)

    def _text_for_block(
        self,
        raw_block: dict[str, Any],
        block_type: str,
        *,
        captions: list[str] | None = None,
    ) -> str | None:
        if block_type == "table":
            return captions[0] if captions else self._first_text_from_keys(raw_block, ("text",))
        if block_type == "image":
            captions = self._captions(raw_block, str(raw_block.get("type") or raw_block.get("block_type") or "").strip().lower())
            return captions[0] if captions else self._first_text_from_keys(raw_block, ("text", "caption"))
        if block_type == "formula":
            return self._formula_text(raw_block)
        if block_type == "list":
            items = self._list_items(raw_block)
            return "\n".join(items) if items else self._raw_text(raw_block)
        return self._raw_text(raw_block) or self._first_text_from_keys(raw_block, ("caption",))

    def _table_html(self, raw_block: dict[str, Any]) -> str | None:
        for key in ("table_body", "table_html", "html", "content"):
            html = extract_first_html(raw_block.get(key))
            if html:
                return html
        return extract_first_html(raw_block)

    def _formula_text(self, raw_block: dict[str, Any]) -> str | None:
        return self._first_text_from_keys(raw_block, ("latex", "text", "content"))

    def _list_items(self, raw_block: dict[str, Any]) -> list[str] | None:
        raw_items = raw_block.get("items", raw_block.get("list_items"))
        if isinstance(raw_items, list):
            items = []
            for item in raw_items:
                if isinstance(item, dict):
                    items.extend(coerce_text_list(item))
                else:
                    text = clean_text(str(item))
                    if text:
                        items.append(text)
            return items or None

        toc_items = split_toc_like_lines(self._raw_text_preserving_lines(raw_block))
        if toc_items:
            return toc_items

        items = coerce_text_list(raw_block.get("content"))
        return items or None

    def _captions(self, raw_block: dict[str, Any], source_type: str) -> list[str]:
        keys = ["caption"]
        if source_type == "table":
            keys.insert(0, "table_caption")
        elif source_type in {"chart", "image", "figure"}:
            keys.insert(0, f"{source_type}_caption")
        return self._unique_texts(collect_text_from_fields(raw_block, tuple(keys)))

    def _footnotes(self, raw_block: dict[str, Any], source_type: str) -> list[str]:
        keys = ["footnote"]
        if source_type == "table":
            keys.insert(0, "table_footnote")
        elif source_type in {"chart", "image", "figure"}:
            keys.insert(0, f"{source_type}_footnote")
        return self._unique_texts(merge_footnote_fragments(collect_text_from_fields(raw_block, tuple(keys))))

    def _resolve_image_path(self, raw_block: dict[str, Any], package_root: Path) -> Path | None:
        raw_path = extract_first_asset_path(raw_block)
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

    def _raw_text(self, raw_block: dict[str, Any]) -> str | None:
        for key in ("text", "content"):
            raw_value = raw_block.get(key)
            if isinstance(raw_value, list) and all(isinstance(item, dict) for item in raw_value):
                text = join_text_fragments(raw_value)
            elif isinstance(raw_value, str):
                text = clean_text(raw_value)
            else:
                texts = coerce_text_list(raw_value)
                text = clean_text(" ".join(texts)) if texts else ""
            if text:
                return text
        return None

    def _raw_text_preserving_lines(self, raw_block: dict[str, Any]) -> str:
        for key in ("text", "content"):
            raw_value = raw_block.get(key)
            if isinstance(raw_value, str):
                return clean_markdown_document(raw_value)
        return self._raw_text(raw_block) or ""

    def _first_text_from_keys(self, raw_block: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            texts = coerce_text_list(raw_block.get(key))
            if texts:
                return clean_text(" ".join(texts))
            raw_value = raw_block.get(key)
            if isinstance(raw_value, str):
                text = clean_text(raw_value)
                if text:
                    return text
        return None

    def _unique_texts(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        texts: list[str] = []
        for value in values:
            text = clean_text(value)
            if text and text not in seen:
                seen.add(text)
                texts.append(text)
        return texts
