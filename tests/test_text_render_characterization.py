import unittest
from types import SimpleNamespace
from unittest import mock

try:
    from .runtime_direct_loaders import load_text_render_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_text_render_module


class FakeRFonts:
    def __init__(self):
        self.values = {}

    def set(self, key, value):
        self.values[key] = value


class FakeRun:
    def __init__(self, text=""):
        self.text = text
        self.bold = None
        self.italic = None
        self.font = SimpleNamespace(
            subscript=False,
            superscript=False,
            size=None,
            name=None,
            color=SimpleNamespace(rgb=None),
        )
        self._element = SimpleNamespace(rPr=SimpleNamespace(rFonts=FakeRFonts()))


class FakeParagraphFormat:
    def __init__(self):
        self.keep_with_next = False
        self.space_before = None
        self.space_after = None
        self.line_spacing_rule = None
        self.line_spacing = None
        self.first_line_indent = None
        self.left_indent = None
        self.right_indent = None


class FakeParagraph:
    def __init__(self):
        self.text = ""
        self.style = None
        self.alignment = None
        self.paragraph_format = FakeParagraphFormat()
        self.runs = []

    def add_run(self, text=""):
        run = FakeRun(text)
        self.runs.append(run)
        return run


class TextRenderCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_text_render_module()

    def make_render_config(self, paragraph_styles=None, terminology=None):
        return self.module.RenderConfig(
            section_layout=self.module.SectionLayout(0, 0, 0, 0, 0, 0),
            use_mineru_header_footer=False,
            terminology=terminology,
            paragraph_styles=paragraph_styles or {},
        )

    def test_normalize_formula_text_converts_tex_sub_sup_to_html(self):
        normalized = self.module.normalize_formula_text("I_{OUT}^{(max)}")

        self.assertEqual(normalized, "I<sub>OUT</sub><sup>(max)</sup>")

    def test_prepare_text_applies_terminology_after_formula_normalization(self):
        terminology = mock.Mock()
        terminology.replace_text.return_value = "PIN"
        render_config = self.make_render_config(terminology=terminology)

        prepared = self.module.prepare_text("I_{OUT}^{(max)}", render_config)

        terminology.replace_text.assert_called_once_with("I<sub>OUT</sub><sup>(max)</sup>")
        self.assertEqual(prepared, "PIN")

    def test_normalize_formula_text_restores_spaced_tex_wrappers_and_symbols(self):
        normalized = self.module.normalize_formula_text(
            "\\mathsf { T } _ { \\mathsf { A } } = + 2 5 ^ { \\circ } \\mathsf { C } , "
            "\\mathsf { V } _ { \\mathsf { S } } = \\pm 5 \\vee \\mathsf { t o } \\pm 1 5 \\vee , "
            "\\mathsf { V } _ { \\mathsf { C M } } = \\mathsf { V } _ { \\mathsf { O U T } } = \\mathsf { V } _ { \\mathsf { S } } / 2"
        )

        self.assertEqual(
            normalized,
            "T<sub>A</sub> = +25°C, V<sub>S</sub> = ±5 V to ±15 V, V<sub>CM</sub> = V<sub>OUT</sub> = V<sub>S</sub> / 2",
        )

    def test_normalize_formula_text_restores_rl_subscript(self):
        normalized = self.module.normalize_formula_text(
            "\\mathsf { R } _ { \\mathsf { L } } = 1 0 \\mathsf { k } \\Omega connected to \\mathsf { V } _ { \\mathsf { S } } / 2"
        )

        self.assertEqual(normalized, "R<sub>L</sub> = 10 kΩ connected to V<sub>S</sub> / 2")

    def test_apply_named_style_config_updates_paragraph_format(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config(
            paragraph_styles={
                "Normal": self.module.ParagraphStyleConfig(
                    alignment="center",
                    line_spacing=1.5,
                    space_before=4,
                    space_after=6,
                    first_line_indent_pt=8,
                    left_indent_pt=10,
                    right_indent_pt=12,
                )
            }
        )

        self.module.apply_named_style_config(paragraph, render_config, "Normal")

        self.assertEqual(paragraph.style, "Normal")
        self.assertEqual(paragraph.alignment, self.module.WD_ALIGN_PARAGRAPH.CENTER)
        self.assertEqual(paragraph.paragraph_format.line_spacing_rule, self.module.WD_LINE_SPACING.MULTIPLE)
        self.assertEqual(paragraph.paragraph_format.line_spacing, 1.5)
        self.assertEqual(paragraph.paragraph_format.space_before, self.module.Pt(4))
        self.assertEqual(paragraph.paragraph_format.space_after, self.module.Pt(6))
        self.assertEqual(paragraph.paragraph_format.first_line_indent, self.module.Pt(8))
        self.assertEqual(paragraph.paragraph_format.left_indent, self.module.Pt(10))
        self.assertEqual(paragraph.paragraph_format.right_indent, self.module.Pt(12))

    def test_render_inline_html_into_paragraph_fallback_applies_requested_flags(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config(
            paragraph_styles={
                "Normal": self.module.ParagraphStyleConfig(font_name="SimSun", font_size=10.5)
            }
        )

        class SoupWithoutRoot:
            def find(self, _name):
                return None

        with mock.patch.object(self.module, "BeautifulSoup", return_value=SoupWithoutRoot()):
            self.module.render_inline_html_into_paragraph(
                paragraph,
                "Alpha",
                render_config=render_config,
                style_name="Normal",
                bold=True,
                italic=True,
                subscript=True,
            )

        self.assertEqual([run.text for run in paragraph.runs], ["Alpha"])
        self.assertTrue(paragraph.runs[0].bold)
        self.assertTrue(paragraph.runs[0].italic)
        self.assertTrue(paragraph.runs[0].font.subscript)
        self.assertFalse(paragraph.runs[0].font.superscript)
        self.assertEqual(paragraph.runs[0].font.name, "SimSun")
        self.assertEqual(paragraph.runs[0].font.size, self.module.Pt(10.5))

    def test_fill_title_paragraph_uses_cover_title_style_on_first_page(self):
        paragraph = FakeParagraph()
        block = self.module.Block(
            type="title",
            bbox=(0.0, 100.0, 320.0, 160.0),
            text="CWQ2P690T 型",
            page_idx=0,
        )
        render_config = self.make_render_config()

        def fake_fill_rich_text(target_paragraph, text, **_kwargs):
            target_paragraph.add_run(text)

        with mock.patch.object(self.module, "fill_rich_text", side_effect=fake_fill_rich_text) as fill_rich_text:
            self.module.fill_title_paragraph(paragraph, block, page_width=400.0, render_config=render_config)

        fill_rich_text.assert_called_once_with(
            paragraph,
            "CWQ2P690T 型",
            render_config=render_config,
            style_name="PartNumber",
            bold=True,
        )
        self.assertTrue(paragraph.paragraph_format.keep_with_next)
        self.assertEqual(paragraph.style, "PartNumber")
        self.assertEqual(paragraph.runs[0].font.size, self.module.BODY_FONT)

    def test_fill_title_paragraph_uses_heading_style_for_numbered_title(self):
        paragraph = FakeParagraph()
        block = self.module.Block(
            type="title",
            bbox=(0.0, 260.0, 320.0, 320.0),
            text="1.2 电气特性",
            page_idx=2,
        )
        render_config = self.make_render_config()

        def fake_fill_rich_text(target_paragraph, text, **_kwargs):
            target_paragraph.add_run(text)

        with mock.patch.object(self.module, "fill_rich_text", side_effect=fake_fill_rich_text) as fill_rich_text:
            self.module.fill_title_paragraph(paragraph, block, page_width=400.0, render_config=render_config)

        fill_rich_text.assert_called_once_with(
            paragraph,
            "1.2 电气特性",
            render_config=render_config,
            style_name="Heading 2",
            bold=True,
        )
        self.assertEqual(paragraph.style, "Heading 2")
        self.assertEqual(paragraph.runs[0].font.size, self.module.BODY_FONT)

    def test_fill_title_paragraph_allows_disabling_keep_with_next(self):
        paragraph = FakeParagraph()
        block = self.module.Block(
            type="title",
            bbox=(0.0, 260.0, 320.0, 320.0),
            text="1.2 电气特性",
            page_idx=2,
        )
        render_config = self.make_render_config()

        def fake_fill_rich_text(target_paragraph, text, **_kwargs):
            target_paragraph.add_run(text)

        with mock.patch.object(self.module, "fill_rich_text", side_effect=fake_fill_rich_text):
            self.module.fill_title_paragraph(
                paragraph,
                block,
                page_width=400.0,
                render_config=render_config,
                keep_with_next=False,
            )

        self.assertFalse(paragraph.paragraph_format.keep_with_next)

    def test_fill_body_paragraph_applies_normal_style_and_prepared_text(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config()

        with (
            mock.patch.object(self.module, "prepare_text", return_value="prepared body") as prepare_text,
            mock.patch.object(self.module, "fill_rich_text") as fill_rich_text,
        ):
            self.module.fill_body_paragraph(paragraph, "raw body", render_config)

        prepare_text.assert_called_once_with("raw body", render_config)
        fill_rich_text.assert_called_once_with(
            paragraph,
            "prepared body",
            render_config=render_config,
            style_name="Normal",
        )
        self.assertEqual(paragraph.style, "Normal")

    def test_fill_list_paragraph_sets_hanging_indent_and_prefixes_bullet(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config()

        with (
            mock.patch.object(self.module, "prepare_text", return_value="条目") as prepare_text,
            mock.patch.object(self.module, "fill_rich_text") as fill_rich_text,
        ):
            self.module.fill_list_paragraph(paragraph, "raw item", render_config)

        prepare_text.assert_called_once_with("raw item", render_config)
        fill_rich_text.assert_called_once_with(
            paragraph,
            "• 条目",
            render_config=render_config,
            style_name="Normal",
        )
        self.assertEqual(paragraph.style, "Normal")
        self.assertEqual(paragraph.alignment, self.module.WD_ALIGN_PARAGRAPH.LEFT)
        self.assertEqual(paragraph.paragraph_format.left_indent, self.module.Pt(10))
        self.assertEqual(paragraph.paragraph_format.first_line_indent, self.module.Pt(-10))

    def test_infer_heading_level_treats_english_appendix_as_level_one(self):
        self.assertEqual(self.module.infer_heading_level("Appendix A"), 1)

    def test_looks_like_heading_text_accepts_title_case_english_heading(self):
        self.assertTrue(self.module.looks_like_heading_text("Absolute Maximum Ratings"))

    def test_looks_like_heading_text_rejects_english_sentence(self):
        self.assertFalse(self.module.looks_like_heading_text("This section describes the device behavior"))

    def test_is_cover_title_rejects_english_contents_heading(self):
        block = self.module.Block(
            type="title",
            bbox=(0.0, 100.0, 320.0, 160.0),
            text="Contents",
            page_idx=0,
        )

        self.assertFalse(self.module.is_cover_title(block, "Contents", page_width=400.0))


if __name__ == "__main__":
    unittest.main()
