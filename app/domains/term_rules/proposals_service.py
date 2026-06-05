# File: app/domains/term_rules/proposals_service.py
# Purpose: 编排术语建议提交、审核和合并到规则集 draft。

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Literal, NoReturn
from uuid import uuid4

from app.domains.audit.models import ActorContext
from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleProposalIntent,
    TermRuleProposalRecord,
    TermRuleProposalStatus,
    TermRuleRecord,
    TermRuleSegmentRecord,
    TermRulesStore,
    utc_now,
)
from app.domains.term_rules.repository import TermRuleProposalRepositoryProtocol
from app.domains.term_rules.schemas import (
    TermRuleProposalConflictResponse,
    TermRuleProposalConflictItemResponse,
    TermRuleResponse,
    TermRuleSegmentResponse,
)
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID, TermRuleSetVersionService
from app.domains.term_rules.yaml_codec import render_segments_html, render_segments_markdown


class TermRuleProposalConflictError(RuntimeError):
    """目标规则或 draft 状态已变化，proposal 不能无提示合并。"""

    def __init__(self, conflicts: list[TermRuleProposalConflictItemResponse]) -> None:
        """保存结构化冲突，同时保留字符串消息兼容旧 router。"""

        self.conflicts = tuple(conflicts)
        message = "; ".join(conflict.message for conflict in conflicts) or "proposal 与当前 draft 存在冲突。"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class TermRuleProposalBulkReviewItem:
    """描述批量审核中单条 proposal 的结果，供 router 映射为 API 响应。"""

    proposal_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | dict[str, Any] | None = None
    proposal: TermRuleProposalRecord | None = None


