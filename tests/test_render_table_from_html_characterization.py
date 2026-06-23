from __future__ import annotations

# tests/test_render_table_from_html_characterization.py: 固化 HTML 表格到 DOCX 的渲染 seam 行为。

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    from .runtime_direct_loaders import load_render_table_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_render_table_module


ROOT = Path(__file__).resolve().parents[1]
TEST_TMPDIR = ROOT / "tests" / ".tmp"
TEST_TMPDIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEST_TMPDIR)


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

class FakeParagraph:
    def __init__(self):
        self.text = ""
        self.rendered = None
        self.runs = []
        self.paragraph_format = types.SimpleNamespace(keep_with_next=False)

    def add_run(self, text=""):
        run = FakeRun(text)
        self.runs.append(run)
        return run


class FakeRun:
    def __init__(self, text=""):
        self.text = text
        self.breaks = []
        self.bold = False
        self.italic = False
        self.font = types.SimpleNamespace(subscript=False, superscript=False, size=None, name=None, color=types.SimpleNamespace(rgb=None))
        self._element = types.SimpleNamespace(rPr=None)

    def add_break(self, break_type):
        self.breaks.append(break_type)


class FakeCell:
    def __init__(self):
        self.vertical_alignment = None
        self.paragraphs = [FakeParagraph()]
        self._tc = FakeTc()

    def merge(self, _target):
        return self


class FakeColumn:
    def __init__(self):
        self.width = None


class FakeTrPr:
    def __init__(self):
        self.children = []

    def find(self, tag):
        for child in self.children:
            if getattr(child, "tag", None) == tag:
                return child
        return None

    def append(self, child):
        self.children.append(child)

    def remove(self, child):
        self.children.remove(child)


class FakeTcPr(FakeTrPr):
    pass


class FakeTc:
    def __init__(self):
        self.tcPr = FakeTcPr()

    def get_or_add_tcPr(self):
        return self.tcPr


class FakeTblPr(FakeTrPr):
    pass


class FakeTbl:
    def __init__(self):
        self.tblPr = FakeTblPr()


class FakeTr:
    def __init__(self):
        self.trPr = FakeTrPr()

    def get_or_add_trPr(self):
        return self.trPr


class FakeRow:
    def __init__(self, cells):
        self.cells = cells
        self._tr = FakeTr()


class FakeTable:
    def __init__(self, rows, cols):
        self.alignment = None
        self.autofit = None
        self.columns = [FakeColumn() for _ in range(cols)]
        self._cells = [[FakeCell() for _ in range(cols)] for _ in range(rows)]
        self.rows = [FakeRow(cells) for cells in self._cells]
        self._tbl = FakeTbl()

    def cell(self, row_idx, col_idx):
        return self._cells[row_idx][col_idx]


class FakeContainer:
    def __init__(self):
        self.tables = []
        self.paragraphs = []

    def add_table(self, rows, cols):
        table = FakeTable(rows, cols)
        self.tables.append(table)
        return table

    def add_paragraph(self):
        paragraph = FakeParagraph()
        self.paragraphs.append(paragraph)
        return paragraph


class RenderTableFromHtmlCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_render_table_module()

    def make_block(self, html="<table></table>", captions=None, footnotes=None):
        return self.module.Block(
            type="table",
            bbox=(0.0, 0.0, 100.0, 100.0),
            html=html,
            captions=captions or [],
            footnotes=footnotes or [],
            page_idx=0,
            block_idx=0,
        )

    def make_render_config(self, terminology=None):
        return self.module.RenderConfig(
            section_layout=self.module.SectionLayout(1000, 1000, 0, 0, 0, 0),
            use_mineru_header_footer=False,
            terminology=terminology,
            paragraph_styles={},
        )

    def test_returns_false_when_html_table_cannot_be_parsed(self):
        container = FakeContainer()
        block = self.make_block()
        render_config = self.make_render_config()

        with mock.patch.object(self.module, "parse_html_table", return_value=None):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertFalse(rendered)
        self.assertEqual(container.tables, [])
        self.assertEqual(container.paragraphs, [])

    def test_later_th_cells_are_treated_as_table_headers(self):
        container = FakeContainer()
        block = self.make_block(
            html="<table><tr><td colspan=\"2\">Group</td></tr><tr><th>PARAMETER</th><th>VALUE</th></tr></table>"
        )
        render_config = self.make_render_config()
        seen: list[tuple[str, bool]] = []

        def record_fill(cell, cell_model, is_header, _render_config, *, compact=False):
            seen.append((cell_model.text, is_header))

        with mock.patch.object(self.module, "fill_table_cell", side_effect=record_fill):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        self.assertIn(("Group", True), seen)
        self.assertIn(("PARAMETER", True), seen)
        self.assertIn(("VALUE", True), seen)

    def test_standard_table_marks_rows_for_word_pagination(self):
        container = FakeContainer()
        block = self.make_block(html="<table><tr><th>H</th></tr><tr><td>A</td></tr></table>")
        render_config = self.make_render_config()

        rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        self.assertEqual(len(container.tables), 1)
        first_row_properties = container.tables[0].rows[0]._tr.trPr
        second_row_properties = container.tables[0].rows[1]._tr.trPr
        self.assertIsNotNone(first_row_properties.find("w:tblHeader"))
        self.assertIsNotNone(first_row_properties.find("w:cantSplit"))
        self.assertIsNotNone(second_row_properties.find("w:cantSplit"))

    def test_large_simple_table_uses_chunk_renderer(self):
        container = FakeContainer()
        block = self.make_block()
        render_config = self.make_render_config()
        table_model = self.module.HtmlTable(
            rows=[[self.module.HtmlCell("h1"), self.module.HtmlCell("h2"), self.module.HtmlCell("h3")]]
            + [[self.module.HtmlCell("a"), self.module.HtmlCell("b"), self.module.HtmlCell("c")] for _ in range(401)]
        )

        with (
            mock.patch.object(self.module, "parse_html_table", return_value=table_model),
            mock.patch.object(self.module, "render_long_simple_table") as render_long_simple_table,
            mock.patch.object(self.module, "render_large_table_fallback") as render_large_table_fallback,
        ):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        render_long_simple_table.assert_called_once()
        self.assertEqual(
            render_long_simple_table.call_args.args[:5],
            (container, block, table_model, render_config, 8000),
        )
        render_large_table_fallback.assert_not_called()

    def test_split_long_simple_table_rows_uses_word_capacity_without_source_page_scaling(self):
        table_long_renderer = self.module.table_long_renderer
        render_config = self.make_render_config()
        header_row = [self.module.HtmlCell("H1"), self.module.HtmlCell("H2"), self.module.HtmlCell("H3")]
        body_rows = [
            [self.module.HtmlCell("A"), self.module.HtmlCell("B"), self.module.HtmlCell("C")]
            for _ in range(6)
        ]

        with (
            mock.patch.object(table_long_renderer, "estimate_row_height", return_value=5.0),
            mock.patch.object(table_long_renderer, "estimate_long_table_page_capacity", side_effect=[10.0, 20.0, 20.0]),
        ):
            chunks = table_long_renderer.split_long_simple_table_rows(
                header_row=header_row,
                body_rows=body_rows,
                render_config=render_config,
                usable_width=6508750,
                first_page_height=300.0,
                continuation_heights=[300.0, 300.0],
                get_style_config_fn=self.module.get_style_config,
            )

        self.assertEqual([len(chunk) for chunk in chunks], [2, 4])

    def test_render_long_simple_table_uses_single_continuous_table_with_repeating_header(self):
        container = FakeContainer()
        render_config = self.make_render_config()
        block = self.make_block(captions=["表 A.1"], footnotes=["注 1"])
        block.continuation_heights = [800.0, 800.0]
        table_model = self.module.HtmlTable(
            rows=[[self.module.HtmlCell("H1"), self.module.HtmlCell("H2"), self.module.HtmlCell("H3")]]
            + [[self.module.HtmlCell("A"), self.module.HtmlCell("B"), self.module.HtmlCell("C")] for _ in range(5)]
        )

        def record_fill(cell, cell_model, is_header, _render_config):
            cell.paragraphs[0].rendered = (cell_model.text, is_header)

        def record_rich_text(paragraph, text, **_kwargs):
            paragraph.rendered = text

        self.module.render_long_simple_table(
            container,
            block,
            table_model,
            render_config,
            usable_width=9000,
            apply_named_style_config_fn=lambda *_args, **_kwargs: None,
            fill_rich_text_fn=record_rich_text,
            prepare_text_fn=lambda text, _config: text,
            fill_table_cell_fn=record_fill,
            remove_table_borders_fn=lambda _table: None,
            get_style_config_fn=self.module.get_style_config,
        )

        self.assertEqual(len(container.tables), 1)
        self.assertEqual(len(container.tables[0].rows), 6)
        self.assertEqual([paragraph.rendered for paragraph in container.paragraphs], ["表 A.1", "注 1"])
        self.assertIsNotNone(container.tables[0].rows[0]._tr.trPr.find("w:tblHeader"))
        self.assertTrue(
            all(row._tr.trPr.find("w:cantSplit") is not None for row in container.tables[0].rows)
        )

    def test_remove_table_borders_applies_printable_grid(self):
        table = FakeTable(rows=2, cols=2)

        self.module.remove_table_borders(table)

        borders = table._tbl.tblPr.find("w:tblBorders")
        self.assertIsNotNone(borders)
        border_map = {child.tag: child.attrs for child in borders.children}
        self.assertEqual(border_map["w:top"]["w:val"], "single")
        self.assertEqual(border_map["w:top"]["w:sz"], self.module.TABLE_OUTER_BORDER_SZ)
        self.assertEqual(border_map["w:insideH"]["w:val"], "single")
        self.assertEqual(border_map["w:insideH"]["w:sz"], self.module.TABLE_INNER_BORDER_SZ)

    def test_fill_table_cell_keeps_header_cell_plain(self):
        cell = FakeCell()
        render_config = self.make_render_config()

        with mock.patch.object(self.module, "fill_table_cell_impl") as fill_table_cell_impl:
            self.module.fill_table_cell(cell, self.module.HtmlCell("H1"), True, render_config)

        shading = cell._tc.tcPr.find("w:shd")
        self.assertIsNone(shading)
        self.assertFalse(self.module.TABLE_HEADER_FILL)
        self.assertFalse(fill_table_cell_impl.call_args.kwargs["compact"])

    def test_split_long_simple_table_rows_without_source_pages_keeps_default_packing(self):
        table_long_renderer = self.module.table_long_renderer
        render_config = self.make_render_config()
        header_row = [self.module.HtmlCell("H1"), self.module.HtmlCell("H2"), self.module.HtmlCell("H3")]
        body_rows = [
            [self.module.HtmlCell("A"), self.module.HtmlCell("B"), self.module.HtmlCell("C")]
            for _ in range(6)
        ]

        with (
            mock.patch.object(table_long_renderer, "estimate_row_height", return_value=5.0),
            mock.patch.object(table_long_renderer, "estimate_long_table_page_capacity", side_effect=[20.0, 20.0]),
        ):
            chunks = table_long_renderer.split_long_simple_table_rows(
                header_row=header_row,
                body_rows=body_rows,
                render_config=render_config,
                usable_width=6508750,
                first_page_height=300.0,
                continuation_heights=[],
                get_style_config_fn=self.module.get_style_config,
                caption_text=None,
            )

        self.assertEqual([len(chunk) for chunk in chunks], [4, 2])

    def test_estimate_long_table_page_capacity_subtracts_caption_height(self):
        table_long_renderer = self.module.table_long_renderer
        render_config = self.make_render_config()
        header_row = [self.module.HtmlCell("H1"), self.module.HtmlCell("H2"), self.module.HtmlCell("H3")]

        with (
            mock.patch.object(table_long_renderer, "estimate_row_height", return_value=10.0),
            mock.patch.object(table_long_renderer, "estimate_paragraph_height", return_value=20.0),
        ):
            capacity = table_long_renderer.estimate_long_table_page_capacity(
                300.0,
                header_row,
                render_config,
                usable_width=6508750,
                is_first_page=False,
                get_style_config_fn=self.module.get_style_config,
                caption_text="表 A.1",
            )

        base_page_height = table_long_renderer.emu_to_pt(
            int(table_long_renderer.A4_HEIGHT - render_config.section_layout.top_margin - render_config.section_layout.bottom_margin)
        )
        expected = max(
            base_page_height - table_long_renderer.DEFAULT_LONG_TABLE_CONT_PAGE_RESERVE_PT - 10.0 - 20.0,
            10.0 + 24,
        )
        self.assertEqual(capacity, expected)

    def test_large_complex_table_uses_fallback_renderer(self):
        container = FakeContainer()
        block = self.make_block(html="x" * (self.module.MAX_COMPLEX_TABLE_HTML_LEN + 1))
        render_config = self.make_render_config()
        table_model = self.module.HtmlTable(rows=[[self.module.HtmlCell("h1"), self.module.HtmlCell("h2"), self.module.HtmlCell("h3"), self.module.HtmlCell("h4")]])

        with (
            mock.patch.object(self.module, "parse_html_table", return_value=table_model),
            mock.patch.object(self.module, "is_long_simple_table", return_value=False),
            mock.patch.object(self.module, "render_long_simple_table") as render_long_simple_table,
            mock.patch.object(self.module, "render_large_table_fallback") as render_large_table_fallback,
        ):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        render_large_table_fallback.assert_called_once_with(container, block, table_model, render_config, 8000)
        render_long_simple_table.assert_not_called()

    def test_small_table_renders_standard_table_and_appends_caption_and_footnote(self):
        container = FakeContainer()
        block = self.make_block(captions=["Caption 1"], footnotes=["Note 1"])
        render_config = self.make_render_config()
        table_model = self.module.HtmlTable(
            rows=[
                [self.module.HtmlCell("H1"), self.module.HtmlCell("H2")],
                [self.module.HtmlCell("A1"), self.module.HtmlCell("A2")],
            ]
        )
        fill_calls = []

        def record_fill(cell, cell_model, is_header, _render_config, *, compact=False):
            fill_calls.append((cell_model.text, is_header))

        def record_rich_text(paragraph, text, **_kwargs):
            paragraph.rendered = text

        with (
            mock.patch.object(self.module, "parse_html_table", return_value=table_model),
            mock.patch.object(self.module, "remove_table_borders"),
            mock.patch.object(self.module, "fill_table_cell", side_effect=record_fill),
            mock.patch.object(self.module, "apply_named_style_config"),
            mock.patch.object(self.module, "fill_rich_text", side_effect=record_rich_text),
            mock.patch.object(self.module, "prepare_text", side_effect=lambda text, _cfg: text),
            mock.patch.object(self.module, "Emu", side_effect=lambda value: int(value)),
            mock.patch.object(self.module, "Mm", side_effect=lambda value: int(float(value) * 1000)),
        ):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        self.assertEqual(len(container.tables), 1)
        self.assertEqual(len(container.tables[0].columns), 2)
        self.assertEqual(fill_calls, [("H1", True), ("H2", True), ("A1", False), ("A2", False)])
        self.assertEqual([paragraph.rendered for paragraph in container.paragraphs], ["Caption 1", "Note 1"])
        self.assertTrue(container.paragraphs[0].paragraph_format.keep_with_next)

    def test_five_column_datasheet_table_uses_wide_description_column(self):
        widths = self.module.compute_table_column_widths(5, 10_000)

        self.assertEqual(sum(widths), 10_000)
        self.assertGreater(widths[1], widths[0] * 3)
        self.assertGreater(widths[1], widths[4] * 3)

    def test_terminology_replacement_runs_before_table_parsing(self):
        container = FakeContainer()
        block = self.make_block(html="<table>RAW</table>")
        terminology = mock.Mock()
        terminology.replace_html.return_value = "<table>REPLACED</table>"
        render_config = self.make_render_config(terminology=terminology)
        table_model = self.module.HtmlTable(rows=[[self.module.HtmlCell("H1")]])

        with (
            mock.patch.object(self.module, "parse_html_table", return_value=table_model) as parse_html_table,
            mock.patch.object(self.module, "remove_table_borders"),
            mock.patch.object(self.module, "fill_table_cell"),
            mock.patch.object(self.module, "apply_named_style_config"),
            mock.patch.object(self.module, "fill_rich_text"),
            mock.patch.object(self.module, "prepare_text", side_effect=lambda text, _cfg: text),
            mock.patch.object(self.module, "Emu", side_effect=lambda value: int(value)),
            mock.patch.object(self.module, "Mm", side_effect=lambda value: int(float(value) * 1000)),
        ):
            rendered = self.module.render_table_from_html(container, block, usable_width=8000, render_config=render_config)

        self.assertTrue(rendered)
        terminology.replace_html.assert_called_once_with("<table>RAW</table>")
        parse_html_table.assert_called_once_with("<table>REPLACED</table>")

    def test_render_normalized_text_fragment_handles_sub_sup_without_beautifulsoup(self):
        paragraph = FakeParagraph()

        with (
            mock.patch.object(self.module, "apply_run_defaults"),
            mock.patch.object(self.module, "BeautifulSoup", side_effect=AssertionError("BeautifulSoup should not be called for simple sub/sup fragments")),
        ):
            self.module.render_normalized_text_fragment(
                paragraph,
                "V<sub>IN</sub><sup>max</sup>",
                style_config=None,
                bold=False,
                italic=False,
                subscript=False,
                superscript=False,
            )

        self.assertEqual([run.text for run in paragraph.runs], ["V", "IN", "max"])
        self.assertFalse(paragraph.runs[0].font.subscript)
        self.assertTrue(paragraph.runs[1].font.subscript)
        self.assertFalse(paragraph.runs[1].font.superscript)
        self.assertTrue(paragraph.runs[2].font.superscript)

    def test_render_normalized_text_fragment_falls_back_for_unknown_markup(self):
        paragraph = FakeParagraph()
        fake_root = object()

        class FallbackSoup:
            def find(self, _name):
                return fake_root

        with (
            mock.patch.object(self.module, "apply_run_defaults"),
            mock.patch.object(self.module, "BeautifulSoup", return_value=FallbackSoup()) as soup_ctor,
            mock.patch.object(self.module, "render_markup_children") as render_markup_children,
        ):
            self.module.render_normalized_text_fragment(
                paragraph,
                "A<b>B</b>",
                style_config=None,
                bold=False,
                italic=False,
                subscript=False,
                superscript=False,
            )

        soup_ctor.assert_called_once()
        render_markup_children.assert_called_once_with(
            fake_root,
            paragraph,
            style_config=None,
            bold=False,
            italic=False,
            subscript=False,
            superscript=False,
        )


if __name__ == "__main__":
    unittest.main()
