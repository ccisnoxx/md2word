from __future__ import annotations

# app/domains/translation/term_version_service.py: 从最小 CSV 术语表加载只读术语版本。

import csv
import hashlib
import json
from pathlib import Path

from app.domains.translation.models import TermVersionSnapshot, TranslationTermEntry


class TermVersionService:
    """P1 术语版本只读加载服务；在线编辑和冲突合并后置。"""

    def __init__(
        self,
        terms_path: Path,
        *,
        default_term_version_id: str,
    ) -> None:
        self.terms_path = terms_path
        self.default_term_version_id = default_term_version_id

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
        entries = [
            entry
            for entry in self._load_entries()
            if entry.language_pair == requested_pair and entry.version == requested_version
        ]
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

    def _load_entries(self) -> list[TranslationTermEntry]:
        if not self.terms_path.exists():
            raise FileNotFoundError(f"术语表文件不存在: {self.terms_path}")
        with self.terms_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            self._validate_headers(reader.fieldnames)
            entries: list[TranslationTermEntry] = []
            for row in reader:
                entry = self._entry_from_row(row)
                if entry is not None:
                    entries.append(entry)
        return entries

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