class TermRuleProposalService:
    """维护 operator proposal 到 admin 审核合并的最小后端合同。"""

    def __init__(
        self,
        *,
        repository: TermRuleProposalRepositoryProtocol,
        term_rule_service: TermRuleService,
        term_rule_set_version_service: TermRuleSetVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.term_rule_service = term_rule_service
        self.term_rule_set_version_service = term_rule_set_version_service
        self.audit_service = audit_service

    def create_proposal(
        self,
        *,
        intent: TermRuleProposalIntent,
        source_term: str | None,
        category_id: str | None,
        segments: list[dict[str, Any]] | None,
        reason: str,
        source_job_id: str | None,
        source_file_id: str | None,
        target_rule_id: str | None,
        created_by: str,
        page_number: int | None = None,
        context_before: str | None = None,
        context_after: str | None = None,
        observed_term_rule_set_id: str | None = None,
        observed_term_rule_version: str | None = None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleProposalRecord:
        """创建 pending_review proposal，并在 update/disable 时保存目标规则快照。"""

        normalized_reason = self._normalize_required_text(reason, "reason")
        target_rule = self._load_target_rule(intent, target_rule_id)
        if intent == TermRuleProposalIntent.CREATE and target_rule_id is not None:
            raise ValueError("create proposal 不能绑定 target_rule_id。")
        if intent == TermRuleProposalIntent.DISABLE:
            assert target_rule is not None
            normalized_source_term = target_rule.source_term
            normalized_category_id = target_rule.category_id
            parsed_segments = target_rule.segments
        else:
            normalized_source_term = self._normalize_required_text(source_term or "", "source_term")
            normalized_category_id = self._normalize_required_text(category_id or "", "category_id")
            self._require_category(self.term_rule_service.repository.load(), normalized_category_id)
            parsed_segments = self._build_segments(segments or [])

        proposal = TermRuleProposalRecord(
            id=f"trp_{uuid4().hex[:12]}",
            intent=intent,
            source_term=normalized_source_term,
            category_id=normalized_category_id,
            segments=parsed_segments,
            reason=normalized_reason,
            source_job_id=self._normalize_optional_text(source_job_id),
            source_file_id=self._normalize_optional_text(source_file_id),
            page_number=page_number,
            context_before=self._normalize_optional_text(context_before),
            context_after=self._normalize_optional_text(context_after),
            observed_term_rule_set_id=self._normalize_optional_text(observed_term_rule_set_id) or DEFAULT_TERM_RULE_SET_ID,
            observed_term_rule_version=self._normalize_optional_text(observed_term_rule_version) or self._current_default_version(),
            target_rule_id=target_rule.id if target_rule is not None else None,
            target_rule_snapshot=self._rule_snapshot(target_rule) if target_rule is not None else None,
            created_by=self._normalize_required_text(created_by, "created_by"),
        )
        saved = self.repository.save_proposal(proposal)
        self._record_audit(actor=actor, action="term_rule_proposal.create", proposal=saved, trace_id=trace_id)
        return saved

    def list_proposals(
        self,
        *,
        status: TermRuleProposalStatus | None = None,
        created_by: str | None = None,
    ) -> list[TermRuleProposalRecord]:
        """按状态和提交人查询 proposals。"""

        return self.repository.list_proposals(status=status, created_by=created_by)

    def list_approved_unpublished_proposals(
        self,
        term_rule_set_id: str = DEFAULT_TERM_RULE_SET_ID,
    ) -> list[TermRuleProposalRecord]:
        """查询已合入 draft 但尚未随 Term Rule Set 版本发布的 proposal。"""

        return [
            proposal
            for proposal in self.repository.list_proposals(status=TermRuleProposalStatus.APPROVED)
            if proposal.merged_term_rule_set_id == term_rule_set_id
            and proposal.published_term_rule_set_version is None
        ]

    def mark_approved_proposals_published(
        self,
        *,
        term_rule_set_id: str,
        published_version: str,
    ) -> list[TermRuleProposalRecord]:
        """在规则集发布成功后，把本轮已 approve proposal 关联到发布版本。"""

        now = utc_now()
        published: list[TermRuleProposalRecord] = []
        for proposal in self.list_approved_unpublished_proposals(term_rule_set_id):
            updated = proposal.model_copy(
                update={
                    "status": TermRuleProposalStatus.PUBLISHED,
                    "published_term_rule_set_id": term_rule_set_id,
                    "published_term_rule_set_version": published_version,
                    "published_at": now,
                    "updated_at": now,
                }
            )
            published.append(self.repository.save_proposal(updated))
        return published

    def get_proposal(self, proposal_id: str) -> TermRuleProposalRecord:
        """读取单条 proposal。"""

        proposal = self.repository.get_proposal(proposal_id)
        if proposal is None:
            raise FileNotFoundError(f"术语建议不存在: {proposal_id}")
        return proposal

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_comment: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleProposalRecord:
        """把 pending proposal 合并到 Term Rule Set draft 后再标记 approved。"""

        proposal = self._require_pending(proposal_id)
        draft_store = self.term_rule_set_version_service.get_draft_store(DEFAULT_TERM_RULE_SET_ID)
        updated_store = self._apply_to_store(proposal, draft_store)
        draft = self.term_rule_set_version_service.update_draft(DEFAULT_TERM_RULE_SET_ID, updated_store)
        now = utc_now()
        approved = proposal.model_copy(
            update={
                "status": TermRuleProposalStatus.APPROVED,
                "reviewed_by": self._normalize_required_text(reviewed_by, "reviewed_by"),
                "reviewed_at": now,
                "review_comment": self._normalize_optional_text(review_comment),
                "merged_term_rule_set_id": DEFAULT_TERM_RULE_SET_ID,
                "merged_draft_snapshot_hash": draft.snapshot_hash,
                "updated_at": now,
            }
        )
        saved = self.repository.save_proposal(approved)
        self._record_audit(actor=actor, action="term_rule_proposal.approve", proposal=saved, trace_id=trace_id)
        return saved

    def bulk_approve_proposals(
        self,
        proposal_ids: list[str],
        *,
        reviewed_by: str,
        review_comment: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> list[TermRuleProposalBulkReviewItem]:
        """逐条复用单条 approve 语义，返回允许部分成功的批量结果。"""

        return self._bulk_review_proposals(
            action="approve",
            proposal_ids=proposal_ids,
            reviewed_by=reviewed_by,
            review_comment=review_comment,
            actor=actor,
            trace_id=trace_id,
        )

    def approve_and_publish_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_comment: str | None,
        publish_reason: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleProposalRecord:
        """审核 proposal、发布当前 draft 为默认版本，并回填发布版本。"""

        approved = self.approve_proposal(
            proposal_id,
            reviewed_by=reviewed_by,
            review_comment=review_comment,
            actor=actor,
            trace_id=trace_id,
        )
        reason = self._normalize_optional_text(publish_reason) or f"publish approved term rule proposal {approved.id}: {approved.source_term}"
        published = self.term_rule_set_version_service.publish_draft(
            DEFAULT_TERM_RULE_SET_ID,
            make_default=True,
            published_by=reviewed_by,
            publish_reason=reason,
            actor=actor,
            trace_id=trace_id,
        )
        self.mark_approved_proposals_published(
            term_rule_set_id=DEFAULT_TERM_RULE_SET_ID,
            published_version=published.version,
        )
        published_proposal = self.get_proposal(proposal_id)
        self._record_audit(
            actor=actor,
            action="term_rule_proposal.approve_and_publish",
            proposal=published_proposal,
            trace_id=trace_id,
        )
        return published_proposal

    def reject_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_comment: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TermRuleProposalRecord:
        """拒绝 pending proposal，拒绝原因必填。"""

        proposal = self._require_pending(proposal_id)
        now = utc_now()
        rejected = proposal.model_copy(
            update={
                "status": TermRuleProposalStatus.REJECTED,
                "reviewed_by": self._normalize_required_text(reviewed_by, "reviewed_by"),
                "reviewed_at": now,
                "review_comment": self._normalize_required_text(review_comment, "review_comment"),
                "updated_at": now,
            }
        )
        saved = self.repository.save_proposal(rejected)
        self._record_audit(actor=actor, action="term_rule_proposal.reject", proposal=saved, trace_id=trace_id)
        return saved

    def bulk_reject_proposals(
        self,
        proposal_ids: list[str],
        *,
        reviewed_by: str,
        review_comment: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> list[TermRuleProposalBulkReviewItem]:
        """逐条复用单条 reject 语义，返回允许部分成功的批量结果。"""

        return self._bulk_review_proposals(
            action="reject",
            proposal_ids=proposal_ids,
            reviewed_by=reviewed_by,
            review_comment=review_comment,
            actor=actor,
            trace_id=trace_id,
        )

    def _bulk_review_proposals(
        self,
        *,
        action: Literal["approve", "reject"],
        proposal_ids: list[str],
        reviewed_by: str,
        review_comment: str | None,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> list[TermRuleProposalBulkReviewItem]:
        """按请求顺序逐条执行审核动作，单条失败不阻断后续 proposal。"""

        normalized_ids = self._normalize_bulk_proposal_ids(proposal_ids)
        items: list[TermRuleProposalBulkReviewItem] = []
        for proposal_id in normalized_ids:
            try:
                if action == "approve":
                    proposal = self.approve_proposal(
                        proposal_id,
                        reviewed_by=reviewed_by,
                        review_comment=review_comment,
                        actor=actor,
                        trace_id=trace_id,
                    )
                else:
                    proposal = self.reject_proposal(
                        proposal_id,
                        reviewed_by=reviewed_by,
                        review_comment=review_comment or "",
                        actor=actor,
                        trace_id=trace_id,
                    )
            except TermRuleProposalConflictError as exc:
                items.append(self._build_bulk_conflict_failure(proposal_id, exc))
                continue
            except FileNotFoundError as exc:
                items.append(
                    self._build_bulk_failure(
                        proposal_id,
                        status_code=HTTPStatus.NOT_FOUND.value,
                        error_code="not_found",
                        detail=str(exc),
                    )
                )
                continue
            except ValueError as exc:
                items.append(
                    self._build_bulk_failure(
                        proposal_id,
                        status_code=HTTPStatus.BAD_REQUEST.value,
                        error_code="invalid_request",
                        detail=str(exc),
                    )
                )
                continue
            items.append(self._build_bulk_success(proposal))
        return items

    @staticmethod
    def _normalize_bulk_proposal_ids(proposal_ids: list[str]) -> list[str]:
        """校验批量请求的 proposal_id 列表，并返回去除首尾空白后的值。"""

        normalized = [proposal_id.strip() for proposal_id in proposal_ids]
        if not normalized:
            raise ValueError("proposal_ids 不能为空。")
        if len(normalized) > 50:
            raise ValueError("proposal_ids 最多支持 50 个。")
        if any(not proposal_id for proposal_id in normalized):
            raise ValueError("proposal_ids 不能包含空值。")
        if len(set(normalized)) != len(normalized):
            raise ValueError("proposal_ids 不能重复。")
        return normalized

    @staticmethod
    def _build_bulk_success(proposal: TermRuleProposalRecord) -> TermRuleProposalBulkReviewItem:
        """构造批量审核中单条成功 proposal 的 service 结果。"""

        return TermRuleProposalBulkReviewItem(
            proposal_id=proposal.id,
            ok=True,
            status_code=HTTPStatus.OK.value,
            proposal=proposal,
        )

    @staticmethod
    def _build_bulk_failure(
        proposal_id: str,
        *,
        status_code: int,
        error_code: str,
        detail: str | dict[str, Any],
    ) -> TermRuleProposalBulkReviewItem:
        """构造批量审核中单条失败 proposal 的 service 结果。"""

        return TermRuleProposalBulkReviewItem(
            proposal_id=proposal_id,
            ok=False,
            status_code=status_code,
            error_code=error_code,
            detail=detail,
        )

    def _build_bulk_conflict_failure(
        self,
        proposal_id: str,
        exc: TermRuleProposalConflictError,
    ) -> TermRuleProposalBulkReviewItem:
        """把结构化冲突保留到批量 item 的 detail 中。"""

        detail = TermRuleProposalConflictResponse(
            message="proposal 与当前 draft 存在冲突，请重新核对后处理。",
            conflicts=list(exc.conflicts),
        ).model_dump(mode="json")
        return self._build_bulk_failure(
            proposal_id,
            status_code=HTTPStatus.CONFLICT.value,
            error_code="term_rule_proposal_conflict",
            detail=detail,
        )

    def _require_pending(self, proposal_id: str) -> TermRuleProposalRecord:
        proposal = self.get_proposal(proposal_id)
        if proposal.status != TermRuleProposalStatus.PENDING_REVIEW:
            raise ValueError("只有 pending_review proposal 可以审核。")
        return proposal

    def _load_target_rule(
        self,
        intent: TermRuleProposalIntent,
        target_rule_id: str | None,
    ) -> TermRuleRecord | None:
        if intent in {TermRuleProposalIntent.UPDATE, TermRuleProposalIntent.DISABLE}:
            normalized_target = self._normalize_required_text(target_rule_id or "", "target_rule_id")
            return self.term_rule_service.get_rule(normalized_target)
        return None

    def _apply_to_store(self, proposal: TermRuleProposalRecord, store: TermRulesStore) -> TermRulesStore:
        """把 proposal 应用到 draft store；遇到证据冲突时先抛错避免写入。"""

        if proposal.intent == TermRuleProposalIntent.CREATE:
            self._require_category(store, proposal.category_id)
            self._ensure_no_conflicting_source_segments(store, proposal)
            self._ensure_unique_source_term(store, proposal.source_term, exclude_rule_id=None)
            return store.model_copy(
                update={
                    "rules": [
                        *store.rules,
                        self._build_rule_record(
                            rule_id=uuid4().hex,
                            category_id=proposal.category_id,
                            source_term=proposal.source_term,
                            segments=proposal.segments,
                            notes=proposal.reason,
                        ),
                    ]
                }
            )

        if proposal.target_rule_id is None or proposal.target_rule_snapshot is None:
            raise ValueError("update/disable proposal 缺少目标规则快照。")
        try:
            target = self._find_rule(store, proposal.target_rule_id)
        except FileNotFoundError:
            self._raise_conflict(
                conflict_type="missing_target_rule",
                message="目标规则已发生变化，当前 draft 中已不存在，请重新提交 proposal。",
                proposal=proposal,
                store=store,
                target_rule_id=proposal.target_rule_id,
            )
        if self._rule_snapshot(target) != proposal.target_rule_snapshot:
            self._raise_conflict(
                conflict_type="stale_target_rule",
                message="目标规则已发生变化，请重新提交 proposal。",
                proposal=proposal,
                store=store,
                target_rule=target,
                target_rule_id=target.id,
            )

        if proposal.intent == TermRuleProposalIntent.DISABLE:
            replacement = target.model_copy(update={"enabled": False, "notes": proposal.reason, "updated_at": utc_now()})
        else:
            self._require_category(store, proposal.category_id)
            self._ensure_unique_source_term(store, proposal.source_term, exclude_rule_id=target.id)
            replacement = self._build_rule_record(
                rule_id=target.id,
                category_id=proposal.category_id,
                source_term=proposal.source_term,
                segments=proposal.segments,
                notes=proposal.reason,
                apply_scope=target.apply_scope,
                case_sensitive=target.case_sensitive,
                enabled=target.enabled,
                priority=target.priority,
                created_at=target.created_at,
            ).model_copy(update={"updated_at": utc_now()})
        return store.model_copy(
            update={
                "rules": [
                    replacement if rule.id == target.id else rule
                    for rule in store.rules
                ]
            }
        )

    @staticmethod
    def _rule_snapshot(rule: TermRuleRecord) -> dict[str, Any]:
        return rule.model_dump(mode="json")

    def _raise_conflict(
        self,
        *,
        conflict_type: Literal["stale_target_rule", "missing_target_rule", "source_term_segments_conflict"],
        message: str,
        proposal: TermRuleProposalRecord,
        store: TermRulesStore,
        target_rule: TermRuleRecord | None = None,
        target_rule_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NoReturn:
        """构造单条结构化 proposal 冲突并中断审核写入。"""

        raise TermRuleProposalConflictError(
            [
                self._build_conflict_item(
                    conflict_type=conflict_type,
                    message=message,
                    proposal=proposal,
                    store=store,
                    target_rule=target_rule,
                    target_rule_id=target_rule_id,
                    metadata=metadata,
                )
            ]
        )

    def _build_conflict_item(
        self,
        *,
        conflict_type: Literal["stale_target_rule", "missing_target_rule", "source_term_segments_conflict"],
        message: str,
        proposal: TermRuleProposalRecord,
        store: TermRulesStore,
        target_rule: TermRuleRecord | None = None,
        target_rule_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TermRuleProposalConflictItemResponse:
        """把 draft 现场和 proposal 快照整理成稳定的冲突响应项。"""

        return TermRuleProposalConflictItemResponse(
            type=conflict_type,
            message=message,
            proposal_id=proposal.id,
            target_rule_id=target_rule_id or proposal.target_rule_id,
            source_term=proposal.source_term,
            category_id=proposal.category_id,
            current_rule=self._rule_response_for_conflict(store, target_rule) if target_rule is not None else None,
            target_rule_snapshot=proposal.target_rule_snapshot,
            metadata=metadata or {},
        )

    @staticmethod
    def _rule_response_for_conflict(store: TermRulesStore, rule: TermRuleRecord) -> TermRuleResponse:
        """把 draft 中的当前规则转换为 conflict payload 使用的 API 规则形态。"""

        category = next((item for item in store.categories if item.id == rule.category_id), None)
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
    def _require_category(store: TermRulesStore, category_id: str) -> None:
        if not any(category.id == category_id for category in store.categories):
            raise FileNotFoundError(f"分类不存在: {category_id}")

    @staticmethod
    def _find_rule(store: TermRulesStore, rule_id: str) -> TermRuleRecord:
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
        for rule in store.rules:
            if rule.source_term == source_term and rule.id != exclude_rule_id:
                raise ValueError(f"规则 source_term 已存在: {source_term}")

    def _ensure_no_conflicting_source_segments(self, store: TermRulesStore, proposal: TermRuleProposalRecord) -> None:
        """阻止同名 source term 但 segments 不一致的 create proposal 自动合并。"""

        proposed_segments = [segment.model_dump(mode="json") for segment in proposal.segments]
        for rule in store.rules:
            if rule.source_term != proposal.source_term:
                continue
            existing_segments = [segment.model_dump(mode="json") for segment in rule.segments]
            if existing_segments != proposed_segments:
                self._raise_conflict(
                    conflict_type="source_term_segments_conflict",
                    message="同一 source_term 已存在不同 segments，请手动处理 draft 冲突。",
                    proposal=proposal,
                    store=store,
                    target_rule=rule,
                    target_rule_id=rule.id,
                    metadata={
                        "existing_segments": existing_segments,
                        "proposed_segments": proposed_segments,
                    },
                )

    def _build_rule_record(
        self,
        *,
        rule_id: str,
        category_id: str,
        source_term: str,
        segments: list[TermRuleSegmentRecord],
        notes: str,
        apply_scope: RuleApplyScope = RuleApplyScope.BOTH,
        case_sensitive: bool = True,
        enabled: bool = True,
        priority: int = 100,
        created_at: Any | None = None,
    ) -> TermRuleRecord:
        return TermRuleRecord(
            id=rule_id,
            category_id=category_id,
            source_term=source_term,
            rule_mode=RuleMode.SIMPLE if len(segments) <= 2 else RuleMode.ADVANCED,
            apply_scope=apply_scope,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=int(priority),
            segments=segments,
            custom_html=render_segments_html(segments),
            custom_markdown=render_segments_markdown(segments),
            notes=notes,
            **({"created_at": created_at} if created_at is not None else {}),
        )

    @staticmethod
    def _build_segments(raw_segments: list[dict[str, Any]]) -> list[TermRuleSegmentRecord]:
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

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        proposal: TermRuleProposalRecord,
        trace_id: str | None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="term_rule_proposal",
            target_id=proposal.id,
            trace_id=trace_id or "",
            reason=proposal.review_comment,
        )

    def _current_default_version(self) -> str | None:
        try:
            detail = self.term_rule_set_version_service.get_set_detail(DEFAULT_TERM_RULE_SET_ID)
        except (FileNotFoundError, ValueError):
            return None
        return detail.default_version

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
