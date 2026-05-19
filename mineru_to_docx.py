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
from app.conversion import runtime_helpers, runtime_models, runtime_rendering_api, runtime_runner
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
MIN_VISUAL_WIDTH = runtime_rendering_api.MIN_VISUAL_WIDTH
VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}
MAX_COMPLEX_TABLE_ROWS = runtime_rendering_api.MAX_COMPLEX_TABLE_ROWS
MAX_COMPLEX_TABLE_HTML_LEN = runtime_rendering_api.MAX_COMPLEX_TABLE_HTML_LEN
DEFAULT_TEMPLATE_CANDIDATES = runtime_runner.DEFAULT_TEMPLATE_CANDIDATES
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
TABLE_BORDER_COLOR = runtime_rendering_api.TABLE_BORDER_COLOR
TABLE_HEADER_FILL = runtime_rendering_api.TABLE_HEADER_FILL
TABLE_OUTER_BORDER_SZ = runtime_rendering_api.TABLE_OUTER_BORDER_SZ
TABLE_INNER_BORDER_SZ = runtime_rendering_api.TABLE_INNER_BORDER_SZ


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


Block = runtime_models.Block
Region = runtime_models.Region
PageData = runtime_models.PageData
MiddlePage = runtime_models.MiddlePage
SectionLayout = runtime_models.SectionLayout
RenderConfig = runtime_models.RenderConfig
ParagraphStyleConfig = runtime_models.ParagraphStyleConfig


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
    兼容入口：CLI 仍从 root script 进入，真实实现已迁到 shared runner。
    """
    runtime_runner.run_conversion(
        input_path=input_path,
        output_path=output_path,
        template_path=template_path,
        subscript_config=subscript_config,
        no_template=no_template,
        use_mineru_header_footer=use_mineru_header_footer,
        document_language=document_language,
        translation_mode=normalize_translation_mode(translation_mode),
        translation_request_output=translation_request_output,
        translation_response=translation_response,
        translation_model=translation_model,
        translation_api_key=translation_api_key,
        translation_base_url=translation_base_url,
        translation_max_pages=translation_max_pages,
        translation_max_chars=translation_max_chars,
    )


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


# Shared helper aliases stay on the root module for CLI/runtime compatibility.
build_translation_config = runtime_helpers.build_translation_config
load_translations_from_payload = runtime_helpers.load_translations_from_payload
resolve_output_path = runtime_helpers.resolve_output_path
resolve_document_language = runtime_helpers.resolve_document_language
detect_document_language = runtime_helpers.detect_document_language
apply_document_language_overrides = runtime_helpers.apply_document_language_overrides
load_section_layout = runtime_helpers.load_section_layout
load_paragraph_styles = runtime_helpers.load_paragraph_styles
build_replacement_pattern = render_config_runtime.build_replacement_pattern


def resolve_template_path(template_arg: str | None) -> Path | None:
    return runtime_helpers.resolve_template_path(template_arg, DEFAULT_TEMPLATE_CANDIDATES)


def find_subscript_config_path() -> Path | None:
    return render_config_runtime.find_subscript_config_path(DEFAULT_SUBSCRIPT_CONFIG_CANDIDATES)


def find_layout_config_path() -> Path | None:
    return render_config_runtime.find_layout_config_path(DEFAULT_LAYOUT_CONFIG_CANDIDATES)


def load_render_config(
    template_document: Any | None,
    subscript_config: Path | None,
    use_mineru_header_footer: bool,
) -> RenderConfig:
    return runtime_helpers.load_render_config(
        template_document,
        subscript_config,
        use_mineru_header_footer,
        default_layout_candidates=DEFAULT_LAYOUT_CONFIG_CANDIDATES,
    )


create_document = runtime_rendering_api.create_document
clear_document_body = runtime_rendering_api.clear_document_body
clone_first_section_layout = runtime_rendering_api.clone_first_section_layout
render_block_annotations = runtime_rendering_api.render_block_annotations
render_table_from_html = runtime_rendering_api.render_table_from_html
prepare_html_table_model = runtime_rendering_api.prepare_html_table_model
render_large_table_if_needed = runtime_rendering_api.render_large_table_if_needed
render_standard_html_table = runtime_rendering_api.render_standard_html_table
render_large_table_fallback = runtime_rendering_api.render_large_table_fallback
fill_table_cell = runtime_rendering_api.fill_table_cell
compute_visual_width = runtime_rendering_api.compute_visual_width
remove_table_borders = runtime_rendering_api.remove_table_borders
apply_table_header_cell_style = runtime_rendering_api.apply_table_header_cell_style


if __name__ == "__main__":
    main()
