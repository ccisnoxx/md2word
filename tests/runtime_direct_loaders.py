from __future__ import annotations

# tests/runtime_direct_loaders.py: 提供 conversion runtime characterization tests 的直接模块加载器。

import importlib
import re
import argparse
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PKG = "app.conversion.runtime"


def _install_dependency_stubs() -> None:
    yaml_mod = types.ModuleType("yaml")
    yaml_mod.safe_load = lambda *_args, **_kwargs: {}
    sys.modules["yaml"] = yaml_mod

    bs4_mod = types.ModuleType("bs4")

    class DummyNavigableString(str):
        pass

    class DummyTag:
        def __init__(self, name="root"):
            self.name = name
            self.children = []
            self.contents = []
            self.parent = None

        def find(self, *_args, **_kwargs):
            return None

        def find_all(self, *_args, **_kwargs):
            return []

    class DummyBeautifulSoup:
        def __init__(self, *_args, **_kwargs):
            self.contents = []

        def find(self, *_args, **_kwargs):
            return None

        def find_all(self, *_args, **_kwargs):
            return []

    bs4_mod.BeautifulSoup = DummyBeautifulSoup
    bs4_mod.NavigableString = DummyNavigableString
    bs4_mod.Tag = DummyTag
    sys.modules["bs4"] = bs4_mod

    docx_mod = types.ModuleType("docx")

    class DummyDocument:
        def __init__(self, *_args, **_kwargs):
            self.sections = [types.SimpleNamespace()]

    docx_mod.Document = DummyDocument
    sys.modules["docx"] = docx_mod

    section_mod = types.ModuleType("docx.enum.section")
    section_mod.WD_ORIENTATION = types.SimpleNamespace(LANDSCAPE="landscape", PORTRAIT="portrait")
    section_mod.WD_SECTION_START = types.SimpleNamespace(NEW_PAGE="new-page")
    sys.modules["docx.enum.section"] = section_mod

    table_mod = types.ModuleType("docx.enum.table")
    table_mod.WD_CELL_VERTICAL_ALIGNMENT = types.SimpleNamespace(CENTER="center", TOP="top")
    table_mod.WD_TABLE_ALIGNMENT = types.SimpleNamespace(CENTER="center")
    sys.modules["docx.enum.table"] = table_mod

    text_mod = types.ModuleType("docx.enum.text")
    text_mod.WD_ALIGN_PARAGRAPH = types.SimpleNamespace(LEFT="left", CENTER="center", RIGHT="right", JUSTIFY="justify")
    text_mod.WD_BREAK = types.SimpleNamespace(PAGE="page")
    text_mod.WD_LINE_SPACING = types.SimpleNamespace(MULTIPLE="multiple")
    text_mod.WD_TAB_ALIGNMENT = types.SimpleNamespace(CENTER="center", RIGHT="right")
    sys.modules["docx.enum.text"] = text_mod

    oxml_mod = types.ModuleType("docx.oxml")

    class DummyOxmlElement:
        def __init__(self, tag):
            self.tag = tag
            self.attrs = {}
            self.children = []

        def set(self, key, value):
            self.attrs[key] = value

        def append(self, child):
            self.children.append(child)

    oxml_mod.OxmlElement = DummyOxmlElement
    sys.modules["docx.oxml"] = oxml_mod

    oxml_ns_mod = types.ModuleType("docx.oxml.ns")
    oxml_ns_mod.qn = lambda value: value
    sys.modules["docx.oxml.ns"] = oxml_ns_mod

    shared_mod = types.ModuleType("docx.shared")
    shared_mod.Emu = lambda value: int(value)
    shared_mod.Mm = lambda value: int(float(value) * 1000)
    shared_mod.Pt = lambda value: value

    class DummyRGBColor:
        def __init__(self, *_args, **_kwargs):
            pass

        @classmethod
        def from_string(cls, _value):
            return cls()

    shared_mod.RGBColor = DummyRGBColor
    sys.modules["docx.shared"] = shared_mod

    loguru_mod = types.ModuleType("loguru")
    loguru_mod.logger = types.SimpleNamespace(
        debug=lambda *_args, **_kwargs: None,
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        add=lambda *_args, **_kwargs: None,
        remove=lambda *_args, **_kwargs: None,
    )
    sys.modules["loguru"] = loguru_mod


