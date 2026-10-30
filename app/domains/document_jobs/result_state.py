"""三个主记录 adapter 共用的纯结果条件；序列化由各 adapter 提供。"""

from datetime import datetime
from typing import Any, Literal

from app.domains.document_jobs.base_quality import current_base, derive_base_quality, fresh_quality_summary
from app.domains.document_jobs.delivery_state import delivery_state_patch
from app.domains.document_jobs.models import DocumentJobPreparedResult, DocumentJobRecord
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.services.renderer.docx_quality import validate_formula_report
from app.services.renderer.evidence import ensure_renderer_integrity


def matches_current(
    job: DocumentJobRecord, *, allowed_statuses: set[str], allowed_stages: set[str],
    expected_retry_count: int | None = None, expected_document_ir_file_id: str | None = None,
    require_no_prepared_result: bool = False, expected_prepared_result_file_id: str | None = None,
) -> bool:
    if require_no_prepared_result and expected_prepared_result_file_id is not None:
        raise ValueError("结果空槽条件不能与凭据 ID 条件并用。")
    if job.status in {"succeeded", "failed", "canceled"} or job.deleted_at is not None or job.archived_at is not None:
        return False
    return (
        job.status in allowed_statuses and job.stage in allowed_stages
        and (expected_retry_count is None or job.retry_count == expected_retry_count)
        and (expected_document_ir_file_id is None or job.document_ir_file_id == expected_document_ir_file_id)
        and (not require_no_prepared_result or job.prepared_result is None)
        and (expected_prepared_result_file_id is None or (
            job.prepared_result is not None and job.prepared_result.file.id == expected_prepared_result_file_id
        ))
    )


def lifecycle_job(
    job: DocumentJobRecord, *, expected_retry_count: int, action: Literal["archive", "delete"],
    actor_id: str, occurred_at: datetime, delete_reason: str | None = None,
) -> DocumentJobRecord | None:
    """在原 job 串行点预留生命周期变更；只改元数据，不重新合成冻结质量。"""

    if (job.retry_count != expected_retry_count or job.status not in {"succeeded", "failed", "canceled"}
            or job.deleted_at is not None):
        return None
    if action == "archive":
        if job.archived_at is not None:
            return job
        patch = {"archived_at": occurred_at, "archived_by": actor_id, "updated_at": occurred_at}
    elif action == "delete":
        if job.delivery_status == "published" or job.current_publication_id is not None:
            return None
        # deleted_* 是既有持久预留；只有确认提交后，调用方才能开始物理删除。
        patch = {"deleted_at": occurred_at, "deleted_by": actor_id, "delete_reason": delete_reason,
            "updated_at": occurred_at}
    else:
        raise ValueError("文档任务生命周期动作必须为 archive 或 delete。")
    return DocumentJobRecord.model_validate({**job.model_dump(mode="python"), **patch})


def prepare_result(
    job: DocumentJobRecord, *, expected_retry_count: int,
    expected_document_ir_file_id: str, candidate: DocumentFileRecord,
) -> DocumentJobRecord | None:
    if not matches_current(job, allowed_statuses={"running"}, allowed_stages={"uploading"},
                           expected_retry_count=expected_retry_count,
                           expected_document_ir_file_id=expected_document_ir_file_id):
        return None
    now = utc_now()
    if job.timeout_at is not None and job.timeout_at <= now:
        return None
    # 已选定的身份优先；迟到候选不能替换凭据，也不参与物化。
    if job.prepared_result is not None:
        return job
    if (candidate.tenant_id, candidate.company_id, candidate.job_id) != (job.tenant_id, job.company_id, job.id):
        raise ValueError("候选结果与任务归属不一致。")
    if type(candidate.metadata.get("retry_count")) is not int or candidate.metadata["retry_count"] != job.retry_count:
        raise ValueError("候选结果缺少当前代身份。")
    if candidate.metadata.get("document_ir_file_id") != job.document_ir_file_id:
        raise ValueError("候选结果不属于当前最终 IR。")
    if candidate.expires_at is None or candidate.expires_at <= now:
        raise ValueError("候选结果已过期。")
    if (not isinstance(candidate.metadata.get("docx_quality"), dict)
            or not isinstance(candidate.metadata.get("source_integrity"), dict)
            or not isinstance(candidate.metadata.get("blocking_quality_flags"), list)):
        raise ValueError("候选结果缺少质量检查证据。")
    ensure_renderer_integrity(candidate.metadata)
    from app.domains.document_jobs.table_evidence import validate_candidate_binding
    validate_candidate_binding(job, candidate)
    receipt = DocumentJobPreparedResult(generation=job.retry_count,
                                      document_ir_file_id=expected_document_ir_file_id, file=candidate)
    return patched_job(job, {"prepared_result": receipt, "updated_at": now})


