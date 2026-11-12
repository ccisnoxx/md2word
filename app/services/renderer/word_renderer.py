from __future__ import annotations

# app/services/renderer/word_renderer.py: 将 DocumentIR v1/v2 按模板配置渲染为可编辑 DOCX。

import io
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_HEADER_FOOTER, WD_SECTION_START
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Twips

from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.failure_context import FAILURE_CONTEXT_ATTRIBUTE, attach_failure_context
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock
from app.services.renderer.formula_renderer import WordFormulaRendererMixin
from app.services.renderer.image_renderer import WordImageRendererMixin
from app.services.renderer.list_numbering import WordListNumberingMixin
from app.services.renderer.native_table_renderer import WordNativeTableRendererMixin
from app.services.renderer.page_layout_renderer import WordPageLayoutMixin
from app.services.renderer.image_evidence import caption_bookmark_inventory, new_image_report, finish_image_report
from app.services.renderer.layout_plan import build_image_plan
from app.services.renderer.block_evidence import RenderCollector, WordRenderResult, ItemEvidence, paragraph_target
from app.services.renderer.block_anchors import bookmark_inventory, materialize_block_anchors
from app.services.renderer.table_renderer import WordTableRendererMixin
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.renderer.template_conformance import build_template_conformance_report
from app.services.renderer.text_renderer import WordTextRendererMixin
from app.services.renderer.content_contract import CONTENT_VERSION, build_formula_source_coverage, formula_sources, content_failure
from app.services.renderer.render_evidence_validation import render_contract_failure
from app.services.renderer.resource_identity import RenderResourceInputs, normalized_resource_identity
from app.services.renderer.render_preparation import PreparedRender, _source_page_context, prepare_render
from app.services.document_ir.table_placeholder import decode_placeholders


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]


@dataclass(frozen=True, slots=True)
class DocumentIRRenderOptions:
    """document_jobs 正式管线为单次渲染提供的选项。"""

    subscript_config_path: Path | None = None
    document_language: str | None = None
    template_version_id: str | None = None
    resource_inputs: RenderResourceInputs | None = field(default=None, repr=False)
    layout_asset_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class DocumentIRRenderResult:
    """同一次渲染生成的 DOCX 与私有公式、图片报告。"""

    content: bytes = field(repr=False)
    formula_report: dict[str, Any]
    image_layout_report: dict[str, Any] | None = None


@dataclass(slots=True)
class _RenderContext:
    """单次渲染的字段目标、图片计划和报告，不写入可并发复用的实例。"""

    caption_bookmarks: dict[tuple[str, int], tuple[str, int]]
    collector: RenderCollector | None = None
    formula_sources: list[dict[str, Any]] = field(default_factory=list)
    formula_entries: list[dict[str, Any]] = field(default_factory=list)
    used_formula_sources: set[int] = field(default_factory=set)
    formula_location: tuple[str, str] | None = None
    image_report: dict[str, Any] = field(default_factory=dict)
    image_spans: dict[str, Any] = field(default_factory=dict)
    image_blocks: dict[str, DocumentIRBlock] = field(default_factory=dict)
    image_records: dict[str, tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=dict)
    consumed_images: set[str] = field(default_factory=set)
    image_bookmark_ids: dict[str, int] = field(default_factory=dict)
    source_blocks: list[DocumentIRBlock] = field(default_factory=list)
    fragment_markers: list[tuple[str, Any]] = field(default_factory=list)
    placeholders: list[Any] = field(default_factory=list)
    assets: dict[str, Any] = field(default_factory=dict)
    image_loader: Any = None


