from __future__ import annotations

# File: app/domains/translation/provider_config_schemas.py
# Purpose: Define admin-facing AI provider configuration API contracts.

from typing import Literal

from pydantic import BaseModel, Field


AiProviderBackend = Literal["disabled", "openai_compatible"]


class AiProviderConfigResponse(BaseModel):
    backend: AiProviderBackend
    base_url: str | None = None
    model: str
    timeout_seconds: float
    max_output_tokens: int
    api_key_configured: bool = False
    api_key_mask: str | None = None
    source: Literal["settings", "runtime_config"]
    updated_at: str | None = None
    updated_by: str | None = None


class AiProviderConfigUpdateRequest(BaseModel):
    backend: AiProviderBackend
    base_url: str | None = None
    model: str | None = Field(default=None, max_length=128)
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    max_output_tokens: int | None = Field(default=None, ge=1, le=200000)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
