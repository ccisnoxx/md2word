from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlparse


def validate_mineru_result_url(full_zip_url: str, allowed_hosts: Sequence[str]) -> None:
    parsed = urlparse(full_zip_url)
    if parsed.scheme.lower() != "https":
        raise ValueError("MinerU 结果地址必须使用 https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("MinerU 结果地址缺少 host")
    normalized_allowed_hosts = tuple(str(item).strip().lower() for item in allowed_hosts if str(item).strip())
    if not normalized_allowed_hosts:
        raise ValueError("未配置允许的 MinerU 结果地址 host")
    if any(host == allowed or host.endswith(f".{allowed}") for allowed in normalized_allowed_hosts):
        return
    raise ValueError(f"MinerU 结果地址 host 不在允许名单中: {host}")
