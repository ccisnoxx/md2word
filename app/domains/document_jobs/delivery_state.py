"""交付状态的纯规则；记录序列化和文件可用性检查分别由仓储与服务负责。"""

import json
from typing import Any
from app.domains.document_jobs.review import receipt_identity

from app.domains.document_jobs.quality_state import quality_patch
from app.domains.document_jobs.models import (
    DocumentJobRecord,
)


DOCUMENT_JOB_STATE_FIELDS = ("quality_status", "review_status", "delivery_status", "quality_summary")


def initial_delivery_state() -> dict[str, Any]:
    """新任务、换代和真正换件均不继承旧质量或复核证据。"""
    return {"quality_status": "pending", "review_status": "unreviewed",
            "delivery_status": "internal_draft", "quality_summary": {}}


def delivery_state_patch(job: DocumentJobRecord, patch: dict[str, Any], *, preview_contribution: dict | None = None,
                       page_quality_contribution: dict | None = None, base_quality_contribution: dict | None = None) -> dict[str, Any]:
    """在模型验证前处理证据失效；已发布记录先检查原值，不能先降级再改内容。"""
    if patch.get("current_publication_id", job.current_publication_id) != job.current_publication_id:
        raise ValueError("发布指针只能由原子发布端口维护。")
    if patch.get("delivery_status") == "published" and job.delivery_status != "published":
        raise ValueError("发布状态只能由原子发布端口维护。")
    if job.delivery_status == "published":
        if preview_contribution is not None or page_quality_contribution is not None or base_quality_contribution is not None:
            raise ValueError("已发布任务不能原地修改预览质量贡献。")
        archive_fields = {"archived_at", "archived_by", "updated_at"}
        if any(key not in archive_fields and value != getattr(job, key, None) for key, value in patch.items()):
            raise ValueError("已发布任务仅允许更新归档元数据，不能原地修改内容或交付状态。")
        # 已发布快照不再参与任何质量/复核重合成；合法归档只更新允许的 metadata。
        return dict(patch)
    if any(key in patch and patch[key] != getattr(job, key) for key in ("current_review_record_id", "current_review_binding", "review_sequence")):
        raise ValueError("正式复核引用和序号只能由复核追加端口维护。")
    updated = dict(patch)
    next_result = patch.get("result_file_id", job.result_file_id)
    if patch.get("retry_count", job.retry_count) != job.retry_count or (
        job.result_file_id is not None and next_result != job.result_file_id
    ):
        updated.update(initial_delivery_state(), word_preview_state=None, current_publication_id=None)
    else:
        updated = quality_patch(job, updated, contribution=preview_contribution,
                                page_quality_contribution=page_quality_contribution, base_quality_contribution=base_quality_contribution)
    if next_result != job.result_file_id and job.result_file_id is None:
        # 首次绑定保留本代质量结论，复核批准不能跨结果身份延续。
        updated.update(review_status="unreviewed", delivery_status="internal_draft")
    if "prepared_result" in patch:
        from app.domains.document_jobs.models import DocumentJobPreparedResult
        receipt = patch["prepared_result"]
        if isinstance(receipt, dict):
            receipt = DocumentJobPreparedResult.model_validate(receipt)
        if receipt_identity(job.model_copy(update={"prepared_result": receipt})) != receipt_identity(job):
            updated.update(review_status="unreviewed", delivery_status="internal_draft")
    if (updated.get("delivery_status", job.delivery_status) == "ready_to_publish"
            and updated.get("quality_status", job.quality_status) in {"pending", "blocked"}):
        # pending 仍可保留内部批准，但不再满足 ready 的质量前提；published 已在前面原样返回。
        updated["delivery_status"] = "internal_draft"
    if (updated.get("quality_status", job.quality_status) == "blocked"
            and job.review_status == "approved" and "review_status" not in updated):
        updated.update(review_status="unreviewed", delivery_status="internal_draft")
    if updated.get("review_status", job.review_status) != job.review_status or (updated.get("review_status") == "unreviewed" and job.current_review_record_id is not None):
        updated.update(current_review_record_id=None, current_review_binding=None)
    return updated


def translation_qa_projection(job: DocumentJobRecord) -> dict[str, Any]:
    """旧响应仅投影当前复核；历史磁盘 QA 原值不作为新批准证据。"""
    current = job.review_status != "unreviewed" and job.translation_qa_status == job.review_status
    return {
        "translation_qa_status": job.review_status,
        "translation_qa_issue_type": job.translation_qa_issue_type if current else None,
        "translation_qa_note": job.translation_qa_note if current else None,
        "translation_qa_reviewed_by": job.translation_qa_reviewed_by if current else None,
        "translation_qa_reviewed_at": job.translation_qa_reviewed_at if current else None,
    }


def backfill_document_job_state_payload(payload: Any) -> dict[str, Any]:
    """仅补四个缺键，保留旧 QA、时间戳和未知 raw 键；非法现值显式失败。"""
    if not isinstance(payload, dict):
        raise ValueError("文档任务 payload 必须是 JSON 对象。")
    updated = {**initial_delivery_state(), **payload}
    DocumentJobRecord.model_validate(updated)
    return updated


def document_job_state_columns(job: DocumentJobRecord) -> tuple[str, str, str, str]:
    """SQL 列是同一权威 payload 的投影，摘要仅在此编码为 JSON 文本。"""
    return (job.quality_status, job.review_status, job.delivery_status,
            json.dumps(job.quality_summary, ensure_ascii=False))

