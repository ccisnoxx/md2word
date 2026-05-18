#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from textwrap import shorten

import yaml
from bs4 import BeautifulSoup
from docx import Document
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Mm, Pt, RGBColor
from loguru import logger
import input_adapter_runtime
import page_layout_runtime
import page_repair_runtime
import render_config_runtime
import text_rendering
import translation_runtime
import llm_client
from config import APP_CONFIG
from table_html_parser import HtmlCell, HtmlTable, parse_html_table
from table_long_renderer import is_long_simple_table, render_long_simple_table
from table_render_runtime import (
    fill_table_cell_impl,
    render_block_annotations_impl,
    render_large_table_fallback_impl,
    render_large_table_if_needed_impl,
    render_standard_html_table_impl,
)
from input_adapter_runtime import (
    build_legacy_pages,
    build_missing_content_list_message,
    build_v2_pages,
    clean_text,
    collect_middle_visual_blocks,
    collect_text_from_fields,
    collect_visual_block_metadata,
    coerce_text_list,
    extract_first_asset_path,
    extract_first_html,
    extract_middle_block_text,
    find_first_file,
    find_nearby_content_directories,
    has_content_list_payload,
    is_empty_table_placeholder,
    is_supported_input_path,
    join_text_fragments,
    load_content_pages,
    load_middle_pages,
    load_pages,
    looks_like_asset_path,
    looks_like_html,
    looks_like_project_root,
    materialize_input,
    normalize_asset_path,
    normalize_visual_key,
    parse_bbox,
    parse_legacy_block,
    parse_middle_discarded_block,
    parse_page_size,
    parse_v2_block,
    parse_v2_page_decoration_block,
    parse_v2_text_block,
    parse_visual_block,
    resolve_asset_path,
)
from page_repair_runtime import (
    attach_table_continuations,
    backfill_middle_visual_metadata,
    bbox_distance,
    collect_placeholder_continuation_heights,
    find_best_visual_match,
    get_page_body_blocks,
    merge_middle_header_footer_blocks,
    merge_page_with_middle,
    repair_and_sort_pages,
)
from page_layout_runtime import (
    build_document,
    build_regions,
    classify_body_block,
    configure_section,
    count_toc_like_entries,
    detect_two_col_bands,
    extract_document_identity,
    fill_template_intro,
    group_rows,
    is_landscape_page,
    is_primary_product_title,
    is_toc_continuation_page,
    is_toc_page,
    looks_like_toc_entry_text,
    prepare_body_render_plan,
    prepare_document_section,
    render_block_into_container,
    render_blocks_in_cell,
    render_document_page,
    render_document_page_body,
    render_footer,
    render_header,
    render_one_col_region,
    render_page_body,
    render_positioned_lines,
    render_toc_page,
    render_two_col_region,
    render_visual_block,
    resolve_toc_page_state,
    should_start_new_section,
    split_page_blocks,
    split_row_text,
)
from render_config_runtime import TerminologyReplacer, build_replacement_pattern
from text_rendering import (
    BODY_FONT,
    SECTION_TITLE_FONT,
    TOP_TITLE_FONT,
    TOC_TITLE_RE,
    append_text_run,
    apply_named_style_config,
    apply_run_defaults,
    apply_style_if_exists,
    clean_tex_fragment,
    compute_toc_indent_pt,
    convert_inline_tex_to_html,
    convert_simple_tex_expr,
    fill_body_paragraph,
    fill_list_paragraph,
    fill_rich_text,
    fill_title_paragraph,
    fill_toc_entry_paragraph,
    fill_toc_title_paragraph,
    get_style_config,
    get_toc_style_name,
    infer_heading_level,
    is_cover_title,
    looks_like_heading_text,
    normalize_formula_text,
    normalize_list_item,
    normalize_toc_text,
    parse_alignment,
    parse_rgb_color,
    prepare_text,
    render_html_children,
    render_inline_html_into_paragraph,
    render_inline_markup_fragment,
    render_markup_children,
    render_normalized_text_fragment,
    replace_control_word,
)
from translation_runtime import (
    TranslationConfig,
    apply_translation_responses,
    load_translation_response_file,
    write_translation_request_file,
)

input_adapter_runtime.bind_runtime(sys.modules[__name__])
page_layout_runtime.bind_runtime(sys.modules[__name__])
page_repair_runtime.bind_runtime(sys.modules[__name__])
render_config_runtime.bind_runtime(sys.modules[__name__])
text_rendering.bind_runtime(sys.modules[__name__])


