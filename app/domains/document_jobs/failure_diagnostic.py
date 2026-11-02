from __future__ import annotations

# 文件：app/domains/document_jobs/failure_diagnostic.py
# 用途：从当前代 stage_failed 事件的已脱敏 MinerU 验证报告或渲染失败上下文投影失败定位，供详情与异常中心共用。

from collections.abc import Iterable
from typing import Any

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.domains.document_jobs.schemas import DocumentJobFailureDiagnosticResponse


def project_failure_diagnostic(
    job: DocumentJobRecord,
    events: Iterable[DocumentJobEventRecord],
) -> DocumentJobFailureDiagnosticResponse | None:
    """报告已在写事件时按白名单脱敏；此处只做类型收窄，不满足条件时返回 None 而非猜测。"""

    if job.status != "failed":
        return None
    # 缺 retry_count 的历史事件无法确认代数，不能用于当前失败。
    event = next((
        item for item in sorted(events, key=lambda item: item.created_at, reverse=True)
        if item.event_type == "stage_failed"
        and _non_negative_int(item.payload.get("retry_count")) == job.retry_count
        and (isinstance(item.payload.get("mineru_validation"), dict) or isinstance(item.payload.get("failure_context"), dict))
    ), None)
    if event is None:
        return None
    if not isinstance(event.payload.get("mineru_validation"), dict):
        return _project_render_failure(event)
    report = event.payload["mineru_validation"]
    first = report.get("first_fatal")
    if report.get("can_convert") is not False or not isinstance(first, dict):
        return None
    code = _text(first.get("code"))
    if code is None:
        return None
    page_index = _non_negative_int(first.get("page_index"))
    affected = {page_index} if page_index is not None else set()
    blockers = report.get("blockers")
    for issue in blockers if isinstance(blockers, list) else []:
        if isinstance(issue, dict) and issue.get("stops_conversion") is True:
            index = _non_negative_int(issue.get("page_index"))
            if index is not None:
                affected.add(index)
    facts = first.get("facts")
    return DocumentJobFailureDiagnosticResponse(
        stage=event.stage,
        scope="document" if page_index is None else "page",
        page_number=None if page_index is None else page_index + 1,
        source_type=_text(first.get("source_type")),
        json_pointer=_text(first.get("json_pointer")),
        reason_code=code,
        reason=_text(facts.get("reason")) if isinstance(facts, dict) else None,
        affected_page_numbers=[index + 1 for index in sorted(affected)],
        fatal_count=_non_negative_int(report.get("fatal_count")) or 0,
        warning_count=_non_negative_int(report.get("warning_count")) or 0,
        details_truncated=report.get("details_truncated") is True,
    )


def _project_render_failure(event: DocumentJobEventRecord) -> DocumentJobFailureDiagnosticResponse | None:
    """渲染操作定位：一次失败只对应一个操作；无源页的操作（如页眉页脚装饰）按文档级展示。"""
    context = event.payload["failure_context"]
    code = _text(context.get("reason_code"))
    if code is None:
        return None
    page_index = _non_negative_int(context.get("source_page_index"))
    block_ids = context.get("block_ids")
    return DocumentJobFailureDiagnosticResponse(
        source="render_operation",
        stage=event.stage,
        scope="document" if page_index is None else "page",
        page_number=None if page_index is None else page_index + 1,
        reason_code=code,
        affected_page_numbers=[] if page_index is None else [page_index + 1],
        fatal_count=1,
        block_ids=[item for item in block_ids if isinstance(item, str)] if isinstance(block_ids, list) else [],
        operation_kind=_text(context.get("operation_kind")),
    )


def _non_negative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