def patched_job(job: DocumentJobRecord, patch: dict[str, Any], *, preview_contribution: dict | None = None,
                page_quality_contribution: dict | None = None) -> DocumentJobRecord:
    if job.delivery_status == "published":
        patch = delivery_state_patch(job, patch, preview_contribution=preview_contribution,
                                     page_quality_contribution=page_quality_contribution)
        return DocumentJobRecord.model_validate(job.model_copy(update=patch).model_dump(mode="python"))
    receipt = job.prepared_result
    fresh = current_base(job) is not None
    base_owned = "document_base" in job.quality_summary.get("checks_v1", {})
    base_contribution = None
    if (patch.get("status") == "succeeded" and patch.get("stage") == "completed"
            and receipt is not None and receipt.generation == job.retry_count
            and receipt.document_ir_file_id == job.document_ir_file_id
            and patch.get("retry_count", job.retry_count) == receipt.generation
            and patch.get("document_ir_file_id", job.document_ir_file_id) == receipt.document_ir_file_id
            and patch.get("result_file_id") == receipt.file.id):
        # 只从锁内已选凭据投影摘要；迟到 renderer 的内存报告不能污染获胜结果。
        metadata = receipt.file.metadata
        if "formula_report" in metadata or "formula_summary" in metadata:
            summary = validate_formula_report(metadata.get("formula_report"))
            if summary != metadata.get("formula_summary"):
                raise ValueError("结果凭据的公式摘要与报告不一致。")
            patch = {**patch, "quality_summary": {**patch.get("quality_summary", job.quality_summary), "formula": summary}}
            # 预览blocked是聚合结果，不能在普通完成时重捕获为永久基础贡献。
            checks = job.quality_summary.get("checks_v1", {})
            base = checks.get("__unattributed__", {}).get("quality_status", job.quality_status)
            # completion不能用调用方的passed覆盖锁内既有基础结论。
            patch.pop("quality_status", None)
            if not base_owned and base == "passed" and summary["fallback_count"]:
                patch["quality_status"] = "warning"
        if fresh:
            patch.pop("quality_status", None)
            base_contribution = derive_base_quality(job)
    if (patch.get("status") == "succeeded" and job.prepared_result is not None
            and patch.get("result_file_id") == job.prepared_result.file.id):
        from app.domains.document_jobs.table_evidence import validate_candidate_binding
        binding = validate_candidate_binding(job, job.prepared_result.file)
        if binding is not None:
            descriptor, _, summary = binding
            # 锁外快照复查后仍可能等锁到期；锁内只使用凭据固化的绝对期限，不读文件仓储。
            now = utc_now()
            if (descriptor.preparation.docx_expires_at <= now or descriptor.preparation.report_expires_at <= now):
                from app.services.tables.evidence import TableEvidenceError
                raise TableEvidenceError("table_evidence_integrity")
            patch = {**patch, "quality_summary": {**patch.get("quality_summary", job.quality_summary), "table_evidence": summary}}
            # 只登记本报告的 blocker；现有聚合 blocked 可能来自可恢复的预览贡献。
            if not base_owned and summary["status"] == "blocked":
                patch["quality_status"] = "blocked"
        proof = job.prepared_result.file.metadata.get("table_placeholder_rendering")
        if proof is not None:
            from app.services.renderer.table_placeholder_evidence import valid_placeholder_evidence
            if not valid_placeholder_evidence(proof) or proof["docx_sha256"] != job.prepared_result.file.checksum_sha256:
                raise ValueError("表格占位结果凭据无效。")
            # 同一锁内基于最新质量摘要合并，只生产 blocker，不推导整任务通过。
            patch = {**patch, **({"quality_status": "blocked"} if not base_owned else {}), "quality_summary": {
                **patch.get("quality_summary", job.quality_summary), "table_placeholder": {
                    "version": proof["version"], "count": proof["count"], "issue_codes": proof["issue_codes"],
                    "ir_sha256": proof["ir_sha256"], "docx_sha256": proof["docx_sha256"],
                }}}
    patch = delivery_state_patch(job, patch, preview_contribution=preview_contribution,
                                     page_quality_contribution=page_quality_contribution,
                                     base_quality_contribution=base_contribution)
    result_stages = {"rendering", "quality_checking", "uploading", "completed"}
    if ("progress" in patch and patch.get("retry_count", job.retry_count) == job.retry_count
            and job.stage in result_stages and patch.get("stage", job.stage) in result_stages):
        # 同代恢复会重新经过 rendering；陈旧快照不能降低锁内最新记录的进度。
        patch = {**patch, "progress": max(job.progress, patch["progress"])}
    updated = DocumentJobRecord.model_validate(job.model_copy(update=patch).model_dump(mode="python"))
    # 主键也是三 adapter 的锁/寻址身份，不能在锁住原记录时改写另一条记录。
    if updated.id != job.id:
        raise ValueError("文档任务更新不允许改变 id。")
    return updated


def retry_job(job: DocumentJobRecord, *, expected_retry_count: int, max_retries: int, **patch: Any) -> DocumentJobRecord | None:
    if (job.status != "failed" or job.retry_count != expected_retry_count or job.retry_count >= max_retries
            or job.archived_at is not None or job.deleted_at is not None):
        return None
    if patch.get("retry_count") != expected_retry_count + 1 or patch.get("status") not in {"pending", "queued", "running"}:
        raise ValueError("重试必须原子进入下一代的可执行状态。")
    updated = patched_job(job, {**patch, "prepared_result": None})
    # failed retry 的胜出换代与 fresh marker 同次持久化；普通 patch/backfill 不走此入口。
    return updated.model_copy(update={"quality_summary": fresh_quality_summary(updated.retry_count)})
