"""定义管理员维护 MinerU 密钥时使用的 API 合同。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.mineru.config import MinerUApiToken, MinerUConfigSource


class MinerUConfigResponse(BaseModel):
    """不含密钥字符的 MinerU 配置安全摘要。"""

    api_token_configured: bool
    source: MinerUConfigSource
    updated_at: datetime | None = None
    updated_by: str | None = None


class MinerUConfigUpdateRequest(BaseModel):
    """只允许用新的非空密钥覆盖当前配置。"""

    model_config = ConfigDict(extra="forbid")

    api_token: MinerUApiToken