A4_WIDTH = Mm(210)
A4_HEIGHT = Mm(297)
PAGE_MARGIN = Mm(15)
HEADER_FOOTER_FONT = Pt(8.5)
CAPTION_FONT = Pt(9)
FOOTNOTE_FONT = Pt(8)
MIN_VISUAL_WIDTH = Mm(45)
VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}
MAX_COMPLEX_TABLE_ROWS = 400
MAX_COMPLEX_TABLE_HTML_LEN = 30000
DEFAULT_TEMPLATE_CANDIDATES = (
    Path("template/datasheet_template.docx"),
    Path("templates/datasheet_template.docx"),
    Path(__file__).parent / "template/datasheet_template.docx",
    Path(__file__).parent / "templates/datasheet_template.docx",
)
DEFAULT_SUBSCRIPT_CONFIG_CANDIDATES = (
    Path("template_configs/subscripts_dictionary.yaml"),
    Path("subscripts_dictionary.yaml"),
    Path(__file__).parent / "template_configs" / "subscripts_dictionary.yaml",
)
DEFAULT_LAYOUT_CONFIG_CANDIDATES = (
    Path("template_configs/datasheet_template.yaml"),
    Path(__file__).parent / "template_configs" / "datasheet_template.yaml",
)
PRODUCT_TITLE_RE = re.compile(r"^(?P<part>[A-Z0-9xX,+/\- ]{3,})\s+(?P<category>.+)$")
TOC_ENTRY_RE = re.compile(
    r"^(?:(?:\d+[、.])|(?:\d+\.\d+)|(?:附录\s*[A-Z\d.\-]+)|(?:appendix\s+[A-Z\d.\-]+)|(?:(?:表|table|图|figure)\s*[A-Z\d.\-]+)|(?:chapter|section|part)\s+(?:[ivxlcdm]+|\d+)).*",
    re.IGNORECASE,
)
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
TABLE_BORDER_COLOR = "C7CDD4"
TABLE_HEADER_FILL = "EEF3F8"
TABLE_OUTER_BORDER_SZ = "8"
TABLE_INNER_BORDER_SZ = "4"


# =========================
# PyCharm 直接运行配置区
# =========================
# 使用方式：
# 1. 想在 PyCharm 中直接点运行时，把 ENABLE_PYCHARM_RUN_CONFIG 改成 True。
# 2. 把 INPUT_PATH / OUTPUT_PATH 改成你要处理的实际路径。
# 3. 其余选项按需调整；不填则走默认模板和默认术语表。
# 4. 保持 False 时，脚本按命令行参数模式运行；需要 PyCharm 直跑时再显式改成 True。
ENABLE_PYCHARM_RUN_CONFIG = False

PYCHARM_RUN_CONFIG = {
    # 必填：MinerU 输出目录或 zip 文件路径。
    "input_path": "/Users/sc/MinerU/OPFA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4",
    # 选填：输出 docx 路径；留空则按默认规则生成。
    "output_path": "/Users/sc/MinerU/md2word_file/out_file/OPA228_P1.docx",
    # 选填：模板路径；留空时自动查找默认模板。
    "template_path": "/Users/sc/MinerU/md2word_file/template/datasheet_template.docx",
    # 选填：术语表路径；留空时自动查找默认术语表。
    "subscript_config": "/Users/sc/MinerU/md2word_file/template_configs/subscripts_dictionary.yaml",
    # True 表示不使用模板；一般保持 False。
    "no_template": False,
    # True 表示用 MinerU 页眉页脚覆盖模板页眉页脚；一般保持 False。
    "use_mineru_header_footer": False,
    # 文档语言：auto / zh / en。auto 会按正文内容自动判断。
    "document_language": "auto",
    # 转换模式：direct 表示直接生成当前语言的 Word；en2zh 表示英文 PDF 走翻译生成中文 Word。
    "translation_mode": "direct",
    # 选填：导出给 LLM 的最小翻译请求 JSON；填写后若没有 translation_response，则只导出请求并退出。
    "translation_request_output": "",
    # 选填：LLM 返回的译文 JSON；填写后会先回填译文，再生成 DOCX。
    "translation_response": "",
    # 选填：直接调用 LLM 时使用的模型和 API 基础地址；api_key 默认取 OPENAI_API_KEY。
    "translation_model": APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL,
    "translation_api_key": "",
    "translation_base_url": "",
    # 分批策略：页数是软上限，字符数是硬上限。
    "translation_max_pages": APP_CONFIG.translation_max_pages,
    "translation_max_chars": APP_CONFIG.translation_max_chars,
    # 日志级别：DEBUG / INFO / WARNING / ERROR
    "log_level": "DEBUG",
}


