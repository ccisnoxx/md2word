"""资源版本 payload 和实物沿用的 SHA-256 格式。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


RENDER_RESOURCE_ERROR_CODES = frozenset({
    "resource_snapshot_invalid", "resource_snapshot_unavailable",
    "resource_snapshot_not_found", "resource_snapshot_missing_template",
    "resource_snapshot_missing_term_rule_set", "resource_snapshot_invalid_status",
    "resource_snapshot_hash_mismatch", "resource_snapshot_payload_hash_mismatch",
    "resource_snapshot_payload_missing", "resource_snapshot_template_version_mismatch",
    "resource_snapshot_file_unavailable", "resource_snapshot_materialization_failed",
    "template_docx_hash_mismatch", "template_layout_config_hash_mismatch", "term_rule_hash_mismatch",
    "term_rule_payload_invalid",
})


def content_sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def resource_payload_sha256(payload: dict[str, Any]) -> str:
    """使用现有资源版本的规范 JSON 编码计算身份。"""

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return content_sha256(encoded)
