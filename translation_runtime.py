from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DEFAULT_TARGET_LANGUAGE = "zh-CN"
DEFAULT_TRANSLATION_DOMAIN = "electronics engineering technical document"
DEFAULT_MAX_PAGES_PER_BATCH = 20
DEFAULT_MAX_CHARS_PER_BATCH = 60000
TRANSLATION_PROMPT_VERSION = "translation-minimal-v1"
DEFAULT_FRONT_SECTION = "front-matter"
SKIPPED_BLOCK_TYPES = {"page_header", "page_footer", "page_number", "table_placeholder"}

TRANSLATABLE_TEXT_RE = re.compile(r"[A-Za-z\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
PROTECTED_PATTERN_RE = re.compile(
    r"(?P<html_var>\b[A-Za-zΑ-Ωα-ω]+(?:<sub>[^<>]+</sub>|<sup>[^<>]+</sup>)+)"
    r"|(?P<value>\b\d+(?:\.\d+)?\s?(?:kΩ|MΩ|Ω|µV|uV|mV|V|µA|uA|mA|A|nA|pA|°C|MHz|kHz|Hz|dB|pF|nF|µF|uF|%)\b)"
    r"|(?P<part>\b[A-Z]{2,}\d[A-Z0-9+\-/]*\b)"
)
PLACEHOLDER_RE = re.compile(r"\{\{PH_\d{3}\}\}")


@dataclass(slots=True)
class TranslationConfig:
    target_language: str = DEFAULT_TARGET_LANGUAGE
    domain: str = DEFAULT_TRANSLATION_DOMAIN
    max_pages_per_batch: int = DEFAULT_MAX_PAGES_PER_BATCH
    max_chars_per_batch: int = DEFAULT_MAX_CHARS_PER_BATCH
    prompt_version: str = TRANSLATION_PROMPT_VERSION


@dataclass(slots=True)
class TranslationItem:
    id: str
    text: str
    source_text: str
    page_number: int
    page_position: int
    block_position: int
    block_idx: int
    field: str
    index: int | None = None
    section_id: str = "s0000"
    section_title: str = DEFAULT_FRONT_SECTION
    section_continuation: bool = False
    placeholders: dict[str, str] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass(slots=True)
class TranslationBatch:
    batch_id: str
    items: list[TranslationItem]
    section_title: str
    section_continuation: bool = False

    @property
    def start_page(self) -> int:
        return min((item.page_number for item in self.items), default=0)

    @property
    def end_page(self) -> int:
        return max((item.page_number for item in self.items), default=0)

    @property
    def char_count(self) -> int:
        return sum(item.char_count for item in self.items)


def build_translation_request_payload(pages: list[Any], config: TranslationConfig) -> dict[str, Any]:
    items = extract_translation_items(pages)
    batches = build_translation_batches(items, total_pages=len(pages), config=config)
    return {
        "target_language": config.target_language,
        "domain": config.domain,
        "prompt_version": config.prompt_version,
        "batches": [serialize_batch(batch, config) for batch in batches],
    }


def serialize_batch(batch: TranslationBatch, config: TranslationConfig) -> dict[str, Any]:
    return {
        "batch_id": batch.batch_id,
        "target_language": config.target_language,
        "domain": config.domain,
        "section": batch.section_title,
        "section_continuation": batch.section_continuation,
        "page_range": [batch.start_page, batch.end_page],
        "items": [{"id": item.id, "text": item.text} for item in batch.items],
    }


def write_translation_request_file(pages: list[Any], output_path: Path, config: TranslationConfig) -> dict[str, Any]:
    payload = build_translation_request_payload(pages, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def extract_translation_items(pages: list[Any]) -> list[TranslationItem]:
    items: list[TranslationItem] = []
    current_section_title = DEFAULT_FRONT_SECTION
    current_section_seq = 0
    current_section_id = "s0000"

    for page_position, page in enumerate(pages):
        page_number = int(getattr(page, "page_idx", page_position) or 0) + 1
        blocks = list(getattr(page, "blocks", []))
        for block_position, block in enumerate(blocks):
            block_idx = int(getattr(block, "block_idx", block_position) if getattr(block, "block_idx", None) is not None else block_position)
            block_text = str(getattr(block, "text", "") or "")
            block_type = str(getattr(block, "type", "") or "")
            if block_type in SKIPPED_BLOCK_TYPES:
                continue
            is_section_start = is_section_start_block(block)
            if is_section_start and is_translatable_text(block_text):
                current_section_seq += 1
                current_section_id = f"s{current_section_seq:04d}"
                current_section_title = clean_section_title(block_text)

            prefix = make_block_id_prefix(page_number, block_idx)
            add_text_item(
                items,
                page_number=page_number,
                page_position=page_position,
                block_position=block_position,
                block_idx=block_idx,
                item_id=f"{prefix}.text",
                source_text=block_text,
                field="text",
                section_id=current_section_id,
                section_title=current_section_title,
            )

            for index, value in enumerate(list(getattr(block, "items", []) or [])):
                add_text_item(
                    items,
                    page_number=page_number,
                    page_position=page_position,
                    block_position=block_position,
                    block_idx=block_idx,
                    item_id=f"{prefix}.items.i{index:03d}",
                    source_text=str(value or ""),
                    field="items",
                    index=index,
                    section_id=current_section_id,
                    section_title=current_section_title,
                )

            for field_name in ("captions", "footnotes"):
                for index, value in enumerate(list(getattr(block, field_name, []) or [])):
                    add_text_item(
                        items,
                        page_number=page_number,
                        page_position=page_position,
                        block_position=block_position,
                        block_idx=block_idx,
                        item_id=f"{prefix}.{field_name}.i{index:03d}",
                        source_text=str(value or ""),
                        field=field_name,
                        index=index,
                        section_id=current_section_id,
                        section_title=current_section_title,
                    )

            html = getattr(block, "html", None)
            for cell_index, cell_text in enumerate(extract_html_cell_texts(html)):
                add_text_item(
                    items,
                    page_number=page_number,
                    page_position=page_position,
                    block_position=block_position,
                    block_idx=block_idx,
                    item_id=f"{prefix}.html.c{cell_index:04d}",
                    source_text=cell_text,
                    field="html",
                    index=cell_index,
                    section_id=current_section_id,
                    section_title=current_section_title,
                )

    return items


def add_text_item(
    items: list[TranslationItem],
    *,
    page_number: int,
    page_position: int,
    block_position: int,
    block_idx: int,
    item_id: str,
    source_text: str,
    field: str,
    section_id: str,
    section_title: str,
    index: int | None = None,
) -> None:
    if not is_translatable_text(source_text):
        return
    protected_text, placeholders = protect_text(source_text)
    items.append(
        TranslationItem(
            id=item_id,
            text=protected_text,
            source_text=source_text,
            page_number=page_number,
            page_position=page_position,
            block_position=block_position,
            block_idx=block_idx,
            field=field,
            index=index,
            section_id=section_id,
            section_title=section_title,
            placeholders=placeholders,
        )
    )


def make_block_id_prefix(page_number: int, block_idx: int) -> str:
    return f"p{page_number:04d}.b{block_idx:04d}"


def is_section_start_block(block: Any) -> bool:
    block_type = str(getattr(block, "type", "") or "")
    return block_type == "title"


def clean_section_title(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[:120] if cleaned else DEFAULT_FRONT_SECTION


def is_translatable_text(text: str) -> bool:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return False
    return bool(TRANSLATABLE_TEXT_RE.search(cleaned))


def protect_text(text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def replacer(match: re.Match[str]) -> str:
        value = match.group(0)
        placeholder = f"{{{{PH_{len(placeholders) + 1:03d}}}}}"
        placeholders[placeholder] = value
        return placeholder

    return PROTECTED_PATTERN_RE.sub(replacer, text), placeholders


def restore_placeholders(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for placeholder, value in placeholders.items():
        restored = restored.replace(placeholder, value)
    return restored


def make_cache_key(item: TranslationItem, config: TranslationConfig, model: str = "") -> str:
    digest = hashlib.sha256(item.source_text.encode("utf-8")).hexdigest()
    return "|".join(
        [
            config.target_language,
            config.prompt_version,
            model,
            item.id,
            digest,
        ]
    )


def build_translation_batches(
    items: list[TranslationItem],
    *,
    total_pages: int,
    config: TranslationConfig,
) -> list[TranslationBatch]:
    if not items:
        return []

    if total_pages <= config.max_pages_per_batch and sum(item.char_count for item in items) <= config.max_chars_per_batch:
        return [make_batch(1, items, section_continuation=False)]

    section_groups = group_items_by_section(items)
    batches: list[TranslationBatch] = []
    current: list[TranslationItem] = []

    for section_items in section_groups:
        if not section_items:
            continue
        if sum(item.char_count for item in section_items) > config.max_chars_per_batch:
            if current:
                batches.append(make_batch(len(batches) + 1, current, section_continuation=False))
                current = []
            batches.extend(split_large_section(section_items, config, start_index=len(batches) + 1))
            continue

        candidate = [*current, *section_items]
        candidate_chars = sum(item.char_count for item in candidate)
        candidate_exceeds_pages = page_span(candidate) > config.max_pages_per_batch
        should_keep_section_with_current = (
            current
            and candidate_exceeds_pages
            and min(item.page_number for item in section_items)
            <= min(item.page_number for item in current) + config.max_pages_per_batch - 1
            and candidate_chars <= config.max_chars_per_batch
        )
        if current and (
            (candidate_exceeds_pages and not should_keep_section_with_current)
            or candidate_chars > config.max_chars_per_batch
        ):
            batches.append(make_batch(len(batches) + 1, current, section_continuation=False))
            current = list(section_items)
        else:
            current = candidate

    if current:
        batches.append(make_batch(len(batches) + 1, current, section_continuation=False))

    return batches


def group_items_by_section(items: list[TranslationItem]) -> list[list[TranslationItem]]:
    groups: list[list[TranslationItem]] = []
    current_section_id: str | None = None
    current: list[TranslationItem] = []
    for item in items:
        if current and item.section_id != current_section_id:
            groups.append(current)
            current = []
        current.append(item)
        current_section_id = item.section_id
    if current:
        groups.append(current)
    return groups


def split_large_section(
    section_items: list[TranslationItem],
    config: TranslationConfig,
    *,
    start_index: int,
) -> list[TranslationBatch]:
    batches: list[TranslationBatch] = []
    current: list[TranslationItem] = []
    continuation = False

    for page_items in group_items_by_page(section_items):
        candidate = [*current, *page_items]
        if current and (
            page_span(candidate) > config.max_pages_per_batch
            or sum(item.char_count for item in candidate) > config.max_chars_per_batch
        ):
            batches.append(make_batch(start_index + len(batches), current, section_continuation=continuation))
            current = list(page_items)
            continuation = True
        else:
            current = candidate

    if current:
        batches.append(make_batch(start_index + len(batches), current, section_continuation=continuation))
    return batches


def group_items_by_page(items: list[TranslationItem]) -> list[list[TranslationItem]]:
    groups: list[list[TranslationItem]] = []
    current_page: int | None = None
    current: list[TranslationItem] = []
    for item in items:
        if current and item.page_number != current_page:
            groups.append(current)
            current = []
        current.append(item)
        current_page = item.page_number
    if current:
        groups.append(current)
    return groups


def page_span(items: list[TranslationItem]) -> int:
    if not items:
        return 0
    return max(item.page_number for item in items) - min(item.page_number for item in items) + 1


def make_batch(index: int, items: list[TranslationItem], *, section_continuation: bool) -> TranslationBatch:
    section_titles = []
    seen = set()
    for item in items:
        if item.section_title in seen:
            continue
        seen.add(item.section_title)
        section_titles.append(item.section_title)
    return TranslationBatch(
        batch_id=f"batch_{index:03d}",
        items=list(items),
        section_title=" | ".join(section_titles[:6]) if section_titles else DEFAULT_FRONT_SECTION,
        section_continuation=section_continuation,
    )


def load_translation_response_file(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pairs: list[dict[str, Any]] = []
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        pairs.extend(raw["items"])
    elif isinstance(raw, dict) and isinstance(raw.get("batches"), list):
        for batch in raw["batches"]:
            if isinstance(batch, dict) and isinstance(batch.get("items"), list):
                pairs.extend(batch["items"])
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and isinstance(entry.get("items"), list):
                pairs.extend(entry["items"])
            elif isinstance(entry, dict):
                pairs.append(entry)
    else:
        raise ValueError(f"不支持的翻译响应 JSON 结构: {path}")

    translations: dict[str, str] = {}
    duplicates: set[str] = set()
    for item in pairs:
        item_id = str(item.get("id", "")).strip()
        text = str(item.get("text", ""))
        if not item_id:
            continue
        if item_id in translations:
            duplicates.add(item_id)
        translations[item_id] = text
    if duplicates:
        raise ValueError(f"翻译响应包含重复 ID: {', '.join(sorted(duplicates)[:10])}")
    return translations


def validate_translation_responses(items: list[TranslationItem], translations: dict[str, str]) -> None:
    expected_ids = {item.id for item in items}
    response_ids = set(translations)
    missing = sorted(expected_ids - response_ids)
    extra = sorted(response_ids - expected_ids)
    if missing:
        raise ValueError(f"翻译响应缺少 ID: {', '.join(missing[:10])}")
    if extra:
        raise ValueError(f"翻译响应包含未知 ID: {', '.join(extra[:10])}")

    item_by_id = {item.id: item for item in items}
    empty_ids: list[str] = []
    placeholder_errors: list[str] = []
    for item_id, translated_text in translations.items():
        if not str(translated_text).strip():
            empty_ids.append(item_id)
            continue
        expected_placeholders = set(item_by_id[item_id].placeholders)
        actual_placeholders = set(PLACEHOLDER_RE.findall(translated_text))
        if expected_placeholders != actual_placeholders:
            placeholder_errors.append(item_id)

    if empty_ids:
        raise ValueError(f"翻译响应存在空译文: {', '.join(empty_ids[:10])}")
    if placeholder_errors:
        raise ValueError(f"翻译响应占位符不匹配: {', '.join(placeholder_errors[:10])}")


def apply_translation_responses(pages: list[Any], translations: dict[str, str]) -> None:
    items = extract_translation_items(pages)
    validate_translation_responses(items, translations)
    html_replacements: dict[tuple[int, int], dict[int, str]] = {}

    for item in items:
        translated_text = restore_placeholders(translations[item.id], item.placeholders)
        block = pages[item.page_position].blocks[item.block_position]
        if item.field == "text":
            block.text = translated_text
        elif item.field in {"items", "captions", "footnotes"}:
            values = getattr(block, item.field)
            assert item.index is not None
            values[item.index] = translated_text
        elif item.field == "html":
            assert item.index is not None
            key = (item.page_position, item.block_position)
            html_replacements.setdefault(key, {})[item.index] = translated_text

    for (page_position, block_position), replacements in html_replacements.items():
        block = pages[page_position].blocks[block_position]
        block.html = rewrite_html_cell_texts(getattr(block, "html", None), replacements)


class HtmlCellTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cell_texts: list[str] = []
        self._in_cell = False
        self._cell_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"td", "th"} and not self._in_cell:
            self._in_cell = True
            self._cell_depth = 0
            self._buffer = []
        elif self._in_cell:
            self._cell_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if not self._in_cell:
            return
        if lowered in {"td", "th"} and self._cell_depth == 0:
            text = " ".join("".join(self._buffer).split())
            self.cell_texts.append(text)
            self._in_cell = False
            self._buffer = []
            return
        if self._cell_depth > 0:
            self._cell_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._buffer.append(data)


def extract_html_cell_texts(html: str | None) -> list[str]:
    if not html:
        return []
    parser = HtmlCellTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.cell_texts


class HtmlCellTextRewriter(HTMLParser):
    def __init__(self, replacements: dict[int, str]) -> None:
        super().__init__(convert_charrefs=False)
        self.replacements = replacements
        self.output: list[str] = []
        self.cell_index = -1
        self._in_replaced_cell = False
        self._cell_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"td", "th"} and not self._in_replaced_cell:
            self.cell_index += 1
            self.output.append(format_start_tag(tag, attrs))
            if self.cell_index in self.replacements:
                self._in_replaced_cell = True
                self._cell_depth = 0
            return

        if self._in_replaced_cell:
            self._cell_depth += 1
            return

        self.output.append(format_start_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._in_replaced_cell:
            self.output.append(format_start_tag(tag, attrs, closed=True))

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._in_replaced_cell:
            if lowered in {"td", "th"} and self._cell_depth == 0:
                self.output.append(escape(self.replacements[self.cell_index], quote=False))
                self.output.append(f"</{tag}>")
                self._in_replaced_cell = False
                return
            if self._cell_depth > 0:
                self._cell_depth -= 1
            return

        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._in_replaced_cell:
            self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._in_replaced_cell:
            self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._in_replaced_cell:
            self.output.append(f"&#{name};")


def rewrite_html_cell_texts(html: str | None, replacements: dict[int, str]) -> str | None:
    if not html or not replacements:
        return html
    parser = HtmlCellTextRewriter(replacements)
    parser.feed(html)
    parser.close()
    return "".join(parser.output)


def format_start_tag(tag: str, attrs: list[tuple[str, str | None]], *, closed: bool = False) -> str:
    suffix = " /" if closed else ""
    if not attrs:
        return f"<{tag}{suffix}>"
    attr_text = "".join(
        f" {name}" if value is None else f' {name}="{escape(value, quote=True)}"'
        for name, value in attrs
    )
    return f"<{tag}{attr_text}{suffix}>"
