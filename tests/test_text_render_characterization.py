"""直接验证正式 renderer 复用的公式、列表与标题语义规则。"""

from __future__ import annotations

import unittest

from app.conversion.docx_rules import text_semantics


class TextRenderCharacterizationTests(unittest.TestCase):
    def test_normalize_formula_text_converts_tex_sub_sup_to_html(self):
        normalized = text_semantics.normalize_formula_text("I_{OUT}^{(max)}")

        self.assertEqual(normalized, "I<sub>OUT</sub><sup>(max)</sup>")

    def test_normalize_formula_text_restores_spaced_tex_wrappers_and_symbols(self):
        normalized = text_semantics.normalize_formula_text(
            "\\mathsf { T } _ { \\mathsf { A } } = + 2 5 ^ { \\circ } \\mathsf { C } , "
            "\\mathsf { V } _ { \\mathsf { S } } = \\pm 5 \\vee \\mathsf { t o } \\pm 1 5 \\vee , "
            "\\mathsf { V } _ { \\mathsf { C M } } = \\mathsf { V } _ { \\mathsf { O U T } } = \\mathsf { V } _ { \\mathsf { S } } / 2"
        )

        self.assertEqual(
            normalized,
            "T<sub>A</sub> = +25°C, V<sub>S</sub> = ±5 V to ±15 V, V<sub>CM</sub> = V<sub>OUT</sub> = V<sub>S</sub> / 2",
        )

    def test_normalize_formula_text_restores_rl_subscript(self):
        normalized = text_semantics.normalize_formula_text(
            "\\mathsf { R } _ { \\mathsf { L } } = 1 0 \\mathsf { k } \\Omega connected to \\mathsf { V } _ { \\mathsf { S } } / 2"
        )

        self.assertEqual(normalized, "R<sub>L</sub> = 10 kΩ connected to V<sub>S</sub> / 2")

    def test_normalize_formula_text_converts_overline_without_latex_residue(self):
        self.assertEqual(text_semantics.normalize_formula_text(r"Y=\overline{A}"), "Y=A̅")
        self.assertEqual(text_semantics.normalize_formula_text(r"\overline{Y = \overline{A}}"), "Y = A̅")

    def test_normalize_formula_text_converts_leading_superscript_marker(self):
        self.assertEqual(text_semantics.normalize_formula_text(r"^{(1)(2)}"), "<sup>(1)(2)</sup>")

    def test_normalize_formula_text_converts_sqrt_and_compacts_units(self):
        self.assertEqual(text_semantics.normalize_formula_text(r"nV/ \sqrt{Hz}"), "nV/√Hz")

    def test_normalize_formula_text_converts_unbraced_circ_and_microsecond_units(self):
        normalized = text_semantics.normalize_formula_text(r"$T_A = +25^\circ C$, $5 \mu s$")

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
                self.assertEqual(text_semantics.normalize_formula_text(raw), expected)

    def test_normalize_formula_text_preserves_double_backslashes_outside_supported_tex(self):
        self.assertEqual(text_semantics.normalize_formula_text(r"共享路径 \\server\datasheet"), r"共享路径 \\server\datasheet")

    def test_normalize_list_item_keeps_negative_temperature_text(self):
        self.assertEqual(text_semantics.normalize_list_item("• Low noise"), "Low noise")
        self.assertEqual(text_semantics.normalize_list_item("-40°C operation"), "-40°C operation")
        self.assertTrue(text_semantics.is_list_item_text("• Low noise"))
        self.assertTrue(text_semantics.is_list_item_text("- nested item"))
        self.assertFalse(text_semantics.is_list_item_text("-40°C operation"))
        self.assertEqual(text_semantics.infer_list_item_level("– nested item"), 1)

    def test_infer_heading_level_treats_english_appendix_as_level_one(self):
        self.assertEqual(text_semantics.infer_heading_level("Appendix A"), 1)

    def test_looks_like_heading_text_accepts_title_case_english_heading(self):
        self.assertTrue(text_semantics.looks_like_heading_text("Absolute Maximum Ratings"))
        self.assertTrue(text_semantics.looks_like_heading_text("Overview"))

    def test_looks_like_heading_text_rejects_english_sentence(self):
        self.assertFalse(text_semantics.looks_like_heading_text("This section describes the device behavior"))
        self.assertFalse(text_semantics.looks_like_heading_text("1.A is not a numbered section heading"))
        self.assertFalse(text_semantics.looks_like_heading_text("图 13 显示了输出响应"))
        self.assertFalse(text_semantics.looks_like_heading_text("表 1"))
        self.assertFalse(text_semantics.looks_like_heading_text("Figure 3 Output Response"))
        self.assertFalse(text_semantics.looks_like_heading_text("• Low noise"))
        self.assertFalse(text_semantics.looks_like_heading_text("Contents"))
        self.assertFalse(text_semantics.looks_like_heading_text("Note: E=mc²"))


if __name__ == "__main__":
    unittest.main()
