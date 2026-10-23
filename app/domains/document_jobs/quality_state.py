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


def quality_patch(job: Any, patch: dict, *, contribution: dict | None = None) -> dict:
    """普通写入只能更新未归属贡献，内部预览 CAS 只能替换自己的贡献。"""
    updated = dict(patch)
    checks = _checks(job.quality_summary)
    summary = deepcopy(patch.get("quality_summary", job.quality_summary))
    if not isinstance(summary, dict):
        raise ValueError("质量摘要必须为对象。")
    if summary.get("checks_v1", {}) != checks:
        raise ValueError("通用摘要更新不能修改或删除质量贡献。")
    if contribution is None and not checks:
        return updated
    if not checks:
        checks["__unattributed__"] = {"quality_status": job.quality_status}
    if "quality_status" in patch:
        # 显式同值 blocked 也是新贡献，普通 progress/receipt 补丁不会进入这里。
        checks["__unattributed__"] = {"quality_status": patch["quality_status"]}
    if contribution is not None:
        if contribution.get("quality_status") not in QUALITY_STATES:
            raise ValueError("预览质量贡献状态无效。")
        checks["word_preview"] = deepcopy(contribution)
    summary["checks_v1"] = checks
    states = {entry["quality_status"] for entry in checks.values()}
    updated.update(quality_summary=summary,
                   quality_status=next(state for state in ("blocked", "pending", "warning", "passed") if state in states))
    return updated
