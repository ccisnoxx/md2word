# File: app/domains/translation/proposals_service.py
# Purpose: 编排翻译术语 proposal 提交、审核和合并到 draft。

from __future__ import annotations

from dataclasses import dataclass, replace
from http import HTTPStatus
from typing import Any, Literal
from uuid import uuid4

from app.domains.audit.models import ActorContext
from app.domains.translation.models import (
    TranslationTermEntry,
    TranslationTermProposalChangeRecord,
    TranslationTermProposalRecord,
    TranslationTermProposalStatus,
    TranslationTermSetRecord,
    normalize_translation_source_term,
    utc_now,
)
from app.domains.translation.repository import TranslationTermRepositoryProtocol
from app.domains.translation.schemas import TranslationTermProposalCompatibilityFindingResponse
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService


class TranslationTermProposalConflictError(RuntimeError):
    """当前 draft 与 proposal 证据版本冲突，不能自动合并。"""

    def __init__(self, conflicts: list[TranslationTermProposalCompatibilityFindingResponse]) -> None:
        """保存结构化冲突，供单条和批量审核接口复用。"""

        self.conflicts = tuple(conflicts)
        super().__init__("; ".join(conflict.message for conflict in conflicts))


@dataclass(frozen=True, slots=True)
class TranslationTermProposalBulkReviewItem:
    """描述批量审核中单条 Translation Term Proposal 的结果。"""

    proposal_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | dict[str, Any] | None = None
    proposal: TranslationTermProposalRecord | None = None