def _reset_modules(*module_names: str) -> None:
    for module_name in module_names:
        sys.modules.pop(module_name, None)


def load_llm_client_module():
    _reset_modules(f"{RUNTIME_PKG}.llm_client")
    return importlib.import_module(f"{RUNTIME_PKG}.llm_client")


def load_render_config_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.render_config_runtime",
        "app.conversion.runtime_models",
        "app.conversion.runtime_helpers",
        f"{RUNTIME_PKG}.page_repair_runtime",
        f"{RUNTIME_PKG}.text_rendering",
        f"{RUNTIME_PKG}.translation_runtime",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    runtime_helpers = importlib.import_module("app.conversion.runtime_helpers")
    module = importlib.import_module(f"{RUNTIME_PKG}.render_config_runtime")
    original_load_render_config = module.load_render_config
    original_load_section_layout = module.load_section_layout
    original_load_paragraph_styles = module.load_paragraph_styles
    original_load_table_style = module.load_table_style
    module.SectionLayout = runtime_models.SectionLayout
    module.RenderConfig = runtime_models.RenderConfig
    module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    module.TableStyleConfig = runtime_models.TableStyleConfig
    module.Block = runtime_models.Block
    module.PageData = runtime_models.PageData
    module.Mm = sys.modules["docx.shared"].Mm
    module.PAGE_MARGIN = module.Mm(15)

    def _load_section_layout(template_document=None, config_path=None):
        return original_load_section_layout(
            template_document,
            config_path,
            page_margin=module.PAGE_MARGIN,
            mm_fn=module.Mm,
            section_layout_cls=runtime_models.SectionLayout,
        )

    def _load_paragraph_styles(config_path=None):
        return original_load_paragraph_styles(
            config_path,
            paragraph_style_config_cls=runtime_models.ParagraphStyleConfig,
        )

    def _load_table_style(config_path=None):
        return original_load_table_style(
            config_path,
            table_style_config_cls=runtime_models.TableStyleConfig,
        )

    def _load_render_config(template_document, subscript_config, use_mineru_header_footer):
        return original_load_render_config(
            template_document,
            subscript_config,
            use_mineru_header_footer,
            find_layout_config_path_fn=module.find_layout_config_path,
            load_section_layout_fn=module.load_section_layout,
            terminology_factory=module.TerminologyReplacer,
            load_paragraph_styles_fn=module.load_paragraph_styles,
            load_table_style_fn=module.load_table_style,
            render_config_cls=runtime_models.RenderConfig,
        )

    module.load_section_layout = _load_section_layout
    module.load_paragraph_styles = _load_paragraph_styles
    module.load_table_style = _load_table_style
    module.load_render_config = _load_render_config
    module.resolve_document_language = runtime_helpers.resolve_document_language
    module.apply_document_language_overrides = runtime_helpers.apply_document_language_overrides
    return module


def load_text_render_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.text_rendering",
        "app.conversion.runtime_models",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    module = importlib.import_module(f"{RUNTIME_PKG}.text_rendering")
    module.Block = runtime_models.Block
    module.SectionLayout = runtime_models.SectionLayout
    module.RenderConfig = runtime_models.RenderConfig
    module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    module.TableStyleConfig = runtime_models.TableStyleConfig
    module.bind_runtime(module)
    return module


def load_page_repair_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.page_repair_runtime",
        f"{RUNTIME_PKG}.input_adapter_runtime",
        "app.conversion.runtime_models",
        f"{RUNTIME_PKG}.text_rendering",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    text_module = importlib.import_module(f"{RUNTIME_PKG}.text_rendering")
    text_module.Block = runtime_models.Block
    text_module.SectionLayout = runtime_models.SectionLayout
    text_module.RenderConfig = runtime_models.RenderConfig
    text_module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    text_module.bind_runtime(text_module)
    input_module = importlib.import_module(f"{RUNTIME_PKG}.input_adapter_runtime")
    input_module.Block = runtime_models.Block
    input_module.PageData = runtime_models.PageData
    input_module.MiddlePage = runtime_models.MiddlePage
    input_module.VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
    input_module.IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}
    input_module.normalize_formula_text = text_module.normalize_formula_text
    input_module.bind_runtime(input_module)
    module = importlib.import_module(f"{RUNTIME_PKG}.page_repair_runtime")
    module.Block = runtime_models.Block
    module.PageData = runtime_models.PageData
    module.MiddlePage = runtime_models.MiddlePage
    module.VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
    module.load_content_pages = input_module.load_content_pages
    module.load_middle_pages = input_module.load_middle_pages

    def _load_pages(package_root):
        pages, source_path = module.load_content_pages(package_root)
        middle_pages = module.load_middle_pages(package_root)
        merged_pages = module.repair_and_sort_pages(pages, middle_pages)
        module.attach_table_continuations(merged_pages)
        return merged_pages, source_path

    module.load_pages = _load_pages
    module.bind_runtime(module)
    return module


