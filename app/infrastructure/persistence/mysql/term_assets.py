from __future__ import annotations

# app/infrastructure/persistence/mysql/term_assets.py: MySQL backend 的术语规则和翻译术语明细表 adapter。

import json
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.domains.term_rules.models import TermRulesStore
from app.domains.translation.models import (
    TranslationTermEntry,
    TranslationTermMatchTraceRecord,
    TranslationTermProposalChangeRecord,
    TranslationTermProposalRecord,
    TranslationTermProposalStatus,
    TranslationTermSetRecord,
    TranslationTermVersionStatus,
    TranslationTermVersionRecord,
    derive_translation_term_set_id,
    normalize_translation_source_term,
    utc_now,
)
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlTermRuleAssetRepository:
    """把发布的 Term Rule Set 版本投影到规范化 MySQL 明细表。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def replace_version(self, term_rule_set_id: str, version: str, store: TermRulesStore) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                for table in ("term_rule_segments", "term_rules", "term_rule_categories"):
                    cursor.execute(
                        f"DELETE FROM {table} WHERE term_rule_set_id = %s AND version = %s",
                        (term_rule_set_id, version),
                    )
                for category in store.categories:
                    cursor.execute(
                        """
                        INSERT INTO term_rule_categories
                            (term_rule_set_id, version, category_id, code, name, priority, enabled, description, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            term_rule_set_id,
                            version,
                            category.id,
                            category.code,
                            category.name,
                            category.priority,
                            int(category.enabled),
                            category.description,
                            category.created_at.isoformat(),
                            category.updated_at.isoformat(),
                        ),
                    )
                for rule in store.rules:
                    cursor.execute(
                        """
                        INSERT INTO term_rules
                            (term_rule_set_id, version, rule_id, category_id, source_term, rule_mode, apply_scope,
                             case_sensitive, enabled, priority, custom_html, custom_markdown, notes, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            term_rule_set_id,
                            version,
                            rule.id,
                            rule.category_id,
                            rule.source_term,
                            rule.rule_mode.value,
                            rule.apply_scope.value,
                            int(rule.case_sensitive),
                            int(rule.enabled),
                            rule.priority,
                            rule.custom_html,
                            rule.custom_markdown,
                            rule.notes,
                            rule.created_at.isoformat(),
                            rule.updated_at.isoformat(),
                        ),
                    )
                    for segment in sorted(rule.segments, key=lambda item: item.seq):
                        cursor.execute(
                            """
                            INSERT INTO term_rule_segments
                                (term_rule_set_id, version, rule_id, seq, segment_text, render_type)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                term_rule_set_id,
                                version,
                                rule.id,
                                segment.seq,
                                segment.segment_text,
                                segment.render_type.value,
                            ),
                        )


