"""交付状态的纯规则；记录序列化和文件可用性检查分别由仓储与服务负责。"""

from datetime import datetime
import json
from typing import Any

from app.domains.document_jobs.models import (
    DocumentJobRecord,
    DocumentJobReviewStatus,
    DocumentJobTranslationQaIssueType,
)


DOCUMENT_JOB_STATE_FIELDS = ("quality_status", "review_status", "delivery_status", "quality_summary")


def initial_delivery_state() -> dict[str, Any]:
    """新任务、换代和真正换件均不继承旧质量或复核证据。"""
    return {"quality_status": "pending", "review_status": "unreviewed",
            "delivery_status": "internal_draft", "quality_summary": {}}


def delivery_state_patch(job: DocumentJobRecord, patch: dict[str, Any]) -> dict[str, Any]:
    """在模型验证前处理证据失效；已发布记录先检查原值，不能先降级再改内容。"""
    if job.delivery_status == "published":
        archive_fields = {"archived_at", "archived_by", "updated_at"}
        if any(key not in archive_fields and value != getattr(job, key, None) for key, value in patch.items()):
            raise ValueError("已发布任务仅允许更新归档元数据，不能原地修改内容或交付状态。")
    updated = dict(patch)
    next_result = patch.get("result_file_id", job.result_file_id)
    if patch.get("retry_count", job.retry_count) != job.retry_count or (
        job.result_file_id is not None and next_result != job.result_file_id
    ):
        updated.update(initial_delivery_state())
    elif next_result != job.result_file_id:
        # 首次绑定保留本代质量结论，复核批准不能跨结果身份延续。
        updated.update(review_status="unreviewed", delivery_status="internal_draft")
    if (updated.get("quality_status", job.quality_status) == "blocked"
            and job.review_status == "approved" and "review_status" not in updated):
        updated.update(review_status="unreviewed", delivery_status="internal_draft")
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


def reviewed_job(
    job: DocumentJobRecord, *, expected_retry_count: int, expected_result_file_id: str | None,
    review_status: DocumentJobReviewStatus, issue_type: DocumentJobTranslationQaIssueType | None,
    note: str | None, reviewed_by: str | None, reviewed_at: datetime | None, updated_at: datetime,
) -> DocumentJobRecord | None:
    """锁内复核 CAS；None 结果也是比较值，不承担文件 I/O 或跨仓储事务。"""
    if (job.retry_count != expected_retry_count or job.result_file_id != expected_result_file_id
            or job.deleted_at is not None or job.delivery_status == "published"):
        return None
    if review_status == "approved" and (
        job.status != "succeeded" or not job.result_file_id or job.quality_status == "blocked"
    ):
        return None
    unreviewed = review_status == "unreviewed"
    patch = {
        "review_status": review_status,
        "translation_qa_status": review_status,
        "translation_qa_issue_type": None if unreviewed else issue_type,
        "translation_qa_note": None if unreviewed else note,
        "translation_qa_reviewed_by": None if unreviewed else reviewed_by,
        "translation_qa_reviewed_at": None if unreviewed else reviewed_at,
        "updated_at": updated_at,
    }
    if review_status != "approved":
        patch["delivery_status"] = "internal_draft"
    return DocumentJobRecord.model_validate(job.model_copy(update=patch).model_dump(mode="python"))


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

