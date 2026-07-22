from __future__ import annotations

# app/conversion/runtime_helpers.py: 提供 legacy conversion runner 复用的配置解析与语言推断。

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.conversion.runtime import page_repair_runtime, render_config_runtime, translation_runtime
from docx.shared import Mm
from app.conversion.runtime.render_config_runtime import TerminologyReplacer

from app.conversion.runtime_models import PageData, ParagraphStyleConfig, RenderConfig, SectionLayout, TableStyleConfig


LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
ENGLISH_STYLE_FONT = "Arial"
CJK_STYLE_FONT_NAMES = {
    "宋体",
    "仿宋",
    "黑体",
    "楷体",
    "微软雅黑",
    "SimSun",
    "FangSong",
    "SimHei",
    "KaiTi",
    "Microsoft YaHei",
}
ENGLISH_STYLE_NAMES = {
    "PartNumber",
    "Category",
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "TocTitle",
    "TocLevel1",
    "TocLevel2",
    "TocLevel3",
    "Normal",
    "Caption",
    "LongTableCaption",
    "TableNote",
    "TableContent",
}
DEFAULT_CJK_FIRST_LINE_INDENT_PT = 21.0
DEFAULT_LAYOUT_CONFIG_CANDIDATES = (
    Path("resources/template_configs/datasheet_template.yaml"),
    Path(__file__).resolve().parents[2] / "resources" / "template_configs" / "datasheet_template.yaml",
)
PAGE_MARGIN = Mm(15)


def build_translation_config(
    *,
    max_pages: int,
    max_chars: int,
    language_pair: str = "en2zh",
    target_language: str = translation_runtime.DEFAULT_TARGET_LANGUAGE,
    domain: str = translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
    prompt_version: str = translation_runtime.TRANSLATION_PROMPT_VERSION,
) -> translation_runtime.TranslationConfig:
    return translation_runtime.TranslationConfig(
        language_pair=language_pair,
        target_language=target_language,
        domain=domain,
        max_pages_per_batch=max(int(max_pages), 1),
        max_chars_per_batch=max(int(max_chars), 1),
        prompt_version=prompt_version,
    )


def load_translations_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    translations: dict[str, str] = {}
    for batch in payload.get("batches", []):
        for item in batch.get("items", []):
            item_id = str(item.get("id", "")).strip()
            if not item_id:
                continue
            translations[item_id] = str(item.get("text", ""))
    return translations


def resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).resolve()
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        return input_path.with_suffix(".docx")
    return input_path / "mineru_output.docx"


def resolve_template_path(template_arg: str | None, default_candidates: tuple[Path, ...]) -> Path | None:
    if template_arg:
        candidate = Path(template_arg).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"模板文件不存在: {candidate}")
        return candidate

    for candidate in default_candidates:
        resolved = candidate if candidate.is_absolute() else candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def find_layout_config_path(default_candidates: tuple[Path, ...] = DEFAULT_LAYOUT_CONFIG_CANDIDATES) -> Path | None:
    return render_config_runtime.find_layout_config_path(default_candidates)


def load_section_layout(template_document: Any | None, config_path: Path | None) -> SectionLayout:
    return render_config_runtime.load_section_layout(
        template_document,
        config_path,
        page_margin=PAGE_MARGIN,
        mm_fn=Mm,
        section_layout_cls=SectionLayout,
    )


def load_paragraph_styles(config_path: Path | None) -> dict[str, ParagraphStyleConfig]:
    return render_config_runtime.load_paragraph_styles(
        config_path,
        paragraph_style_config_cls=ParagraphStyleConfig,
    )


def load_table_style(config_path: Path | None) -> TableStyleConfig:
    return render_config_runtime.load_table_style(
        config_path,
        table_style_config_cls=TableStyleConfig,
    )


def load_render_config(
    template_document: Any | None,
    subscript_config: Path | None,
    use_mineru_header_footer: bool,
    *,
    layout_config_path: Path | None = None,
    default_layout_candidates: tuple[Path, ...] = DEFAULT_LAYOUT_CONFIG_CANDIDATES,
) -> RenderConfig:
    return render_config_runtime.load_render_config(
        template_document,
        subscript_config,
        use_mineru_header_footer,
        find_layout_config_path_fn=lambda: layout_config_path or find_layout_config_path(default_layout_candidates),
        load_section_layout_fn=load_section_layout,
        terminology_factory=TerminologyReplacer,
        load_paragraph_styles_fn=load_paragraph_styles,
        load_table_style_fn=load_table_style,
        render_config_cls=RenderConfig,
    )


def resolve_document_language(pages: list[PageData], *, preferred: str = "auto") -> str:
    normalized = str(preferred or "auto").strip().lower()
    if normalized in {"zh", "en", "ru"}:
        return normalized
    return detect_document_language(pages)


def detect_document_language(pages: list[PageData]) -> str:
    sample_fragments: list[str] = []
    for page in pages[: min(len(pages), 12)]:
        for block in page_repair_runtime.get_page_body_blocks(page):
            if block.text:
                sample_fragments.append(block.text)
            if block.items:
                sample_fragments.extend(block.items[:3])
            if block.captions:
                sample_fragments.extend(block.captions[:1])
            if block.footnotes:
                sample_fragments.extend(block.footnotes[:1])
            if sum(len(fragment) for fragment in sample_fragments) >= 4000:
                break
        if sum(len(fragment) for fragment in sample_fragments) >= 4000:
            break

    sample_text = " ".join(sample_fragments)
    latin_letters = len(LATIN_LETTER_RE.findall(sample_text))
    cjk_chars = len(CJK_CHAR_RE.findall(sample_text))
    if latin_letters >= 40 and (cjk_chars == 0 or latin_letters >= cjk_chars * 3):
        return "en"
    return "zh"


def apply_document_language_overrides(render_config: RenderConfig, document_language: str) -> RenderConfig:
    if document_language != "en":
        return render_config

    paragraph_styles: dict[str, ParagraphStyleConfig] = {}
    for style_name, style_config in render_config.paragraph_styles.items():
        overrides: dict[str, Any] = {}
        if style_name in ENGLISH_STYLE_NAMES and style_config.western_font_name is None and (
            style_config.font_name is None or style_config.font_name in CJK_STYLE_FONT_NAMES
        ):
            overrides["font_name"] = ENGLISH_STYLE_FONT
        if style_name == "Normal" and (
            style_config.first_line_indent_pt is None
            or abs(style_config.first_line_indent_pt - DEFAULT_CJK_FIRST_LINE_INDENT_PT) < 0.01
        ):
            overrides["first_line_indent_pt"] = 0.0
        paragraph_styles[style_name] = replace(style_config, **overrides) if overrides else style_config

    return replace(render_config, paragraph_styles=paragraph_styles)
