from __future__ import annotations

# app/domains/translation/profiles_service.py: 编排 Translation Profile 草稿、发布版本和默认指针。

import hashlib
import json
import re
from datetime import timedelta, timezone
from typing import Any

from app.conversion.runtime import llm_client, translation_runtime
from app.domains.audit.models import ActorContext
from app.core.config import Settings
from app.domains.resources.models import ResourceVersionRecord, utc_now
from app.domains.translation.models import TranslationProfileSnapshot
from app.domains.translation.schemas import (
    TranslationProfileDetailResponse,
    TranslationProfileDraftResponse,
    TranslationProfileDraftUpdateRequest,
    TranslationProfileListItemResponse,
    TranslationProfileListResponse,
    TranslationProfileVersionResponse,
)
from app.domains.resources.service import ResourceVersionService


DEFAULT_TRANSLATION_PROFILE_ID = "electronics-en2zh"
DRAFT_VERSION = "draft"
TRANSLATION_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
SHANGHAI_TZ = timezone(timedelta(hours=8))


class TranslationProfileVersionService:
    """管理单实例 Translation Profile 的草稿、发布版本和默认指针。"""

    def __init__(
        self,
        settings: Settings,
        resource_version_service: ResourceVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.resource_version_service = resource_version_service
        self.audit_service = audit_service

    def list_profiles(self) -> TranslationProfileListResponse:
        """列出当前支持的 Translation Profile；MVP 只内置 electronics-en2zh。"""

        default_record = self._default_record(DEFAULT_TRANSLATION_PROFILE_ID)
        version_records = self._version_records(DEFAULT_TRANSLATION_PROFILE_ID)
        payload = default_record.payload if default_record is not None else self._default_payload(DEFAULT_TRANSLATION_PROFILE_ID)
        return TranslationProfileListResponse(
            items=[
                TranslationProfileListItemResponse(
                    id=DEFAULT_TRANSLATION_PROFILE_ID,
                    default_version=default_record.version if default_record is not None else None,
                    version_count=len(version_records),
                    target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
                    domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
                    prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
                    model=self._payload_text(payload, "model"),
                    max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
                    max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
                )
            ]
        )

    def get_profile_detail(self, translation_profile_id: str) -> TranslationProfileDetailResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        default_record = self._default_record(normalized_id)
        return TranslationProfileDetailResponse(
            id=normalized_id,
            default_version=default_record.version if default_record is not None else None,
            versions=[self._version_response(record, default_record=default_record) for record in self._version_records(normalized_id)],
        )

    def get_draft(self, translation_profile_id: str) -> TranslationProfileDraftResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        record = self._ensure_draft_record(normalized_id)
        return self._draft_response(record)

    def update_draft(
        self,
        translation_profile_id: str,
        request: TranslationProfileDraftUpdateRequest,
    ) -> TranslationProfileDraftResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        existing = self.resource_version_service.repository.get_resource_version(
            "translation_profile",
            normalized_id,
            DRAFT_VERSION,
        )
        base_version = self._payload_text(existing.payload if existing is not None else None, "base_version")
        if base_version is None:
            default_record = self._default_record(normalized_id)
            base_version = default_record.version if default_record is not None else None
        payload = self._build_payload(
            translation_profile_id=normalized_id,
            version=DRAFT_VERSION,
            base_version=base_version,
            target_language=request.target_language,
            domain=request.domain,
            prompt_version=request.prompt_version,
            model=request.model,
            max_pages_per_batch=request.max_pages_per_batch,
            max_chars_per_batch=request.max_chars_per_batch,
        )
        record = self.resource_version_service.create_or_update_draft(
            resource_type="translation_profile",
            resource_id=normalized_id,
            version=DRAFT_VERSION,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"translation_profile:{normalized_id}@{DRAFT_VERSION}",
            payload=payload,
        )
        return self._draft_response(record)

    def publish_draft(
        self,
        translation_profile_id: str,
        *,
        make_default: bool,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        draft = self._ensure_draft_record(normalized_id)
        version = self._next_version(normalized_id)
        payload = self._build_payload_from_record(
            draft,
            version=version,
            published_at=utc_now(),
        )
        self.resource_version_service.create_or_update_draft(
            resource_type="translation_profile",
            resource_id=normalized_id,
            version=version,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"translation_profile:{normalized_id}@{version}",
            payload=payload,
        )
        record = self.resource_version_service.publish(
            "translation_profile",
            normalized_id,
            version,
            make_default=make_default,
        )
        self._record_audit(
            actor=actor,
            action="translation_profile.publish",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def set_default_version(
        self,
        translation_profile_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        self.resource_version_service.set_default("translation_profile", normalized_id, version)
        record = self._require_version_record(normalized_id, version)
        self._record_audit(
            actor=actor,
            action="translation_profile.set_default",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def rollback(
        self,
        translation_profile_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        self.resource_version_service.rollback_default("translation_profile", normalized_id, version)
        record = self._require_version_record(normalized_id, version)
        self._record_audit(
            actor=actor,
            action="translation_profile.rollback",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def resolve_default_snapshot(self) -> TranslationProfileSnapshot | None:
        """返回当前默认已发布 Translation Profile；未发布时让调用方回退 settings。"""

        record = self._default_record(DEFAULT_TRANSLATION_PROFILE_ID)
        if record is None:
            return None
        payload = record.payload or {}
        return TranslationProfileSnapshot(
            translation_profile_id=record.resource_id,
            version=record.version,
            snapshot_hash=record.snapshot_hash,
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
        )

    def _ensure_draft_record(self, translation_profile_id: str) -> ResourceVersionRecord:
        existing = self.resource_version_service.repository.get_resource_version(
            "translation_profile",
            translation_profile_id,
            DRAFT_VERSION,
        )
        if existing is not None:
            return existing

        default_record = self._default_record(translation_profile_id)
        if default_record is not None:
            payload = self._build_payload_from_record(default_record, version=DRAFT_VERSION, base_version=default_record.version)
        else:
            payload = self._default_payload(translation_profile_id)
        return self.resource_version_service.create_or_update_draft(
            resource_type="translation_profile",
            resource_id=translation_profile_id,
            version=DRAFT_VERSION,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"translation_profile:{translation_profile_id}@{DRAFT_VERSION}",
            payload=payload,
        )

    def _default_payload(self, translation_profile_id: str) -> dict[str, Any]:
        return self._build_payload(
            translation_profile_id=translation_profile_id,
            version=DRAFT_VERSION,
            base_version=None,
            target_language=translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self.settings.openai_model or llm_client.DEFAULT_MODEL,
            max_pages_per_batch=self.settings.translation_max_pages,
            max_chars_per_batch=self.settings.translation_max_chars,
        )

    def _version_records(self, translation_profile_id: str) -> list[ResourceVersionRecord]:
        return [
            record
            for record in self.resource_version_service.repository.list_resource_versions(
                "translation_profile",
                translation_profile_id,
            )
            if record.version != DRAFT_VERSION
        ]

    def _default_record(self, translation_profile_id: str) -> ResourceVersionRecord | None:
        return self.resource_version_service.repository.get_default_resource_version("translation_profile", translation_profile_id)

    def _require_version_record(self, translation_profile_id: str, version: str) -> ResourceVersionRecord:
        record = self.resource_version_service.repository.get_resource_version("translation_profile", translation_profile_id, version)
        if record is None:
            raise FileNotFoundError(f"Translation Profile 版本不存在: {translation_profile_id}@{version}")
        return record

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        target_id: str,
        trace_id: str | None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="translation_profile",
            target_id=target_id,
            trace_id=trace_id or "",
        )

    def _build_payload_from_record(
        self,
        record: ResourceVersionRecord,
        *,
        version: str,
        base_version: str | None = None,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        payload = record.payload or {}
        return self._build_payload(
            translation_profile_id=record.resource_id,
            version=version,
            base_version=base_version if base_version is not None else self._payload_text(payload, "base_version"),
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
            published_at=published_at,
        )

    def _build_payload(
        self,
        *,
        translation_profile_id: str,
        version: str,
        base_version: str | None,
        target_language: str,
        domain: str,
        prompt_version: str,
        model: str | None,
        max_pages_per_batch: int,
        max_chars_per_batch: int,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        return {
            "translation_profile_id": translation_profile_id,
            "version": version,
            "base_version": base_version,
            "target_language": self._normalize_required_text(target_language, "target_language"),
            "domain": self._normalize_required_text(domain, "domain"),
            "prompt_version": self._normalize_required_text(prompt_version, "prompt_version"),
            "model": self._normalize_optional_text(model),
            "max_pages_per_batch": max(int(max_pages_per_batch), 1),
            "max_chars_per_batch": max(int(max_chars_per_batch), 1),
            "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else published_at,
        }

    def _draft_response(self, record: ResourceVersionRecord) -> TranslationProfileDraftResponse:
        payload = record.payload or {}
        return TranslationProfileDraftResponse(
            translation_profile_id=record.resource_id,
            base_version=self._payload_text(payload, "base_version"),
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
            snapshot_hash=record.snapshot_hash,
        )

    def _version_response(
        self,
        record: ResourceVersionRecord,
        *,
        default_record: ResourceVersionRecord | None = None,
    ) -> TranslationProfileVersionResponse:
        payload = record.payload or {}
        default = default_record if default_record is not None else self._default_record(record.resource_id)
        return TranslationProfileVersionResponse(
            translation_profile_id=record.resource_id,
            version=record.version,
            status=record.status.value,
            snapshot_hash=record.snapshot_hash,
            is_default=default is not None and default.version == record.version,
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
            published_at=self._payload_text(payload, "published_at"),
        )

    def _next_version(self, translation_profile_id: str) -> str:
        prefix = utc_now().astimezone(SHANGHAI_TZ).strftime("%Y.%m.%d-")
        max_suffix = 0
        for record in self.resource_version_service.repository.list_resource_versions("translation_profile", translation_profile_id):
            if not record.version.startswith(prefix):
                continue
            suffix = record.version.removeprefix(prefix)
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
        return f"{prefix}{max_suffix + 1}"

    @staticmethod
    def _snapshot_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _payload_text(payload: dict[str, Any] | None, key: str) -> str | None:
        value = payload.get(key) if payload is not None else None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _payload_int(payload: dict[str, Any], key: str, default: int) -> int:
        value = payload.get(key)
        return int(value) if isinstance(value, (int, str)) and str(value).isdigit() else max(int(default), 1)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空。")
        return normalized

    @staticmethod
    def _require_known_profile_id(translation_profile_id: str) -> str:
        normalized = translation_profile_id.strip()
        if not TRANSLATION_PROFILE_ID_RE.match(normalized):
            raise ValueError("translation_profile_id 只能包含大小写字母、数字、下划线、短横线和英文句点，长度不超过 128。")
        if normalized != DEFAULT_TRANSLATION_PROFILE_ID:
            raise FileNotFoundError(f"Translation Profile 不存在: {normalized}")
        return normalized
