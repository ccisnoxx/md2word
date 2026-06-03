from __future__ import annotations

# tests/test_render_config_characterization.py: 固化渲染配置、术语替换和语言覆盖的加载行为。

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from .runtime_direct_loaders import load_render_config_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_render_config_module


class RenderConfigCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_render_config_module()

    def test_load_section_layout_uses_template_base_and_yaml_overrides_selected_fields(self):
        config_path = Path(__file__)
        template_document = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    top_margin=111,
                    bottom_margin=222,
                    left_margin=333,
                    right_margin=444,
                    header_distance=555,
                    footer_distance=666,
                )
            ]
        )

        with mock.patch.object(
            self.module.yaml,
            "safe_load",
            return_value={
                "page_setup": {
                    "top_margin": 2.0,
                    "header_distance": 1.2,
                }
            },
        ):
            layout = self.module.load_section_layout(template_document, config_path)

        self.assertEqual(layout.top_margin, self.module.Mm(20.0))
        self.assertEqual(layout.header_distance, self.module.Mm(12.0))
        self.assertEqual(layout.bottom_margin, 222)
        self.assertEqual(layout.left_margin, 333)
        self.assertEqual(layout.right_margin, 444)
        self.assertEqual(layout.footer_distance, 666)

    def test_load_section_layout_falls_back_to_default_layout_without_template_or_config(self):
        layout = self.module.load_section_layout(template_document=None, config_path=None)

        self.assertEqual(layout.top_margin, self.module.PAGE_MARGIN)
        self.assertEqual(layout.bottom_margin, self.module.PAGE_MARGIN)
        self.assertEqual(layout.left_margin, self.module.PAGE_MARGIN)
        self.assertEqual(layout.right_margin, self.module.PAGE_MARGIN)
        self.assertEqual(layout.header_distance, self.module.Mm(8))
        self.assertEqual(layout.footer_distance, self.module.Mm(8))

    def test_load_paragraph_styles_maps_yaml_keys_to_word_styles(self):
        config_path = Path(__file__)

        with mock.patch.object(
            self.module.yaml,
            "safe_load",
            return_value={
                "heading2": {
                    "font_name": "SimHei",
                    "font_size": 14,
                    "bold": True,
                    "alignment": "center",
                    "space_before": 6,
                    "space_after": 8,
                },
                "normal": {
                    "font_name": "SimSun",
                    "font_size": 10.5,
                    "italic": False,
                    "color": "#112233",
                    "line_spacing": 1.5,
                    "first_line_indent_pt": 12,
                    "left_indent_pt": 4,
                    "right_indent_pt": 5,
                },
            },
        ):
            styles = self.module.load_paragraph_styles(config_path)

        self.assertEqual(styles["Heading 2"].font_name, "SimHei")
        self.assertEqual(styles["Heading 2"].font_size, 14.0)
        self.assertTrue(styles["Heading 2"].bold)
        self.assertEqual(styles["Heading 2"].alignment, "center")
        self.assertEqual(styles["Heading 2"].space_before, 6.0)
        self.assertEqual(styles["Heading 2"].space_after, 8.0)

        self.assertEqual(styles["Normal"].font_name, "SimSun")
        self.assertEqual(styles["Normal"].font_size, 10.5)
        self.assertFalse(styles["Normal"].italic)
        self.assertEqual(styles["Normal"].color, "#112233")
        self.assertEqual(styles["Normal"].line_spacing, 1.5)
        self.assertEqual(styles["Normal"].first_line_indent_pt, 12.0)
        self.assertEqual(styles["Normal"].left_indent_pt, 4.0)
        self.assertEqual(styles["Normal"].right_indent_pt, 5.0)

    def test_load_table_style_maps_header_bold_flag(self):
        config_path = Path(__file__)

        with mock.patch.object(
            self.module.yaml,
            "safe_load",
            return_value={"table_style": {"header_bold": False}},
        ):
            table_style = self.module.load_table_style(config_path)

        self.assertFalse(table_style.header_bold)

    def test_load_render_config_omits_empty_terminology(self):
        layout = self.module.SectionLayout(1, 2, 3, 4, 5, 6)
        styles = {"Normal": self.module.ParagraphStyleConfig(font_name="SimSun")}
        table_style = self.module.TableStyleConfig(header_bold=False)
        empty_terminology = SimpleNamespace(rules=[])

        with (
            mock.patch.object(self.module, "find_layout_config_path", return_value=Path("/tmp/layout.yaml")),
            mock.patch.object(self.module, "load_section_layout", return_value=layout) as load_section_layout,
            mock.patch.object(self.module, "load_paragraph_styles", return_value=styles) as load_paragraph_styles,
            mock.patch.object(self.module, "load_table_style", return_value=table_style) as load_table_style,
            mock.patch.object(self.module, "TerminologyReplacer", return_value=empty_terminology) as terminology_ctor,
        ):
            render_config = self.module.load_render_config(
                template_document="template",
                subscript_config=Path("/tmp/subscripts.yaml"),
                use_mineru_header_footer=True,
            )

        terminology_ctor.assert_called_once_with(Path("/tmp/subscripts.yaml"))
        load_section_layout.assert_called_once_with("template", Path("/tmp/layout.yaml"))
        load_paragraph_styles.assert_called_once_with(Path("/tmp/layout.yaml"))
        load_table_style.assert_called_once_with(Path("/tmp/layout.yaml"))
        self.assertIs(render_config.section_layout, layout)
        self.assertIsNone(render_config.terminology)
        self.assertIs(render_config.paragraph_styles, styles)
        self.assertIs(render_config.table_style, table_style)
        self.assertTrue(render_config.use_mineru_header_footer)

    def test_load_render_config_keeps_non_empty_terminology(self):
        layout = self.module.SectionLayout(1, 2, 3, 4, 5, 6)
        terminology = SimpleNamespace(rules=["VIN"])

        with (
            mock.patch.object(self.module, "find_layout_config_path", return_value=None),
            mock.patch.object(self.module, "load_section_layout", return_value=layout),
            mock.patch.object(self.module, "load_paragraph_styles", return_value={}),
            mock.patch.object(self.module, "TerminologyReplacer", return_value=terminology),
        ):
            render_config = self.module.load_render_config(
                template_document=None,
                subscript_config=None,
                use_mineru_header_footer=False,
            )

        self.assertIs(render_config.terminology, terminology)
        self.assertFalse(render_config.use_mineru_header_footer)

    def test_terminology_replacer_sorts_rules_by_priority_then_length(self):
        config_path = Path(__file__)
        raw_config = {
            "case_sensitive": True,
            "categories": {
                "precise": {"priority": 10},
                "fallback": {"priority": 20},
            },
            "subscript_rules": {
                "fallback": {"V": "VOLT"},
                "precise": {"VIN": "PIN"},
            },
        }

        with mock.patch.object(self.module.yaml, "safe_load", return_value=raw_config):
            replacer = self.module.TerminologyReplacer(config_path)

        self.assertEqual([rule.source for rule in replacer.rules], ["VIN", "V"])
        self.assertEqual(replacer.replace_text("VIN V"), "PIN VOLT")

    def test_terminology_replacer_respects_rules_meta_apply_scope_and_case_sensitivity(self):
        config_path = Path(__file__)
        raw_config = {
            "case_sensitive": True,
            "categories": {
                "mixed": {"priority": 10},
            },
            "subscript_rules": {
                "mixed": {
                    "VIN": "V<sub>IN</sub>",
                    "vout": "V<sub>OUT</sub>",
                }
            },
            "rules_meta": {
                "VIN": {"apply_scope": "table", "case_sensitive": True, "enabled": True, "priority": 10},
                "vout": {"apply_scope": "markdown", "case_sensitive": False, "enabled": True, "priority": 20},
            },
        }

        with mock.patch.object(self.module.yaml, "safe_load", return_value=raw_config):
            replacer = self.module.TerminologyReplacer(config_path)

        self.assertEqual(replacer.replace_text("VIN vout"), "VIN V<sub>OUT</sub>")
        self.assertEqual(replacer._replace_text_for_output_mode("VIN vOut", "table"), "V<sub>IN</sub> vOut")

    def test_resolve_document_language_detects_english_from_page_content(self):
        pages = [
            self.module.PageData(
                page_idx=0,
                blocks=[
                    self.module.Block(
                        type="paragraph",
                        bbox=(0, 0, 100, 20),
                        text="Absolute Maximum Ratings Recommended Operating Conditions Device Information",
                    )
                ],
            )
        ]

        self.assertEqual(self.module.resolve_document_language(pages, preferred="auto"), "en")

    def test_resolve_document_language_honors_explicit_override(self):
        pages = [
            self.module.PageData(
                page_idx=0,
                blocks=[self.module.Block(type="paragraph", bbox=(0, 0, 100, 20), text="中文内容")],
            )
        ]

        self.assertEqual(self.module.resolve_document_language(pages, preferred="en"), "en")

    def test_apply_document_language_overrides_uses_english_font_and_indent(self):
        render_config = self.module.RenderConfig(
            section_layout=self.module.SectionLayout(1, 2, 3, 4, 5, 6),
            use_mineru_header_footer=False,
            terminology=None,
            paragraph_styles={
                "Normal": self.module.ParagraphStyleConfig(font_name="宋体", first_line_indent_pt=21.0),
                "Heading 1": self.module.ParagraphStyleConfig(font_name="宋体", bold=True),
                "Caption": self.module.ParagraphStyleConfig(font_name="宋体"),
            },
        )

        adapted = self.module.apply_document_language_overrides(render_config, "en")

        self.assertEqual(adapted.paragraph_styles["Normal"].font_name, "Arial")
        self.assertEqual(adapted.paragraph_styles["Normal"].first_line_indent_pt, 0.0)
        self.assertEqual(adapted.paragraph_styles["Heading 1"].font_name, "Arial")
        self.assertEqual(adapted.paragraph_styles["Caption"].font_name, "Arial")

    def test_apply_document_language_overrides_keeps_non_english_config_unchanged(self):
        normal_style = self.module.ParagraphStyleConfig(font_name="宋体", first_line_indent_pt=21.0)
        render_config = self.module.RenderConfig(
            section_layout=self.module.SectionLayout(1, 2, 3, 4, 5, 6),
            use_mineru_header_footer=False,
            terminology=None,
            paragraph_styles={"Normal": normal_style},
        )

        adapted = self.module.apply_document_language_overrides(render_config, "zh")

        self.assertIs(adapted, render_config)
        self.assertIs(adapted.paragraph_styles["Normal"], normal_style)


if __name__ == "__main__":
    unittest.main()
