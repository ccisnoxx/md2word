"""任务创建配置摘要的用例输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentJobConfigVersionOption(BaseModel):
    """任务创建配置中一个可绑定的 published 资源版本。"""

    resource_id: str
    version: str
    label: str
    status: str = "published"
    is_default: bool = False
    snapshot_hash: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class DocumentJobConfigDefaults(BaseModel):
    template: DocumentJobConfigVersionOption | None = None
    term_rule_set: DocumentJobConfigVersionOption | None = None
    translation_term_set: DocumentJobConfigVersionOption | None = None
    translation_profile: DocumentJobConfigVersionOption | None = None


class DocumentJobTranslationResourceDefaults(BaseModel):
    """Default translation resources for one supported language pair."""

    translation_term_set: DocumentJobConfigVersionOption | None = None
    translation_profile: DocumentJobConfigVersionOption | None = None


class DocumentJobConfigOptions(BaseModel):
    templates: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    term_rule_sets: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    translation_term_sets: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    translation_profiles: list[DocumentJobConfigVersionOption] = Field(default_factory=list)


class DocumentJobConfigReadiness(BaseModel):
    en2zh_available: bool = False
    ru2zh_available: bool = False
    translation_modes: dict[str, bool] = Field(default_factory=dict)
    p0_document_jobs_required: bool = False
    p0_document_jobs_ready: bool = True
    document_jobs_worker_backend: str = "disabled"
    document_jobs_automatic_execution_enabled: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentJobConfigSummaryResponse(BaseModel):
    role: str
    resource_mode: Literal["legacy", "versioned"]
    defaults: DocumentJobConfigDefaults
    translation_defaults: dict[str, DocumentJobTranslationResourceDefaults] = Field(default_factory=dict)
    options: DocumentJobConfigOptions
    readiness: DocumentJobConfigReadiness
