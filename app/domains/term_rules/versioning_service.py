# File: app/domains/term_rules/versioning_service.py
# Purpose: 编排术语规则集草稿、发布版本和默认指针同步。

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domains.audit.models import ActorContext
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus, utc_now
from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleCategoryRecord,
    TermRuleImportValidationFinding,
    TermRuleImportValidationReport,
    TermRuleImportValidationSummary,
    TermRuleRecord,
    TermRuleSegmentRecord,
    TermRulesStore,
)
from app.domains.term_rules.repository import TermRuleAssetRepositoryProtocol, TermRuleRepositoryProtocol
from app.domains.term_rules.schemas import (
    TermRuleCreateRequest,
    TermRuleDraftRuleDeleteResponse,
    TermRuleDraftRuleMutationResponse,
    TermRuleGovernanceFindingResponse,
    TermRuleListResponse,
    TermRuleResponse,
    TermRuleSegmentResponse,
    TermRuleSetDetailResponse,
    TermRuleSetDiffItemResponse,
    TermRuleSetDiffResponse,
    TermRuleSetDiffSummaryResponse,
    TermRuleSetDraftResponse,
    TermRuleSetListItemResponse,
    TermRuleSetListResponse,
    TermRuleSetPreflightResponse,
    TermRuleSetPreflightSummaryResponse,
    TermRuleSetVersionResponse,
    TermRuleSetVersionRefResponse,
    TermRuleUpdateRequest,
)
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.yaml_codec import (
    CURRENT_SCHEMA_VERSION,
    TermRuleYamlCodec,
    render_segments_html,
    render_segments_markdown,
)


DEFAULT_TERM_RULE_SET_ID = "electronics-default"
DRAFT_VERSION = "draft"
TERM_RULE_SET_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
SHANGHAI_TZ = timezone(timedelta(hours=8))
TERM_RULE_IMPORT_DEDUPE_MODES = {"reject", "keep_first"}
TERM_RULE_IMPORT_TARGETS = {"draft", "seed"}
TERM_RULE_EXPORT_FORMATS = {"term_rules_v2", "legacy_runtime"}


@dataclass(frozen=True, slots=True)
class TermRuleSetImportDuplicate:
    """Term Rule Set YAML 导入时被去重丢弃的一条重复规则。"""

    source_term: str
    path: str | None
    message: str


@dataclass(frozen=True, slots=True)
class TermRuleSetImportReport:
    """Term Rule Set YAML 导入报告。"""

    dedupe: str
    total_rules: int
    imported_rules: int
    duplicate_rules: int
    duplicates: tuple[TermRuleSetImportDuplicate, ...] = ()


@dataclass(frozen=True, slots=True)
class TermRuleSetImportResult:
    """Term Rule Set 导入执行结果。"""

    target: str
    version: str
    record: ResourceVersionRecord
    validation: TermRuleImportValidationReport
    import_report: TermRuleSetImportReport


@dataclass(frozen=True, slots=True)
class TermRuleSetExportResult:
    """Term Rule Set 导出结果。"""

    set_id: str
    version: str
    format: str
    yaml_text: str
    exported_at: Any
    exported_by: str | None


@dataclass(frozen=True, slots=True)
class TermRuleSetStoreRef:
    """service 内部使用的规则集版本引用和解析后的 store。"""

    ref: str
    version: str
    snapshot_hash: str | None
    store: TermRulesStore
    record: ResourceVersionRecord


class TermRuleSetPreflightError(ValueError):
    """表示发布前校验存在 blocking findings。"""

    def __init__(self, report: TermRuleSetPreflightResponse) -> None:
        super().__init__("Term Rule Set 发布前校验未通过。")
        self.report = report


