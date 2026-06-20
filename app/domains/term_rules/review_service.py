from __future__ import annotations

# File: app/domains/term_rules/review_service.py
# Purpose: Implement terminology rule batch submission, item review, and effective-rule history.

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Literal
from uuid import uuid4

from fastapi import status

from app.core.errors import ApiError
from app.domains.audit.models import ActorContext
from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleRecord,
    TermRuleReviewAction,
    TermRuleReviewBatchRecord,
    TermRuleReviewItemRecord,
    TermRuleReviewItemStatus,
    TermRuleScopeType,
    TermRuleSegmentRecord,
    TermRuleVersionRecord,
    TermRulesStore,
    normalize_term_key,
    utc_now,
)
from app.domains.term_rules.repository import TermRuleReviewRepositoryProtocol
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID, TermRuleSetVersionService
from app.domains.term_rules.yaml_codec import render_segments_html, render_segments_markdown


@dataclass(frozen=True, slots=True)
class TermRuleReviewBulkResultItem:
    item_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | dict[str, Any] | None = None
    item: TermRuleReviewItemRecord | None = None


class TermRuleReviewService:
    """Owns the explicit batch/item review flow for effective term rules."""

    def __init__(
        self,
        *,
        repository: TermRuleReviewRepositoryProtocol,
        term_rule_service: TermRuleService,
        term_rule_set_version_service: TermRuleSetVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.term_rule_service = term_rule_service
        self.term_rule_set_version_service = term_rule_set_version_service
        self.audit_service = audit_service

    def create_batch(
        self,
        *,
        submitted_by: str,
        submitter_role: str,
        submitter_department_id: str,
        source_job_id: str | None,
        source_file_id: str | None,
        reason: str,
        raw_items: list[Any],
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> tuple[TermRuleReviewBatchRecord, list[TermRuleReviewItemRecord]]:
        if not raw_items:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "review batch 至少需要一条变更。")
        if len(raw_items) > 50:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "review batch 最多支持 50 条变更。")

        department_id = self._normalize_required_text(submitter_department_id, "department_id")
        batch = TermRuleReviewBatchRecord(
            id=f"trb_{uuid4().hex[:12]}",
            submitted_by=self._normalize_required_text(submitted_by, "submitted_by"),
            submitter_department_id=department_id,
            source_job_id=self._normalize_optional_text(source_job_id),
            source_file_id=self._normalize_optional_text(source_file_id),
            reason=self._normalize_optional_text(reason) or "",
        )
        saved_batch = self.repository.save_batch(batch)
        store = self.term_rule_service.repository.load()
        items = [
            self.repository.save_item(
                self._build_review_item(
                    batch=saved_batch,
                    seq=index,
                    raw_item=raw_item,
                    store=store,
                    submitter_role=submitter_role,
                    submitter_department_id=department_id,
                )
            )
            for index, raw_item in enumerate(raw_items, start=1)
        ]
        self._record_audit(actor=actor, action="term_rule_review_batch.create", target_id=saved_batch.id, trace_id=trace_id)
        return saved_batch, items

    def list_batches(
        self,
        *,
        submitted_by: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TermRuleReviewBatchRecord], int]:
        return self.repository.list_batches(submitted_by=submitted_by, page=page, page_size=page_size)

    def get_batch(self, batch_id: str) -> TermRuleReviewBatchRecord:
        batch = self.repository.get_batch(batch_id)
        if batch is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"术语规则审核批次不存在: {batch_id}")
        return batch

    def list_items(self, *, batch_id: str | None = None) -> list[TermRuleReviewItemRecord]:
        return self.repository.list_items(batch_id=batch_id)

    def get_item(self, item_id: str) -> TermRuleReviewItemRecord:
        item = self.repository.get_item(item_id)
        if item is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"术语规则审核项不存在: {item_id}")
        return item

    def approve_item(
        self,
        item_id: str,
        *,
        reviewed_by: str,
        reason: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleReviewItemRecord:
        item = self._require_pending_item(item_id)
        store = self.term_rule_service.repository.load()
        conflict = self._approval_conflict(item, store)
        if conflict is not None:
            conflicted = self._mark_item_conflict(item, conflict, reviewed_by=reviewed_by)
            self._record_audit(actor=actor, action="term_rule_review_item.conflict", target_id=item.id, trace_id=trace_id)
            return conflicted

        before_rule: TermRuleRecord | None = None
        if item.action in {TermRuleReviewAction.UPDATE, TermRuleReviewAction.DELETE}:
            before_rule = self._find_rule(store, item.target_rule_id or "")
        after_rule = self._apply_item_to_store(item, store, before_rule)
        now = utc_now()
        approved = item.model_copy(
            update={
                "status": TermRuleReviewItemStatus.APPROVED,
                "reviewed_by": self._normalize_required_text(reviewed_by, "reviewed_by"),
                "reviewed_at": now,
                "updated_at": now,
            }
        )
        saved = self.repository.save_item(approved)
        self._save_version(
            item=saved,
            before_rule=before_rule,
            after_rule=after_rule,
            created_by=reviewed_by,
        )
        self._publish_store(store, reviewed_by=reviewed_by, reason=reason or f"approve term rule review item {item.id}", actor=actor, trace_id=trace_id)
        self._record_audit(actor=actor, action="term_rule_review_item.approve", target_id=saved.id, trace_id=trace_id)
        return saved

    def reject_item(
        self,
        item_id: str,
        *,
        reviewed_by: str,
        reason: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleReviewItemRecord:
        item = self._require_pending_item(item_id)
        now = utc_now()
        rejected = item.model_copy(
            update={
                "status": TermRuleReviewItemStatus.REJECTED,
                "rejection_reason": self._normalize_required_text(reason, "reason"),
                "reviewed_by": self._normalize_required_text(reviewed_by, "reviewed_by"),
                "reviewed_at": now,
                "updated_at": now,
            }
        )
        saved = self.repository.save_item(rejected)
        self._record_audit(actor=actor, action="term_rule_review_item.reject", target_id=saved.id, trace_id=trace_id)
        return saved

    def bulk_review(
        self,
        *,
        action: Literal["approve", "reject"],
        item_ids: list[str],
        reviewed_by: str,
        reason: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> list[TermRuleReviewBulkResultItem]:
        normalized_ids = self._normalize_bulk_ids(item_ids)
        if action == "reject" and not self._normalize_optional_text(reason):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "批量拒绝必须填写原因。")
        results: list[TermRuleReviewBulkResultItem] = []
        for item_id in normalized_ids:
            try:
                item = (
                    self.approve_item(
                        item_id,
                        reviewed_by=reviewed_by,
                        reason=reason,
                        actor=actor,
                        trace_id=trace_id,
                    )
                    if action == "approve"
                    else self.reject_item(
                        item_id,
                        reviewed_by=reviewed_by,
                        reason=reason or "",
                        actor=actor,
                        trace_id=trace_id,
                    )
                )
            except ApiError as exc:
                results.append(
                    TermRuleReviewBulkResultItem(
                        item_id=item_id,
                        ok=False,
                        status_code=exc.status_code,
                        error_code=exc.code,
                        detail=exc.message,
                    )
                )
                continue
            ok = item.status != TermRuleReviewItemStatus.CONFLICT
            results.append(
                TermRuleReviewBulkResultItem(
                    item_id=item.id,
                    ok=ok,
                    status_code=HTTPStatus.OK.value if ok else HTTPStatus.CONFLICT.value,
                    error_code=None if ok else "conflict",
                    detail=None if ok else item.conflict_reason,
                    item=item,
                )
            )
        return results

    def create_global_rule(
        self,
        *,
        raw_item: Any,
        reviewed_by: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleRecord:
        store = self.term_rule_service.repository.load()
        snapshot = self._snapshot_from_raw_item(raw_item, store=store, action=TermRuleReviewAction.CREATE)
        rule = self._rule_from_snapshot(
            snapshot,
            rule_id=self._normalize_optional_text(getattr(raw_item, "id", None)) or uuid4().hex,
            scope_type=TermRuleScopeType.GLOBAL,
            scope_id=None,
            current_version=1,
            active=True,
        )
        conflict = self._find_active_by_identity(store, rule.scope_type, rule.scope_id, rule.normalized_term)
        if conflict is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "同 scope 下 active source_term 已存在。")
        store.rules.append(rule)
        self._save_direct_version(action=TermRuleReviewAction.CREATE, before_rule=None, after_rule=rule, created_by=reviewed_by)
        self._publish_store(store, reviewed_by=reviewed_by, reason=f"admin create global rule {rule.source_term}", actor=actor, trace_id=trace_id)
        return rule

    def update_global_rule(
        self,
        *,
        rule_id: str,
        raw_item: Any,
        reviewed_by: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleRecord:
        store = self.term_rule_service.repository.load()
        before = self._find_rule(store, rule_id)
        if before.scope_type != TermRuleScopeType.GLOBAL:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "管理员正式编辑仅支持 global 规则。")
        merged = self._merged_update_snapshot(before, raw_item)
        after = self._rule_from_snapshot(
            merged,
            rule_id=before.id,
            scope_type=TermRuleScopeType.GLOBAL,
            scope_id=None,
            current_version=before.current_version + 1,
            active=True,
            created_at=before.created_at,
        )
        conflict = self._find_active_by_identity(store, after.scope_type, after.scope_id, after.normalized_term, exclude_rule_id=before.id)
        if conflict is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "同 scope 下 active source_term 已存在。")
        self._replace_rule(store, after)
        self._save_direct_version(action=TermRuleReviewAction.UPDATE, before_rule=before, after_rule=after, created_by=reviewed_by)
        self._publish_store(store, reviewed_by=reviewed_by, reason=f"admin update global rule {after.source_term}", actor=actor, trace_id=trace_id)
        return after

    def delete_global_rule(
        self,
        *,
        rule_id: str,
        reviewed_by: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleRecord:
        store = self.term_rule_service.repository.load()
        before = self._find_rule(store, rule_id)
        if before.scope_type != TermRuleScopeType.GLOBAL:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "管理员正式删除仅支持 global 规则。")
        after = before.model_copy(update={"active": False, "enabled": False, "current_version": before.current_version + 1, "updated_at": utc_now()})
        self._replace_rule(store, after)
        self._save_direct_version(action=TermRuleReviewAction.DELETE, before_rule=before, after_rule=after, created_by=reviewed_by)
        self._publish_store(store, reviewed_by=reviewed_by, reason=f"admin delete global rule {before.source_term}", actor=actor, trace_id=trace_id)
        return after

    def _build_review_item(
        self,
        *,
        batch: TermRuleReviewBatchRecord,
        seq: int,
        raw_item: Any,
        store: TermRulesStore,
        submitter_role: str,
        submitter_department_id: str,
    ) -> TermRuleReviewItemRecord:
        action = TermRuleReviewAction(getattr(raw_item, "action"))
        scope_type, scope_id = self._resolve_submission_scope(
            raw_item=raw_item,
            submitter_role=submitter_role,
            submitter_department_id=submitter_department_id,
            action=action,
        )
        target_rule = None
        if action in {TermRuleReviewAction.UPDATE, TermRuleReviewAction.DELETE}:
            target_rule = self._find_rule(store, self._normalize_required_text(getattr(raw_item, "target_rule_id", None), "target_rule_id"))
            if submitter_role != "admin" and (target_rule.scope_type != scope_type or target_rule.scope_id != scope_id):
                raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "普通用户只能提交本部门规则变更。")
        snapshot = self._snapshot_from_raw_item(raw_item, store=store, action=action, target_rule=target_rule)
        normalized_term = normalize_term_key(snapshot["source_term"])
        return TermRuleReviewItemRecord(
            id=f"tri_{uuid4().hex[:12]}",
            batch_id=batch.id,
            seq=seq,
            action=action,
            scope_type=scope_type,
            scope_id=scope_id,
            normalized_term=normalized_term,
            target_rule_id=target_rule.id if target_rule is not None else None,
            base_version=getattr(raw_item, "base_version", None) or (target_rule.current_version if target_rule is not None else None),
            submitted_snapshot=snapshot,
        )

    def _resolve_submission_scope(
        self,
        *,
        raw_item: Any,
        submitter_role: str,
        submitter_department_id: str,
        action: TermRuleReviewAction,
    ) -> tuple[TermRuleScopeType, str | None]:
        if submitter_role != "admin":
            if action == TermRuleReviewAction.DELETE:
                raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "普通用户不能提交删除规则请求。")
            requested_scope = getattr(raw_item, "scope_type", None)
            if requested_scope == TermRuleScopeType.GLOBAL.value:
                raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "普通用户不能提交 global 规则变更。")
            return TermRuleScopeType.DEPARTMENT, submitter_department_id
        raw_scope = getattr(raw_item, "scope_type", None) or TermRuleScopeType.GLOBAL.value
        scope_type = TermRuleScopeType(raw_scope)
        scope_id = None if scope_type == TermRuleScopeType.GLOBAL else self._normalize_required_text(getattr(raw_item, "scope_id", None), "scope_id")
        return scope_type, scope_id

    def _snapshot_from_raw_item(
        self,
        raw_item: Any,
        *,
        store: TermRulesStore,
        action: TermRuleReviewAction,
        target_rule: TermRuleRecord | None = None,
    ) -> dict[str, Any]:
        if action == TermRuleReviewAction.DELETE:
            if target_rule is None:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "delete item 缺少目标规则。")
            return target_rule.model_dump(mode="json")
        source_term = self._normalize_required_text(getattr(raw_item, "source_term", None), "source_term")
        category_id = self._normalize_required_text(getattr(raw_item, "category_id", None), "category_id")
        self._require_category(store, category_id)
        segments = self._build_segments(getattr(raw_item, "segments", None) or [])
        return {
            "source_term": source_term,
            "category_id": category_id,
            "apply_scope": getattr(raw_item, "apply_scope", None) or RuleApplyScope.BOTH.value,
            "case_sensitive": bool(getattr(raw_item, "case_sensitive", True)),
            "enabled": bool(getattr(raw_item, "enabled", True)),
            "priority": int(getattr(raw_item, "priority", 100)),
            "segments": [segment.model_dump(mode="json") for segment in segments],
            "custom_html": self._normalize_optional_text(getattr(raw_item, "custom_html", None)),
            "custom_markdown": self._normalize_optional_text(getattr(raw_item, "custom_markdown", None)),
            "notes": str(getattr(raw_item, "notes", "") or ""),
        }

    def _merged_update_snapshot(self, before: TermRuleRecord, raw_item: Any) -> dict[str, Any]:
        snapshot = before.model_dump(mode="json")
        for field_name in (
            "source_term",
            "category_id",
            "apply_scope",
            "case_sensitive",
            "enabled",
            "priority",
            "segments",
            "custom_html",
            "custom_markdown",
            "notes",
        ):
            if field_name in getattr(raw_item, "model_fields_set", set()):
                value = getattr(raw_item, field_name)
                if field_name == "segments" and value is not None:
                    snapshot[field_name] = [segment.model_dump(mode="json") for segment in self._build_segments(value)]
                elif value is not None or field_name in {"custom_html", "custom_markdown"}:
                    snapshot[field_name] = value
        return snapshot

    def _approval_conflict(self, item: TermRuleReviewItemRecord, store: TermRulesStore) -> str | None:
        if item.action == TermRuleReviewAction.CREATE:
            existing = self._find_active_by_identity(store, item.scope_type, item.scope_id, item.normalized_term)
            return "同 scope 下 active source_term 已存在。" if existing is not None else None
        try:
            target = self._find_rule(store, item.target_rule_id or "")
        except ApiError:
            return "目标规则不存在或已被删除。"
        if not target.active:
            return "目标规则已被删除。"
        if target.current_version != item.base_version:
            return f"目标规则版本已变化: base_version={item.base_version} current_version={target.current_version}。"
        if item.action == TermRuleReviewAction.UPDATE:
            next_term = normalize_term_key(item.submitted_snapshot.get("source_term", ""))
            existing = self._find_active_by_identity(store, item.scope_type, item.scope_id, next_term, exclude_rule_id=target.id)
            if existing is not None:
                return "同 scope 下 active source_term 已存在。"
        return None

    def _mark_item_conflict(
        self,
        item: TermRuleReviewItemRecord,
        reason: str,
        *,
        reviewed_by: str,
    ) -> TermRuleReviewItemRecord:
        now = utc_now()
        conflicted = item.model_copy(
            update={
                "status": TermRuleReviewItemStatus.CONFLICT,
                "conflict_reason": reason,
                "reviewed_by": self._normalize_required_text(reviewed_by, "reviewed_by"),
                "reviewed_at": now,
                "updated_at": now,
            }
        )
        return self.repository.save_item(conflicted)

    def _apply_item_to_store(
        self,
        item: TermRuleReviewItemRecord,
        store: TermRulesStore,
        before_rule: TermRuleRecord | None,
    ) -> TermRuleRecord:
        if item.action == TermRuleReviewAction.CREATE:
            rule = self._rule_from_snapshot(
                item.submitted_snapshot,
                rule_id=uuid4().hex,
                scope_type=item.scope_type,
                scope_id=item.scope_id,
                current_version=1,
                active=True,
            )
            store.rules.append(rule)
            return rule
        if before_rule is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", "目标规则不存在。")
        if item.action == TermRuleReviewAction.DELETE:
            deleted = before_rule.model_copy(update={"active": False, "enabled": False, "current_version": before_rule.current_version + 1, "updated_at": utc_now()})
            self._replace_rule(store, deleted)
            return deleted
        updated = self._rule_from_snapshot(
            item.submitted_snapshot,
            rule_id=before_rule.id,
            scope_type=item.scope_type,
            scope_id=item.scope_id,
            current_version=before_rule.current_version + 1,
            active=True,
            created_at=before_rule.created_at,
        )
        self._replace_rule(store, updated)
        return updated

    def _rule_from_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        rule_id: str,
        scope_type: TermRuleScopeType,
        scope_id: str | None,
        current_version: int,
        active: bool,
        created_at: Any | None = None,
    ) -> TermRuleRecord:
        segments = [
            TermRuleSegmentRecord(
                seq=index,
                segment_text=str(segment["segment_text"]),
                render_type=RuleRenderType(str(segment["render_type"])),
            )
            for index, segment in enumerate(snapshot.get("segments") or [], start=1)
        ]
        return TermRuleRecord(
            id=rule_id,
            category_id=self._normalize_required_text(snapshot.get("category_id"), "category_id"),
            source_term=self._normalize_required_text(snapshot.get("source_term"), "source_term"),
            normalized_term=normalize_term_key(str(snapshot.get("source_term", ""))),
            scope_type=scope_type,
            scope_id=scope_id,
            current_version=current_version,
            active=active,
            rule_mode=RuleMode.SIMPLE if len(segments) <= 2 else RuleMode.ADVANCED,
            apply_scope=RuleApplyScope(str(snapshot.get("apply_scope") or RuleApplyScope.BOTH.value)),
            case_sensitive=bool(snapshot.get("case_sensitive", True)),
            enabled=bool(snapshot.get("enabled", True)),
            priority=int(snapshot.get("priority", 100)),
            segments=segments,
            custom_html=snapshot.get("custom_html") or render_segments_html(segments),
            custom_markdown=snapshot.get("custom_markdown") or render_segments_markdown(segments),
            notes=str(snapshot.get("notes", "") or ""),
            **({"created_at": created_at} if created_at is not None else {}),
        ).model_copy(update={"updated_at": utc_now()})

    def _publish_store(
        self,
        store: TermRulesStore,
        *,
        reviewed_by: str,
        reason: str,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> None:
        self.term_rule_set_version_service.publish_store_as_default(
            DEFAULT_TERM_RULE_SET_ID,
            store=store,
            published_by=reviewed_by,
            publish_reason=reason,
            actor=actor,
            trace_id=trace_id,
        )

    def _save_version(
        self,
        *,
        item: TermRuleReviewItemRecord,
        before_rule: TermRuleRecord | None,
        after_rule: TermRuleRecord,
        created_by: str,
    ) -> None:
        self.repository.save_version(
            TermRuleVersionRecord(
                id=f"trv_{uuid4().hex[:12]}",
                rule_id=after_rule.id,
                version=after_rule.current_version,
                action=item.action,
                scope_type=after_rule.scope_type,
                scope_id=after_rule.scope_id,
                normalized_term=after_rule.normalized_term,
                review_item_id=item.id,
                before_snapshot=before_rule.model_dump(mode="json") if before_rule is not None else None,
                after_snapshot=after_rule.model_dump(mode="json"),
                created_by=created_by,
            )
        )

    def _save_direct_version(
        self,
        *,
        action: TermRuleReviewAction,
        before_rule: TermRuleRecord | None,
        after_rule: TermRuleRecord,
        created_by: str,
    ) -> None:
        self.repository.save_version(
            TermRuleVersionRecord(
                id=f"trv_{uuid4().hex[:12]}",
                rule_id=after_rule.id,
                version=after_rule.current_version,
                action=action,
                scope_type=after_rule.scope_type,
                scope_id=after_rule.scope_id,
                normalized_term=after_rule.normalized_term,
                before_snapshot=before_rule.model_dump(mode="json") if before_rule is not None else None,
                after_snapshot=after_rule.model_dump(mode="json"),
                created_by=created_by,
            )
        )

    def _require_pending_item(self, item_id: str) -> TermRuleReviewItemRecord:
        item = self.get_item(item_id)
        if item.status != TermRuleReviewItemStatus.PENDING:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "只有 pending 审核项可以处理。")
        return item

    @staticmethod
    def _normalize_bulk_ids(item_ids: list[str]) -> list[str]:
        normalized = [item_id.strip() for item_id in item_ids]
        if not normalized:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "item_ids 不能为空。")
        if len(normalized) > 50:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "item_ids 最多支持 50 个。")
        if any(not item_id for item_id in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "item_ids 不能包含空值。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "item_ids 不能重复。")
        return normalized

    @staticmethod
    def _find_rule(store: TermRulesStore, rule_id: str) -> TermRuleRecord:
        for rule in store.rules:
            if rule.id == rule_id:
                return rule
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"规则不存在: {rule_id}")

    @staticmethod
    def _replace_rule(store: TermRulesStore, replacement: TermRuleRecord) -> None:
        for index, rule in enumerate(store.rules):
            if rule.id == replacement.id:
                store.rules[index] = replacement
                return
        raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"规则不存在: {replacement.id}")

    @staticmethod
    def _find_active_by_identity(
        store: TermRulesStore,
        scope_type: TermRuleScopeType,
        scope_id: str | None,
        normalized_term: str,
        *,
        exclude_rule_id: str | None = None,
    ) -> TermRuleRecord | None:
        for rule in store.rules:
            if not rule.active or rule.id == exclude_rule_id:
                continue
            if rule.scope_type == scope_type and rule.scope_id == scope_id and rule.normalized_term == normalized_term:
                return rule
        return None

    @staticmethod
    def _require_category(store: TermRulesStore, category_id: str) -> None:
        if not any(category.id == category_id for category in store.categories):
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"分类不存在: {category_id}")

    @staticmethod
    def _build_segments(raw_segments: list[Any]) -> list[TermRuleSegmentRecord]:
        if not raw_segments:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "segments 必须是非空数组。")
        segments: list[TermRuleSegmentRecord] = []
        for index, raw_segment in enumerate(raw_segments, start=1):
            segment_payload = raw_segment if isinstance(raw_segment, dict) else {}
            text = str(getattr(raw_segment, "segment_text", None) or segment_payload.get("segment_text", "")).strip()
            if not text:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "segment_text 不能为空。")
            render_type_value = str(getattr(raw_segment, "render_type", None) or segment_payload.get("render_type", "")).strip()
            try:
                render_type = RuleRenderType(render_type_value)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"不支持的 render_type: {render_type_value}") from exc
            segments.append(TermRuleSegmentRecord(seq=index, segment_text=text, render_type=render_type))
        return segments

    @staticmethod
    def _normalize_required_text(value: Any, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", f"{field_name} 不能为空。")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

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
            target_type="term_rule_review",
            target_id=target_id,
            trace_id=trace_id or "",
        )