@dataclass(slots=True)
class Block:
    type: str
    bbox: tuple[float, float, float, float]
    text: str = ""
    items: list[str] = field(default_factory=list)
    level: int = 1
    image_path: Path | None = None
    captions: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    html: str | None = None
    page_idx: int | None = None
    block_idx: int | None = None
    continuation_heights: list[float] = field(default_factory=list)

    @property
    def x1(self) -> float:
        return self.bbox[0]

    @property
    def y1(self) -> float:
        return self.bbox[1]

    @property
    def x2(self) -> float:
        return self.bbox[2]

    @property
    def y2(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def mid_y(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2


@dataclass(slots=True)
class Region:
    kind: str
    blocks: list[Block]


@dataclass(slots=True)
class PageData:
    page_idx: int
    blocks: list[Block]
    page_size: tuple[float, float] | None = None


@dataclass(slots=True)
class MiddlePage:
    page_idx: int
    page_size: tuple[float, float] | None = None
    discarded_blocks: list[Block] = field(default_factory=list)
    visual_blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class SectionLayout:
    top_margin: Any
    bottom_margin: Any
    left_margin: Any
    right_margin: Any
    header_distance: Any
    footer_distance: Any


@dataclass(slots=True)
class RenderConfig:
    section_layout: SectionLayout
    use_mineru_header_footer: bool
    terminology: "TerminologyReplacer | None" = None
    paragraph_styles: dict[str, "ParagraphStyleConfig"] = field(default_factory=dict)


@dataclass(slots=True)
class ParagraphStyleConfig:
    font_name: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None
    alignment: str | None = None
    line_spacing: float | None = None
    space_before: float | None = None
    space_after: float | None = None
    first_line_indent_pt: float | None = None
    left_indent_pt: float | None = None
    right_indent_pt: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 MinerU 目录或 zip 包，结合模板生成近似保留版式的 DOCX。"
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=None,
        help="MinerU 输出目录或 zip 文件。留空时优先使用当前目录；若当前目录是脚本工程目录，则回退到已配置的 PYCHARM_RUN_CONFIG。",
    )
    parser.add_argument(
        "--output",
        help="输出 DOCX 路径。默认目录输入写到目录下，zip 输入写到 zip 同名 .docx。",
    )
    parser.add_argument(
        "--template",
        help="Word 模板路径。默认自动查找 template/datasheet_template.docx。",
    )
    parser.add_argument(
        "--no-template",
        action="store_true",
        help="不使用模板，直接生成纯文档。",
    )
    parser.add_argument(
        "--use-mineru-header-footer",
        action="store_true",
        help="使用 MinerU 识别出的页眉页脚覆盖模板页眉页脚。",
    )
    parser.add_argument(
        "--subscript-config",
        help="术语/上下标 YAML 路径。默认自动查找 template_configs/subscripts_dictionary.yaml。",
    )
    parser.add_argument(
        "--document-language",
        choices=("auto", "zh", "en"),
        default="auto",
        help="文档语言。默认 auto 自动判断；en 会启用英文友好的标题/目录规则和排版覆盖。",
    )
    parser.add_argument(
        "--translation-mode",
        choices=("direct", "en2zh", "none", "llm_en_to_zh"),
        default="direct",
        help="翻译模式。默认 direct；en2zh 会先调 LLM 把英文文档译成中文，再生成 Word。",
    )
    parser.add_argument(
        "--translation-request-output",
        help="导出给 LLM 的最小翻译请求 JSON。未同时提供 --translation-response 时，只导出请求并退出。",
    )
    parser.add_argument(
        "--translation-response",
        help="LLM 返回的译文 JSON；提供后会按 ID 回填译文再生成 DOCX。",
    )
    parser.add_argument(
        "--translation-max-pages",
        type=int,
        default=APP_CONFIG.translation_max_pages,
        help="翻译分批页数软上限。默认 20。",
    )
    parser.add_argument(
        "--translation-max-chars",
        type=int,
        default=APP_CONFIG.translation_max_chars,
        help="翻译分批字符数硬上限。默认 60000。",
    )
    parser.add_argument(
        "--translation-model",
        default=APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL,
        help="en2zh 模式下使用的模型名。",
    )
    parser.add_argument(
        "--translation-api-key",
        help="en2zh 模式下可选的 API key。未提供时读取 OPENAI_API_KEY。",
    )
    parser.add_argument(
        "--translation-base-url",
        help="en2zh 模式下可选的 OpenAI 兼容 base_url。默认读取 OPENAI_BASE_URL。",
    )
    return parser.parse_args()


def normalize_translation_mode(mode: str | None) -> str:
    normalized = str(mode or "direct").strip().lower()
    if normalized in {"none", "direct", "zh2zh", "zh_to_zh"}:
        return "direct"
    if normalized in {"en2zh", "llm_en_to_zh", "en_to_zh"}:
        return "en2zh"
    raise ValueError(f"不支持的 translation_mode: {mode}")


def main() -> None:
    configure_logging(PYCHARM_RUN_CONFIG.get("log_level", "INFO") if ENABLE_PYCHARM_RUN_CONFIG else "INFO")
    if ENABLE_PYCHARM_RUN_CONFIG:
        run_with_pycharm_config()
        return

    args = parse_args()
    run_conversion(**resolve_cli_run_options(args))


def run_with_pycharm_config() -> None:
    """
    供 PyCharm 直接运行时使用。

    这里故意不依赖 argparse，方便用户在代码里直接填绝对路径后点击运行。
    """
    if not str(PYCHARM_RUN_CONFIG.get("input_path", "")).strip():
        raise ValueError("PYCHARM_RUN_CONFIG['input_path'] 不能为空。")

    run_conversion(
        input_path=PYCHARM_RUN_CONFIG["input_path"],
        output_path=PYCHARM_RUN_CONFIG.get("output_path"),
        template_path=PYCHARM_RUN_CONFIG.get("template_path"),
        subscript_config=PYCHARM_RUN_CONFIG.get("subscript_config"),
        no_template=bool(PYCHARM_RUN_CONFIG.get("no_template", False)),
        use_mineru_header_footer=bool(PYCHARM_RUN_CONFIG.get("use_mineru_header_footer", False)),
        document_language=str(PYCHARM_RUN_CONFIG.get("document_language", "auto") or "auto"),
        translation_mode=normalize_translation_mode(str(PYCHARM_RUN_CONFIG.get("translation_mode", "direct") or "direct")),
        translation_request_output=str(PYCHARM_RUN_CONFIG.get("translation_request_output", "") or "") or None,
        translation_response=str(PYCHARM_RUN_CONFIG.get("translation_response", "") or "") or None,
        translation_model=str(PYCHARM_RUN_CONFIG.get("translation_model", llm_client.DEFAULT_MODEL) or llm_client.DEFAULT_MODEL),
        translation_api_key=str(PYCHARM_RUN_CONFIG.get("translation_api_key", "") or "") or None,
        translation_base_url=str(PYCHARM_RUN_CONFIG.get("translation_base_url", "") or "") or None,
        translation_max_pages=int(PYCHARM_RUN_CONFIG.get("translation_max_pages", APP_CONFIG.translation_max_pages) or APP_CONFIG.translation_max_pages),
        translation_max_chars=int(PYCHARM_RUN_CONFIG.get("translation_max_chars", APP_CONFIG.translation_max_chars) or APP_CONFIG.translation_max_chars),
    )


def resolve_cli_run_options(args: argparse.Namespace) -> dict[str, Any]:
    input_path = args.input_path
    output_path = args.output
    template_path = args.template
    subscript_config = args.subscript_config
    no_template = args.no_template
    use_mineru_header_footer = args.use_mineru_header_footer
    document_language = getattr(args, "document_language", "auto")
    translation_mode = normalize_translation_mode(getattr(args, "translation_mode", "direct"))
    translation_request_output = getattr(args, "translation_request_output", None)
    translation_response = getattr(args, "translation_response", None)
    translation_model = getattr(args, "translation_model", llm_client.DEFAULT_MODEL)
    translation_api_key = getattr(args, "translation_api_key", None)
    translation_base_url = getattr(args, "translation_base_url", None)
    translation_max_pages = getattr(args, "translation_max_pages", translation_runtime.DEFAULT_MAX_PAGES_PER_BATCH)
    translation_max_chars = getattr(args, "translation_max_chars", translation_runtime.DEFAULT_MAX_CHARS_PER_BATCH)

    configured_input_path = get_configured_input_path()
    if should_use_pycharm_cli_fallback(input_path, configured_input_path):
        current_dir = Path.cwd().resolve()
        logger.warning(
            "no input_path provided and current directory {} looks like the script project root; fallback to PYCHARM_RUN_CONFIG['input_path']={}",
            current_dir,
            configured_input_path,
        )
        input_path = str(configured_input_path)
        if output_path is None:
            output_path = PYCHARM_RUN_CONFIG.get("output_path")
        if template_path is None:
            template_path = PYCHARM_RUN_CONFIG.get("template_path")
        if subscript_config is None:
            subscript_config = PYCHARM_RUN_CONFIG.get("subscript_config")
        if not no_template:
            no_template = bool(PYCHARM_RUN_CONFIG.get("no_template", False))
        if not use_mineru_header_footer:
            use_mineru_header_footer = bool(PYCHARM_RUN_CONFIG.get("use_mineru_header_footer", False))
        if document_language == "auto":
            document_language = str(PYCHARM_RUN_CONFIG.get("document_language", "auto") or "auto")
        translation_mode = normalize_translation_mode(
            str(PYCHARM_RUN_CONFIG.get("translation_mode", translation_mode) or translation_mode)
        )
        if translation_request_output is None:
            configured_request_output = str(PYCHARM_RUN_CONFIG.get("translation_request_output", "") or "")
            translation_request_output = configured_request_output or None
        if translation_response is None:
            configured_response = str(PYCHARM_RUN_CONFIG.get("translation_response", "") or "")
            translation_response = configured_response or None
        translation_model = str(PYCHARM_RUN_CONFIG.get("translation_model", translation_model) or translation_model)
        if translation_api_key is None:
            configured_api_key = str(PYCHARM_RUN_CONFIG.get("translation_api_key", "") or "")
            translation_api_key = configured_api_key or None
        if translation_base_url is None:
            configured_base_url = str(PYCHARM_RUN_CONFIG.get("translation_base_url", "") or "")
            translation_base_url = configured_base_url or None
        translation_max_pages = int(PYCHARM_RUN_CONFIG.get("translation_max_pages", translation_max_pages) or translation_max_pages)
        translation_max_chars = int(PYCHARM_RUN_CONFIG.get("translation_max_chars", translation_max_chars) or translation_max_chars)
    elif input_path is None:
        input_path = "."

    return {
        "input_path": input_path,
        "output_path": output_path,
        "template_path": template_path,
        "subscript_config": subscript_config,
        "no_template": no_template,
        "use_mineru_header_footer": use_mineru_header_footer,
        "document_language": document_language,
        "translation_mode": translation_mode,
        "translation_request_output": translation_request_output,
        "translation_response": translation_response,
        "translation_model": translation_model,
        "translation_api_key": translation_api_key,
        "translation_base_url": translation_base_url,
        "translation_max_pages": translation_max_pages,
        "translation_max_chars": translation_max_chars,
    }


def should_use_pycharm_cli_fallback(input_path: str | None, configured_input_path: Path | None) -> bool:
    if input_path is not None or configured_input_path is None:
        return False

    current_dir = Path.cwd().resolve()
    if not looks_like_project_root(current_dir):
        return False
    if has_content_list_payload(current_dir):
        return False
    return is_supported_input_path(configured_input_path)


def get_configured_input_path() -> Path | None:
    raw_value = str(PYCHARM_RUN_CONFIG.get("input_path", "")).strip()
    if not raw_value:
        return None

    candidate = Path(raw_value).expanduser().resolve()
    return candidate if is_supported_input_path(candidate) else None


def run_conversion(
    *,
    input_path: str,
    output_path: str | None,
    template_path: str | None,
    subscript_config: str | None,
    no_template: bool,
    use_mineru_header_footer: bool,
    document_language: str = "auto",
    translation_mode: str = "direct",
    translation_request_output: str | None = None,
    translation_response: str | None = None,
    translation_model: str = llm_client.DEFAULT_MODEL,
    translation_api_key: str | None = None,
    translation_base_url: str | None = None,
    translation_max_pages: int = APP_CONFIG.translation_max_pages,
    translation_max_chars: int = APP_CONFIG.translation_max_chars,
) -> None:
    """
    统一的转换入口。

    命令行模式和 PyCharm 代码内配置模式都走这里，避免两套逻辑后续再分叉。
    """
    original_input = Path(input_path).expanduser().resolve()
    resolved_output_path = resolve_output_path(original_input, output_path)
    resolved_template_path = None if no_template else resolve_template_path(template_path)
    resolved_subscript_config = Path(subscript_config).expanduser().resolve() if subscript_config else None
    resolved_translation_request_output = (
        Path(translation_request_output).expanduser().resolve() if translation_request_output else None
    )
    resolved_translation_response = Path(translation_response).expanduser().resolve() if translation_response else None

    logger.info("start conversion input={} output={}", original_input, resolved_output_path)
    translation_mode = normalize_translation_mode(translation_mode)
    logger.debug(
        "conversion options template={} subscript_config={} no_template={} use_mineru_header_footer={} document_language={} translation_mode={} translation_request_output={} translation_response={} translation_model={} translation_api_key_present={} translation_base_url={}",
        resolved_template_path,
        resolved_subscript_config,
        no_template,
        use_mineru_header_footer,
        document_language,
        translation_mode,
        resolved_translation_request_output,
        resolved_translation_response,
        translation_model,
        bool(translation_api_key),
        translation_base_url,
    )

    template_document = Document(str(resolved_template_path)) if resolved_template_path else None
    with materialize_input(original_input) as package_root:
        pages, source_path = load_pages(package_root)
        translation_config = build_translation_config(
            max_pages=translation_max_pages,
            max_chars=translation_max_chars,
        )
        if translation_mode == "en2zh":
            if resolved_translation_request_output:
                payload = write_translation_request_file(pages, resolved_translation_request_output, translation_config)
                logger.info(
                    "translation request output={} batches={}",
                    resolved_translation_request_output,
                    len(payload.get("batches", [])),
                )
            if resolved_translation_response:
                translations = load_translation_response_file(resolved_translation_response)
                apply_translation_responses(pages, translations)
                logger.info("translation response applied items={}", len(translations))
            else:
                payload = translation_runtime.build_translation_request_payload(pages, translation_config)
                llm_response = llm_client.translate_payload(
                    payload,
                    llm_client.LLMClientConfig(
                        model=translation_model,
                        api_key=translation_api_key,
                        base_url=translation_base_url,
                    ),
                )
                translations = load_translations_from_payload(llm_response)
                apply_translation_responses(pages, translations)
                logger.info(
                    "llm translation applied batches={} items={}",
                    len(llm_response.get("batches", [])),
                    len(translations),
                )
        elif resolved_translation_request_output or resolved_translation_response:
            logger.warning("translation_mode=direct 时忽略 translation_request_output / translation_response")

        preferred_document_language = document_language
        if translation_mode == "en2zh" and document_language == "auto":
            preferred_document_language = "zh"

        resolved_document_language = resolve_document_language(pages, preferred=preferred_document_language)
        render_config = apply_document_language_overrides(
            load_render_config(
                template_document=template_document,
                subscript_config=resolved_subscript_config,
                use_mineru_header_footer=use_mineru_header_footer,
            ),
            resolved_document_language,
        )
        logger.info("document_language={}", resolved_document_language)
        document = build_document(pages, render_config, template_document)
        document.core_properties.title = source_path.stem
        document.save(resolved_output_path)

    logger.info("source={}", source_path)
    logger.info("output={}", resolved_output_path)
    logger.info("pages={}", len(pages))
    logger.info("template={}", resolved_template_path if resolved_template_path else "none")


def build_translation_config(*, max_pages: int, max_chars: int) -> TranslationConfig:
    return TranslationConfig(
        target_language=translation_runtime.DEFAULT_TARGET_LANGUAGE,
        domain=translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
        max_pages_per_batch=max(int(max_pages), 1),
        max_chars_per_batch=max(int(max_chars), 1),
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


def configure_logging(level_name: str) -> None:
    logger.remove()
    logger.add(
        sink=sys.stderr,
        level=str(level_name).upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=False,
        diagnose=False,
    )


def resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).resolve()
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        return input_path.with_suffix(".docx")
    return input_path / "mineru_output.docx"

def resolve_template_path(template_arg: str | None) -> Path | None:
    if template_arg:
        candidate = Path(template_arg).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"模板文件不存在: {candidate}")
        return candidate

    for candidate in DEFAULT_TEMPLATE_CANDIDATES:
        resolved = candidate if candidate.is_absolute() else candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def find_subscript_config_path() -> Path | None:
    return render_config_runtime.find_subscript_config_path(DEFAULT_SUBSCRIPT_CONFIG_CANDIDATES)