class DocumentIRWordRenderer(WordTextRendererMixin, WordFormulaRendererMixin, WordListNumberingMixin, WordTableRendererMixin,
                             WordNativeTableRendererMixin, WordImageRendererMixin, WordPageLayoutMixin):
    """P0 Word 渲染器：覆盖标题、段落、基础表格和图片。"""

    def render_to_bytes(
        self,
        document_ir: DocumentIR,
        *,
        template_path: Path | None,
        config_path: Path | None,
        image_loader: ImageContentLoader,
        options: DocumentIRRenderOptions | None = None,
    ) -> bytes:
        """按模板 DOCX 与配置包生成 Word 二进制。"""

        return self.render_to_result(document_ir, template_path=template_path, config_path=config_path, image_loader=image_loader, options=options).content

    def render_to_result(
        self,
        document_ir: DocumentIR,
        *,
        template_path: Path | None,
        config_path: Path | None,
        image_loader: ImageContentLoader,
        options: DocumentIRRenderOptions | None = None,
    ) -> WordRenderResult:
        """以单次文档上下文生成字节和私有报告，兼容入口共用此核心。"""

        verified_inputs = options.resource_inputs if options is not None else None
        if verified_inputs is None:
            config_content = config_path.read_bytes() if config_path is not None else None
            template_content = template_path.read_bytes() if template_path is not None else None
        else:
            config_content = verified_inputs.template_config
            template_content = verified_inputs.template_docx
        template_config = self._load_template_config(document_ir, config_path, options, content=config_content)
        asset_dir = options.layout_asset_dir if options is not None else None
        logo_path = self._resolve_asset_path(
            template_config.header.logo_path, asset_dir or (config_path.parent if config_path is not None else None),
        )
        logo_content = logo_path.read_bytes() if template_config.header.enabled and logo_path is not None and logo_path.exists() else None
        resources = normalized_resource_identity(template_content=template_content, config=template_config,
            logo_content=logo_content, document_language=options.document_language if options and options.document_language else document_ir.metadata.document_language)
        prepared = prepare_render(document_ir, template_config, resources)
        document, render_context, reserved_bookmarks = self._open_document(
            document_ir, prepared, template_config, template_content=template_content,
            config_content=config_content, logo_content=logo_content, image_loader=image_loader, options=options)
        for operation_index, operation in enumerate(prepared.plan.operations):
            self._dispatch_operation(document, document_ir, operation_index, operation, prepared,
                                     template_config, render_context)
        result = self._freeze_result(document, document_ir, prepared, render_context, reserved_bookmarks)
        conformance = build_template_conformance_report(
            result.content, template_content=template_content, layout_config_content=config_content,
            header_override=template_config.header.enabled, footer_override=template_config.footer.enabled,
            resource_hashes_verified=verified_inputs is not None,
        )
        return replace(
            result, template_conformance=conformance,
            resource_inputs=replace(verified_inputs, logo=logo_content) if verified_inputs is not None else None,
        )

    def _open_document(self, document_ir: DocumentIR, prepared: PreparedRender,
                       template_config: TemplateConfigPackage, *, template_content: bytes | None,
                       config_content: bytes | None, logo_content: bytes | None,
                       image_loader: ImageContentLoader, options: DocumentIRRenderOptions | None,
                       ) -> tuple[Any, _RenderContext, Any]:
        """加载模板、清空正文、写入页面设置与页眉页脚，并建立本次渲染上下文。"""

        table_plan, plan, collector = prepared.table_plan, prepared.plan, prepared.collector
        # 资源快照和计划在创建 Word 对象前固定；后续 writer 只消费同一计划。
        document = Document(io.BytesIO(template_content)) if template_content is not None else Document()
        reserved_bookmarks = bookmark_inventory(document)
        self._clear_body(
            document, preserve_header=not template_config.header.enabled, preserve_footer=not template_config.footer.enabled,
        )
        self._apply_page_setup(document, template_config)
        self._apply_header_footer(document, template_config, logo_bytes=logo_content)
        self._apply_document_settings(document, document_ir)

        assets_by_id = {asset.id: asset for asset in document_ir.assets}
        render_context = self._build_render_context(document_ir, table_plan, plan.table_units)
        render_context.collector = collector
        render_context.assets, render_context.image_loader = assets_by_id, image_loader
        expected_formulas = len(render_context.formula_sources)
        if any(1_000_001 <= value <= 1_000_000 + expected_formulas for value in reserved_bookmarks[1]):
            raise content_failure("ir_render_evidence:target_mismatch")
        render_context.image_report = new_image_report(document_ir, template_config=template_config,
            template_content=template_content, config_content=config_content,
            template_version_id=options.template_version_id if options else None,
            language=(options.document_language if options and options.document_language else document_ir.metadata.document_language))
        render_context.source_blocks = sorted(document_ir.blocks, key=lambda block: block.order)
        render_context.image_blocks = {block.id: block for block in document_ir.blocks if block.type == "image"}
        render_context.image_spans = {block_id: span for span in build_image_plan(document_ir) for block_id in span.block_ids}
        document.part._md2word_formula_context = render_context
        return document, render_context, reserved_bookmarks

    def _dispatch_operation(self, document: Any, document_ir: DocumentIR, operation_index: int, operation: Any,
                            prepared: PreparedRender, template_config: TemplateConfigPackage,
                            render_context: _RenderContext) -> None:
        """执行单个计划操作；失败时只补充操作定位后原样抛出。"""

        blocks, decisions, collector = prepared.blocks, prepared.decisions, prepared.collector
        native_units, unit_contracts, tables = prepared.native_units, prepared.unit_contracts, prepared.tables
        assets_by_id, image_loader = render_context.assets, render_context.image_loader
        try:
            if operation.kind == "section":
                if operation.start_kind != "initial":
                    section = document.add_section(WD_SECTION_START.NEW_PAGE if operation.start_kind == "new_page" else WD_SECTION_START.CONTINUOUS)
                    if operation.start_kind == "continuous":
                        self._set_section_columns(section, operation.columns)
            elif operation.kind == "configure_page":
                self._configure_layout_page_section(document, template_config, landscape=operation.landscape)
            elif operation.kind == "decoration":
                self._render_page_decoration(document, operation, blocks, template_config, collector)
            elif operation.kind == "column_break":
                document.add_paragraph().add_run().add_break(WD_BREAK.COLUMN)
            elif operation.kind == "logical_table":
                self._render_native_unit(document, native_units[operation.unit_id], unit_contracts[operation.unit_id],
                    blocks, template_config, render_context, page_break_before=decisions[operation.block_ids[0]].page_break_before)
            elif operation.kind == "block":
                block = blocks[operation.block_ids[0]]
                if block.type == "image":
                    self._render_image_span(document, render_context.image_spans[block.id], [blocks[key] for key in operation.block_ids],
                        assets_by_id, template_config, image_loader, render_context, page_width=operation.page_width)
                else:
                    self._render_block(document, block, assets_by_id, template_config, image_loader, render_context,
                        decision=decisions[block.id], table_model=tables.get(block.id, (None, None))[0], page_width=operation.page_width)
        except Exception as error:
            # 只补充定位后原样抛出：异常类型、失败分类与错误码不变。
            # 块类操作本身不带页索引，取首块渲染决策中的源页。
            decision = decisions.get(operation.block_ids[0]) if operation.block_ids else None
            page_index = (operation.source_page_index if operation.source_page_index is not None
                          else decision.source_page_index if decision is not None else None)
            attach_failure_context(error, operation_index=operation_index, operation_kind=operation.kind,
                section_id=operation.section_id, block_ids=list(operation.block_ids),
                source_page_index=page_index, unit_id=getattr(operation, "unit_id", None),
                **_source_page_context(document_ir))
            raise

    def _freeze_result(self, document: Any, document_ir: DocumentIR, prepared: PreparedRender,
                       render_context: _RenderContext, reserved_bookmarks: Any) -> WordRenderResult:
        """实体化锚点、保存 DOCX，并冻结块级证据与公式覆盖。"""

        table_plan, plan, collector = prepared.table_plan, prepared.plan, prepared.collector
        self._materialize_fragment_markers(document, render_context, reserved_bookmarks)
        collector.created_anchors, collector.block_anchor_counts = materialize_block_anchors(
            document, collector.records, collector.targets, reserved_bookmarks)
        buffer = io.BytesIO()
        document.save(buffer)
        content = buffer.getvalue()
        try:
            evidence, ownership, anchors, anchor_ownership = collector.freeze(document, content, plan)
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise render_contract_failure(error) from None
        formula_report = {"schema_version": "formula-render/v1", "entries": render_context.formula_entries}
        coverage = build_formula_source_coverage(document_ir, content, table_plan, formula_report)
        return WordRenderResult(content, plan, evidence, CONTENT_VERSION, coverage, ownership,
            formula_report=formula_report,
            image_layout_report=finish_image_report(render_context.image_report),
            block_anchor_evidence=anchors, _anchor_ownership=anchor_ownership,
            block_anchor_counts=collector.block_anchor_counts)

    def _apply_document_settings(self, document: Any, document_ir: DocumentIR) -> None:
        """设置输出选项；显式多行正文的软换行不参与两端对齐拉伸。"""

        settings = document.settings.element
        for tag in ("w:doNotAutoCompressPictures", "w:updateFields"):
            element = settings.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                settings.append(element)
            element.set(qn("w:val"), "true")

        if any(block.type == "paragraph" and (block.layout is None or block.layout.role == "body")
               and "\n" in (block.text or "") for block in document_ir.blocks):
            compat = settings.find(qn("w:compat"))
            if compat is None:
                compat = OxmlElement("w:compat")
                settings.insert_element_before(compat,
                    "w:docVars", "w:rsids", "m:mathPr", "w:uiCompat97To2003", "w:attachedSchema",
                    "w:themeFontLang", "w:clrSchemeMapping", "w:doNotIncludeSubdocsInStats",
                    "w:doNotAutoCompressPictures", "w:forceUpgrade", "w:captions", "w:readModeInkLockDown",
                    "w:smartTagType", "sl:schemaLibrary", "w:shapeDefaults", "w:doNotEmbedSmartTags",
                    "w:decimalSymbol", "w:listSeparator")
            element = compat.find(qn("w:doNotExpandShiftReturn"))
            if element is None:
                element = OxmlElement("w:doNotExpandShiftReturn")
                # CT_Compat 是有序序列，保留既有标志并在其规范位置插入。
                preceding_tags = {qn(tag) for tag in (
                    "w:useSingleBorderforContiguousCells", "w:wpJustification", "w:noTabHangInd", "w:noLeading",
                    "w:spaceForUL", "w:noColumnBalance", "w:balanceSingleByteDoubleByteWidth",
                    "w:noExtraLineSpacing", "w:doNotLeaveBackslashAlone", "w:ulTrailSpace",
                )}
                position = max((index + 1 for index, child in enumerate(compat)
                                if child.tag in preceding_tags), default=0)
                compat.insert(position, element)
            element.set(qn("w:val"), "true")

    def _content_width_and_columns(self, document: Any) -> tuple[int, int]:
        sections = getattr(document, "sections", None)
        if not sections:
            return int(Cm(14)), 1
        section = sections[-1]
        total_width = section.page_width - section.left_margin - section.right_margin
        if total_width <= 0:
            return int(Cm(14)), 1

        columns = section._sectPr.find(qn("w:cols"))
        raw_count = columns.get(qn("w:num")) if columns is not None else None
        column_count = max(int(raw_count), 1) if raw_count and raw_count.isdigit() else 1
        if column_count == 1:
            return int(total_width), 1
        raw_space = columns.get(qn("w:space")) if columns is not None else None
        column_space = int(raw_space) if raw_space and raw_space.isdigit() else 720
        available_width = total_width - Twips(column_space * (column_count - 1))
        return max(int(available_width / column_count), 1), column_count

    def _build_render_context(self, document_ir: DocumentIR, table_plan, contracts) -> _RenderContext:
        placeholders = decode_placeholders(document_ir)
        return _RenderContext(caption_bookmarks=caption_bookmark_inventory(document_ir, table_contracts=contracts,
                primary_table_block_ids={document_ir.blocks[unit.anchor_block_index].id
                                         for unit in table_plan.units if unit.is_group_primary}),
            formula_sources=[source.binding for source in formula_sources(document_ir, table_plan) if source.representative is None],
            placeholders=placeholders,
            image_bookmark_ids={f"reserved-placeholder:{index}": 2_000_000 + index for index in range(len(placeholders))})

    def _materialize_fragment_markers(self, document, context, reserved):
        """全部固定公式完成后分配 TAB 数字 ID，通用 block 锚点随后读取实际占用集。"""
        if len(context.used_formula_sources) != len(context.formula_sources):
            raise content_failure("ir_render_evidence:target_mismatch")
        names, ids = bookmark_inventory(document)
        if len(context.formula_entries) != len(context.formula_sources):
            raise content_failure("ir_render_evidence:target_mismatch")
        names.update(reserved[0])
        ids.update(reserved[1])
        next_id = max(max(ids, default=-1), 1_000_000 + len(context.formula_entries)) + 1
        if next_id + len(context.fragment_markers) > 2_147_483_647:
            raise content_failure("ir_render_evidence:target_mismatch")
        for name, paragraph in context.fragment_markers:
            if name in names:
                raise content_failure("ir_render_evidence:target_mismatch")
            start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
            start.set(qn("w:name"), name)
            start.set(qn("w:id"), str(next_id))
            end.set(qn("w:id"), str(next_id))
            paragraph.append(start)
            paragraph.append(end)
            names.add(name)
            next_id += 1

    def _load_template_config(
        self,
        document_ir: DocumentIR,
        config_path: Path | None,
        options: DocumentIRRenderOptions | None,
        *,
        content: bytes | None = None,
    ) -> TemplateConfigPackage:
        document_language = (
            options.document_language
            if options is not None and options.document_language
            else document_ir.metadata.document_language
        )
        template_config = (TemplateConfigPackage.load_content(content) if content is not None else TemplateConfigPackage.load(config_path)).for_document_language(document_language)
        terminology = None
        if options is not None and options.resource_inputs is not None:
            terminology = TerminologyReplacer.from_content(options.resource_inputs.symbol_rules)
        elif options is not None and options.subscript_config_path is not None:
            terminology = TerminologyReplacer(options.subscript_config_path)
        if terminology is not None and terminology.rules:
            template_config.terminology = terminology
        return template_config

    def _clear_body(self, document: Any, *, preserve_header: bool, preserve_footer: bool) -> None:
        body = document._body._element
        sect_pr = body.sectPr
        sections = document.element.sectPr_lst
        # 清除前面的分节时，将末节沿用的引用固定下来，避免一同丢失。
        if sect_pr is not None and len(sections) > 1:
            for reference_type in WD_HEADER_FOOTER:
                if preserve_header and sect_pr.get_headerReference(reference_type) is None:
                    for source in reversed(sections[:-1]):
                        if (reference := source.get_headerReference(reference_type)) is not None:
                            sect_pr.add_headerReference(reference_type, reference.rId)
                            break
                if preserve_footer and sect_pr.get_footerReference(reference_type) is None:
                    for source in reversed(sections[:-1]):
                        if (reference := source.get_footerReference(reference_type)) is not None:
                            sect_pr.add_footerReference(reference_type, reference.rId)
                            break
        for child in list(body):
            if child is sect_pr:
                continue
            body.remove(child)

    def _resolve_asset_path(self, raw_path: str | None, asset_dir: Path | None) -> Path | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        if asset_dir is not None:
            return (asset_dir / candidate).resolve()
        return candidate.resolve()

    def _render_block(
        self, document: Any, block: DocumentIRBlock, assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage, image_loader: ImageContentLoader, render_context: _RenderContext,
        *, decision: Any, table_model: Any = None, page_width: float | None = None,
    ) -> None:
        collector = render_context.collector
        if decision.mode == "native_text":
            texts = block.list_items or [] if block.type == "list" else [block.latex or block.text or "" if block.type == "formula" else block.text or ""]
            for index, (text, policy) in enumerate(zip(texts, decision.text_policies, strict=True)):
                if policy.mode == "coalesced":
                    collector.records[block.id].items.append(ItemEvidence(item_index=index, disposition="coalesced",
                        representative_block_id=policy.representative_block_id, representative_item_index=policy.representative_item_index))
                    collector.representatives[block.id, index] = (block.id, policy.representative_block_id, index, policy.representative_item_index)
                    continue
                render_context.formula_location = (block.id, f"list_items/{index}" if block.type == "list"
                    else "latex" if block.type == "formula" and block.latex else "text")
                if policy.mode == "toc_formula_first":
                    field_paragraph = document.add_paragraph()
                    self._fill_toc_entry_paragraph(field_paragraph, policy, template_config)
                    if decision.keep_with_next:
                        field_paragraph.paragraph_format.keep_with_next = True
                    collector.add(block.id, [paragraph_target(field_paragraph, "toc_field", index)])
                paragraph = document.add_paragraph()
                self._fill_planned_text(paragraph, text, policy, template_config,
                    reference_bookmarks=render_context.caption_bookmarks)
                if decision.keep_with_next:
                    paragraph.paragraph_format.keep_with_next = True
                if decision.page_break_before and (block.type == "heading" or policy.mode == "table_context"):
                    paragraph.paragraph_format.page_break_before = True
                role = "list_item" if block.type == "list" else "formula" if block.type == "formula" else "body"
                collector.add(block.id, [paragraph_target(paragraph, role, index)])
                if block.type == "list":
                    collector.records[block.id].items.append(ItemEvidence(item_index=index, disposition="rendered"))
            if block.type == "list" and not texts:
                collector.records[block.id].reason_code = "empty_list"
        elif decision.table_strategy is not None:
            placeholders = [item for item in render_context.placeholders if item.owner_block_id == block.id]
            if placeholders and not (block.html or "").strip():
                collector.add(block.id, self._render_table_captions(document, block, template_config,
                    caption_bookmarks=render_context.caption_bookmarks, page_break_before=decision.page_break_before,
                    style_groups=decision.annotation_styles))
                if block.text and block.text not in block.captions:
                    paragraph = document.add_paragraph()
                    self._set_formula_source(document, block.id, "text")
                    self._fill_paragraph(paragraph, block.text, template_config.normal, terminology=template_config.terminology)
                    collector.add(block.id, [paragraph_target(paragraph)])
                self._render_table_placeholders(document, {item.fragment_id for item in placeholders},
                    assets_by_id, image_loader, render_context, template_config)
                collector.add(block.id, self._render_table_notes(document, block, template_config))
                return
            collector.add(block.id, self._render_table(document, block, template_config,
                caption_bookmarks=render_context.caption_bookmarks, reference_bookmarks=render_context.caption_bookmarks,
                page_break_before=decision.page_break_before, table_model=table_model, table_strategy=decision.table_strategy, annotation_styles=decision.annotation_styles))
