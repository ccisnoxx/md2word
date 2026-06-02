from __future__ import annotations

# app/domains/translation/term_set_version_service.py: 编排 Translation Term Set 草稿、发布、默认指针和归档。

import csv
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import timedelta, timezone
from io import StringIO
from typing import Any

from app.domains.audit.models import ActorContext
from app.domains.translation.models import (
    TranslationTermEntry,
    TranslationTermProposalChangeRecord,
    TranslationTermSetRecord,
    TranslationTermVersionRecord,
    derive_translation_term_set_id,
    normalize_translation_source_term,
    utc_now,
)
from app.domains.translation.repository import TranslationTermRepositoryProtocol


DRAFT_VERSION = "draft"
SHANGHAI_TZ = timezone(timedelta(hours=8))
TRANSLATION_TERM_IMPORT_TARGETS = {"draft", "seed"}
TRANSLATION_TERM_IMPORT_DEDUPE_MODES = {"reject", "keep_first"}
TRANSLATION_TERM_CSV_COLUMNS = (
    "language_pair",
    "source_term",
    "target_term",
    "version",
    "case_sensitive",
    "status",
    "priority",
    "domain",
    "category",
    "note",
)


@dataclass(frozen=True, slots=True)
class TranslationTermValidationFinding:
    """Translation Term Set 发布或变更校验中的一条错误或 warning。"""

    code: str
    message: str
    normalized_source_term: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationTermValidationReport:
    """Translation Term Set 校验报告；errors 阻断发布，warnings 可继续发布。"""

    errors: tuple[TranslationTermValidationFinding, ...] = ()
    warnings: tuple[TranslationTermValidationFinding, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class TranslationTermDraft:
    """当前 Translation Term Set draft 的条目和校验结果。"""

    set_id: str
    language_pair: str
    version: str
    base_version: str | None
    snapshot_hash: str
    entries: tuple[TranslationTermEntry, ...]
    validation: TranslationTermValidationReport


@dataclass(frozen=True, slots=True)
class TranslationTermPublishResult:
    """Translation Term Set 发布结果。"""

    version: TranslationTermVersionRecord
    entries: tuple[TranslationTermEntry, ...]
    validation: TranslationTermValidationReport


@dataclass(frozen=True, slots=True)
class TranslationTermCsvDuplicate:
    """CSV 导入时被发现或丢弃的规范化重复项。"""

    row_number: int
    kept_row_number: int
    source_term: str
    normalized_source_term: str


@dataclass(frozen=True, slots=True)
class TranslationTermCsvImportReport:
    """Translation Term Set CSV 导入报告。"""

    dedupe: str
    total_rows: int = 0
    imported_rows: int = 0
    duplicate_rows: int = 0
    duplicates: tuple[TranslationTermCsvDuplicate, ...] = ()


@dataclass(frozen=True, slots=True)
class TranslationTermSetImportResult:
    """Translation Term Set CSV 导入执行结果。"""

    target: str
    set_id: str
    language_pair: str
    version: str
    term_count: int
    snapshot_hash: str
    validation: TranslationTermValidationReport
    import_report: TranslationTermCsvImportReport


@dataclass(frozen=True, slots=True)
class TranslationTermSetExportResult:
    """Translation Term Set CSV 导出结果。"""

    set_id: str
    language_pair: str
    version: str
    csv_text: str
    exported_at: Any
    exported_by: str | None


class TranslationTermSetVersionService:
    """管理单 language_pair Translation Term Set 的 draft/published/archived 版本。"""

    def __init__(
        self,
        repository: TranslationTermRepositoryProtocol,
        audit_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.audit_service = audit_service

    def get_draft(self, set_id: str) -> TranslationTermDraft:
        """没有 draft 时从当前默认 published 版本复制。"""

        term_set = self._require_set(set_id)
        version_record, entries = self._ensure_draft(term_set)
        return self._draft_response(term_set, version_record, entries)

    def update_draft(
        self,
        set_id: str,
        entries: list[TranslationTermEntry],
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermDraft:
        """替换当前 draft 条目；仅 errors 阻断，warnings 留给发布预览。"""

        term_set = self._require_set(set_id)
        self._ensure_draft(term_set)
        normalized_entries = self._entries_for_version(entries, term_set=term_set, version=DRAFT_VERSION)
        validation = self.validate_entries(normalized_entries, base_entries=self._default_entries(term_set))
        if validation.errors:
            raise ValueError(self._validation_error_message(validation))
        snapshot_hash = self._snapshot_hash(normalized_entries)
        self.repository.replace_version(
            term_set.language_pair,
            DRAFT_VERSION,
            normalized_entries,
            snapshot_hash,
            status="draft",
            make_default=False,
            set_draft=True,
        )
        refreshed_set = self._require_set(set_id)
        version_record = self._require_version(refreshed_set, DRAFT_VERSION)
        draft = self._draft_response(refreshed_set, version_record, normalized_entries)
        self._record_audit(
            actor=actor,
            action="translation_term_set.draft_update",
            target_id=f"{set_id}@{DRAFT_VERSION}",
            trace_id=trace_id,
        )
        return draft

    def import_csv_text(
        self,
        set_id: str,
        csv_text: str,
        *,
        target: str,
        dedupe: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermSetImportResult:
        """把 CSV 导入当前 draft，或在空集时作为 seed/default 初始化。"""

        if target not in TRANSLATION_TERM_IMPORT_TARGETS:
            raise ValueError(f"不支持的 Translation Term Set 导入目标: {target}")
        if dedupe not in TRANSLATION_TERM_IMPORT_DEDUPE_MODES:
            raise ValueError(f"不支持的 Translation Term Set 去重策略: {dedupe}")
        entries, report = self._parse_csv_text(csv_text, dedupe=dedupe)
        if report.duplicate_rows and dedupe == "reject":
            duplicate = report.duplicates[0]
            raise ValueError(f"Translation Term Set CSV 存在重复 normalized_source_term: {duplicate.normalized_source_term}")
        if target == "seed":
            result = self._import_seed_entries(set_id, entries, report, actor=actor, trace_id=trace_id)
        else:
            result = self._import_draft_entries(set_id, entries, report, actor=actor, trace_id=trace_id)
        self._record_audit(
            actor=actor,
            action="translation_term_set.import",
            target_id=f"{result.set_id}@{result.version}",
            trace_id=trace_id,
            reason=f"target={target}; dedupe={dedupe}",
        )
        return result

    def export_csv(
        self,
        set_id: str,
        *,
        version: str | None = None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermSetExportResult:
        """导出指定或默认 Translation Term Set 版本为 CSV。"""

        term_set = self._require_set(set_id)
        version_record = self._require_default_version(term_set) if version is None else self._require_version(term_set, version)
        entries = self.repository.load_version(term_set.language_pair, version_record.version)
        csv_text = self._dump_csv(entries)
        exported_at = utc_now()
        exported_by = actor.actor_id if actor is not None else None
        self._record_audit(
            actor=actor,
            action="translation_term_set.export",
            target_id=f"{term_set.set_id}@{version_record.version}",
            trace_id=trace_id,
            reason="format=csv",
        )
        return TranslationTermSetExportResult(
            set_id=term_set.set_id,
            language_pair=term_set.language_pair,
            version=version_record.version,
            csv_text=csv_text,
            exported_at=exported_at,
            exported_by=exported_by,
        )

    def publish_draft(
        self,
        set_id: str,
        *,
        make_default: bool,
        published_by: str | None = None,
        release_note: str | None = None,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermPublishResult:
        """发布当前 draft；版本号由后端生成，draft 发布后清除 draft 指针。"""

        term_set = self._require_set(set_id)
        _draft_record, draft_entries = self._ensure_draft(term_set)
        validation = self.validate_entries(draft_entries, base_entries=self._default_entries(term_set))
        if validation.errors:
            raise ValueError(self._validation_error_message(validation))
        version = self._next_version(term_set.set_id)
        published_entries = self._entries_for_version(draft_entries, term_set=term_set, version=version)
        snapshot_hash = self._snapshot_hash(published_entries)
        published_at = utc_now()
        self.repository.replace_version(
            term_set.language_pair,
            version,
            published_entries,
            snapshot_hash,
            status="published",
            make_default=make_default,
            clear_draft=True,
            published_by=published_by,
            published_at=published_at,
            release_note=release_note,
        )
        version_record = self._require_version(self._require_set(set_id), version)
        result = TranslationTermPublishResult(
            version=version_record,
            entries=tuple(published_entries),
            validation=validation,
        )
        self._record_audit(
            actor=actor,
            action="translation_term_set.publish",
            target_id=f"{set_id}@{version}",
            trace_id=trace_id,
            reason=release_note,
        )
        return result

    def set_default_version(
        self,
        set_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermVersionRecord:
        """只允许 published 版本成为默认版本。"""

        term_set = self._require_set(set_id)
        version_record = self._require_version(term_set, version)
        if version_record.status != "published":
            raise ValueError("Translation Term Set 默认版本只能指向 published 版本。")
        self.repository.save_set(
            replace(
                term_set,
                default_version=version,
                updated_at=utc_now(),
            )
        )
        self._record_audit(
            actor=actor,
            action="translation_term_set.set_default",
            target_id=f"{set_id}@{version}",
            trace_id=trace_id,
        )
        return version_record

    def rollback(
        self,
        set_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermVersionRecord:
        """第一版 rollback 只切默认指针，不生成新版本。"""

        version_record = self.set_default_version(set_id, version)
        self._record_audit(
            actor=actor,
            action="translation_term_set.rollback",
            target_id=f"{set_id}@{version}",
            trace_id=trace_id,
        )
        return version_record

    def archive(
        self,
        set_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationTermVersionRecord:
        """归档历史 published 版本；当前默认版本不能归档。"""

        term_set = self._require_set(set_id)
        if term_set.default_version == version:
            raise ValueError("当前默认 Translation Term Set 版本不能归档。")
        version_record = self._require_version(term_set, version)
        if version_record.status == "archived":
            return version_record
        if version_record.status != "published":
            raise ValueError("只有 published Translation Term Set 版本可以归档。")
        archived = replace(version_record, status="archived", updated_at=utc_now())
        saved = self.repository.save_version(archived)
        self._record_audit(
            actor=actor,
            action="translation_term_set.archive",
            target_id=f"{set_id}@{version}",
            trace_id=trace_id,
        )
        return saved

    def _import_draft_entries(
        self,
        set_id: str,
        entries: list[TranslationTermEntry],
        report: TranslationTermCsvImportReport,
        *,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> TranslationTermSetImportResult:
        term_set = self._require_set(set_id)
        self._require_language_pair(entries, term_set.language_pair)
        draft = self.update_draft(set_id, entries, actor=None, trace_id=None)
        return TranslationTermSetImportResult(
            target="draft",
            set_id=draft.set_id,
            language_pair=draft.language_pair,
            version=draft.version,
            term_count=len(draft.entries),
            snapshot_hash=draft.snapshot_hash,
            validation=draft.validation,
            import_report=report,
        )

    def _import_seed_entries(
        self,
        set_id: str,
        entries: list[TranslationTermEntry],
        report: TranslationTermCsvImportReport,
        *,
        actor: ActorContext | None,
        trace_id: str | None,
    ) -> TranslationTermSetImportResult:
        if not entries:
            raise ValueError("Translation Term Set CSV 没有可导入术语。")
        language_pair = entries[0].language_pair
        self._require_language_pair(entries, language_pair)
        expected_set_id = derive_translation_term_set_id(language_pair)
        if set_id.strip() != expected_set_id:
            raise ValueError(f"Translation Term Set ID 与 CSV language_pair 不匹配: expected={expected_set_id} actual={set_id}")
        existing_set = self.repository.get_set(expected_set_id)
        if existing_set is not None and existing_set.default_version:
            raise ValueError("seed 初始化只能在 Translation Term Set 缺少默认版本时执行。")
        version = self._require_single_csv_version(entries)
        term_set = existing_set or TranslationTermSetRecord(set_id=expected_set_id, language_pair=language_pair)
        normalized_entries = self._entries_for_version(entries, term_set=term_set, version=version)
        validation = self.validate_entries(normalized_entries)
        if validation.errors:
            raise ValueError(self._validation_error_message(validation))
        snapshot_hash = self._snapshot_hash(normalized_entries)
        self.repository.replace_version(
            language_pair,
            version,
            normalized_entries,
            snapshot_hash,
            status="published",
            make_default=True,
            published_by=actor.actor_id if actor is not None else "seed",
            published_at=utc_now(),
            release_note="import seed initialization",
        )
        saved_set = self._require_set(expected_set_id)
        version_record = self._require_version(saved_set, version)
        return TranslationTermSetImportResult(
            target="seed",
            set_id=saved_set.set_id,
            language_pair=saved_set.language_pair,
            version=version_record.version,
            term_count=version_record.term_count,
            snapshot_hash=version_record.snapshot_hash,
            validation=validation,
            import_report=report,
        )

    def validate_entries(
        self,
        entries: list[TranslationTermEntry],
        *,
        base_entries: list[TranslationTermEntry] | None = None,
    ) -> TranslationTermValidationReport:
        """校验 draft/publish 条目；重复和空值阻断，重叠和无变化只 warning。"""

        errors: list[TranslationTermValidationFinding] = []
        warnings: list[TranslationTermValidationFinding] = []
        seen: dict[str, str] = {}
        normalized_terms: list[tuple[str, str]] = []
        for entry in entries:
            source_term = entry.source_term.strip()
            target_term = entry.target_term.strip()
            normalized_source_term = normalize_translation_source_term(source_term)
            if not source_term:
                errors.append(TranslationTermValidationFinding("empty_source_term", "source_term 不能为空。"))
                continue
            if not target_term:
                errors.append(
                    TranslationTermValidationFinding(
                        "empty_target_term",
                        f"target_term 不能为空: {source_term}",
                        normalized_source_term,
                    )
                )
            if entry.status not in {"active", "disabled"}:
                errors.append(
                    TranslationTermValidationFinding(
                        "invalid_term_status",
                        f"术语状态只能是 active 或 disabled: {entry.status}",
                        normalized_source_term,
                    )
                )
            previous = seen.get(normalized_source_term)
            if previous is not None:
                errors.append(
                    TranslationTermValidationFinding(
                        "duplicate_normalized_source_term",
                        f"normalized_source_term 重复: {normalized_source_term}",
                        normalized_source_term,
                    )
                )
            else:
                seen[normalized_source_term] = source_term
            if entry.status == "active":
                normalized_terms.append((normalized_source_term, source_term))

        for index, (left_key, left_source) in enumerate(normalized_terms):
            for right_key, right_source in normalized_terms[index + 1:]:
                if left_key == right_key:
                    continue
                if left_key in right_key or right_key in left_key:
                    warnings.append(
                        TranslationTermValidationFinding(
                            "overlapping_source_term",
                            f"术语存在重叠: {left_source} / {right_source}",
                            left_key if len(left_key) <= len(right_key) else right_key,
                        )
                    )

        if base_entries is not None and self._entries_payload(entries) == self._entries_payload(base_entries):
            warnings.append(
                TranslationTermValidationFinding(
                    "no_actual_changes",
                    "draft 与当前默认版本没有实际变化。",
                )
            )
        return TranslationTermValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    def validate_changes(
        self,
        base_entries: list[TranslationTermEntry],
        changes: list[TranslationTermProposalChangeRecord],
        *,
        observed_version: str | None = None,
        current_version: str | None = None,
    ) -> TranslationTermValidationReport:
        """校验 proposal change 可否应用；不存在的 update/delete 阻断。"""

        errors: list[TranslationTermValidationFinding] = []
        warnings: list[TranslationTermValidationFinding] = []
        existing_by_key = {entry.normalized_source_term: entry for entry in base_entries}
        for change in changes:
            source_term = change.source_term.strip()
            normalized_source_term = normalize_translation_source_term(source_term)
            if not source_term:
                errors.append(TranslationTermValidationFinding("empty_source_term", "source_term 不能为空。"))
                continue
            if change.action == "add":
                if normalized_source_term in existing_by_key:
                    errors.append(
                        TranslationTermValidationFinding(
                            "add_existing_term",
                            f"新增术语已存在: {normalized_source_term}",
                            normalized_source_term,
                        )
                    )
                if not (change.target_term or "").strip():
                    errors.append(
                        TranslationTermValidationFinding(
                            "empty_target_term",
                            f"target_term 不能为空: {source_term}",
                            normalized_source_term,
                        )
                    )
            elif change.action == "update":
                target = existing_by_key.get(normalized_source_term)
                if target is None:
                    errors.append(
                        TranslationTermValidationFinding(
                            "update_missing_term",
                            f"update 目标术语不存在: {normalized_source_term}",
                            normalized_source_term,
                        )
                    )
                elif not self._change_updates_anything(target, change):
                    warnings.append(
                        TranslationTermValidationFinding(
                            "no_actual_changes",
                            f"update 没有实际变化: {normalized_source_term}",
                            normalized_source_term,
                        )
                    )
            elif change.action == "delete":
                if normalized_source_term not in existing_by_key:
                    errors.append(
                        TranslationTermValidationFinding(
                            "delete_missing_term",
                            f"delete 目标术语不存在: {normalized_source_term}",
                            normalized_source_term,
                        )
                    )
            else:
                errors.append(
                    TranslationTermValidationFinding(
                        "invalid_change_action",
                        f"不支持的术语变更动作: {change.action}",
                        normalized_source_term,
                    )
                )
        if observed_version is not None and current_version is not None and observed_version != current_version:
            warnings.append(
                TranslationTermValidationFinding(
                    "stale_observed_version",
                    f"证据版本和当前版本不同: observed={observed_version} current={current_version}",
                )
            )
        return TranslationTermValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    def _parse_csv_text(
        self,
        csv_text: str,
        *,
        dedupe: str,
    ) -> tuple[list[TranslationTermEntry], TranslationTermCsvImportReport]:
        reader = csv.DictReader(StringIO(csv_text), skipinitialspace=True)
        self._validate_csv_headers(reader.fieldnames)
        entries: list[TranslationTermEntry] = []
        duplicates: list[TranslationTermCsvDuplicate] = []
        seen: dict[tuple[str, str], int] = {}
        total_rows = 0
        for row_number, row in enumerate(reader, start=2):
            total_rows += 1
            entry = self._entry_from_csv_row(row)
            key = (entry.language_pair, entry.normalized_source_term)
            kept_row_number = seen.get(key)
            if kept_row_number is not None:
                duplicates.append(
                    TranslationTermCsvDuplicate(
                        row_number=row_number,
                        kept_row_number=kept_row_number,
                        source_term=entry.source_term,
                        normalized_source_term=entry.normalized_source_term,
                    )
                )
                if dedupe == "keep_first":
                    continue
            else:
                seen[key] = row_number
            entries.append(entry)
        report = TranslationTermCsvImportReport(
            dedupe=dedupe,
            total_rows=total_rows,
            imported_rows=len(entries),
            duplicate_rows=len(duplicates),
            duplicates=tuple(duplicates),
        )
        return entries, report

    def _entry_from_csv_row(self, row: dict[str, str | None]) -> TranslationTermEntry:
        language_pair = self._required_csv_text(row, "language_pair")
        source_term = self._required_csv_text(row, "source_term")
        target_term = self._required_csv_text(row, "target_term")
        version = self._required_csv_text(row, "version")
        status = (row.get("status") or "active").strip() or "active"
        if status not in {"active", "disabled"}:
            raise ValueError(f"Translation Term Set CSV status 只能是 active 或 disabled: {status}")
        return TranslationTermEntry(
            language_pair=language_pair,
            source_term=source_term,
            normalized_source_term=normalize_translation_source_term(source_term),
            target_term=target_term,
            version=version,
            case_sensitive=self._csv_bool(row.get("case_sensitive")),
            status=status,
            priority=self._csv_int(row.get("priority"), default=0),
            domain=self._optional_csv_text(row.get("domain")),
            category=self._optional_csv_text(row.get("category")),
            note=(row.get("note") or "").strip(),
        )

    def _dump_csv(self, entries: list[TranslationTermEntry]) -> str:
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(TRANSLATION_TERM_CSV_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "language_pair": entry.language_pair,
                    "source_term": entry.source_term,
                    "target_term": entry.target_term,
                    "version": entry.version,
                    "case_sensitive": "true" if entry.case_sensitive else "false",
                    "status": entry.status,
                    "priority": str(entry.priority),
                    "domain": entry.domain or "",
                    "category": entry.category or "",
                    "note": entry.note,
                }
            )
        return buffer.getvalue()

    def _ensure_draft(self, term_set: TranslationTermSetRecord) -> tuple[TranslationTermVersionRecord, list[TranslationTermEntry]]:
        if term_set.draft_version:
            draft_record = self._require_version(term_set, term_set.draft_version)
            if draft_record.status != "draft":
                raise ValueError("Translation Term Set draft 指针指向了非 draft 版本。")
            return draft_record, self.repository.load_version(term_set.language_pair, draft_record.version)

        default_record = self._require_default_version(term_set)
        default_entries = self.repository.load_version(term_set.language_pair, default_record.version)
        draft_entries = self._entries_for_version(default_entries, term_set=term_set, version=DRAFT_VERSION)
        snapshot_hash = self._snapshot_hash(draft_entries)
        self.repository.replace_version(
            term_set.language_pair,
            DRAFT_VERSION,
            draft_entries,
            snapshot_hash,
            status="draft",
            make_default=False,
            set_draft=True,
        )
        refreshed_set = self._require_set(term_set.set_id)
        return self._require_version(refreshed_set, DRAFT_VERSION), draft_entries

    def _draft_response(
        self,
        term_set: TranslationTermSetRecord,
        version_record: TranslationTermVersionRecord,
        entries: list[TranslationTermEntry],
    ) -> TranslationTermDraft:
        return TranslationTermDraft(
            set_id=term_set.set_id,
            language_pair=term_set.language_pair,
            version=version_record.version,
            base_version=term_set.default_version,
            snapshot_hash=version_record.snapshot_hash,
            entries=tuple(entries),
            validation=self.validate_entries(entries, base_entries=self._default_entries(term_set)),
        )

    def _require_set(self, set_id: str) -> TranslationTermSetRecord:
        normalized_id = set_id.strip()
        record = self.repository.get_set(normalized_id)
        if record is None:
            raise FileNotFoundError(f"Translation Term Set 不存在: {normalized_id}")
        expected_id = derive_translation_term_set_id(record.language_pair)
        if record.set_id != expected_id:
            raise ValueError(f"Translation Term Set ID 与 language_pair 不匹配: {record.set_id}")
        return record

    def _require_version(self, term_set: TranslationTermSetRecord, version: str) -> TranslationTermVersionRecord:
        record = self.repository.get_version(term_set.set_id, version)
        if record is None:
            raise FileNotFoundError(f"Translation Term Set 版本不存在: {term_set.set_id}@{version}")
        return record

    def _require_default_version(self, term_set: TranslationTermSetRecord) -> TranslationTermVersionRecord:
        if not term_set.default_version:
            raise FileNotFoundError(f"Translation Term Set 缺少默认版本: {term_set.set_id}")
        record = self._require_version(term_set, term_set.default_version)
        if record.status != "published":
            raise ValueError("Translation Term Set 默认指针指向了非 published 版本。")
        return record

    def _default_entries(self, term_set: TranslationTermSetRecord) -> list[TranslationTermEntry]:
        if not term_set.default_version:
            return []
        return self.repository.load_version(term_set.language_pair, term_set.default_version)

    def _next_version(self, set_id: str) -> str:
        prefix = utc_now().astimezone(SHANGHAI_TZ).strftime("%Y%m%d-%H%M%S-")
        max_suffix = 0
        for record in self.repository.list_versions(set_id):
            if not record.version.startswith(prefix):
                continue
            suffix = record.version.removeprefix(prefix)
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
        return f"{prefix}{max_suffix + 1:03d}"

    @staticmethod
    def _entries_for_version(
        entries: list[TranslationTermEntry],
        *,
        term_set: TranslationTermSetRecord,
        version: str,
    ) -> list[TranslationTermEntry]:
        now = utc_now()
        return [
            replace(
                entry,
                set_id=term_set.set_id,
                language_pair=term_set.language_pair,
                version=version,
                source_term=entry.source_term.strip(),
                normalized_source_term=normalize_translation_source_term(entry.source_term),
                target_term=entry.target_term.strip(),
                updated_at=now,
            )
            for entry in entries
        ]

    @staticmethod
    def _entries_payload(entries: list[TranslationTermEntry]) -> list[dict[str, Any]]:
        return [
            {
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
            for entry in entries
        ]

    def _snapshot_hash(self, entries: list[TranslationTermEntry]) -> str:
        encoded = json.dumps(self._entries_payload(entries), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _change_updates_anything(
        target: TranslationTermEntry,
        change: TranslationTermProposalChangeRecord,
    ) -> bool:
        checks = {
            "target_term": change.target_term,
            "case_sensitive": change.case_sensitive,
            "status": change.status,
            "priority": change.priority,
            "domain": change.domain,
            "category": change.category,
            "note": change.note,
        }
        return any(value is not None and getattr(target, key) != value for key, value in checks.items())

    @staticmethod
    def _validation_error_message(report: TranslationTermValidationReport) -> str:
        return "Translation Term Set 校验失败: " + "; ".join(error.message for error in report.errors)

    @staticmethod
    def _validate_csv_headers(fieldnames: list[str] | None) -> None:
        required = {"language_pair", "source_term", "target_term", "version"}
        actual = set(fieldnames or [])
        missing = sorted(required - actual)
        if missing:
            raise ValueError(f"Translation Term Set CSV 缺少字段: {', '.join(missing)}")

    @staticmethod
    def _required_csv_text(row: dict[str, str | None], key: str) -> str:
        value = (row.get(key) or "").strip()
        if not value:
            raise ValueError(f"Translation Term Set CSV 字段不能为空: {key}")
        return value

    @staticmethod
    def _optional_csv_text(value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None

    @staticmethod
    def _csv_bool(value: str | None) -> bool:
        normalized = (value or "").strip().lower()
        if not normalized:
            return False
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
        raise ValueError(f"Translation Term Set CSV 布尔字段无效: {value}")

    @staticmethod
    def _csv_int(value: str | None, *, default: int) -> int:
        normalized = (value or "").strip()
        if not normalized:
            return default
        try:
            return int(normalized)
        except ValueError as exc:
            raise ValueError(f"Translation Term Set CSV 整数字段无效: {value}") from exc

    @staticmethod
    def _require_language_pair(entries: list[TranslationTermEntry], language_pair: str) -> None:
        mismatch = next((entry.language_pair for entry in entries if entry.language_pair != language_pair), None)
        if mismatch is not None:
            raise ValueError(f"Translation Term Set CSV language_pair 不匹配: expected={language_pair} actual={mismatch}")

    @staticmethod
    def _require_single_csv_version(entries: list[TranslationTermEntry]) -> str:
        versions = {entry.version for entry in entries}
        if len(versions) != 1:
            raise ValueError("Translation Term Set seed 导入 CSV 必须只包含一个 version。")
        return next(iter(versions))

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
            target_type="translation_term_set",
            target_id=target_id,
            trace_id=trace_id or "",
            reason=reason,
        )
