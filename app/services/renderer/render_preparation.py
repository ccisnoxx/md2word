"""DocumentIR 渲染准备阶段：在创建 Word 对象前冻结布局、表格与渲染计划。"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from app.services.document_ir.integrity import build_page_counts
from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.services.failure_context import attach_failure_context
from app.services.renderer.block_evidence import RenderCollector
from app.services.renderer.layout_plan import LayoutPlan, _block_page_index, build_layout_plan
from app.services.renderer.logical_table_plan import LogicalTableRenderPlan, build_content_table_plan
from app.services.renderer.render_evidence_validation import render_contract_failure
from app.services.renderer.render_plan import RenderPlan, ResourceIdentity, build_render_plan
from app.services.renderer.table_renderer import TableRenderError, prepare_table_input
from app.services.renderer.template_config import TemplateConfigPackage


@dataclass(frozen=True, slots=True)
class PreparedRender:
    """单次渲染的冻结输入；后续 writer 只消费这里的计划，不再重建。

    字典字段是由计划派生的只读索引，在分发阶段按块/单元查找，避免每个操作重复构建。
    """

    layout_plan: LayoutPlan
    table_plan: LogicalTableRenderPlan
    tables: dict[str, tuple[Any, str]]
    plan: RenderPlan
    collector: RenderCollector
    blocks: dict[str, DocumentIRBlock]
    decisions: dict[str, Any]
    native_units: dict[Any, Any]
    unit_contracts: dict[str, Any]


def _source_page_context(document_ir: DocumentIR) -> dict[str, Any]:
    """失败任务没有交付结果，总页数只能随失败定位一起带出。"""
    counts = build_page_counts(document_ir) or {}
    return {"source_page_count": counts.get("source_page_count"), "page_count_basis": counts.get("page_count_basis")}


def _attach_plan_failure_context(error: BaseException, document_ir: DocumentIR, operation_kind: str,
                                 block: DocumentIRBlock | None = None) -> None:
    """计划阶段尚无操作序号；只有能归属到具体块时才带页码，否则按文档级失败展示。"""
    attach_failure_context(error, operation_index=None, operation_kind=operation_kind, section_id=None,
                           block_ids=[block.id] if block is not None else [],
                           source_page_index=_block_page_index(block) if block is not None else None, unit_id=None,
                           **_source_page_context(document_ir))


def prepare_render(document_ir: DocumentIR, template_config: TemplateConfigPackage,
                   resources: ResourceIdentity) -> PreparedRender:
    """依次构建布局计划、内容表格计划、表格输入和 RenderPlan；每一步失败都带计划阶段定位后原样抛出。"""

    try:
        layout_plan = build_layout_plan(document_ir)
    except Exception as error:
        _attach_plan_failure_context(error, document_ir, "layout_plan")
        raise
    try:
        table_plan = build_content_table_plan(document_ir, layout_plan)
    except Exception as error:
        _attach_plan_failure_context(error, document_ir, "table_plan",
                                     document_ir.blocks[error.block_index] if isinstance(error, TableRenderError) else None)
        raise
    grid_by_block = {fragment.source.block_id: fragment.render.grid for unit in table_plan.units
                    for fragment in unit.fragments if fragment.render is not None}
    tables = {}
    for block in document_ir.blocks:
        if block.type != "table":
            continue
        if block.id in grid_by_block:
            tables[block.id] = (SimpleNamespace(rows=range(grid_by_block[block.id].rows),
                max_columns=grid_by_block[block.id].columns), "standard")
            continue
        try:
            tables[block.id] = prepare_table_input(block, template_config)
        except Exception as error:
            _attach_plan_failure_context(error, document_ir, "table_prepare", block)
            raise
    try:
        plan = build_render_plan(document_ir, layout_plan=layout_plan, effective_config=template_config,
            resource_identity=resources, table_models={key: value[0] for key, value in tables.items()},
            table_strategies={key: value[1] for key, value in tables.items()}, logical_table_plan=table_plan)
        collector = RenderCollector(document_ir, plan)
    except (ValueError, TypeError, UnicodeError) as error:
        failure = render_contract_failure(error)
        _attach_plan_failure_context(failure, document_ir, "render_plan")
        raise failure from None
    except Exception as error:
        _attach_plan_failure_context(error, document_ir, "render_plan")
        raise
    return PreparedRender(
        layout_plan=layout_plan, table_plan=table_plan, tables=tables, plan=plan, collector=collector,
        blocks={block.id: block for block in document_ir.blocks},
        decisions={decision.block_id: decision for decision in plan.decisions},
        native_units={unit.key: unit for unit in table_plan.units},
        unit_contracts={unit.unit_id: unit for unit in plan.table_units},
    )
