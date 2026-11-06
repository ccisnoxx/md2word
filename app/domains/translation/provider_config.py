from __future__ import annotations

# File: app/domains/translation/provider_config.py
# Purpose: Manage admin-owned runtime AI provider configuration without exposing secrets.

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.domains.resources.models import utc_now


AiProviderBackend = Literal["disabled", "openai_compatible"]
AiProviderConfigSource = Literal["settings", "runtime_config"]


class AiProviderConfigRecord(BaseModel):
    """Persisted runtime AI provider overrides; API keys are never returned by routers."""

    backend: AiProviderBackend | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    updated_at: str | None = None
    updated_by: str | None = None


@dataclass(frozen=True, slots=True)
class EffectiveAiProviderConfig:
    """Effective provider configuration after merging runtime overrides over Settings."""

    backend: AiProviderBackend
    base_url: str | None
    api_key: str | None
    model: str
    timeout_seconds: float
    max_output_tokens: int
    source: AiProviderConfigSource
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)


class AiProviderConfigService:
    """Read and update runtime AI provider settings from a local config file."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.config_path = settings.ai_provider_config_file

    def get_record(self) -> AiProviderConfigRecord | None:
        """Return persisted overrides, or None when the admin has not configured AI in UI."""

        if not self.config_path.exists():
            return None
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI provider config is not readable JSON: {self.config_path}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"AI provider config must be a JSON object: {self.config_path}")
        try:
            return AiProviderConfigRecord.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"AI provider config is invalid: {self.config_path}") from exc

    def get_effective_config(self) -> EffectiveAiProviderConfig:
        """Merge runtime overrides with environment Settings for provider calls and health checks."""

        record = self.get_record()
        return self._effective_from_record(record)

    def update_config(
        self,
        *,
        backend: AiProviderBackend,
        base_url: str | None,
        model: str | None,
        timeout_seconds: float | None,
        max_output_tokens: int | None,
        api_key: str | None,
        clear_api_key: bool,
        api_key_supplied: bool,
        updated_by: str,
    ) -> EffectiveAiProviderConfig:
        """Persist sanitized runtime overrides; omitted api_key keeps the previous runtime secret."""

        existing = self.get_record()
        normalized_api_key = self._normalize_optional(api_key) if api_key_supplied else None
        if clear_api_key:
            next_api_key = None
        elif api_key_supplied:
            next_api_key = normalized_api_key
        elif existing is not None:
            next_api_key = existing.api_key
        else:
            next_api_key = None

        record = AiProviderConfigRecord(
            backend=backend,
            base_url=self._normalize_optional(base_url),
            api_key=next_api_key,
            model=self._normalize_optional(model),
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            updated_at=utc_now().isoformat(),
            updated_by=updated_by,
        )
        self._write_record(record)
        return self._effective_from_record(record)

    def _effective_from_record(self, record: AiProviderConfigRecord | None) -> EffectiveAiProviderConfig:
        source: AiProviderConfigSource = "runtime_config" if record is not None else "settings"
        backend = record.backend if record is not None and record.backend is not None else self.settings.translation_provider_backend
        base_url = (
            self._normalize_optional(record.base_url)
            if record is not None and record.base_url is not None
            else self._normalize_optional(self.settings.openai_base_url)
        )
        api_key = (
            self._normalize_optional(record.api_key)
            if record is not None and record.api_key is not None
            else self._normalize_optional(self.settings.openai_api_key)
        )
        model = (
            self._normalize_optional(record.model)
            if record is not None and record.model is not None
            else self._normalize_optional(self.settings.openai_model)
        ) or "deepseek-v4-flash"
        timeout_seconds = (
            record.timeout_seconds
            if record is not None and record.timeout_seconds is not None
            else self.settings.translation_provider_timeout_seconds
        )
        max_output_tokens = (
            record.max_output_tokens
            if record is not None and record.max_output_tokens is not None
            else self.settings.translation_provider_max_output_tokens
        )
        return EffectiveAiProviderConfig(
            backend=backend,
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            source=source,
            updated_at=record.updated_at if record is not None else None,
            updated_by=record.updated_by if record is not None else None,
        )

    def _write_record(self, record: AiProviderConfigRecord) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2)
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # 唯一名称的排他创建避开历史残留，也不跟随残留符号链接。
            descriptor, temp_name = tempfile.mkstemp(
                dir=self.config_path.parent, prefix=f"{self.config_path.name}.", suffix=".tmp"
            )
        except OSError as exc:
            raise OSError("无法创建 AI Provider 配置临时文件。") from exc

        temp_path = Path(temp_name)
        try:
            try:
                self._restrict_permissions(descriptor)
                with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as stream:
                    stream.write(payload + "\n")
            finally:
                os.close(descriptor)
            # 替换保留已确认的 inode 权限，不在覆盖旧配置后执行可能失败的权限操作。
            temp_path.replace(self.config_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _restrict_permissions(descriptor: int) -> None:
        try:
            os.fchmod(descriptor, 0o600)
            mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
        except OSError as exc:
            raise OSError("无法设置或确认 AI Provider 配置文件权限为 0600。") from exc
        if mode != 0o600:
            raise OSError("AI Provider 配置文件权限必须为 0600，已停止写入。")

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