class TermRuleSetVersionService:
    """管理单实例术语规则集的草稿、发布版本和 live runtime 同步。"""

    def __init__(
        self,
        *,
        repository: TermRuleRepositoryProtocol,
        runtime_yaml_path: Path,
        resource_version_service: ResourceVersionService,
        audit_service: Any | None = None,
        asset_repository: TermRuleAssetRepositoryProtocol | None = None,
    ) -> None:
        self.repository = repository
        self.runtime_yaml_path = runtime_yaml_path
        self.resource_version_service = resource_version_service
        self.audit_service = audit_service
        self.asset_repository = asset_repository
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
            versions=[
                self._version_response(record, default_record=default_record)
                for record in self._version_records(normalized_id)
            ],
        )

    def get_draft(self, term_rule_set_id: str) -> TermRuleSetDraftResponse:
        normalized_id = self._require_known_set_id(term_rule_set_id)
        record = self._ensure_draft_record(normalized_id)
        return self._draft_response(record)

    def get_draft_store(self, term_rule_set_id: str) -> TermRulesStore:
        """返回当前 draft 的结构化 store，供 proposal 审核原子合并使用。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        record = self._ensure_draft_record(normalized_id)
        return self._store_from_record(record)

    def build_diff(
        self,
        term_rule_set_id: str,
        *,
        from_ref: str = "default",
        to_ref: str = DRAFT_VERSION,
        include_unchanged: bool = False,
    ) -> TermRuleSetDiffResponse:
        """返回 draft 与默认或指定 published 版本之间的结构化差异。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        if to_ref != DRAFT_VERSION:
            raise ValueError("当前仅支持 to=draft 的 Term Rule Set diff。")
        base = self._resolve_store_ref(normalized_id, from_ref)
        target = self._resolve_store_ref(normalized_id, to_ref)
        summary, items = self._diff_store_refs(
            base,
            target,
            include_unchanged=include_unchanged,
        )
        return TermRuleSetDiffResponse(
            term_rule_set_id=normalized_id,
            base_ref=self._version_ref_response(base),
            target_ref=self._version_ref_response(target),
            summary=summary,
            items=items,
        )

    def build_preflight(
        self,
        term_rule_set_id: str,
        *,
        base_ref: str = "default",
        approved_unpublished_proposal_count: int = 0,
    ) -> TermRuleSetPreflightResponse:
        """构建当前 draft 的发布前校验报告。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        base = self._resolve_store_ref(normalized_id, base_ref)
        draft = self._resolve_store_ref(normalized_id, DRAFT_VERSION)
        diff_summary, _items = self._diff_store_refs(base, draft, include_unchanged=False)
        errors, warnings, conflicts = self._preflight_findings(
            draft=draft,
            diff_summary=diff_summary,
            approved_unpublished_proposal_count=approved_unpublished_proposal_count,
        )
        error_count = len(errors)
        warning_count = len(warnings)
        conflict_count = len(conflicts)
        rule_count, enabled_rule_count = self._count_rules(draft.store)
        return TermRuleSetPreflightResponse(
            term_rule_set_id=normalized_id,
            valid=error_count == 0 and conflict_count == 0,
            blocking=error_count > 0 or conflict_count > 0,
            base_ref=self._version_ref_response(base),
            draft_ref=self._version_ref_response(draft),
            summary=TermRuleSetPreflightSummaryResponse(
                error_count=error_count,
                warning_count=warning_count,
                conflict_count=conflict_count,
                rule_count=rule_count,
                enabled_rule_count=enabled_rule_count,
            ),
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
            diff_summary=diff_summary,
        )

    def list_draft_rules(
        self,
        term_rule_set_id: str,
        *,
        category_id: str | None,
        enabled: bool | None,
        q: str | None,
        page: int,
        page_size: int,
    ) -> TermRuleListResponse:
        """按 live 规则查询语义分页返回当前 draft 规则。"""

        store = self.get_draft_store(term_rule_set_id)
        needle = q.lower() if q else None
        rules: list[TermRuleRecord] = []
        for rule in self._sorted_rules(store):
            if category_id and rule.category_id != category_id:
                continue
            if enabled is not None and rule.enabled != enabled:
                continue
            if needle and needle not in rule.source_term.lower():
                continue
            rules.append(rule)
        total = len(rules)
        start = (page - 1) * page_size
        end = start + page_size
        return TermRuleListResponse(
            items=[self._rule_response(store, rule) for rule in rules[start:end]],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_draft_rule(self, term_rule_set_id: str, rule_id: str) -> TermRuleResponse:
        """返回当前 draft 中的单条规则。"""

        store = self.get_draft_store(term_rule_set_id)
        return self._rule_response(store, self._find_rule(store, rule_id))

    def create_draft_rule(
        self,
        term_rule_set_id: str,
        payload: TermRuleCreateRequest,
    ) -> TermRuleDraftRuleMutationResponse:
        """在 Term Rule Set draft 中新增一条规则，并返回新的 draft 元数据。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        store = self.get_draft_store(normalized_id)
        rule_id = self._normalize_optional_id(payload.id) or uuid4().hex
        if any(rule.id == rule_id for rule in store.rules):
            raise ValueError(f"规则 ID 已存在: {rule_id}")
        category = self._find_category(store, payload.category_id)
        source_term = self._normalize_required_text(payload.source_term, "source_term")
        self._ensure_unique_source_term(store, source_term, exclude_rule_id=None)
        rule = self._build_rule_record(
            rule_id=rule_id,
            category_id=category.id,
            source_term=source_term,
            apply_scope=payload.apply_scope,
            case_sensitive=payload.case_sensitive,
            enabled=payload.enabled,
            priority=payload.priority,
            segments=[item.model_dump() for item in payload.segments],
            custom_html=payload.custom_html,
            custom_markdown=payload.custom_markdown,
            notes=payload.notes,
        )
        updated_store = store.model_copy(update={"rules": [*store.rules, rule]})
        draft = self.update_draft(normalized_id, updated_store)
        return TermRuleDraftRuleMutationResponse(rule=self._rule_response(updated_store, rule), draft=draft)

    def update_draft_rule(
        self,
        term_rule_set_id: str,
        rule_id: str,
        payload: TermRuleUpdateRequest,
    ) -> TermRuleDraftRuleMutationResponse:
        """更新 Term Rule Set draft 中的一条规则，并返回新的 draft 元数据。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        store = self.get_draft_store(normalized_id)
        rule = self._find_rule(store, rule_id)
        fields = payload.model_fields_set
        category_id = rule.category_id
        if "category_id" in fields and payload.category_id is not None:
            category_id = self._find_category(store, payload.category_id).id
        source_term = rule.source_term
        if "source_term" in fields and payload.source_term is not None:
            source_term = self._normalize_required_text(payload.source_term, "source_term")
            self._ensure_unique_source_term(store, source_term, exclude_rule_id=rule.id)
        segments = [
            {"segment_text": segment.segment_text, "render_type": segment.render_type.value}
            for segment in sorted(rule.segments, key=lambda item: item.seq)
        ]
        segments_changed = "segments" in fields and payload.segments is not None
        if segments_changed and payload.segments is not None:
            segments = [item.model_dump() for item in payload.segments]
        custom_html = rule.custom_html
        custom_markdown = rule.custom_markdown
        if "custom_html" in fields:
            custom_html = payload.custom_html
        elif segments_changed:
            custom_html = None
        if "custom_markdown" in fields:
            custom_markdown = payload.custom_markdown
        elif segments_changed:
            custom_markdown = None
        updated = self._build_rule_record(
            rule_id=rule.id,
            category_id=category_id,
            source_term=source_term,
            apply_scope=(
                payload.apply_scope
                if "apply_scope" in fields and payload.apply_scope is not None
                else rule.apply_scope.value
            ),
            case_sensitive=(
                payload.case_sensitive
                if "case_sensitive" in fields and payload.case_sensitive is not None
                else rule.case_sensitive
            ),
            enabled=payload.enabled if "enabled" in fields and payload.enabled is not None else rule.enabled,
            priority=payload.priority if "priority" in fields and payload.priority is not None else rule.priority,
            segments=segments,
            custom_html=custom_html,
            custom_markdown=custom_markdown,
            notes=payload.notes if "notes" in fields and payload.notes is not None else rule.notes,
            created_at=rule.created_at,
        ).model_copy(update={"updated_at": utc_now()})
        updated_store = store.model_copy(
            update={
                "rules": [
                    updated if existing.id == rule.id else existing
                    for existing in store.rules
                ]
            }
        )
        draft = self.update_draft(normalized_id, updated_store)
        return TermRuleDraftRuleMutationResponse(rule=self._rule_response(updated_store, updated), draft=draft)

    def delete_draft_rule(self, term_rule_set_id: str, rule_id: str) -> TermRuleDraftRuleDeleteResponse:
        """从 Term Rule Set draft 中移除一条规则，并返回新的 draft 元数据。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        store = self.get_draft_store(normalized_id)
        self._find_rule(store, rule_id)
        updated_store = store.model_copy(update={"rules": [rule for rule in store.rules if rule.id != rule_id]})
        draft = self.update_draft(normalized_id, updated_store)
        return TermRuleDraftRuleDeleteResponse(id=rule_id, removed=True, draft=draft)

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

    def import_store(
        self,
        term_rule_set_id: str,
        store: TermRulesStore,
        *,
        target: str,
        dedupe: str,
        validation: TermRuleImportValidationReport,
        import_report: TermRuleSetImportReport,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleSetImportResult:
        """把已校验的 YAML store 导入 draft，或在空集时作为 seed/default 初始化。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        if target not in TERM_RULE_IMPORT_TARGETS:
            raise ValueError(f"不支持的 Term Rule Set 导入目标: {target}")
        if dedupe not in TERM_RULE_IMPORT_DEDUPE_MODES:
            raise ValueError(f"不支持的 Term Rule Set 去重策略: {dedupe}")
        if target == "seed":
            record = self._import_seed_store(normalized_id, store, actor=actor, trace_id=trace_id)
            version = record.version
        else:
            record = self._replace_draft_record(normalized_id, store)
            version = DRAFT_VERSION
        self._record_audit(
            actor=actor,
            action="term_rule_set.import",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
            reason=f"target={target}; dedupe={dedupe}",
        )
        return TermRuleSetImportResult(
            target=target,
            version=version,
            record=record,
            validation=validation,
            import_report=import_report,
        )

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
        preflight = self.build_preflight(normalized_id)
        if preflight.blocking:
            raise TermRuleSetPreflightError(preflight)
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
            make_default=False,
        )
        self._mirror_version(record)
        if make_default:
            self._sync_live_store_then_set_default(normalized_id, record)
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
        record = self._require_published_version_record(normalized_id, version)
        self._sync_live_store_then_set_default(normalized_id, record)
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
        record = self._require_published_version_record(normalized_id, version)
        self._sync_live_store_then_set_default(normalized_id, record)
        self._record_audit(
            actor=actor,
            action="term_rule_set.rollback",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def export_version(
        self,
        term_rule_set_id: str,
        *,
        version: str | None = None,
        export_format: str = "term_rules_v2",
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleSetExportResult:
        """导出指定或默认 Term Rule Set 版本为 term_rules.v2.yaml 或 legacy runtime YAML。"""

        normalized_id = self._require_known_set_id(term_rule_set_id)
        if export_format not in TERM_RULE_EXPORT_FORMATS:
            raise ValueError(f"不支持的 Term Rule Set 导出格式: {export_format}")
        record = (
            self._default_record(normalized_id)
            if version is None
            else self._require_version_record(normalized_id, version)
        )
        if record is None:
            raise FileNotFoundError(f"术语规则集缺少默认版本: {normalized_id}")
        store = self._store_from_record(record)
        yaml_text = (
            self.yaml_codec.dump_legacy_runtime_yaml(store)
            if export_format == "legacy_runtime"
            else self.yaml_codec.dump_store(store)
        )
        exported_at = utc_now()
        exported_by = actor.actor_id if actor is not None else None
        self._record_audit(
            actor=actor,
            action="term_rule_set.export",
            target_id=f"{normalized_id}@{record.version}",
            trace_id=trace_id,
            reason=f"format={export_format}",
        )
        return TermRuleSetExportResult(
            set_id=normalized_id,
            version=record.version,
            format=export_format,
            yaml_text=yaml_text,
            exported_at=exported_at,
            exported_by=exported_by,
        )

    def bootstrap_seed_as_default_if_empty(self, seed_path: Path, *, version: str = "seed") -> ResourceVersionRecord:
        """MySQL mode 下仅在 SQL 无默认版本时从 seed 建立初始 published/default 版本。"""

        normalized_id = self._require_known_set_id(DEFAULT_TERM_RULE_SET_ID)
        default_record = self._default_record(normalized_id)
        if default_record is not None:
            self._sync_live_store(default_record)
            return default_record
        existing_seed = self.resource_version_service.repository.get_resource_version(
            "term_rule_set",
            normalized_id,
            version,
        )
        if existing_seed is not None and existing_seed.status == ResourceVersionStatus.PUBLISHED:
            self._sync_live_store_then_set_default(normalized_id, existing_seed)
            return existing_seed
        if not seed_path.exists():
            raise FileNotFoundError(f"bootstrap 规则文件不存在: {seed_path}")
        result = self.yaml_codec.validate_yaml_text(seed_path.read_text(encoding="utf-8"))
        if result.errors or result.store is None:
            message = result.errors[0].message if result.errors else "bootstrap 规则导入失败"
            raise ValueError(message)
        duplicate = next((item for item in result.warnings if item.code == "duplicate_source_term"), None)
        if duplicate is not None:
            raise ValueError(duplicate.message)
        payload = self._build_payload(
            term_rule_set_id=normalized_id,
            version=version,
            store=result.store,
            base_version=None,
            published_by="seed",
            publish_reason="seed initialization",
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
        published = self.resource_version_service.publish(
            "term_rule_set",
            normalized_id,
            version,
            make_default=False,
        )
        self._sync_live_store_then_set_default(normalized_id, published)
        return published

    def _replace_draft_record(self, term_rule_set_id: str, store: TermRulesStore) -> ResourceVersionRecord:
        existing = self.resource_version_service.repository.get_resource_version(
            "term_rule_set",
            term_rule_set_id,
            DRAFT_VERSION,
        )
        base_version = self._payload_text(existing.payload if existing is not None else None, "base_version")
        if base_version is None:
            default_record = self._default_record(term_rule_set_id)
            base_version = default_record.version if default_record is not None else None
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

    def _import_seed_store(
        self,
        term_rule_set_id: str,
        store: TermRulesStore,
        *,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> ResourceVersionRecord:
        if self._default_record(term_rule_set_id) is not None:
            raise ValueError("seed 初始化只能在 Term Rule Set 缺少默认版本时执行。")
        payload = self._build_payload(
            term_rule_set_id=term_rule_set_id,
            version="seed",
            store=store,
            base_version=None,
            published_by=actor.actor_id if actor is not None else "seed",
            publish_reason="import seed initialization",
            published_at=utc_now(),
        )
        self.resource_version_service.create_or_update_draft(
            resource_type="term_rule_set",
            resource_id=term_rule_set_id,
            version="seed",
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"term_rule_set:{term_rule_set_id}@seed",
            payload=payload,
        )
        published = self.resource_version_service.publish(
            "term_rule_set",
            term_rule_set_id,
            "seed",
            make_default=False,
        )
        self._sync_live_store_then_set_default(term_rule_set_id, published)
        return published

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
        record = self.resource_version_service.repository.get_resource_version(
            "term_rule_set",
            term_rule_set_id,
            version,
        )
        if record is None:
            raise FileNotFoundError(f"术语规则版本不存在: {term_rule_set_id}@{version}")
        return record

    def _require_published_version_record(self, term_rule_set_id: str, version: str) -> ResourceVersionRecord:
        record = self._require_version_record(term_rule_set_id, version)
        if record.status != ResourceVersionStatus.PUBLISHED:
            raise ValueError("默认术语规则版本只能指向 published 版本。")
        return record

    def _sync_live_store_then_set_default(self, term_rule_set_id: str, record: ResourceVersionRecord) -> None:
        previous_default = self._default_record(term_rule_set_id)
        try:
            self._sync_live_store(record)
            self.resource_version_service.set_default("term_rule_set", term_rule_set_id, record.version)
        except Exception as exc:
            if previous_default is not None:
                self.resource_version_service.repository.set_default_resource_version(
                    "term_rule_set",
                    term_rule_set_id,
                    previous_default.version,
                )
            raise ValueError("Term Rule Set 默认版本切换失败，已保留原默认指针。") from exc

    def _sync_live_store(self, record: ResourceVersionRecord) -> None:
        store = self._store_from_record(record)
        self.repository.save(store)
        self.runtime_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_yaml_path.write_text(self.yaml_codec.dump_legacy_runtime_yaml(store), encoding="utf-8")
        self._mirror_store(record.resource_id, record.version, store)

    def mirror_seed_store(self, store: TermRulesStore) -> None:
        """MySQL mode 下把当前本地 seed/runtime 规则写入 SQL 明细表。"""

        self._mirror_store(DEFAULT_TERM_RULE_SET_ID, "seed", store)

    def _mirror_version(self, record: ResourceVersionRecord) -> None:
        if self.asset_repository is None:
            return
        self._mirror_store(record.resource_id, record.version, self._store_from_record(record))

    def _mirror_store(self, term_rule_set_id: str, version: str, store: TermRulesStore) -> None:
        if self.asset_repository is None:
            return
        self.asset_repository.replace_version(term_rule_set_id, version, store)

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

    def _resolve_store_ref(self, term_rule_set_id: str, ref: str) -> TermRuleSetStoreRef:
        """把 default/draft/版本号解析为 store 引用。"""

        normalized_ref = str(ref or "").strip()
        if not normalized_ref:
            raise ValueError("版本引用不能为空。")
        if normalized_ref == DRAFT_VERSION:
            record = self._ensure_draft_record(term_rule_set_id)
        elif normalized_ref == "default":
            record = self._default_record(term_rule_set_id)
            if record is None:
                raise FileNotFoundError(f"术语规则集缺少默认版本: {term_rule_set_id}")
        else:
            record = self._require_published_version_record(term_rule_set_id, normalized_ref)
        return TermRuleSetStoreRef(
            ref=normalized_ref,
            version=record.version,
            snapshot_hash=record.snapshot_hash,
            store=self._store_from_record(record),
            record=record,
        )

    def _version_ref_response(self, store_ref: TermRuleSetStoreRef) -> TermRuleSetVersionRefResponse:
        """把内部 store ref 转换为 API 版本引用响应。"""

        rule_count, enabled_rule_count = self._count_rules(store_ref.store)
        return TermRuleSetVersionRefResponse(
            ref=store_ref.ref,
            version=store_ref.version,
            snapshot_hash=store_ref.snapshot_hash,
            rule_count=rule_count,
            enabled_rule_count=enabled_rule_count,
        )

    def _diff_store_refs(
        self,
        base: TermRuleSetStoreRef,
        target: TermRuleSetStoreRef,
        *,
        include_unchanged: bool,
    ) -> tuple[TermRuleSetDiffSummaryResponse, list[TermRuleSetDiffItemResponse]]:
        """按 rule id 比较两个 store ref 并返回 summary 与明细。"""

        base_rules = {rule.id: rule for rule in base.store.rules}
        target_rules = {rule.id: rule for rule in target.store.rules}
        summary_counts = {
            "added": 0,
            "updated": 0,
            "disabled": 0,
            "removed": 0,
            "unchanged": 0,
        }
        items: list[TermRuleSetDiffItemResponse] = []
        for rule_id in sorted(
            base_rules.keys() | target_rules.keys(),
            key=lambda item: self._diff_sort_key(item, base_rules, target_rules),
        ):
            before = base_rules.get(rule_id)
            after = target_rules.get(rule_id)
            before_payload = self._rule_comparison_payload(before) if before is not None else None
            after_payload = self._rule_comparison_payload(after) if after is not None else None
            changed_fields = self._changed_fields(before_payload, after_payload)
            change_type = self._diff_change_type(before, after, changed_fields)
            summary_counts[change_type] += 1
            if change_type == "unchanged" and not include_unchanged:
                continue
            rule_for_identity = after if after is not None else before
            if rule_for_identity is None:
                continue
            items.append(
                TermRuleSetDiffItemResponse(
                    change_type=change_type,
                    rule_id=rule_id,
                    source_term=rule_for_identity.source_term,
                    category_id=rule_for_identity.category_id,
                    changed_fields=changed_fields,
                    before=self._rule_response(base.store, before) if before is not None else None,
                    after=self._rule_response(target.store, after) if after is not None else None,
                )
            )
        total = sum(summary_counts.values())
        return (
            TermRuleSetDiffSummaryResponse(total=total, **summary_counts),
            items,
        )

    @staticmethod
    def _diff_sort_key(
        rule_id: str,
        base_rules: dict[str, TermRuleRecord],
        target_rules: dict[str, TermRuleRecord],
    ) -> tuple[str, str]:
        """为 diff 明细提供稳定排序键。"""

        rule = target_rules.get(rule_id) or base_rules[rule_id]
        return rule.source_term, rule.id

    @staticmethod
    def _rule_comparison_payload(rule: TermRuleRecord) -> dict[str, Any]:
        """抽取参与 diff 判断的规则字段。"""

        return {
            "category_id": rule.category_id,
            "source_term": rule.source_term,
            "rule_mode": rule.rule_mode.value,
            "apply_scope": rule.apply_scope.value,
            "case_sensitive": rule.case_sensitive,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "segments": [
                {
                    "seq": segment.seq,
                    "segment_text": segment.segment_text,
                    "render_type": segment.render_type.value,
                }
                for segment in sorted(rule.segments, key=lambda item: item.seq)
            ],
            "custom_html": rule.custom_html,
            "custom_markdown": rule.custom_markdown,
            "notes": rule.notes,
        }

    @staticmethod
    def _changed_fields(
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> list[str]:
        """返回两个规则比较 payload 中发生变化的字段名。"""

        if before is None and after is None:
            return []
        if before is None:
            return list(after.keys()) if after is not None else []
        if after is None:
            return list(before.keys())
        return [key for key in before.keys() if before.get(key) != after.get(key)]

    @staticmethod
    def _diff_change_type(
        before: TermRuleRecord | None,
        after: TermRuleRecord | None,
        changed_fields: list[str],
    ) -> str:
        """根据 before/after 状态推导 diff change_type。"""

        if before is None and after is not None:
            return "added"
        if before is not None and after is None:
            return "removed"
        if before is not None and after is not None and before.enabled and not after.enabled:
            return "disabled"
        if changed_fields:
            return "updated"
        return "unchanged"

    def _preflight_findings(
        self,
        *,
        draft: TermRuleSetStoreRef,
        diff_summary: TermRuleSetDiffSummaryResponse,
        approved_unpublished_proposal_count: int,
    ) -> tuple[
        list[TermRuleGovernanceFindingResponse],
        list[TermRuleGovernanceFindingResponse],
        list[TermRuleGovernanceFindingResponse],
    ]:
        """执行治理层发布前检查并按 severity 分类。"""

        errors: list[TermRuleGovernanceFindingResponse] = []
        warnings: list[TermRuleGovernanceFindingResponse] = []
        conflicts: list[TermRuleGovernanceFindingResponse] = []
        categories = self._category_map(draft.store)
        seen_terms: dict[str, TermRuleRecord] = {}
        for index, rule in enumerate(draft.store.rules):
            path_prefix = f"rules.{index}"
            category = categories.get(rule.category_id)
            if category is None:
                errors.append(
                    self._finding(
                        severity="error",
                        code="missing_category",
                        message=f"规则引用了不存在的分类: {rule.category_id}",
                        path=f"{path_prefix}.category_id",
                        rule=rule,
                    )
                )
            elif rule.enabled and not category.enabled:
                errors.append(
                    self._finding(
                        severity="error",
                        code="disabled_category",
                        message=f"启用规则不能引用已禁用分类: {category.code}",
                        path=f"{path_prefix}.category_id",
                        rule=rule,
                    )
                )
            if not rule.segments:
                errors.append(
                    self._finding(
                        severity="error",
                        code="empty_segments",
                        message=f"规则 segments 不能为空: {rule.source_term}",
                        path=f"{path_prefix}.segments",
                        rule=rule,
                    )
                )
            if rule.source_term in seen_terms:
                errors.append(
                    self._finding(
                        severity="error",
                        code="duplicate_source_term",
                        message=f"draft 内 source_term 重复: {rule.source_term}",
                        path=f"{path_prefix}.source_term",
                        rule=rule,
                        metadata={"first_rule_id": seen_terms[rule.source_term].id},
                    )
                )
            else:
                seen_terms[rule.source_term] = rule

        default_record = self._default_record(draft.record.resource_id)
        draft_base_version = self._payload_text(draft.record.payload, "base_version")
        if default_record is not None and draft_base_version and draft_base_version != default_record.version:
            warnings.append(
                self._finding(
                    severity="warning",
                    code="default_version_drift",
                    message="draft 基线版本不是当前默认版本，发布前需要人工确认。",
                    metadata={
                        "draft_base_version": draft_base_version,
                        "current_default_version": default_record.version,
                    },
                )
            )
        if diff_summary.removed > 0:
            warnings.append(
                self._finding(
                    severity="warning",
                    code="removed_rules",
                    message=f"本次发布会移除 {diff_summary.removed} 条规则。",
                    metadata={"count": diff_summary.removed},
                )
            )
        if diff_summary.disabled > 0:
            warnings.append(
                self._finding(
                    severity="warning",
                    code="disabled_rules",
                    message=f"本次发布会停用 {diff_summary.disabled} 条规则。",
                    metadata={"count": diff_summary.disabled},
                )
            )
        if approved_unpublished_proposal_count > 0:
            warnings.append(
                self._finding(
                    severity="warning",
                    code="approved_unpublished_proposals",
                    message="发布成功后会把已审核通过且尚未发布的 proposal 标记为本次版本。",
                    metadata={"count": approved_unpublished_proposal_count},
                )
            )
        return errors, warnings, conflicts

    @staticmethod
    def _finding(
        *,
        severity: str,
        code: str,
        message: str,
        path: str | None = None,
        rule: TermRuleRecord | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TermRuleGovernanceFindingResponse:
        """构造发布前校验 finding 响应。"""

        return TermRuleGovernanceFindingResponse(
            severity=severity,
            code=code,
            message=message,
            path=path,
            rule_id=rule.id if rule is not None else None,
            source_term=rule.source_term if rule is not None else None,
            category_id=rule.category_id if rule is not None else None,
            metadata=metadata or {},
        )

    @staticmethod
    def _sorted_rules(store: TermRulesStore) -> list[TermRuleRecord]:
        """按 live rule 列表语义稳定排序 draft 规则。"""

        return sorted(store.rules, key=lambda item: (item.priority, item.source_term))

    @staticmethod
    def _category_map(store: TermRulesStore) -> dict[str, TermRuleCategoryRecord]:
        """按 category id 建立 draft 分类索引。"""

        return {category.id: category for category in store.categories}

    def _rule_response(self, store: TermRulesStore, rule: TermRuleRecord) -> TermRuleResponse:
        """把 draft store 中的规则转换为 API 响应。"""

        category = self._category_map(store).get(rule.category_id)
        return TermRuleResponse(
            id=rule.id,
            category_id=rule.category_id,
            category_code=category.code if category is not None else "",
            category_name=category.name if category is not None else "",
            source_term=rule.source_term,
            rule_mode=rule.rule_mode.value,
            apply_scope=rule.apply_scope.value,
            case_sensitive=rule.case_sensitive,
            enabled=rule.enabled,
            priority=rule.priority,
            segments=[
                TermRuleSegmentResponse(
                    seq=segment.seq,
                    segment_text=segment.segment_text,
                    render_type=segment.render_type.value,
                )
                for segment in sorted(rule.segments, key=lambda item: item.seq)
            ],
            custom_html=rule.custom_html,
            custom_markdown=rule.custom_markdown,
            notes=rule.notes,
        )

    @staticmethod
    def _find_category(store: TermRulesStore, category_id: str) -> TermRuleCategoryRecord:
        """在 draft store 中按 ID 查找分类。"""

        for category in store.categories:
            if category.id == category_id:
                return category
        raise FileNotFoundError(f"分类不存在: {category_id}")

    @staticmethod
    def _find_rule(store: TermRulesStore, rule_id: str) -> TermRuleRecord:
        """在 draft store 中按 ID 查找规则。"""

        for rule in store.rules:
            if rule.id == rule_id:
                return rule
        raise FileNotFoundError(f"规则不存在: {rule_id}")

    @staticmethod
    def _ensure_unique_source_term(
        store: TermRulesStore,
        source_term: str,
        *,
        exclude_rule_id: str | None,
    ) -> None:
        """确保 draft 内 source_term 唯一。"""

        for rule in store.rules:
            if rule.source_term == source_term and rule.id != exclude_rule_id:
                raise ValueError(f"规则 source_term 已存在: {source_term}")

    @staticmethod
    def _normalize_optional_id(raw_id: str | None) -> str | None:
        """规范化可选 ID，并拒绝不稳定字符。"""

        if raw_id is None:
            return None
        normalized = raw_id.strip()
        if not normalized:
            return None
        if not TERM_RULE_SET_ID_RE.match(normalized):
            raise ValueError(
                "id 只能包含大小写字母、数字、下划线、短横线和英文句点，"
                "长度不超过 128。"
            )
        return normalized

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        """规范化必填文本字段。"""

        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    def _build_rule_record(
        self,
        *,
        rule_id: str,
        category_id: str,
        source_term: str,
        apply_scope: str,
        case_sensitive: bool,
        enabled: bool,
        priority: int,
        segments: list[dict[str, Any]],
        custom_html: str | None,
        custom_markdown: str | None,
        notes: str,
        created_at: Any | None = None,
    ) -> TermRuleRecord:
        """按 live 规则构建约定创建 draft 规则记录。"""

        parsed_segments = self._build_segments(segments)
        try:
            parsed_apply_scope = RuleApplyScope(str(apply_scope).strip().lower())
        except ValueError as exc:
            raise ValueError(f"不支持的 apply_scope: {apply_scope}") from exc
        resolved_custom_html = custom_html if custom_html is not None else render_segments_html(parsed_segments)
        resolved_custom_markdown = (
            custom_markdown
            if custom_markdown is not None
            else render_segments_markdown(parsed_segments)
        )
        return TermRuleRecord(
            id=rule_id,
            category_id=category_id,
            source_term=source_term,
            rule_mode=RuleMode.SIMPLE if len(parsed_segments) <= 2 else RuleMode.ADVANCED,
            apply_scope=parsed_apply_scope,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=int(priority),
            segments=parsed_segments,
            custom_html=resolved_custom_html,
            custom_markdown=resolved_custom_markdown,
            notes=str(notes or ""),
            **({"created_at": created_at} if created_at is not None else {}),
        )

    @staticmethod
    def _build_segments(raw_segments: list[dict[str, Any]]) -> list[TermRuleSegmentRecord]:
        """把 API segment payload 转换为按序保存的规则片段。"""

        if not raw_segments:
            raise ValueError("segments 必须是非空数组")
        segments: list[TermRuleSegmentRecord] = []
        for index, raw_segment in enumerate(raw_segments):
            segment_text = str(raw_segment.get("segment_text", "") or "")
            if not segment_text:
                raise ValueError("segment_text 不能为空")
            render_type_value = str(raw_segment.get("render_type", "") or "").strip().lower()
            try:
                render_type = RuleRenderType(render_type_value)
            except ValueError as exc:
                raise ValueError(f"不支持的 render_type: {render_type_value}") from exc
            segments.append(
                TermRuleSegmentRecord(
                    seq=index + 1,
                    segment_text=segment_text,
                    render_type=render_type,
                )
            )
        return segments

    @staticmethod
    def build_import_validation_report(
        *,
        valid: bool,
        store: TermRulesStore | None,
        errors: list[TermRuleImportValidationFinding],
        warnings: list[TermRuleImportValidationFinding],
    ) -> TermRuleImportValidationReport:
        return TermRuleImportValidationReport(
            valid=valid,
            summary=TermRuleImportValidationSummary(
                category_count=len(store.categories) if store is not None else 0,
                rule_count=len(store.rules) if store is not None else 0,
                error_count=len(errors),
                warning_count=len(warnings),
            ),
            errors=errors,
            warnings=warnings,
        )

    def _next_version(self, term_rule_set_id: str) -> str:
        prefix = utc_now().astimezone(SHANGHAI_TZ).strftime("%Y.%m.%d-")
        max_suffix = 0
        for record in self.resource_version_service.repository.list_resource_versions(
            "term_rule_set",
            term_rule_set_id,
        ):
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
            raise ValueError(
                "term_rule_set_id 只能包含大小写字母、数字、下划线、短横线和英文句点，"
                "长度不超过 128。"
            )
        if normalized != DEFAULT_TERM_RULE_SET_ID:
            raise FileNotFoundError(f"术语规则集不存在: {normalized}")
        return normalized
