from __future__ import annotations

# app/services/document_ir/mineru_converter.py: 将 MinerU 原始结果包转换为 DocumentIR v2。

import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    clean_text,
    classify_mineru_block,
    mineru_raw_text_preserving_lines,
    mineru_list_items,
    coerce_text_list,
    collect_text_from_fields,
    select_mineru_table_html,
    find_final_promotional_page,
    merge_footnote_fragments,
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
from app.services.document_ir.integrity import DocumentIntegrityError, build_source_integrity, ensure_integrity
from app.services.document_ir.caption_reconciler import reconcile_captions
from app.services.document_ir.logical_table_group import TableSourceLedger, attach_logical_table_groups, capture_table_sources
from app.services.document_ir.artifact_validator import (
    MinerUArtifactValidator, MinerUArtifactValidationError, MinerUValidationReport, ValidatedImage,
)
from app.services.document_ir.mineru_package import (
    DEFAULT_POLICY, MinerUPackageError, MinerUValidationPolicy, extract_zip, find_content_list,
    package_sha256, read_json_payload,
)
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRAsset,
    DocumentIRBlock,
    DocumentIRBlockType,
    DocumentIRMetadata,
)
from app.services.document_ir.table_annotations import split_table_annotation_texts


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
    validation_report: MinerUValidationReport | None = None