def load_page_layout_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.page_layout_runtime",
        f"{RUNTIME_PKG}.text_rendering",
        "app.conversion.runtime_models",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    text_module = importlib.import_module(f"{RUNTIME_PKG}.text_rendering")
    text_module.Block = runtime_models.Block
    text_module.SectionLayout = runtime_models.SectionLayout
    text_module.RenderConfig = runtime_models.RenderConfig
    text_module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    text_module.bind_runtime(text_module)
    module = importlib.import_module(f"{RUNTIME_PKG}.page_layout_runtime")
    module.Block = runtime_models.Block
    module.PageData = runtime_models.PageData
    module.Region = runtime_models.Region
    module.SectionLayout = runtime_models.SectionLayout
    module.RenderConfig = runtime_models.RenderConfig
    module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    module.TableStyleConfig = runtime_models.TableStyleConfig
    module.TOC_TITLE_RE = text_module.TOC_TITLE_RE
    module.TOC_ENTRY_RE = re.compile(
        r"^(?:\d+[.、]|\d+\.\d+|附录\s*[A-Z\d.\-]+|appendix\s+[A-Z\d.\-]+|(?:表|table|图|figure)\s*[A-Z\d.\-]+|(?:chapter|section|part)\s+(?:[ivxlcdm]+|\d+))",
        re.IGNORECASE,
    )
    module.PRODUCT_TITLE_RE = re.compile(r"^(?P<part>[A-Z0-9xX,+/\- ]{3,})\s+(?P<category>.+)$")
    module.VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
    module.HEADER_FOOTER_FONT = module.Pt(8.5)
    module.create_document = lambda template_document=None: template_document if template_document is not None else module.Document()
    module.clear_document_body = lambda _document: None
    module.clone_first_section_layout = lambda _document: None
    module.fill_title_paragraph = text_module.fill_title_paragraph
    module.fill_body_paragraph = text_module.fill_body_paragraph
    module.fill_list_paragraph = text_module.fill_list_paragraph
    module.is_list_item_text = text_module.is_list_item_text
    module.normalize_list_item = text_module.normalize_list_item
    module.infer_list_item_level = text_module.infer_list_item_level
    module.normalize_toc_text = text_module.normalize_toc_text
    module.infer_heading_level = text_module.infer_heading_level
    module.get_toc_style_name = text_module.get_toc_style_name
    module.fill_toc_entry_paragraph = text_module.fill_toc_entry_paragraph
    module.fill_toc_title_paragraph = text_module.fill_toc_title_paragraph
    module.looks_like_heading_text = text_module.looks_like_heading_text
    module.is_cover_title = text_module.is_cover_title
    module.render_inline_html_into_paragraph = text_module.render_inline_html_into_paragraph
    module.prepare_text = text_module.prepare_text
    module.fill_rich_text = text_module.fill_rich_text
    module.apply_named_style_config = text_module.apply_named_style_config
    module.get_style_config = text_module.get_style_config
    module.apply_run_defaults = text_module.apply_run_defaults
    module.bind_runtime(module)
    return module


