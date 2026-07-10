"""定义管理员维护 MinerU 账号与密钥时使用的 API 合同。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.mineru.config import MinerUApiToken, MinerUConfigSource, MinerUUid


class MinerUConfigResponse(BaseModel):
    """不含 UID 或密钥字符的 MinerU 配置安全摘要。"""

    api_token_configured: bool
    uid_configured: bool
    source: MinerUConfigSource
    updated_at: datetime | None = None
    updated_by: str | None = None


class MinerUConfigUpdateRequest(BaseModel):
    """只允许用新的完整非空账号与密钥绑定覆盖当前配置。"""

    model_config = ConfigDict(extra="forbid")

    api_token: MinerUApiToken
    uid: MinerUUid
