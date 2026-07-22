from __future__ import annotations

# tests/test_text_render_characterization.py: 固化 DOCX 文本、标题、列表和公式归一化行为。

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


class FakeRunProperties:
    def __init__(self):
        self.rFonts = FakeRFonts()

    def get_or_add_rFonts(self):
        return self.rFonts


class FakeRunElement:
    def __init__(self):
        self.rPr = FakeRunProperties()

    def get_or_add_rPr(self):
        return self.rPr


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
        self._element = FakeRunElement()


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
        self.tab_stops = SimpleNamespace(calls=[], add_tab_stop=self._add_tab_stop)

    def _add_tab_stop(self, *args):
        self.tab_stops.calls.append(args)


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


def font_slot_values(run):
    return {
        key.rsplit("}", 1)[-1].rsplit(":", 1)[-1]: value
        for key, value in run._element.rPr.rFonts.values.items()
    }


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

    def test_normalize_formula_text_converts_overline_without_latex_residue(self):
        self.assertEqual(self.module.normalize_formula_text(r"Y=\overline{A}"), "Y=A̅")
        self.assertEqual(self.module.normalize_formula_text(r"\overline{Y = \overline{A}}"), "Y = A̅")

    def test_normalize_formula_text_converts_leading_superscript_marker(self):
        self.assertEqual(self.module.normalize_formula_text(r"^{(1)(2)}"), "<sup>(1)(2)</sup>")

    def test_fill_toc_entry_paragraph_uses_dot_leader_tab_for_page_number(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config()

        self.module.fill_toc_entry_paragraph(paragraph, "特性 .... 1", render_config)

        self.assertEqual([run.text for run in paragraph.runs], ["特性", "\t1"])
        self.assertEqual(len(paragraph.paragraph_format.tab_stops.calls), 1)

    def test_fill_toc_entry_paragraph_uses_supplied_usable_width_for_tab_stop(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config()

        self.module.fill_toc_entry_paragraph(paragraph, "1 FEATURES .... 1", render_config, 123456)

        self.assertEqual(paragraph.paragraph_format.tab_stops.calls[0], (123456,))

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

    def test_apply_run_defaults_writes_independent_font_slots(self):
        run = FakeRun("中文 Latin العربية")
        style = self.module.ParagraphStyleConfig(
            font_name="SimSun",
            western_font_name="Arial",
            complex_script_font_name="Times New Roman",
        )

        self.module.apply_run_defaults(run, style)

        self.assertEqual(run.font.name, "Arial")
        self.assertEqual(
            font_slot_values(run),
            {
                "eastAsia": "SimSun",
                "ascii": "Arial",
                "hAnsi": "Arial",
                "cs": "Times New Roman",
            },
        )

    def test_apply_run_defaults_keeps_legacy_single_font_behavior(self):
        run = FakeRun("中文 Latin العربية")

        self.module.apply_run_defaults(run, self.module.ParagraphStyleConfig(font_name="SimSun"))

        self.assertEqual(run.font.name, "SimSun")
        self.assertEqual(set(font_slot_values(run).values()), {"SimSun"})
        self.assertEqual(set(font_slot_values(run)), {"eastAsia", "ascii", "hAnsi", "cs"})

    def test_apply_run_defaults_preserves_explicit_empty_font_inheritance(self):
        run = FakeRun("中文 Latin العربية")
        style = self.module.ParagraphStyleConfig(
            font_name="SimSun",
            western_font_name="",
            complex_script_font_name="",
        )

        self.module.apply_run_defaults(run, style)

        self.assertIsNone(run.font.name)
        self.assertEqual(font_slot_values(run), {"eastAsia": "SimSun"})

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

    def test_fill_list_paragraph_uses_word_numbering_without_manual_marker(self):
        paragraph = FakeParagraph()
        render_config = self.make_render_config()

        with (
            mock.patch.object(self.module, "apply_bullet_numbering") as apply_bullet_numbering,
            mock.patch.object(self.module, "prepare_text", return_value="条目") as prepare_text,
            mock.patch.object(self.module, "fill_rich_text") as fill_rich_text,
        ):
            self.module.fill_list_paragraph(paragraph, "raw item", render_config, level=1)

        prepare_text.assert_called_once_with("raw item", render_config)
        apply_bullet_numbering.assert_called_once_with(paragraph, level=1)
        fill_rich_text.assert_called_once_with(
            paragraph,
            "条目",
            render_config=render_config,
            style_name="Normal",
        )
        self.assertEqual(paragraph.style, "Normal")
        self.assertEqual(paragraph.alignment, self.module.WD_ALIGN_PARAGRAPH.LEFT)
        self.assertEqual(paragraph.paragraph_format.space_before, self.module.Pt(0))
        self.assertEqual(paragraph.paragraph_format.space_after, self.module.Pt(0))
        self.assertEqual(paragraph.paragraph_format.line_spacing_rule, self.module.WD_LINE_SPACING.MULTIPLE)
        self.assertEqual(paragraph.paragraph_format.line_spacing, 1.0)
        self.assertEqual(paragraph.paragraph_format.left_indent, self.module.Pt(24))
        self.assertEqual(paragraph.paragraph_format.first_line_indent, self.module.Pt(-9))

    def test_normalize_formula_text_converts_sqrt_and_compacts_units(self):
        self.assertEqual(self.module.normalize_formula_text(r"nV/ \sqrt{Hz}"), "nV/√Hz")

    def test_normalize_formula_text_converts_unbraced_circ_and_microsecond_units(self):
        normalized = self.module.normalize_formula_text(r"$T_A = +25^\circ C$, $5 \mu s$")

        self.assertEqual(normalized, "T<sub>A</sub> = +25°C, 5 μs")

    def test_normalize_formula_text_accepts_double_escaped_datasheet_tex_commands(self):
        cases = {
            r"$\\sqrt{Hz}$": "√Hz",
            r"$5 \\mu s$": "5 μs",
            r"$R_{\\theta JC(top)}$": "R<sub>θJC(top)</sub>",
            r"nV/\\sqrt{Hz}": "nV/√Hz",
            r"$\\mathrm { \\mu V / ^ { \\circ } C }$": "μV/°C",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(self.module.normalize_formula_text(raw), expected)

    def test_normalize_list_item_keeps_negative_temperature_text(self):
        self.assertEqual(self.module.normalize_list_item("• Low noise"), "Low noise")
        self.assertEqual(self.module.normalize_list_item("-40°C operation"), "-40°C operation")
        self.assertTrue(self.module.is_list_item_text("• Low noise"))
        self.assertTrue(self.module.is_list_item_text("- nested item"))
        self.assertFalse(self.module.is_list_item_text("-40°C operation"))
        self.assertEqual(self.module.infer_list_item_level("– nested item"), 1)

    def test_infer_heading_level_treats_english_appendix_as_level_one(self):
        self.assertEqual(self.module.infer_heading_level("Appendix A"), 1)

    def test_looks_like_heading_text_accepts_title_case_english_heading(self):
        self.assertTrue(self.module.looks_like_heading_text("Absolute Maximum Ratings"))

    def test_looks_like_heading_text_rejects_english_sentence(self):
        self.assertFalse(self.module.looks_like_heading_text("This section describes the device behavior"))
        self.assertFalse(self.module.looks_like_heading_text("1.A is not a numbered section heading"))

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
