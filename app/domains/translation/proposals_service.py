from __future__ import annotations

# app/domains/translation/proposals_service.py: 编排翻译术语 proposal 提交、审核和合并到 draft。

from dataclasses import replace
from typing import Any
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
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService


class TranslationTermProposalConflictError(RuntimeError):
    """当前 draft 与 proposal 证据版本冲突，不能自动合并。"""

    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = tuple(conflicts)
        super().__init__("; ".join(conflicts))


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
        conflicts: list[str] = []
        for change in proposal.changes:
            key = normalize_translation_source_term(change.source_term)
            draft_entry = draft_by_key.get(key)
            observed_entry = observed_by_key.get(key)
            if change.action == "add":
                if draft_entry is not None:
                    conflicts.append(f"add 目标术语已存在于当前 draft: {key}")
                continue
            if draft_entry is None:
                conflicts.append(f"{change.action} 目标术语不存在于当前 draft: {key}")
                continue
            if observed_entry is not None and self._entry_payload(draft_entry) != self._entry_payload(observed_entry):
                conflicts.append(f"{change.action} 目标术语已被其他变更修改: {key}")
        if conflicts:
            raise TranslationTermProposalConflictError(conflicts)

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
