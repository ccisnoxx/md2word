from __future__ import annotations

# 回调预检与实际下载共用的 MinerU 结果地址策略。

from collections.abc import Sequence
from urllib.parse import urlparse


def validate_mineru_result_url(full_zip_url: str, allowed_hosts: Sequence[str]) -> None:
    try:
        parsed = urlparse(full_zip_url)
        host = (parsed.hostname or "").lower()
        # urlparse 延迟验证端口，必须在发送前触发检查。
        parsed.port
    except ValueError:
        raise ValueError("MinerU 结果地址格式无效") from None
    if parsed.scheme.lower() != "https":
        raise ValueError("MinerU 结果地址必须使用 https")
    if not host:
        raise ValueError("MinerU 结果地址缺少 host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("MinerU 结果地址不能包含用户名或密码")
    normalized_allowed_hosts = tuple(str(item).strip().lower() for item in allowed_hosts if str(item).strip())
    if not normalized_allowed_hosts:
        raise ValueError("未配置允许的 MinerU 结果地址 host")
    if any(host == allowed or host.endswith(f".{allowed}") for allowed in normalized_allowed_hosts):
        return
    raise ValueError("MinerU 结果地址 host 不在允许名单中")
