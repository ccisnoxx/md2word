from __future__ import annotations

# app/domains/translation/document_ir_translator.py: 只翻译 DocumentIR 文本节点并保持结构字段稳定。

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Protocol

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.domains.translation.models import (
    TermVersionSnapshot,
    TranslationTermEntry,
    TranslationTermMatchTraceRecord,
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTextItem,
    normalize_translation_source_term,
)
from app.domains.translation.provider import TranslationProvider


_TRACE_CONTEXT_RADIUS = 40
_TRACE_CONTEXT_MAX_CHARS = 120


class DocumentIRTranslationError(RuntimeError):
    """翻译 provider 调用或返回结构异常时抛出的领域错误。"""


class TranslationCallRecorder(Protocol):
    """DocumentIR 翻译过程的审计回调端口。"""

    def record_success(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult,
        *,
        duration_ms: int,
    ) -> None: ...

    def record_failure(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        *,
        error: Exception,
        duration_ms: int,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _TextTarget:
    item_id: str
    block_id: str
    field: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class _TermMatch:
    entry: TranslationTermEntry
    item_id: str
    item_index: int
    match_start: int
    match_end: int
    context_snippet: str
    term_index: int

    @property
    def matched_length(self) -> int:
        return self.match_end - self.match_start


class DocumentIRTranslationService:
    """DocumentIR 文本翻译服务；不让 AI 接触结构、资产或样式信息。"""

    def __init__(self, provider: TranslationProvider) -> None:
        self.provider = provider

    def translate(
        self,
        document_ir: DocumentIR,
        *,
        term_version: TermVersionSnapshot | None,
        language_pair: str = "en2zh",
        call_recorder: TranslationCallRecorder | None = None,
    ) -> DocumentIR:
        """返回翻译后的 DocumentIR 副本；blocks/assets 数量和顺序保持不变。"""

        translated = document_ir.model_copy(deep=True)
        targets, items = self._extract_items(translated)
        if not items:
            return translated
        matched_terms, term_traces = self._match_request_terms(
            items=items,
            term_version=term_version,
            language_pair=language_pair,
            job_id=document_ir.metadata.job_id or "",
        )
        request = TranslationProviderRequest(
            language_pair=language_pair,
            source_language=self._source_language(language_pair),
            target_language=self._target_language(language_pair),
            items=tuple(items),
            terms=matched_terms,
            term_traces=term_traces,
        )
        started_at = time.perf_counter()
        result: TranslationProviderResult | None = None
        try:
            result = self.provider.translate(request)
            replacements = self._validate_result(items, result)
            self._apply_replacements(translated, targets, replacements)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if call_recorder is not None:
                call_recorder.record_failure(request, result, error=exc, duration_ms=duration_ms)
            raise DocumentIRTranslationError(str(exc)) from exc
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if call_recorder is not None:
            call_recorder.record_success(request, result, duration_ms=duration_ms)
        translated.metadata.document_language = self._target_document_language(language_pair)
        return translated

    def _match_request_terms(
        self,
        *,
        items: list[TranslationTextItem],
        term_version: TermVersionSnapshot | None,
        language_pair: str,
        job_id: str,
    ) -> tuple[tuple[TranslationTermEntry, ...], tuple[TranslationTermMatchTraceRecord, ...]]:
        if term_version is None:
            return (), ()
        matches: list[_TermMatch] = []
        for item_index, item in enumerate(items):
            item_matches: list[_TermMatch] = []
            for term_index, entry in enumerate(term_version.entries):
                if entry.language_pair != language_pair or entry.status != "active":
                    continue
                pattern = self._build_term_pattern(entry)
                if pattern is None:
                    continue
                for match in pattern.finditer(item.text):
                    item_matches.append(
                        _TermMatch(
                            entry=entry,
                            item_id=item.id,
                            item_index=item_index,
                            match_start=match.start(),
                            match_end=match.end(),
                            context_snippet=self._context_snippet(item.text, match.start(), match.end()),
                            term_index=term_index,
                        )
                    )
            matches.extend(self._select_non_overlapping_matches(item_matches))
        if not matches:
            return (), ()

        injected_matches = self._dedupe_injected_matches(matches)
        terms = tuple(match.entry for match in injected_matches)
        traces = tuple(
            self._build_trace_record(
                match=match,
                term_version=term_version,
                job_id=job_id,
                sequence=index,
            )
            for index, match in enumerate(injected_matches, start=1)
        )
        return terms, traces

    def _select_non_overlapping_matches(self, matches: list[_TermMatch]) -> list[_TermMatch]:
        selected: list[_TermMatch] = []
        selected_ranges: list[tuple[int, int]] = []
        for match in sorted(matches, key=self._match_rank):
            if any(match.match_start < end and start < match.match_end for start, end in selected_ranges):
                continue
            selected.append(match)
            selected_ranges.append((match.match_start, match.match_end))
        return selected

    def _dedupe_injected_matches(self, matches: list[_TermMatch]) -> list[_TermMatch]:
        injected: list[_TermMatch] = []
        seen_terms: set[tuple[str, str, str]] = set()
        for match in sorted(matches, key=self._match_rank):
            normalized_source_term = (
                match.entry.normalized_source_term
                or normalize_translation_source_term(match.entry.source_term)
            )
            term_key = (match.entry.set_id, match.entry.version, normalized_source_term)
            if term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            injected.append(match)
        return injected

    def _build_trace_record(
        self,
        *,
        match: _TermMatch,
        term_version: TermVersionSnapshot,
        job_id: str,
        sequence: int,
    ) -> TranslationTermMatchTraceRecord:
        trace_key = "|".join(
            [
                job_id,
                match.item_id,
                match.entry.set_id,
                term_version.version,
                match.entry.source_term,
                str(match.match_start),
                str(match.match_end),
                str(sequence),
            ]
        )
        trace_id = f"ttmt_{hashlib.sha256(trace_key.encode('utf-8')).hexdigest()[:16]}"
        return TranslationTermMatchTraceRecord(
            id=trace_id,
            job_id=job_id,
            segment_id=match.item_id,
            batch_id="document_ir_provider_request_0001",
            translation_term_set_id=match.entry.set_id,
            translation_term_version=term_version.version,
            source_term=match.entry.source_term,
            target_term=match.entry.target_term,
            match_start=match.match_start,
            match_end=match.match_end,
            context_snippet=match.context_snippet,
            injected_to_glossary=True,
        )

    @staticmethod
    def _build_term_pattern(entry: TranslationTermEntry) -> re.Pattern[str] | None:
        source_term = " ".join(entry.source_term.strip().split())
        if not source_term:
            return None
        escaped_parts = [re.escape(part) for part in source_term.split(" ")]
        flags = 0 if entry.case_sensitive else re.IGNORECASE
        return re.compile(r"\s+".join(escaped_parts), flags=flags)

    @staticmethod
    def _match_rank(match: _TermMatch) -> tuple[int, int, int, int, int, int]:
        return (
            -match.matched_length,
            -match.entry.priority,
            match.term_index,
            match.item_index,
            match.match_start,
            match.match_end,
        )

    @staticmethod
    def _context_snippet(text: str, match_start: int, match_end: int) -> str:
        snippet_start = max(0, match_start - _TRACE_CONTEXT_RADIUS)
        snippet_end = min(len(text), match_end + _TRACE_CONTEXT_RADIUS)
        snippet = text[snippet_start:snippet_end]
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet += "..."
        if len(snippet) > _TRACE_CONTEXT_MAX_CHARS:
            return snippet[: _TRACE_CONTEXT_MAX_CHARS - 3] + "..."
        return snippet

    def _extract_items(self, document_ir: DocumentIR) -> tuple[list[_TextTarget], list[TranslationTextItem]]:
        targets: list[_TextTarget] = []
        items: list[TranslationTextItem] = []
        for block in sorted(document_ir.blocks, key=lambda item: item.order):
            self._append_block_text(block, targets, items)
            self._append_list_items(block, targets, items)
            self._append_table_text_nodes(block, targets, items)
        return targets, items

    def _append_block_text(
        self,
        block: DocumentIRBlock,
        targets: list[_TextTarget],
        items: list[TranslationTextItem],
    ) -> None:
        if block.type in {"formula", "list"} or not self._has_text(block.text):
            return
        item_id = f"{block.id}.text"
        targets.append(_TextTarget(item_id=item_id, block_id=block.id, field="text"))
        items.append(TranslationTextItem(id=item_id, text=block.text.strip()))

    def _append_list_items(
        self,
        block: DocumentIRBlock,
        targets: list[_TextTarget],
        items: list[TranslationTextItem],
    ) -> None:
        if block.type != "list" or not block.list_items:
            return
        for index, item in enumerate(block.list_items):
            if not self._has_text(item):
                continue
            item_id = f"{block.id}.list_items.{index:04d}"
            targets.append(_TextTarget(item_id=item_id, block_id=block.id, field="list_items", index=index))
            items.append(TranslationTextItem(id=item_id, text=item.strip()))

    def _append_table_text_nodes(
        self,
        block: DocumentIRBlock,
        targets: list[_TextTarget],
        items: list[TranslationTextItem],
    ) -> None:
        if block.type != "table" or not block.html:
            return
        soup = BeautifulSoup(block.html, "html.parser")
        text_index = 0
        for node in soup.find_all(string=True):
            text = str(node).strip()
            if not text:
                continue
            item_id = f"{block.id}.html.{text_index:04d}"
            targets.append(_TextTarget(item_id=item_id, block_id=block.id, field="html", index=text_index))
            items.append(TranslationTextItem(id=item_id, text=text))
            text_index += 1

    def _validate_result(
        self,
        items: list[TranslationTextItem],
        result: TranslationProviderResult,
    ) -> dict[str, str]:
        expected_ids = [item.id for item in items]
        returned_ids = [item.id for item in result.items]
        if returned_ids != expected_ids:
            raise ValueError("翻译 provider 返回的 item id 与请求不一致。")
        return {item.id: item.text for item in result.items}

    def _apply_replacements(
        self,
        document_ir: DocumentIR,
        targets: list[_TextTarget],
        replacements: dict[str, str],
    ) -> None:
        blocks_by_id = {block.id: block for block in document_ir.blocks}
        html_replacements: dict[str, dict[int, str]] = {}
        for target in targets:
            block = blocks_by_id[target.block_id]
            translated_text = replacements[target.item_id]
            if target.field == "text":
                block.text = translated_text
            elif target.field == "list_items" and block.list_items is not None and target.index is not None:
                block.list_items[target.index] = translated_text
            elif target.field == "html" and target.index is not None:
                html_replacements.setdefault(block.id, {})[target.index] = translated_text

        for block_id, replacements_by_index in html_replacements.items():
            block = blocks_by_id[block_id]
            block.html = self._replace_html_text_nodes(block.html or "", replacements_by_index)

    def _replace_html_text_nodes(self, html: str, replacements: dict[int, str]) -> str:
        soup = BeautifulSoup(html, "html.parser")
        text_index = 0
        for node in soup.find_all(string=True):
            text = str(node).strip()
            if not text:
                continue
            if text_index in replacements:
                node.replace_with(NavigableString(replacements[text_index]))
            text_index += 1
        return str(soup)

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return bool(value and value.strip())

    @staticmethod
    def _source_language(language_pair: str) -> str:
        source, _, _target = language_pair.partition("2")
        return source or "en"

    @staticmethod
    def _target_language(language_pair: str) -> str:
        _source, separator, target = language_pair.partition("2")
        return target if separator and target else "zh"

    @staticmethod
    def _target_document_language(language_pair: str) -> str:
        target = DocumentIRTranslationService._target_language(language_pair)
        if target.lower().startswith("zh"):
            return "zh"
        if target.lower().startswith("en"):
            return "en"
        return target
