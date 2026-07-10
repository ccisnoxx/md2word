"""读取并更新 MinerU API 密钥的应用私有运行时配置。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.core.config import Settings
from app.domains.resources.models import utc_now


MinerUApiToken = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
]
MinerUConfigSource = Literal["settings", "runtime_config"]


class MinerUConfigError(RuntimeError):
    """运行时配置文件存在但不可读取或不符合合同。"""


class MinerUConfigWriteError(RuntimeError):
    """运行时配置文件无法安全写入。"""


class MinerUConfigRecord(BaseModel):
    """配置中心写入磁盘的唯一 MinerU 密钥记录。"""

    model_config = ConfigDict(extra="forbid")

    api_token: MinerUApiToken
    updated_at: datetime
    updated_by: str = Field(min_length=1, max_length=256)


@dataclass(frozen=True, slots=True)
class EffectiveMinerUConfig:
    """合并运行时文件与启动配置后的 MinerU 密钥状态。"""

    api_token: str | None
    source: MinerUConfigSource
    updated_at: datetime | None = None
    updated_by: str | None = None

    @property
    def api_token_configured(self) -> bool:
        """返回当前是否存在可用于新请求的 MinerU API 密钥。"""

        return bool(self.api_token)


class MinerUConfigService:
    """以共享私有文件为权威来源，按请求解析 MinerU 密钥。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.config_path = settings.mineru_config_file

    def get_record(self) -> MinerUConfigRecord | None:
        """读取配置中心记录；文件不存在表示尚未接管环境变量。"""

        try:
            raw_payload = self.config_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            if self.config_path.is_symlink():
                raise MinerUConfigError("MinerU 运行时配置文件不可读取或格式非法。") from exc
            return None
        except OSError as exc:
            raise MinerUConfigError("MinerU 运行时配置文件不可读取或格式非法。") from exc
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise MinerUConfigError("MinerU 运行时配置文件不可读取或格式非法。") from exc
        if not isinstance(payload, dict):
            raise MinerUConfigError("MinerU 运行时配置文件必须是 JSON 对象。")
        try:
            return MinerUConfigRecord.model_validate(payload)
        except ValidationError as exc:
            raise MinerUConfigError("MinerU 运行时配置文件字段不符合合同。") from exc

    def get_effective_config(self) -> EffectiveMinerUConfig:
        """返回有效配置；只有运行时文件不存在时才读取环境变量。"""

        record = self.get_record()
        if record is not None:
            return EffectiveMinerUConfig(
                api_token=record.api_token,
                source="runtime_config",
                updated_at=record.updated_at,
                updated_by=record.updated_by,
            )
        api_token = self.settings.mineru_api_token.strip() or None
        return EffectiveMinerUConfig(api_token=api_token, source="settings")

    def update_api_token(self, *, api_token: str, updated_by: str) -> EffectiveMinerUConfig:
        """用非空密钥覆盖运行时记录，不读取或保存历史值。"""

        record = MinerUConfigRecord(
            api_token=api_token,
            updated_at=utc_now(),
            updated_by=updated_by,
        )
        self._write_record(record)
        return EffectiveMinerUConfig(
            api_token=record.api_token,
            source="runtime_config",
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def _write_record(self, record: MinerUConfigRecord) -> None:
        """在目标目录原子替换私有配置，避免留下半写入文件。"""

        temp_path: Path | None = None
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.config_path.parent,
                prefix=".mineru_config.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                temp_path = Path(handle.name)
            self._restrict_permissions(temp_path)
            temp_path.replace(self.config_path)
            temp_path = None
            self._restrict_permissions(self.config_path)
        except OSError as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise MinerUConfigWriteError("MinerU 运行时配置文件写入失败。") from exc

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        """在支持 POSIX 权限的平台上限制配置文件仅当前用户可读写。"""

        try:
            path.chmod(0o600)
        except OSError:
            return
