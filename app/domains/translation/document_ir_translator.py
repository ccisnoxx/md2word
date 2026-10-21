from __future__ import annotations

# app/domains/translation/document_ir_translator.py: 只翻译 DocumentIR 文本节点并保持结构字段稳定。

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.domains.translation.models import (
    TermVersionSnapshot,
    TranslationPromptSnapshot,
    TranslationTermEntry,
    TranslationTermMatchTraceRecord,
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTextItem,
    normalize_translation_source_term,
)
from app.domains.translation.provider import TranslationProvider, TranslationProviderResponseError
from app.domains.translation.integrity import (
    TranslationIntegrityEvidence, TranslationIntegrityError, TranslationIntegrityValidator,
)
from app.domains.translation.protected_tokens import EncodedTokenBatch, encode


_TRACE_CONTEXT_RADIUS = 40
_TRACE_CONTEXT_MAX_CHARS = 120
DEFAULT_MAX_ITEMS_PER_PROVIDER_REQUEST = 300
DEFAULT_MAX_CHARS_PER_PROVIDER_REQUEST = 8000


class DocumentIRTranslationError(RuntimeError):
    """翻译失败的安全领域错误；保留专用机器码与脱敏证据。"""

    def __init__(self, message: str, *, code: str = "translation_provider_failed", evidence: TranslationIntegrityEvidence | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = evidence


class TranslationCallRecorder(Protocol):
    """DocumentIR 翻译过程的审计回调端口。"""

    def record_success(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult,
        *,
        duration_ms: int,
        integrity: TranslationIntegrityEvidence | None = None,
    ) -> None: ...

    def record_failure(
        self,
        request: TranslationProviderRequest,
        result: TranslationProviderResult | None,
        *,
        error: Exception,
        duration_ms: int,
        integrity: TranslationIntegrityEvidence | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DocumentIRTranslationTarget:
    """DocumentIR 内一个可翻译文本节点的位置。"""

    item_id: str
    block_id: str
    field: str
    index: int | None = None
    page_number: int | None = None
    order: int = 0


@dataclass(frozen=True, slots=True)
class DocumentIRTranslationBatchPlan:
    """一次 provider batch task 的确定性输入边界。"""

    batch_id: str
    item_ids: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    item_count: int
    char_count: int
    split_level: int = 0
    parent_batch_id: str | None = None


@dataclass(frozen=True, slots=True)
class _TermMatch:
    entry: TranslationTermEntry
    item_id: str
    item_index: int
    match_start: int
    match_end: int
    context_snippet: str = field(repr=False)
    term_index: int

    @property
    def matched_length(self) -> int:
        return self.match_end - self.match_start


@dataclass(frozen=True, slots=True)
class PreparedTranslationRequest:
    """单次调用的原文、真实请求与内存 ledger；不得把该载体落盘或发给 Provider。"""

    source_items: tuple[TranslationTextItem, ...] = field(repr=False)
    request: TranslationProviderRequest = field(repr=False)
    encoded_batch: EncodedTokenBatch = field(repr=False)


class DocumentIRTranslationService:
    """DocumentIR 文本翻译服务；不让 AI 接触结构、资产或样式信息。"""

    def __init__(
        self,
        provider: TranslationProvider,
        *,
        max_items_per_request: int = DEFAULT_MAX_ITEMS_PER_PROVIDER_REQUEST,
        max_chars_per_request: int = DEFAULT_MAX_CHARS_PER_PROVIDER_REQUEST,
    ) -> None:
        self.provider = provider
        self.validator = TranslationIntegrityValidator()
        self.max_items_per_request = max(1, int(max_items_per_request))
        self.max_chars_per_request = max(1, int(max_chars_per_request))

    def translate(
        self,
        document_ir: DocumentIR,
        *,
        term_version: TermVersionSnapshot | None,
        language_pair: str = "en2zh",
        prompt: TranslationPromptSnapshot | None = None,
        call_recorder: TranslationCallRecorder | None = None,
        max_pages_per_batch: int | None = None,
    ) -> DocumentIR:
        """返回翻译后的 DocumentIR 副本；blocks/assets 数量和顺序保持不变。"""

        translated = document_ir.model_copy(deep=True)
        try:
            targets, items, batches = self.build_translation_plan(
                document_ir,
                max_pages_per_batch=max_pages_per_batch or max(1, len(document_ir.pages)),
                max_chars_per_batch=self.max_chars_per_request,
                batch_id_prefix="document_ir_provider_request",
            )
        except TranslationIntegrityError as exc:
            raise DocumentIRTranslationError(str(exc), code=exc.code, evidence=exc.evidence) from None
        if not items:
            return translated
        items_by_id = {item.id: item for item in items}
        replacements: dict[str, str] = {}
        for batch in batches:
            prepared = self.build_provider_request(
                document_ir, [items_by_id[item_id] for item_id in batch.item_ids],
                term_version=term_version, language_pair=language_pair, prompt=prompt,
                batch_id=batch.batch_id, page_start=batch.page_start, page_end=batch.page_end,
            )
            request = prepared.request
            started_at = time.perf_counter()
            result: TranslationProviderResult | None = None
            try:
                result = self.provider.translate(request)
                validated = self.validator.validate(prepared.source_items, prepared.encoded_batch, result)
            except Exception as exc:
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                code = exc.code if isinstance(exc, TranslationIntegrityError) else (
                    "translation_provider_truncated" if isinstance(exc, TranslationProviderResponseError) and exc.suspected_truncation else
                    "translation_provider_invalid_response" if isinstance(exc, TranslationProviderResponseError) else "translation_provider_failed"
                )
                evidence = exc.evidence if isinstance(exc, TranslationIntegrityError) else self.validator.call_failure_evidence(
                    prepared.source_items, prepared.encoded_batch, error_code=code,
                )
                if call_recorder is not None:
                    call_recorder.record_failure(request, result, error=exc, duration_ms=duration_ms, integrity=evidence)
                raise DocumentIRTranslationError("翻译 Provider 调用或完整性校验失败。", code=code, evidence=evidence) from None
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if call_recorder is not None:
                call_recorder.record_success(request, result, duration_ms=duration_ms, integrity=validated.evidence)
            replacements.update(validated.replacements)
        self.apply_replacements(translated, targets, replacements)
        translated.metadata.document_language = self._target_document_language(language_pair)
        return translated

    def build_translation_plan(
        self,
        document_ir: DocumentIR,
        *,
        max_pages_per_batch: int,
        max_chars_per_batch: int,
        batch_id_prefix: str,
    ) -> tuple[
        list[DocumentIRTranslationTarget],
        list[TranslationTextItem],
        list[DocumentIRTranslationBatchPlan],
    ]:
        """按页数、实际编码字符和 item 数生成确定性计划；char_count 仍表示源文。"""

        targets, items = self.extract_translation_items(document_ir)
        if not items:
            return targets, items, []
        targets_by_id = {target.item_id: target for target in targets}
        batches: list[DocumentIRTranslationBatchPlan] = []
        current: list[TranslationTextItem] = []
        current_chars = 0
        current_page_start: int | None = None
        current_page_end: int | None = None
        max_pages = max(1, int(max_pages_per_batch))
        max_chars = max(1, int(max_chars_per_batch))

        def flush() -> None:
            nonlocal current, current_chars, current_page_start, current_page_end
            if not current:
                return
            batch_index = len(batches) + 1
            batches.append(
                DocumentIRTranslationBatchPlan(
                    batch_id=f"{batch_id_prefix}_{batch_index:04d}",
                    item_ids=tuple(item.id for item in current),
                    page_start=current_page_start,
                    page_end=current_page_end,
                    item_count=len(current),
                    char_count=current_chars,
                )
            )
            current = []
            current_chars = 0
            current_page_start = None
            current_page_end = None

        for item in items:
            target = targets_by_id[item.id]
            item_chars = len(item.text)
            self.validator.prepare((item,), max_chars=max_chars)
            item_page = target.page_number
            next_page_start = current_page_start
            next_page_end = current_page_end
            if item_page is not None:
                next_page_start = item_page if next_page_start is None else min(next_page_start, item_page)
                next_page_end = item_page if next_page_end is None else max(next_page_end, item_page)
            exceeds_pages = (
                bool(current)
                and next_page_start is not None
                and next_page_end is not None
                and next_page_end - next_page_start + 1 > max_pages
            )
            candidate = encode(tuple([*current, item]))
            exceeds_chars = bool(current) and sum(len(value.text) for value in candidate.items) > max_chars
            exceeds_items = bool(current) and len(current) >= self.max_items_per_request
            if exceeds_pages or exceeds_chars or exceeds_items:
                flush()
                next_page_start = item_page
                next_page_end = item_page
            current.append(item)
            current_chars += item_chars
            current_page_start = next_page_start
            current_page_end = next_page_end
        flush()
        return targets, items, batches

    def build_provider_request(
        self,
        document_ir: DocumentIR,
        items: list[TranslationTextItem],
        *,
        term_version: TermVersionSnapshot | None,
        language_pair: str,
        prompt: TranslationPromptSnapshot | None = None,
        batch_id: str,
        attempt: int | None = None,
        split_level: int | None = None,
        parent_batch_id: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        max_chars_per_request: int | None = None,
    ) -> PreparedTranslationRequest:
        source_items = tuple(items)
        encoded = self.validator.prepare(
            source_items, max_chars=max_chars_per_request if max_chars_per_request is not None else self.max_chars_per_request,
        )
        matched_terms, term_traces = self._match_request_terms(
            items=items,
            term_version=term_version,
            language_pair=language_pair,
            job_id=document_ir.metadata.job_id or "",
            batch_id=batch_id,
            encoded_batch=encoded,
        )
        request = TranslationProviderRequest(
            language_pair=language_pair,
            source_language=self._source_language(language_pair),
            target_language=self._target_language(language_pair),
            items=encoded.items,
            prompt_id=prompt.id if prompt is not None else None,
            prompt_content_hash=prompt.content_hash if prompt is not None else None,
            system_prompt_markdown=prompt.markdown if prompt is not None else None,
            terms=matched_terms,
            term_traces=term_traces,
            batch_id=batch_id,
            attempt=attempt,
            split_level=split_level,
            parent_batch_id=parent_batch_id,
            page_start=page_start,
            page_end=page_end,
        )
        return PreparedTranslationRequest(source_items, request, encoded)

    def _match_request_terms(
        self,
        *,
        items: list[TranslationTextItem],
        term_version: TermVersionSnapshot | None,
        language_pair: str,
        job_id: str,
        batch_id: str,
        encoded_batch: EncodedTokenBatch,
    ) -> tuple[tuple[TranslationTermEntry, ...], tuple[TranslationTermMatchTraceRecord, ...]]:
        if term_version is None:
            return (), ()
        matches: list[_TermMatch] = []
        for item_index, item in enumerate(items):
            item_matches: list[_TermMatch] = []
            for term_index, entry in enumerate(term_version.entries):
                if entry.language_pair != language_pair or entry.status not in {"publishable", "active"}:
                    continue
                pattern = self._build_term_pattern(entry)
                if pattern is None:
                    continue
                for match in pattern.finditer(item.text):
                    if any(
                        token.item_id == item.id and match.start() < token.end and token.start < match.end()
                        for token in encoded_batch.occurrences
                    ):
                        continue
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
                batch_id=batch_id,
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
        batch_id: str,
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
            batch_id=batch_id,
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

    def extract_translation_items(
        self,
        document_ir: DocumentIR,
    ) -> tuple[list[DocumentIRTranslationTarget], list[TranslationTextItem]]:
        targets: list[DocumentIRTranslationTarget] = []
        items: list[TranslationTextItem] = []
        for block in sorted(document_ir.blocks, key=lambda item: item.order):
            self._append_block_text(block, targets, items)
            self._append_list_items(block, targets, items)
            self._append_table_text_nodes(block, targets, items)
        return targets, items

    def _append_block_text(
        self,
        block: DocumentIRBlock,
        targets: list[DocumentIRTranslationTarget],
        items: list[TranslationTextItem],
    ) -> None:
        if block.type in {"formula", "list"} or not self._has_text(block.text):
            return
        item_id = f"{block.id}.text"
        targets.append(
            DocumentIRTranslationTarget(
                item_id=item_id,
                block_id=block.id,
                field="text",
                page_number=self._block_page_number(block),
                order=block.order,
            )
        )
        items.append(TranslationTextItem(id=item_id, text=block.text.strip()))

    def _append_list_items(
        self,
        block: DocumentIRBlock,
        targets: list[DocumentIRTranslationTarget],
        items: list[TranslationTextItem],
    ) -> None:
        if block.type != "list" or not block.list_items:
            return
        for index, item in enumerate(block.list_items):
            if not self._has_text(item):
                continue
            item_id = f"{block.id}.list_items.{index:04d}"
            targets.append(
                DocumentIRTranslationTarget(
                    item_id=item_id,
                    block_id=block.id,
                    field="list_items",
                    index=index,
                    page_number=self._block_page_number(block),
                    order=block.order,
                )
            )
            items.append(TranslationTextItem(id=item_id, text=item.strip()))

    def _append_table_text_nodes(
        self,
        block: DocumentIRBlock,
        targets: list[DocumentIRTranslationTarget],
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
            targets.append(
                DocumentIRTranslationTarget(
                    item_id=item_id,
                    block_id=block.id,
                    field="html",
                    index=text_index,
                    page_number=self._block_page_number(block),
                    order=block.order,
                )
            )
            items.append(TranslationTextItem(id=item_id, text=text))
            text_index += 1

    def apply_replacements(
        self,
        document_ir: DocumentIR,
        targets: list[DocumentIRTranslationTarget],
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

    @staticmethod
    def _block_page_number(block: DocumentIRBlock) -> int | None:
        page_index = block.layout.page_index if block.layout is not None else block.page_index
        if page_index is None:
            return None
        return page_index + 1

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
