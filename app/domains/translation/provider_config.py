from __future__ import annotations

# File: app/domains/translation/provider_config.py
# Purpose: Manage admin-owned runtime AI provider configuration without exposing secrets.

import json
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
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2)
        temp_path = self.config_path.with_suffix(f"{self.config_path.suffix}.tmp")
        temp_path.write_text(payload + "\n", encoding="utf-8")
        self._restrict_permissions(temp_path)
        temp_path.replace(self.config_path)
        self._restrict_permissions(self.config_path)

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        try:
            path.chmod(0o600)
        except OSError:
            return

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