def find_layout_config_path() -> Path | None:
    return render_config_runtime.find_layout_config_path(DEFAULT_LAYOUT_CONFIG_CANDIDATES)


def load_render_config(
    template_document: Any | None,
    subscript_config: Path | None,
    use_mineru_header_footer: bool,
) -> RenderConfig:
    return render_config_runtime.load_render_config(
        template_document,
        subscript_config,
        use_mineru_header_footer,
        find_layout_config_path_fn=find_layout_config_path,
        load_section_layout_fn=load_section_layout,
        terminology_factory=TerminologyReplacer,
        load_paragraph_styles_fn=load_paragraph_styles,
        render_config_cls=RenderConfig,
    )


def resolve_document_language(pages: list[PageData], *, preferred: str = "auto") -> str:
    normalized = str(preferred or "auto").strip().lower()
    if normalized in {"zh", "en"}:
        return normalized
    return detect_document_language(pages)


def detect_document_language(pages: list[PageData]) -> str:
    sample_fragments: list[str] = []
    for page in pages[: min(len(pages), 12)]:
        for block in get_page_body_blocks(page):
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
        if style_name in ENGLISH_STYLE_NAMES and (
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


def build_replacement_pattern(source: str) -> str:
    return render_config_runtime.build_replacement_pattern(source)


def create_document(template_document: Any | None) -> Document:
    return template_document if template_document is not None else Document()


def clear_document_body(document: Document) -> None:
    body = document._body._element
    sect_pr = body.sectPr
    for child in list(body):
        if child is sect_pr:
            continue
        body.remove(child)


def clone_first_section_layout(document: Document) -> None:
    if len(document.sections) <= 1:
        return

    base_section = document.sections[0]
    for section in document.sections[1:]:
        section.page_width = base_section.page_width
        section.page_height = base_section.page_height
        section.orientation = base_section.orientation
        section.left_margin = base_section.left_margin
        section.right_margin = base_section.right_margin
        section.top_margin = base_section.top_margin
        section.bottom_margin = base_section.bottom_margin
        section.header_distance = base_section.header_distance
        section.footer_distance = base_section.footer_distance
        section.header.is_linked_to_previous = True
        section.footer.is_linked_to_previous = True


def render_block_annotations(container: Any, block: Block, render_config: RenderConfig) -> None:
    render_block_annotations_impl(
        container,
        block,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        fill_rich_text_fn=fill_rich_text,
        prepare_text_fn=prepare_text,
    )


def render_table_from_html(
    container: Any,
    block: Block,
    usable_width: int,
    render_config: RenderConfig,
) -> bool:
    logger.debug(
        "render html table page={} block={} bbox={} caption={} raw_html_len={}",
        block.page_idx,
        block.block_idx,
        block.bbox,
        block.captions[0] if block.captions else "N/A",
        len(block.html or ""),
    )
    prepared_table = prepare_html_table_model(block, render_config)
    if prepared_table is None:
        return False

    html, table_model, max_cols = prepared_table

    logger.debug(
        "parsed html table page={} block={} rows={} max_cols={}",
        block.page_idx,
        block.block_idx,
        len(table_model.rows),
        max_cols,
    )

    if render_large_table_if_needed(container, block, table_model, max_cols, len(html or ""), render_config, usable_width):
        return True

    merge_failures = render_standard_html_table(container, table_model, max_cols, usable_width, render_config)

    render_block_annotations(container, block, render_config)

    if merge_failures > 0:
        logger.warning(
            "table merge fallback page={} block={} bbox={} count={} caption={}",
            block.page_idx,
            block.block_idx,
            block.bbox,
            merge_failures,
            block.captions[0] if block.captions else "N/A",
        )

    logger.debug(
        "rendered html table page={} block={} rows={} max_cols={} merge_failures={}",
        block.page_idx,
        block.block_idx,
        len(table_model.rows),
        max_cols,
        merge_failures,
    )

    return True


def prepare_html_table_model(
    block: Block,
    render_config: RenderConfig,
) -> tuple[str | None, "HtmlTable", int] | None:
    html = block.html
    if render_config.terminology:
        html = render_config.terminology.replace_html(html)

    table_model = parse_html_table(html)
    if not table_model or not table_model.rows:
        logger.warning(
            "skip html table page={} block={} because parsed rows are empty caption={}",
            block.page_idx,
            block.block_idx,
            block.captions[0] if block.captions else "N/A",
        )
        return None

    max_cols = table_model.max_columns
    if max_cols <= 0:
        logger.warning(
            "skip html table page={} block={} because max_cols<=0 caption={}",
            block.page_idx,
            block.block_idx,
            block.captions[0] if block.captions else "N/A",
        )
        return None

    return html, table_model, max_cols


def render_large_table_if_needed(
    container: Any,
    block: Block,
    table_model: "HtmlTable",
    max_cols: int,
    html_len: int,
    render_config: RenderConfig,
    usable_width: int,
) -> bool:
    def render_long_simple_table_adapter(
        target_container: Any,
        target_block: Block,
        target_table_model: HtmlTable,
        target_render_config: RenderConfig,
        target_usable_width: int,
    ) -> None:
        render_long_simple_table(
            target_container,
            target_block,
            target_table_model,
            target_render_config,
            target_usable_width,
            apply_named_style_config_fn=apply_named_style_config,
            fill_rich_text_fn=fill_rich_text,
            prepare_text_fn=prepare_text,
            fill_table_cell_fn=fill_table_cell,
            remove_table_borders_fn=remove_table_borders,
            get_style_config_fn=get_style_config,
        )

    return render_large_table_if_needed_impl(
        container,
        block,
        table_model,
        max_cols,
        html_len,
        render_config,
        usable_width,
        max_complex_rows=MAX_COMPLEX_TABLE_ROWS,
        max_complex_html_len=MAX_COMPLEX_TABLE_HTML_LEN,
        is_long_simple_table_fn=is_long_simple_table,
        render_long_simple_table_fn=render_long_simple_table_adapter,
        render_large_table_fallback_fn=render_large_table_fallback,
        logger=logger,
    )


def render_standard_html_table(
    container: Any,
    table_model: "HtmlTable",
    max_cols: int,
    usable_width: int,
    render_config: RenderConfig,
) -> int:
    return render_standard_html_table_impl(
        container,
        table_model,
        max_cols,
        usable_width,
        render_config,
        remove_table_borders_fn=remove_table_borders,
        fill_table_cell_fn=fill_table_cell,
    )


def render_large_table_fallback(
    container: Any,
    block: Block,
    table_model: "HtmlTable",
    render_config: RenderConfig,
    usable_width: int,
) -> None:
    render_large_table_fallback_impl(
        container,
        block,
        table_model,
        render_config,
        usable_width,
        compute_visual_width_fn=compute_visual_width,
        remove_table_borders_fn=remove_table_borders,
        fill_table_cell_fn=fill_table_cell,
        render_block_annotations_fn=render_block_annotations,
        html_cell_cls=HtmlCell,
    )


def fill_table_cell(cell: Any, cell_model: "HtmlCell", is_header: bool, render_config: RenderConfig) -> None:
    fill_table_cell_impl(
        cell,
        cell_model,
        is_header,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        render_inline_html_into_paragraph_fn=render_inline_html_into_paragraph,
        prepare_text_fn=prepare_text,
    )
    if is_header:
        apply_table_header_cell_style(cell)


def compute_visual_width(block: Block, page_width: float, usable_width: int) -> int:
    ratio = min(max(block.width / max(page_width, 1.0), 0.45), 1.0)
    width_by_ratio = int(usable_width * ratio)
    min_width = int(Emu(MIN_VISUAL_WIDTH))
    return min(max(width_by_ratio, min_width), int(usable_width))

def remove_table_borders(table: Any) -> None:
    table_element = table._tbl
    table_properties = table_element.tblPr
    borders = table_properties.find(qn("w:tblBorders"))
    if borders is not None:
        table_properties.remove(borders)

    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), TABLE_OUTER_BORDER_SZ)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), TABLE_BORDER_COLOR)
        borders.append(element)
    for edge in ("insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), TABLE_INNER_BORDER_SZ)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), TABLE_BORDER_COLOR)
        borders.append(element)
    table_properties.append(borders)


def apply_table_header_cell_style(cell: Any) -> None:
    cell_properties = cell._tc.get_or_add_tcPr()
    shading = cell_properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        cell_properties.append(shading)
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), TABLE_HEADER_FILL)


if __name__ == "__main__":
    main()
