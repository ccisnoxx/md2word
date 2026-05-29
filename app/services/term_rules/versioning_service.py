from __future__ import annotations

# app/services/term_rules/versioning_service.py: 编排术语规则集草稿、发布版本和默认指针同步。

import hashlib
import json
import re
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.audit_models import ActorContext
from app.core.resource_models import ResourceVersionRecord, utc_now
from app.core.rule_models import TermRulesStore
from app.repositories.protocols import TermRuleRepositoryProtocol
from app.schemas.term_rules import (
    TermRuleSetDetailResponse,
    TermRuleSetDraftResponse,
    TermRuleSetListItemResponse,
    TermRuleSetListResponse,
    TermRuleSetVersionResponse,
)
from app.services.resource_versions import ResourceVersionService
from app.services.term_rules.yaml_codec import CURRENT_SCHEMA_VERSION, TermRuleYamlCodec


DEFAULT_TERM_RULE_SET_ID = "electronics-default"
DRAFT_VERSION = "draft"
TERM_RULE_SET_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
SHANGHAI_TZ = timezone(timedelta(hours=8))


class TermRuleSetVersionService:
    """管理单实例术语规则集的草稿、发布版本和 live runtime 同步。"""

    def __init__(
        self,
        *,
        repository: TermRuleRepositoryProtocol,
        runtime_yaml_path: Path,
        resource_version_service: ResourceVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.runtime_yaml_path = runtime_yaml_path
        self.resource_version_service = resource_version_service
        self.audit_service = audit_service
        self.yaml_codec = TermRuleYamlCodec()

    def list_sets(self) -> TermRuleSetListResponse:
        """列出当前支持的术语规则集；MVP 只内置 electronics-default。"""

        default_record = self._default_record(DEFAULT_TERM_RULE_SET_ID)
        version_records = self._version_records(DEFAULT_TERM_RULE_SET_ID)
        store = self._store_from_record(default_record) if default_record is not None else self.repository.load()
        rule_count, enabled_rule_count = self._count_rules(store)
        return TermRuleSetListResponse(
            items=[
                TermRuleSetListItemResponse(
                    id=DEFAULT_TERM_RULE_SET_ID,
                    default_version=default_record.version if default_record is not None else None,
                    version_count=len(version_records),
                    rule_count=rule_count,
                    enabled_rule_count=enabled_rule_count,
                )
            ]
        )

    def get_set_detail(self, term_rule_set_id: str) -> TermRuleSetDetailResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        default_record = self._default_record(normalized_id)
        return TermRuleSetDetailResponse(
            id=normalized_id,
            default_version=default_record.version if default_record is not None else None,
            versions=[self._version_response(record, default_record=default_record) for record in self._version_records(normalized_id)],
        )

    def get_draft(self, term_rule_set_id: str) -> TermRuleSetDraftResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        record = self._ensure_draft_record(normalized_id)
        return self._draft_response(record)

    def update_draft(self, term_rule_set_id: str, store: TermRulesStore) -> TermRuleSetDraftResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        existing = self.resource_version_service.repository.get_resource_version(
            "term_rule_set",
            normalized_id,
            DRAFT_VERSION,
        )
        base_version = self._payload_text(existing.payload if existing is not None else None, "base_version")
        if base_version is None:
            default_record = self._default_record(normalized_id)
            base_version = default_record.version if default_record is not None else None
        payload = self._build_payload(
            term_rule_set_id=normalized_id,
            version=DRAFT_VERSION,
            store=store,
            base_version=base_version,
        )
        record = self.resource_version_service.create_or_update_draft(
            resource_type="term_rule_set",
            resource_id=normalized_id,
            version=DRAFT_VERSION,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"term_rule_set:{normalized_id}@{DRAFT_VERSION}",
            payload=payload,
        )
        return self._draft_response(record)

    def publish_draft(
        self,
        term_rule_set_id: str,
        *,
        make_default: bool,
        published_by: str | None,
        publish_reason: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleSetVersionResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        draft = self._ensure_draft_record(normalized_id)
        store = self._store_from_record(draft)
        version = self._next_version(normalized_id)
        payload = self._build_payload(
            term_rule_set_id=normalized_id,
            version=version,
            store=store,
            base_version=self._payload_text(draft.payload, "base_version"),
            published_by=published_by,
            publish_reason=publish_reason,
            published_at=utc_now(),
        )
        self.resource_version_service.create_or_update_draft(
            resource_type="term_rule_set",
            resource_id=normalized_id,
            version=version,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"term_rule_set:{normalized_id}@{version}",
            payload=payload,
        )
        record = self.resource_version_service.publish(
            "term_rule_set",
            normalized_id,
            version,
            make_default=make_default,
        )
        if make_default:
            self._sync_live_store(record)
        self._record_audit(
            actor=actor,
            action="term_rule_set.publish",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
            reason=publish_reason,
        )
        return self._version_response(record)

    def set_default_version(
        self,
        term_rule_set_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleSetVersionResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        self.resource_version_service.set_default("term_rule_set", normalized_id, version)
        record = self._require_version_record(normalized_id, version)
        self._sync_live_store(record)
        self._record_audit(
            actor=actor,
            action="term_rule_set.set_default",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def rollback(
        self,
        term_rule_set_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleSetVersionResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        self.resource_version_service.rollback_default("term_rule_set", normalized_id, version)
        record = self._require_version_record(normalized_id, version)
        self._sync_live_store(record)
        self._record_audit(
            actor=actor,
            action="term_rule_set.rollback",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def _ensure_draft_record(self, term_rule_set_id: str) -> ResourceVersionRecord:
        existing = self.resource_version_service.repository.get_resource_version(
            "term_rule_set",
            term_rule_set_id,
            DRAFT_VERSION,
        )
        if existing is not None:
            return existing

        default_record = self._default_record(term_rule_set_id)
        if default_record is not None:
            store = self._store_from_record(default_record)
            base_version = default_record.version
        else:
            store = self.repository.load()
            base_version = None
        payload = self._build_payload(
            term_rule_set_id=term_rule_set_id,
            version=DRAFT_VERSION,
            store=store,
            base_version=base_version,
        )
        return self.resource_version_service.create_or_update_draft(
            resource_type="term_rule_set",
            resource_id=term_rule_set_id,
            version=DRAFT_VERSION,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"term_rule_set:{term_rule_set_id}@{DRAFT_VERSION}",
            payload=payload,
        )

    def _version_records(self, term_rule_set_id: str) -> list[ResourceVersionRecord]:
        return [
            record
            for record in self.resource_version_service.repository.list_resource_versions(
                "term_rule_set",
                term_rule_set_id,
            )
            if record.version != DRAFT_VERSION
        ]

    def _default_record(self, term_rule_set_id: str) -> ResourceVersionRecord | None:
        return self.resource_version_service.repository.get_default_resource_version("term_rule_set", term_rule_set_id)

    def _require_version_record(self, term_rule_set_id: str, version: str) -> ResourceVersionRecord:
        record = self.resource_version_service.repository.get_resource_version("term_rule_set", term_rule_set_id, version)
        if record is None:
            raise FileNotFoundError(f"术语规则版本不存在: {term_rule_set_id}@{version}")
        return record

    def _sync_live_store(self, record: ResourceVersionRecord) -> None:
        store = self._store_from_record(record)
        self.repository.save(store)
        self.runtime_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_yaml_path.write_text(self.yaml_codec.dump_legacy_runtime_yaml(store), encoding="utf-8")

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        target_id: str,
        trace_id: str | None,
        reason: str | None = None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="term_rule_set",
            target_id=target_id,
            trace_id=trace_id or "",
            reason=reason,
        )

    def _build_payload(
        self,
        *,
        term_rule_set_id: str,
        version: str,
        store: TermRulesStore,
        base_version: str | None,
        published_by: str | None = None,
        publish_reason: str | None = None,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        rule_count, enabled_rule_count = self._count_rules(store)
        return {
            "term_rule_set_id": term_rule_set_id,
            "version": version,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "base_version": base_version,
            "rule_count": rule_count,
            "enabled_rule_count": enabled_rule_count,
            "published_by": self._normalize_optional_text(published_by),
            "publish_reason": self._normalize_optional_text(publish_reason),
            "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else published_at,
            "store": store.model_dump(mode="json"),
        }

    def _draft_response(self, record: ResourceVersionRecord) -> TermRuleSetDraftResponse:
        store = self._store_from_record(record)
        rule_count, enabled_rule_count = self._count_rules(store)
        return TermRuleSetDraftResponse(
            term_rule_set_id=record.resource_id,
            base_version=self._payload_text(record.payload, "base_version"),
            rule_count=rule_count,
            enabled_rule_count=enabled_rule_count,
            yaml_text=self.yaml_codec.dump_store(store),
            snapshot_hash=record.snapshot_hash,
        )

    def _version_response(
        self,
        record: ResourceVersionRecord,
        *,
        default_record: ResourceVersionRecord | None = None,
    ) -> TermRuleSetVersionResponse:
        payload = record.payload or {}
        default = default_record if default_record is not None else self._default_record(record.resource_id)
        return TermRuleSetVersionResponse(
            term_rule_set_id=record.resource_id,
            version=record.version,
            status=record.status.value,
            rule_count=self._payload_int(payload, "rule_count"),
            enabled_rule_count=self._payload_int(payload, "enabled_rule_count"),
            snapshot_hash=record.snapshot_hash,
            is_default=default is not None and default.version == record.version,
            published_by=self._payload_text(payload, "published_by"),
            publish_reason=self._payload_text(payload, "publish_reason"),
            published_at=self._payload_text(payload, "published_at"),
        )

    @staticmethod
    def _store_from_record(record: ResourceVersionRecord) -> TermRulesStore:
        payload = record.payload or {}
        store_payload = payload.get("store")
        if not isinstance(store_payload, dict):
            raise ValueError("术语规则版本 payload 缺少 store。")
        return TermRulesStore.model_validate(store_payload)

    @staticmethod
    def _count_rules(store: TermRulesStore) -> tuple[int, int]:
        return len(store.rules), sum(1 for rule in store.rules if rule.enabled)

    def _next_version(self, term_rule_set_id: str) -> str:
        prefix = utc_now().astimezone(SHANGHAI_TZ).strftime("%Y.%m.%d-")
        max_suffix = 0
        for record in self.resource_version_service.repository.list_resource_versions("term_rule_set", term_rule_set_id):
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
    def _payload_int(payload: dict[str, Any], key: str) -> int:
        value = payload.get(key)
        return int(value) if isinstance(value, (int, str)) and str(value).isdigit() else 0

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _require_known_set_id(term_rule_set_id: str) -> str:
        normalized = term_rule_set_id.strip()
        if not TERM_RULE_SET_ID_RE.match(normalized):
            raise ValueError("term_rule_set_id 只能包含大小写字母、数字、下划线、短横线和英文句点，长度不超过 128。")
        if normalized != DEFAULT_TERM_RULE_SET_ID:
            raise FileNotFoundError(f"术语规则集不存在: {normalized}")
        return normalized