class MinerUToDocumentIRService:
    """P0 MinerU -> DocumentIR v2 转换器，优先保留块顺序和资产引用。"""

    def __init__(self, *, policy: MinerUValidationPolicy = DEFAULT_POLICY) -> None:
        self.policy = policy

    def convert_zip(
        self,
        zip_path: Path,
        *,
        job_id: str,
        source_file_id: str,
        document_language: str,
    ) -> MinerUToDocumentIRResult:
        """读取 MinerU 结果 zip，生成 DocumentIR v2 和待登记图片资产。"""

        report = MinerUValidationReport(package_sha256=package_sha256(zip_path), policy_version=self.policy.version)
        validator = MinerUArtifactValidator(report, policy=self.policy)
        with tempfile.TemporaryDirectory(prefix="document_ir_mineru_") as temp_dir:
            package_root = Path(temp_dir).resolve()
            try:
                extract_zip(zip_path, package_root, policy=self.policy)
                content_list_path = find_content_list(package_root)
                report.content_list_path = content_list_path.relative_to(package_root).as_posix()
                report.content_list_sha256 = package_sha256(content_list_path)
                validator.check_report_limits()
                payload, _checksum = read_json_payload(content_list_path, policy=self.policy)
                validated = validator.validate(payload, package_root=package_root, content_list_path=content_list_path)
                table_sources = capture_table_sources(payload, validated.blocks, checksum=report.content_list_sha256)
                return self._convert_blocks(
                    validated.blocks,
                    package_root=package_root,
                    content_list_path=content_list_path,
                    job_id=job_id,
                    source_file_id=source_file_id,
                    document_language=document_language,
                    validator=validator,
                    table_sources=table_sources,
                )
            except MinerUPackageError as error:
                validator.add_package_error(error)
                raise MinerUArtifactValidationError(report) from error

    def _convert_blocks(
        self,
        raw_blocks: list[dict[str, Any]],
        *,
        package_root: Path,
        content_list_path: Path,
        job_id: str,
        source_file_id: str,
        document_language: str,
        validator: MinerUArtifactValidator,
        table_sources: TableSourceLedger,
    ) -> MinerUToDocumentIRResult:
        """执行既有归一化与映射，归一化证据仍由当前 validator 统一限额。"""
        validation_report = validator.report
        blocks: list[DocumentIRBlock] = []
        image_assets: list[MinerUImageAsset] = []
        ir_assets: list[DocumentIRAsset] = []
        quality_flags: list[str] = []
        unsupported_types: set[str] = set()
        filtered_page_index = find_final_promotional_page(
            raw_blocks,
            final_page_index=find_final_source_page_index(raw_blocks, package_root, policy=self.policy),
        )
        before_filter_count = len(raw_blocks)
        filtered_sources: list[dict[str, Any]] = []
        if filtered_page_index is not None:
            filtered_sources = [
                {**block["_mineru_source"], "rule_id": "final_promotional_page/v1", "reason": "final_promotional_page"}
                for block in raw_blocks if parse_page_index(block) == filtered_page_index
            ]
            raw_blocks = [block for block in raw_blocks if parse_page_index(block) != filtered_page_index]
            quality_flags.append(f"final_promotional_page_filtered:{filtered_page_index}")
        before_merge = raw_blocks
        merge_evidence: list[dict[str, Any]] = []
        raw_blocks = merge_table_placeholder_continuations(raw_blocks, evidence=merge_evidence)
        validator.record_normalization(before_merge, raw_blocks, filtered_page_index=filtered_page_index,
                                       filtered_block_count=before_filter_count - len(before_merge),
                                       merge_evidence=merge_evidence, filtered_sources=filtered_sources)
        validator.complete_validation(raw_blocks, package_root=package_root, content_list_path=content_list_path)
        try:
            reconciled = reconcile_captions(raw_blocks)
        except DocumentIntegrityError as error:
            raise DocumentIntegrityError(error.boundary, {
                **error.evidence, "mineru_validation": validation_report.model_dump(mode="json"),
            }) from error
        if any(result.evidence and result.evidence["status"] == "uncertain" for result in reconciled):
            quality_flags.append("caption_binding_uncertain")
        source_type_counts = Counter(block["_mineru_source"]["source_type"] for block in raw_blocks)
        pages = build_pages(
            raw_blocks,
            package_root,
            quality_flags,
            excluded_page_indices={filtered_page_index} if filtered_page_index is not None else None,
            policy=self.policy,
        )
        page_width_by_index = {page.index: page.width for page in pages}

        for index, raw_block in enumerate(raw_blocks):
            block_id = f"block_{index + 1:04d}"
            source_type = str(raw_block.get("type") or raw_block.get("block_type") or "text").strip().lower()
            block_type = classify_mineru_block(raw_block, source_type)
            block_role = role_for_source_type(source_type)
            if block_type == "paragraph" and block_role == "body" and source_type not in {"", "text", "paragraph", "para"}:
                unsupported_types.add(raw_block["_mineru_source"]["source_type"])
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
            metadata = self._metadata_from_raw(raw_block)
            metadata.update(build_block_layout_metadata(layout, page_width=page_width))
            caption_result = reconciled[index]
            captions = caption_result.captions
            if caption_result.evidence is not None:
                caption_evidence = caption_result.evidence
                for receipt in [*caption_evidence["bindings"], *caption_evidence.get("candidates", [])]:
                    receipt["donor_block_id"] = f"block_{receipt.pop('donor_index') + 1:04d}"
                    receipt["target_block_id"] = f"block_{receipt.pop('target_index') + 1:04d}"
                if "members" in caption_evidence:
                    caption_evidence["members"] = [f"block_{member + 1:04d}" for member in caption_evidence["members"]]
                metadata["caption_reconciliation"] = caption_evidence
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
                image = raw_block.get("_mineru_validated_asset")
                if not isinstance(image, ValidatedImage):
                    raise ValueError("MinerU 图片缺少已验证资产。")
                asset_id = f"asset_{block_id}"
                asset_ref = asset_id
                image_assets.append(MinerUImageAsset(
                    asset_id=asset_id, block_id=block_id, source_path=image.source_path,
                    mime_type=image.mime_type, content=image.content,
                ))
                ir_assets.append(DocumentIRAsset(id=asset_id, kind="image", source_path=image.source_path))
            for context_index, context_text in enumerate(table_contexts):
                context_metadata = dict(metadata)
                context_metadata.pop("caption_reconciliation", None)
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
                    html=select_mineru_table_html(raw_block) if block_type == "table" else None,
                    latex=self._formula_text(raw_block) if block_type == "formula" else None,
                    list_items=(mineru_list_items(raw_block) or None) if block_type == "list" else None,
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
                source_block_count=len(raw_blocks),
                source_type_counts=dict(sorted(source_type_counts.items())),
                mineru_validation=validation_report,
            ),
            pages=pages,
            blocks=blocks,
            assets=ir_assets,
            quality_flags=quality_flags,
        )
        evidence = build_source_integrity(document)
        if validation_report is not None:
            evidence["mineru_validation"] = validation_report.model_dump(mode="json")
        ensure_integrity("MinerU→DocumentIR", evidence)
        attach_logical_table_groups(document, table_sources)
        return MinerUToDocumentIRResult(document=document, image_assets=image_assets, validation_report=validation_report)

    def _metadata_from_raw(self, raw_block: dict[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {"source_type": raw_block["_mineru_source"]["source_type"]}
        for key in ("bbox", "page_idx", "page_index", "text_level"):
            if key in raw_block:
                metadata[key] = raw_block[key]
        if "_mineru_source" in raw_block:
            metadata["mineru_source"] = raw_block["_mineru_source"]
        image = raw_block.get("_mineru_validated_asset")
        if isinstance(image, ValidatedImage):
            metadata["mineru_asset_resolution"] = image.resolution
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
            return captions[0] if captions else self._first_text_from_keys(raw_block, ("text",))
        if block_type == "formula":
            return self._formula_text(raw_block)
        if block_type == "list":
            items = (mineru_list_items(raw_block) or None)
            return "\n".join(items) if items else self._raw_text(raw_block)
        return self._raw_text(raw_block) or self._first_text_from_keys(raw_block, ("caption",))

    def _formula_text(self, raw_block: dict[str, Any]) -> str | None:
        content = raw_block.get("content")
        if isinstance(content, dict) and any(key in content for key in ("math_content", "math_type", "image_source")):
            math_content = content.get("math_content")
            if not isinstance(math_content, str):
                return None
            return math_content.strip() or None
        return self._first_text_from_keys(raw_block, ("latex", "math_content", "equation_content", "text", "content"))

    def _footnotes(self, raw_block: dict[str, Any], source_type: str) -> list[str]:
        keys = ["footnote"]
        if source_type == "table":
            keys.insert(0, "table_footnote")
        elif source_type in {"chart", "image", "figure"}:
            keys.insert(0, f"{source_type}_footnote")
        return self._unique_texts(merge_footnote_fragments(collect_text_from_fields(raw_block, tuple(keys))))

    def _raw_text(self, raw_block: dict[str, Any]) -> str | None:
        text = clean_text(mineru_raw_text_preserving_lines(raw_block))
        return text or None

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
