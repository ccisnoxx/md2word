"""质量贡献的唯一合成规则；未知基础结论不从历史 QA 猜测。"""

from copy import deepcopy
from typing import Any

QUALITY_STATES = {"pending", "passed", "warning", "blocked"}


def _checks(summary: dict) -> dict:
    checks = summary.get("checks_v1", {})
    if not isinstance(checks, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict) or value.get("quality_status") not in QUALITY_STATES
        for key, value in checks.items()
    ):
        raise ValueError("质量贡献结构无效，不能覆盖未知检查。")
    return deepcopy(checks)


def effective_quality_status(job: Any) -> str:
    """未知或非法 base 在读副本和资格判断中保守解释；不改原槽或已发布快照。"""
    from app.domains.document_jobs.base_quality import unknown_base_status
    if job.delivery_status == "published":
        return job.quality_status
    checks = job.quality_summary.get("checks_v1", {})
    if not isinstance(checks, dict):
        _checks(job.quality_summary)
    if "document_base" not in checks:
        return job.quality_status
    # 已存在的 null/非对象槽沿原结构合同拒绝，不能与 legacy 无槽混为一谈。
    checks = _checks(job.quality_summary)
    unknown = unknown_base_status(checks["document_base"], generation=job.retry_count)
    if unknown is None:
        return job.quality_status
    states = {job.quality_status, unknown}
    states.update(value["quality_status"] for name, value in checks.items() if name != "document_base")
    return next(state for state in ("blocked", "pending", "warning", "passed") if state in states)


def quality_patch(job: Any, patch: dict, *, contribution: dict | None = None,
                  page_quality_contribution: dict | None = None, base_quality_contribution: dict | None = None) -> dict:
    """普通写入只能更新未归属贡献；内部 CAS 分别提交各自 producer。"""
    updated = dict(patch)
    checks = _checks(job.quality_summary)
    summary = deepcopy(patch.get("quality_summary", job.quality_summary))
    if not isinstance(summary, dict):
        raise ValueError("质量摘要必须为对象。")
    if summary.get("checks_v1", {}) != checks:
        raise ValueError("通用摘要更新不能修改或删除质量贡献。")
    if contribution is None and page_quality_contribution is None and base_quality_contribution is None and not checks:
        return updated
    represented = {entry["quality_status"] for entry in checks.values()}
    aggregate = next((state for state in ("blocked", "pending", "warning", "passed") if state in represented), None)
    from app.domains.document_jobs.base_quality import unknown_base_status
    unknown = (unknown_base_status(checks["document_base"], generation=job.retry_count)
               if "document_base" in checks else None)
    interpreted = next((state for state in ("blocked", "pending", "warning", "passed")
        if state in represented or state == unknown), None)
    if not checks or job.quality_status not in {aggregate, interpreted}:
        # 仅捕获尚未归属的旧结论；未知 base 派生的 pending 已由本槽解释，不能永久反灌。
        checks["__unattributed__"] = {"quality_status": job.quality_status}
    if "quality_status" in patch:
        # 显式同值 blocked 也是新贡献，普通 progress/receipt 补丁不会进入这里。
        checks["__unattributed__"] = {"quality_status": patch["quality_status"]}
    if contribution is not None:
        if contribution.get("quality_status") not in QUALITY_STATES:
            raise ValueError("预览质量贡献状态无效。")
        checks["word_preview"] = deepcopy(contribution)
    if page_quality_contribution is not None:
        if page_quality_contribution.get("quality_status") not in QUALITY_STATES:
            raise ValueError("页面质量贡献状态无效。")
        checks["word_page_quality"] = deepcopy(page_quality_contribution)
    if base_quality_contribution is not None:
        from app.domains.document_jobs.base_quality import BaseQualityContribution, current_base
        checked = BaseQualityContribution.model_validate(base_quality_contribution)
        if current_base(job) is None or checked.generation != job.retry_count:
            raise ValueError("基础质量贡献只能完成自己的本代命名槽。")
        checks["document_base"] = checked.model_dump(mode="json")
    summary["checks_v1"] = checks
    states = {entry["quality_status"] for entry in checks.values()}
    unknown = (unknown_base_status(checks["document_base"], generation=job.retry_count)
               if "document_base" in checks else None)
    if unknown is not None:
        states.add(unknown)
    updated.update(quality_summary=summary,
                   quality_status=next(state for state in ("blocked", "pending", "warning", "passed") if state in states))
    return updated
