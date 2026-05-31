from __future__ import annotations

# app/domains/translation/document_ir_translator.py: 只翻译 DocumentIR 文本节点并保持结构字段稳定。

import time
from dataclasses import dataclass
from typing import Protocol

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.domains.translation.models import (
    TermVersionSnapshot,
    TranslationProviderRequest,
    TranslationProviderResult,
    TranslationTextItem,
)
from app.domains.translation.provider import TranslationProvider


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
        request = TranslationProviderRequest(
            language_pair=language_pair,
            source_language=self._source_language(language_pair),
            target_language=self._target_language(language_pair),
            items=tuple(items),
            terms=term_version.entries if term_version is not None else (),
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