def load_render_table_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.text_rendering",
        f"{RUNTIME_PKG}.table_html_parser",
        f"{RUNTIME_PKG}.table_long_renderer",
        f"{RUNTIME_PKG}.table_render_runtime",
        "app.conversion.runtime_models",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    text_module = importlib.import_module(f"{RUNTIME_PKG}.text_rendering")
    text_module.Block = runtime_models.Block
    text_module.SectionLayout = runtime_models.SectionLayout
    text_module.RenderConfig = runtime_models.RenderConfig
    text_module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    text_module.bind_runtime(text_module)
    table_parser = importlib.import_module(f"{RUNTIME_PKG}.table_html_parser")
    long_table = importlib.import_module(f"{RUNTIME_PKG}.table_long_renderer")
    table_runtime = importlib.import_module(f"{RUNTIME_PKG}.table_render_runtime")

    module = types.ModuleType("render_table_runtime_seam")
    module.Block = runtime_models.Block
    module.SectionLayout = runtime_models.SectionLayout
    module.RenderConfig = runtime_models.RenderConfig
    module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    module.TableStyleConfig = runtime_models.TableStyleConfig
    module.HtmlCell = table_parser.HtmlCell
    module.HtmlTable = table_parser.HtmlTable
    module.parse_html_table = table_parser.parse_html_table
    module.table_long_renderer = long_table
    module.is_long_simple_table = long_table.is_long_simple_table
    module.render_long_simple_table = long_table.render_long_simple_table
    module.render_normalized_text_fragment = text_module.render_normalized_text_fragment
    module.apply_run_defaults = text_module.apply_run_defaults
    module.BeautifulSoup = sys.modules["bs4"].BeautifulSoup
    module.render_markup_children = text_module.render_markup_children
    module.apply_named_style_config = text_module.apply_named_style_config
    module.fill_rich_text = text_module.fill_rich_text
    module.prepare_text = text_module.prepare_text
    module.get_style_config = text_module.get_style_config
    module.render_inline_html_into_paragraph = text_module.render_inline_html_into_paragraph
    module.fill_table_cell_impl = table_runtime.fill_table_cell_impl
    module.compute_table_column_widths = table_runtime.compute_table_column_widths
    module.normalize_formula_text = text_module.normalize_formula_text
    module.append_text_run = text_module.append_text_run
    module.render_inline_markup_fragment = text_module.render_inline_markup_fragment
    module.render_html_children = text_module.render_html_children
    module.Emu = sys.modules["docx.shared"].Emu
    module.Mm = sys.modules["docx.shared"].Mm
    module.Pt = sys.modules["docx.shared"].Pt
    module.OxmlElement = sys.modules["docx.oxml"].OxmlElement
    module.qn = sys.modules["docx.oxml.ns"].qn
    module.WD_CELL_VERTICAL_ALIGNMENT = sys.modules["docx.enum.table"].WD_CELL_VERTICAL_ALIGNMENT
    module.WD_TABLE_ALIGNMENT = sys.modules["docx.enum.table"].WD_TABLE_ALIGNMENT
    module.WD_ALIGN_PARAGRAPH = sys.modules["docx.enum.text"].WD_ALIGN_PARAGRAPH
    module.logger = sys.modules["loguru"].logger
    module.MIN_VISUAL_WIDTH = module.Mm(45)
    module.MAX_COMPLEX_TABLE_ROWS = 400
    module.MAX_COMPLEX_TABLE_HTML_LEN = 30000
    module.TABLE_BORDER_COLOR = "C7CDD4"
    module.TABLE_HEADER_FILL = ""
    module.TABLE_OUTER_BORDER_SZ = "8"
    module.TABLE_INNER_BORDER_SZ = "4"

    def render_block_annotations(container, block, render_config):
        return table_runtime.render_block_annotations_impl(
            container,
            block,
            render_config,
            apply_named_style_config_fn=module.apply_named_style_config,
            fill_rich_text_fn=module.fill_rich_text,
            prepare_text_fn=module.prepare_text,
        )

    def render_block_captions(container, block, render_config, *, keep_with_next=False):
        return table_runtime.render_block_captions_impl(
            container,
            block,
            render_config,
            apply_named_style_config_fn=module.apply_named_style_config,
            fill_rich_text_fn=module.fill_rich_text,
            prepare_text_fn=module.prepare_text,
            keep_with_next=keep_with_next,
        )

    def render_block_footnotes(container, block, render_config):
        return table_runtime.render_block_footnotes_impl(
            container,
            block,
            render_config,
            apply_named_style_config_fn=module.apply_named_style_config,
            fill_rich_text_fn=module.fill_rich_text,
            prepare_text_fn=module.prepare_text,
        )

    def prepare_html_table_model(block, render_config):
        html = block.html
        if render_config.terminology:
            html = render_config.terminology.replace_html(html)

        table_model = module.parse_html_table(html)
        if not table_model or not table_model.rows:
            module.logger.warning(
                "skip html table page={} block={} because parsed rows are empty caption={}",
                block.page_idx,
                block.block_idx,
                block.captions[0] if block.captions else "N/A",
            )
            return None

        max_cols = table_model.max_columns
        if max_cols <= 0:
            module.logger.warning(
                "skip html table page={} block={} because max_cols<=0 caption={}",
                block.page_idx,
                block.block_idx,
                block.captions[0] if block.captions else "N/A",
            )
            return None

        return html, table_model, max_cols

    def render_large_table_if_needed(container, block, table_model, max_cols, html_len, render_config, usable_width):
        def render_long_simple_table_adapter(target_container, target_block, target_table_model, target_render_config, target_usable_width):
            module.render_long_simple_table(
                target_container,
                target_block,
                target_table_model,
                target_render_config,
                target_usable_width,
                apply_named_style_config_fn=module.apply_named_style_config,
                fill_rich_text_fn=module.fill_rich_text,
                prepare_text_fn=module.prepare_text,
                fill_table_cell_fn=module.fill_table_cell,
                remove_table_borders_fn=module.remove_table_borders,
                get_style_config_fn=module.get_style_config,
            )

        return table_runtime.render_large_table_if_needed_impl(
            container,
            block,
            table_model,
            max_cols,
            html_len,
            render_config,
            usable_width,
            max_complex_rows=module.MAX_COMPLEX_TABLE_ROWS,
            max_complex_html_len=module.MAX_COMPLEX_TABLE_HTML_LEN,
            is_long_simple_table_fn=module.is_long_simple_table,
            render_long_simple_table_fn=render_long_simple_table_adapter,
            render_large_table_fallback_fn=module.render_large_table_fallback,
            logger=module.logger,
        )

    def render_standard_html_table(container, table_model, max_cols, usable_width, render_config):
        return table_runtime.render_standard_html_table_impl(
            container,
            table_model,
            max_cols,
            usable_width,
            render_config,
            remove_table_borders_fn=module.remove_table_borders,
            fill_table_cell_fn=module.fill_table_cell,
        )

    def render_large_table_fallback(container, block, table_model, render_config, usable_width):
        return table_runtime.render_large_table_fallback_impl(
            container,
            block,
            table_model,
            render_config,
            usable_width,
            compute_visual_width_fn=module.compute_visual_width,
            remove_table_borders_fn=module.remove_table_borders,
            fill_table_cell_fn=module.fill_table_cell,
            render_block_captions_fn=module.render_block_captions,
            render_block_footnotes_fn=module.render_block_footnotes,
            html_cell_cls=module.HtmlCell,
        )

    def fill_table_cell(cell, cell_model, is_header, render_config, *, compact=False):
        module.fill_table_cell_impl(
            cell,
            cell_model,
            is_header,
            render_config,
            apply_named_style_config_fn=module.apply_named_style_config,
            render_inline_html_into_paragraph_fn=module.render_inline_html_into_paragraph,
            prepare_text_fn=module.prepare_text,
            compact=compact,
        )
        if is_header:
            module.apply_table_header_cell_style(cell)

    def compute_visual_width(block, page_width, usable_width):
        ratio = min(max(block.width / max(page_width, 1.0), 0.45), 1.0)
        width_by_ratio = int(usable_width * ratio)
        min_width = int(module.Emu(module.MIN_VISUAL_WIDTH))
        return min(max(width_by_ratio, min_width), int(usable_width))

    def remove_table_borders(table):
        table_element = table._tbl
        table_properties = table_element.tblPr
        borders = table_properties.find(module.qn("w:tblBorders"))
        if borders is not None:
            table_properties.remove(borders)

        borders = module.OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right"):
            element = module.OxmlElement(f"w:{edge}")
            element.set(module.qn("w:val"), "single")
            element.set(module.qn("w:sz"), module.TABLE_OUTER_BORDER_SZ)
            element.set(module.qn("w:space"), "0")
            element.set(module.qn("w:color"), module.TABLE_BORDER_COLOR)
            borders.append(element)
        for edge in ("insideH", "insideV"):
            element = module.OxmlElement(f"w:{edge}")
            element.set(module.qn("w:val"), "single")
            element.set(module.qn("w:sz"), module.TABLE_INNER_BORDER_SZ)
            element.set(module.qn("w:space"), "0")
            element.set(module.qn("w:color"), module.TABLE_BORDER_COLOR)
            borders.append(element)
        table_properties.append(borders)

    def apply_table_header_cell_style(_cell):
        return

    def render_table_from_html(container, block, usable_width, render_config):
        module.logger.debug(
            "render html table page={} block={} bbox={} caption={} raw_html_len={}",
            block.page_idx,
            block.block_idx,
            block.bbox,
            block.captions[0] if block.captions else "N/A",
            len(block.html or ""),
        )
        prepared_table = module.prepare_html_table_model(block, render_config)
        if prepared_table is None:
            return False

        html, table_model, max_cols = prepared_table
        module.logger.debug(
            "parsed html table page={} block={} rows={} max_cols={}",
            block.page_idx,
            block.block_idx,
            len(table_model.rows),
            max_cols,
        )
        if module.render_large_table_if_needed(container, block, table_model, max_cols, len(html or ""), render_config, usable_width):
            return True
        module.render_block_captions(container, block, render_config, keep_with_next=True)
        merge_failures = module.render_standard_html_table(container, table_model, max_cols, usable_width, render_config)
        module.render_block_footnotes(container, block, render_config)
        if merge_failures > 0:
            module.logger.warning(
                "table merge fallback page={} block={} bbox={} count={} caption={}",
                block.page_idx,
                block.block_idx,
                block.bbox,
                merge_failures,
                block.captions[0] if block.captions else "N/A",
            )
        module.logger.debug(
            "rendered html table page={} block={} rows={} max_cols={} merge_failures={}",
            block.page_idx,
            block.block_idx,
            len(table_model.rows),
            max_cols,
            merge_failures,
        )
        return True

    module.render_block_annotations = render_block_annotations
    module.render_block_captions = render_block_captions
    module.render_block_footnotes = render_block_footnotes
    module.prepare_html_table_model = prepare_html_table_model
    module.render_large_table_if_needed = render_large_table_if_needed
    module.render_standard_html_table = render_standard_html_table
    module.render_large_table_fallback = render_large_table_fallback
    module.fill_table_cell = fill_table_cell
    module.compute_visual_width = compute_visual_width
    module.remove_table_borders = remove_table_borders
    module.apply_table_header_cell_style = apply_table_header_cell_style
    module.render_table_from_html = render_table_from_html
    def render_normalized_text_fragment(*args, **kwargs):
        text_module.bind_runtime(module)
        return text_module.render_normalized_text_fragment(*args, **kwargs)
    module.render_normalized_text_fragment = render_normalized_text_fragment
    return module


