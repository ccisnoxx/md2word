from __future__ import annotations

# app/domains/translation/term_version_service.py: 管理翻译术语 seed 导入和只读版本解析。

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.domains.translation.models import TermVersionSnapshot, TranslationTermEntry, normalize_translation_source_term
from app.domains.translation.repository import TranslationTermRepositoryProtocol


TranslationTermImportDedupeMode = Literal["reject", "keep_first"]


@dataclass(frozen=True, slots=True)
class TranslationTermImportDuplicate:
    """CSV 导入时被发现的规范化重复项。"""

    row_number: int
    kept_row_number: int
    language_pair: str
    version: str
    source_term: str
    normalized_source_term: str


@dataclass(frozen=True, slots=True)
class TranslationTermImportReport:
    """翻译术语 CSV seed/admin 导入报告。"""

    dedupe: TranslationTermImportDedupeMode
    total_rows: int = 0
    imported_rows: int = 0
    duplicate_rows: int = 0
    duplicates: tuple[TranslationTermImportDuplicate, ...] = field(default_factory=tuple)


class TermVersionService:
    """翻译术语版本加载服务；MySQL repository 存在时 SQL 是运行时唯一真源。"""

    def __init__(
        self,
        terms_path: Path,
        *,
        default_term_version_id: str,
        repository: TranslationTermRepositoryProtocol | None = None,
    ) -> None:
        self.terms_path = terms_path
        self.default_term_version_id = default_term_version_id
        self.repository = repository

    def resolve_for_job(self, term_version_id: str | None, *, language_pair: str | None) -> TermVersionSnapshot | None:
        """解析 job 绑定的术语版本；非翻译任务且未显式传入时不绑定。"""

        normalized_language_pair = self._normalize_optional_text(language_pair)
        normalized_id = self._normalize_optional_text(term_version_id)
        if normalized_id is None:
            if normalized_language_pair is None:
                return None
            normalized_id = self.default_term_version_id
        return self.load_version(normalized_id, language_pair=normalized_language_pair)

    def load_version(self, term_version_id: str, *, language_pair: str | None = None) -> TermVersionSnapshot:
        """按 `language_pair@version` 或独立 version 加载 CSV 中的术语版本。"""

        requested_pair, requested_version = self._parse_term_version_id(term_version_id, language_pair=language_pair)
        entries = self._load_version_entries(requested_pair, requested_version)
        if not entries:
            raise FileNotFoundError(f"术语版本不存在: {requested_pair}@{requested_version}")
        canonical_id = self._term_version_id(requested_pair, requested_version)
        return TermVersionSnapshot(
            term_version_id=canonical_id,
            language_pair=requested_pair,
            version=requested_version,
            snapshot_hash=self._snapshot_hash(entries),
            entries=tuple(entries),
        )

    def bootstrap_repository_from_csv_if_empty(self) -> None:
        """MySQL mode 下把 CSV seed 导入 SQL；已有默认版本时不再读取 CSV。"""

        if self.repository is None:
            return
        default_pair, default_version = self._parse_term_version_id(self.default_term_version_id, language_pair=None)
        if self.repository.has_version(default_pair, default_version):
            return
        entries, _report = self.load_csv_entries_for_import(dedupe="reject")
        entries_by_version: dict[tuple[str, str], list[TranslationTermEntry]] = {}
        for entry in entries:
            entries_by_version.setdefault((entry.language_pair, entry.version), []).append(entry)
        for (language_pair, version), entries in entries_by_version.items():
            if self.repository.has_version(language_pair, version):
                continue
            self.repository.replace_version(language_pair, version, entries, self._snapshot_hash(entries))

    def load_csv_entries_for_import(
        self,
        *,
        dedupe: TranslationTermImportDedupeMode = "reject",
    ) -> tuple[list[TranslationTermEntry], TranslationTermImportReport]:
        """读取 CSV seed/import 文件；默认严格拒绝规范化重复项。"""

        if dedupe not in {"reject", "keep_first"}:
            raise ValueError(f"不支持的翻译术语去重策略: {dedupe}")
        entries, report = self._load_entries_from_csv(dedupe=dedupe)
        if report.duplicate_rows and dedupe == "reject":
            duplicate = report.duplicates[0]
            raise ValueError(
                "翻译术语 CSV 存在重复 normalized_source_term: "
                f"{duplicate.language_pair}@{duplicate.version}/{duplicate.normalized_source_term}"
            )
        return entries, report

    def _load_version_entries(self, language_pair: str, version: str) -> list[TranslationTermEntry]:
        if self.repository is not None:
            entries = self.repository.load_version(language_pair, version)
            if not entries:
                raise FileNotFoundError(f"术语版本不存在: {language_pair}@{version}")
            return entries
        entries, _report = self.load_csv_entries_for_import(dedupe="reject")
        return [
            entry
            for entry in entries
            if entry.language_pair == language_pair and entry.version == version
        ]

    def _load_entries_from_csv(
        self,
        *,
        dedupe: TranslationTermImportDedupeMode,
    ) -> tuple[list[TranslationTermEntry], TranslationTermImportReport]:
        if not self.terms_path.exists():
            raise FileNotFoundError(f"术语表文件不存在: {self.terms_path}")
        with self.terms_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            self._validate_headers(reader.fieldnames)
            entries: list[TranslationTermEntry] = []
            duplicates: list[TranslationTermImportDuplicate] = []
            seen: dict[tuple[str, str, str], int] = {}
            total_rows = 0
            for row_number, row in enumerate(reader, start=2):
                total_rows += 1
                entry = self._entry_from_row(row)
                if entry is not None:
                    key = (entry.language_pair, entry.version, entry.normalized_source_term)
                    kept_row_number = seen.get(key)
                    if kept_row_number is not None:
                        duplicates.append(
                            TranslationTermImportDuplicate(
                                row_number=row_number,
                                kept_row_number=kept_row_number,
                                language_pair=entry.language_pair,
                                version=entry.version,
                                source_term=entry.source_term,
                                normalized_source_term=entry.normalized_source_term,
                            )
                        )
                        if dedupe == "keep_first":
                            continue
                    else:
                        seen[key] = row_number
                    entries.append(entry)
        report = TranslationTermImportReport(
            dedupe=dedupe,
            total_rows=total_rows,
            imported_rows=len(entries),
            duplicate_rows=len(duplicates),
            duplicates=tuple(duplicates),
        )
        return entries, report

    def _entry_from_row(self, row: dict[str, str | None]) -> TranslationTermEntry | None:
        language_pair = self._required_row_text(row, "language_pair")
        source_term = self._required_row_text(row, "source_term")
        target_term = self._required_row_text(row, "target_term")
        version = self._required_row_text(row, "version")
        if language_pair.startswith("#"):
            return None
        return TranslationTermEntry(
            language_pair=language_pair,
            source_term=source_term,
            normalized_source_term=normalize_translation_source_term(source_term),
            target_term=target_term,
            version=version,
        )

    def _parse_term_version_id(self, term_version_id: str, *, language_pair: str | None) -> tuple[str, str]:
        normalized_id = term_version_id.strip()
        if "@" in normalized_id:
            raw_pair, raw_version = normalized_id.split("@", 1)
            pair = raw_pair.strip()
            version = raw_version.strip()
        else:
            if language_pair is None:
                raise ValueError("term_version_id 未包含 language_pair，且当前任务无法推断语言方向。")
            pair = language_pair
            version = normalized_id
        if not pair or not version:
            raise ValueError("term_version_id 必须使用 language_pair@version 或非空 version。")
        if language_pair is not None and pair != language_pair:
            raise ValueError(f"术语版本语言方向不匹配: expected={language_pair} actual={pair}")
        return pair, version

    def _validate_headers(self, fieldnames: list[str] | None) -> None:
        required = {"language_pair", "source_term", "target_term", "version"}
        actual = set(fieldnames or [])
        missing = sorted(required - actual)
        if missing:
            raise ValueError(f"术语表 CSV 缺少字段: {', '.join(missing)}")

    def _required_row_text(self, row: dict[str, str | None], key: str) -> str:
        value = (row.get(key) or "").strip()
        if not value:
            raise ValueError(f"术语表 CSV 字段不能为空: {key}")
        return value

    def _snapshot_hash(self, entries: list[TranslationTermEntry]) -> str:
        payload = [
            {
                "language_pair": entry.language_pair,
                "source_term": entry.source_term,
                "target_term": entry.target_term,
                "version": entry.version,
            }
            for entry in entries
        ]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _term_version_id(language_pair: str, version: str) -> str:
        return f"{language_pair}@{version}"
