from __future__ import annotations

# app/services/document_ir/mineru_converter.py: 将 MinerU 原始结果包转换为 DocumentIR v2。

import hashlib
import mimetypes
import re
import tempfile
from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    clean_markdown_document,
    clean_text,
    coerce_text_list,
    extract_first_asset_path,
    extract_first_html,
    find_values_by_key,
    find_final_promotional_page,
    join_text_fragments,
    merge_footnote_fragments,
    split_multiline_list_items,
    split_toc_like_lines,
)
from app.conversion.docx_rules.text_semantics import parse_decimal_list_marker
from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.layout_signals import (
    build_block_layout,
    build_block_layout_metadata,
    build_pages,
    find_final_source_page_index,
    merge_table_placeholder_continuations,
    parse_bbox,
    parse_page_index,
)
from app.services.document_ir.integrity import build_source_integrity, complement_crop_rects, ensure_integrity
from app.services.document_ir.mineru_package import extract_zip, find_content_list, load_content_blocks
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockType,
    DocumentIRMetadata,
)
from app.services.document_ir.semantic_normalization import (
    DECORATION_SOURCE_TYPES,
    SemanticCandidate,
    normalize_semantics,
)
from app.services.document_ir.table_annotations import is_table_caption_annotation, split_table_annotation_texts