class MysqlTranslationTermRepository:
    """用 MySQL backend 保存和读取翻译术语版本。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_set(self, record: TranslationTermSetRecord) -> TranslationTermSetRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO translation_term_sets
                        (set_id, language_pair, default_version, draft_version, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        language_pair = VALUES(language_pair),
                        default_version = VALUES(default_version),
                        draft_version = VALUES(draft_version),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        record.set_id,
                        record.language_pair,
                        record.default_version,
                        record.draft_version,
                        self._iso(record.created_at),
                        self._iso(record.updated_at),
                    ),
                )
        return record

    def get_set(self, set_id: str) -> TranslationTermSetRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, default_version, draft_version, created_at, updated_at
                    FROM translation_term_sets
                    WHERE set_id = %s
                    """,
                    (set_id,),
                )
                row = cursor.fetchone()
        return self._load_set(row) if row is not None else None

    def get_set_by_language_pair(self, language_pair: str) -> TranslationTermSetRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, default_version, draft_version, created_at, updated_at
                    FROM translation_term_sets
                    WHERE language_pair = %s
                    """,
                    (language_pair,),
                )
                row = cursor.fetchone()
        return self._load_set(row) if row is not None else None

    def list_sets(self) -> list[TranslationTermSetRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, default_version, draft_version, created_at, updated_at
                    FROM translation_term_sets
                    ORDER BY language_pair, set_id
                    """
                )
                rows = cursor.fetchall()
        return [self._load_set(row) for row in rows]

    def save_version(self, record: TranslationTermVersionRecord) -> TranslationTermVersionRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO translation_term_versions
                        (set_id, language_pair, version, status, snapshot_hash, term_count,
                         published_by, published_at, release_note, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        language_pair = VALUES(language_pair),
                        status = VALUES(status),
                        snapshot_hash = VALUES(snapshot_hash),
                        term_count = VALUES(term_count),
                        published_by = VALUES(published_by),
                        published_at = VALUES(published_at),
                        release_note = VALUES(release_note),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        record.set_id,
                        record.language_pair,
                        record.version,
                        record.status,
                        record.snapshot_hash,
                        record.term_count,
                        record.published_by,
                        self._optional_iso(record.published_at),
                        record.release_note,
                        self._iso(record.created_at),
                        self._iso(record.updated_at),
                    ),
                )
        return record

    def get_version(self, set_id: str, version: str) -> TranslationTermVersionRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, version, status, snapshot_hash, term_count,
                           published_by, published_at, release_note, created_at, updated_at
                    FROM translation_term_versions
                    WHERE set_id = %s AND version = %s
                    """,
                    (set_id, version),
                )
                row = cursor.fetchone()
        return self._load_version(row) if row is not None else None

    def list_versions(self, set_id: str) -> list[TranslationTermVersionRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, version, status, snapshot_hash, term_count,
                           published_by, published_at, release_note, created_at, updated_at
                    FROM translation_term_versions
                    WHERE set_id = %s
                    ORDER BY created_at, version
                    """,
                    (set_id,),
                )
                rows = cursor.fetchall()
        return [self._load_version(row) for row in rows]

    def replace_version(
        self,
        language_pair: str,
        version: str,
        entries: list[TranslationTermEntry],
        snapshot_hash: str,
        *,
        status: TranslationTermVersionStatus = "published",
        make_default: bool | None = None,
        set_draft: bool = False,
        clear_draft: bool = False,
        published_by: str | None = None,
        published_at: datetime | None = None,
        release_note: str | None = None,
    ) -> None:
        now = utc_now()
        set_id = derive_translation_term_set_id(language_pair)
        existing_set = self.get_set_by_language_pair(language_pair)
        resolved_set_id = existing_set.set_id if existing_set is not None else set_id
        default_version = existing_set.default_version if existing_set is not None else None
        draft_version = existing_set.draft_version if existing_set is not None else None
        if status == "published" and (make_default is True or (make_default is None and not default_version)):
            default_version = version
        if set_draft:
            draft_version = version
        if clear_draft:
            draft_version = None
        self.save_set(
            TranslationTermSetRecord(
                set_id=resolved_set_id,
                language_pair=language_pair,
                default_version=default_version,
                draft_version=draft_version,
                created_at=existing_set.created_at if existing_set is not None else now,
                updated_at=now,
            )
        )
        self.save_version(
            TranslationTermVersionRecord(
                set_id=resolved_set_id,
                language_pair=language_pair,
                version=version,
                status=status,
                snapshot_hash=snapshot_hash,
                term_count=len(entries),
                published_by=published_by,
                published_at=published_at,
                release_note=release_note,
                created_at=now,
                updated_at=now,
            )
        )
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM translation_terms WHERE set_id = %s AND version = %s",
                    (resolved_set_id, version),
                )
                for index, entry in enumerate(entries, start=1):
                    resolved_entry = self._entry_for_version(
                        entry,
                        set_id=resolved_set_id,
                        language_pair=language_pair,
                        version=version,
                    )
                    cursor.execute(
                        """
                        INSERT INTO translation_terms
                            (set_id, language_pair, version, seq, source_term, normalized_source_term, target_term,
                             recommended_translations, forbidden_translations, synonyms,
                             case_sensitive, status, priority, project, content_type, tags, maintainer,
                             domain, category, note, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            resolved_entry.set_id,
                            resolved_entry.language_pair,
                            resolved_entry.version,
                            index,
                            resolved_entry.source_term,
                            resolved_entry.normalized_source_term,
                            resolved_entry.target_term,
                            self._json_list(resolved_entry.recommended_translations),
                            self._json_list(resolved_entry.forbidden_translations),
                            self._json_list(resolved_entry.synonyms),
                            int(resolved_entry.case_sensitive),
                            resolved_entry.status,
                            resolved_entry.priority,
                            resolved_entry.project,
                            resolved_entry.content_type,
                            self._json_list(resolved_entry.tags),
                            resolved_entry.maintainer,
                            resolved_entry.domain,
                            resolved_entry.category,
                            resolved_entry.note,
                            self._iso(resolved_entry.created_at),
                            self._iso(resolved_entry.updated_at),
                        ),
                    )

    def load_version(self, language_pair: str, version: str) -> list[TranslationTermEntry]:
        term_set = self.get_set_by_language_pair(language_pair)
        if term_set is None:
            return []
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT set_id, language_pair, version, source_term, normalized_source_term, target_term,
                           recommended_translations, forbidden_translations, synonyms,
                           case_sensitive, status, priority, project, content_type, tags, maintainer,
                           domain, category, note, created_at, updated_at
                    FROM translation_terms
                    WHERE set_id = %s AND version = %s
                    ORDER BY seq
                    """,
                    (term_set.set_id, version),
                )
                rows = cursor.fetchall()
        return [self._load_entry(row) for row in rows]

    def has_version(self, language_pair: str, version: str) -> bool:
        term_set = self.get_set_by_language_pair(language_pair)
        if term_set is None:
            return False
        return self.get_version(term_set.set_id, version) is not None

    def save_proposal(self, proposal: TranslationTermProposalRecord) -> TranslationTermProposalRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO translation_term_proposals
                        (id, status, submitted_by, source_job_id, source_file_id,
                         observed_translation_term_set_id, observed_translation_term_version,
                         reviewed_by, reviewed_at, review_note,
                         published_translation_term_set_id, published_translation_term_version,
                         published_at, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        submitted_by = VALUES(submitted_by),
                        source_job_id = VALUES(source_job_id),
                        source_file_id = VALUES(source_file_id),
                        observed_translation_term_set_id = VALUES(observed_translation_term_set_id),
                        observed_translation_term_version = VALUES(observed_translation_term_version),
                        reviewed_by = VALUES(reviewed_by),
                        reviewed_at = VALUES(reviewed_at),
                        review_note = VALUES(review_note),
                        published_translation_term_set_id = VALUES(published_translation_term_set_id),
                        published_translation_term_version = VALUES(published_translation_term_version),
                        published_at = VALUES(published_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        proposal.id,
                        proposal.status,
                        proposal.submitted_by,
                        proposal.source_job_id,
                        proposal.source_file_id,
                        proposal.observed_translation_term_set_id,
                        proposal.observed_translation_term_version,
                        proposal.reviewed_by,
                        self._optional_iso(proposal.reviewed_at),
                        proposal.review_note,
                        proposal.published_translation_term_set_id,
                        proposal.published_translation_term_version,
                        self._optional_iso(proposal.published_at),
                        self._iso(proposal.created_at),
                        self._iso(proposal.updated_at),
                    ),
                )
                cursor.execute("DELETE FROM translation_term_proposal_changes WHERE proposal_id = %s", (proposal.id,))
                for change in sorted(proposal.changes, key=lambda item: item.seq):
                    cursor.execute(
                        """
                        INSERT INTO translation_term_proposal_changes
                            (proposal_id, seq, action, source_term, normalized_source_term, target_term,
                             case_sensitive, term_status, priority, domain, category, note, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            change.proposal_id,
                            change.seq,
                            change.action,
                            change.source_term,
                            change.normalized_source_term,
                            change.target_term,
                            self._optional_bool_int(change.case_sensitive),
                            change.status,
                            change.priority,
                            change.domain,
                            change.category,
                            change.note,
                            self._iso(change.created_at),
                            self._iso(change.updated_at),
                        ),
                    )
        return proposal

    def get_proposal(self, proposal_id: str) -> TranslationTermProposalRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, status, submitted_by, source_job_id, source_file_id,
                           observed_translation_term_set_id, observed_translation_term_version,
                           reviewed_by, reviewed_at, review_note,
                           published_translation_term_set_id, published_translation_term_version,
                           published_at, created_at, updated_at
                    FROM translation_term_proposals
                    WHERE id = %s
                    """,
                    (proposal_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                changes = self._load_proposal_changes(cursor, proposal_id)
        return self._load_proposal(row, changes)

    def list_proposals(
        self,
        *,
        status: TranslationTermProposalStatus | None = None,
        submitted_by: str | None = None,
    ) -> list[TranslationTermProposalRecord]:
        conditions: list[str] = []
        params: list[Any] = []
        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        if submitted_by is not None:
            conditions.append("submitted_by = %s")
            params.append(submitted_by)
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id, status, submitted_by, source_job_id, source_file_id,
                           observed_translation_term_set_id, observed_translation_term_version,
                           reviewed_by, reviewed_at, review_note,
                           published_translation_term_set_id, published_translation_term_version,
                           published_at, created_at, updated_at
                    FROM translation_term_proposals
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    """,
                    tuple(params),
                )
                rows = cursor.fetchall()
                return [
                    self._load_proposal(row, self._load_proposal_changes(cursor, row["id"]))
                    for row in rows
                ]

    def append_match_trace(self, trace: TranslationTermMatchTraceRecord) -> TranslationTermMatchTraceRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO translation_term_match_traces
                        (id, job_id, segment_id, batch_id, translation_term_set_id, translation_term_version,
                         source_term, target_term, match_start, match_end, context_snippet,
                         injected_to_glossary, provider_trace_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        trace.id,
                        trace.job_id,
                        trace.segment_id,
                        trace.batch_id,
                        trace.translation_term_set_id,
                        trace.translation_term_version,
                        trace.source_term,
                        trace.target_term,
                        trace.match_start,
                        trace.match_end,
                        trace.context_snippet,
                        int(trace.injected_to_glossary),
                        trace.provider_trace_id,
                        self._iso(trace.created_at),
                    ),
                )
        return trace

    def list_match_traces(self, job_id: str) -> list[TranslationTermMatchTraceRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, job_id, segment_id, batch_id, translation_term_set_id, translation_term_version,
                           source_term, target_term, match_start, match_end, context_snippet,
                           injected_to_glossary, provider_trace_id, created_at
                    FROM translation_term_match_traces
                    WHERE job_id = %s
                    ORDER BY created_at, id
                    """,
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [self._load_trace(row) for row in rows]

    def _load_proposal_changes(self, cursor: Any, proposal_id: str) -> tuple[TranslationTermProposalChangeRecord, ...]:
        cursor.execute(
            """
            SELECT proposal_id, seq, action, source_term, normalized_source_term, target_term,
                   case_sensitive, term_status, priority, domain, category, note, created_at, updated_at
            FROM translation_term_proposal_changes
            WHERE proposal_id = %s
            ORDER BY seq
            """,
            (proposal_id,),
        )
        return tuple(self._load_proposal_change(row) for row in cursor.fetchall())

    @staticmethod
    def _entry_for_version(
        entry: TranslationTermEntry,
        *,
        set_id: str,
        language_pair: str,
        version: str,
    ) -> TranslationTermEntry:
        return replace(
            entry,
            set_id=set_id,
            language_pair=language_pair,
            version=version,
            normalized_source_term=entry.normalized_source_term or normalize_translation_source_term(entry.source_term),
        )

    @staticmethod
    def _load_set(row: dict[str, Any]) -> TranslationTermSetRecord:
        return TranslationTermSetRecord(
            set_id=row["set_id"],
            language_pair=row["language_pair"],
            default_version=row["default_version"],
            draft_version=row["draft_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_version(row: dict[str, Any]) -> TranslationTermVersionRecord:
        return TranslationTermVersionRecord(
            set_id=row["set_id"],
            language_pair=row["language_pair"],
            version=row["version"],
            status=row["status"],
            snapshot_hash=row["snapshot_hash"],
            term_count=int(row["term_count"]),
            published_by=row["published_by"],
            published_at=row["published_at"],
            release_note=row["release_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_entry(row: dict[str, Any]) -> TranslationTermEntry:
        return TranslationTermEntry(
            set_id=row["set_id"],
            language_pair=row["language_pair"],
            version=row["version"],
            source_term=row["source_term"],
            normalized_source_term=row["normalized_source_term"],
            target_term=row["target_term"],
            recommended_translations=MysqlTranslationTermRepository._load_json_list(row.get("recommended_translations")),
            forbidden_translations=MysqlTranslationTermRepository._load_json_list(row.get("forbidden_translations")),
            synonyms=MysqlTranslationTermRepository._load_json_list(row.get("synonyms")),
            case_sensitive=bool(row["case_sensitive"]),
            status=row["status"],
            priority=int(row["priority"]),
            project=row.get("project"),
            content_type=row.get("content_type"),
            tags=MysqlTranslationTermRepository._load_json_list(row.get("tags")),
            maintainer=row.get("maintainer"),
            domain=row["domain"],
            category=row["category"],
            note=row["note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_proposal(
        row: dict[str, Any],
        changes: tuple[TranslationTermProposalChangeRecord, ...],
    ) -> TranslationTermProposalRecord:
        return TranslationTermProposalRecord(
            id=row["id"],
            status=row["status"],
            submitted_by=row["submitted_by"],
            source_job_id=row["source_job_id"],
            source_file_id=row["source_file_id"],
            observed_translation_term_set_id=row["observed_translation_term_set_id"],
            observed_translation_term_version=row["observed_translation_term_version"],
            reviewed_by=row["reviewed_by"],
            reviewed_at=row["reviewed_at"],
            review_note=row["review_note"],
            published_translation_term_set_id=row["published_translation_term_set_id"],
            published_translation_term_version=row["published_translation_term_version"],
            published_at=row["published_at"],
            changes=changes,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_proposal_change(row: dict[str, Any]) -> TranslationTermProposalChangeRecord:
        return TranslationTermProposalChangeRecord(
            proposal_id=row["proposal_id"],
            seq=int(row["seq"]),
            action=row["action"],
            source_term=row["source_term"],
            normalized_source_term=row["normalized_source_term"],
            target_term=row["target_term"],
            case_sensitive=bool(row["case_sensitive"]) if row["case_sensitive"] is not None else None,
            status=row["term_status"],
            priority=int(row["priority"]) if row["priority"] is not None else None,
            domain=row["domain"],
            category=row["category"],
            note=row["note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_trace(row: dict[str, Any]) -> TranslationTermMatchTraceRecord:
        return TranslationTermMatchTraceRecord(
            id=row["id"],
            job_id=row["job_id"],
            segment_id=row["segment_id"],
            batch_id=row["batch_id"],
            translation_term_set_id=row["translation_term_set_id"],
            translation_term_version=row["translation_term_version"],
            source_term=row["source_term"],
            target_term=row["target_term"],
            match_start=row["match_start"],
            match_end=row["match_end"],
            context_snippet=row["context_snippet"],
            injected_to_glossary=bool(row["injected_to_glossary"]),
            provider_trace_id=row["provider_trace_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _iso(value: Any) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    @classmethod
    def _optional_iso(cls, value: Any | None) -> str | None:
        return cls._iso(value) if value is not None else None

    @staticmethod
    def _json_list(values: tuple[str, ...] | list[str]) -> str:
        return json.dumps([item for item in values if item], ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _load_json_list(value: Any) -> tuple[str, ...]:
        if not value:
            return ()
        try:
            decoded = json.loads(str(value))
        except json.JSONDecodeError:
            return ()
        if not isinstance(decoded, list):
            return ()
        return tuple(str(item).strip() for item in decoded if str(item).strip())

    @staticmethod
    def _optional_bool_int(value: bool | None) -> int | None:
        return int(value) if value is not None else None
