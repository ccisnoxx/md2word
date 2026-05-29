from __future__ import annotations

# app/api/v1/routers/term_rule_write_guard.py: 阻止版本化模式下 legacy term-rules 写入口绕过发布流程。

from fastapi import HTTPException, status

from app.core.runtime import AppRuntime


def ensure_legacy_term_rule_write_allowed(runtime: AppRuntime) -> None:
    """MySQL 资源版本模式下，术语写入必须走 Term Rule Set 草稿/发布流程。"""

    if runtime.term_rule_set_version_service is None:
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="术语规则版本化已启用，请使用 /api/v1/term-rule-sets/{set_id}/draft/rules 更新草稿后发布。",
    )