NUMBERED_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?P<label>图|Figure)\s*(?P<number>\d+)(?![A-Za-z0-9]|[.．]\d|[-–—][A-Za-z0-9])",
    re.IGNORECASE,
)
FIGURE_CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?|\u56fe)\s*\w", re.IGNORECASE)
_GROUP_CAPTIONS_KEY = "_md2word_group_captions"
_CONTENT_GROUP_KEY = "_md2word_content_group_id"
_CAPTION_OWNER_UNRESOLVED_KEY = "_md2word_caption_owner_unresolved"
_VISUAL_CROP_RECTS_KEY = "_md2word_visual_crop_rects"
_VISUAL_OVERLAP_GROUP_KEY = "_md2word_visual_overlap_group_id"
_VISUAL_OVERLAP_NORMALIZATION_KEY = "_md2word_visual_overlap_normalization"
_VISUAL_OVERLAP_UNRESOLVED_KEY = "_md2word_visual_overlap_unresolved"
_MAX_CONTAINED_TABLE_AREA_RATIO = 0.5


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
        """绑定唯一 MinerU 结果根后生成 DocumentIR v2 和待登记图片资产。"""

        with tempfile.TemporaryDirectory(prefix="document_ir_mineru_") as temp_dir:
            archive_root = Path(temp_dir)
            extract_zip(zip_path, archive_root)
            content_list_path = find_content_list(archive_root)
            package_root = content_list_path.parent
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
        raw_blocks = merge_table_placeholder_continuations(raw_blocks)
        raw_blocks = self._normalize_contained_table_images(raw_blocks, package_root)
        raw_blocks = self._reassociate_numbered_image_captions(raw_blocks, package_root)
        raw_blocks = self._reassociate_visual_group_captions(raw_blocks)
        source_type_counts = Counter(self._source_type(block) or "text" for block in raw_blocks)
        pages = build_pages(
            raw_blocks,
            package_root,
            quality_flags,
            excluded_page_indices={filtered_page_index} if filtered_page_index is not None else None,
        )
        page_width_by_index = {page.index: page.width for page in pages}
        page_height_by_index = {page.index: page.height for page in pages}
        semantic_candidates: list[SemanticCandidate] = []
        for index, raw_block in enumerate(raw_blocks):
            source_type = self._source_type(raw_block) or "text"
            base_type = self._map_block_type(raw_block, source_type)
            page_index = parse_page_index(raw_block)
            semantic_candidates.append(
                SemanticCandidate(
                    source_index=index,
                    source_type=source_type,
                    block_type=base_type,
                    text=self._text_for_block(
                        raw_block,
                        base_type,
                        captions=self._captions(raw_block, source_type),
                    )
                    or "",
                    page_index=page_index,
                    bbox=parse_bbox(raw_block.get("bbox")),
                    page_width=page_width_by_index.get(page_index),
                    page_height=page_height_by_index.get(page_index),
                    heading_level=self._source_heading_level(raw_block),
                    list_items=tuple(self._list_items(raw_block) or ()),
                )
            )
        semantic_decisions = normalize_semantics(semantic_candidates)

        for index, raw_block in enumerate(raw_blocks):
            block_id = f"block_{index + 1:04d}"
            source_type = str(raw_block.get("type") or raw_block.get("block_type") or "text").strip().lower()
            decision = semantic_decisions[index]
            block_type = decision.block_type
            block_role = decision.role
            known_paragraph_sources = {
                "",
                "text",
                "paragraph",
                "para",
                "title",
                "heading",
                "page_footnote",
                *DECORATION_SOURCE_TYPES,
            }
            if block_type == "paragraph" and block_role == "body" and source_type not in known_paragraph_sources:
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
            layout = layout.model_copy(update={"role": block_role})
            metadata = self._metadata_from_raw(raw_block, source_type)
            metadata.update(build_block_layout_metadata(layout, page_width=page_width))
            metadata["semantic_decision_reason"] = decision.reason
            if raw_block.get(_CONTENT_GROUP_KEY):
                metadata["content_group_id"] = raw_block[_CONTENT_GROUP_KEY]
            if raw_block.get(_CAPTION_OWNER_UNRESOLVED_KEY):
                metadata["caption_owner_unresolved"] = True
            for raw_key, metadata_key in (
                (_VISUAL_CROP_RECTS_KEY, "visual_crop_rects"),
                (_VISUAL_OVERLAP_GROUP_KEY, "visual_overlap_group_id"),
                (_VISUAL_OVERLAP_NORMALIZATION_KEY, "visual_overlap_normalization"),
            ):
                if raw_block.get(raw_key) is not None:
                    metadata[metadata_key] = raw_block[raw_key]
            if raw_block.get(_VISUAL_OVERLAP_UNRESOLVED_KEY):
                metadata["visual_overlap_unresolved"] = True
            if decision.annotation_role is not None:
                metadata["annotation_role"] = decision.annotation_role
            quality_flags.extend(decision.quality_flags)
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
            if block_type == "image" and metadata.get("visual_overlap_normalization"):
                quality_flags.append(f"visual_overlap_normalized:{metadata['visual_overlap_group_id']}")
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
                    image_content = image_path.read_bytes()
                    image_assets.append(
                        MinerUImageAsset(
                            asset_id=asset_id,
                            block_id=block_id,
                            source_path=source_path,
                            mime_type=mime_type,
                            content=image_content,
                        )
                    )
                    ir_assets.append(
                        DocumentIRAsset(
                            id=asset_id,
                            kind="image",
                            source_path=source_path,
                            mime_type=mime_type,
                            checksum_sha256=f"sha256:{hashlib.sha256(image_content).hexdigest()}",
                        )
                    )
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
            group_captions = raw_block.get(_GROUP_CAPTIONS_KEY)
            if isinstance(group_captions, list):
                self._append_group_captions(
                    blocks,
                    group_captions,
                    placement="before",
                    owner_block_id=block_id,
                    order=index,
                    page_index=page_index,
                    page_width=page_width,
                    quality_flags=quality_flags,
                )
            blocks.append(
                DocumentIRBlock(
                    id=block_id,
                    type=block_type,
                    order=index,
                    page_index=page_index,
                    text=self._text_for_block(raw_block, block_type, captions=captions),
                    level=decision.heading_level if block_type == "heading" else None,
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
            if isinstance(group_captions, list):
                self._append_group_captions(
                    blocks,
                    group_captions,
                    placement="after",
                    owner_block_id=block_id,
                    order=index,
                    page_index=page_index,
                    page_width=page_width,
                    quality_flags=quality_flags,
                )
            if decision.insert_toc_anchor:
                blocks.append(
                    DocumentIRBlock(
                        id=f"{block_id}_toc_anchor",
                        type="paragraph",
                        order=index,
                        page_index=page_index,
                        text="",
                        layout=layout.model_copy(update={"role": "body"}),
                        metadata={
                            "source_type": "toc_anchor",
                            "source_block_id": block_id,
                            "annotation_role": "toc_anchor",
                            "semantic_decision_reason": "synthetic_toc_anchor",
                        },
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
                source_block_count=len(raw_blocks),
                source_type_counts=dict(sorted(source_type_counts.items())),
            ),
            pages=pages,
            blocks=blocks,
            assets=ir_assets,
            quality_flags=quality_flags,
        )
        ensure_integrity("MinerU→DocumentIR", build_source_integrity(document))
        return MinerUToDocumentIRResult(document=document, image_assets=image_assets)

    def _map_block_type(self, raw_block: dict[str, Any], source_type: str) -> DocumentIRBlockType:
        if source_type in {*DECORATION_SOURCE_TYPES, "page_footnote"}:
            return "paragraph"
        if source_type in {"title", "heading"}:
            return "heading"
        if source_type in {"table"} or raw_block.get("table_body") or raw_block.get("table_html"):
            return "table"
        if source_type in {"chart", "image", "figure"} or raw_block.get("img_path") or raw_block.get("image_path"):
            return "image"
        if source_type in {"equation", "formula", "interline_equation", "inline_equation", "equation_interline"}:
            return "formula"
        if source_type in {"list", "index"} or isinstance(raw_block.get("items"), list):
            return "list"
        if split_multiline_list_items(self._raw_text_preserving_lines(raw_block)):
            return "list"
        if split_toc_like_lines(self._raw_text_preserving_lines(raw_block)):
            return "list"
        return "paragraph"

    def _reassociate_numbered_image_captions(
        self,
        raw_blocks: list[dict[str, Any]],
        package_root: Path,
    ) -> list[dict[str, Any]]:
        """在严格可判定时修复同页连续视觉组的 MinerU 图注错配。"""

        sparse_table_indices = self._sparse_visual_table_indices(raw_blocks, package_root)
        normalized: list[dict[str, Any]] = []
        index = 0
        while index < len(raw_blocks):
            first = raw_blocks[index]
            page_index = parse_page_index(first)
            if page_index is None or not (
                self._is_image_source_block(first) or index in sparse_table_indices
            ):
                normalized.append(first)
                index += 1
                continue

            end = index + 1
            while (
                end < len(raw_blocks)
                and parse_page_index(raw_blocks[end]) == page_index
                and (
                    self._is_image_source_block(raw_blocks[end])
                    or end in sparse_table_indices
                )
            ):
                end += 1
            normalized.extend(
                self._reassociate_image_group(
                    raw_blocks[index:end],
                    sparse_table_positions={
                        position - index
                        for position in sparse_table_indices
                        if index <= position < end
                    },
                )
            )
            index = end
        return normalized

    def _sparse_visual_table_indices(
        self,
        raw_blocks: list[dict[str, Any]],
        package_root: Path,
    ) -> set[int]:
        """只把有图题且与相邻稀疏表严格对齐的 table 纳入视觉组试算。"""

        sparse_indices = {
            index
            for index, block in enumerate(raw_blocks)
            if self._is_sparse_visual_table(block, package_root)
        }
        candidates: set[int] = set()
        for index in sparse_indices:
            captions = self._captions(raw_blocks[index], "table")
            if len(captions) != 1 or NUMBERED_FIGURE_CAPTION_RE.match(captions[0]) is None:
                continue
            for neighbor in (index - 1, index + 1):
                if (
                    neighbor in sparse_indices
                    and parse_page_index(raw_blocks[neighbor]) == parse_page_index(raw_blocks[index])
                    and self._strictly_horizontally_aligned(raw_blocks[index], raw_blocks[neighbor])
                ):
                    candidates.update((index, neighbor))
        return candidates

    def _is_sparse_visual_table(self, raw_block: dict[str, Any], package_root: Path) -> bool:
        if (
            self._source_type(raw_block) != "table"
            or raw_block.get(_VISUAL_OVERLAP_GROUP_KEY)
            or raw_block.get(_VISUAL_OVERLAP_UNRESOLVED_KEY)
            or self._resolve_image_path(raw_block, package_root) is None
        ):
            return False
        table = parse_html_table(self._table_html(raw_block))
        return table is not None and len(table.rows) == 1 and 0 < table.max_columns <= 3

    def _reassociate_visual_group_captions(
        self,
        raw_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """用跨类型、对齐或已确定的表图关系把图题收口到唯一视觉主体组。"""

        normalized = deepcopy(raw_blocks)
        for owner_index, block in enumerate(normalized):
            if self._source_type(block) != "table":
                continue
            captions = self._captions(block, "table")
            figure_captions = [caption for caption in captions if FIGURE_CAPTION_RE.match(caption)]
            if not figure_captions:
                continue
            overlap_group_id = block.get(_VISUAL_OVERLAP_GROUP_KEY)
            overlap_subject_indices = [
                index
                for index, candidate in enumerate(normalized)
                if overlap_group_id and candidate.get(_VISUAL_OVERLAP_GROUP_KEY) == overlap_group_id
            ]
            if (
                len(captions) == 1
                and len(figure_captions) == 1
                and sorted(self._source_type(normalized[index]) for index in overlap_subject_indices) == ["image", "table"]
            ):
                self._bind_group_caption(
                    normalized,
                    subject_indices=overlap_subject_indices,
                    owner_index=max(overlap_subject_indices),
                    text=figure_captions[0],
                    placement="after",
                    reason="figure_caption_reassigned_to_visual_composite",
                )
                self._clear_annotation_fields(block, captions=True, footnotes=False)
                continue
            subject_indices = self._prior_image_subject_indices(normalized, owner_index)
            if len(captions) != 1 or len(figure_captions) != 1 or not subject_indices:
                block[_CAPTION_OWNER_UNRESOLVED_KEY] = True
                continue
            self._bind_group_caption(
                normalized,
                subject_indices=subject_indices,
                owner_index=owner_index,
                text=figure_captions[0],
                placement="before",
                reason="figure_caption_reassigned_to_image_group",
            )
            self._clear_annotation_fields(block, captions=True, footnotes=False)

        for subject_indices in self._aligned_image_pairs(normalized):
            if any(normalized[index].get(_CONTENT_GROUP_KEY) for index in subject_indices):
                continue
            captions = [
                caption
                for index in subject_indices
                for caption in self._captions(normalized[index], self._source_type(normalized[index]))
            ]
            footnotes = [
                footnote
                for index in subject_indices
                for footnote in self._footnotes(normalized[index], self._source_type(normalized[index]))
            ]
            if captions or len(footnotes) != 1 or not is_table_caption_annotation(footnotes[0]):
                continue
            owner_index = next(
                index
                for index in subject_indices
                if self._footnotes(normalized[index], self._source_type(normalized[index]))
            )
            self._bind_group_caption(
                normalized,
                subject_indices=subject_indices,
                owner_index=max(subject_indices),
                text=footnotes[0],
                placement="after",
                reason="shared_image_caption_group",
            )
            self._clear_annotation_fields(normalized[owner_index], captions=False, footnotes=True)
        return normalized

    def _normalize_contained_table_images(
        self,
        raw_blocks: list[dict[str, Any]],
        package_root: Path,
    ) -> list[dict[str, Any]]:
        """仅在表格与整图存在唯一包含关系时拆出可编辑表格。"""

        normalized = deepcopy(raw_blocks)
        table_indices = [index for index, block in enumerate(normalized) if self._source_type(block) == "table"]
        image_indices = [index for index, block in enumerate(normalized) if self._is_image_source_block(block)]
        images_by_table: dict[int, list[int]] = {}
        tables_by_image: dict[int, list[int]] = {}
        for table_index in table_indices:
            table = normalized[table_index]
            table_page = parse_page_index(table)
            table_bbox = parse_bbox(table.get("bbox"))
            if table_page is None or table_bbox is None:
                continue
            for image_index in image_indices:
                image = normalized[image_index]
                image_bbox = parse_bbox(image.get("bbox"))
                if (
                    parse_page_index(image) == table_page
                    and image_bbox is not None
                    and self._bbox_contains(image_bbox, table_bbox)
                ):
                    images_by_table.setdefault(table_index, []).append(image_index)
                    tables_by_image.setdefault(image_index, []).append(table_index)

        for table_index, containing_images in images_by_table.items():
            if len(containing_images) != 1:
                self._mark_visual_overlap_unresolved(normalized, [table_index, *containing_images])
                continue
            image_index = containing_images[0]
            if len(tables_by_image.get(image_index, [])) != 1:
                self._mark_visual_overlap_unresolved(normalized, [image_index, *tables_by_image[image_index]])
                continue
            table = normalized[table_index]
            image = normalized[image_index]
            table_bbox = parse_bbox(table.get("bbox"))
            image_bbox = parse_bbox(image.get("bbox"))
            assert table_bbox is not None and image_bbox is not None
            table_area = (table_bbox[2] - table_bbox[0]) * (table_bbox[3] - table_bbox[1])
            image_area = (image_bbox[2] - image_bbox[0]) * (image_bbox[3] - image_bbox[1])
            table_model = parse_html_table(self._table_html(table))
            # ponytail: 仅接受表区不超过半幅的情况；获得像素级对象边界后才应放宽。
            if (
                image_area <= 0
                or table_area <= 0
                or table_area > image_area * _MAX_CONTAINED_TABLE_AREA_RATIO
                or table_model is None
                or self._resolve_image_path(table, package_root) is None
                or self._resolve_image_path(image, package_root) is None
            ):
                self._mark_visual_overlap_unresolved(normalized, [table_index, image_index])
                continue

            mask = self._relative_bbox(table_bbox, image_bbox)
            crop_rects = complement_crop_rects(mask)
            if not crop_rects:
                self._mark_visual_overlap_unresolved(normalized, [table_index, image_index])
                continue
            group_id = f"visual_overlap:block_{table_index + 1:04d}:block_{image_index + 1:04d}"
            normalization = {
                "reason": "editable_table_extracted_from_containing_image",
                "table_block_id": f"block_{table_index + 1:04d}",
                "image_block_id": f"block_{image_index + 1:04d}",
                "masked_rect": list(mask),
                "crop_fragment_count": len(crop_rects),
            }
            for block in (table, image):
                block[_VISUAL_OVERLAP_GROUP_KEY] = group_id
                block[_VISUAL_OVERLAP_NORMALIZATION_KEY] = normalization
            image[_VISUAL_CROP_RECTS_KEY] = [list(rect) for rect in crop_rects]
        return normalized

    def _mark_visual_overlap_unresolved(
        self,
        raw_blocks: list[dict[str, Any]],
        indices: list[int],
    ) -> None:
        for index in set(indices):
            raw_blocks[index][_VISUAL_OVERLAP_UNRESOLVED_KEY] = True

    def _bbox_contains(
        self,
        outer: tuple[float, float, float, float],
        inner: tuple[float, float, float, float],
    ) -> bool:
        return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]

    def _relative_bbox(
        self,
        inner: tuple[float, float, float, float],
        outer: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        width = outer[2] - outer[0]
        height = outer[3] - outer[1]
        return (
            (inner[0] - outer[0]) / width,
            (inner[1] - outer[1]) / height,
            (inner[2] - outer[0]) / width,
            (inner[3] - outer[1]) / height,
        )

    def _prior_image_subject_indices(
        self,
        raw_blocks: list[dict[str, Any]],
        owner_index: int,
    ) -> list[int]:
        owner = raw_blocks[owner_index]
        page_index = parse_page_index(owner)
        owner_bbox = parse_bbox(owner.get("bbox"))
        if page_index is None or owner_bbox is None:
            return []
        subject_indices: list[int] = []
        for index in range(owner_index - 1, -1, -1):
            candidate = raw_blocks[index]
            if parse_page_index(candidate) != page_index:
                break
            candidate_type = self._source_type(candidate)
            if candidate_type in {"title", "heading", "table"}:
                break
            if not self._is_image_source_block(candidate):
                continue
            bbox = parse_bbox(candidate.get("bbox"))
            if bbox is None or bbox[3] > owner_bbox[1] or min(bbox[2], owner_bbox[2]) <= max(bbox[0], owner_bbox[0]):
                return []
            subject_indices.append(index)
        return list(reversed(subject_indices))

    def _aligned_image_pairs(self, raw_blocks: list[dict[str, Any]]) -> list[list[int]]:
        indices_by_page: dict[int, list[int]] = {}
        for index, block in enumerate(raw_blocks):
            page_index = parse_page_index(block)
            if page_index is not None and self._is_image_source_block(block) and parse_bbox(block.get("bbox")) is not None:
                indices_by_page.setdefault(page_index, []).append(index)

        pairs: list[list[int]] = []
        for indices in indices_by_page.values():
            for left_position, left_index in enumerate(indices):
                matches: list[int] = []
                for right_index in indices[left_position + 1 :]:
                    if self._strictly_horizontally_aligned(raw_blocks[left_index], raw_blocks[right_index]):
                        matches.append(right_index)
                if len(matches) == 1:
                    pairs.append([left_index, matches[0]])
        pair_counts = Counter(index for pair in pairs for index in pair)
        return [pair for pair in pairs if all(pair_counts[index] == 1 for index in pair)]

    def _strictly_horizontally_aligned(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> bool:
        left_bbox = parse_bbox(left.get("bbox"))
        right_bbox = parse_bbox(right.get("bbox"))
        if left_bbox is None or right_bbox is None:
            return False
        overlap = min(left_bbox[3], right_bbox[3]) - max(left_bbox[1], right_bbox[1])
        min_height = min(left_bbox[3] - left_bbox[1], right_bbox[3] - right_bbox[1])
        return (
            min_height > 0
            and overlap >= min_height * 0.8
            and min(left_bbox[2], right_bbox[2]) <= max(left_bbox[0], right_bbox[0])
        )

    def _bind_group_caption(
        self,
        raw_blocks: list[dict[str, Any]],
        *,
        subject_indices: list[int],
        owner_index: int,
        text: str,
        placement: str,
        reason: str,
    ) -> None:
        group_id = "image_group:" + ":".join(str(index + 1) for index in subject_indices)
        bboxes = [parse_bbox(raw_blocks[index].get("bbox")) for index in subject_indices]
        if any(bbox is None for bbox in bboxes):
            raw_blocks[owner_index][_CAPTION_OWNER_UNRESOLVED_KEY] = True
            return
        resolved_bboxes = [bbox for bbox in bboxes if bbox is not None]
        left = min(bbox[0] for bbox in resolved_bboxes)
        right = max(bbox[2] for bbox in resolved_bboxes)
        if placement == "before":
            owner_bbox = parse_bbox(raw_blocks[owner_index].get("bbox"))
            if owner_bbox is None:
                raw_blocks[owner_index][_CAPTION_OWNER_UNRESOLVED_KEY] = True
                return
            caption_bottom = owner_bbox[1]
            group_bbox = [left, caption_bottom - 1, right, caption_bottom]
        else:
            caption_top = max(bbox[3] for bbox in resolved_bboxes) + 1
            group_bbox = [left, caption_top, right, caption_top + 1]
        for index in subject_indices:
            raw_blocks[index][_CONTENT_GROUP_KEY] = group_id
        raw_blocks[owner_index].setdefault(_GROUP_CAPTIONS_KEY, []).append(
            {
                "text": text,
                "placement": placement,
                "reason": reason,
                "content_group_id": group_id,
                "subject_source_indices": subject_indices,
                "bbox": group_bbox,
            }
        )

    def _clear_annotation_fields(
        self,
        value: Any,
        *,
        captions: bool,
        footnotes: bool,
    ) -> None:
        caption_keys = {"caption", "table_caption", "chart_caption", "image_caption", "figure_caption"}
        footnote_keys = {"footnote", "table_footnote", "chart_footnote", "image_footnote", "figure_footnote"}
        if isinstance(value, dict):
            for key, child in value.items():
                if (captions and key in caption_keys) or (footnotes and key in footnote_keys):
                    value[key] = []
                else:
                    self._clear_annotation_fields(child, captions=captions, footnotes=footnotes)
        elif isinstance(value, list):
            for child in value:
                self._clear_annotation_fields(child, captions=captions, footnotes=footnotes)

    def _append_group_captions(
        self,
        blocks: list[DocumentIRBlock],
        group_captions: list[Any],
        *,
        placement: str,
        owner_block_id: str,
        order: int,
        page_index: int | None,
        page_width: float | None,
        quality_flags: list[str],
    ) -> None:
        for caption_index, item in enumerate(group_captions):
            if not isinstance(item, dict) or item.get("placement") != placement:
                continue
            text = str(item.get("text") or "").strip()
            subject_indices = item.get("subject_source_indices")
            bbox = item.get("bbox")
            if not text or not isinstance(subject_indices, list):
                continue
            caption_id = f"{owner_block_id}_group_caption_{caption_index + 1:04d}"
            caption_layout = build_block_layout(
                {"page_idx": page_index, "bbox": bbox},
                source_type="standalone_caption",
                source_index=order,
                quality_flags=quality_flags,
                block_id=caption_id,
                page_width=page_width,
            )
            blocks.append(
                DocumentIRBlock(
                    id=caption_id,
                    type="paragraph",
                    order=order,
                    page_index=page_index,
                    text=text,
                    layout=caption_layout,
                    metadata={
                        "source_type": "standalone_caption",
                        "source_block_id": owner_block_id,
                        "annotation_role": "standalone_caption",
                        "semantic_decision_reason": str(item.get("reason") or "image_group_caption"),
                        "content_group_id": item.get("content_group_id"),
                        "subject_block_ids": [f"block_{int(index) + 1:04d}" for index in subject_indices],
                    },
                )
            )
            subject_ids = ":".join(f"block_{int(index) + 1:04d}" for index in subject_indices)
            quality_flags.append(f"{item.get('reason')}:{subject_ids if placement == 'after' else owner_block_id}")

    def _reassociate_image_group(
        self,
        group: list[dict[str, Any]],
        *,
        sparse_table_positions: set[int],
    ) -> list[dict[str, Any]]:
        captions_by_block = [
            self._reassociation_caption_candidates(block)
            if sparse_table_positions
            else self._captions(block, self._source_type(block))
            for block in group
        ]
        if not sparse_table_positions and not any(len(captions) != 1 for captions in captions_by_block):
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
        for position, (block, (_label, _number, caption)) in enumerate(zip(group, ordered, strict=True)):
            copied = deepcopy(block)
            source_type = self._source_type(copied)
            self._clear_annotation_fields(copied, captions=True, footnotes=False)
            if position in sparse_table_positions:
                footnotes = self._footnotes(copied, "table")
                self._clear_annotation_fields(copied, captions=False, footnotes=True)
                copied["type"] = "chart"
                copied.pop("block_type", None)
                copied.pop("table_body", None)
                copied.pop("table_html", None)
                source_type = "chart"
                if footnotes:
                    copied["chart_footnote"] = footnotes
            copied[f"{source_type}_caption"] = [caption]
            reassociated.append(copied)
        return reassociated

    def _reassociation_caption_candidates(self, raw_block: dict[str, Any]) -> list[str]:
        """仅为严格编号组试算拆出 flat rich caption 的第二个明确图号。"""

        source_type = self._source_type(raw_block)
        captions = self._captions(raw_block, source_type)
        splits: list[tuple[str, list[str]]] = []
        for value in self._caption_values(raw_block, source_type):
            split = self._split_second_numbered_rich_caption(value)
            if split is not None:
                splits.append((join_text_fragments(value), split))
        if len(splits) != 1:
            return captions
        original, split = splits[0]
        if original not in captions:
            return captions
        index = captions.index(original)
        return [*captions[:index], *split, *captions[index + 1 :]]

    def _split_second_numbered_rich_caption(self, value: Any) -> list[str] | None:
        if not (
            isinstance(value, list)
            and value
            and all(self._is_caption_inline_node(item) for item in value)
        ):
            return None
        starts = [
            index
            for index, node in enumerate(value)
            if node.get("type") == "text"
            and NUMBERED_FIGURE_CAPTION_RE.match(clean_text(node.get("content", "")))
        ]
        if len(starts) != 2 or starts[0] != 0:
            return None
        split = [join_text_fragments(value[: starts[1]]), join_text_fragments(value[starts[1] :])]
        return split if all(NUMBERED_FIGURE_CAPTION_RE.match(caption) for caption in split) else None

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

    def _source_heading_level(self, raw_block: dict[str, Any]) -> int | None:
        """读取顶层或 v2 content 内的显式标题层级，不在 converter 内猜默认值。"""

        raw_level = raw_block.get("text_level", raw_block.get("level"))
        content = raw_block.get("content")
        if raw_level is None and isinstance(content, dict):
            raw_level = content.get("level")
        if raw_level is None:
            return None
        try:
            return int(raw_level)
        except (TypeError, ValueError):
            return None

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
        content = raw_block.get("content")
        if isinstance(content, dict) and any(key in content for key in ("math_content", "math_type", "image_source")):
            math_content = content.get("math_content")
            if not isinstance(math_content, str):
                return None
            return math_content.strip() or None
        return self._first_text_from_keys(raw_block, ("latex", "math_content", "equation_content", "text", "content"))

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

        content = raw_block.get("content")
        if isinstance(content, dict) and isinstance(content.get("list_items"), list):
            items = [
                join_text_fragments(item.get("item_content", []))
                for item in content["list_items"]
                if isinstance(item, dict) and isinstance(item.get("item_content"), list)
            ]
            return [item for item in items if item] or None

        raw_text = self._raw_text_preserving_lines(raw_block)
        if parse_decimal_list_marker(raw_text) is not None:
            return [clean_text(raw_text)]
        multiline_items = split_multiline_list_items(raw_text)
        if multiline_items:
            return multiline_items

        toc_items = split_toc_like_lines(raw_text)
        if toc_items:
            return toc_items

        items = coerce_text_list(raw_block.get("content"))
        return items or None

    def _captions(self, raw_block: dict[str, Any], source_type: str) -> list[str]:
        captions = [
            caption
            for value in self._caption_values(raw_block, source_type)
            for caption in self._caption_texts(value)
        ]
        return self._unique_texts(captions)

    def _caption_values(self, raw_block: dict[str, Any], source_type: str) -> list[Any]:
        keys = ["caption"]
        if source_type == "table":
            keys.insert(0, "table_caption")
        elif source_type in {"chart", "image", "figure"}:
            keys.insert(0, f"{source_type}_caption")
        return [
            value
            for key in keys
            for value in find_values_by_key(raw_block, key)
        ]

    def _caption_texts(self, value: Any) -> list[str]:
        """按 MinerU 数组层级保留题注逻辑分组。"""

        if isinstance(value, list):
            if value and all(self._is_caption_inline_node(item) for item in value):
                caption = join_text_fragments(value)
                return [caption] if caption else []
            return [caption for item in value for caption in self._caption_texts(item)]
        return coerce_text_list(value)

    def _is_caption_inline_node(self, value: Any) -> bool:
        return (
            isinstance(value, dict)
            and isinstance(value.get("type"), str)
            and isinstance(value.get("content"), str)
        )

    def _footnotes(self, raw_block: dict[str, Any], source_type: str) -> list[str]:
        keys = ["footnote"]
        if source_type == "table":
            keys.insert(0, "table_footnote")
        elif source_type in {"chart", "image", "figure"}:
            keys.insert(0, f"{source_type}_footnote")
        footnotes = [
            footnote
            for key in keys
            for value in find_values_by_key(raw_block, key)
            for footnote in self._caption_texts(value)
        ]
        return self._unique_texts(merge_footnote_fragments(footnotes))

    def _resolve_image_path(self, raw_block: dict[str, Any], package_root: Path) -> Path | None:
        """只在已绑定结果根内解析资产，basename fallback 必须唯一。"""

        raw_path = extract_first_asset_path(raw_block)
        if not raw_path:
            return None
        normalized = raw_path.strip().replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if not normalized:
            return None
        relative_path = Path(normalized)
        if (
            not relative_path.name
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            return None
        root = package_root.resolve()
        direct = (root / relative_path).resolve()
        if direct.is_file() and root in direct.parents:
            return direct
        matches = [
            resolved
            for match in package_root.rglob(relative_path.name)
            if (resolved := match.resolve()).is_file() and root in resolved.parents
        ]
        return matches[0] if len(matches) == 1 else None

    def _raw_text(self, raw_block: dict[str, Any]) -> str | None:
        text = clean_text(self._raw_text_preserving_lines(raw_block))
        return text or None

    def _raw_text_preserving_lines(self, raw_block: dict[str, Any]) -> str:
        for key in ("text", "content"):
            raw_value = raw_block.get(key)
            if isinstance(raw_value, str):
                return clean_markdown_document(raw_value)
            nodes = self._rich_text_nodes(raw_value)
            if nodes is not None:
                return join_text_fragments(nodes, clean=False)
            texts = coerce_text_list(raw_value)
            if texts:
                return "\n".join(texts)
        return ""

    def _rich_text_nodes(self, raw_value: Any) -> list[dict[str, Any]] | None:
        if isinstance(raw_value, list) and all(isinstance(item, dict) for item in raw_value):
            return raw_value
        if not isinstance(raw_value, dict):
            return None
        for field_name in (
            "title_content",
            "paragraph_content",
            "page_header_content",
            "page_footer_content",
            "page_number_content",
        ):
            nodes = raw_value.get(field_name)
            if isinstance(nodes, list) and all(isinstance(item, dict) for item in nodes):
                return nodes
        return None

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
