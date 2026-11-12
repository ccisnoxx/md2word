"""临时下载令牌编解码：任务文件令牌与发布最终件令牌共用同一签名密钥。

令牌只证明“签发时已授权”；取件时调用方仍须按令牌声明重新校验文件合同。
各函数接收 settings 并在原有位置读取密钥：校验时先判定格式/过期再取密钥，密钥缺失（503）
不会掩盖非法令牌（403）。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.document_jobs.views.quality_review import QualityChecksum, QualityId
from app.domains.resources.models import utc_now


def download_token_secret(settings: Settings) -> str:
    secret = settings.auth_jwt_secret_key.strip()
    if not secret:
        raise ApplicationError(
            "service_unavailable",
            "AUTH_JWT_SECRET_KEY 未配置，无法生成临时下载链接。",
        )
    return secret


def build_file_download_token(
    settings: Settings,
    *,
    job_id: str,
    file_id: str,
    expires_at: datetime,
) -> str:
    secret = download_token_secret(settings)
    expires_ts = int(expires_at.timestamp())
    message = f"{job_id}:{file_id}:{expires_ts}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{file_id}.{expires_ts}.{signature}"


def verify_file_download_token(settings: Settings, *, job_id: str, token: str) -> str:
    """校验任务文件令牌并返回其中的 file_id。"""

    parts = token.split(".")
    if len(parts) != 3:
        raise ApplicationError("forbidden", "下载链接无效。")
    file_id, raw_expires_ts, signature = parts
    try:
        expires_ts = int(raw_expires_ts)
    except ValueError as exc:
        raise ApplicationError("forbidden", "下载链接无效。") from exc
    if expires_ts < int(utc_now().timestamp()):
        raise ApplicationError("forbidden", "下载链接已过期。")
    message = f"{job_id}:{file_id}:{expires_ts}"
    expected = hmac.new(
        download_token_secret(settings).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ApplicationError("forbidden", "下载链接无效。")
    return file_id


class PublicationDownloadClaims(BaseModel):
    """用途与版本参与签名；字段严格限制，不能复用内部草稿 token。"""
    model_config = ConfigDict(extra="forbid", strict=True)
    purpose: Literal["publication_download/v1"] = "publication_download/v1"
    job_id: QualityId
    publication_id: QualityId
    result_file_id: QualityId
    result_sha256: QualityChecksum
    expires_ts: StrictInt = Field(gt=0)


def build_publication_download_token(settings: Settings, claims: PublicationDownloadClaims) -> str:
    message = json.dumps(claims.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(message).decode("ascii").rstrip("=")
    signature = hmac.new(download_token_secret(settings).encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_publication_download_token(
    settings: Settings, *, job_id: str, publication_id: str, token: str,
) -> PublicationDownloadClaims:
    invalid = ApplicationError("forbidden", "最终件下载链接无效。", reason_code="publication_download_token_invalid")
    if len(token) > 2048:
        raise invalid
    try:
        encoded, signature = token.split(".")
        message = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        expected = hmac.new(download_token_secret(settings).encode("utf-8"), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise invalid
        claims = PublicationDownloadClaims.model_validate_json(message)
        if claims.job_id != job_id or claims.publication_id != publication_id:
            raise invalid
        canonical = build_publication_download_token(settings, claims)
        if not hmac.compare_digest(token, canonical):
            raise invalid
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise invalid from None
    if claims.expires_ts <= utc_now().timestamp():
        raise ApplicationError("forbidden", "最终件下载链接已过期。", reason_code="publication_download_token_expired")
    return claims