def load_input_adapter_module():
    _install_dependency_stubs()
    _reset_modules(
        f"{RUNTIME_PKG}.input_adapter_runtime",
        f"{RUNTIME_PKG}.text_rendering",
        f"{RUNTIME_PKG}.page_repair_runtime",
        f"{RUNTIME_PKG}.translation_runtime",
        "app.conversion.runtime_models",
    )
    runtime_models = importlib.import_module("app.conversion.runtime_models")
    text_module = importlib.import_module(f"{RUNTIME_PKG}.text_rendering")
    text_module.Block = runtime_models.Block
    text_module.SectionLayout = runtime_models.SectionLayout
    text_module.RenderConfig = runtime_models.RenderConfig
    text_module.ParagraphStyleConfig = runtime_models.ParagraphStyleConfig
    text_module.bind_runtime(text_module)
    page_repair_module = importlib.import_module(f"{RUNTIME_PKG}.page_repair_runtime")
    page_repair_module.Block = runtime_models.Block
    page_repair_module.PageData = runtime_models.PageData
    page_repair_module.MiddlePage = runtime_models.MiddlePage
    page_repair_module.VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
    page_repair_module.bind_runtime(page_repair_module)
    translation_module = importlib.import_module(f"{RUNTIME_PKG}.translation_runtime")
    module = importlib.import_module(f"{RUNTIME_PKG}.input_adapter_runtime")
    module.Block = runtime_models.Block
    module.PageData = runtime_models.PageData
    module.MiddlePage = runtime_models.MiddlePage
    module.VISUAL_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
    module.IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}
    module.normalize_formula_text = text_module.normalize_formula_text
    module.prepare_text = lambda text, render_config: text_module.prepare_text(text, render_config)
    module.LOCAL_RUN_CONFIG = {
        "input_path": "",
        "output_path": "",
        "template_path": "",
        "subscript_config": "",
        "no_template": False,
        "use_mineru_header_footer": False,
        "document_language": "auto",
        "translation_mode": "direct",
        "translation_request_output": "",
        "translation_response": "",
        "translation_model": "test-model",
        "translation_api_key": "",
        "translation_base_url": "",
        "translation_max_pages": translation_module.DEFAULT_MAX_PAGES_PER_BATCH,
        "translation_max_chars": translation_module.DEFAULT_MAX_CHARS_PER_BATCH,
    }

    def normalize_translation_mode(mode: str | None) -> str:
        normalized = str(mode or "direct").strip().lower()
        if normalized in {"none", "direct", "zh2zh", "zh_to_zh"}:
            return "direct"
        if normalized in {"en2zh", "llm_en_to_zh", "en_to_zh"}:
            return "en2zh"
        raise ValueError(f"不支持的 translation_mode: {mode}")

    def get_configured_input_path() -> Path | None:
        raw_value = str(module.LOCAL_RUN_CONFIG.get("input_path", "")).strip()
        if not raw_value:
            return None
        candidate = module.Path(raw_value).expanduser().resolve()
        return candidate if module.is_supported_input_path(candidate) else None

    def should_use_configured_input_fallback(input_path: str | None, configured_input_path: Path | None) -> bool:
        if input_path is not None or configured_input_path is None:
            return False
        current_dir = module.Path.cwd().resolve()
        if not module.looks_like_project_root(current_dir):
            return False
        if module.has_content_list_payload(current_dir):
            return False
        return module.is_supported_input_path(configured_input_path)

    def resolve_local_run_options(args: argparse.Namespace) -> dict[str, object]:
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
        translation_model = getattr(args, "translation_model", "test-model")
        translation_api_key = getattr(args, "translation_api_key", None)
        translation_base_url = getattr(args, "translation_base_url", None)
        translation_max_pages = getattr(args, "translation_max_pages", translation_module.DEFAULT_MAX_PAGES_PER_BATCH)
        translation_max_chars = getattr(args, "translation_max_chars", translation_module.DEFAULT_MAX_CHARS_PER_BATCH)

        configured_input_path = get_configured_input_path()
        if should_use_configured_input_fallback(input_path, configured_input_path):
            input_path = str(configured_input_path)
            if output_path is None:
                output_path = module.LOCAL_RUN_CONFIG.get("output_path")
            if template_path is None:
                template_path = module.LOCAL_RUN_CONFIG.get("template_path")
            if subscript_config is None:
                subscript_config = module.LOCAL_RUN_CONFIG.get("subscript_config")
            if not no_template:
                no_template = bool(module.LOCAL_RUN_CONFIG.get("no_template", False))
            if not use_mineru_header_footer:
                use_mineru_header_footer = bool(module.LOCAL_RUN_CONFIG.get("use_mineru_header_footer", False))
            if document_language == "auto":
                document_language = str(module.LOCAL_RUN_CONFIG.get("document_language", "auto") or "auto")
            translation_mode = normalize_translation_mode(
                str(module.LOCAL_RUN_CONFIG.get("translation_mode", translation_mode) or translation_mode)
            )
            if translation_request_output is None:
                configured_request_output = str(module.LOCAL_RUN_CONFIG.get("translation_request_output", "") or "")
                translation_request_output = configured_request_output or None
            if translation_response is None:
                configured_response = str(module.LOCAL_RUN_CONFIG.get("translation_response", "") or "")
                translation_response = configured_response or None
            translation_model = str(module.LOCAL_RUN_CONFIG.get("translation_model", translation_model) or translation_model)
            if translation_api_key is None:
                configured_api_key = str(module.LOCAL_RUN_CONFIG.get("translation_api_key", "") or "")
                translation_api_key = configured_api_key or None
            if translation_base_url is None:
                configured_base_url = str(module.LOCAL_RUN_CONFIG.get("translation_base_url", "") or "")
                translation_base_url = configured_base_url or None
            translation_max_pages = int(module.LOCAL_RUN_CONFIG.get("translation_max_pages", translation_max_pages) or translation_max_pages)
            translation_max_chars = int(module.LOCAL_RUN_CONFIG.get("translation_max_chars", translation_max_chars) or translation_max_chars)
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

    module.normalize_translation_mode = normalize_translation_mode
    module.get_configured_input_path = get_configured_input_path
    module.should_use_configured_input_fallback = should_use_configured_input_fallback
    module.resolve_local_run_options = resolve_local_run_options
    module.bind_runtime(module)
    return module