class TranslationTermProposalService:
    """维护 Translation Term Proposal 从 operator 提交到 admin 发布的闭环。"""

    def __init__(
        self,
        *,
        repository: TranslationTermRepositoryProtocol,
        term_set_version_service: TranslationTermSetVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.term_set_version_service = term_set_version_service
        self.audit_service = audit_service

    def create_proposal(
        self,
        *,
        language_pair: str,
        changes: list[dict[str, Any]],
        submitted_by: str,
        source_job_id: str | None,
        source_file_id: str | None,
        observed_translation_term_set_id: str | None = None,
        observed_translation_term_version: str | None = None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermProposalRecord:
        """创建 pending proposal，并保留批量 add/update/delete changes。"""

        term_set = self._resolve_term_set(
            language_pair=language_pair,
            observed_set_id=observed_translation_term_set_id,
        )
        resolved_observed_version = (
            self._normalize_optional_text(observed_translation_term_version)
            or term_set.default_version
        )
        parsed_changes = self._build_changes("pending", changes)
        base_entries = self._entries_for_version(term_set, resolved_observed_version)
        validation = self.term_set_version_service.validate_changes(
            base_entries,
            parsed_changes,
            observed_version=resolved_observed_version,
            current_version=term_set.default_version,
        )
        if validation.errors:
            raise ValueError(self._validation_error_message(validation))
        proposal_id = f"ttp_{uuid4().hex[:12]}"
        proposal_changes = tuple(replace(change, proposal_id=proposal_id) for change in parsed_changes)
        now = utc_now()
        proposal = TranslationTermProposalRecord(
            id=proposal_id,
            status="pending",
            submitted_by=self._normalize_required_text(submitted_by, "submitted_by"),
            source_job_id=self._normalize_optional_text(source_job_id),
            source_file_id=self._normalize_optional_text(source_file_id),
            observed_translation_term_set_id=term_set.set_id,
            observed_translation_term_version=resolved_observed_version,
            changes=proposal_changes,
            created_at=now,
            updated_at=now,
        )
        saved = self.repository.save_proposal(proposal)
        self._record_audit(actor=actor, action="translation_term_proposal.create", proposal=saved, trace_id=trace_id)
        return saved

    def list_proposals(
        self,
        *,
        status: TranslationTermProposalStatus | None = None,
        submitted_by: str | None = None,
    ) -> list[TranslationTermProposalRecord]:
        """按状态和提交人查询 Translation Term Proposals。"""

        return self.repository.list_proposals(status=status, submitted_by=submitted_by)

    def get_proposal(self, proposal_id: str) -> TranslationTermProposalRecord:
        """读取单条 Translation Term Proposal。"""

        proposal = self.repository.get_proposal(proposal_id)
        if proposal is None:
            raise FileNotFoundError(f"翻译术语建议不存在: {proposal_id}")
        return proposal

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_note: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermProposalRecord:
        """把 pending proposal 合并到当前 Translation Term Set draft。"""

        proposal = self._require_pending(proposal_id)
        term_set = self._term_set_for_proposal(proposal)
        draft = self.term_set_version_service.get_draft(term_set.set_id)
        self._raise_conflicts_if_any(proposal, term_set, list(draft.entries))
        updated_entries = self._apply_changes(list(draft.entries), list(proposal.changes))
        self.term_set_version_service.update_draft(
            term_set.set_id,
            updated_entries,
            actor=actor,
            trace_id=trace_id,
        )
        now = utc_now()
        approved = replace(
            proposal,
            status="approved",
            reviewed_by=self._normalize_required_text(reviewed_by, "reviewed_by"),
            reviewed_at=now,
            review_note=self._normalize_optional_text(review_note),
            updated_at=now,
        )
        saved = self.repository.save_proposal(approved)
        self._record_audit(
            actor=actor,
            action="translation_term_proposal.approve",
            proposal=saved,
            trace_id=trace_id,
            reason=review_note,
        )
        return saved

    def bulk_approve_proposals(
        self,
        proposal_ids: list[str],
        *,
        reviewed_by: str,
        review_note: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> list[TranslationTermProposalBulkReviewItem]:
        """逐条复用单条 approve 语义，返回允许部分成功的批量结果。"""

        return self._bulk_review_proposals(
            action="approve",
            proposal_ids=proposal_ids,
            reviewed_by=reviewed_by,
            review_note=review_note,
            actor=actor,
            trace_id=trace_id,
        )

    def approve_and_publish_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_note: str | None,
        release_note: str | None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermProposalRecord:
        """审核 proposal，发布当前 draft，并把新版本设为默认版本。"""

        approved = self.approve_proposal(
            proposal_id,
            reviewed_by=reviewed_by,
            review_note=review_note,
            actor=actor,
            trace_id=trace_id,
        )
        term_set = self._term_set_for_proposal(approved)
        published = self.term_set_version_service.publish_draft(
            term_set.set_id,
            make_default=True,
            published_by=reviewed_by,
            release_note=self._normalize_optional_text(release_note)
            or f"publish approved translation term proposal {approved.id}",
            actor=actor,
            trace_id=trace_id,
        )
        now = utc_now()
        saved = self.repository.save_proposal(
            replace(
                approved,
                status="published",
                published_translation_term_set_id=term_set.set_id,
                published_translation_term_version=published.version.version,
                published_at=now,
                updated_at=now,
            )
        )
        self._record_audit(
            actor=actor,
            action="translation_term_proposal.approve_and_publish",
            proposal=saved,
            trace_id=trace_id,
            reason=release_note or review_note,
        )
        return saved

    def reject_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        review_note: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermProposalRecord:
        """拒绝 pending proposal，拒绝原因必填。"""

        proposal = self._require_pending(proposal_id)
        now = utc_now()
        rejected = replace(
            proposal,
            status="rejected",
            reviewed_by=self._normalize_required_text(reviewed_by, "reviewed_by"),
            reviewed_at=now,
            review_note=self._normalize_required_text(review_note, "review_note"),
            updated_at=now,
        )
        saved = self.repository.save_proposal(rejected)
        self._record_audit(
            actor=actor,
            action="translation_term_proposal.reject",
            proposal=saved,
            trace_id=trace_id,
            reason=review_note,
        )
        return saved

    def bulk_reject_proposals(
        self,
        proposal_ids: list[str],
        *,
        reviewed_by: str,
        review_note: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> list[TranslationTermProposalBulkReviewItem]:
        """逐条复用单条 reject 语义，返回允许部分成功的批量结果。"""

        return self._bulk_review_proposals(
            action="reject",
            proposal_ids=proposal_ids,
            reviewed_by=reviewed_by,
            review_note=review_note,
            actor=actor,
            trace_id=trace_id,
        )

    def _bulk_review_proposals(
        self,
        *,
        action: Literal["approve", "reject"],
        proposal_ids: list[str],
        reviewed_by: str,
        review_note: str | None,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> list[TranslationTermProposalBulkReviewItem]:
        """按请求顺序逐条执行审核动作，单条失败不阻断后续 proposal。"""

        normalized_ids = self._normalize_bulk_proposal_ids(proposal_ids)
        items: list[TranslationTermProposalBulkReviewItem] = []
        for proposal_id in normalized_ids:
            try:
                if action == "approve":
                    proposal = self.approve_proposal(
                        proposal_id,
                        reviewed_by=reviewed_by,
                        review_note=review_note,
                        actor=actor,
                        trace_id=trace_id,
                    )
                else:
                    proposal = self.reject_proposal(
                        proposal_id,
                        reviewed_by=reviewed_by,
                        review_note=review_note or "",
                        actor=actor,
                        trace_id=trace_id,
                    )
            except TranslationTermProposalConflictError as exc:
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
    def _build_bulk_success(proposal: TranslationTermProposalRecord) -> TranslationTermProposalBulkReviewItem:
        """构造批量审核中单条成功 proposal 的 service 结果。"""

        return TranslationTermProposalBulkReviewItem(
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
    ) -> TranslationTermProposalBulkReviewItem:
        """构造批量审核中单条失败 proposal 的 service 结果。"""

        return TranslationTermProposalBulkReviewItem(
            proposal_id=proposal_id,
            ok=False,
            status_code=status_code,
            error_code=error_code,
            detail=detail,
        )

    def _build_bulk_conflict_failure(
        self,
        proposal_id: str,
        exc: TranslationTermProposalConflictError,
    ) -> TranslationTermProposalBulkReviewItem:
        """把结构化冲突保留到批量 item 的 detail 中。"""

        return self._build_bulk_failure(
            proposal_id,
            status_code=HTTPStatus.CONFLICT.value,
            error_code="translation_term_proposal_conflict",
            detail=self._conflict_detail(exc),
        )

    @staticmethod
    def _conflict_detail(exc: TranslationTermProposalConflictError) -> dict[str, Any]:
        """构造单条和批量接口共用的结构化 conflict detail。"""

        return {
            "code": "translation_term_proposal_conflict",
            "message": "proposal 与当前 draft 存在冲突，请重新核对后处理。",
            "conflicts": [conflict.model_dump(mode="json") for conflict in exc.conflicts],
        }

    def _resolve_term_set(
        self,
        *,
        language_pair: str,
        observed_set_id: str | None,
    ) -> TranslationTermSetRecord:
        normalized_set_id = self._normalize_optional_text(observed_set_id)
        if normalized_set_id is not None:
            term_set = self.repository.get_set(normalized_set_id)
        else:
            normalized_pair = self._normalize_required_text(language_pair, "language_pair")
            term_set = self.repository.get_set_by_language_pair(normalized_pair)
        if term_set is None:
            raise FileNotFoundError("Translation Term Set 不存在。")
        return term_set

    def _term_set_for_proposal(self, proposal: TranslationTermProposalRecord) -> TranslationTermSetRecord:
        if proposal.observed_translation_term_set_id is None:
            raise ValueError("proposal 缺少 observed_translation_term_set_id。")
        term_set = self.repository.get_set(proposal.observed_translation_term_set_id)
        if term_set is None:
            raise FileNotFoundError(f"Translation Term Set 不存在: {proposal.observed_translation_term_set_id}")
        return term_set

    def _entries_for_version(
        self,
        term_set: TranslationTermSetRecord,
        version: str | None,
    ) -> list[TranslationTermEntry]:
        if not version:
            return []
        return self.repository.load_version(term_set.language_pair, version)

    def _raise_conflicts_if_any(
        self,
        proposal: TranslationTermProposalRecord,
        term_set: TranslationTermSetRecord,
        draft_entries: list[TranslationTermEntry],
    ) -> None:
        draft_by_key = {entry.normalized_source_term: entry for entry in draft_entries}
        observed_entries = self._entries_for_version(term_set, proposal.observed_translation_term_version)
        observed_by_key = {entry.normalized_source_term: entry for entry in observed_entries}
        conflicts: list[TranslationTermProposalCompatibilityFindingResponse] = []
        for change in proposal.changes:
            key = normalize_translation_source_term(change.source_term)
            draft_entry = draft_by_key.get(key)
            observed_entry = observed_by_key.get(key)
            if change.action == "add":
                if draft_entry is not None:
                    conflicts.append(
                        self._proposal_conflict_finding(
                            code="add_existing_term",
                            message=f"新增术语已存在于当前 draft: {key}",
                            normalized_source_term=key,
                            action=change.action,
                            current_entry=self._entry_payload(draft_entry),
                            observed_entry=self._entry_payload(observed_entry) if observed_entry else None,
                        )
                    )
                continue
            if draft_entry is None:
                conflicts.append(
                    self._proposal_conflict_finding(
                        code="missing_target_term",
                        message=f"{change.action} 目标术语不存在于当前 draft: {key}",
                        normalized_source_term=key,
                        action=change.action,
                        current_entry=None,
                        observed_entry=self._entry_payload(observed_entry) if observed_entry else None,
                    )
                )
                continue
            if observed_entry is not None and self._entry_payload(draft_entry) != self._entry_payload(observed_entry):
                conflicts.append(
                    self._proposal_conflict_finding(
                        code="stale_target_term",
                        message=f"{change.action} 目标术语已被其他变更修改: {key}",
                        normalized_source_term=key,
                        action=change.action,
                        current_entry=self._entry_payload(draft_entry),
                        observed_entry=self._entry_payload(observed_entry),
                    )
                )
        if conflicts:
            raise TranslationTermProposalConflictError(conflicts)

    @staticmethod
    def _proposal_conflict_finding(
        *,
        code: str,
        message: str,
        normalized_source_term: str | None = None,
        action: str | None = None,
        current_entry: dict[str, Any] | None = None,
        observed_entry: dict[str, Any] | None = None,
    ) -> TranslationTermProposalCompatibilityFindingResponse:
        """创建 approve 阻断冲突的 compatibility-style finding。"""

        return TranslationTermProposalCompatibilityFindingResponse(
            severity="conflict",
            code=code,
            message=message,
            normalized_source_term=normalized_source_term,
            action=action,
            current_entry=current_entry,
            observed_entry=observed_entry,
        )

    def _apply_changes(
        self,
        entries: list[TranslationTermEntry],
        changes: list[TranslationTermProposalChangeRecord],
    ) -> list[TranslationTermEntry]:
        by_key = {entry.normalized_source_term: entry for entry in entries}
        ordered_keys = [entry.normalized_source_term for entry in entries]
        for change in changes:
            key = normalize_translation_source_term(change.source_term)
            if change.action == "add":
                by_key[key] = TranslationTermEntry(
                    language_pair=entries[0].language_pair if entries else "",
                    version="draft",
                    source_term=change.source_term,
                    target_term=self._normalize_required_text(change.target_term or "", "target_term"),
                    case_sensitive=bool(change.case_sensitive) if change.case_sensitive is not None else False,
                    status=change.status or "active",
                    priority=int(change.priority or 0),
                    domain=change.domain,
                    category=change.category,
                    note=change.note or "",
                )
                ordered_keys.append(key)
            elif change.action == "update":
                target = by_key[key]
                by_key[key] = replace(
                    target,
                    target_term=change.target_term if change.target_term is not None else target.target_term,
                    case_sensitive=change.case_sensitive if change.case_sensitive is not None else target.case_sensitive,
                    status=change.status if change.status is not None else target.status,
                    priority=change.priority if change.priority is not None else target.priority,
                    domain=change.domain if change.domain is not None else target.domain,
                    category=change.category if change.category is not None else target.category,
                    note=change.note if change.note is not None else target.note,
                    updated_at=utc_now(),
                )
            elif change.action == "delete":
                by_key.pop(key, None)
                ordered_keys = [item for item in ordered_keys if item != key]
        return [by_key[key] for key in ordered_keys if key in by_key]

    def _build_changes(
        self,
        proposal_id: str,
        raw_changes: list[dict[str, Any]],
    ) -> list[TranslationTermProposalChangeRecord]:
        if not raw_changes:
            raise ValueError("changes 必须是非空数组。")
        changes: list[TranslationTermProposalChangeRecord] = []
        for index, raw_change in enumerate(raw_changes, start=1):
            action = self._normalize_required_text(str(raw_change.get("action", "")), "action")
            if action not in {"add", "update", "delete"}:
                raise ValueError(f"不支持的翻译术语 proposal action: {action}")
            source_term = self._normalize_required_text(str(raw_change.get("source_term", "")), "source_term")
            target_term = self._normalize_optional_text(raw_change.get("target_term"))
            status = self._normalize_optional_text(raw_change.get("status"))
            if status is not None and status not in {"active", "disabled"}:
                raise ValueError(f"不支持的翻译术语状态: {status}")
            changes.append(
                TranslationTermProposalChangeRecord(
                    proposal_id=proposal_id,
                    seq=index,
                    action=action,
                    source_term=source_term,
                    target_term=target_term,
                    case_sensitive=raw_change.get("case_sensitive"),
                    status=status,
                    priority=raw_change.get("priority"),
                    domain=self._normalize_optional_text(raw_change.get("domain")),
                    category=self._normalize_optional_text(raw_change.get("category")),
                    note=self._normalize_optional_text(raw_change.get("note")),
                )
            )
        return changes

    def _require_pending(self, proposal_id: str) -> TranslationTermProposalRecord:
        proposal = self.get_proposal(proposal_id)
        if proposal.status != "pending":
            raise ValueError("只有 pending proposal 可以审核。")
        return proposal

    @staticmethod
    def _entry_payload(entry: TranslationTermEntry) -> dict[str, Any]:
        return {
            "source_term": entry.source_term.strip(),
            "normalized_source_term": normalize_translation_source_term(entry.source_term),
            "target_term": entry.target_term.strip(),
            "case_sensitive": bool(entry.case_sensitive),
            "status": entry.status,
            "priority": int(entry.priority),
            "domain": entry.domain,
            "category": entry.category,
            "note": entry.note,
        }

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        proposal: TranslationTermProposalRecord,
        trace_id: str | None,
        reason: str | None = None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="translation_term_proposal",
            target_id=proposal.id,
            trace_id=trace_id or "",
            reason=reason or proposal.review_note,
        )

    @staticmethod
    def _validation_error_message(report: Any) -> str:
        return "Translation Term Proposal 校验失败: " + "; ".join(error.message for error in report.errors)

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: Any | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
